"""Focused module-boundary regressions; no desktop client or manual interaction."""
import tempfile
import unittest
import wave
from dataclasses import replace
from functools import wraps
from pathlib import Path
from types import SimpleNamespace as Data
from unittest.mock import AsyncMock, Mock, patch

from PIL import Image

from koma.documents.session import DocumentSession
from koma.editor.batch_properties import apply_properties
from koma.editor.document_tools import DocumentTools
from koma.editor.models import Storyboard, StoryFrame, StoryLink
from koma.editor.media_models import AudioTrack, TimelineMarker
from koma.editor.node_clipboard import NodeClipboard
from koma.editor.timeline_order import reorder
from koma.editor.view import StoryboardView
from koma.exports.sequence import ExportSequence
from koma.exports.audio_segment import extract
from koma.preferences import AppPreferences


async def immediate(function, *args):
    return function(*args)


def inline(function):
    """Use the existing headless fixture convention; no Windows socket loop."""
    @wraps(function)
    def run(self):
        coroutine = function(self)
        try:
            coroutine.send(None)
        except StopIteration:
            return
        finally:
            coroutine.close()
        raise AssertionError('Unexpected external I/O in a headless integration check')
    return run


class WorkflowIntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.sessions = []
        worker = patch('asyncio.to_thread', side_effect=immediate)
        worker.start()
        self.addCleanup(worker.stop)

    def tearDown(self):
        for session in self.sessions:
            session.close()

    async def make_view(self, board=Storyboard()):
        session = DocumentSession(self.directory)
        self.sessions.append(session)
        session.board = board
        view = StoryboardView(Mock(), session, AppPreferences(self.directory))
        view.page.show_dialog.side_effect = lambda popup: setattr(popup, 'open', True)
        for method in ('pan', 'zoom', 'reset'):
            setattr(view.workspace.viewer, method, AsyncMock())
        await view.activate()
        self.assertFalse(view.load_error)
        return view

    @inline
    async def test_clipboard_copies_assets_links_and_scene_media_between_real_views(self):
        source = await self.make_view()
        asset = 'a' * 32 + '.png'
        source.store.images.mkdir(parents=True, exist_ok=True)
        Image.new('RGB', (8, 8), 'red').save(source.store.images / asset)
        audio = 'b' * 32 + '.wav'
        source.store.audio.mkdir(parents=True, exist_ok=True)
        with wave.open(str(source.store.audio / audio), 'wb') as output:
            output.setparams((2, 2, 48000, 0, 'NONE', 'not compressed'))
            output.writeframes(b'\0' * 48000 * 4)
        root = StoryFrame(kind='main', title='Cena', x=0, y=0)
        frame = StoryFrame(image=asset, x=480, y=0)
        source.board = Storyboard(frames=(root, frame), links=(StoryLink(root.id, frame.id),),
            audio_tracks=(AudioTrack(asset=audio, duration=1, scene_id=root.id),),
            markers=(TimelineMarker(scene_id=root.id),))
        source.refresh()
        source.workspace.navigation.apply_selection({root.id, frame.id}, frame.id)
        destination = await self.make_view()
        clipboard = NodeClipboard()
        with patch('koma.editor.node_clipboard.ft.Clipboard') as service:
            service.return_value.set = AsyncMock()
            service.return_value.get = AsyncMock(side_effect=lambda: clipboard.token)
            await clipboard.copy(source)
            await clipboard.paste(destination)
        destination.board.validate()
        self.assertEqual(len(destination.board.frames), 2)
        self.assertEqual(len(destination.board.links), 1)
        copied_root, copied_frame = destination.board.frames
        self.assertNotEqual(copied_root.id, root.id)
        self.assertNotEqual(copied_frame.image, asset)
        self.assertEqual((destination.store.images / copied_frame.image).read_bytes(), (source.store.images / asset).read_bytes())
        self.assertEqual(destination.board.audio_tracks[0].scene_id, copied_root.id)
        self.assertEqual(destination.board.markers[0].scene_id, copied_root.id)
        await destination.graph.undo()
        self.assertFalse(destination.board.frames)
        await destination.graph.redo()
        self.assertEqual(len(destination.board.frames), 2)

    @inline
    async def test_project_import_does_not_use_system_clipboard(self):
        frame = StoryFrame(title='Importado', x=0, y=0)
        source = await self.make_view(Storyboard(frames=(frame,)))
        path = self.directory / 'source.koma'
        source.session.save(source.board, path)
        target = await self.make_view()
        app = Data(view=target, settings=target.settings, page=target.page, node_clipboard=NodeClipboard())
        picker = Data(pick_files=AsyncMock(return_value=[Data(path=str(path))]))
        with patch('koma.editor.document_tools.ft.FilePicker', return_value=picker), patch('koma.editor.node_clipboard.ft.Clipboard') as clipboard:
            await DocumentTools(app).import_project()
            clipboard.assert_not_called()
        self.assertEqual([f.title for f in target.board.frames], ['Importado'])
        self.assertNotEqual(target.board.frames[0].id, frame.id)

    @inline
    async def test_reorder_preserves_other_scenes_and_batch_duration_targets_only_frames(self):
        root, a, b, other, c = (StoryFrame(kind='main', x=0, y=0), StoryFrame(x=480, y=0),
            StoryFrame(x=960, y=0), StoryFrame(kind='main', x=0, y=600), StoryFrame(x=480, y=600))
        links = (StoryLink(root.id, a.id), StoryLink(a.id, b.id), StoryLink(other.id, c.id))
        view = await self.make_view(Storyboard(frames=(root, a, b, other, c), links=links))
        view.workspace.navigation.apply_selection({a.id}, a.id)
        view.player.open()
        await reorder(view.player, b.id, a.id, expected=(view.board, view.session))
        self.assertEqual(tuple(f.id for f in view.player.timeline.frames), (b.id, a.id))
        self.assertIn(StoryLink(other.id, c.id), view.board.links)
        positions = {frame.id: (frame.x, frame.y) for frame in view.board.frames}
        self.assertEqual(positions[a.id], (b.x, b.y))
        self.assertEqual(positions[b.id], (a.x, a.y))
        self.assertEqual(positions[root.id], (root.x, root.y))
        self.assertEqual(positions[c.id], (c.x, c.y))
        self.assertEqual(view.cards[b.id].content.left, a.x + view.workspace.extent.origin_x)
        self.assertEqual(len(view.history.past), 1)
        self.assertEqual(view.history.past_labels[-1], 'Reordenar quadros')
        await view.graph.undo()
        self.assertEqual(view.board.links, links)
        self.assertEqual(next(f.x for f in view.board.frames if f.id == a.id), a.x)
        await view.graph.redo()
        self.assertEqual(next(f.x for f in view.board.frames if f.id == b.id), a.x)
        await apply_properties(view, {root.id, a.id, b.id}, {'duration': 3})
        durations = {f.id: f.duration for f in view.board.frames}
        self.assertEqual((durations[root.id], durations[a.id], durations[b.id]), (2, 3, 3))
        view.board.validate()

    @inline
    async def test_export_range_clips_audio_and_keeps_source_unchanged(self):
        root = StoryFrame(kind='main')
        frame = StoryFrame(duration=2)
        audio = AudioTrack(asset='c' * 32 + '.wav', duration=4, scene_id=root.id)
        board = Storyboard(frames=(root, frame), links=(StoryLink(root.id, frame.id),), audio_tracks=(audio,))
        sequence = ExportSequence.from_project(board).window(1, 3)
        self.assertEqual(sequence.durations, (2,))
        self.assertEqual(sequence.audio_tracks[0].source_offset, 1)
        self.assertEqual(sequence.audio_tracks[0].duration, 2)
        self.assertEqual(board.frames[1].duration, 2)
        source, target = self.directory / 'audio.wav', self.directory / 'range.wav'
        with wave.open(str(source), 'wb') as output:
            output.setparams((2, 2, 48000, 0, 'NONE', 'not compressed'))
            output.writeframes(b'\0' * 4 * 48000 * 4)
        original = source.read_bytes()
        extract(source, target, 1, 2)
        with wave.open(str(target), 'rb') as result:
            self.assertEqual(result.getnframes(), 2 * 48000)
        self.assertEqual(source.read_bytes(), original)

    @inline
    async def test_invalid_batch_and_stale_export_keep_document_unchanged(self):
        frame = StoryFrame(x=0, y=0)
        view = await self.make_view(Storyboard(frames=(frame,)))
        before = view.board
        await apply_properties(view, {frame.id}, {'duration': -1})
        self.assertIs(view.board, before)
        self.assertFalse(view.history.past)
        view.files.video_options()
        popup = view.page.show_dialog.call_args.args[0]
        view.board = replace(view.board, title='Changed during dialog')
        with patch('koma.editor.file_actions.ft.FilePicker') as picker:
            await popup.actions[-1].on_click(None)
            picker.assert_not_called()
        error = popup.content.controls[3]
        self.assertTrue(error.visible)
        self.assertIn('projeto mudou', error.value)

    @inline
    async def test_audio_drag_commits_once_and_escape_preview_can_be_cancelled(self):
        frame = StoryFrame(x=0, y=0)
        track = AudioTrack(asset='d' * 32 + '.wav', duration=1)
        view = await self.make_view(Storyboard(frames=(frame,), audio_tracks=(track,)))
        player = view.player
        player.open()
        player.strip.resized(Data(width=800))
        drag = player.strip.audio_lane.drag
        before = view.board
        drag.begin(Data(global_position=Data(x=100)))
        drag.move(Data(global_position=Data(x=500)))
        self.assertIs(view.board, before)
        drag.cancel()
        self.assertIs(view.board, before)
        self.assertFalse(view.history.past)
        drag.begin(Data(global_position=Data(x=100)))
        drag.move(Data(global_position=Data(x=500)))
        await drag.end()
        self.assertEqual(view.board.audio_tracks[0].start, 1)
        self.assertEqual(len(view.history.past), 1)

    @inline
    async def test_import_rejects_destination_changed_during_source_read(self):
        source = await self.make_view(Storyboard(frames=(StoryFrame(x=0, y=0),)))
        path = self.directory / 'source.koma'
        source.session.save(source.board, path)
        target = await self.make_view()
        app = Data(view=target, settings=target.settings, page=target.page, node_clipboard=NodeClipboard())
        picker = Data(pick_files=AsyncMock(return_value=[Data(path=str(path))]))
        from koma.editor.node_clipboard import capture_selection
        async def capture(*args):
            payload = await capture_selection(*args)
            target.board = replace(target.board, title='Changed during import')
            return payload
        with patch('koma.editor.document_tools.ft.FilePicker', return_value=picker), patch('koma.editor.document_tools.capture_selection', side_effect=capture):
            await DocumentTools(app).import_project()
        self.assertFalse(target.board.frames)
        self.assertEqual(target.board.title, 'Changed during import')
        self.assertFalse(target.history.past)

    @inline
    async def test_duration_drag_uses_timing_only_updates_until_release(self):
        frames = (StoryFrame(x=0, y=0), StoryFrame(x=480, y=0))
        view = await self.make_view(Storyboard(frames=frames))
        player = view.player
        player.open()
        player.strip.resized(Data(width=800))
        block = player.strip.blocks[frames[0].id]
        block.duration_pointer_down(Data(global_position=Data(x=100)))
        block.begin(Data(global_position=Data(x=110)))
        self.assertGreater(player.timeline.frames[0].duration, frames[0].duration)
        original = view.board
        view.page.update.reset_mock()
        with patch.object(Storyboard, 'validate', side_effect=AssertionError('Full graph validation during drag')), patch.object(player.preview, 'set_frame') as preview, patch.object(view.cards[frames[0].id], 'sync') as card:
            block.move(Data(global_position=Data(x=300)))
            preview.assert_not_called()
            card.assert_not_called()
        self.assertIs(view.board, original)
        self.assertFalse(view.history.past)
        self.assertEqual(view.page.update.call_args.args, (player.strip.content, player.controls, player.caption))
        await block.finish(None)
        self.assertEqual(len(view.history.past), 1)
        self.assertEqual(view.board.frames[0].duration, 3)
