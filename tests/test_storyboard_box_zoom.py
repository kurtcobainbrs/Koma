"""Zoom por caixa preserva nodes, seleção e enquadramento durante a transição."""

from unittest import TestCase
from unittest.mock import AsyncMock, patch

from tests import test_storyboard_selection as fixtures


class BoxZoomTests(TestCase):
    setUp = fixtures.StoryboardSelectionTests.setUp
    point = fixtures.StoryboardSelectionTests.point

    def camera(self):
        self.workspace.viewer.zoom = AsyncMock()
        self.workspace.viewer.pan = AsyncMock()
        self.workspace.viewer.reset = AsyncMock()
        self.nav.set_mode('zoom')
        return self.workspace.box_zoom

    def test_rectangle_in_both_directions_fits_and_preserves_document_and_selection(self):
        self.nav.apply_selection({self.frames[0].id})
        original = self.view.store.path.read_bytes()
        box = self.camera()
        ws = self.workspace
        for start, end in [((800, 600), (1200, 900)), ((1200, 900), (800, 600))]:
            box.press(self.point(*start))
            box.begin(self.point(*start))
            box.update(self.point(*end))
            self.assertTrue(box.overlay.visible)
            self.assertFalse(ws.viewer.scale_enabled)
            with patch('koma.editor.canvas.asyncio.sleep', new_callable=AsyncMock):
                fixtures.finish(box.end())
            expected = min((ws.viewport_width - 48) / 400, (ws.viewport_height - 48) / 300, 2.5)
            self.assertAlmostEqual(ws.zoom, expected)
            self.assertAlmostEqual(1000 * ws.zoom + ws.translation_x, ws.viewport_width / 2)
            self.assertAlmostEqual(750 * ws.zoom + ws.translation_y, ws.viewport_height / 2)
            self.assertFalse(box.overlay.visible)
            self.assertTrue(ws.viewer.scale_enabled)
            self.assertEqual(self.nav.selection.ids, {self.frames[0].id})
        self.assertEqual(self.view.store.path.read_bytes(), original)
        ws.viewer.reset.assert_not_awaited()

    def test_small_drag_does_not_zoom_and_press_does_not_change_camera(self):
        box = self.camera()
        box.press(self.point(100, 100))
        self.workspace.viewer.zoom.assert_not_awaited()
        box.begin(self.point(100, 100))
        box.update(self.point(103, 102))
        fixtures.finish(box.end())
        self.workspace.viewer.zoom.assert_not_awaited()
        self.assertEqual(self.workspace.zoom, 1)

    def test_escape_and_mode_switch_cancel_the_box_without_changing_selection(self):
        box = self.camera()
        for cancel in (lambda: fixtures.finish(self.nav.key_down(fixtures.Data(key='Escape'))),
                       lambda: self.nav.set_mode('pan')):
            self.nav.set_mode('zoom')
            box.press(self.point(100, 100))
            box.begin(self.point(100, 100))
            box.update(self.point(500, 400))
            cancel()
            self.assertFalse(box.active)
            self.assertFalse(box.overlay.visible)
            fixtures.finish(box.end())
            self.workspace.viewer.zoom.assert_not_awaited()

    def test_transition_is_progressive_and_can_be_interrupted_by_new_navigation(self):
        self.camera()
        ws = self.workspace
        scales = []
        async def next_tick(_):
            scales.append(ws.zoom)
            if len(scales) == 4:
                ws.cancel_camera_transition()
        with patch('koma.editor.canvas.asyncio.sleep', side_effect=next_tick):
            fixtures.finish(ws.focus_region((800, 600, 1000, 750)))
        self.assertEqual(len(scales), 4)
        self.assertEqual(scales, sorted(scales))
        self.assertGreater(ws.zoom, 1)
        self.assertLess(ws.zoom, 2.5)
        self.assertEqual(ws.viewer.zoom.await_count, 4)

    def test_busy_editor_ignores_box_and_camera_requests(self):
        box = self.camera()
        self.view.busy = True
        box.press(self.point(100, 100))
        box.begin(self.point(100, 100))
        self.assertFalse(box.active)
        fixtures.finish(self.workspace.focus_region((0, 0, 300, 200)))
        self.workspace.viewer.zoom.assert_not_awaited()
