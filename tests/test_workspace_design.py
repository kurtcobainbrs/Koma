"""Integration guards for the approved layout and local presentation updates."""
from dataclasses import replace
from types import SimpleNamespace as Data
from unittest import TestCase
from unittest.mock import patch

from tests import test_storyboard as fixtures
from koma.editor.drawing_models import DrawingLayer, DrawingStroke
from koma.editor.frame_format import FrameFormat
from koma.editor.media_models import AudioTrack
from koma.ui.timeline_thumbnail import TimelineThumbnail


class WorkspaceDesignTests(TestCase):
    setUp = fixtures.StoryboardTests.setUp
    view = fixtures.StoryboardTests.view

    def editor(self):
        view = self.view()
        fixtures.finish(view.add_frame())
        view.player.open()
        return view, view.player

    def test_node_body_and_ports_follow_format_without_waiting_for_a_size_event(self):
        view, player = self.editor()
        for format in (FrameFormat(1080, 1920), FrameFormat(1000, 1000), FrameFormat()):
            old_card = view.cards[view.board.frames[0].id]
            view.workspace.node_heights[old_card.identifier] = old_card.layout.height(old_card.body.height)
            view.changed(replace(view.board, frame_format=format))
            view.refresh()
            card = view.cards[view.board.frames[0].id]
            self.assertEqual(card.body.height, card.viewport.height)
            self.assertAlmostEqual(card.viewport.width / card.viewport.height, format.aspect_ratio)
            self.assertAlmostEqual(card.viewport.width, card.layout.image_width(card.width))
            self.assertAlmostEqual(card.content.width - card.viewport.width,
                card.layout.inset * 2 + card.layout.socket_size)
            self.assertEqual(card.output_socket.top, (card.body.height - card.output_socket.height) / 2)
            anchor = view.workspace.links.port(card.identifier, True)
            self.assertAlmostEqual(anchor[1] - card.content.top,
                card.layout.inset + card.layout.header_height + card.layout.spacing + card.body.height / 2)
            self.assertEqual(card.box.border.bottom.width, card.layout.border)

    def test_duration_resize_reuses_thumbnail_image_and_vector_paths(self):
        view, player = self.editor()
        frame = replace(view.board.frames[0], drawing=DrawingLayer((DrawingStroke(((.1, .2), (.8, .7))),)))
        thumbnail = TimelineThumbnail()
        thumbnail.sync(frame, {}, 100, 74)
        image, vector = thumbnail.canvas.controls[0], thumbnail.drawing.canvas.shapes[0]
        with patch('koma.ui.drawing_overlay.cv.Path', side_effect=AssertionError('Rebuilt vector during resize')):
            for width in (120, 180, 240, 90):
                thumbnail.sync(frame, {}, width, 74)
                self.assertIs(thumbnail.canvas.controls[0], image)
                self.assertIs(thumbnail.drawing.canvas.shapes[0], vector)

    def test_inspector_drawing_action_uses_node_data_and_shared_history(self):
        view, player = self.editor()
        frame = view.board.frames[0]
        before, history = view.board, len(view.history.past)
        fixtures.finish(view.properties.toggle_drawing())
        self.assertFalse(view.board.frames[0].drawing.visible)
        self.assertIs(player.timeline.frames[0], view.board.frames[0])
        self.assertEqual(len(view.history.past), history + 1)
        self.assertEqual(view.store.load(), view.board)
        fixtures.finish(player.strip.undo_edit())
        self.assertEqual(view.board, before)
        self.assertEqual(view.board.frames[0].id, frame.id)

    def test_audio_volume_commits_once_and_escape_discards_preview(self):
        view, player = self.editor()
        track = AudioTrack(asset='f' * 32 + '.wav', title='Ambiente', duration=4)
        view.changed(replace(view.board, audio_tracks=(track,)))
        controls = player.strip.audio_controls
        before, history = view.board, len(view.history.past)
        controls.gain.begin()
        controls.volume.value = 1.5
        self.assertIs(view.board, before)
        fixtures.finish(controls.gain.finish(Data(control=controls.volume)))
        self.assertEqual(view.board.audio_tracks[0].volume, 1.5)
        self.assertEqual(len(view.history.past), history + 1)
        self.assertEqual(view.store.load(), view.board)
        controls.gain.begin()
        controls.volume.value = .2
        fixtures.finish(player.key_down(Data(key='Escape')))
        self.assertEqual(controls.volume.value, 1.5)
        self.assertTrue(player.opened)
        self.assertEqual(len(view.history.past), history + 1)
        fixtures.finish(player.strip.undo_edit())
        self.assertEqual(view.board, before)
