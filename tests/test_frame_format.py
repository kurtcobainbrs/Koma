"""Custom formats stay consistent through persistence, undo and rendering."""

from dataclasses import replace
from io import BytesIO
import json
from unittest import TestCase

from PIL import Image

from koma.editor.frame_format import FrameFormat
from koma.documents.store import document, parse_document
from koma.documents.session import DocumentSession
from koma.editor.subtitle_preview import preview_bytes
from koma.exports.video_export import prepare_frames
from koma.exports.pdf_export import export_pdf
from tests import test_storyboard as fixtures


class FrameFormatTests(TestCase):
    setUp = fixtures.StoryboardTests.setUp
    view = fixtures.StoryboardTests.view

    def test_legacy_documents_and_custom_bundle_roundtrip(self):
        view = self.view()
        raw = json.loads(json.dumps(document(view.board, view.store.document_id)))
        raw.pop('frame_format')
        for version in (1, 2):
            raw['version'] = version
            self.assertEqual(parse_document(raw)[0].frame_format, FrameFormat())
        board = replace(view.board, frame_format=FrameFormat(1080, 1920))
        path = self.session.save(board, self.root / 'vertical.koma')
        reopened = DocumentSession.open(path, self.root / 'other')
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.board, board)

    def test_apply_format_updates_card_and_preview_and_undo_restores(self):
        view = self.view()
        fixtures.finish(view.add_frame())
        settings = view.project_properties
        settings.width.value, settings.height.value = '1080', '1920'
        settings.dimensions_changed()
        fixtures.finish(settings.apply())
        frame_format = view.board.frame_format
        card = next(iter(view.cards.values())).viewport
        self.assertAlmostEqual(card.width / card.height, frame_format.aspect_ratio)
        view.player.preview_bounds = (800, 400)
        view.player.fit_preview()
        self.assertAlmostEqual(view.player.screen.width / view.player.screen.height, 9 / 16)
        self.assertLessEqual(view.player.screen.height, 400)
        self.assertEqual(view.store.load().frame_format, frame_format)
        fixtures.finish(view.graph.undo())
        self.assertEqual(view.board.frame_format, FrameFormat())

    def test_invalid_dimensions_do_not_change_document(self):
        view = self.view()
        original = view.board
        settings = view.project_properties
        for width, height in [('abc', '1080'), ('0', '1080'), ('8192', '8192'), ('1081', '1920')]:
            settings.width.value, settings.height.value = width, height
            fixtures.finish(settings.apply())
            self.assertIs(view.board, original)
            self.assertIsNotNone(settings.width.error_text)

    def test_free_ratio_accepts_portrait_and_decimal_without_rounding_the_ratio(self):
        self.assertEqual(FrameFormat().with_ratio('9x16'), FrameFormat(1080, 1920))
        self.assertEqual(FrameFormat().with_ratio('1:1').aspect_ratio, 1)
        cinema = FrameFormat().with_ratio('2,39:1')
        self.assertEqual(cinema.ratio_label, '239:100')
        view = self.view()
        settings = view.project_properties
        settings.ratio.value = '5:4'
        fixtures.finish(settings.apply())
        self.assertEqual(view.board.frame_format.ratio_label, '5:4')

    def test_portrait_square_and_free_ratio_render_exact_dimensions(self):
        view = self.view()
        fixtures.finish(view.import_paths([self.source]))
        output = self.root / 'render'
        output.mkdir()
        for size in [(128, 256), (128, 128), (320, 128)]:
            paths = prepare_frames(view.board.frames, view.store, output, size)
            with Image.open(paths[0]) as image:
                self.assertEqual(image.size, size)
            with Image.open(BytesIO(preview_bytes('Legenda', size))) as subtitle:
                self.assertEqual(subtitle.size, size)
        pdf = export_pdf(replace(view.board, frame_format=FrameFormat(128, 256)),
            view.store, self.root / 'vertical.pdf')
        self.assertTrue(pdf.read_bytes().startswith(b'%PDF'))
