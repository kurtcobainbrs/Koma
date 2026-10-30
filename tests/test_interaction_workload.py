"""Exercise real Flet patches, not just mocked update calls, on hot interactions."""
from dataclasses import replace
from types import SimpleNamespace as Data
from unittest import TestCase
from unittest.mock import patch

from flet.controls.base_control import BaseControl
from flet.controls.object_patch import ObjectPatch, DiffBuilder
from koma.editor.drawing_models import DrawingLayer, DrawingStroke
from koma.editor.models import StoryFrame, StoryLink
from koma.editor.timeline import TimeScale
from tests import test_storyboard as fixtures


class InteractionWorkloadTests(TestCase):
    setUp = fixtures.StoryboardTests.setUp
    view = fixtures.StoryboardTests.view

    def editor(self):
        layer = DrawingLayer((DrawingStroke(tuple((i / 100, i / 100) for i in range(100))),))
        frames = tuple(StoryFrame(x=i * 400, y=0, drawing=layer) for i in range(8))
        self.session.board = replace(self.session.board, frames=frames,
            links=tuple(StoryLink(a.id, b.id) for a, b in zip(frames, frames[1:])))
        view = self.view()
        view.workspace.navigation.apply_selection({frames[0].id}, frames[0].id)
        ObjectPatch.from_diff(None, view.content, BaseControl)
        def update(*roots):
            for root in roots:
                ObjectPatch.from_diff(root, root, BaseControl)
        view.page.update.side_effect = update
        return view, view.player

    def guard(self, forbidden):
        original = DiffBuilder._compare_dataclasses
        def compare(instance, parent, path, src, dst, frozen):
            if any(dst is item for item in forbidden):
                raise AssertionError('Stable media/vector content traversed during local interaction')
            return original(instance, parent, path, src, dst, frozen)
        return patch.object(DiffBuilder, '_compare_dataclasses', compare)

    def test_selection_and_raise_skip_card_media_and_batch_the_updates(self):
        view, player = self.editor()
        media = [card.viewport.stack for card in view.cards.values()]
        with self.guard(media):
            view.page.update.reset_mock()
            view.workspace.navigation.apply_selection(set(view.cards))
            self.assertEqual(view.page.update.call_count, 1)
            view.workspace.raise_node(view.board.frames[0].id)
        self.assertTrue(all(not card.box.content.is_isolated() for card in view.cards.values()))

    def test_mode_roundtrip_reuses_timeline_and_skips_stable_media(self):
        view, player = self.editor()
        player.open()
        player.strip.resized(Data(width=900))
        timeline = player.timeline
        media = [card.viewport.stack for card in view.cards.values()]
        media += [block.thumbnail.drawing.canvas for block in player.strip.blocks.values()]
        media += [player.preview.stack, player.drawing_surface.overlay.canvas]
        with self.guard(media), patch('koma.editor.animatic.Timeline', side_effect=AssertionError('Rebuilt unchanged timeline')):
            player.close()
            player.open()
        self.assertIs(player.timeline, timeline)

    def test_duration_pointer_patches_skip_waveform_and_thumbnail_paths(self):
        view, player = self.editor()
        player.open()
        player.strip.resized(Data(width=900))
        stable = [block.thumbnail.drawing.canvas for block in player.strip.blocks.values()]
        stable.append(player.strip.audio_lane.canvas.shapes[0])
        before = view.board
        with self.guard(stable):
            token = player.duration_editor.begin(before.frames[0].id, 0, TimeScale(100))
            for x in (20, 35, 50, 65):
                player.duration_editor.move(token, x)
        self.assertIs(view.board, before)
        player.duration_editor.cancel()

    def test_selection_highlight_reuses_connection_geometry(self):
        view, player = self.editor()
        samples = {edge: cached[2] for edge, cached in view.workspace.links.cache.items()}
        with patch('koma.editor.links_layer.route', side_effect=AssertionError('Rerouted unchanged wire')):
            view.workspace.navigation.apply_selection({view.board.frames[-1].id})
        self.assertTrue(all(view.workspace.links.cache[edge][2] is points for edge, points in samples.items()))

    def test_model_edit_in_canvas_invalidates_retained_animatic_content(self):
        view, player = self.editor()
        player.open()
        player.close()
        frame = view.board.frames[0]
        fixtures.finish(view.set_frame_properties(frame.id, drawing=DrawingLayer()))
        with patch.object(view.work_modes, 'show', wraps=view.work_modes.show) as show:
            player.open()
        self.assertFalse(show.call_args.kwargs['retain_timeline'])
        self.assertIs(player.timeline.frames[0], view.board.frames[0])

    def test_repeated_modes_restore_selection_and_cancel_temporary_pointer_state(self):
        view, player = self.editor()
        ws, nav = view.workspace, view.workspace.navigation
        before = view.board
        for _ in range(4):
            nav.temporary_pan = True
            nav.sync(update=False)
            self.assertTrue(ws.scene.ignore_interactions)
            ws.secondary_pointer.press = Data()
            player.open()
            self.assertIsNone(ws.secondary_pointer.press)
            player.close()
            self.assertTrue(view.work_modes.canvas.visible)
            self.assertFalse(view.work_modes.animatic.visible)
            self.assertIs(view.work_modes.active_surface, view.work_modes.canvas)
            self.assertFalse(ws.scene.ignore_interactions)
            self.assertFalse(ws.viewer.pan_enabled)
            self.assertTrue(ws.viewer.scale_enabled)
            fixtures.finish(nav.background_click(None))
            self.assertFalse(nav.selection.ids)
            card = view.cards[before.frames[0].id].content
            start = Data(local_position=Data(x=card.left - 1, y=card.top - 1))
            end = Data(local_position=Data(x=card.left + card.width + 1, y=card.top + 40))
            ws.box_selection.press(start)
            ws.box_selection.begin(start)
            ws.box_selection.update(end)
            ws.box_selection.end()
            self.assertIn(before.frames[0].id, nav.selection.ids)
        self.assertIs(view.board, before)

    def test_late_animatic_layout_and_scroll_events_do_no_work_after_returning(self):
        view, player = self.editor()
        player.open()
        player.strip.resized(Data(width=900))
        player.close()
        before = (player.preview_bounds, player.preview.width, player.preview.height,
            player.drawing_surface.bounds, player.strip.width, player.strip.offset)
        view.page.update.reset_mock()
        with patch.object(player.drawing_surface, 'redraw', side_effect=AssertionError('Inactive drawing redraw')), \
                patch.object(player.strip, 'sync', side_effect=AssertionError('Inactive timeline update')):
            for i in range(100):
                size = Data(width=800 + i, height=450 + i)
                player.preview_resized(size)
                player.preview.resized(size)
                player.drawing_surface.resized(size)
                player.strip.resized(size)
                player.strip.scrolled(Data(pixels=i))
        view.page.update.assert_not_called()
        self.assertEqual(before, (player.preview_bounds, player.preview.width, player.preview.height,
            player.drawing_surface.bounds, player.strip.width, player.strip.offset))
