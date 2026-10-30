"""Real tiny video fixtures verify owned media, fixed timing and bounded preview."""
from dataclasses import replace, asdict
from pathlib import Path
from types import SimpleNamespace as Data
from unittest import TestCase
from unittest.mock import AsyncMock, Mock, patch
import json
import av
import flet as ft
from PIL import Image

from koma.editor.models import StoryFrame, Storyboard
from koma.editor.node_media import NodeMedia, MediaTransform
from koma.editor.node_clipboard import NodeClipboard, capture_selection
from koma.editor.view import StoryboardView
from koma.documents.store import document, parse_document, StoryboardStore
from koma.documents.bundle import export_bundle, restore_bundle
from koma.documents.session import DocumentSession
from koma.documents.videos import VideoReader
from koma.exports.video_export import prepare_frames
from koma.preferences import AppPreferences
from koma.ui.node_media_list import NodeMediaList, MEDIA_PAGE_SIZE
from tests import test_storyboard as fixtures


def make_clip(path):
    with av.open(str(path), 'w') as container:
        stream = container.add_stream('libx264', rate=24)
        stream.width = stream.height = 64
        stream.pix_fmt = 'yuv420p'
        for index in range(24):
            picture = Image.new('RGB', (64, 64), 'red' if index < 12 else 'blue')
            frame = av.VideoFrame.from_image(picture)
            frame.pts = index
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)


class NodeMediaTests(TestCase):
    setUp = fixtures.StoryboardTests.setUp
    view = fixtures.StoryboardTests.view

    def project(self):
        view = self.view()
        fixtures.finish(view.import_paths([self.source]))
        frame = view.board.frames[0]
        fixtures.finish(view.set_frame_properties(frame.id, duration=3.5, notes='Preserve', image_fit='contain'))
        clip = self.root / 'Animation.mp4'
        make_clip(clip)
        return view, view.board.frames[0], clip

    def import_clip(self, view, frame, clip):
        fixtures.finish(view.node_media.import_paths(frame.id, [clip]))
        return view.board.frames[0]

    def test_import_switch_and_remove_preserve_timing_and_per_media_crop(self):
        view, original, clip = self.project()
        source = clip.read_bytes()
        frame = self.import_clip(view, original, clip)
        self.assertEqual(len(frame.media), 2)
        self.assertEqual(frame.active_media.kind, 'video')
        self.assertEqual(frame.duration, 3.5)
        self.assertEqual(frame.notes, original.notes)
        self.assertAlmostEqual(frame.active_media.duration, 1)
        self.assertEqual(clip.read_bytes(), source)
        self.assertTrue((view.store.videos / frame.active_media.asset).is_file())
        image_id, video_id = frame.media[0].id, frame.active_media_id
        fixtures.finish(view.node_media.activate(frame.id, image_id))
        selected = view.board.frames[0]
        self.assertEqual(selected.image_fit, 'contain')
        self.assertEqual(selected.duration, 3.5)
        fixtures.finish(view.node_media.activate(frame.id, video_id))
        self.assertEqual(view.board.frames[0].image_fit, 'cover')
        fixtures.finish(view.node_media.remove(frame.id, video_id))
        self.assertEqual(len(view.board.frames[0].media), 1)
        fixtures.finish(view.graph.undo())
        self.assertEqual(len(view.board.frames[0].media), 2)
        self.assertEqual(view.board.frames[0].duration, 3.5)
        fixtures.finish(view.graph.redo())
        self.assertEqual(len(view.board.frames[0].media), 1)
        self.assertEqual(view.board.frames[0].duration, 3.5)

    def test_save_bundle_keeps_inactive_media_and_canonical_model_only(self):
        view, original, clip = self.project()
        frame = self.import_clip(view, original, clip)
        fixtures.finish(view.node_media.activate(frame.id, frame.media[0].id))
        raw = document(view.board, view.store.document_id)
        self.assertNotIn('image', raw['frames'][0])
        self.assertNotIn('crop_x', raw['frames'][0])
        self.assertEqual(len(raw['frames'][0]['media']), 2)
        restored, _ = parse_document(json.loads(json.dumps(raw)))
        self.assertEqual(restored, view.board)
        target = export_bundle(view.board, view.store, self.root / 'Media.koma')
        store = StoryboardStore(self.root / 'restored')
        opened = restore_bundle(target, store)
        self.assertEqual(opened, view.board)
        self.assertTrue((store.videos / frame.media[1].asset).is_file())
        self.assertTrue((store.images / frame.media[1].poster).is_file())
        self.assertTrue((store.images / frame.media[0].asset).is_file())

    def test_legacy_image_migrates_and_position_edits_do_not_duplicate_media(self):
        name = 'a' * 32 + '.png'
        identifier = 'b' * 32
        raw = dict(format='koma', version=5, document_id='c' * 32, title='Legacy', links=[], groups=[],
            frames=[dict(id=identifier, image=name, image_fit='contain', crop_x=.25, duration=4)])
        board, _ = parse_document(raw)
        frame = board.frames[0]
        self.assertEqual(len(frame.media), 1)
        self.assertEqual(frame.image, name)
        self.assertEqual(frame.crop_x, .25)
        moved = replace(frame, x=48, y=72)
        self.assertEqual(moved.media, frame.media)
        self.assertEqual(moved.duration, 4)
        cropped = replace(moved, crop_y=.5)
        self.assertEqual(cropped.active_media.transform.crop_y, .5)
        self.assertEqual(frame.crop_y, 0)

    def test_cross_document_copy_preserves_all_media_and_owns_video_assets(self):
        view, original, clip = self.project()
        frame = self.import_clip(view, original, clip)
        payload = fixtures.finish(capture_selection(view.board, view.store, {frame.id}))
        session = DocumentSession(self.root / 'destination')
        self.addCleanup(session.close)
        target = StoryboardView(Mock(), session, AppPreferences(self.root / 'destination'))
        fixtures.finish(target.activate())
        clipboard = NodeClipboard()
        clipboard.payload, clipboard.token = payload, 'media-copy'
        with patch.object(ft.Clipboard, 'get', new=AsyncMock(return_value=clipboard.token)):
            fixtures.finish(clipboard.paste(target))
        copy = target.board.frames[0]
        self.assertEqual(len(copy.media), 2)
        self.assertEqual(copy.duration, frame.duration)
        self.assertNotEqual(copy.active_media.asset, frame.active_media.asset)
        self.assertTrue((target.store.videos / copy.active_media.asset).is_file())
        self.assertTrue((target.store.images / copy.media[0].asset).is_file())

    def test_export_video_changes_frames_and_holds_last_without_changing_duration(self):
        view, original, clip = self.project()
        frame = self.import_clip(view, original, clip)
        work = self.root / 'prepared'
        work.mkdir()
        paths = prepare_frames((frame,), view.store, work, (64, 64), fps=24)
        self.assertEqual(paths[0].suffix, '.mp4')
        with av.open(str(paths[0])) as container:
            frames = list(container.decode(video=0))
        self.assertEqual(len(frames), 84)
        first = frames[0].to_image().getpixel((32, 32))
        last = frames[-1].to_image().getpixel((32, 32))
        self.assertGreater(first[0], first[2])
        self.assertGreater(last[2], last[0])
        self.assertEqual(view.board.frames[0].duration, 3.5)

    def test_invalid_video_drop_is_transactional(self):
        view = self.view()
        invalid = self.root / 'Invalid.mp4'
        invalid.write_bytes(b'not a movie')
        before = view.board
        fixtures.finish(view.image_input.drop([str(invalid)], (24, 24)))
        self.assertIs(view.board, before)
        self.assertFalse(tuple(view.store.videos.glob('*')))

    def test_paged_list_does_not_decode_inactive_videos(self):
        view, original, clip = self.project()
        frame = self.import_clip(view, original, clip)
        entries = tuple(replace(frame.active_media, id=f'{index:032x}') for index in range(MEDIA_PAGE_SIZE * 3))
        many = replace(frame, media=entries, active_media_id=entries[-1].id)
        widget = NodeMediaList(view)
        with patch('koma.documents.videos.open_video') as opened:
            widget.sync(many)
            opened.assert_not_called()
        self.assertLessEqual(len(widget.rows.controls), MEDIA_PAGE_SIZE)
        self.assertEqual(widget.page_number, 2)

    def test_preview_coalesces_seeks_and_decodes_only_current_video(self):
        view, original, clip = self.project()
        frame = self.import_clip(view, original, clip)
        player = view.player
        player.open()
        preview = player.video_preview
        self.addCleanup(lambda: fixtures.finish(preview.shutdown()))
        with patch.object(preview.reader, 'read', wraps=preview.reader.read) as read:
            for index in range(100):
                preview.request(frame, index / 100)
            read.assert_not_called()
            async def execute(executor, fn, *args):
                return fn(*args)
            loop = Data(run_in_executor=execute)
            with patch('asyncio.get_running_loop', return_value=loop):
                fixtures.finish(preview.drain())
            read.assert_called_once()
        self.assertIsInstance(player.preview.image.src, bytes)
        preview.clear()
