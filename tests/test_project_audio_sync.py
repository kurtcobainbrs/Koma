"""Critical absolute-time, history and reference-transfer integrations; no GUI use."""
from dataclasses import replace
from types import SimpleNamespace as Data
from unittest import TestCase
from unittest.mock import AsyncMock, patch
from array import array
import json
import wave
from PIL import Image
from koma.exports.video_export import FrameComposer
from koma.audio_transport import mixed_pcm_stream
from koma.documents.store import document, parse_document
from koma.documents.audio import Waveform, SAMPLE_RATE
from koma.editor.models import Storyboard, StoryFrame, StoryLink
from koma.editor.media_models import AudioTrack, TimelineMarker
from koma.editor.project_timeline import ProjectTimeline, SceneTimeline
from koma.editor.timeline import Timeline, TimeScale
from koma.editor.media_animation import MediaKeyframe, MediaPose
from koma.editor.node_media import MediaTransform
from koma.exports.sequence import ExportSequence
from tests import test_storyboard as fixtures


class ProjectAudioSyncTests(TestCase):
    setUp = fixtures.StoryboardTests.setUp
    view = fixtures.StoryboardTests.view

    def project(self):
        a, b = StoryFrame(kind='main'), StoryFrame(kind='main')
        first, second = StoryFrame(duration=2), StoryFrame(duration=3)
        music = AudioTrack(asset='a' * 32 + '.wav', duration=20, start=.5)
        marker = TimelineMarker(position=2.5)
        self.session.board = Storyboard(frames=(a, first, b, second),
            links=(StoryLink(a.id, first.id), StoryLink(b.id, second.id)),
            audio_tracks=(music,), markers=(marker,))
        return self.view(), a, b, first, second, music, marker

    def test_scene_and_montage_share_absolute_picture_audio_marker_and_viewport(self):
        view, a, b, first, second, music, marker = self.project()
        player = view.player
        player.open()
        player.strip.resized(Data(width=800))
        player.select_scene(None)
        player.strip.zoom(4)
        player.strip.offset = 50
        scale, offset = player.strip.scale, player.strip.offset
        board, count = view.board, len(view.history.past)
        player.select_scene(b.id)
        self.assertEqual(player.timeline.starts, [2])
        self.assertEqual((player.timeline.total, player.timeline.playback_start, player.timeline.playback_end), (5, 2, 5))
        self.assertEqual(player.position, 2)
        player.reference_presentation.data.sync()
        self.assertEqual(player.reference_presentation.data.starts, (48,))
        self.assertEqual(player.reference_presentation.data.counts, (72,))
        self.assertEqual(player.timeline.audio_tracks, (music,))
        self.assertEqual(player.timeline.markers, (marker,))
        self.assertEqual((player.strip.scale, player.strip.offset), (scale, offset))
        player.select_scene(None)
        self.assertEqual(player.timeline.durations, (2, 3))
        self.assertEqual((player.strip.scale, player.strip.offset), (scale, offset))
        wave = Waveform((array('h', [-12000, 12000] * 2000),), SAMPLE_RATE * 20)
        self.assertEqual(wave.visible_peaks(scale, music.start, offset, 800),
            wave.visible_peaks(scale, SceneTimeline(board, b.id).audio_tracks[0].start, offset, 800))
        self.assertIs(view.board, board)
        self.assertEqual(len(view.history.past), count)

    def test_audio_toolbar_groups_controls_and_scope_switch_preserves_waveform_and_document(self):
        view, a, b, first, second, music, marker = self.project()
        optional = AudioTrack(asset='b' * 32 + '.wav', title='Ambiente', duration=1, scene_id=b.id)
        view.changed(replace(view.board, audio_tracks=(music, optional)))
        player = view.player
        player.open()
        player.select_scene(b.id)
        player.strip.resized(Data(width=800))
        controls = player.strip.audio_controls
        board, count = view.board, len(view.history.past)
        waveform = player.strip.audio_lane.canvas.shapes
        self.assertIn(controls.scope.button, controls.content.controls)
        self.assertIn(controls.import_button, controls.content.controls)
        self.assertIn(controls.mute, controls.level_group.controls)
        self.assertIn(controls.start, controls.start_group.controls)
        self.assertTrue(controls.edit_group.visible)
        fixtures.finish(controls.scope.button.items[1].on_click(None))
        self.assertTrue(player.media.audio_scene)
        self.assertEqual(player.media.track, optional)
        self.assertEqual(controls.file_name.value, 'Ambiente')
        self.assertIs(player.strip.audio_lane.canvas.shapes, waveform)
        self.assertIs(view.board, board)
        self.assertEqual(len(view.history.past), count)
        fixtures.finish(controls.scope.button.items[0].on_click(None))
        self.assertFalse(player.media.audio_scene)
        self.assertEqual(player.media.track, music)

    def test_montage_trim_is_temporary_then_one_history_commit_with_exact_durations(self):
        view, a, b, first, second, music, marker = self.project()
        player = view.player
        player.open()
        player.select_scene(None)
        player.strip.resized(Data(width=800))
        before, count = view.board, len(view.history.past)
        scale = player.strip.scale
        token = player.duration_editor.begin(first.id, 0, scale)
        player.duration_editor.move(token, scale.pixels(.5))
        self.assertIs(view.board, before)
        self.assertEqual(player.timeline.durations, (2.5, 2.5))
        self.assertEqual(player.timeline.starts, [0, 2.5])
        self.assertEqual(player.timeline.audio_tracks, (music,))
        fixtures.finish(player.duration_editor.finish(token))
        self.assertEqual(len(view.history.past), count + 1)
        self.assertEqual(view.board.audio_tracks, (music,))
        fixtures.finish(view.graph.undo())
        self.assertEqual(view.board, before)
        fixtures.finish(view.graph.redo())
        self.assertEqual(ProjectTimeline(view.board).durations, (2.5, 2.5))
        self.assertEqual(parse_document(json.loads(json.dumps(document(view.board, self.session.store.document_id))))[0], view.board)

    def test_export_scene_uses_project_music_source_time_without_padding_shots(self):
        view, a, b, first, second, music, marker = self.project()
        scene = ExportSequence.from_timelines([Timeline(view.board, b.id)])
        self.assertEqual(scene.durations, (3,))
        self.assertEqual((scene.audio_tracks[0].start, scene.audio_tracks[0].source_offset), (0, 1.5))
        self.assertEqual(scene.audio_tracks[0].duration, 3)
        self.assertEqual(ExportSequence.from_timelines([SceneTimeline(view.board, b.id)]), scene)
        project = ExportSequence.from_project(view.board)
        self.assertEqual(project.starts, (0, 2))
        self.assertEqual(project.total, 5)
        self.assertEqual(sum(track.duration for track in project.audio_tracks), 4.5)
        window = project.window(2.5, 4)
        self.assertEqual(window.audio_tracks[0].source_offset, 2)

    def test_legacy_audio_is_promoted_once_and_optional_scene_track_is_preserved(self):
        view, a, b, first, second, music, marker = self.project()
        old = replace(music, scene_id=a.id)
        optional = AudioTrack(asset='b' * 32 + '.wav', duration=1, scene_id=b.id)
        board = replace(view.board, audio_tracks=(old, optional))
        raw = json.loads(json.dumps(document(board, self.session.store.document_id)))
        raw['version'] = 11
        migrated, identifier = parse_document(raw)
        self.assertEqual(migrated.audio_tracks, (music, optional))
        self.assertEqual(parse_document(json.loads(json.dumps(document(migrated, identifier))))[0], migrated)
        self.assertEqual(SceneTimeline(migrated, b.id).audio_tracks[1].start, 2)

    def test_delete_uses_only_explicit_marker_or_key_selection(self):
        view = self.view()
        fixtures.finish(view.import_paths([self.source]))
        frame = view.board.frames[0]
        transform = MediaTransform(keyframes=(MediaKeyframe(0, MediaPose()), MediaKeyframe(1, MediaPose(.2))))
        frame = replace(frame, media=(replace(frame.active_media, transform=transform),))
        marker = TimelineMarker(position=.5)
        view.changed(replace(view.board, frames=(frame,), markers=(marker,)))
        view.refresh()
        player = view.player
        player.open()
        player.strip.resized(Data(width=800))
        keys = player.strip.keyframe_lane.editor
        keys.select(0)
        player.marker_editor.select(marker.id)
        self.assertIsNone(keys.selected)
        fixtures.finish(player.key_down(Data(key='Delete', ctrl=False, alt=False, shift=False, meta=False)))
        self.assertEqual(view.board.markers, ())
        self.assertEqual(view.board.frames[0].active_media.transform.keyframes, transform.keyframes)
        fixtures.finish(view.graph.undo())
        keys.select(0)
        self.assertIsNone(player.marker_editor.selected)
        fixtures.finish(player.key_down(Data(key='Delete', ctrl=False, alt=False, shift=False, meta=False)))
        self.assertEqual(view.board.markers, (marker,))
        self.assertEqual(len(view.board.frames[0].active_media.transform.keyframes), 1)

    def test_refs_send_creates_new_nodes_without_overwriting_and_copy_uses_image_bytes(self):
        view = self.view()
        fixtures.finish(view.import_paths([self.source]))
        original = view.board.frames[0]
        view.work_modes.show_references()
        refs = view.references
        fixtures.finish(refs.actions.import_paths([self.source, self.source]))
        refs.selection.replace({item.id for item in view.board.references})
        view.workspace.navigation.apply_selection({original.id}, original.id)
        before, count = view.board, len(view.history.past)
        clipboard = AsyncMock()
        with patch('koma.editor.reference_actions.ft.Clipboard', return_value=clipboard):
            fixtures.finish(refs.actions.copy_image())
            self.assertEqual(clipboard.set_image.call_args.args[0], (view.store.images / before.references[0].asset).read_bytes())
        fixtures.finish(refs.actions.send_to_canvas())
        self.assertEqual(len(view.board.frames), 3)
        self.assertEqual(view.board.frames[0], original)
        self.assertEqual(view.board.references, before.references)
        self.assertEqual(len(view.history.past), count + 1)
        fixtures.finish(view.graph.undo())
        self.assertEqual(view.board, before)
        fixtures.finish(view.graph.redo())
        self.assertEqual(len(view.board.frames), 3)

    def test_flip_is_node_owned_undoable_persistent_and_applied_before_rotation(self):
        view = self.view()
        fixtures.finish(view.import_paths([self.source]))
        player = view.player
        player.open()
        editor = player.media_transform
        before, count = view.board, len(view.history.past)
        fixtures.finish(editor.flip('horizontal'))
        frame = editor.frame()
        self.assertTrue(frame.active_media.transform.flip_x)
        self.assertFalse(frame.active_media.transform.flip_y)
        self.assertEqual(player.preview.image.scale.scale_x, -1)
        self.assertEqual(len(view.history.past), count + 1)
        image = Image.new('RGB', (100, 100), 'red')
        image.paste('blue', (50, 0, 100, 100))
        picture = FrameComposer(frame, (100, 100), include_subtitles=False).compose(image)
        self.assertEqual(picture.getpixel((10, 50)), (0, 0, 255))
        self.assertEqual(picture.getpixel((90, 50)), (255, 0, 0))
        restored, _ = parse_document(json.loads(json.dumps(document(view.board, self.session.store.document_id))))
        self.assertEqual(restored, view.board)
        fixtures.finish(view.graph.undo())
        self.assertEqual(view.board, before)
        fixtures.finish(view.graph.redo())
        self.assertTrue(editor.frame().active_media.transform.flip_x)

    def test_optional_scene_audio_is_mixed_at_its_absolute_sample_offset(self):
        for name, value in (('music.wav', 1000), ('scene.wav', 2000)):
            with wave.open(str(self.root / name), 'wb') as output:
                output.setparams((2, 2, SAMPLE_RATE, 0, 'NONE', 'not compressed'))
                output.writeframes(array('h', [value] * 480 * 2).tobytes())
        tracks = (AudioTrack(asset='music.wav', duration=.01),
            AudioTrack(asset='scene.wav', duration=.01, start=.005))
        stream = mixed_pcm_stream(Data(audio=self.root), tracks, 0, .015)
        self.addCleanup(stream.close)
        next(stream)
        first = array('h'); first.frombytes(stream.send(240))
        overlap = array('h'); overlap.frombytes(stream.send(240))
        tail = array('h'); tail.frombytes(stream.send(240))
        self.assertEqual(set(first), {1000})
        self.assertEqual(set(overlap), {3000})
        self.assertEqual(set(tail), {2000})

    def test_keys_remain_visible_outside_shot_and_keep_their_selected_owner(self):
        view = self.view()
        fixtures.finish(view.import_paths([self.source, self.source]))
        first, second = view.board.frames
        transform = MediaTransform(keyframes=(MediaKeyframe(0, MediaPose()), MediaKeyframe(6, MediaPose(.2))))
        first = replace(first, media=(replace(first.active_media, transform=transform),))
        view.changed(replace(view.board, frames=(first, second)))
        view.refresh()
        player = view.player
        player.open()
        player.strip.resized(Data(width=800))
        player.select_node(first.id, seek=True)
        lane = player.strip.keyframe_lane
        self.assertEqual(set(lane.points), {0, 6})
        self.assertGreater(player.strip.view_total, 6)
        player.strip.navigator.seek(2.5)
        self.assertEqual(player.timeline.frames[player.current].id, second.id)
        self.assertEqual(lane.owner, (first.id, first.active_media.id))
        lane.editor.select(6)
        self.assertEqual(player.position, 2.5)
        fixtures.finish(player.delete_selection())
        self.assertEqual(len(next(frame for frame in view.board.frames if frame.id == first.id).active_media.transform.keyframes), 1)
        self.assertEqual(next(frame for frame in view.board.frames if frame.id == second.id), second)
        fixtures.finish(view.graph.undo())
        lane.editor.begin(6, 0)
        lane.editor.move(-player.strip.scale.pixels(5))
        fixtures.finish(lane.editor.finish())
        keys = next(frame for frame in view.board.frames if frame.id == first.id).active_media.transform.keyframes
        self.assertEqual(tuple(key.time for key in keys), (0, 1))
        self.assertEqual(view.player.timeline.total, 4)
