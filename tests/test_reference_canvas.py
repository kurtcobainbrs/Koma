"""Owned reference assets, gesture transactions and compatibility; no manual UI tests."""
import json
import asyncio
from dataclasses import replace
from types import SimpleNamespace as Data
from unittest import TestCase
from unittest.mock import AsyncMock, patch
import msgpack
from flet.controls.base_control import BaseControl
from flet.controls.object_patch import ObjectPatch
from flet.messaging.protocol import configure_encode_object_for_msgpack
from koma.documents.bundle import export_bundle, restore_bundle
from koma.documents.store import StoryboardStore, document, parse_document
from koma.editor.reference_models import ReferenceImage
from koma.editor.shortcuts import Action
from koma.exports.sequence import ExportSequence
from tests import test_storyboard as fixtures


class ReferenceCanvasTests(TestCase):
    setUp = fixtures.StoryboardTests.setUp
    view = fixtures.StoryboardTests.view

    def editor(self):
        view = self.view()
        view.work_modes.show_references()
        canvas = view.references
        canvas.viewer._invoke_method = AsyncMock()
        canvas.viewer.pan = AsyncMock()
        canvas.viewer.reset = AsyncMock()
        canvas.viewer.zoom = AsyncMock()
        return view, canvas

    def test_fit_and_zoom_are_camera_only_and_old_camera_tasks_are_cancelled(self):
        view, canvas = self.editor()
        fixtures.finish(canvas.actions.import_paths([self.source], (30, 40)))
        board, count = view.board, len(view.history.past)
        fixtures.finish(canvas.execute(Action.FOCUS))
        self.assertEqual([call.args[0] for call in canvas.viewer._invoke_method.call_args_list], ['reset', 'zoom', 'pan'])
        self.assertIs(view.board, board)
        self.assertEqual(len(view.history.past), count)
        previous = canvas.camera_task
        view.work_modes.show_canvas()
        previous.cancel.assert_called()
        self.assertIsNone(canvas.camera_task)

    def test_tool_switch_gives_pan_only_to_pan_tool_without_rebinding_image_gestures(self):
        view, canvas = self.editor()
        fixtures.finish(canvas.actions.import_paths([self.source], (300, 300)))
        item = view.board.references[0]
        handler = canvas.cards[item.id].content.controls[0].content.on_pan_start
        board, count = view.board, len(view.history.past)
        self.assertFalse(canvas.viewer.pan_enabled)
        canvas.set_pan(True)
        self.assertTrue(canvas.viewer.pan_enabled)
        self.assertTrue(canvas.interaction.ignore_interactions)
        canvas.begin(item.id, Data(global_position=Data(x=0, y=0)))
        self.assertIsNone(canvas.gesture)
        canvas.set_pan(False)
        self.assertFalse(canvas.viewer.pan_enabled)
        self.assertFalse(canvas.interaction.ignore_interactions)
        self.assertIs(canvas.cards[item.id].content.controls[0].content.on_pan_start, handler)
        canvas.begin(item.id, Data(global_position=Data(x=0, y=0)))
        canvas.move(Data(global_position=Data(x=30, y=20)))
        self.assertEqual(canvas.gesture['preview'][0].x, item.x + 30)
        self.assertIs(view.board, board)
        self.assertEqual(len(view.history.past), count)
        canvas.cancel()
        camera = canvas.translation
        canvas.camera_begin(None)
        canvas.camera_move(Data(scale=1, local_focal_point=Data(x=100, y=100),
            focal_point_delta=Data(x=25, y=10)))
        self.assertEqual(canvas.translation, camera)

    def test_import_bundle_restore_undo_and_redo_keep_owned_assets(self):
        view, canvas = self.editor()
        before, history = view.board, view.history
        fixtures.finish(canvas.actions.import_paths([self.source], (30, 40)))
        self.assertEqual(len(view.history.past), 1)
        item = view.board.references[0]
        self.assertEqual((item.x, item.y, item.width, item.height), (30, 40, 320, 180))
        self.assertFalse(view.board.frames)
        self.assertFalse(ExportSequence.from_project(view.board).frames)
        self.assertEqual(self.store.load(), view.board)
        destination = export_bundle(view.board, view.store, self.root / 'references.koma')
        self.source.unlink()
        restored_store = StoryboardStore(self.root / 'restored')
        restored = restore_bundle(destination, restored_store)
        self.assertEqual(restored, view.board)
        self.assertTrue((restored_store.images / item.asset).is_file())
        fixtures.finish(view.graph.undo())
        self.assertEqual(view.board, before)
        fixtures.finish(view.graph.redo())
        self.assertEqual(view.board, restored)
        self.assertIs(view.history, history)

    def test_drag_is_temporary_local_and_cancel_restores_then_one_commit(self):
        view, canvas = self.editor()
        fixtures.finish(canvas.actions.import_paths([self.source], (200, 200)))
        item, before = view.board.references[0], view.board
        count = len(view.history.past)
        canvas.begin(item.id, Data(global_position=Data(x=10, y=10)))
        with patch.object(view, 'refresh', side_effect=AssertionError('Global refresh during drag')):
            canvas.move(Data(global_position=Data(x=70, y=50)))
            self.assertIs(view.board, before)
            self.assertEqual(len(view.history.past), count)
        canvas.cancel()
        self.assertEqual(canvas.cards[item.id].left, item.x + canvas.extent.x)
        canvas.begin(item.id, Data(global_position=Data(x=10, y=10)))
        canvas.move(Data(global_position=Data(x=70, y=50)))
        fixtures.finish(canvas.finish())
        self.assertEqual(view.board.references[0].x, item.x + 60)
        self.assertEqual(view.board.references[0].y, item.y + 40)
        self.assertEqual(len(view.history.past), count + 1)
        self.assertEqual(self.store.load(), view.board)
        canvas.begin(item.id, Data(global_position=Data(x=0, y=0)), resize=True)
        canvas.move(Data(global_position=Data(x=320, y=180)))
        fixtures.finish(canvas.finish())
        resized = view.board.references[0]
        self.assertEqual(resized.width / resized.height, item.width / item.height)
        self.assertEqual(resized.width, item.width * 2)

    def test_duplicate_delete_modes_and_preferences_do_not_touch_story_nodes(self):
        view, canvas = self.editor()
        fixtures.finish(view.add_frame())
        nodes, history = view.board.frames, view.history
        fixtures.finish(canvas.actions.import_paths([self.source], (40, 40)))
        fixtures.finish(canvas.execute(Action.DUPLICATE))
        first, second = view.board.references
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(first.asset, second.asset)
        self.assertEqual(second.x - first.x, 24)
        fixtures.finish(canvas.execute(Action.DELETE))
        self.assertEqual(view.board.references, (first,))
        before = view.board
        count = len(history.past)
        values = view.settings.configuration.editable()
        values['references'].update(background='#232323', image_width=480, wheel_sensitivity=2)
        fixtures.finish(view.settings.configuration.commit(values))
        self.assertEqual(canvas.body.bgcolor, '#232323')
        self.assertEqual(canvas.viewer.scale_factor, 120)
        self.assertIs(view.board, before)
        view.work_modes.show_canvas()
        self.assertFalse(canvas.active)
        view.player.open()
        self.assertFalse(canvas.active)
        view.work_modes.show_references()
        self.assertTrue(canvas.active)
        self.assertFalse(view.player.opened)
        self.assertEqual(view.board.frames, nodes)
        self.assertEqual(len(history.past), count)
        patch_, _, _ = ObjectPatch.from_diff(None, view.content, BaseControl)
        self.assertTrue(msgpack.packb(patch_.to_message(), default=configure_encode_object_for_msgpack(BaseControl)))

    def test_version_seven_migrates_without_rewriting_sequence_data_and_invalid_references_rejected(self):
        view, canvas = self.editor()
        from koma.editor.models import Storyboard, StoryFrame
        from koma.editor.sequence_models import SequenceState
        child = StoryFrame()
        group = StoryFrame(kind='sequence', sequence=SequenceState(members=(child.id,), entry=child.id, exit=child.id))
        original = Storyboard(frames=(group, child))
        raw = json.loads(json.dumps(document(original, view.store.document_id)))
        raw['version'] = 7
        raw.pop('references')
        migrated, _ = parse_document(raw)
        self.assertEqual(migrated.references, ())
        self.assertEqual(migrated, original)
        raw['version'] = 8
        raw['references'] = [dict(id='a' * 32, asset='../outside.png')]
        with self.assertRaises(ValueError):
            parse_document(raw)
        raw['references'] = [dict(id='a' * 32, asset='b' * 32 + '.png', width=float('nan'))]
        with self.assertRaises(ValueError):
            parse_document(raw)

    def test_clipboard_and_drop_share_import_and_use_reference_coordinates(self):
        from koma.documents.images import import_image_bytes
        view, canvas = self.editor()
        with patch.object(view.image_input, 'clipboard_source', new=AsyncMock(return_value=(import_image_bytes, self.original))):
            fixtures.finish(canvas.execute(Action.PASTE))
        self.assertEqual(len(view.board.references), 1)
        x, y = 900, 500
        event = Data(protocol=1, session_token=view.session.directory.name, files=[str(self.source)], scene_x=x, scene_y=y)
        origin = canvas.extent.x, canvas.extent.y
        fixtures.finish(canvas.dropped(event))
        dropped = view.board.references[-1]
        self.assertEqual((dropped.x, dropped.y), (x - origin[0], y - origin[1]))
        canvas.selection.replace(set())
        canvas.box_press(Data(local_position=Data(x=dropped.x + canvas.extent.x - 1, y=dropped.y + canvas.extent.y - 1)))
        canvas.box_begin(Data(local_position=Data(x=x, y=y)))
        canvas.box_move(Data(local_position=Data(x=dropped.x + canvas.extent.x + dropped.width + 1,
            y=dropped.y + canvas.extent.y + dropped.height + 1)))
        canvas.box_end()
        self.assertIn(dropped.id, canvas.selection.ids)

    def test_stale_import_and_stale_gesture_cannot_overwrite_new_data(self):
        view, canvas = self.editor()
        fixtures.finish(canvas.actions.import_paths([self.source], (200, 200)))
        item = view.board.references[0]
        canvas.begin(item.id, Data(global_position=Data(x=0, y=0)))
        canvas.move(Data(global_position=Data(x=50, y=50)))
        changed = replace(view.board, title='Changed')
        view.changed(changed)
        fixtures.finish(canvas.finish())
        self.assertEqual(view.board.title, 'Changed')
        self.assertEqual(view.board.references, (item,))
        async def source():
            view.changed(replace(view.board, title='During clipboard read'))
            from koma.documents.images import import_image
            return import_image, self.source
        count = len(view.history.past)
        with patch.object(view.image_input, 'clipboard_source', side_effect=source):
            fixtures.finish(canvas.actions.paste())
        self.assertEqual(len(view.board.references), 1)
        self.assertEqual(len(view.history.past), count + 1)

    def test_group_scale_preserves_layout_and_commits_once_with_cancel_and_undo(self):
        view, canvas = self.editor()
        fixtures.finish(canvas.actions.import_paths([self.source, self.source], (300, 300)))
        originals, board = view.board.references, view.board
        count = len(view.history.past)
        from koma.editor.reference_transform import bounds
        left, top, right, bottom = bounds(originals)
        canvas.begin(None, Data(global_position=Data(x=0, y=0)), resize=True)
        canvas.move(Data(global_position=Data(x=right-left, y=bottom-top)))
        self.assertIs(view.board, board)
        for original, preview in zip(originals, canvas.gesture['preview']):
            self.assertEqual(preview.width, original.width * 2)
            self.assertEqual(preview.height, original.height * 2)
            self.assertEqual(preview.x, left + (original.x - left) * 2)
        canvas.cancel()
        self.assertEqual(view.board.references, originals)
        canvas.begin(None, Data(global_position=Data(x=0, y=0)), resize=True)
        canvas.move(Data(global_position=Data(x=right-left, y=bottom-top)))
        fixtures.finish(canvas.finish())
        self.assertEqual(len(view.history.past), count + 1)
        self.assertEqual(self.store.load(), view.board)
        fixtures.finish(view.graph.undo())
        self.assertEqual(view.board.references, originals)
        fixtures.finish(view.graph.redo())
        self.assertEqual(view.board.references[1].width, originals[1].width * 2)

    def test_drag_uses_scene_coordinates_and_keeps_pointer_down_offset_at_any_zoom(self):
        view, canvas = self.editor()
        fixtures.finish(canvas.actions.import_paths([self.source], (400, 400)))
        original = view.board.references[0]
        for zoom in (.25, 1, 4):
            canvas.zoom = zoom
            press = Data(local_position=Data(x=20, y=20), global_position=Data(x=100, y=100))
            canvas.object_press(original.id, press)
            canvas.begin(original.id, Data(local_position=Data(x=30, y=25),
                global_position=Data(x=100 + 10 * zoom, y=100 + 5 * zoom)))
            self.assertEqual(canvas.gesture['preview'][0].x, original.x + 10)
            canvas.move(Data(local_position=Data(x=60, y=40),
                global_position=Data(x=100 + 40 * zoom, y=100 + 20 * zoom)))
            self.assertEqual(canvas.gesture['preview'][0].x, original.x + 40)
            self.assertEqual(canvas.gesture['preview'][0].y, original.y + 20)
            canvas.cancel()

    def test_open_fits_all_images_after_real_viewport_size_even_with_existing_selection(self):
        view, canvas = self.editor()
        fixtures.finish(canvas.actions.import_paths([self.source, self.source], (400, 400)))
        canvas.selection.replace({view.board.references[0].id})
        canvas.camera_used = False
        canvas.camera_revision += 1
        canvas.resized(Data(width=1200, height=700))
        board, past = view.board, tuple(view.history.past)
        asyncio.run(canvas.restore_camera(canvas.camera_revision))
        from koma.editor.reference_transform import bounds
        left, top, right, bottom = bounds(view.board.references)
        for x, y in ((left, top), (right, bottom)):
            sx = (x + canvas.extent.x) * canvas.zoom + canvas.translation[0]
            sy = (y + canvas.extent.y) * canvas.zoom + canvas.translation[1]
            self.assertGreaterEqual(sx, 0)
            self.assertLessEqual(sx, 1200)
            self.assertGreaterEqual(sy, 0)
            self.assertLessEqual(sy, 700)
        self.assertIs(view.board, board)
        self.assertEqual(tuple(view.history.past), past)

    def test_refs_roundtrip_keeps_last_camera_after_first_framing(self):
        view, canvas = self.editor()
        fixtures.finish(canvas.actions.import_paths([self.source], (400, 400)))
        canvas.resized(Data(width=1200, height=700))
        asyncio.run(canvas.restore_camera(canvas.camera_revision))
        self.assertTrue(canvas.camera_used)
        canvas.zoom = 2
        canvas.translation = (-800, -600)
        board, past = view.board, tuple(view.history.past)
        view.work_modes.show_canvas()
        view.work_modes.show_references()
        canvas.layout_ready.set()
        canvas.viewer._invoke_method.reset_mock()
        asyncio.run(canvas.restore_camera(canvas.camera_revision))
        self.assertEqual((canvas.zoom, canvas.translation), (2, (-800, -600)))
        calls = canvas.viewer._invoke_method.call_args_list
        self.assertEqual(calls[1].kwargs['arguments'], {'factor': 2})
        self.assertEqual(calls[2].kwargs['arguments'], {'dx': -400, 'dy': -300, 'dz': 0})
        self.assertIs(view.board, board)
        self.assertEqual(tuple(view.history.past), past)

    def test_fit_discards_pending_gesture_and_ignores_camera_callbacks_from_its_own_update(self):
        view, canvas = self.editor()
        fixtures.finish(canvas.actions.import_paths([self.source], (400, 400)))
        original = view.board.references[0]
        canvas.begin(original.id, Data(global_position=Data(x=0, y=0)))
        canvas.move(Data(global_position=Data(x=50, y=50)))
        async def invoke(name, arguments, timeout):
            canvas.camera_begin(None)
        canvas.viewer._invoke_method.side_effect = invoke
        board, count = view.board, len(view.history.past)
        fixtures.finish(canvas.fit())
        self.assertIsNone(canvas.gesture)
        self.assertTrue(canvas.camera_used)
        self.assertFalse(canvas.camera_applying)
        self.assertEqual([call.args[0] for call in canvas.viewer._invoke_method.call_args_list[-3:]], ['reset', 'zoom', 'pan'])
        self.assertIs(view.board, board)
        self.assertEqual(len(view.history.past), count)

    def test_first_move_and_scale_do_not_rebase_world_or_change_camera(self):
        view, canvas = self.editor()
        fixtures.finish(canvas.actions.import_paths([self.source], (300, 300)))
        item = view.board.references[0]
        canvas.zoom = 2
        canvas.translation = (-800, -600)
        extent, camera = canvas.extent, (canvas.zoom, canvas.translation)
        pending_revision = canvas.camera_revision
        canvas.viewer._invoke_method.reset_mock()
        canvas.viewer.pan.reset_mock()
        canvas.begin(item.id, Data(global_position=Data(x=1000, y=1000)))
        canvas.move(Data(global_position=Data(x=0, y=0)))
        fixtures.finish(canvas.finish())
        self.assertEqual(view.board.references[0].x, -200)
        self.assertEqual(canvas.extent, extent)
        self.assertEqual((canvas.zoom, canvas.translation), camera)
        canvas.begin(item.id, Data(global_position=Data(x=0, y=0)), resize=True)
        canvas.move(Data(global_position=Data(x=640, y=360)))
        fixtures.finish(canvas.finish())
        self.assertEqual(view.board.references[0].width, 640)
        self.assertEqual(canvas.extent, extent)
        self.assertEqual((canvas.zoom, canvas.translation), camera)
        canvas.layout_ready.set()
        asyncio.run(canvas.restore_camera(pending_revision))
        canvas.viewer._invoke_method.assert_not_called()
        canvas.viewer.pan.assert_not_called()

    def test_native_camera_initial_pose_and_fit_use_one_state_patch_without_runtime_calls(self):
        from koma.ui.spatial_view import SpatialView
        with patch('koma.ui.drop_runtime.supports', side_effect=lambda feature: feature == 'spatial_camera_v1'):
            view = self.view()
        view.work_modes.show_references()
        canvas = view.references
        self.assertIsInstance(canvas.viewer, SpatialView)
        self.assertEqual(canvas.viewer.camera_x, -canvas.extent.x)
        fixtures.finish(canvas.actions.import_paths([self.source], (400, 400)))
        board, past = view.board, tuple(view.history.past)
        revision = canvas.viewer.camera_revision
        with patch.object(canvas.viewer, '_invoke_method', new=AsyncMock(side_effect=AssertionError('Imperative camera call'))):
            fixtures.finish(canvas.fit(all_items=True))
        self.assertEqual(canvas.viewer.camera_revision, revision + 1)
        self.assertEqual(canvas.viewer.camera_zoom, canvas.zoom)
        self.assertEqual((canvas.viewer.camera_x, canvas.viewer.camera_y), canvas.translation)
        self.assertIs(view.board, board)
        self.assertEqual(tuple(view.history.past), past)

    def test_secondary_pan_reuses_canvas_navigation_and_changes_camera_only(self):
        from koma.ui.canvas_gestures import NativeSecondaryPan
        with patch('koma.ui.drop_runtime.enabled', return_value=True), patch('koma.ui.drop_runtime.supports', return_value=True):
            view = self.view()
        view.work_modes.show_references()
        canvas = view.references
        self.assertIsInstance(canvas.secondary_pan, NativeSecondaryPan)
        self.assertIs(canvas.secondary_pan.content, canvas.viewer)
        self.assertTrue(canvas.secondary_pan.pan_enabled)
        board, past = view.board, tuple(view.history.past)
        canvas.secondary_navigation(Data(moved=True, zoom=2, translation_x=-200, translation_y=-300))
        self.assertEqual((canvas.zoom, canvas.translation), (2, (-200, -300)))
        self.assertEqual((canvas.viewer.camera_x, canvas.viewer.camera_y), (-200, -300))
        self.assertFalse(canvas.pan_mode)
        self.assertFalse(canvas.viewer.pan_enabled)
        self.assertIs(view.board, board)
        self.assertEqual(tuple(view.history.past), past)
        view.work_modes.show_canvas()
        canvas.secondary_navigation(Data(moved=True, zoom=4, translation_x=0, translation_y=0))
        self.assertEqual((canvas.zoom, canvas.translation), (2, (-200, -300)))

    def test_g_s_preview_confirm_cancel_share_drag_history_and_remap(self):
        from koma.editor.shortcuts import Action
        view, canvas = self.editor()
        fixtures.finish(canvas.actions.import_paths([self.source], (400, 400)))
        original, before = view.board.references[0], view.board
        count = len(view.history.past)
        canvas.transform_mode.hover(Data(global_position=Data(x=100, y=100)))
        fixtures.finish(canvas.key_down(Data(key='g')))
        self.assertTrue(canvas.transform_mode.active)
        self.assertFalse(canvas.viewer.scale_enabled)
        canvas.transform_mode.hover(Data(global_position=Data(x=140, y=120)))
        self.assertIs(view.board, before)
        fixtures.finish(canvas.key_down(Data(key='Enter')))
        self.assertFalse(canvas.transform_mode.active)
        self.assertEqual(view.board.references[0].x, original.x + 40)
        self.assertEqual(len(view.history.past), count + 1)
        moved = view.board
        fixtures.finish(canvas.key_down(Data(key='s')))
        canvas.transform_mode.hover(Data(global_position=Data(x=460, y=300)))
        self.assertEqual(canvas.gesture['preview'][0].width, original.width * 2)
        fixtures.finish(canvas.key_down(Data(key='Escape')))
        self.assertIs(view.board, moved)
        self.assertTrue(canvas.viewer.scale_enabled)
        self.assertEqual(len(view.history.past), count + 1)
        view.keymap.rebind(Action.SCALE_REFS, ('Q',))
        fixtures.finish(canvas.key_down(Data(key='q')))
        canvas.transform_mode.hover(Data(global_position=Data(x=780, y=480)))
        fixtures.finish(canvas.key_down(Data(key='Enter')))
        self.assertEqual(view.board.references[0].width, original.width * 2)
        self.assertEqual(len(view.history.past), count + 2)
        fixtures.finish(view.graph.undo())
        self.assertEqual(view.board, moved)
        fixtures.finish(view.graph.redo())
        self.assertEqual(self.store.load(), view.board)

    def test_scale_alignment_preserves_proportion_fixed_corner_and_undo(self):
        from koma.editor.reference_transform import AlignmentIndex
        item = ReferenceImage(asset='a' * 32 + '.png', width=100, height=50)
        target = replace(item, x=200, y=100)
        index = AlignmentIndex.from_items((target,))
        preview, guides = index.scale((item,), 95, 47.5, 8)
        self.assertEqual((preview[0].width, preview[0].height), (200, 100))
        self.assertEqual((preview[0].x, preview[0].y), (0, 0))
        self.assertEqual(guides, (200, 100))
        free, guides = index.scale((item,), 95, 47.5, 1)
        self.assertEqual(free[0].width, 195)
        self.assertEqual(guides, (None, None))
        view, canvas = self.editor()
        fixtures.finish(canvas.actions.import_paths([self.source, self.source], (300, 300)))
        first, second = view.board.references
        canvas.selection.replace({first.id})
        before = view.board
        canvas.begin(None, Data(global_position=Data(x=0, y=0)), resize=True)
        canvas.move(Data(global_position=Data(x=20, y=11.25)))
        preview = canvas.gesture['preview'][0]
        self.assertEqual(preview.x + preview.width, second.x)
        self.assertTrue(canvas.overlays.guides.shapes)
        self.assertIs(view.board, before)
        fixtures.finish(canvas.finish())
        self.assertFalse(canvas.overlays.guides.shapes)
        fixtures.finish(view.graph.undo())
        self.assertEqual(view.board, before)

    def test_grid_and_alignment_use_visible_local_canvas_after_camera_transform(self):
        view, canvas = self.editor()
        fixtures.finish(canvas.actions.import_paths([self.source, self.source], (300, 300)))
        first, second = view.board.references
        canvas.zoom = 2
        canvas.viewport = (1600, 700)
        canvas.translation = (24 - (canvas.extent.x + 300) * 2, 24 - (canvas.extent.y + 300) * 2)
        canvas.toggle_option('grid_enabled')
        grid = canvas.overlays.grid_box
        self.assertTrue(grid.visible)
        self.assertEqual((grid.width, grid.height), (800, 350))
        self.assertTrue(all(-24 <= line.x1 <= 824 and -24 <= line.y1 <= 374
            for line in canvas.overlays.grid.shapes))
        canvas.tap(first.id)
        self.assertEqual(canvas.selection.ids, {first.id})
        before = view.board
        canvas.begin(first.id, Data(local_position=Data(x=0, y=0), global_position=Data(x=0, y=0)))
        canvas.move(Data(local_position=Data(x=23, y=0), global_position=Data(x=46, y=0)))
        self.assertEqual(canvas.gesture['preview'][0].x + first.width, second.x)
        guides = canvas.overlays.guide_box
        self.assertEqual((guides.width, guides.height), (800, 350))
        self.assertTrue(canvas.overlays.guides.shapes)
        self.assertTrue(all(0 <= line.x1 <= guides.width and 0 <= line.y1 <= guides.height
            for line in canvas.overlays.guides.shapes))
        canvas.cancel()
        canvas.begin(None, Data(local_position=Data(x=0, y=0), global_position=Data(x=0, y=0)), resize=True)
        canvas.move(Data(local_position=Data(x=22, y=12.375), global_position=Data(x=44, y=24.75)))
        preview = canvas.gesture['preview'][0]
        self.assertEqual(preview.x + preview.width, second.x)
        self.assertTrue(canvas.overlays.guides.shapes)
        canvas.cancel()
        self.assertIs(view.board, before)

    def test_smart_alignment_grid_and_guides_are_transient_and_preferences_are_global(self):
        from koma.editor.reference_transform import AlignmentIndex
        target = ReferenceImage(asset='a' * 32 + '.png', x=500, y=300, width=100, height=80)
        index = AlignmentIndex.from_items(item for item in (target,))
        self.assertEqual(index.snap((0, 0, 100, 80), 397, 219, 8), (400, 220, (500, 300)))
        self.assertEqual(index.snap((0, 0, 100, 80), 397, 219, 2), (397, 220, (None, 300)))
        self.assertEqual(index.snap((0, 0, 100, 80), 397, 219, 8, smart=False, grid=24), (408, 216, (None, None)))
        view, canvas = self.editor()
        fixtures.finish(canvas.actions.import_paths([self.source], (100, 100)))
        values = view.settings.configuration.editable()
        values['references'].update(grid=True, grid_snap=True, grid_spacing=24, smart_align=False)
        board, count = view.board, len(view.history.past)
        fixtures.finish(view.settings.configuration.commit(values))
        self.assertTrue(canvas.grid_enabled)
        self.assertTrue(canvas.grid_snap)
        self.assertTrue(canvas.overlays.grid.shapes)
        self.assertIs(view.board, board)
        self.assertEqual(len(view.history.past), count)
        canvas.begin(board.references[0].id, Data(global_position=Data(x=0, y=0)))
        canvas.move(Data(global_position=Data(x=17, y=17)))
        self.assertEqual(canvas.gesture['preview'][0].x, 120)
        canvas.cancel()
        self.assertFalse(canvas.overlays.guides.shapes)
        self.assertIs(view.board, board)
