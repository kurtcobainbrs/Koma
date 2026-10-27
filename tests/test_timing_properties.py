"""Conversão de unidades, FPS persistido e duração de um frame no editor."""

from dataclasses import replace
import json
from types import SimpleNamespace as Data
from unittest import TestCase
from unittest.mock import AsyncMock

from tests import test_storyboard as fixtures
from koma.documents.store import document, parse_document
from koma.exports.video_export import frame_counts


class TimingTests(TestCase):
    setUp = fixtures.StoryboardTests.setUp
    view = fixtures.StoryboardTests.view

    def editor(self):
        view = self.view()
        fixtures.finish(view.add_frame())
        view.workspace.navigation.apply_selection({view.board.frames[0].id})
        return view, view.properties

    def enter(self, field, value):
        field.value = value
        fixtures.finish(field.on_change(Data(control=field)))

    def test_frames_update_seconds_card_and_export(self):
        view, props = self.editor()
        self.enter(props.duration_frames, '36')
        self.assertEqual(view.board.frames[0].duration, 1.5)
        self.assertEqual(props.duration.value, '1.5')
        self.assertEqual(frame_counts(view.board.frames, view.board.fps), [36])
        self.assertEqual(view.cards[view.board.frames[0].id].duration.value, '36 f · 1.5 s')
        self.assertEqual(view.store.load(), view.board)

    def test_expressions_update_both_units_and_invalid_expressions_preserve_model(self):
        view, props = self.editor()
        self.enter(props.duration_frames, '(24+12)*2')
        self.assertEqual(view.board.frames[0].duration, 3)
        self.assertEqual(props.duration.value, '3')
        self.assertEqual(frame_counts(view.board.frames, view.board.fps), [72])
        self.enter(props.duration, '1,5/2')
        self.assertEqual(props.duration_frames.value, '18')
        before = view.board
        for field in (props.duration, props.duration_frames):
            for text in ('24*', '1/0', '1-2', '3600*100', 'open("file")'):
                self.enter(field, text)
                self.assertIs(view.board, before)
                self.assertIsNotNone(field.error_text)
        self.enter(props.duration_frames, '24*2')
        self.assertIsNone(props.duration_frames.error_text)
        self.assertEqual(view.board.frames[0].duration, 2)
        self.assertEqual(props.duration.value, '2')

    def test_seconds_with_comma_update_frames_including_subframes(self):
        view, props = self.editor()
        self.enter(props.duration, '1,5')
        self.assertEqual(props.duration_frames.value, '36')
        self.enter(props.duration, '0,1')
        self.assertEqual(props.duration_frames.value, '2.4')
        self.assertEqual(view.board.frames[0].duration, .1)

    def test_enter_displays_expression_result_without_an_extra_history_entry(self):
        view, props = self.editor()
        for field, expression, result, other, converted in (
                (props.duration_frames, '24*3', '72', props.duration, '3'),
                (props.duration, '1,5/2', '0.75', props.duration_frames, '18')):
            self.enter(field, expression)
            history = len(view.history.past)
            fixtures.finish(field.on_submit(Data(control=field)))
            self.assertEqual(field.value, result)
            self.assertEqual(other.value, converted)
            self.assertEqual(len(view.history.past), history)
            self.assertIsNone(field.error_text)

    def test_enter_rejects_invalid_expression_without_replacing_input(self):
        view, props = self.editor()
        before = view.board
        for field in (props.duration, props.duration_frames):
            field.value = '24/0'
            fixtures.finish(field.on_submit(Data(control=field)))
            self.assertEqual(field.value, '24/0')
            self.assertIsNotNone(field.error_text)
            self.assertIs(view.board, before)

    def test_one_frame_at_each_supported_fps(self):
        view, props = self.editor()
        for fps in (24, 25, 30, 60):
            view.project_properties.fps.value = str(fps)
            fixtures.finish(view.project_properties.fps_changed())
            self.enter(props.duration_frames, '1')
            self.assertAlmostEqual(view.board.frames[0].duration, 1 / fps)
            self.assertEqual(frame_counts(view.board.frames, fps), [1])
            props.sync()
            self.assertEqual(props.duration_frames.value, '1')

    def test_invalid_input_preserves_duration_and_reports_error(self):
        view, props = self.editor()
        before = view.board
        for field in (props.duration, props.duration_frames):
            for value in ('0', '-1', 'nan', 'inf', 'abc', '999999999'):
                self.enter(field, value)
                self.assertIsNotNone(field.error_text)
                self.assertEqual(view.board, before)

    def test_fps_preserves_seconds_persists_and_undo_restores_conversion(self):
        view, props = self.editor()
        view.project_properties.fps.value = '30'
        fixtures.finish(view.project_properties.fps_changed())
        self.assertEqual(view.board.fps, 30)
        self.assertEqual(view.board.frames[0].duration, 2)
        self.assertEqual(props.duration_frames.value, '60')
        restored, _ = parse_document(json.loads(json.dumps(document(view.board, view.store.document_id))))
        self.assertEqual(restored.fps, 30)
        self.assertEqual(view.store.load().fps, 30)
        fixtures.finish(view.graph.undo())
        self.assertEqual(view.project_properties.fps.value, '24')
        self.assertEqual(props.duration_frames.value, '48')

    def test_legacy_document_defaults_to_24_and_invalid_fps_is_rejected(self):
        view, _ = self.editor()
        raw = json.loads(json.dumps(document(view.board, view.store.document_id)))
        del raw['fps']
        self.assertEqual(parse_document(raw)[0].fps, 24)
        for fps in (True, 23, '24', 24.0):
            with self.assertRaises(ValueError):
                replace(view.board, fps=fps).validate()

    def test_export_uses_project_fps(self):
        view, props = self.editor()
        view.project_properties.fps.value = '60'
        fixtures.finish(view.project_properties.fps_changed())
        view.files.pick_video = AsyncMock()
        view.files.video_options()
        popup = view.page.show_dialog.call_args.args[0]
        fixtures.finish(popup.actions[-1].on_click(None))
        self.assertEqual(view.files.pick_video.call_args.args[2], 60)

