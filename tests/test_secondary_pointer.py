"""Secondary drag moves only the camera; a release without drag opens the menu."""

from types import SimpleNamespace as Data
from unittest import TestCase
from unittest.mock import AsyncMock
from koma.ui.canvas_gestures import NativeSecondaryPan

from tests import test_storyboard as fixtures


class SecondaryPointerTests(TestCase):
    setUp = fixtures.StoryboardTests.setUp
    view = fixtures.StoryboardTests.view

    def event(self, x, y):
        return Data(global_position=Data(x=x, y=y), local_position=Data(x=x, y=y))

    def workspace(self):
        view = self.view()
        fixtures.finish(view.add_frame())
        ws = fixtures.StoryboardTests.camera(self, view.workspace)
        ws.context_menu.open = AsyncMock()
        return view, ws

    def test_drag_pans_at_zoom_without_menu_or_document_changes(self):
        view, ws = self.workspace()
        ws.zoom = 2
        board, history = view.board, len(view.history.past)
        ws.secondary_pointer.begin(self.event(100, 100))
        fixtures.finish(ws.secondary_pointer.move(self.event(180, 140)))
        fixtures.finish(ws.secondary_pointer.end(self.event(200, 150)))
        self.assertEqual((ws.translation_x, ws.translation_y), (100, 50))
        ws.context_menu.open.assert_not_awaited()
        self.assertIs(view.board, board)
        self.assertEqual(len(view.history.past), history)

    def test_release_opens_menu_but_cancel_does_not(self):
        view, ws = self.workspace()
        press = self.event(100, 100)
        ws.secondary_pointer.begin(press)
        ws.context_menu.open.assert_not_awaited()
        fixtures.finish(ws.secondary_pointer.end(self.event(102, 101)))
        ws.context_menu.open.assert_awaited_once_with(press)
        ws.context_menu.open.reset_mock()
        ws.secondary_pointer.begin(press)
        ws.secondary_pointer.cancel()
        fixtures.finish(ws.secondary_pointer.end(press))
        ws.context_menu.open.assert_not_awaited()
        self.assertTrue(ws.viewer.scale_enabled)

    def test_cut_tool_keeps_unmodified_right_drag_for_pan(self):
        view, ws = self.workspace()
        ws.navigation.set_mode('cut')
        ws.secondary_pointer.begin(self.event(100, 100))
        fixtures.finish(ws.secondary_pointer.end(self.event(140, 130)))
        self.assertEqual((ws.translation_x, ws.translation_y), (40, 30))
        self.assertFalse(ws.links.cut_points)
        ws.secondary_pointer.native = NativeSecondaryPan(content=ws.viewer)
        ws.secondary_pointer.sync()
        self.assertTrue(ws.secondary_pointer.native.pan_enabled)
        self.assertIn('Ctrl', ws.secondary_pointer.native.reserved_modifiers)

    def test_native_snapshot_updates_camera_without_sending_pan_back_to_client(self):
        view, ws = self.workspace()
        ws.secondary_pointer.native = NativeSecondaryPan(content=ws.viewer)
        ws.secondary_pointer.begin(self.event(100, 100))
        self.assertIsNone(ws.secondary_pointer.press)
        event = self.event(100, 100)
        event.moved, event.zoom = True, 1.5
        event.translation_x, event.translation_y = 80, -30
        fixtures.finish(ws.secondary_pointer.native_navigation(event))
        ws.viewer.pan.assert_not_awaited()
        ws.context_menu.open.assert_not_awaited()
        self.assertEqual((ws.zoom, ws.translation_x, ws.translation_y), (1.5, 80, -30))
