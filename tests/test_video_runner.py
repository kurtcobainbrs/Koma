"""Small real MP4s exercise timing, audio, composition and safe publication."""
import math
import asyncio
import threading
import tempfile
import unittest
import wave
from array import array
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch, AsyncMock
import av
from PIL import Image
from koma.documents.store import StoryboardStore
from koma.documents.images import import_image
from koma.documents.videos import import_video
from koma.editor.models import StoryFrame
from koma.editor.drawing_models import DrawingLayer, DrawingStroke
from koma.exports.video_frames import FileFrames, StoryboardFrames
from koma.exports.video_runner import VideoRunner
from koma.exports.sequence import ExportSequence
from koma.exports.video_export import frame_counts
from tests.test_node_media import make_clip
from tests import test_storyboard as fixtures
from koma.editor.media_models import AudioTrack
from koma.editor.timeline import Timeline


class VideoRunnerTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.image = self.root / 'image.png'
        Image.new('RGB', (256, 144), '#404040').save(self.image)
        self.source = FileFrames((self.image,), (24,))
        self.destination = self.root / 'video.mp4'
        self.destination.write_bytes(b'previous video')
        self.runner = VideoRunner(self.root / 'logs')

    def export(self, source=None, progress=lambda event: None, **options):
        return self.runner.write(source or self.source, self.destination, 24, 'HIGH', 0, progress, **options)

    def video(self):
        with av.open(str(self.destination)) as container:
            stream = container.streams.video[0]
            pictures = [frame.to_image() for frame in container.decode(stream)]
            return (stream.width, stream.height, float(stream.average_rate)), pictures

    def assert_preserved(self):
        self.assertEqual(self.destination.read_bytes(), b'previous video')
        self.assertFalse(tuple(self.root.glob('.koma-video-*')))

    def test_success_produces_h264_frames_and_preserves_sources(self):
        original = self.image.read_bytes()
        self.assertEqual(self.export(), self.destination)
        metadata, pictures = self.video()
        self.assertEqual(metadata, (256, 144, 24))
        self.assertEqual(len(pictures), 24)
        self.assertEqual(self.image.read_bytes(), original)
        with av.open(str(self.destination)) as result:
            self.assertEqual(result.streams.video[0].codec_context.name, 'h264')
            self.assertFalse(result.streams.audio)
        self.assertFalse(tuple(self.root.glob('.koma-video-*')))

    def test_cancel_preserves_previous_video_and_cleans_temporary_files(self):
        self.assertIsNone(self.export(progress=lambda event: self.runner.cancel()))
        self.assert_preserved()

    def test_encoder_failure_preserves_video_and_logs_no_project_content(self):
        with patch('koma.exports.video_runner.encode', side_effect=RuntimeError('PRIVATE CONTENT')):
            with self.assertRaises(RuntimeError):
                self.export()
        self.assert_preserved()
        log = next((self.root / 'logs').glob('*.log')).read_text()
        self.assertNotIn('PRIVATE CONTENT', log)
        self.assertIn('RuntimeError', log)

    def test_changed_source_and_destination_are_never_overwritten(self):
        with self.assertRaises(ValueError):
            self.export(progress=lambda event: self.image.write_bytes(b'externally changed'))
        self.assert_preserved()
        Image.new('RGB', (256, 144)).save(self.image)
        with self.assertRaises(ValueError):
            self.export(progress=lambda event: self.destination.write_bytes(b'external destination'))
        self.assertEqual(self.destination.read_bytes(), b'external destination')
        self.assertFalse(tuple(self.root.glob('.koma-video-*')))

    def test_stale_confirmation_and_source_as_destination_are_rejected(self):
        with self.assertRaises(ValueError):
            self.export(expected_destination_stamp=None)
        self.assert_preserved()
        path = self.root / 'source.mp4'
        make_clip(path)
        original = path.read_bytes()
        with self.assertRaises(ValueError):
            self.runner.write(FileFrames((path,), (24,)), path, 24, 'HIGH', 0, lambda event: None)
        self.assertEqual(path.read_bytes(), original)

    def test_audio_preserves_offset_trim_volume_overlap_and_silence(self):
        path = self.root / 'tone.wav'
        rate = 48000
        samples = array('h')
        for index in range(rate):
            value = round(10000 * math.sin(index * 2 * math.pi * 440 / rate))
            samples.extend((value, value))
        with wave.open(str(path), 'wb') as target:
            target.setparams((2, 2, rate, 0, 'NONE', 'not compressed'))
            target.writeframes(samples.tobytes())
        self.export(audio_tracks=[
            dict(path=str(path), start=.25, volume=.5, offset=.25, duration=.5),
            dict(path=str(path), start=.5, volume=.25, duration=.25),
            dict(path=str(path), start=0, volume=0)])
        decoded = []
        with av.open(str(self.destination)) as container:
            self.assertEqual(container.streams.audio[0].codec_context.name, 'aac')
            for frame in container.decode(audio=0):
                plane = array('f')
                plane.frombytes(bytes(frame.planes[0])[:frame.samples * 4])
                decoded.extend(plane)
        def rms(start, end):
            region = decoded[round(start * rate):round(end * rate)]
            return math.sqrt(sum(value * value for value in region) / len(region))
        self.assertLess(rms(.05, .15), .01)
        self.assertGreater(rms(.3, .4), .05)
        self.assertGreater(rms(.55, .65), rms(.3, .4) * 1.2)
        self.assertLess(rms(.85, .95), .01)
        self.assertLessEqual(abs(len(decoded) - rate), 1024)

    def test_document_source_preserves_drawing_subtitle_and_video_window(self):
        store = StoryboardStore(self.root / 'store')
        name, _ = import_image(self.image, store)
        drawing = DrawingLayer((DrawingStroke(((.1, .1), (.9, .1)), '#FF0000', .05),))
        frame = StoryFrame(image=name, duration=1, subtitle='Teste', drawing=drawing)
        source = StoryboardFrames((frame,), store, (256, 144), (24,))
        self.export(source)
        _, pictures = self.video()
        pixel = pictures[0].getpixel((128, 14))
        self.assertGreater(pixel[0], pixel[1] + 100)
        self.export(replace(source, include_subtitles=False))
        _, plain = self.video()
        region = (50, 80, 206, 144)
        self.assertNotEqual(pictures[0].crop(region).tobytes(), plain[0].crop(region).tobytes())
        clip = self.root / 'clip.mp4'
        make_clip(clip)
        media, _ = import_video(clip, store)
        node = StoryFrame(media=(media,), duration=1.25)
        window = ExportSequence((node,), (1.25,), ()).window(.75, 1.25)
        self.assertEqual(window.source_offsets, (.75,))
        source = StoryboardFrames(window.frames, store, (64, 64),
            tuple(frame_counts(window.frames, 24, durations=window.durations)), offsets=window.source_offsets)
        self.export(source)
        metadata, pictures = self.video()
        self.assertEqual(len(pictures), 12)
        self.assertEqual(metadata, (64, 64, 24))
        for picture in (pictures[0], pictures[-1]):
            pixel = picture.getpixel((32, 32))
            self.assertGreater(pixel[2], pixel[0] + 100)
        self.assertEqual(node.duration, 1.25)


class VideoRunnerAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_background_progress_shutdown_and_task_cancellation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / 'frame.png'
            Image.new('RGB', (64, 64)).save(image)
            source = FileFrames((image,), (24,))
            for action in ('shutdown', 'cancel_task'):
                runner = VideoRunner(root / 'logs')
                destination = root / 'previous.mp4'
                destination.write_bytes(b'previous')
                entered = threading.Event()
                main_thread = threading.get_ident()
                progress_threads, worker_threads = [], []
                def encode(source, output, fps, quality, size, tracks, cancelled, notify):
                    worker_threads.append(threading.get_ident())
                    output.write_bytes(b'partial')
                    notify(dict(phase='Codificando MP4', done=1, total=24))
                    entered.set()
                    for _ in range(500):
                        if cancelled():
                            return False
                        threading.Event().wait(.01)
                    raise AssertionError('Cancelamento não chegou ao worker')
                with patch('koma.exports.video_runner.encode', side_effect=encode):
                    task = asyncio.create_task(runner.run(source, destination, 24, 'HIGH', 0,
                        lambda event: progress_threads.append(threading.get_ident())))
                    self.assertTrue(await asyncio.to_thread(entered.wait, 5))
                    await asyncio.sleep(0)
                    if action == 'shutdown':
                        await runner.shutdown()
                        self.assertIsNone(await task)
                    else:
                        task.cancel()
                        with self.assertRaises(asyncio.CancelledError):
                            await task
                self.assertEqual(progress_threads, [main_thread])
                self.assertNotEqual(worker_threads[0], main_thread)
                self.assertFalse(runner.running)
                self.assertFalse(tuple(root.glob('.koma-video-*')))
                self.assertEqual(destination.read_bytes(), b'previous')


class ExportCommandTests(unittest.TestCase):
    setUp = fixtures.StoryboardTests.setUp
    view = fixtures.StoryboardTests.view

    def test_editor_passes_snapshot_timing_audio_and_subtitle_options_to_internal_exporter(self):
        view = self.view()
        fixtures.finish(view.add_frame())
        track = AudioTrack(asset='a' * 32 + '.wav', duration=1, volume=.5)
        view.changed(replace(view.board, audio_tracks=(track,)))
        before = view.board
        selection = ExportSequence.from_timelines([Timeline(before)]).window(.25, .75)
        destination = self.root / 'export.mp4'
        view.files.runner.run = AsyncMock(return_value=destination)
        with patch('asyncio.current_task', return_value=None):
            fixtures.finish(view.files.export_video(selection, destination, 24, (64, 64), None,
                include_subtitles=False))
        args, options = view.files.runner.run.call_args
        self.assertIsInstance(args[0], StoryboardFrames)
        self.assertEqual(args[0].frames, selection.frames)
        self.assertEqual(args[0].counts, (12,))
        self.assertEqual(args[0].offsets, (.25,))
        self.assertFalse(args[0].include_subtitles)
        audio = options['audio_tracks'][0]
        self.assertEqual((audio['start'], audio['offset'], audio['duration'], audio['volume']), (0, .25, .5, .5))
        self.assertIs(view.board, before)
        self.assertFalse(view.busy)
        self.assertNotIn('blender', view.files.commands)
