from unittest import TestCase
from types import SimpleNamespace as Data

from tests import test_storyboard as fixtures


class FreePlacementTests(TestCase):
    setUp = fixtures.StoryboardTests.setUp
    view = fixtures.StoryboardTests.view

    def arranged(self):
        view = self.view()
        for x in (0, 384, 768):
            fixtures.finish(view.add_node('frame', position=(x, 0)))
        return view, view.board.frames

    def test_preview_keeps_neighbors_fixed_and_follows_pointer(self):
        view, (a, b, c) = self.arranged()
        ws, before = view.workspace, view.board
        ws.begin_drag(a.id, Data(global_position=Data(x=0, y=0)))
        for x in (384, 960, 1200, 0):
            ws.update_drag(a.id, Data(global_position=Data(x=x, y=0)))
            expected = (x, 0)
            node = view.cards[a.id].content
            self.assertEqual((node.left - ws.extent.origin_x, node.top - ws.extent.origin_y), expected)
            for frame in (b, c):
                node = view.cards[frame.id].content
                self.assertEqual((node.left - ws.extent.origin_x, node.top - ws.extent.origin_y), (frame.x, frame.y))
            self.assertEqual(view.board, before)
        ws.cancel_drag(a.id)
        self.assertEqual(view.board, before)

    def test_drop_moves_only_dragged_node_in_one_undo_step(self):
        view, (a, b, c) = self.arranged()
        ws, before = view.workspace, view.board
        edits = len(view.history.past)
        ws.begin_drag(a.id, Data(global_position=Data(x=0, y=0)))
        ws.update_drag(a.id, Data(global_position=Data(x=384, y=0)))
        fixtures.finish(ws.end_drag(a.id))
        positions = {frame.id: (frame.x, frame.y) for frame in view.board.frames}
        self.assertEqual(positions[a.id], (384, 0))
        self.assertEqual(positions[b.id], (384, 0))
        self.assertEqual(positions[c.id], (768, 0))
        self.assertEqual(len(view.history.past), edits + 1)
        fixtures.finish(view.graph.undo())
        self.assertEqual(view.board, before)
