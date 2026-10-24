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

    def test_click_and_drag_sockets_connect_and_reject_other_canvas_sources(self):
        output = self.view.cards[self.a.id].sockets.controls[-1]
        target = self.view.cards[self.b.id].sockets.controls[0]
        finish(target.on_accept(Data(src=Data(group='other', data=self.a.id))))
        self.assertFalse(self.view.board.links)
        finish(output.content.on_tap_down(None))
        finish(target.content.on_tap_down(None))
        self.assertEqual(self.view.board.links, (StoryLink(self.a.id, self.b.id),))
        self.assertIsNone(self.workspace.links.pending)
        self.assertEqual(self.view.store.load(), self.view.board)
        finish(self.view.graph.undo())
        finish(target.on_accept(Data(src=output)))
        self.assertEqual(len(self.view.board.links), 1)

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

