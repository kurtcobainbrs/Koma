from types import SimpleNamespace as Data
from unittest import TestCase
from unittest.mock import AsyncMock

from koma.editor.animatic import Timeline
from koma.editor.models import StoryFrame
from tests import test_storyboard as fixtures


class CanvasBasicsTests(TestCase):
    setUp = fixtures.StoryboardTests.setUp
    view = fixtures.StoryboardTests.view

    def test_duplicate_button_places_copy_near_original_and_selects_it(self):
        view = self.view()
        fixtures.finish(view.add_frame())
        identifier = view.board.frames[0].id
        fixtures.finish(view.position_frames({identifier: (12000, -5500)}))
        original = view.board.frames[0]
        fixtures.finish(view.cards[identifier].duplicate(None))
        copy = next(frame for frame in view.board.frames if frame.id != identifier)
        self.assertEqual((copy.x - original.x, copy.y - original.y), (48, 48))
        self.assertLessEqual(max(abs(copy.x - original.x), abs(copy.y - original.y)), 360)
        self.assertEqual(view.workspace.navigation.selection.ids, {copy.id})
        self.assertEqual(copy.image, original.image)

    def test_ctrl_d_duplicates_selected_node_and_preserves_undo(self):
        view = self.view()
        fixtures.finish(view.add_frame())
        original = view.board
        nav = view.workspace.navigation
        nav.select_node(original.frames[0].id)
        nav.control_keys.add('control')
        fixtures.finish(nav.key_down(Data(key='d')))
        self.assertEqual(len(view.board.frames), 2)
        self.assertNotEqual(nav.selected, original.frames[0].id)
        fixtures.finish(view.graph.undo())
        self.assertEqual(view.board, original)

    def test_creating_and_moving_nodes_allows_overlap(self):
        view = self.view()
        fixtures.finish(view.add_node('frame', position=(0, 0)))
        fixtures.finish(view.add_node('frame', position=(0, 0)))
        first, second = view.board.frames
        self.assertEqual((first.x, first.y), (second.x, second.y))
        fixtures.finish(view.position_frames({second.id: (48, 48)}))
        fixtures.finish(view.position_frames({second.id: (first.x, first.y)}))
        self.assertEqual([(f.x, f.y) for f in view.board.frames], [(0, 0), (0, 0)])

    def test_mute_skips_node_preserves_links_persists_and_undoes(self):
        view = self.view()
        for _ in range(3):
            fixtures.finish(view.add_frame())
        a, b, c = view.board.frames
        fixtures.finish(view.graph.connect(a.id, b.id))
        fixtures.finish(view.graph.connect(b.id, c.id))
        links = view.board.links
        view.workspace.navigation.select_node(b.id)
        fixtures.finish(view.workspace.navigation.key_down(Data(key='m')))
        self.assertEqual([f.id for f in Timeline(view.board).frames], [a.id, c.id])
        self.assertEqual(Timeline(view.board).total, 4)
        self.assertEqual(view.board.links, links)
        self.assertTrue(view.store.load().frames[1].muted)
        fixtures.finish(view.graph.undo())
        self.assertEqual(len(Timeline(view.board).frames), 3)
        self.assertFalse(view.board.frames[1].muted)

    def test_muted_scene_has_no_playback_and_default_is_not_muted(self):
        view = self.view()
        fixtures.finish(view.add_principal())
        fixtures.finish(view.add_frame())
        main, frame = view.board.frames
        fixtures.finish(view.graph.connect(main.id, frame.id))
        fixtures.finish(view.toggle_muted({main.id}))
        self.assertFalse(Timeline(view.board, frame.id).frames)
        self.assertFalse(StoryFrame().muted)

    def test_context_inserts_at_world_position_and_offers_node_mute(self):
        view = self.view()
        ws = view.workspace
        menu = ws.context_menu
        x, y = ws.extent.origin_x + 288, ws.extent.origin_y + 144
        fixtures.finish(menu.open(Data(local_position=Data(x=x, y=y), global_position=Data(x=400, y=300))))
        fixtures.finish(menu.items[1].on_click(None))
        frame = view.board.frames[0]
        self.assertEqual((frame.x, frame.y), (288, 144))
        point = Data(x=view.cards[frame.id].content.left + 10, y=view.cards[frame.id].content.top + 10)
        fixtures.finish(menu.open(Data(local_position=point, global_position=Data(x=400, y=300))))
        self.assertIn('Mutar', menu.items[0].content.value)
        fixtures.finish(menu.items[0].on_click(None))
        self.assertTrue(view.board.frames[0].muted)

    def test_shift_a_opens_compact_insertion_menu_and_escape_closes(self):
        view = self.view()
        ws, nav = view.workspace, view.workspace.navigation
        ws.context_menu.pointer = (400, 300)
        nav.shift_keys.add('shift')
        fixtures.finish(nav.key_down(Data(key='a')))
        menu = ws.context_menu
        self.assertTrue(menu.layer.visible)
        self.assertEqual([item.content.value for item in menu.items],
            ['Início de cena', 'Quadro', 'Importar imagens…'])
        self.assertEqual(menu.popup.width, 208)
        self.assertTrue(all(item.style.animation_duration == 0 for item in menu.items))
        fixtures.finish(nav.key_down(Data(key='Escape')))
        self.assertFalse(menu.layer.visible)

    def test_m_does_not_intercept_typing_and_muted_node_has_visual_indicator(self):
        view = self.view()
        fixtures.finish(view.add_frame())
        frame = view.board.frames[0]
        nav = view.workspace.navigation
        nav.select_node(frame.id)
        nav.editing_fields.add((frame.id, 'notes'))
        fixtures.finish(nav.key_down(Data(key='m')))
        self.assertFalse(view.board.frames[0].muted)
        nav.editing_fields.clear()
        fixtures.finish(nav.key_down(Data(key='m')))
        self.assertTrue(view.cards[frame.id].mute_marker.visible)
        self.assertEqual(view.cards[frame.id].box.opacity, .5)
        fixtures.finish(nav.key_down(Data(key='m')))
        self.assertFalse(view.board.frames[0].muted)
