"""Negative starts, project-wide picker memory and sample-correct source windows."""
from array import array
import asyncio
from dataclasses import replace
from types import SimpleNamespace as Data
from unittest import TestCase
from unittest.mock import AsyncMock, patch
import wave
from koma.dialog_directories import DialogDirectories
from koma.editor.models import Storyboard, StoryFrame, StoryLink
from koma.editor.media_models import AudioTrack
from koma.editor.project_timeline import ProjectTimeline, SceneTimeline
from koma.exports.sequence import ExportSequence
from koma.audio_transport import mixed_pcm_stream
from koma.documents.session import DocumentSession
from tests import test_storyboard as fixtures


class AudioOffsetTests(TestCase):
    setUp = fixtures.StoryboardTests.setUp
    view = fixtures.StoryboardTests.view

    def test_negative_expression_is_undoable_and_does_not_change_picture_timing(self):
        root, frame = StoryFrame(kind='main'), StoryFrame(duration=3)
        music = AudioTrack(asset='a' * 32 + '.wav', duration=20)
        self.session.board = Storyboard(frames=(root, frame), links=(StoryLink(root.id, frame.id),), audio_tracks=(music,))
        view = self.view()
        view.player.open()
        before = view.board
        fixtures.finish(view.player.media.set_start('-24*2'))
        self.assertEqual(view.board.audio_tracks[0].start, -2)
        self.assertEqual(view.player.timeline.total, 3)
        self.assertEqual(view.player.timeline.audio_tracks[0].source_offset, 2)
        exported = ExportSequence.from_project(view.board).audio_tracks[0]
        self.assertEqual((exported.start, exported.duration, exported.source_offset), (0, 3, 2))
        fixtures.finish(view.graph.undo())
        self.assertEqual(view.board, before)
        fixtures.finish(view.graph.redo())
        self.assertEqual(view.board.audio_tracks[0].start, -2)

    def test_negative_start_preserves_pcm_source_window_and_saved_asset(self):
        asset = 'a' * 32 + '.wav'
        self.store.audio.mkdir(exist_ok=True)
        with wave.open(str(self.store.audio / asset), 'wb') as output:
            output.setparams((2, 2, 48000, 0, 'NONE', 'not compressed'))
            output.writeframes(array('h', [1000] * 240 * 2 + [2000] * 240 * 2).tobytes())
        original = (self.store.audio / asset).read_bytes()
        root, frame = StoryFrame(kind='main'), StoryFrame(duration=1)
        track = AudioTrack(asset=asset, duration=.01, start=-.005)
        board = Storyboard(frames=(root, frame), links=(StoryLink(root.id, frame.id),), audio_tracks=(track,))
        projected = ProjectTimeline(board).audio_tracks[0]
        self.assertEqual((projected.start, projected.duration, projected.source_offset), (0, .005, .005))
        stream = mixed_pcm_stream(self.store, (projected,), 0, 1)
        self.addCleanup(stream.close)
        next(stream)
        samples = array('h'); samples.frombytes(stream.send(240))
        self.assertEqual(set(samples), {2000})
        self.assertEqual(ExportSequence.from_project(board).audio_tracks[0].source_offset, .005)
        target = self.session.save(board, self.root / 'negative.koma')
        restored = DocumentSession.open(target, self.root / 'reopened')
        self.addCleanup(restored.close)
        self.assertEqual(restored.board, board)
        self.assertEqual((restored.store.audio / asset).read_bytes(), original)

    def test_audio_picker_remembers_its_folder_across_restarts_separately_from_images(self):
        audio, images = self.root / 'music', self.root / 'images'
        audio.mkdir(); images.mkdir()
        source = audio / 'track.wav'
        view = self.view()
        fixtures.finish(view.add_frame())
        view.player.open()
        asyncio.run(view.settings.dialog_directories.remember('audio', source))
        memory = DialogDirectories(view.settings.directory)
        self.assertEqual(asyncio.run(memory.initial('audio', str(images))), str(audio))
        self.assertEqual(asyncio.run(memory.initial('images', str(images))), str(images))
        picker = AsyncMock()
        picker.pick_files.return_value = []
        with patch('koma.editor.timeline_media.ft.FilePicker', return_value=picker):
            asyncio.run(view.player.media.pick_audio())
        self.assertEqual(picker.pick_files.call_args.kwargs['initial_directory'], str(audio))
