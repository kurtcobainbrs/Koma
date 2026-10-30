"""Exercise Flet's post-event dispatch, including its implicit ancestor update."""
import flet as ft
from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock, patch

from flet.controls.context import _context_page, _update_behavior_context_var
from flet.messaging.session import Session
from koma.ui.event_updates import explicit_updates
from tests.test_storyboard import StoryboardTests


class EventUpdatesTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.policy_token = _update_behavior_context_var.set(None)
        ft.context.reset_auto_update()
        self.fixture = StoryboardTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.view = self.fixture.view()
        self.session = Session(Mock())
        self.page = self.session.page
        self.context_token = _context_page.set(self.page)

    async def asyncTearDown(self):
        _update_behavior_context_var.reset(self.policy_token)
        _context_page.reset(self.context_token)

    async def dispatch(self, control, name, data):
        self.page.add(control)
        # Each client event is dispatched in a fresh task by Flet.
        import asyncio
        ft.context.reset_auto_update()
        ft.context.enable_auto_update()
        with patch.object(self.session, 'patch_control', wraps=self.session.patch_control) as updates, \
                patch.object(self.session, 'error') as errors:
            await asyncio.create_task(self.session.dispatch_event(control._i, name, data))
        errors.assert_not_called()
        return updates.call_count

    async def test_hover_reproduces_old_ancestor_update_and_suppresses_it(self):
        ws = self.view.workspace
        raw = ws.hover.__wrapped__.__get__(ws)
        event = {'l': {'x': 20, 'y': 30}, 'g': {'x': 20, 'y': 30},
            'k': 'mouse', 'ts': 0, 'dev': 0, 'ps': 0, 'pMin': 0, 'pMax': 1,
            'dist': 0, 'distMax': 0, 'size': 0, 'rMj': 0, 'rMn': 0,
            'rMin': 0, 'rMax': 0, 'or': 0, 'tilt': 0}
        original_links_hover = ws.links.hover.__wrapped__.__get__(ws.links)
        with patch.object(ws.links, 'hover', original_links_hover):
            self.assertGreater(await self.dispatch(ft.GestureDetector(on_hover=raw), 'hover', event), 0)
        self.assertEqual(await self.dispatch(ft.GestureDetector(on_hover=ws.hover), 'hover', event), 0)
        self.assertEqual(ws.context_menu.pointer, (20, 30))

    async def test_repeated_pointer_events_do_not_accumulate_ancestor_updates(self):
        control = ft.GestureDetector(on_pan_down=self.view.workspace.box_selection.press)
        self.page.add(control)
        import asyncio
        ft.context.reset_auto_update()
        ft.context.enable_auto_update()
        with patch.object(self.session, 'patch_control', wraps=self.session.patch_control) as updates, \
                patch.object(self.session, 'error') as errors:
            for x in range(50):
                await asyncio.create_task(self.session.dispatch_event(control._i, 'pan_down',
                    {'l': {'x': x, 'y': 30}, 'g': {'x': x, 'y': 30}}))
        errors.assert_not_called()
        updates.assert_not_called()
        self.assertEqual(self.view.workspace.box_selection.pending[0], (49, 30))

    async def test_canvas_and_animatic_key_release_do_not_patch_the_page(self):
        for controller in (self.view.workspace.navigation, self.view.player):
            control = ft.KeyboardListener(content=ft.Container(), on_key_up=controller.key_up)
            self.assertEqual(await self.dispatch(control, 'key_up', {'key': 'Shift Left'}), 0)

    async def test_explicit_async_update_works_and_policy_does_not_leak(self):
        label = ft.Text('Antes')
        self.page.add(label)

        @explicit_updates
        async def edit(e):
            label.value = 'Depois'
            self.page.update(label)

        self.assertEqual(await self.dispatch(ft.TextButton('Editar', on_click=edit), 'click', {}), 1)
        self.assertEqual(label.value, 'Depois')
        # A separate, ordinary Flet event still has its default auto-update.
        self.assertGreater(await self.dispatch(ft.TextButton('Outro', on_click=lambda e: None), 'click', {}), 0)
