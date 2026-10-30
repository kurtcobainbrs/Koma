"""Focus request bursts and connection/mode races, without native/manual UI."""
import asyncio
import flet as ft
from types import SimpleNamespace as Data
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from koma.ui.focus_requests import FocusRequests, FocusListener, FOCUS_TIMEOUT_SECONDS


class FocusRequestsTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tasks = []
        def run_task(handler, *args):
            task = asyncio.create_task(handler(*args))
            self.tasks.append(task)
            return task
        self.requests = FocusRequests(Data(run_task=run_task))

    async def asyncTearDown(self):
        self.requests.cancel()
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)

    async def test_burst_has_one_in_flight_request(self):
        gate = asyncio.Event()
        target = Data(focus=AsyncMock(side_effect=gate.wait))
        for _ in range(50):
            self.requests.request(target, lambda: True)
        await asyncio.sleep(0)
        self.assertEqual(len(self.tasks), 1)
        target.focus.assert_awaited_once()
        gate.set()
        await self.tasks[0]
        self.assertIsNone(self.requests.task)

    async def test_switch_target_cancels_obsolete_request(self):
        gate = asyncio.Event()
        old = Data(focus=AsyncMock(side_effect=gate.wait))
        new = Data(focus=AsyncMock())
        self.requests.request(old, lambda: True)
        await asyncio.sleep(0)
        self.requests.request(new, lambda: True)
        self.assertEqual(len(self.tasks), 1)
        new.focus.assert_not_awaited()
        gate.set()
        await asyncio.gather(*self.tasks)
        new.focus.assert_awaited_once()
        self.assertIsNone(self.requests.target)

    async def test_disconnect_cancels_pending_and_reconnect_accepts_requests(self):
        gate = asyncio.Event()
        old = Data(focus=AsyncMock(side_effect=gate.wait))
        self.requests.request(old, lambda: True)
        await asyncio.sleep(0)
        self.requests.disconnect()
        self.requests.request(old, lambda: True)
        gate.set()
        await asyncio.gather(*self.tasks)
        self.assertEqual(len(self.tasks), 1)
        self.requests.reconnect()
        target = Data(focus=AsyncMock())
        self.requests.request(target, lambda: True)
        await self.tasks[-1]
        target.focus.assert_awaited_once()

    async def test_session_closed_race_finishes_without_callback_error(self):
        target = Data(focus=AsyncMock(side_effect=RuntimeError('Session closed')))
        self.requests.request(target, lambda: True)
        await self.tasks[0]
        self.assertFalse(self.requests.connected)
        self.requests.request(target, lambda: True)
        self.assertEqual(len(self.tasks), 1)

    async def test_suspended_tab_and_invalidated_mode_skip_focus(self):
        target = Data(focus=AsyncMock())
        active = True
        self.requests.request(target, lambda: active)
        active = False
        await self.tasks[0]
        target.focus.assert_not_awaited()
        self.requests.suspend()
        self.requests.request(target, lambda: True)
        self.assertEqual(len(self.tasks), 1)
        self.requests.resume()
        self.requests.request(target, lambda: True)
        await self.tasks[-1]
        target.focus.assert_awaited_once()

    async def test_unrelated_runtime_error_remains_visible(self):
        target = Data(focus=AsyncMock(side_effect=RuntimeError('Broken focus contract')))
        self.requests.request(target, lambda: True)
        with self.assertRaisesRegex(RuntimeError, 'Broken focus contract'):
            await self.tasks[0]

    async def test_native_focus_uses_transport_timeout_and_timeout_is_handled(self):
        listener = FocusListener(content=ft.Container())
        listener._invoke_method = AsyncMock(side_effect=TimeoutError())
        self.requests.request(listener, lambda: True)
        with self.assertLogs('koma.ui.focus_requests', level='WARNING'):
            await self.tasks[0]
        listener._invoke_method.assert_awaited_once_with('focus', timeout=FOCUS_TIMEOUT_SECONDS)
        self.assertIsNone(self.requests.task)
