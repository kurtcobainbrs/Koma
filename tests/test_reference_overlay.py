"""Reference export: selectable fields, exact counters, ranges and real MP4."""
from unittest import TestCase
from unittest.mock import AsyncMock, patch

import av
import flet as ft
from PIL import Image, ImageChops

from koma.editor.models import Storyboard, StoryFrame, StoryLink
from koma.editor.timeline import Timeline
from koma.exports.sequence import ExportSequence
from koma.exports.reference_overlay import (FrameReference, REFERENCE_FIELDS, ReferenceOverlay,
    reference_values)
from koma.exports.video_frames import StoryboardFrames
from koma.exports.video_runner import VideoRunner
from tests import test_storyboard as fixtures


class ReferenceOverlayTests(TestCase):
    setUp = fixtures.StoryboardTests.setUp
    view = fixtures.StoryboardTests.view

    def test_all_fields_keep_complete_names_and_wrap_in_a_narrow_preview(self):
        from koma.ui.reference_readout import ReferenceReadout
        project = Storyboard(title='Projeto com um nome longo para identificar a montagem inteira')
        scene = StoryFrame(kind='main', title='Cena com identificação completa')
        frame = StoryFrame(title='Quadro com descrição completa para o trabalho de animação')
        values = reference_values(frame, FrameReference(scene, 3, project), local_frame=2, count=48,
            current_frame=50, total_frames=120, fps=24, size=(1080, 1920))
        overlay = ReferenceOverlay((1080, 1920), tuple(REFERENCE_FIELDS))
        self.assertEqual(overlay.parts(values, overlay.font), [values[key] for key in REFERENCE_FIELDS if values[key]])
        self.assertIn(project.title, values['project'])
        self.assertIn(frame.title, values['shot'])
        self.assertTrue(values['project'].startswith('Proj.:'))
        readout = ReferenceReadout()
        readout.sync(values, tuple(REFERENCE_FIELDS), size=(180, 320))
        self.assertIsInstance(readout.row, ft.Column)
        for key, cell in readout.cells.items():
            self.assertEqual(cell.content.value, values[key])
            self.assertIsNone(cell.content.max_lines)
            self.assertEqual(cell.content.no_wrap, readout.metrics.getlength(values[key]) <= 164)
            self.assertLessEqual(cell.width, 180 - 2 * readout.content.left)
            self.assertNotIn('…', cell.content.value)
        self.assertEqual(sum(len(row.controls) for row in readout.row.controls), sum(bool(value) for value in values.values()))
        for row in readout.row.controls:
            self.assertLessEqual(sum(cell.width for cell in row.controls) + row.spacing * (len(row.controls) - 1), 164)

    def test_empty_names_are_omitted_without_hiding_production_codes(self):
        from koma.ui.reference_readout import ReferenceReadout
        project = Storyboard(title='  ')
        scene = StoryFrame(kind='main', title='')
        frame = StoryFrame(title='')
        values = reference_values(frame, FrameReference(scene, 3, project, scene_number=2),
            local_frame=1, count=48, current_frame=1, total_frames=48, fps=24, size=(320, 180))
        self.assertEqual(values['project'], '')
        self.assertEqual(values['sequence'], '')
        self.assertEqual(values['scene'], 'Scene_02')
        self.assertEqual(values['shot'], 'shot_0003')
        fields = ('project', 'sequence')
        readout = ReferenceReadout()
        readout.sync(values, fields)
        self.assertFalse(readout.content.visible)
        overlay = ReferenceOverlay((320, 180), fields)
        picture = Image.new('RGB', (320, 180))
        self.assertEqual(overlay.parts(values, overlay.font), [])
        self.assertIs(overlay.apply(picture, values), picture)

    def test_fields_are_independent_and_counters_match_encoded_spans(self):
        scene = StoryFrame(kind='main', title='Cena 02')
        shot = StoryFrame(title='Plano A')
        values = reference_values(shot, FrameReference(scene, 3), local_frame=2, count=48,
            current_frame=50, total_frames=120, fps=24, size=(1920, 1080))
        self.assertEqual(values['duration_frames'], 'Dur.: 0048 f')
        self.assertEqual(values['duration_seconds'], 'Dur.: 0002.000 s')
        self.assertEqual(values['shot_frame'], 'Shot: 0002/0048')
        self.assertEqual(values['current_frame'], 'Frame: 0050')
        overlay = ReferenceOverlay((1920, 1080), ('fps', 'current_frame'))
        self.assertEqual(overlay.parts(values, overlay.font), ['Frame: 0050', '24 FPS'])
        original = Image.new('RGB', (1920, 1080), 'gray')
        image = overlay.apply(original, values)
        self.assertIsNot(image, original)
        self.assertEqual(original.getpixel((40, 40)), (128, 128, 128))
        for size in ((64, 64), (128, 256), (256, 128)):
            full = ReferenceOverlay(size, tuple(REFERENCE_FIELDS))
            result = full.apply(Image.new('RGB', size), values)
            self.assertEqual(result.size, size)

    def test_multi_scene_and_range_preserve_node_references_and_shot_number(self):
        a, b = StoryFrame(kind='main', title='A'), StoryFrame(kind='main', title='B')
        first, second = StoryFrame(duration=1), StoryFrame(duration=2)
        board = Storyboard(frames=(a, first, b, second), links=(StoryLink(a.id, first.id), StoryLink(b.id, second.id)))
        sequence = ExportSequence.from_project(board)
        self.assertIs(sequence.references[0].scene, a)
        self.assertIs(sequence.references[1].scene, b)
        self.assertIs(sequence.references[1].project, board)
        window = sequence.window(1.5, 2.5)
        self.assertEqual(window.frames, (second,))
        self.assertIs(window.references[0], sequence.references[1])
        self.assertEqual(window.source_offsets, (.5,))

    def test_real_mp4_changes_counter_each_frame_without_changing_cached_image(self):
        frame = StoryFrame(duration=.25)
        source = StoryboardFrames((frame,), self.store, (256, 144), (6,), False,
            reference_fields=('current_frame', 'total_frames'), references=(FrameReference(),))
        pictures = list(source.pictures(source.size, 24, lambda: False))
        first_bytes = pictures[0].tobytes()
        self.assertIsNotNone(ImageChops.difference(pictures[0], pictures[-1]).getbbox())
        self.assertEqual(pictures[0].tobytes(), first_bytes)
        destination = self.root / 'reference.mp4'
        result = VideoRunner(self.root / 'logs').write(source, destination, 24, 'HIGH', 0, lambda event: None)
        self.assertEqual(result, destination)
        with av.open(str(destination)) as container:
            decoded = [frame.to_image() for frame in container.decode(video=0)]
        self.assertEqual(len(decoded), 6)
        self.assertIsNotNone(ImageChops.difference(decoded[0], decoded[-1]).getbbox())

    def test_export_options_remember_choices_and_forward_them_to_frame_source(self):
        view = self.view()
        fixtures.finish(view.add_frame())
        view.files.video_options()
        popup = view.page.show_dialog.call_args.args[0]
        popup.open = True
        def checkboxes(control):
            if isinstance(control, ft.Checkbox):
                yield control
            for child in getattr(control, 'controls', ()) or ():
                yield from checkboxes(child)
            child = getattr(control, 'content', None)
            if isinstance(child, ft.Control):
                yield from checkboxes(child)
        boxes = {control.label: control for control in checkboxes(popup.content)}
        for key in ('fps', 'duration_seconds'):
            checkbox = boxes[REFERENCE_FIELDS[key]]
            checkbox.value = True
            checkbox.on_change(None)
        expected = ('duration_seconds', 'fps')
        self.assertEqual(view.preferences.options.reference_fields, expected)
        view.preferences.write(view.preferences.options)
        self.assertEqual(view.preferences.read().reference_fields, expected)
        with patch.object(view.files, 'pick_video', new=AsyncMock()) as picker:
            fixtures.finish(popup.actions[-1].on_click(None))
        self.assertIsNotNone(picker.call_args, str(popup.content.controls[3].value))
        self.assertEqual(picker.call_args.kwargs['reference_fields'], expected)
        sequence = picker.call_args.args[0]
        with patch.object(view.files, 'track_task'), patch.object(view.files.runner, 'run', new=AsyncMock(return_value=None)) as runner:
            fixtures.finish(view.files.export_video(sequence, self.root / 'output.mp4', 24, (256, 144), None,
                reference_fields=expected))
        source = runner.call_args.args[0]
        self.assertEqual(source.reference_fields, expected)
        self.assertEqual(len(source.references), len(source.frames))
        self.assertEqual(view.board, view.store.load())

    def test_old_preferences_keep_reference_overlay_disabled(self):
        import json
        view = self.view()
        view.preferences.path.write_text(json.dumps({'version': 1, 'include_subtitles': False}), encoding='utf-8')
        options = view.preferences.read()
        self.assertFalse(options.include_subtitles)
        self.assertEqual(options.reference_fields, ())
        with self.assertRaises(ValueError):
            view.preferences.update(reference_fields=('unknown',))

    def test_live_readouts_have_fixed_counter_widths_and_update_only_preview(self):
        from types import SimpleNamespace as Data
        from koma.exports.reference_overlay import ReferenceTypography, reference_font
        view = self.view()
        fixtures.finish(view.add_frame())
        fixtures.finish(view.add_frame())
        player = view.player
        player.open()
        player.strip.resized(Data(width=800))
        view.preferences.update(reference_fields=('current_frame', 'shot_frame'))
        presentation = player.reference_presentation
        presentation.refresh()
        self.assertTrue(all(not hasattr(block, 'reference') for block in player.strip.blocks.values()))
        widths = {key: cell.width for key, cell in presentation.preview.cells.items()}
        with patch.object(player.strip, 'sync', side_effect=AssertionError('Whole timeline refreshed')):
            for frame in (9, 10, 11):
                player.position = (frame - 1) / view.board.fps
                player.render_position()
                self.assertEqual(presentation.preview.cells['current_frame'].content.value, f'Frame: {frame:04d}')
                self.assertEqual({key: cell.width for key, cell in presentation.preview.cells.items()}, widths)
        self.assertEqual(presentation.sync_current(), [presentation.preview.content])
        typography = ReferenceTypography(reference_font(20))
        self.assertEqual(typography.getlength('Frame: 0009'), typography.getlength('Frame: 0010'))
