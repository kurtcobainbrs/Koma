"""Absolute snap targets, gesture snapshots and single history commits."""
from dataclasses import replace
from types import SimpleNamespace as Data
from unittest import TestCase
from unittest.mock import patch
from koma.editor.models import Storyboard, StoryFrame, StoryLink
from koma.editor.node_media import NodeMedia, MediaTransform
from koma.editor.media_animation import MediaKeyframe, MediaPose
from koma.editor.media_models import TimelineMarker
from koma.editor.timeline import TimeScale
from koma.documents.images import import_image
from tests import test_storyboard as fixtures


class TimelineSnapTests(TestCase):
    setUp = fixtures.StoryboardTests.setUp
    view = fixtures.StoryboardTests.view

    def editor(self):
        asset, _ = import_image(self.source, self.store)
        a, b = StoryFrame(kind='main'), StoryFrame(kind='main')
        first = StoryFrame(duration=2, media=(NodeMedia(asset=asset,
            transform=MediaTransform(keyframes=(MediaKeyframe(1.5, MediaPose()),))),))
        second = StoryFrame(duration=3, media=(NodeMedia(asset=asset,
            transform=MediaTransform(keyframes=(MediaKeyframe(2.5, MediaPose()),))),))
        moving, fixed = TimelineMarker(position=3), TimelineMarker(position=1.25)
        self.session.board = Storyboard(frames=(a, first, b, second),
            links=(StoryLink(a.id, first.id), StoryLink(b.id, second.id)), markers=(moving, fixed))
        view = self.view()
        player = view.player
        player.open()
        player.select_scene(None)
        player.strip.resized(Data(width=800))
        player.strip.scale = TimeScale(100)
        player.strip.sync()
        return view, player, first, second, moving

    def test_shared_index_includes_keys_scene_shot_boundaries_and_markers(self):
        view, player, first, second, moving = self.editor()
        snap, scale = player.snapping, player.strip.scale
        targets = snap.capture(player.timeline)
        for raw, expected in ((1.48, 1.5), (1.23, 1.25), (1.98, 2), (2.98, 3), (4.48, 4.5)):
            self.assertEqual(snap.resolve(raw, scale, targets), expected)
        self.assertEqual(snap.resolve(1.48, TimeScale(1000), targets), 1.48)
        self.assertIs(snap.capture(player.timeline).positions, targets.positions)
        excluded = snap.capture(player.timeline, exclude=(('key', first.id, 1.5),))
        self.assertEqual(snap.resolve(1.48, scale, excluded), 1.48)
        player.strip.audio_controls.toggle_snap()
        self.assertFalse(snap.enabled)
        self.assertEqual(snap.resolve(1.48, scale, targets), 1.48)
        self.assertIs(player.strip.audio_controls.snap.icon, player.strip.audio_controls.snap_icons[False])

    def test_marker_snaps_to_key_without_rebuilding_index_during_move(self):
        view, player, first, second, moving = self.editor()
        before, count = view.board, len(view.history.past)
        token = player.marker_editor.begin(moving.id, 0, player.strip.scale)
        with patch.object(player.snapping, 'prepare', side_effect=AssertionError('Index rebuilt during drag')):
            player.marker_editor.move(token, -148)
        self.assertEqual(player.marker_editor.position, 1.5)
        self.assertIs(view.board, before)
        fixtures.finish(player.marker_editor.finish(token))
        self.assertEqual(len(view.history.past), count + 1)
        fixtures.finish(view.graph.undo())
        self.assertEqual(view.board, before)

    def test_key_and_cut_snap_to_marker_using_the_same_absolute_targets(self):
        view, player, first, second, moving = self.editor()
        player.select_node(first.id, seek=True)
        keys = player.strip.keyframe_lane.editor
        keys.begin(1.5, 0)
        keys.move(-23)
        self.assertEqual(keys.position, 1.25)
        keys.cancel()
        before = view.board
        token = player.duration_editor.begin(first.id, 0, player.strip.scale)
        player.duration_editor.move(token, -73)
        self.assertEqual(player.timeline.durations, (1.25, 3.75))
        self.assertIs(view.board, before)
        player.duration_editor.cancel()
        player.strip.navigator.seek(4.48, snap=True)
        self.assertEqual(player.position, 4.5)
