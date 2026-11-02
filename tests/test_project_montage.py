"""Whole-project projection and scene ordering share model, history and export."""
from types import SimpleNamespace as Data
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch
from koma.editor.models import Storyboard, StoryFrame, StoryLink
from koma.editor.media_models import AudioTrack, TimelineMarker
from koma.editor.project_timeline import ProjectTimeline
from koma.exports.sequence import ExportSequence
from tests import test_storyboard as fixtures


class ProjectMontageTests(TestCase):
    setUp = fixtures.StoryboardTests.setUp
    view = fixtures.StoryboardTests.view

    def project(self):
        a, b = StoryFrame(kind='main', title='A'), StoryFrame(kind='main', title='B')
        first, second = StoryFrame(title='First', duration=2), StoryFrame(title='Second', duration=3)
        self.session.board = Storyboard(frames=(a, first, b, second),
            links=(StoryLink(a.id, first.id), StoryLink(b.id, second.id)),
            audio_tracks=(AudioTrack(asset='a' * 32 + '.wav', title='A', duration=4, scene_id=a.id),
                AudioTrack(asset='b' * 32 + '.wav', title='B', duration=1, scene_id=b.id)),
            markers=(TimelineMarker(title='B marker', position=.5, scene_id=b.id),))
        return self.view(), a, b, first, second

    def test_montage_matches_export_and_scene_navigation_does_not_change_document(self):
        view, a, b, first, second = self.project()
        before = view.board
        player = view.player
        player.open()
        player.strip.resized(Data(width=800))
        player.select_scene(None)
        self.assertIsInstance(player.timeline, ProjectTimeline)
        export = ExportSequence.from_project(before)
        self.assertEqual(player.timeline.frames, export.frames)
        self.assertEqual(player.timeline.durations, export.durations)
        self.assertEqual(player.timeline.total, 7)
        self.assertEqual(player.timeline.starts, [0, 4])
        self.assertIs(player.timeline.frames[0], next(frame for frame in before.frames if frame.id == first.id))
        self.assertEqual(player.timeline.audio_tracks[1].start, 4)
        self.assertEqual(player.timeline.markers[0].position, 4.5)
        outside = TimelineMarker(title='Outside scene', position=8, scene_id=a.id)
        projected = ProjectTimeline(replace(before, markers=(*before.markers, outside)))
        self.assertNotIn(outside.id, {marker.id for marker in projected.markers})
        with patch.object(player.audio_transport, '_submit') as submitted:
            player.audio_transport.update(player.timeline, view.store, True, 0)
            self.assertEqual(submitted.call_args.args[0].scene_id, a.id)
            player.audio_transport.update(player.timeline, view.store, True, 4.5)
            self.assertEqual(submitted.call_args.args[0].scene_id, b.id)
        player.reference_presentation.data.sync()
        self.assertEqual(player.reference_presentation.data.counts, (96, 72))
        index = view.sequences.index
        with patch.object(index, 'playback', side_effect=AssertionError('Scene list rebuilt during seek')):
            player.strip.navigator.seek(4.5)
        self.assertEqual(player.layout.sidebar.active, b.id)
        player.select_scene(b.id)
        self.assertEqual(player.timeline.root.id, b.id)
        self.assertFalse(player.project_mode)
        self.assertIs(view.board, before)
        self.assertFalse(view.history.past)

    def test_scene_drag_preserves_nodes_positions_links_and_has_one_undo(self):
        view, a, b, first, second = self.project()
        view.player.open()
        view.player.select_scene(None)
        before = view.board
        sidebar = view.player.layout.sidebar
        sidebar.begin()
        fixtures.finish(sidebar.drop(Data(src=Data(data=b.id, group=sidebar.drag_group),
            local_position=Data(y=0)), a.id))
        self.assertEqual([frame.id for frame in view.board.frames if frame.node_type.starts_scene], [b.id, a.id])
        self.assertEqual(view.board.links, before.links)
        self.assertEqual({frame.id: frame for frame in view.board.frames}, {frame.id: frame for frame in before.frames})
        self.assertEqual(len(view.history.past), 1)
        self.assertTrue(all(any(control is row for row in sidebar.rows.values())
            for control in sidebar.take_updates()))
        self.assertEqual(view.store.load(), view.board)
        fixtures.finish(view.graph.undo())
        self.assertEqual(view.board, before)
        fixtures.finish(view.graph.redo())
        self.assertEqual(view.player.timeline.frames[0].id, second.id)

    def test_project_selection_excludes_loose_nodes_and_unscoped_audio(self):
        view, a, b, first, second = self.project()
        loose, detached = StoryFrame(title='Loose'), StoryFrame(title='Detached chain')
        board = replace(view.board, frames=(*view.board.frames, loose, detached),
            links=(*view.board.links, StoryLink(loose.id, detached.id)),
            audio_tracks=(*view.board.audio_tracks,
                AudioTrack(asset='c' * 32 + '.wav', duration=20)))
        board.validate()
        for projection in (ProjectTimeline(board), ExportSequence.from_project(board)):
            self.assertEqual(tuple(frame.id for frame in projection.frames), (first.id, second.id))
            self.assertTrue(all(any(frame is node for node in board.frames) for frame in projection.frames))
            self.assertEqual(projection.total, 7)
            self.assertEqual(len(projection.audio_tracks), 2)
        self.assertIn(loose, board.frames)
        self.assertIn(detached, board.frames)
        without_scenes = Storyboard(frames=(loose, detached),
            links=(StoryLink(loose.id, detached.id),))
        self.assertEqual(ProjectTimeline(without_scenes).frames, ())
        self.assertEqual(ExportSequence.from_project(without_scenes).total, 0)

    def test_stale_drop_and_inactive_mode_cannot_reorder(self):
        view, a, b, first, second = self.project()
        view.player.open()
        sidebar = view.player.layout.sidebar
        sidebar.begin()
        fixtures.finish(view.set_frame_properties(first.id, title='Updated'))
        before = view.board
        event = Data(src=Data(data=b.id, group=sidebar.drag_group), local_position=Data(y=0))
        fixtures.finish(sidebar.drop(event, a.id))
        self.assertIs(view.board, before)
        sidebar.begin()
        view.player.close()
        fixtures.finish(sidebar.drop(event, a.id))
        self.assertIs(view.board, before)

    def test_global_sidebar_defaults_restore_and_project_mode_is_retained(self):
        view, a, b, first, second = self.project()
        view.player.open()
        before = view.board
        values = view.settings.configuration.editable()
        values['animatic'].update(scenes_visible=False, scenes_width=300, initial_scope='Montagem')
        fixtures.finish(view.settings.configuration.commit(values))
        sidebar = view.player.layout.sidebar
        self.assertFalse(sidebar.content.visible)
        self.assertTrue(sidebar.reopen.visible)
        self.assertEqual(sidebar.content.width, 300)
        self.assertFalse(view.player.layout.scene_splitter.content.visible)
        sidebar.toggle()
        self.assertTrue(sidebar.content.visible)
        view.player.close()
        view.workspace.navigation.apply_selection(set(), None)
        view.player.open()
        self.assertTrue(view.player.project_mode)
        self.assertIs(view.board, before)
        self.assertFalse(view.history.past)
