"""Print layout/filter/export-dialog integration, without manual app testing."""
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch, AsyncMock
from shutil import which
import subprocess
from PIL import Image
from koma.editor.models import Storyboard, StoryFrame, StoryLink
from koma.editor.frame_format import FrameFormat
from koma.editor.drawing_models import DrawingLayer, DrawingStroke
from koma.exports.pdf_options import PdfOptions, PAGE_MARGIN, FRAME_PADDING, SHEET_HEADER, CARD_PADDING
from koma.exports.pdf_export import export_pdf, print_sequence
from koma.editor.production_numbers import ProductionNumbers
from koma.editor.sequences import SequenceIndex
from koma.editor.project_timeline import ProjectTimeline
from koma.preference_catalog import defaults
from koma.ui.pdf_export_panel import PdfExportPanel
from tests import test_storyboard as fixtures


class PdfOptionTests(TestCase):
    setUp = fixtures.StoryboardTests.setUp
    view = fixtures.StoryboardTests.view

    def project(self):
        asset = self.store.images / ('e' * 32 + '.png')
        asset.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGB', (90, 160), '#FF0000').save(asset)
        scene = StoryFrame(kind='main', title='Cena teste')
        frame = StoryFrame(image=asset.name, title='Quadro teste',
            drawing=DrawingLayer((DrawingStroke(((.1, .5), (.9, .5)), '#00FF00', .04),)))
        return Storyboard(title='Projeto teste', frames=(scene, frame), links=(StoryLink(scene.id, frame.id),),
            frame_format=FrameFormat(1080, 1920))

    def test_layout_uses_project_ratio_and_adapts_rows_with_validated_controls(self):
        options = PdfOptions()
        for size in ((1920, 1080), (1080, 1920), (1000, 1000), (2400, 1000)):
            format = FrameFormat(*size)
            geometry = options.geometry(format)
            self.assertAlmostEqual(geometry.image_width / geometry.image_height, format.aspect_ratio)
            self.assertGreater(geometry.image_height, 0)
            self.assertLessEqual(geometry.image_height, geometry.card_height - options.text_height)
        self.assertEqual(options.geometry(FrameFormat()).rows, 2)
        self.assertEqual(options.geometry(FrameFormat(1080, 1920)).rows, 1)
        self.assertEqual(replace(options, columns=2, rows=2).geometry(FrameFormat()).capacity, 4)
        with self.assertRaises(ValueError):
            replace(options, columns=0).validate()

    def test_pdf_uses_montage_order_and_existing_scene_shot_codes_with_muted_gaps(self):
        a, b = StoryFrame(kind='main', title='A'), StoryFrame(kind='main', title='B')
        first, second = StoryFrame(title='First'), StoryFrame(title='Second')
        skipped, last, loose = StoryFrame(muted=True), StoryFrame(title='Last'), StoryFrame()
        board = Storyboard(frames=(b, last, second, loose, a, skipped, first), links=(
            StoryLink(a.id, first.id), StoryLink(first.id, skipped.id), StoryLink(skipped.id, second.id),
            StoryLink(b.id, last.id)))
        values = defaults()
        values['identity'].update(scene_prefix='Scene_', shot_prefix='shot_')
        frames, codes, sections = print_sequence(board, values)
        identity = ProductionNumbers(SequenceIndex(board), values['identity'])
        self.assertEqual(frames, ProjectTimeline(board).frames)
        self.assertEqual(frames, (last, first, second))
        self.assertEqual([section[0] for section in sections], [identity.label(b.id), identity.label(a.id)])
        self.assertEqual(codes, {frame.id: identity.code(frame.id) for frame in frames})
        self.assertEqual(codes[second.id], 'shot_0004')
        self.assertNotIn(loose.id, codes)

    def test_pdf_render_has_selected_filter_correct_ratio_and_colored_drawing(self):
        renderer = which('pdftoppm')
        if not renderer:
            self.skipTest('Poppler não está instalado neste ambiente.')
        board = replace(self.project(), media_filter='grayscale')
        values = defaults()
        values['pdf']['title'] = 'MEU STORYBOARD'
        output = self.root / 'storyboard.pdf'
        export_pdf(board, self.store, output, preferences=values)
        self.assertTrue(output.read_bytes().startswith(b'%PDF'))
        prefix = self.root / 'page'
        subprocess.run([renderer, '-f', '1', '-singlefile', '-scale-to', '1000', '-png', str(output), str(prefix)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=20)
        with Image.open(prefix.with_suffix('.png')) as image:
            options = PdfOptions.from_preferences(values)
            geometry = options.geometry(board.frame_format)
            scale = image.width / options.page_size[0]
            x = PAGE_MARGIN + FRAME_PADDING + (geometry.card_width - geometry.image_width) / 2
            y = PAGE_MARGIN + FRAME_PADDING + SHEET_HEADER + CARD_PADDING
            y += (geometry.card_height - options.text_height - geometry.image_height) / 2
            region = image.crop((round(x * scale), round(y * scale),
                round((x + geometry.image_width) * scale), round((y + geometry.image_height) * scale))).convert('RGB')
            pixels = list(region.get_flattened_data())
            neutral = [(x % region.width, x // region.width) for x, (r, g, b) in enumerate(pixels)
                if abs(r - 76) < 3 and abs(g - 76) < 3 and abs(b - 76) < 3]
            self.assertGreater(len(neutral), 10000)
            width = max(p[0] for p in neutral) - min(p[0] for p in neutral) + 1
            height = max(p[1] for p in neutral) - min(p[1] for p in neutral) + 1
            self.assertAlmostEqual(width / height, board.frame_format.aspect_ratio, delta=.03)
            self.assertTrue(any(g > 200 and r < 50 and b < 50 for r, g, b in pixels))

    def test_export_dialog_cancel_and_confirm_preserve_document_and_capture_options(self):
        self.session.board = self.project()
        view = self.view()
        before, history = view.board, tuple(view.history.past)
        panel = PdfExportPanel(view)
        panel.open()
        panel.controls['title'].value = 'Meu título'
        panel.cancel()
        self.assertEqual(view.settings.configuration.values['pdf']['title'], 'KOMA STORYBOARD')
        panel = PdfExportPanel(view)
        panel.open()
        panel.controls['title'].value = 'Meu título'
        with patch.object(view, 'export_pdf_file', new_callable=AsyncMock) as export:
            fixtures.finish(panel.confirm())
            self.assertEqual(export.call_args.kwargs['options'].title, 'Meu título')
        self.assertEqual(view.settings.configuration.values['pdf']['title'], 'KOMA STORYBOARD')
        panel = PdfExportPanel(view)
        panel.open()
        panel.controls['title'].value = 'Padrão pessoal'
        panel.remember.value = True
        with patch.object(view, 'export_pdf_file', new_callable=AsyncMock):
            fixtures.finish(panel.confirm())
        self.assertEqual(view.settings.configuration.values['pdf']['title'], 'Padrão pessoal')
        self.assertIs(view.board, before)
        self.assertEqual(tuple(view.history.past), history)
