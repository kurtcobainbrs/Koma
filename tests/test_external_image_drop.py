"""Comando de importação e adaptação de eventos reais do Flutter."""

from types import SimpleNamespace as Data
from unittest import TestCase
from unittest.mock import patch
import msgpack
from flet.controls.base_control import BaseControl
from flet.controls.object_patch import ObjectPatch
from flet.messaging.protocol import configure_encode_object_for_msgpack
from tests import test_storyboard as fixtures

class ExternalDropTests(TestCase):
    setUp = fixtures.StoryboardTests.setUp
    view = fixtures.StoryboardTests.view

    def event(self, view, **changes):
        data = dict(protocol=1, session_token=view.session.directory.name,
            files=[str(self.source)], node_id=None, scene_x=1096., scene_y=2096., origin_x=1000., origin_y=2000.)
        data.update(changes)
        return Data(**data)

    def test_flutter_node_id_replaces_only_second_node_ignoring_camera_and_selection(self):
        view = self.view()
        fixtures.finish(view.add_frame())
        fixtures.finish(view.add_frame())
        first, second = view.board.frames
        view.workspace.navigation.apply_selection({first.id})
        view.workspace.translation_x, view.workspace.translation_y = 99999, -99999
        view.workspace.zoom = .15
        fixtures.finish(view.external_drop.handle(self.event(view, node_id=second.id)))
        self.assertFalse(view.board.frames[0].image)
        self.assertTrue(view.board.frames[1].image)
        self.assertEqual(view.properties.active, second.id)

    def test_flutter_blank_drop_uses_scene_position_and_origin_from_same_event(self):
        view = self.view()
        fixtures.finish(view.external_drop.handle(self.event(view)))
        self.assertEqual((view.board.frames[0].x, view.board.frames[0].y), (96, 96))

    def test_expired_node_is_rejected_and_does_not_create_another(self):
        view = self.view()
        fixtures.finish(view.external_drop.handle(self.event(view, node_id='missing-node')))
        self.assertEqual(len(view.board.frames), 0)

    def test_invalid_or_stale_flutter_events_do_not_change_document(self):
        view = self.view()
        for changes in (dict(session_token='another-tab'), dict(protocol=99),
                dict(scene_x=float('nan')), dict(files=[None]), dict(node_id=[])):
            fixtures.finish(view.external_drop.handle(self.event(view, **changes)))
            self.assertEqual(len(view.board.frames), 0)

    def test_busy_or_transitioning_editor_rejects_event(self):
        view = self.view()
        view.can_accept_drop = lambda: False
        fixtures.finish(view.external_drop.handle(self.event(view)))
        self.assertEqual(len(view.board.frames), 0)
        view.can_accept_drop = lambda: True
        view.lock(True)
        fixtures.finish(view.external_drop.handle(self.event(view)))
        self.assertEqual(len(view.board.frames), 0)

    def test_custom_controls_serialize_and_keep_native_target_ids(self):
        with patch('koma.ui.drop_runtime.enabled', return_value=True):
            view = self.view()
            fixtures.finish(view.add_frame())
            identifier = view.board.frames[0].id
            self.assertEqual(view.cards[identifier].content.content.node_id, identifier)
            self.assertEqual(view.external_drop.control.session_token, view.session.directory.name)
            view.lock(True)
            self.assertTrue(view.external_drop.control.disabled)
            encoder = configure_encode_object_for_msgpack(BaseControl)
            delta, _, _ = ObjectPatch.from_diff(None, view.content, BaseControl)
            msgpack.packb(delta.to_message(), default=encoder)


    def test_empty_canvas_creates_node_at_drop_and_undo_removes_it(self):
        view = self.view()
        before = view.board
        fixtures.finish(view.image_input.drop([str(self.source)], (-72, 96)))
        frame = view.board.frames[0]
        self.assertEqual((frame.x, frame.y), (-72, 96))
        self.assertTrue(frame.image)
        self.assertEqual(self.source.read_bytes(), self.original)
        self.assertEqual(view.store.load(), view.board)
        self.assertEqual(view.properties.active, frame.id)
        fixtures.finish(view.graph.undo())
        self.assertEqual(view.board, before)


    def test_drop_on_node_changes_only_image_and_crop_and_can_undo(self):
        view = self.view()
        fixtures.finish(view.add_frame())
        fixtures.finish(view.add_frame())
        a, b = view.board.frames
        fixtures.finish(view.graph.connect(a.id, b.id))
        fixtures.finish(view.set_frame_properties(a.id, crop_x=.5, title='Meu quadro', duration=3))
        before = view.board
        fixtures.finish(view.image_input.drop([str(self.source)], (900, 900), a.id))
        updated = next(f for f in view.board.frames if f.id == a.id)
        self.assertEqual(updated.title, 'Meu quadro')
        self.assertEqual(updated.duration, 3)
        self.assertEqual((updated.x, updated.y), (a.x, a.y))
        self.assertEqual(updated.crop_x, 0)
        self.assertTrue(updated.image)
        self.assertEqual(view.board.links, before.links)
        self.assertEqual(len(view.board.frames), 2)
        fixtures.finish(view.graph.undo())
        self.assertEqual(view.board, before)


    def test_invalid_corrupt_missing_and_directory_inputs_do_not_change_board(self):
        view = self.view()
        corrupt = self.root / 'corrompida.png'
        corrupt.write_bytes(b'not an image')
        text = self.root / 'arquivo.txt'
        text.write_text('texto')
        directory = self.root / 'pasta.png'
        directory.mkdir()
        before = view.board
        for path in (corrupt, text, directory, self.root / 'ausente.png'):
            fixtures.finish(view.image_input.drop([str(path)], (0, 0)))
            self.assertEqual(view.board, before)
            self.assertFalse(view.busy)
            self.assertEqual(view.feedback.state, 'warning')


    def test_oversized_image_is_rejected_before_document_changes(self):
        view = self.view()
        before = view.board
        with patch('koma.documents.images.IMAGE_LIMIT', 100):
            fixtures.finish(view.image_input.drop([str(self.source)], (0, 0)))
        self.assertEqual(view.board, before)
        self.assertFalse(view.busy)


    def test_multiple_files_and_scene_node_are_rejected(self):
        view = self.view()
        fixtures.finish(view.add_principal())
        before = view.board
        fixtures.finish(view.image_input.drop([str(self.source)] * 2, (0, 0)))
        self.assertEqual(view.board, before)
        fixtures.finish(view.image_input.drop([str(self.source)], (0, 0), before.frames[0].id))
        self.assertEqual(view.board, before)


    def test_limit_prevents_new_node_but_allows_image_replacement(self):
        view = self.view()
        fixtures.finish(view.add_frame())
        before = view.board
        with patch('koma.editor.image_input.MAX_CARDS', 1):
            fixtures.finish(view.image_input.drop([str(self.source)], (0, 0)))
            self.assertEqual(view.board, before)
            fixtures.finish(view.image_input.drop([str(self.source)], (0, 0), before.frames[0].id))
        self.assertTrue(view.board.frames[0].image)


    def test_decode_exception_does_not_escape_drop_or_leave_editor_locked(self):
        view = self.view()
        with patch('koma.editor.image_input.import_image', side_effect=MemoryError('Sem memória')):
            fixtures.finish(view.image_input.drop([str(self.source)], (0, 0)))
        self.assertEqual(len(view.board.frames), 0)
        self.assertFalse(view.busy)


    def test_recovery_failure_keeps_original_bundle_untouched_and_edit_undoable(self):
        view = self.view()
        target = self.root / 'preservado.koma'
        view.session.save(view.board, target)
        original_bundle = target.read_bytes()
        before = view.board
        with patch.object(view.session, 'recover', side_effect=OSError('Falha simulada')):
            fixtures.finish(view.image_input.drop([str(self.source)], (96, 96)))
        self.assertEqual(target.read_bytes(), original_bundle)
        self.assertEqual(self.source.read_bytes(), self.original)
        self.assertTrue(view.dirty)
        self.assertTrue(view.retry_save.visible)
        fixtures.finish(view.graph.undo())
        self.assertEqual(view.board, before)


    def test_decoding_cannot_commit_into_a_switched_session(self):
        view = self.view()
        before = view.board
        from koma.editor.image_input import import_image
        def decode_then_switch(*args):
            result = import_image(*args)
            view.session = object()
            return result
        session = view.session
        try:
            with patch('koma.editor.image_input.import_image', side_effect=decode_then_switch):
                fixtures.finish(view.image_input.drop([str(self.source)], (96, 96)))
            self.assertEqual(view.board, before)
        finally:
            view.session = session

