"""Project-owned filter persistence, isolation and rendering; no manual testing."""
from dataclasses import replace
import json
from unittest import TestCase
from unittest.mock import patch
import flet as ft
from PIL import Image
from koma.media_filters import grayscale, GRAYSCALE_MATRIX
from koma.ui.media_filter import media_filter, refresh_media_filters
from koma.editor.drawing_models import DrawingLayer, DrawingStroke
from koma.editor.models import StoryFrame
from koma.exports.video_export import FrameComposer
from koma.exports.video_frames import StoryboardFrames
from koma.exports.video_encoder import encode
from koma.preference_catalog import defaults
from koma.global_preferences import validate_configuration
from koma.documents.store import document, parse_document, DOCUMENT_VERSION, StoryboardStore
from koma.documents.bundle import export_bundle, restore_bundle
from tests import test_storyboard as fixtures
import av


class MediaFilterTests(TestCase):
    setUp = fixtures.StoryboardTests.setUp
    view = fixtures.StoryboardTests.view

    def test_grayscale_preserves_alpha_source_and_export_annotation_colors(self):
        source = Image.new('RGBA', (100, 100), (255, 0, 0, 128))
        before = source.tobytes()
        result = grayscale(source)
        self.assertEqual(result.getpixel((0, 0)), (76, 76, 76, 128))
        self.assertEqual(source.tobytes(), before)
        values = defaults()
        frame = StoryFrame(drawing=DrawingLayer((DrawingStroke(((.1, .5), (.9, .5)), '#00FF00', .08),)))
        opaque = Image.new('RGB', source.size, 'red')
        colored = FrameComposer(frame, opaque.size, preferences=values).compose(opaque)
        self.assertEqual(colored.getpixel((0, 0)), (255, 0, 0))
        neutral = FrameComposer(frame, opaque.size, preferences=values, media_filter='grayscale').compose(opaque)
        self.assertEqual(neutral.getpixel((0, 0)), (76, 76, 76))
        self.assertEqual(neutral.getpixel((50, 50)), (0, 255, 0))

    def test_project_change_reuses_media_and_supports_undo_redo_without_full_refresh(self):
        with patch('koma.ui.drop_runtime.supports', return_value=True):
            view = self.view()
            fixtures.finish(view.import_paths([self.source]))
            board, history = view.board, tuple(view.history.past)
            retained = media_filter(view, ft.Image(src=self.original))
            child = retained.content
            with patch.object(view, 'refresh', side_effect=AssertionError('Full canvas refresh')):
                selector = view.chrome.filter_selector
                fixtures.finish(selector.input.button.items[1].on_click(None))
                self.assertEqual(view.board.media_filter, 'grayscale')
                self.assertEqual(retained.matrix, list(GRAYSCALE_MATRIX))
                self.assertEqual(view.store.load().media_filter, 'grayscale')
                self.assertEqual(len(view.history.past), len(history) + 1)
                fixtures.finish(view.graph.undo())
                self.assertEqual(view.board, board)
                self.assertIsNone(retained.matrix)
                fixtures.finish(view.graph.redo())
            self.assertEqual(retained.matrix, list(GRAYSCALE_MATRIX))
            self.assertIs(retained.content, child)
            self.assertEqual(view.board.media_filter, 'grayscale')
            self.assertEqual(view.board.frames, board.frames)
            self.assertEqual(view.store.load(), view.board)
            self.assertEqual(self.source.read_bytes(), self.original)

    def test_unsupported_client_keeps_media_visible(self):
        view = self.view()
        image = ft.Image(src=self.original)
        with patch('koma.ui.drop_runtime.supports', return_value=False):
            self.assertIs(media_filter(view, image).content, image)
        refresh_media_filters(view)

    def test_legacy_settings_are_ignored_and_filter_is_isolated_between_projects(self):
        migrated = validate_configuration({'filters': {'preview_bw': True, 'export_bw': False}})
        self.assertNotIn('filters', migrated)
        view = self.view()
        from koma.documents.session import DocumentSession
        from koma.editor.view import StoryboardView
        session = DocumentSession(self.root / 'other')
        self.addCleanup(session.close)
        other = StoryboardView(view.page, session, view.settings)
        fixtures.finish(other.activate())
        selector = view.chrome.filter_selector
        fixtures.finish(selector.input.button.items[1].on_click(None))
        self.assertEqual(view.board.media_filter, 'grayscale')
        self.assertEqual(other.board.media_filter, 'none')
        other.chrome.filter_selector.sync()
        self.assertEqual(other.chrome.filter_selector.input.text.value, 'Sem filtro')
        self.assertEqual(selector.input.text.value, 'Preto e branco')

    def test_document_migration_validation_and_portable_file_preserve_project_filter(self):
        view = self.view()
        fixtures.finish(view.add_frame())
        board = replace(view.board, media_filter='grayscale')
        raw = json.loads(json.dumps(document(board, 'a' * 32)))
        self.assertEqual(raw['version'], DOCUMENT_VERSION)
        self.assertEqual(parse_document(raw)[0], board)
        raw['version'] = 9
        raw.pop('media_filter')
        self.assertEqual(parse_document(raw)[0].media_filter, 'none')
        raw['version'] = DOCUMENT_VERSION
        raw['media_filter'] = 'invalid'
        with self.assertRaises(ValueError):
            parse_document(raw)
        path = self.root / 'filtered.koma'
        export_bundle(board, view.store, path)
        store = StoryboardStore(self.root / 'restored')
        restored = restore_bundle(path, store)
        self.assertEqual(restored.media_filter, 'grayscale')

    def test_references_keep_unfiltered_images_when_project_filter_is_enabled(self):
        with patch('koma.ui.drop_runtime.supports', return_value=True):
            view = self.view()
            fixtures.finish(view.chrome.filter_selector.input.button.items[1].on_click(None))
            view.work_modes.show_references()
            fixtures.finish(view.references.actions.import_paths([self.source], (0, 0)))
            item = view.board.references[0]
            view.references.sync()
            gesture = view.references.cards[item.id].content.controls[0].content
            self.assertIs(gesture.content, view.references.images[item.id])
            self.assertIsInstance(gesture.content, ft.Image)

    def test_mp4_stream_uses_project_filter_without_modifying_source(self):
        source = self.store.images / ('f' * 32 + '.png')
        source.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGB', (64, 64), 'red').save(source)
        original = source.read_bytes()
        values = defaults()
        frames = StoryboardFrames((StoryFrame(image=source.name),), self.store,
            (64, 64), (2,), preferences=values, media_filter='grayscale')
        output = self.root / 'filtered.mp4'
        self.assertTrue(encode(frames, output, 24, 'HIGH', 0, (), lambda: False, lambda _: None))
        with av.open(str(output)) as video:
            pixels = next(video.decode(video=0)).to_image()
            r, g, b = pixels.getpixel((32, 32))
            self.assertLessEqual(max(r, g, b) - min(r, g, b), 2)
        self.assertEqual(source.read_bytes(), original)
