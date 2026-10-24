"""Atalho G reutiliza movimento de grupo, confirmação e cancelamento do canvas."""

from unittest import TestCase
from unittest.mock import patch

from tests import test_storyboard_selection as fixtures
from koma.editor.shortcuts import Action
from koma.editor.models import StoryLink


class GrabTests(TestCase):
    setUp = fixtures.StoryboardSelectionTests.setUp

    def pointer(self, x, y):
        return fixtures.Data(global_position=fixtures.Data(x=x, y=y), local_position=fixtures.Data(x=x, y=y))

    def test_remapped_move_updates_execution_and_menu_labels(self):
        a = self.frames[0]
        self.nav.apply_selection({a.id})
        self.view.keymap.rebind(Action.MOVE, ['L'])
        fixtures.finish(self.nav.key_down(fixtures.Data(key='g')))
        self.assertFalse(self.workspace.grab.active)
        fixtures.finish(self.nav.key_down(fixtures.Data(key='l')))
        self.assertTrue(self.workspace.grab.active)
        self.assertEqual(self.view.chrome.edit_items[5].content, 'Mover · L')
        self.workspace.grab.cancel()

    def test_alt_drag_detaches_and_bridges_neighbors_as_one_undo(self):
        ws, nav = self.workspace, self.nav
        a, b, c = self.frames
        fixtures.finish(self.view.graph.connect(a.id, b.id))
        fixtures.finish(self.view.graph.connect(b.id, c.id))
        before = self.view.board
        nav.apply_selection({b.id})
        fixtures.finish(nav.key_down(fixtures.Data(key='Alt Left')))
        ws.begin_drag(b.id, self.pointer(100, 100))
        ws.update_drag(b.id, self.pointer(172, 148))
        self.assertEqual(self.view.board, before)
        nav.key_up(fixtures.Data(key='Alt Left'))
        fixtures.finish(ws.end_drag(b.id))
        self.assertEqual(self.view.board.links, (StoryLink(a.id, c.id),))
        self.assertIn(b.id, {frame.id for frame in self.view.board.frames})
        self.assertEqual(nav.selection.ids, {b.id})
        fixtures.finish(self.view.graph.undo())
        self.assertEqual(self.view.board, before)

    def test_detach_modifier_can_change_and_cancel_preserves_connections(self):
        ws, nav = self.workspace, self.nav
        a, b, c = self.frames
        fixtures.finish(self.view.graph.connect(a.id, b.id))
        fixtures.finish(self.view.graph.connect(b.id, c.id))
        before = self.view.board
        nav.apply_selection({b.id})
        self.view.keymap.rebind(Action.DETACH, ['Shift'])
        fixtures.finish(nav.key_down(fixtures.Data(key='Shift Left')))
        ws.begin_drag(b.id, self.pointer(100, 100))
        ws.update_drag(b.id, self.pointer(172, 148))
        self.assertTrue(ws.drag.detach_flow)
        fixtures.finish(nav.key_down(fixtures.Data(key='Escape')))
        self.assertEqual(self.view.board, before)

    def test_g_moves_group_at_zoom_and_commits_only_once_on_click_with_undo(self):
        ws, nav = self.workspace, self.nav
        a, b, c = self.frames
        before = self.view.board
        nav.apply_selection({a.id, b.id}, a.id)
        ws.zoom = .5
        ws.hover(self.pointer(100, 100))
        with patch.object(self.view.store, 'save', wraps=self.view.store.save) as save:
            fixtures.finish(nav.key_down(fixtures.Data(key='g')))
            self.assertTrue(ws.grab.active)
            self.assertTrue(ws.scene.ignore_interactions)
            self.assertFalse(ws.viewer.scale_enabled)
            ws.hover(self.pointer(137, 127))
            self.assertEqual(self.view.board, before)
            save.assert_not_called()
            fixtures.finish(ws.pointer_surface.on_tap_down(self.pointer(137, 127)))
            save.assert_called_once()
        self.assertFalse(ws.grab.active)
        moved = {frame.id: frame for frame in self.view.board.frames}
        self.assertEqual((moved[a.id].x, moved[a.id].y), (72, 48))
        self.assertEqual(moved[b.id].x - moved[a.id].x, b.x - a.x)
        self.assertEqual(moved[c.id], c)
        fixtures.finish(self.view.graph.undo())
        self.assertEqual(self.view.board, before)

    def test_escape_right_click_and_unmount_restore_positions_without_saving(self):
        ws, nav = self.workspace, self.nav
        a = self.frames[0]
        nav.apply_selection({a.id})
        original = self.view.store.path.read_bytes()
        for cancel in (lambda: fixtures.finish(nav.key_down(fixtures.Data(key='Escape'))),
                       lambda: ws.pointer_surface.on_secondary_tap_down(None), ws.content.will_unmount):
            ws.hover(self.pointer(50, 50))
            fixtures.finish(nav.key_down(fixtures.Data(key='g')))
            ws.hover(self.pointer(150, 150))
            cancel()
            self.assertFalse(ws.grab.active)
            self.assertIsNone(ws.drag)
            self.assertEqual(self.view.cards[a.id].content.left, a.x + ws.extent.origin_x)
            self.assertEqual(self.view.store.path.read_bytes(), original)

    def test_g_ignores_text_fields_and_empty_selection_and_enter_confirms(self):
        ws, nav = self.workspace, self.nav
        fixtures.finish(nav.key_down(fixtures.Data(key='g')))
        self.assertFalse(ws.grab.active)
        nav.apply_selection({self.frames[0].id})
        nav.editing_fields.add((self.frames[0].id, 'subtitle'))
        fixtures.finish(nav.key_down(fixtures.Data(key='g')))
        self.assertFalse(ws.grab.active)
        nav.editing_fields.clear()
        ws.grab.pointer = None
        fixtures.finish(nav.key_down(fixtures.Data(key='g')))
        ws.hover(self.pointer(100, 100))
        self.assertEqual(self.view.cards[self.frames[0].id].content.left, ws.extent.origin_x)
        ws.hover(self.pointer(148, 124))
        fixtures.finish(nav.key_down(fixtures.Data(key='Enter')))
        self.assertFalse(ws.grab.active)
        self.assertEqual(self.view.board.frames[0].x, 48)
