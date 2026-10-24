"""Persistência, drag-and-drop, imagens e PDF sem tocar nos arquivos de produção."""

import tempfile
import inspect
import json
import asyncio
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as Data
from unittest.mock import AsyncMock, Mock, patch

import msgpack
from PIL import Image
from flet.controls.base_control import BaseControl
from flet.controls.object_patch import ObjectPatch
from flet.messaging.protocol import configure_encode_object_for_msgpack

from koma.preferences import AppPreferences
from koma.documents.session import DocumentSession
from koma.documents.images import import_image
from koma.editor.geometry import NODE_HEIGHT
from koma.editor.models import Storyboard, StoryFrame
from koma.exports.pdf_export import export_pdf
from koma.documents.store import StoryboardStore
from koma.editor.view import StoryboardView
from koma.editor.geometry import (GRID_STEP, MAX_ZOOM, MIN_ZOOM, ZOOM_STEP, WHEEL_ZOOM_FACTOR,
    INITIAL_CANVAS_WIDTH, INITIAL_CANVAS_HEIGHT, CANVAS_EDGE_MARGIN, content_bounds, frame_bounds, coordinate)


def finish(coroutine):
    try:
        coroutine.send(None)
    except StopIteration as result:
        return result.value
    raise AssertionError('Suspensão inesperada')


async def immediate(function, *args):
    return function(*args)


class StoryboardTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.source = self.root / 'referência.png'
        Image.new('RGB', (800, 450), 'gray').save(self.source)
        self.original = self.source.read_bytes()
        self.session = DocumentSession(self.root / 'data')
        self.store = self.session.store
        self.addCleanup(self.session.close)
        thread = patch('asyncio.to_thread', side_effect=immediate)
        thread.start()
        self.addCleanup(thread.stop)

    def view(self):
        session = self.session
        if self.store.path.exists():
            session.board = self.store.load()
        view = StoryboardView(Mock(), session, AppPreferences(self.root / 'data'))
        finish(view.activate())
        return view




    def test_import_owns_copy_preserves_original_and_restores_thumbnail(self):
        view = self.view()
        finish(view.import_paths([self.source]))
        self.assertEqual(len(view.board.frames), 1)
        frame = view.board.frames[0]
        self.assertTrue((self.store.images / frame.image).is_file())
        self.assertTrue(view.thumbnails[frame.image])
        self.assertEqual(self.source.read_bytes(), self.original)
        self.source.unlink()
        restored = self.view()
        self.assertEqual(restored.board, view.board)
        self.assertTrue(restored.thumbnails[frame.image])

    def test_invalid_image_does_not_discard_valid_imports(self):
        invalid = self.root / 'invalid.png'
        invalid.write_bytes(b'not image')
        view = self.view()
        finish(view.import_paths([invalid, self.source]))
        self.assertEqual(len(view.board.frames), 1)
        self.assertEqual(view.feedback.state, 'warning')
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_move_before_target_and_to_end_preserves_fields_and_controls(self):
        view = self.view()
        for _ in range(3):
            finish(view.add_frame())
        a, b, c = view.board.frames
        card = view.cards[c.id]
        view.workspace.navigation.select_node(c.id)
        finish(view.edit_frame(c.id, 'action', 'A câmera se aproxima.'))
        finish(view.move(a.id, c.id))
        self.assertEqual([f.id for f in view.board.frames], [b.id, a.id, c.id])
        finish(view.move(c.id, b.id))
        self.assertEqual([f.id for f in view.board.frames], [c.id, b.id, a.id])
        finish(view.move(c.id))
        self.assertEqual([f.id for f in view.board.frames], [b.id, a.id, c.id])
        self.assertIs(view.cards[c.id], card)
        self.assertEqual(view.properties.active, c.id)
        self.assertEqual(view.store.load().frames[-1].action, 'A câmera se aproxima.')

    def test_drag_requires_a_frame_from_the_current_editable_board(self):
        view = self.view()
        finish(view.add_frame())
        before = view.board
        view.workspace.begin_drag('another-project-frame', Data(global_position=Data(x=0, y=0)))
        self.assertIsNone(view.workspace.drag)
        view.busy = True
        view.workspace.begin_drag(before.frames[0].id, Data(global_position=Data(x=0, y=0)))
        self.assertIsNone(view.workspace.drag)
        self.assertEqual(view.board, before)


    def test_drag_is_scaled_saves_only_on_drop_and_keeps_narrative_order(self):
        for zoom in (0.5, 2):
            view = self.view()
            if not view.board.frames:
                finish(view.add_frame())
                finish(view.add_frame())
            frame = view.board.frames[0]
            order = [f.id for f in view.board.frames]
            card = view.cards[frame.id]
            workspace = view.workspace
            workspace.zoom = zoom
            with patch.object(view.store, 'save', wraps=view.store.save) as save:
                card.handle.on_pan_start(Data(global_position=Data(x=100, y=100)))
                self.assertFalse(workspace.viewer.pan_enabled)
                card.handle.on_pan_update(Data(global_position=Data(x=193, y=147)))
                node = card.content
                self.assertEqual(node.left, workspace.extent.origin_x + frame.x + 93 / zoom)
                self.assertEqual(node.top, workspace.extent.origin_y + frame.y + 47 / zoom)
                save.assert_not_called()
                self.assertEqual(view.page.update.call_args.args, (node,))
                self.assertEqual(view.board.frames[0], frame)
                finish(card.handle.on_pan_end(None))
                save.assert_called_once()
            moved = view.board.frames[0]
            self.assertEqual(moved.x, coordinate(frame.x + 93 / zoom))
            self.assertEqual(moved.y, coordinate(frame.y + 47 / zoom))
            self.assertEqual(moved.x % GRID_STEP, 0)
            self.assertFalse(workspace.viewer.pan_enabled)
            self.assertTrue(workspace.viewer.scale_enabled)
            self.assertEqual([f.id for f in view.store.load().frames], order)
            self.assertIs(view.cards[frame.id], card)

    def test_snap_can_be_disabled_and_cancelling_drag_restores_position(self):
        view = self.view()
        finish(view.add_frame())
        frame = view.board.frames[0]
        workspace = view.workspace
        workspace.zoom = 2
        workspace.snap.on_click(None)
        self.assertFalse(workspace.snap_enabled)
        workspace.begin_drag(frame.id, Data(global_position=Data(x=10, y=10)))
        workspace.update_drag(frame.id, Data(global_position=Data(x=23, y=17)))
        workspace.cancel_drag(frame.id)
        self.assertEqual(view.cards[frame.id].content.left, workspace.extent.origin_x + frame.x)
        self.assertEqual(view.store.load().frames[0], frame)
        workspace.begin_drag(frame.id, Data(global_position=Data(x=10, y=10)))
        workspace.update_drag(frame.id, Data(global_position=Data(x=23, y=17)))
        finish(workspace.end_drag(frame.id))
        self.assertEqual(view.store.load().frames[0].x, frame.x + 6.5)
        self.assertEqual(view.store.load().frames[0].y, frame.y + 3.5)

    def test_sequence_actions_are_explicit_and_do_not_reposition_nodes(self):
        view = self.view()
        for _ in range(3):
            finish(view.add_frame())
        a, b, c = view.board.frames
        finish(view.position_frame(c.id, 0, 0))
        self.assertEqual([f.id for f in view.board.frames], [a.id, b.id, c.id])
        finish(view.order_by_position())
        self.assertEqual([f.id for f in view.board.frames], [c.id, a.id, b.id])
        finish(view.cards[c.id].sequence.items[1].on_click(None))
        self.assertEqual([f.id for f in view.board.frames], [a.id, c.id, b.id])
        self.assertEqual(view.board.frames[1].x, 0)
        self.assertEqual(view.board.frames[1].y, 0)

    def test_zoom_reset_fit_and_gestures_do_not_write_document(self):
        view = self.view()
        finish(view.add_frame())
        workspace = view.workspace
        workspace.viewer.zoom = AsyncMock()
        workspace.viewer.pan = AsyncMock()
        workspace.viewer.reset = AsyncMock()
        workspace.interaction_start(None)
        workspace.interaction_update(Data(scale=1.6))
        self.assertAlmostEqual(workspace.zoom, 1.6)
        workspace.interaction_start(None)
        workspace.interaction_update(Data(scale=0.5))
        self.assertAlmostEqual(workspace.zoom, 0.8)
        workspace.interaction_update(Data(scale=float('nan')))
        self.assertAlmostEqual(workspace.zoom, 0.8)
        before = self.store.path.read_bytes()
        finish(workspace.set_zoom(100))
        self.assertEqual(workspace.zoom, MAX_ZOOM)
        finish(workspace.set_zoom(0.001))
        self.assertEqual(workspace.zoom, MIN_ZOOM)
        finish(workspace.reset())
        self.assertEqual(workspace.zoom, 1)
        finish(workspace.fit())
        self.assertGreaterEqual(workspace.zoom, MIN_ZOOM)
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_height_observer_stays_inside_positioned_node_and_expanded_text_comes_forward(self):
        view = self.view()
        finish(view.add_frame())
        finish(view.add_frame())
        frame = view.board.frames[0]
        card = view.cards[frame.id]
        # No Flet 1.0.5, observar o Container posicionado quebra o parent data do Stack.
        self.assertIsNone(card.content.on_size_change)
        card.box.on_size_change(Data(height=710))
        self.assertEqual(view.workspace.node_heights[frame.id], 710)
        view.workspace.navigation.select_node(frame.id)
        self.assertTrue(view.properties.fields.visible)
        self.assertEqual(view.workspace.z_order[-1], frame.id)

    def test_snap_remains_on_grid_at_world_boundaries(self):
        self.assertEqual(coordinate(-100), -96)
        self.assertEqual(coordinate(200000) % GRID_STEP, 0)

    def test_header_drag_covers_number_and_free_space_but_not_action_buttons(self):
        view = self.view()
        finish(view.add_frame())
        card = view.cards[view.board.frames[0].id]
        header = card.box.content.controls[0]
        self.assertIs(header.controls[0], card.handle)
        self.assertTrue(card.handle.expand)
        self.assertIsNone(card.handle.content.width)
        self.assertIn(card.number, card.handle.content.content.controls)
        self.assertNotIn(card.sequence, card.handle.content.content.controls)
        self.assertIs(header.controls[1], card.sequence)

    def test_canvas_starts_larger_grows_with_nodes_and_does_not_shrink_on_removal(self):
        view = self.view()
        workspace = view.workspace
        viewer = workspace.viewer
        self.assertEqual(workspace.stack.width, INITIAL_CANVAS_WIDTH)
        self.assertEqual(workspace.stack.height, INITIAL_CANVAS_HEIGHT)
        for _ in range(10):
            finish(view.add_frame())
        self.assertGreater(workspace.stack.height, INITIAL_CANVAS_HEIGHT)
        first = view.board.frames[0]
        finish(view.position_frame(first.id, 4800, 4200))
        width, height = content_bounds(view.board.frames)
        self.assertGreaterEqual(workspace.stack.width, width + CANVAS_EDGE_MARGIN)
        self.assertGreaterEqual(workspace.stack.height, height + CANVAS_EDGE_MARGIN)
        extent = workspace.stack.width, workspace.stack.height
        view.changed(replace(view.board, frames=()))
        view.refresh()
        self.assertEqual((workspace.stack.width, workspace.stack.height), extent)
        self.assertIs(workspace.viewer, viewer)

    def test_snap_button_state_is_clear_and_toggle_does_not_reposition_nodes(self):
        view = self.view()
        finish(view.add_frame())
        before = view.board
        snap = view.workspace.snap
        snap.on_click(None)
        self.assertFalse(view.workspace.snap_enabled)
        self.assertIn('desativado', snap.tooltip)
        snap.on_click(None)
        self.assertTrue(view.workspace.snap_enabled)
        self.assertIn('ativado', snap.tooltip)
        self.assertEqual(view.board, before)

    def test_wheel_and_button_zoom_are_more_gradual(self):
        view = self.view()
        workspace = view.workspace
        self.assertEqual(workspace.viewer.scale_factor, WHEEL_ZOOM_FACTOR)
        self.assertGreater(WHEEL_ZOOM_FACTOR, 200)
        workspace.viewer.zoom = AsyncMock()
        workspace.viewer.pan = AsyncMock()
        finish(workspace.zoom_in(None))
        self.assertAlmostEqual(workspace.zoom, ZOOM_STEP)
        self.assertLessEqual(ZOOM_STEP, 1.1)
        finish(workspace.zoom_out(None))
        self.assertAlmostEqual(workspace.zoom, 1.0)

    def test_invalid_coordinates_are_rejected_without_changing_saved_document(self):
        for x, y in [(float('nan'), 0), (0, float('inf')), (-100001, 0), (0, None), (True, 0)]:
            with self.subTest(x=x, y=y), self.assertRaises(ValueError):
                StoryFrame(x=x, y=y).validate()

    def camera(self, workspace):
        workspace.viewer.zoom = AsyncMock()
        workspace.viewer.pan = AsyncMock()
        workspace.viewer.reset = AsyncMock()
        return workspace

    def test_loaded_nodes_start_in_the_center_without_rewriting_saved_coordinates(self):
        board = Storyboard(frames=(StoryFrame(x=-480, y=-240), StoryFrame(x=384, y=120)))
        self.store.save(board)
        original = self.store.path.read_bytes()
        view = self.view()
        workspace = view.workspace
        left, top, right, bottom = frame_bounds(view.board.frames)
        self.assertLessEqual(abs(workspace.extent.origin_x + (left + right) / 2 - workspace.stack.width / 2), GRID_STEP)
        self.assertLessEqual(abs(workspace.extent.origin_y + (top + bottom) / 2 - workspace.stack.height / 2), GRID_STEP)
        self.assertEqual(view.board, board)
        self.assertEqual(self.store.path.read_bytes(), original)

    def test_growth_to_left_and_top_preserves_screen_position_and_saves_negative_coordinates(self):
        view = self.view()
        finish(view.add_frame())
        frame = view.board.frames[0]
        workspace = self.camera(view.workspace)
        workspace.initial_view_done = True
        workspace.zoom = .7
        old_origin = workspace.extent.origin_x, workspace.extent.origin_y
        old_size = workspace.stack.width, workspace.stack.height
        expected = ((-4000 + old_origin[0]) * .7, (-3500 + old_origin[1]) * .7)
        finish(view.position_frame(frame.id, -4000, -3500))
        node = view.cards[frame.id].content
        self.assertAlmostEqual(node.left * workspace.zoom + workspace.translation_x, expected[0])
        self.assertAlmostEqual(node.top * workspace.zoom + workspace.translation_y, expected[1])
        self.assertGreaterEqual(node.left, CANVAS_EDGE_MARGIN)
        self.assertGreaterEqual(node.top, CANVAS_EDGE_MARGIN)
        self.assertGreater(workspace.stack.width, old_size[0])
        self.assertGreater(workspace.stack.height, old_size[1])
        self.assertEqual(view.store.load().frames[0].x, -4000)
        self.assertEqual(view.store.load().frames[0].y, -3500)

    def test_selection_pan_and_zoom_modes_keep_document_unchanged(self):
        view = self.view()
        finish(view.add_frame())
        frame = view.board.frames[0]
        nav = view.workspace.navigation
        before = view.store.path.read_bytes()
        view.cards[frame.id].handle.on_tap_down(None)
        self.assertEqual(nav.selected, frame.id)
        self.assertFalse(nav.focus_button.disabled)
        nav.buttons['pan'].on_click(None)
        self.assertTrue(view.workspace.scene.ignore_interactions)
        self.assertTrue(view.workspace.viewer.pan_enabled)
        view.workspace.begin_drag(frame.id, Data(global_position=Data(x=0, y=0)))
        self.assertIsNone(view.workspace.drag)
        nav.buttons['zoom'].on_click(None)
        self.assertFalse(view.workspace.viewer.pan_enabled)
        self.assertTrue(view.workspace.scene.ignore_interactions)
        self.assertIsNone(view.workspace.pointer_surface.on_tap_down)
        self.assertEqual(view.workspace.pointer_surface.on_pan_start, view.workspace.box_zoom.begin)
        nav.buttons['select'].on_click(None)
        self.assertFalse(view.workspace.scene.ignore_interactions)
        self.assertIsNone(view.workspace.pointer_surface.on_tap_down)
        self.assertEqual(view.store.path.read_bytes(), before)

    def test_space_is_temporary_pan_and_text_fields_keep_their_shortcuts(self):
        view = self.view()
        finish(view.add_frame())
        frame = view.board.frames[0]
        nav = view.workspace.navigation
        finish(nav.key_down(Data(key='Space')))
        self.assertEqual(nav.effective_mode, 'pan')
        nav.key_up(Data(key='Space'))
        self.assertEqual(nav.effective_mode, 'select')
        nav.select_node(frame.id)
        field = view.properties.action
        field.on_focus(None)
        for key in ('Space', 'h', 'z', 'v', 'f'):
            finish(nav.key_down(Data(key=key)))
        self.assertEqual(nav.effective_mode, 'select')
        field.on_blur(None)
        finish(nav.key_down(Data(key='h')))
        self.assertEqual(nav.mode, 'pan')
        finish(nav.key_down(Data(key='z')))
        self.assertEqual(nav.mode, 'zoom')
        finish(nav.key_down(Data(key='Escape')))
        self.assertEqual(nav.mode, 'select')
        self.assertIsNone(nav.selected)

    def test_focus_and_center_zoom_preserve_world_point_under_viewport_center(self):
        view = self.view()
        finish(view.add_frame())
        frame = view.board.frames[0]
        workspace = self.camera(view.workspace)
        workspace.navigation.select_node(frame.id)
        finish(workspace.navigation.focus_selected())
        node = view.cards[frame.id].content
        center_x, center_y = node.left + 168, node.top + NODE_HEIGHT / 2
        self.assertAlmostEqual(center_x * workspace.zoom + workspace.translation_x, workspace.viewport_width / 2)
        self.assertAlmostEqual(center_y * workspace.zoom + workspace.translation_y, workspace.viewport_height / 2)
        finish(workspace.zoom_in(None))
        self.assertAlmostEqual(center_x * workspace.zoom + workspace.translation_x, workspace.viewport_width / 2)
        self.assertAlmostEqual(center_y * workspace.zoom + workspace.translation_y, workspace.viewport_height / 2)

    def test_selection_focus_fills_viewport_with_margin_for_single_and_multiple_nodes(self):
        self.store.save(Storyboard(frames=(StoryFrame(x=-480, y=-240), StoryFrame(x=384, y=120))))
        view = self.view()
        workspace = self.camera(view.workspace)
        workspace.node_heights = {frame.id: 220 for frame in view.board.frames}
        original = self.store.path.read_bytes()
        for width, height in [(1100, 850), (460, 500)]:
            workspace.resized(Data(width=width, height=height))
            for frames in [view.board.frames[:1], view.board.frames]:
                with self.subTest(width=width, count=len(frames)):
                    ids = {frame.id for frame in frames}
                    finish(workspace.focus_nodes(ids))
                    left, top, right, bottom = frame_bounds(frames, workspace.node_heights)
                    margin = GRID_STEP * 3
                    expected = min((width - margin * 2) / (right - left),
                                   (height - margin * 2) / (bottom - top), 2.5)
                    self.assertAlmostEqual(workspace.zoom, expected)
                    center_x = (left + right) / 2 + workspace.extent.origin_x
                    center_y = (top + bottom) / 2 + workspace.extent.origin_y
                    self.assertAlmostEqual(center_x * expected + workspace.translation_x, width / 2)
                    self.assertAlmostEqual(center_y * expected + workspace.translation_y, height / 2)
                    self.assertLessEqual((right - left) * expected, width - margin * 2)
                    self.assertLessEqual((bottom - top) * expected, height - margin * 2)
        self.assertEqual(self.store.path.read_bytes(), original)

    def test_zoom_tool_clicks_anchor_the_clicked_point_and_right_click_reduces(self):
        view = self.view()
        workspace = self.camera(view.workspace)
        workspace.navigation.set_mode('zoom')
        point = Data(x=1300, y=800)
        finish(workspace.scene_click(Data(local_position=point)))
        self.assertAlmostEqual(workspace.zoom, ZOOM_STEP)
        self.assertAlmostEqual(point.x * workspace.zoom + workspace.translation_x, point.x)
        self.assertAlmostEqual(point.y * workspace.zoom + workspace.translation_y, point.y)
        finish(workspace.scene_secondary_click(Data(local_position=point)))
        self.assertAlmostEqual(workspace.zoom, 1)
        self.assertAlmostEqual(workspace.translation_x, 0)
        self.assertAlmostEqual(workspace.translation_y, 0)

    def test_escape_cancels_drag_and_background_click_clears_selection(self):
        view = self.view()
        finish(view.add_frame())
        workspace = view.workspace
        frame = view.board.frames[0]
        workspace.begin_drag(frame.id, Data(global_position=Data(x=0, y=0)))
        workspace.update_drag(frame.id, Data(global_position=Data(x=-200, y=-200)))
        finish(workspace.navigation.key_down(Data(key='Escape')))
        self.assertIsNone(workspace.drag)
        self.assertEqual(workspace.navigation.selected, frame.id)
        self.assertEqual(view.store.load().frames[0], frame)
        workspace.navigation.select_node(frame.id)
        finish(workspace.background_hit.on_tap_down(Data(local_position=Data(x=0, y=0))))
        self.assertIsNone(workspace.navigation.selected)

    def test_initial_camera_framing_runs_only_once_even_with_overlapping_tasks(self):
        view = self.view()
        finish(view.add_frame())
        workspace = view.workspace
        workspace.fit = AsyncMock()
        async def run():
            await asyncio.gather(workspace.ensure_initial_view(), workspace.ensure_initial_view(), workspace.ensure_initial_view())
        asyncio.run(run())
        workspace.fit.assert_awaited_once()

    def test_texts_save_and_duplicate_has_independent_identifier(self):
        view = self.view()
        finish(view.add_frame())
        first = view.board.frames[0]
        card = view.cards[first.id]
        view.workspace.navigation.select_node(first.id)
        view.properties.action.value = 'Descrição'
        finish(view.properties.action.on_change(Data(control=view.properties.action)))
        self.assertEqual(view.store.load().frames[0].action, 'Descrição')
        finish(view.duplicate(first.id))
        a, b = view.board.frames
        self.assertNotEqual(a.id, b.id)
        self.assertEqual(a.action, b.action)
        finish(view.edit_frame(b.id, 'action', 'Outra ação'))
        self.assertEqual(view.board.frames[0].action, 'Descrição')

    def test_delete_requires_explicit_confirmation(self):
        view = self.view()
        finish(view.add_frame())
        view.confirm_remove(view.board.frames[0].id)
        self.assertEqual(len(view.board.frames), 1)
        confirmation = view.page.show_dialog.call_args.args[0]
        self.assertFalse(confirmation.modal)
        finish(confirmation.actions[-1].on_click(None))
        self.assertEqual(view.store.load().frames, ())

    def test_native_picker_callbacks_are_async_and_replace_image(self):
        view = self.view()
        picker = Mock()
        picker.pick_files = AsyncMock(return_value=[Data(path=str(self.source))])
        with patch('koma.editor.view.ft.FilePicker', return_value=picker):
            self.assertTrue(inspect.iscoroutinefunction(view.import_button.on_click))
            finish(view.import_button.on_click(None))
            first = view.board.frames[0]
            card = view.cards[first.id]
            view.workspace.navigation.select_node(first.id)
            self.assertTrue(inspect.iscoroutinefunction(view.properties.image_button.on_click))
            self.assertTrue(inspect.iscoroutinefunction(card.box.content.controls[0].controls[-2].on_click))
            finish(view.properties.image_button.on_click(None))
            self.assertEqual(len(view.board.frames), 1)
            self.assertNotEqual(view.board.frames[0].image, first.image)
            self.assertFalse(picker.pick_files.call_args.kwargs['allow_multiple'])
        self.assertFalse(view.busy)
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_export_picker_cancellation_and_failure_unlock_without_losing_board(self):
        view = self.view()
        finish(view.add_frame())
        before = view.board
        picker = Mock()
        picker.save_file = AsyncMock(return_value=None)
        with patch('koma.editor.view.ft.FilePicker', return_value=picker), \
                patch('koma.editor.view.export_pdf') as export:
            finish(view.export())
            export.assert_not_called()
            self.assertFalse(view.busy)
            picker.save_file.return_value = str(self.root / 'presentation.pdf')
            export.side_effect = ValueError('missing image')
            finish(view.export())
        self.assertFalse(view.busy)
        self.assertEqual(view.board, before)
        self.assertEqual(view.feedback.state, 'error')


    def test_serialized_cards_stay_mutable_through_edit_move_and_expand(self):
        view = self.view()
        encoder = configure_encode_object_for_msgpack(BaseControl)
        def publish(previous):
            delta, _, _ = ObjectPatch.from_diff(previous, view.content, BaseControl)
            msgpack.packb(delta.to_message(), default=encoder)
        publish(None)
        view.page.update.side_effect = lambda *args: publish(view.content)
        finish(view.import_paths([self.source]))
        finish(view.add_frame())
        a, b = view.board.frames
        finish(view.move(b.id, a.id))
        card = view.cards[a.id]
        view.workspace.navigation.select_node(a.id)
        card.handle.on_pan_start(Data(global_position=Data(x=20, y=20)))
        card.handle.on_pan_update(Data(global_position=Data(x=99, y=71)))
        finish(card.handle.on_pan_end(None))
        finish(view.edit_frame(a.id, 'notes', 'Nota'))
        card.highlight(True)
        card.highlight(False)
        publish(view.content)

    def test_pdf_handles_unicode_long_text_placeholder_and_owns_images(self):
        name, _ = import_image(self.source, self.store)
        board = Storyboard('Apresentação de produto', (
            StoryFrame(title='Aproximação', image=name, action='Descrição com acentuação & <símbolos>.',
                audio='Som da máquina.\nPausa.'),
            StoryFrame(title='Detalhe', notes='Texto longo de revisão. ' * 600 + 'FIM DO STORYBOARD'),
        ))
        result = export_pdf(board, self.store, self.root / 'presentation.pdf')
        data = result.read_bytes()
        self.assertTrue(data.startswith(b'%PDF-'))
        self.assertIn(b'%%EOF', data)
        self.assertGreater(len(data), 5000)
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_failed_pdf_preserves_existing_destination_and_reports_missing_image(self):
        destination = self.root / 'existing.pdf'
        destination.write_bytes(b'original pdf')
        board = Storyboard(frames=(StoryFrame(),))
        with patch('koma.exports.pdf_export.SimpleDocTemplate.build', side_effect=ValueError('failed')):
            with self.assertRaises(ValueError):
                export_pdf(board, self.store, destination)
        self.assertEqual(destination.read_bytes(), b'original pdf')
        with self.assertRaises(ValueError):
            export_pdf(Storyboard(frames=(StoryFrame(image='a' * 32 + '.png'),)), self.store, destination)
        self.assertEqual(destination.read_bytes(), b'original pdf')


if __name__ == '__main__':
    unittest.main()
