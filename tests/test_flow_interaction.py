import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from dataclasses import replace
from types import SimpleNamespace as Data
import msgpack
from flet.controls.base_control import BaseControl
from flet.controls.object_patch import ObjectPatch
from flet.messaging.protocol import configure_encode_object_for_msgpack
from koma.editor import graph
from koma.editor.models import Storyboard, StoryFrame, StoryLink
from koma.editor.view import StoryboardView
from koma.documents.session import DocumentSession
from koma.preferences import AppPreferences
from tests.test_storyboard_selection import finish, immediate
from tests import test_storyboard as fixtures
class FlowInteractionTests(unittest.TestCase):
    def test_portrait_connection_tracks_measured_card_after_refresh_drag_and_resize(self):
        from koma.editor.frame_format import FrameFormat
        finish(self.view.graph.connect(self.a.id, self.b.id))
        self.view.changed(replace(self.view.board, frame_format=FrameFormat(1080, 1920)))
        self.view.refresh()
        self.nav.select_node(self.b.id)
        card = self.view.cards[self.b.id]
        card.viewport.resized(Data(width=300, height=544))
        self.workspace.node_resized(self.b.id, Data(height=612))
        self.view.refresh()
        self.assertEqual(card.viewport.height, 544)
        links = self.workspace.links
        before = links.port(self.b.id, False)
        board = self.view.board
        self.workspace.begin_drag(self.b.id, Data(global_position=Data(x=100, y=100)))
        self.workspace.update_drag(self.b.id, Data(global_position=Data(x=124, y=148)))
        after = links.port(self.b.id, False)
        self.assertEqual((after[0] - before[0], after[1] - before[1]), (24, 48))
        expected = card.content.top + 612 - card.layout.socket_bottom
        self.assertEqual(after[1], expected)
        self.assertIs(self.view.board, board)
        self.workspace.node_resized(self.b.id, Data(height=720))
        self.assertEqual(links.port(self.b.id, False)[1], expected + 108)
        self.workspace.cancel_drag(self.b.id)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        worker = patch('asyncio.to_thread', side_effect=immediate)
        worker.start()
        self.addCleanup(worker.stop)
        root = Path(temporary.name).resolve()
        self.view = StoryboardView(Mock(), DocumentSession(root), AppPreferences(root))
        self.addCleanup(self.view.session.close)
        self.a, self.b, self.c = (StoryFrame(title='A', x=0, y=0), StoryFrame(title='B', x=960, y=0),
                                  StoryFrame(title='C', x=480, y=600))
        self.view.session.board = self.view.session.saved_board = Storyboard(frames=(self.a, self.b, self.c))
        self.view.store.save(self.view.session.board)
        finish(self.view.activate())
        self.workspace, self.nav = self.view.workspace, self.view.workspace.navigation

    def test_click_sockets_connect(self):
        output = self.view.cards[self.a.id].sockets.controls[-1]
        target = self.view.cards[self.b.id].sockets.controls[0]
        output.on_tap_down(None)
        finish(target.on_tap_down(None))
        self.assertEqual(self.view.board.links, (StoryLink(self.a.id, self.b.id),))
        self.assertIsNone(self.workspace.links.pending)
        self.assertEqual(self.view.store.load(), self.view.board)

    def test_drag_draws_curve_and_connects_on_node_body_at_any_zoom(self):
        links = self.workspace.links
        self.workspace.zoom = .5
        source = links.port(self.a.id, True)
        left, top, right, bottom = links.bounds(self.b.id)
        endpoint = ((left + right) / 2, (top + bottom) / 2)
        links.drag_begin(self.a.id, Data(global_position=Data(x=100, y=100), local_position=Data(x=6, y=6)))
        links.drag_update(Data(global_position=Data(
            x=100 + (endpoint[0] - source[0]) * .5,
            y=100 + (endpoint[1] - source[1]) * .5)))
        self.assertIsNotNone(links.preview_shape)
        self.assertIn(links.preview_shape, links.canvas.shapes)
        self.assertFalse(self.view.board.links)
        finish(links.drag_end())
        self.assertEqual(self.view.board.links, (StoryLink(self.a.id, self.b.id),))
        self.assertIsNone(links.preview_shape)
        finish(self.view.graph.undo())
        self.assertFalse(self.view.board.links)

    def test_drop_on_empty_canvas_cancels_connection(self):
        links = self.workspace.links
        links.drag_begin(self.a.id, Data(global_position=Data(x=0, y=0), local_position=Data(x=6, y=6)))
        links.drag_update(Data(global_position=Data(x=-2000, y=-2000)))
        finish(links.drag_end())
        self.assertFalse(self.view.board.links)
        self.assertIsNone(links.pending)
        self.assertIsNone(links.preview_shape)

    def test_cut_is_committed_only_on_release_and_undo_restores_it(self):
        finish(self.view.graph.connect(self.a.id, self.b.id))
        before = self.view.board
        self.nav.set_mode('cut')
        a, b = self.workspace.links.port(self.a.id, True), self.workspace.links.port(self.b.id, False)
        x, y = (a[0]+b[0])/2, a[1]
        self.workspace.links.cut_begin(Data(local_position=Data(x=x, y=y-40)))
        self.workspace.links.cut_update(Data(local_position=Data(x=x, y=y+40)))
        self.assertEqual(self.view.board, before)
        finish(self.workspace.links.cut_end())
        self.assertFalse(self.view.board.links)
        finish(self.view.graph.undo())
        self.assertEqual(self.view.board, before)

    def test_drop_inserts_node_and_one_undo_restores_links_and_positions(self):
        finish(self.view.graph.connect(self.a.id, self.b.id))
        before = self.view.board
        self.workspace.begin_drag(self.c.id, Data(global_position=Data(x=0, y=600)))
        self.workspace.update_drag(self.c.id, Data(global_position=Data(x=0, y=0)))
        self.assertEqual(self.workspace.links.candidate, StoryLink(self.a.id, self.b.id))
        finish(self.workspace.end_drag(self.c.id))
        self.assertEqual([frame.id for frame in self.view.board.frames], [self.a.id, self.c.id, self.b.id])
        finish(self.view.graph.undo())
        self.assertEqual(self.view.board, before)

    def test_connected_node_does_not_attach_to_crossed_line(self):
        finish(self.view.graph.connect(self.a.id, self.b.id))
        finish(self.view.graph.connect(self.b.id, self.c.id))
        before = self.view.board.links
        edge = StoryLink(self.a.id, self.b.id)
        self.assertIsNone(self.workspace.links.drop_candidate(self.c.id))
        self.workspace.links.candidate = edge
        finish(self.view.position_frames({self.c.id: (480, 0)}, insert_flow=True))
        self.assertEqual(self.view.board.links, before)
        self.assertEqual(next(f for f in self.view.board.frames if f.id == self.b.id).x, self.b.x)

    def test_insertion_shifts_only_downstream_nodes_and_undo_restores_all(self):
        from koma.editor.geometry import NODE_WIDTH, GRID_STEP
        finish(self.view.position_frames({self.b.id: (600, 0)}))
        finish(self.view.add_node('frame', position=(984, 0)))
        tail = self.view.board.frames[-1]
        finish(self.view.graph.connect(self.a.id, self.b.id))
        finish(self.view.graph.connect(self.b.id, tail.id))
        before = self.view.board
        edits = len(self.view.history.past)
        self.workspace.links.candidate = StoryLink(self.a.id, self.b.id)
        finish(self.view.position_frames({self.c.id: (480, 0)}, insert_flow=True))
        positions = {f.id: (f.x, f.y) for f in self.view.board.frames}
        expected = 480 + NODE_WIDTH + GRID_STEP
        self.assertEqual(positions[self.b.id], (expected, 0))
        self.assertEqual(positions[tail.id], (expected + 384, 0))
        self.assertEqual(positions[self.a.id], (0, 0))
        self.assertEqual(positions[self.c.id], (480, 0))
        self.assertEqual(len(self.view.history.past), edits + 1)
        finish(self.view.graph.undo())
        self.assertEqual(self.view.board, before)

    def test_undo_redo_refresh_existing_text_controls_and_ignore_typing_shortcuts(self):
        self.nav.select_node(self.a.id)
        field = self.view.properties.action
        finish(self.view.edit_frame(self.a.id, 'action', 'Texto'))
        field.value = 'Texto'
        self.nav.control_keys.add('Control Left')
        self.nav.field_focus(self.a.id, 'action', True)
        finish(self.nav.key_down(Data(key='z')))
        self.assertEqual(self.view.board.frames[0].action, 'Texto')
        self.nav.field_focus(self.a.id, 'action', False)
        finish(self.nav.key_down(Data(key='z')))
        self.assertEqual(field.value, '')
        self.nav.shift_keys.add('Shift Left')
        finish(self.nav.key_down(Data(key='z')))
        self.assertEqual(field.value, 'Texto')

    def test_scene_move_and_duplicate_keep_internal_flow_and_membership(self):
        finish(self.view.graph.connect(self.a.id, self.b.id))
        finish(self.view.graph.commit(graph.group_frames(self.view.board, {self.a.id, self.b.id}, 'Cena')))
        group = self.view.board.groups[0]
        before = self.view.board
        self.workspace.scene_frames.start(group.id)(Data(global_position=Data(x=0, y=0)))
        self.workspace.scene_frames.drag(group.id)(Data(global_position=Data(x=48, y=24)))
        finish(self.workspace.scene_frames.end(group.id)(None))
        moved = {frame.id: frame for frame in self.view.board.frames}
        self.assertEqual(moved[self.a.id].x, self.a.x+48)
        self.assertEqual(moved[self.b.id].x, self.b.x+48)
        finish(self.view.graph.undo())
        self.assertEqual(self.view.board, before)
        finish(self.view.duplicate_frames(group.members))
        self.assertEqual(len(self.view.board.groups), 2)
        self.assertEqual(len(self.view.board.links), 2)

    def test_wires_use_cache_and_highlight_selected_path_without_disk_access(self):
        finish(self.view.graph.connect(self.a.id, self.b.id))
        edge = self.view.board.links[0]
        shape = self.workspace.links.cache[edge][1]
        with patch.object(self.view.store, 'save') as save:
            self.workspace.begin_drag(self.c.id, Data(global_position=Data(x=0, y=0)))
            self.workspace.update_drag(self.c.id, Data(global_position=Data(x=0, y=20)))
            self.assertIs(self.workspace.links.cache[edge][1], shape)
            self.nav.apply_selection({self.a.id})
            self.assertEqual(self.workspace.links.highlighted, {edge})
            self.workspace.cancel_drag(self.c.id)
            save.assert_not_called()

    def test_serialized_flow_groups_and_history_remain_mutable(self):
        root = self.view.content
        encoder = configure_encode_object_for_msgpack(BaseControl)
        def publish(previous):
            delta, _, _ = ObjectPatch.from_diff(previous, root, BaseControl)
            msgpack.packb(delta.to_message(), default=encoder)
        publish(None)
        self.view.page.update.side_effect = lambda *args: publish(root)
        finish(self.view.graph.connect(self.a.id, self.b.id))
        finish(self.view.graph.commit(graph.group_frames(self.view.board, {self.a.id, self.b.id}, 'Cena')))
        self.nav.apply_selection({self.a.id, self.b.id})
        self.workspace.begin_drag(self.a.id, Data(global_position=Data(x=0, y=0)))
        self.workspace.update_drag(self.a.id, Data(global_position=Data(x=48, y=24)))
        finish(self.workspace.end_drag(self.a.id))
        finish(self.view.graph.undo())
        finish(self.view.graph.redo())
        finish(self.view.graph.ungroup(self.view.board.groups[0].id))

