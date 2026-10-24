"""Seleção por caixa, modificadores e operações de grupo, sem leituras de imagens."""

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as Data
from unittest.mock import AsyncMock, Mock, patch

import flet as ft
import msgpack
from flet.controls.base_control import BaseControl
from flet.controls.object_patch import ObjectPatch
from flet.messaging.protocol import configure_encode_object_for_msgpack

from koma.preferences import AppPreferences
from koma.documents.session import DocumentSession
from koma.editor.geometry import NODE_WIDTH, NODE_HEIGHT, GRID_STEP
from koma.editor.models import Storyboard, StoryFrame
from koma.editor.view import StoryboardView


def finish(coroutine):
    try:
        coroutine.send(None)
    except StopIteration as result:
        return result.value
    raise AssertionError('Suspensão inesperada')


async def immediate(function, *args):
    return function(*args)


class StoryboardSelectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        worker = patch('asyncio.to_thread', side_effect=immediate)
        worker.start()
        self.addCleanup(worker.stop)
        self.view = StoryboardView(Mock(), DocumentSession(self.root), AppPreferences(self.root))
        self.addCleanup(self.view.session.close)
        self.frames = (StoryFrame(title='A', x=0, y=0), StoryFrame(title='B', x=480, y=0),
                       StoryFrame(title='C', x=0, y=600))
        self.view.session.board = self.view.session.saved_board = Storyboard(frames=self.frames)
        self.view.store.save(self.view.session.board)
        finish(self.view.activate())
        self.workspace = self.view.workspace
        self.nav = self.workspace.navigation

    def point(self, x, y):
        return Data(local_position=Data(x=x, y=y))

    def box(self, ids, reverse=False):
        nodes = [self.view.cards[key].content for key in ids]
        start = self.point(min(node.left for node in nodes) - 10, min(node.top for node in nodes) - 10)
        end = self.point(max(node.left + NODE_WIDTH for node in nodes) + 10,
                         max(node.top + NODE_HEIGHT for node in nodes) + 10)
        if reverse:
            start, end = end, start
        self.workspace.box_selection.press(start)
        finish(self.nav.background_click(start))
        self.workspace.box_selection.begin(start)
        self.workspace.box_selection.update(end)
        return self.workspace.box_selection

    def test_box_selects_in_both_directions_without_saving_or_reading_images(self):
        before = self.view.store.path.read_bytes()
        a, b, c = self.frames
        with patch.object(self.view.store, 'save') as save:
            for reverse in (False, True):
                box = self.box({a.id, b.id}, reverse)
                self.assertEqual(self.nav.selection.ids, {a.id, b.id})
                self.assertTrue(box.overlay.visible)
                box.end()
                self.assertFalse(box.overlay.visible)
                self.assertTrue(self.workspace.viewer.scale_enabled)
            save.assert_not_called()
        self.assertEqual(self.view.store.path.read_bytes(), before)

    def test_shift_click_toggles_and_plain_selected_click_preserves_group(self):
        a, b, c = self.frames
        self.nav.node_click(a.id)
        finish(self.nav.key_down(Data(key='Shift Left')))
        self.nav.node_click(b.id)
        self.assertEqual(self.nav.selection.ids, {a.id, b.id})
        self.nav.node_click(a.id)
        self.assertEqual(self.nav.selection.ids, {b.id})
        self.nav.node_click(a.id)
        self.nav.key_up(Data(key='Shift Left'))
        self.nav.node_click(b.id)
        self.assertEqual(self.nav.selection.ids, {a.id, b.id})
        self.assertEqual(self.nav.selected, b.id)
        self.nav.node_click(c.id)
        self.assertEqual(self.nav.selection.ids, {c.id})

    def test_shift_box_adds_control_box_subtracts_and_escape_restores_previous_selection(self):
        a, b, c = self.frames
        self.nav.apply_selection({c.id}, c.id)
        finish(self.nav.key_down(Data(key='Shift Left')))
        self.box({a.id, b.id}).end()
        self.assertEqual(self.nav.selection.ids, {a.id, b.id, c.id})
        self.nav.key_up(Data(key='Shift Left'))
        finish(self.nav.key_down(Data(key='Control Left')))
        self.box({a.id, b.id}).end()
        self.assertEqual(self.nav.selection.ids, {c.id})
        self.nav.key_up(Data(key='Control Left'))
        self.box({a.id, b.id})
        finish(self.nav.key_down(Data(key='Escape')))
        self.assertEqual(self.nav.selection.ids, {c.id})
        self.assertFalse(self.workspace.box_selection.active)

    def test_group_drag_snap_preserves_spacing_and_commits_once(self):
        a, b, c = self.frames
        finish(self.view.position_frame(b.id, 489.5, 11.5))
        self.nav.apply_selection({a.id, b.id}, a.id)
        originals = {f.id: (f.x, f.y) for f in self.view.board.frames}
        self.workspace.zoom = .5
        with patch.object(self.view.store, 'save', wraps=self.view.store.save) as save:
            self.workspace.begin_drag(a.id, Data(global_position=Data(x=10, y=10)))
            self.workspace.update_drag(a.id, Data(global_position=Data(x=47, y=37)))
            save.assert_not_called()
            self.assertEqual(set(self.workspace.drag.positions), {a.id, b.id})
            finish(self.workspace.end_drag(a.id))
            save.assert_called_once()
        moved = {f.id: (f.x, f.y) for f in self.view.board.frames}
        self.assertEqual(moved[a.id][0] % GRID_STEP, 0)
        self.assertEqual(moved[b.id][0] - moved[a.id][0], 489.5)
        self.assertEqual(moved[b.id][1] - moved[a.id][1], 11.5)
        self.assertEqual(moved[c.id], originals[c.id])
        self.assertEqual(self.nav.selection.ids, {a.id, b.id})

    def test_cancel_group_drag_restores_every_node_and_keeps_selection(self):
        a, b, _ = self.frames
        self.nav.apply_selection({a.id, b.id}, a.id)
        before = self.view.board
        self.workspace.begin_drag(a.id, Data(global_position=Data(x=10, y=10)))
        self.workspace.update_drag(a.id, Data(global_position=Data(x=-200, y=-150)))
        finish(self.nav.key_down(Data(key='Escape')))
        self.assertEqual(self.view.board, before)
        self.assertEqual(self.nav.selection.ids, {a.id, b.id})
        for frame in self.frames[:2]:
            self.assertEqual(self.view.cards[frame.id].content.left, frame.x + self.workspace.extent.origin_x)

    def test_group_duplicate_preserves_layout_and_images_and_selects_only_copies(self):
        a, b, c = self.frames
        self.nav.apply_selection({a.id, b.id}, b.id)
        with patch.object(self.view.store, 'save', wraps=self.view.store.save) as save:
            finish(self.nav.duplicate_selected())
            save.assert_called_once()
        self.assertEqual(len(self.view.board.frames), 5)
        copies = [frame for frame in self.view.board.frames if frame.id in self.nav.selection.ids]
        self.assertEqual(len(copies), 2)
        self.assertEqual([frame.title for frame in copies], ['A', 'B'])
        self.assertEqual(copies[1].x - copies[0].x, b.x - a.x)
        self.assertEqual(copies[0].x, a.x + 2 * GRID_STEP)
        self.assertEqual(self.view.board.frames[0], a)
        self.assertEqual(self.view.board.frames[-1], c)

    def test_group_delete_uses_confirmation_snapshot_and_leaves_other_frames(self):
        a, b, c = self.frames
        self.nav.apply_selection({a.id, b.id})
        self.nav.delete_selected()
        self.assertEqual(len(self.view.board.frames), 3)
        confirmation = self.view.page.show_dialog.call_args.args[0]
        self.nav.apply_selection({c.id})
        finish(confirmation.actions[-1].on_click(None))
        self.assertEqual(self.view.board.frames, (c,))
        self.assertEqual(self.view.store.load().frames, (c,))

    def test_selection_colors_and_active_border_come_from_theme(self):
        a, b, c = self.frames
        self.nav.apply_selection({a.id, b.id}, a.id)
        self.assertEqual(self.view.cards[a.id].box.border.top.color, ft.Colors.ON_SURFACE)
        self.assertEqual(self.view.cards[b.id].box.border.top.color, ft.Colors.SECONDARY)
        self.assertNotEqual(self.view.cards[a.id].box.bgcolor, self.view.cards[b.id].box.bgcolor)
        self.assertNotEqual(self.view.cards[b.id].box.bgcolor, self.view.cards[c.id].box.bgcolor)
        self.assertTrue(self.nav.selection_bar.visible)
        self.assertIn('2', self.nav.selection_count.value)

    def test_pan_zoom_and_field_editing_do_not_start_box_or_apply_bulk_shortcuts(self):
        a, b, c = self.frames
        for mode in ('pan', 'zoom'):
            self.nav.set_mode(mode)
            self.workspace.box_selection.begin(self.point(0, 0))
            self.assertFalse(self.workspace.box_selection.active)
        self.nav.set_mode('select')
        self.nav.select_node(a.id)
        field = self.view.properties.action
        field.on_focus(None)
        before = self.view.board
        for key in ('a', 'Delete', 'd'):
            finish(self.nav.key_down(Data(key=key)))
        self.assertEqual(self.view.board, before)
        self.assertNotEqual(self.nav.selection.ids, {a.id, b.id, c.id})

    def test_shortcuts_select_all_deselect_and_focus_entire_group(self):
        finish(self.nav.key_down(Data(key='a')))
        self.assertEqual(self.nav.selection.ids, {f.id for f in self.frames})
        self.workspace.focus_nodes = AsyncMock()
        finish(self.nav.key_down(Data(key='f')))
        self.workspace.focus_nodes.assert_awaited_once_with(self.nav.selection.ids)
        finish(self.nav.key_down(Data(key='Alt Left')))
        finish(self.nav.key_down(Data(key='a')))
        self.assertEqual(self.nav.selection.ids, set())

    def test_serialized_marquee_and_group_move_keep_controls_mutable(self):
        root = self.view.content
        encoder = configure_encode_object_for_msgpack(BaseControl)
        def publish(previous):
            delta, _, _ = ObjectPatch.from_diff(previous, root, BaseControl)
            msgpack.packb(delta.to_message(), default=encoder)
        publish(None)
        self.view.page.update.side_effect = lambda *args: publish(root)
        a, b, _ = self.frames
        self.box({a.id, b.id}).end()
        self.workspace.begin_drag(a.id, Data(global_position=Data(x=0, y=0)))
        self.workspace.update_drag(a.id, Data(global_position=Data(x=100, y=100)))
        finish(self.workspace.end_drag(a.id))
        finish(self.nav.duplicate_selected())
        self.assertEqual(len(self.nav.selection.ids), 2)
