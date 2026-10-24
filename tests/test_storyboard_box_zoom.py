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
        self.assertEqual(ws.viewer.reset.await_count, 2)

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

    def test_focus_is_one_stable_transform_after_previous_pan_and_zoom(self):
        self.camera()
        ws = self.workspace
        ws.zoom = .5
        ws.translation_x, ws.translation_y = 180, -240
        async def reset():
            self.assertTrue(ws.focusing_region)
            self.assertFalse(ws.viewer.scale_enabled)
            # Um callback atrasado do gesto anterior não pode alterar a câmera.
            ws.interaction_update(fixtures.Data(scale=3))
            self.assertEqual(ws.zoom, .5)
        ws.viewer.reset.side_effect = reset
        fixtures.finish(ws.focus_region((800, 600, 1200, 900)))
        expected = min((ws.viewport_width - 48) / 400, (ws.viewport_height - 48) / 300, 2.5)
        ws.viewer.reset.assert_awaited_once()
        ws.viewer.zoom.assert_awaited_once_with(expected)
        self.assertAlmostEqual(ws.translation_x + 1000 * ws.zoom, ws.viewport_width / 2)
        self.assertAlmostEqual(ws.translation_y + 750 * ws.zoom, ws.viewport_height / 2)
        self.assertFalse(ws.focusing_region)
        self.assertTrue(ws.viewer.scale_enabled)
        self.assertEqual(self.nav.definitions['zoom'].cursor.value, 'precise')

    def test_busy_editor_ignores_box_and_camera_requests(self):
        box = self.camera()
        self.view.busy = True
        box.press(self.point(100, 100))
        box.begin(self.point(100, 100))
        self.assertFalse(box.active)
        fixtures.finish(self.workspace.focus_region((0, 0, 300, 200)))
        self.workspace.viewer.zoom.assert_not_awaited()
