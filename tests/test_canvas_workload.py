"""Bound redundant canvas work without relying on timing or a desktop session."""
from dataclasses import replace
from types import SimpleNamespace as Data
from unittest import TestCase
from unittest.mock import AsyncMock, Mock, patch

from koma.editor.models import StoryFrame
from koma.editor.view import StoryboardView, CARD_BUILD_BATCH
from koma.preferences import AppPreferences
from koma.ui.image_source import thumbnail_source
from koma.ui.retained_container import RetainedContainer
import flet as ft
import msgpack
from flet.controls.base_control import BaseControl
from flet.controls.object_patch import ObjectPatch
from flet.messaging.protocol import configure_encode_object_for_msgpack
from tests import test_storyboard as fixtures


class CanvasWorkloadTests(TestCase):
    setUp = fixtures.StoryboardTests.setUp
    view = fixtures.StoryboardTests.view

    def test_background_clears_selection_and_box_selection_works_after_grab(self):
        view = self.view()
        for _ in range(2):
            fixtures.finish(view.add_frame())
        ws = view.workspace
        ws.navigation.apply_selection(set(view.cards))
        ws.grab.start()
        ws.grab.cancel()
        self.assertIsInstance(ws.motion_layer, ft.Stack)
        self.assertFalse(ws.motion_layer.is_isolated())
        fixtures.finish(ws.background_hit.on_tap_down(None))
        self.assertFalse(ws.navigation.selection.ids)
        card = view.cards[view.board.frames[0].id].content
        start = Data(local_position=Data(x=card.left - 10, y=card.top - 10))
        end = Data(local_position=Data(x=card.left + card.width + 10, y=card.top + 40))
        ws.background_hit.on_pan_down(start)
        ws.background_hit.on_pan_start(start)
        ws.background_hit.on_pan_update(end)
        self.assertTrue(ws.box_selection.overlay.visible)
        self.assertIn(view.board.frames[0].id, ws.navigation.selection.ids)
        ws.background_hit.on_pan_end(None)
        self.assertFalse(ws.box_selection.overlay.visible)

    def test_retained_body_skips_gesture_traversal_and_flushes_changes_afterwards(self):
        held = False
        text = ft.Text('Before')
        body = RetainedContainer(hold_updates=lambda: held, content=text)
        node = RetainedContainer(hold_updates=lambda: held, content=body, left=0)
        encoder = configure_encode_object_for_msgpack(BaseControl)
        def encode(previous):
            patch_, _, _ = ObjectPatch.from_diff(previous, node, BaseControl)
            return msgpack.packb(patch_.to_message(), default=encoder)
        encode(None)
        held = True
        text.value = 'Pending body change'
        node.left = 48
        self.assertNotIn(b'Pending body change', encode(node))
        held = False
        self.assertIn(b'Pending body change', encode(node))

    def test_whole_scene_moves_as_one_preview_and_commits_once_with_undo(self):
        view = self.view()
        for _ in range(3):
            fixtures.finish(view.add_frame())
        ws = view.workspace
        ws.navigation.apply_selection(set(view.cards))
        def event(x, y):
            return Data(global_position=Data(x=x, y=y), local_position=Data(x=x, y=y))
        ws.hover(event(0, 0))
        ws.grab.start()
        self.assertTrue(ws.drag.rigid)
        board, history = view.board, len(view.history.past)
        with patch.object(ws.links, 'refresh', wraps=ws.links.refresh) as links:
            view.page.update.reset_mock()
            ws.hover(event(48, 72))
            links.assert_not_called()
            view.page.update.assert_called_once_with(ws.motion_layer)
        self.assertIs(view.board, board)
        self.assertIsNotNone(ws.motion_layer.offset)
        fixtures.finish(ws.grab.confirm())
        self.assertEqual(len(view.history.past), history + 1)
        self.assertIsNone(ws.motion_layer.offset)
        self.assertEqual([(f.x, f.y) for f in view.board.frames], [(f.x + 48, f.y + 72) for f in board.frames])
        fixtures.finish(view.graph.undo())
        self.assertEqual(view.board, board)
        ws.hover(event(0, 0))
        ws.grab.start()
        ws.hover(event(120, 120))
        ws.grab.cancel()
        self.assertIsNone(ws.motion_layer.offset)
        self.assertEqual(view.board, board)

    def test_duplicate_reuses_local_image_and_skips_unchanged_card_content(self):
        view = self.view()
        with patch('koma.ui.drop_runtime.enabled', return_value=True):
            fixtures.finish(view.import_paths([self.source]))
            original = view.board.frames[0]
            view.workspace.navigation.apply_selection(set())
            view.refresh()
            card = view.cards[original.id]
            expected = str(view.store.thumbnails / original.image)
            self.assertEqual(card.viewport.image.src, expected)
            before = original
            with patch.object(card.viewport, 'set_frame', wraps=card.viewport.set_frame) as sync:
                fixtures.finish(view.duplicate_frames({original.id}))
                sync.assert_not_called()
            copy = next(frame for frame in view.board.frames if frame.id != original.id)
            self.assertEqual(view.cards[copy.id].viewport.image.src, expected)
            self.assertIs(view.board.frames[0], before)
            self.assertEqual(copy.image, original.image)
            fixtures.finish(view.graph.undo())
            self.assertEqual(view.board.frames, (original,))
            fixtures.finish(view.graph.redo())
            self.assertEqual(len(view.board.frames), 2)
        with patch('koma.ui.drop_runtime.enabled', return_value=False):
            self.assertIs(thumbnail_source(view, original.image), view.thumbnails[original.image])

    def test_repeated_grab_pointer_does_not_refresh_links_or_modify_document(self):
        view = self.view()
        fixtures.finish(view.add_frame())
        frame = view.board.frames[0]
        ws = view.workspace
        ws.navigation.apply_selection({frame.id})
        point = Data(global_position=Data(x=10, y=10), local_position=Data(x=10, y=10))
        ws.hover(point)
        ws.grab.start()
        before = view.board
        moved = Data(global_position=Data(x=100, y=100), local_position=Data(x=100, y=100))
        with patch.object(ws.links, 'refresh', wraps=ws.links.refresh) as refresh:
            ws.hover(moved)
            ws.hover(moved)
            refresh.assert_called_once()
        self.assertIs(view.board, before)
        ws.grab.cancel()
        self.assertIs(view.board, before)

    def test_large_document_build_yields_between_bounded_batches(self):
        frames = tuple(StoryFrame(x=index * 20, y=0) for index in range(CARD_BUILD_BATCH * 2))
        self.session.board = replace(self.session.board, frames=frames)
        view = StoryboardView(Mock(), self.session, AppPreferences(self.root / 'data'))
        activation = view.activate()
        yields = 0
        try:
            while True:
                activation.send(None)
                yields += 1
                self.assertTrue(view.busy)
                self.assertLessEqual(len(view.cards), yields * CARD_BUILD_BATCH)
        except StopIteration:
            pass
        finally:
            activation.close()
        self.assertEqual(yields, 2)
        self.assertTrue(view.loaded)
        self.assertFalse(view.load_error)
        self.assertEqual(len(view.cards), len(frames))

    def test_layout_burst_refreshes_links_once_and_cancel_discards_late_work(self):
        view = self.view()
        fixtures.finish(view.add_frame())
        ws = view.workspace
        identifier = view.board.frames[0].id
        view.page.run_task.reset_mock()
        with patch.object(ws.links, 'refresh', wraps=ws.links.refresh) as refresh:
            for height in range(300, 400):
                ws.node_resized(identifier, Data(height=height))
            self.assertEqual(ws.node_heights[identifier], 399)
            refresh.assert_not_called()
            view.page.run_task.assert_called_once()
            token = ws.measurements.token
            with patch('asyncio.sleep', new=AsyncMock()):
                fixtures.finish(ws.measurements.flush(token))
            refresh.assert_called_once()
            ws.node_resized(identifier, Data(height=450))
            token = ws.measurements.token
            ws.measurements.cancel()
            with patch('asyncio.sleep', new=AsyncMock()):
                fixtures.finish(ws.measurements.flush(token))
            self.assertEqual(refresh.call_count, 1)
