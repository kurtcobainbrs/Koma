"""Scene/shot production roles follow graph order, independent of names and XY."""
from types import SimpleNamespace as Data
from unittest import TestCase
from koma.editor.models import Storyboard, StoryFrame, StoryLink
from koma.editor.sequences import SequenceIndex
from koma.exports.sequence import ExportSequence
from koma.exports.reference_overlay import reference_values
from koma.editor.timeline_order import reorder
from tests import test_storyboard as fixtures


class ProductionNumberTests(TestCase):
    setUp = fixtures.StoryboardTests.setUp
    view = fixtures.StoryboardTests.view

    def project(self):
        scenes = StoryFrame(kind='main', title='Mineração', x=0, y=0), StoryFrame(kind='main', title='Esteira', x=0, y=600)
        shots = tuple(StoryFrame(title=f'Plano {i}', x=i * 400, y=0) for i in range(5))
        board = Storyboard(frames=(scenes[0], *shots[:3], scenes[1], *shots[3:]), links=tuple(
            StoryLink(a.id, b.id) for chain in ((scenes[0], *shots[:3]), (scenes[1], *shots[3:]))
            for a, b in zip(chain, chain[1:])))
        return board, scenes, shots

    def test_global_shots_continue_between_scenes_and_names_do_not_determine_codes(self):
        board, scenes, shots = self.project()
        numbers = SequenceIndex(board).production
        self.assertEqual([numbers.code(frame.id) for frame in scenes], ['Scene_01', 'Scene_02'])
        self.assertEqual([numbers.code(frame.id) for frame in shots], [f'shot_{i:04d}' for i in range(1, 6)])
        renamed = board.change(scenes[0].id, title='Novo nome')
        moved = renamed.change(shots[0].id, x=9000, y=9000)
        self.assertEqual(SequenceIndex(moved).production.code(shots[0].id), 'shot_0001')
        self.assertEqual(SequenceIndex(moved).production.label(scenes[0].id), 'Scene_01 · Novo nome')

    def test_reorder_updates_canvas_timeline_reference_and_undo_without_storing_numbers(self):
        board, scenes, shots = self.project()
        view = self.view()
        view.changed(board)
        view.refresh()
        view.workspace.navigation.select_node(shots[0].id)
        view.player.open()
        view.player.strip.resized(Data(width=800))
        fixtures.finish(reorder(view.player, shots[2].id, shots[0].id))
        self.assertEqual(view.production.code(shots[2].id), 'shot_0001')
        self.assertEqual(view.production.code(shots[0].id), 'shot_0002')
        self.assertEqual(view.production.code(shots[3].id), 'shot_0004')
        self.assertEqual(view.cards[scenes[0].id].scene_code.value, 'Scene_01')
        self.assertEqual(view.cards[shots[0].id].number.value, 'shot_0002')
        self.assertIn('shot_0001', view.player.strip.blocks[shots[2].id].title.value)
        export = ExportSequence.from_project(view.board)
        reference = export.references[3]
        values = reference_values(export.frames[3], reference, local_frame=1, count=48,
            current_frame=1, total_frames=48, fps=24, size=(1920, 1080))
        self.assertIn('Scene_02', values['scene'])
        self.assertIn('shot_0004', values['shot'])
        fixtures.finish(view.graph.undo())
        self.assertEqual(view.production.code(shots[0].id), 'shot_0001')
        self.assertEqual(view.production.code(shots[2].id), 'shot_0003')
        self.assertEqual(view.store.load(), view.board)
