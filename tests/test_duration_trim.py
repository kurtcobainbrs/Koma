"""Shared-cut/ripple integration and guards against expensive pointer updates."""
from dataclasses import replace
from types import SimpleNamespace as Data
from unittest import TestCase
from unittest.mock import patch
from tests import test_storyboard as fixtures
from koma.editor.models import StoryFrame, Storyboard, MAX_DURATION
from koma.editor.timeline import Timeline, TimeScale
from koma.editor.duration_trim import DurationTrim
from koma.editor.shortcuts import Action
from koma.editor.media_models import TimelineMarker
from koma.exports.video_export import frame_counts


class DurationTrimTests(TestCase):
    setUp = fixtures.StoryboardTests.setUp
    view = fixtures.StoryboardTests.view

    def editor(self):
        view = self.view()
        for _ in range(3):
            fixtures.finish(view.add_frame())
        view.changed(replace(view.board, markers=(TimelineMarker(position=4),)))
        view.player.open()
        view.player.strip.resized(Data(width=800))
        return view, view.player

    def test_roll_keeps_later_cuts_and_marker_fixed_with_one_save_and_history_entry(self):
        view, player = self.editor()
        before, history = view.board, len(view.history.past)
        with patch.object(view.store, 'save', wraps=view.store.save) as save:
            token = player.duration_editor.begin(before.frames[0].id, 0, TimeScale(100))
            player.duration_editor.move(token, 50)
            self.assertIs(view.board, before)
            self.assertEqual(tuple(frame.duration for frame in player.timeline.frames), (2.5, 1.5, 2))
            self.assertEqual(player.timeline.starts[2], 4)
            self.assertEqual(player.timeline.total, 6)
            save.assert_not_called()
            fixtures.finish(player.duration_editor.finish(token))
            save.assert_called_once()
        self.assertEqual(view.board.markers, before.markers)
        self.assertEqual(view.board.frames[2], before.frames[2])
        self.assertEqual(len(view.history.past), history + 1)
        self.assertEqual(frame_counts(view.board.frames, 24), [60, 36, 48])
        self.assertEqual(view.store.load(), view.board)
        fixtures.finish(player.strip.undo_edit())
        self.assertEqual(view.board, before)
        fixtures.finish(player.strip.redo_edit())
        self.assertEqual(tuple(frame.duration for frame in view.board.frames), (2.5, 1.5, 2))

    def test_modifier_uses_keymap_and_ripple_moves_later_cuts(self):
        view, player = self.editor()
        for modifier in ('Shift', 'Ctrl'):
            view.keymap.rebind(Action.RIPPLE_DURATION, (modifier,))
            block = next(iter(player.strip.blocks.values()))
            scale = player.strip.scale
            with patch('koma.ui.timeline_strip.pressed_modifiers', return_value={modifier}):
                block.begin(Data(global_position=Data(x=0)))
            self.assertTrue(block.token.ripple)
            block.move(Data(global_position=Data(x=scale.pixels(.5))))
            self.assertEqual(tuple(frame.duration for frame in player.timeline.frames), (2.5, 2, 2))
            self.assertEqual(player.timeline.starts[2], 4.5)
            fixtures.finish(block.finish(None))
            self.assertEqual(frame_counts(view.board.frames, 24), [60, 48, 48])
            fixtures.finish(player.strip.undo_edit())

    def test_limits_stop_at_one_frame_without_falling_back_to_ripple(self):
        view, player = self.editor()
        token = player.duration_editor.begin(view.board.frames[0].id, 0, TimeScale(100))
        player.duration_editor.move(token, 10000)
        self.assertAlmostEqual(player.timeline.frames[1].duration, 1 / 24)
        self.assertEqual(player.timeline.starts[2], 4)
        self.assertEqual(player.timeline.total, 6)
        with patch.object(player, 'render_duration_preview') as render:
            player.duration_editor.move(token, 20000)
            render.assert_not_called()
        player.duration_editor.cancel()

    def test_cancel_restores_both_labels_without_a_save(self):
        view, player = self.editor()
        before = view.board
        labels = tuple(view.cards[frame.id].duration.value for frame in before.frames)
        history = len(view.history.past)
        with patch.object(view.store, 'save') as save:
            token = player.duration_editor.begin(before.frames[0].id, 0, TimeScale(100))
            player.duration_editor.move(token, 75)
            player.duration_editor.cancel()
            save.assert_not_called()
        self.assertIs(view.board, before)
        self.assertEqual(len(view.history.past), history)
        self.assertEqual(tuple(view.cards[frame.id].duration.value for frame in before.frames), labels)
        self.assertFalse(view.busy)

    def test_start_and_pointer_updates_do_not_touch_canvas_images_or_validate_drawings(self):
        view, player = self.editor()
        view.page.update.reset_mock()
        with patch.object(player.preview, 'set_frame') as image, \
                patch.object(player.drawing_surface, 'sync') as drawing, \
                patch.object(StoryFrame, 'validate', side_effect=AssertionError('Heavy validation during drag')):
            token = player.duration_editor.begin(view.board.frames[0].id, 0, TimeScale(100))
            for x in (25, 50, 75):
                player.duration_editor.move(token, x)
            image.assert_not_called()
            drawing.assert_not_called()
        for call in view.page.update.call_args_list:
            self.assertFalse(any(control is view.content or control is view.canvas for control in call.args))
        player.duration_editor.cancel()

    def test_last_frame_changes_total_and_fractional_pairs_preserve_originals(self):
        frames = (StoryFrame(duration=.1), StoryFrame(duration=MAX_DURATION))
        timeline = Timeline(Storyboard(frames=frames))
        trim = DurationTrim.at(timeline, 0)
        self.assertEqual(trim.resolve(.1), trim.originals)
        values = trim.resolve(-100)
        self.assertLessEqual(values[frames[1].id], MAX_DURATION)
        self.assertAlmostEqual(sum(values.values()), .1 + MAX_DURATION)
        last = DurationTrim.at(timeline, 1)
        self.assertEqual(last.resolve(3), {frames[1].id: 3})
        short = Timeline(Storyboard(frames=(StoryFrame(duration=1 / 60), StoryFrame(duration=1 / 60))))
        trim = DurationTrim.at(short, 0)
        self.assertEqual(trim.resolve(2), trim.originals)
