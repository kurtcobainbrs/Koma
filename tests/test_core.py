import unittest
from dataclasses import replace
from koma.editor import graph
from koma.editor.history import StoryHistory
from koma.editor.models import Storyboard, StoryFrame, StoryLink

class FlowRulesTests(unittest.TestCase):
    def setUp(self):
        self.a, self.b, self.c, self.d = tuple(StoryFrame(title=str(i), x=i * 480, y=24) for i in range(4))
        self.board = Storyboard(frames=(self.c, self.b, self.a, self.d))

    def chain(self):
        return graph.connect(graph.connect(self.board, self.a.id, self.b.id), self.b.id, self.c.id)

    def test_order_follows_connections_and_positions_are_preserved(self):
        board = self.chain()
        self.assertEqual(board.frames[:3], (self.a, self.b, self.c))
        self.assertEqual(graph.connect(board, self.a.id, self.b.id), board)

    def test_cycles_self_links_missing_frames_and_occupied_sockets_are_rejected(self):
        board = self.chain()
        for source, target in ((self.c.id, self.a.id), (self.a.id, self.d.id),
                               (self.d.id, self.b.id), (self.d.id, self.d.id), ('missing', self.d.id)):
            with self.subTest(source=source, target=target), self.assertRaises(ValueError):
                graph.connect(board, source, target)
        self.assertEqual(len(board.links), 2)

    def test_insert_detaches_old_neighbors_and_bridges_both_sequences(self):
        board = graph.connect(self.chain(), self.c.id, self.d.id)
        moved = graph.insert(board, self.c.id, StoryLink(self.a.id, self.b.id))
        self.assertEqual(moved.frames, (self.a, self.c, self.b, self.d))
        self.assertEqual(set(moved.links), {StoryLink(self.a.id, self.c.id),
            StoryLink(self.c.id, self.b.id), StoryLink(self.b.id, self.d.id)})

    def test_remove_multiple_consecutive_nodes_preserves_or_breaks_flow(self):
        board = graph.connect(self.chain(), self.c.id, self.d.id)
        board = graph.group_frames(board, {self.b.id, self.c.id}, 'Cena')
        kept = graph.remove_frames(board, {self.b.id, self.c.id}, reconnect=True)
        self.assertEqual(kept.links, (StoryLink(self.a.id, self.d.id),))
        self.assertFalse(kept.groups)
        self.assertFalse(graph.remove_frames(board, {self.b.id, self.c.id}).links)

    def test_groups_reassign_members_without_duplicate_membership(self):
        board = graph.group_frames(self.board, {self.a.id, self.b.id}, 'Primeira')
        board = graph.group_frames(board, {self.b.id, self.c.id}, 'Segunda')
        self.assertEqual(set(board.groups[0].members), {self.a.id})
        with self.assertRaises(ValueError):
            graph.group_frames(board, {self.a.id}, ' ')

    def test_path_and_organize_follow_whole_chain_but_ignore_disconnected_nodes(self):
        board = self.chain()
        self.assertEqual(graph.path_links(board, {self.b.id}), set(board.links))
        self.assertFalse(graph.path_links(board, {self.d.id}))
        organized = graph.organize(board)
        a, b, c, d = organized.frames
        self.assertEqual(a.y, b.y)
        self.assertEqual(b.y, c.y)
        self.assertLess(a.x, b.x)
        self.assertGreater(d.y, a.y)

    def test_history_coalesces_typing_and_new_edits_clear_redo(self):
        history = StoryHistory(limit=2)
        first = replace(self.board, title='A')
        second = replace(first, title='AB')
        history.record(self.board, 'title')
        history.record(first, 'title')
        self.assertEqual(history.undo(second), self.board)
        self.assertEqual(history.redo(self.board), second)
        history.undo(second)
        history.record(self.board)
        self.assertFalse(history.future)


