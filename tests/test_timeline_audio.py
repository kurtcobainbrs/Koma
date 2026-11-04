"""Áudio portátil, waveform, edição de marcadores e transporte sem dispositivo real."""

from array import array
import asyncio
from contextlib import ExitStack
from dataclasses import replace
import json
import math
from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import patch
import wave
from zipfile import ZipFile

from koma.audio_transport import AudioTransport, pcm_stream
from koma.documents.audio import import_audio, load_waveform, validate_audio, SAMPLE_RATE, CHANNELS
from koma.documents.session import DocumentSession
from koma.documents.store import document, parse_document
from koma.editor import graph
from koma.editor.media_models import AudioTrack, TimelineMarker
from koma.editor.models import Storyboard, StoryFrame, StoryLink
from koma.editor.timeline import Timeline, TimeScale
from koma.exports.video_export import timeline_frame_counts
from tests import test_storyboard as fixtures


def tone(path, seconds=.25, rate=16000):
    samples = array('h', (round(12000 * math.sin(2 * math.pi * 440 * i / rate)) for i in range(round(seconds * rate))))
    with wave.open(str(path), 'wb') as output:
        output.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
        output.writeframes(samples.tobytes())
    return path


class AudioFileTests(TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.session = DocumentSession(self.root / 'data')
        self.addCleanup(self.session.close)
        self.source = tone(self.root / 'áudio de teste.wav')

    def test_import_normalizes_without_modifying_source_and_generates_zoomable_peaks(self):
        original = self.source.read_bytes()
        name, duration, waveform = import_audio(self.source, self.session.store)
        self.assertEqual(self.source.read_bytes(), original)
        self.assertAlmostEqual(duration, .25, places=3)
        self.assertEqual(validate_audio(self.session.store.audio / name), duration)
        self.assertGreater(len(waveform.levels), 1)
        self.assertLess(min(waveform.levels[0]), -10000)
        self.assertGreater(max(waveform.levels[0]), 10000)
        peaks = waveform.visible_peaks(TimeScale(4000), 2, 8000, 300)
        self.assertLessEqual(len(peaks), 602)
        self.assertTrue(peaks)

    def test_corrupt_cache_is_regenerated_and_corrupt_audio_is_rejected(self):
        name, duration, waveform = import_audio(self.source, self.session.store)
        cache = self.session.store.waveforms / f'{Path(name).stem}.peaks'
        cache.write_bytes(b'bad')
        restored = load_waveform(self.session.store.audio / name, self.session.store.waveforms)
        self.assertEqual(restored.levels, waveform.levels)
        bad = self.root / 'bad.wav'
        bad.write_bytes(b'not a waveform')
        before = set(self.session.store.audio.iterdir())
        with self.assertRaises(ValueError):
            import_audio(bad, self.session.store)
        self.assertEqual(set(self.session.store.audio.iterdir()), before)

    def test_cancelled_import_leaves_no_partial_assets(self):
        with self.assertRaises(ValueError):
            import_audio(self.source, self.session.store, lambda: True)
        self.assertEqual(list(self.session.store.audio.iterdir()), [])

    def test_bundle_and_recovery_own_audio_and_preserve_markers_without_original(self):
        name, duration, _ = import_audio(self.source, self.session.store)
        frame = StoryFrame(duration=.2)
        board = Storyboard(frames=(frame,), audio_tracks=(AudioTrack(asset=name, duration=duration),),
            markers=(TimelineMarker(title='Entrada', position=.1),))
        self.session.board = board
        target = self.session.save(board, self.root / 'audio.koma')
        self.source.unlink()
        opened = DocumentSession.open(target, self.root / 'other')
        self.addCleanup(opened.close)
        self.assertEqual(opened.board, board)
        self.assertEqual(validate_audio(opened.store.audio / name), duration)
        with ZipFile(target) as archive:
            self.assertIn(f'audio/{name}', archive.namelist())
            self.assertFalse(any('peaks' in item for item in archive.namelist()))
        changed = replace(board, markers=(*board.markers, TimelineMarker(title='Fim', position=.2)))
        self.session.board = changed
        self.session.recover(changed)
        self.session.lease.close()
        recovered = DocumentSession.from_recovery(self.session.directory / 'session.json', self.root / 'data')
        self.addCleanup(recovered.close)
        self.assertEqual(recovered.board, changed)
        self.assertTrue((recovered.store.audio / name).is_file())

    def test_truncated_audio_cannot_replace_an_existing_bundle(self):
        name, duration, _ = import_audio(self.source, self.session.store)
        board = Storyboard(audio_tracks=(AudioTrack(asset=name, duration=duration),))
        target = self.session.save(board, self.root / 'safe.koma')
        previous = target.read_bytes()
        path = self.session.store.audio / name
        path.write_bytes(path.read_bytes()[:-20])
        with self.assertRaises(ValueError):
            self.session.save(board)
        self.assertEqual(target.read_bytes(), previous)

    def test_pcm_seek_delay_gain_and_end_silence(self):
        name, duration, _ = import_audio(self.source, self.session.store)
        stream = pcm_stream(self.session.store.audio / name, .9, 1, 1.5, .5)
        next(stream)
        self.assertEqual(stream.send(2400), bytes(2400 * CHANNELS * 2))
        data = stream.send(4800)
        samples = array('h'); samples.frombytes(data)
        self.assertGreater(max(samples), 5000)
        self.assertLess(max(samples), 7000)
        tail = stream.send(48000)
        self.assertTrue(tail.endswith(bytes(1000)))
        stream.close()


class MediaModelTests(TestCase):
    def test_legacy_manifest_defaults_to_no_audio_or_markers(self):
        raw = document(Storyboard(), 'a' * 32)
        raw['version'] = 1
        raw.pop('audio_tracks'); raw.pop('markers')
        board, _ = parse_document(json.loads(json.dumps(raw)))
        self.assertEqual(board.audio_tracks, ())
        self.assertEqual(board.markers, ())

    def test_media_validation_rejects_paths_duplicates_unknown_scene_and_nonfinite_values(self):
        base = AudioTrack(asset='a' * 32 + '.wav', duration=1)
        for track in (replace(base, asset='../bad.wav'), replace(base, start=float('nan')),
                replace(base, duration=0), replace(base, scene_id='b' * 32), replace(base, scene_id=0), replace(base, volume=True)):
            with self.subTest(track=track), self.assertRaises(ValueError):
                Storyboard(audio_tracks=(track,)).validate()
        with self.assertRaises(ValueError):
            Storyboard(audio_tracks=(base, replace(base, id='b' * 32))).validate()
        with self.assertRaises(ValueError):
            Storyboard(markers=(TimelineMarker(position=-1),)).validate()

    def test_scene_scope_audio_tail_and_scene_deletion_are_consistent(self):
        main, other, frame = StoryFrame(kind='main'), StoryFrame(kind='main'), StoryFrame(duration=1)
        track = AudioTrack(asset='a' * 32 + '.wav', duration=3, start=.5, scene_id=main.id)
        marker = TimelineMarker(title='Corte', position=.5, scene_id=main.id)
        board = Storyboard(frames=(main, frame, other), links=(StoryLink(main.id, frame.id),),
            audio_tracks=(track,), markers=(marker,))
        board.validate()
        timeline = Timeline(board, main.id)
        self.assertEqual(timeline.total, 1)
        self.assertEqual(timeline_frame_counts(timeline, 24), [24])
        self.assertEqual(Timeline(board, other.id).audio_tracks, ())
        self.assertEqual(Timeline(board, other.id).markers, ())
        removed = graph.remove_frames(board, {main.id})
        self.assertEqual(removed.audio_tracks, ())
        self.assertEqual(removed.markers, ())


class MediaEditingTests(TestCase):
    setUp = fixtures.StoryboardTests.setUp
    view = fixtures.StoryboardTests.view

    def editor(self):
        view = self.view()
        fixtures.finish(view.add_frame())
        view.player.open()
        view.player.strip.resized(type('Size', (), {'width': 800})())
        self.addCleanup(view.player.audio_transport.close)
        return view, view.player

    def test_import_move_mute_remove_and_undo_preserve_assets_and_history(self):
        view, player = self.editor()
        source = tone(self.root / 'music.wav')
        history = len(view.history.past)
        asyncio.run(player.media.import_path(source))
        self.assertEqual(len(view.history.past), history + 1)
        track = player.media.track
        self.assertTrue((view.store.audio / track.asset).is_file())
        fixtures.finish(player.media.set_start('24*2'))
        self.assertEqual(player.media.track.start, 2)
        fixtures.finish(player.media.change_track(muted=True))
        self.assertTrue(player.media.track.muted)
        fixtures.finish(player.media.remove_audio())
        self.assertIsNone(player.media.track)
        fixtures.finish(player.strip.undo_edit())
        self.assertEqual(player.media.track.asset, track.asset)
        self.assertEqual(view.store.load(), view.board)

    def test_markers_snap_edit_remove_and_undo_without_mutating_frames(self):
        view, player = self.editor()
        frames = view.board.frames
        player.position = .52
        fixtures.finish(player.media.set_marker('Entrada'))
        marker = player.timeline.markers[0]
        self.assertEqual(marker.position, 12 / 24)
        fixtures.finish(player.media.set_marker('Corte', '24*1.5', marker.id))
        self.assertEqual(player.timeline.markers[0].position, 1.5)
        player.media.jump_marker(1)
        self.assertEqual(player.position, 1.5)
        fixtures.finish(player.media.remove_marker(marker.id))
        fixtures.finish(player.strip.undo_edit())
        self.assertEqual(player.timeline.markers[0].title, 'Corte')
        self.assertEqual(view.board.frames, frames)

    def test_bad_marker_and_import_preserve_document(self):
        view, player = self.editor()
        before = view.board
        for title, position in (('', '1'), ('fora', '24*100'), ('bad', '1/0')):
            with self.assertRaises(ValueError):
                fixtures.finish(player.media.set_marker(title, position))
            self.assertIs(view.board, before)
        bad = self.root / 'bad.mp3'; bad.write_bytes(b'broken')
        with self.assertRaises(ValueError):
            asyncio.run(player.media.import_path(bad))
        self.assertIs(view.board, before)
        self.assertFalse(view.busy)

    def test_waveform_cache_is_bounded_and_cancellation_allows_retry(self):
        view, player = self.editor()
        media = player.media
        for index in range(media.waveform_limit + 3):
            media.remember_waveform((view.store.directory, str(index)), object())
        self.assertEqual(len(media.waveforms), media.waveform_limit)
        self.assertNotIn((view.store.directory, '0'), media.waveforms)
        track = AudioTrack(asset='a' * 32 + '.wav', duration=1)
        media.cancelled.set()
        asyncio.run(media.load_waveform(track))
        self.assertFalse(media.failed)
        media.cancelled.clear()
        from koma.documents.audio import Waveform
        waveform = Waveform((array('h', [-1, 1]),), 240)
        with patch('koma.editor.timeline_media.load_waveform', return_value=waveform):
            asyncio.run(media.load_waveform(track))
        self.assertEqual(media.waveforms[(view.store.directory, track.asset)], waveform)


class TransportTests(TestCase):
    def test_commands_are_serialized_and_stopping_closes_device(self):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as cleanup:
            root = Path(directory)
            source = tone(root / 'source.wav')
            session = DocumentSession(root / 'data')
            cleanup.callback(session.close)
            name, duration, _ = import_audio(source, session.store)
            devices = []
            class Device:
                def __init__(self, **kwargs):
                    self.closed = False
                    devices.append(self)
                def start(self, stream):
                    self.first = stream.send(480)
                def close(self):
                    self.closed = True
            transport = AudioTransport(device_factory=Device)
            cleanup.callback(transport.close)
            board = Storyboard(frames=(StoryFrame(),), audio_tracks=(AudioTrack(asset=name, duration=duration),))
            transport.update(Timeline(board), session.store, True, 0)
            transport.executor.submit(lambda: None).result(timeout=5)
            self.assertEqual(len(devices), 1)
            self.assertEqual(len(devices[0].first), 480 * CHANNELS * 2)
            transport.stop()
            transport.executor.submit(lambda: None).result(timeout=5)
            self.assertTrue(devices[0].closed)
            self.assertEqual(transport.error, '')
