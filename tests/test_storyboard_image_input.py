"""Colagem explícita no ativo, atalhos locais e preservação das fontes."""

from types import SimpleNamespace as Data
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from flet.controls.exceptions import FletUnsupportedPlatformException

from tests import test_storyboard as fixtures
from tests.test_storyboard_selection import finish
from koma.documents.images import import_image_bytes


class ImageInputTests(TestCase):
    setUp = fixtures.StoryboardTests.setUp
    view = fixtures.StoryboardTests.view

    def clipboard(self, data=None, files=None):
        return Data(get_image=AsyncMock(return_value=data), get_files=AsyncMock(return_value=files or []))

    def test_ctrl_v_replaces_only_the_active_frame_and_undo_restores_image_and_crop(self):
        view = self.view()
        finish(view.import_paths([self.source]))
        finish(view.add_frame())
        a, b = view.board.frames
        finish(view.set_frame_properties(a.id, crop_y=.7))
        view.workspace.navigation.apply_selection({a.id, b.id}, a.id)
        original = view.board
        clipboard = self.clipboard(self.original)
        with patch('koma.editor.image_input.ft.Clipboard', return_value=clipboard):
            finish(view.workspace.navigation.key_down(Data(key='Control Left')))
            finish(view.workspace.navigation.key_down(Data(key='v')))
        changed = view.board.frames[0]
        self.assertNotEqual(changed.image, a.image)
        self.assertEqual(changed.crop_y, 0)
        self.assertEqual(view.board.frames[1], b)
        self.assertEqual(view.workspace.navigation.mode, 'select')
        self.assertTrue((view.store.images / a.image).exists())
        self.assertEqual(self.source.read_bytes(), self.original)
        self.assertEqual(view.store.load(), view.board)
        finish(view.graph.undo())
        self.assertEqual(view.board, original)
        self.assertEqual(view.cards[a.id].viewport.frame.image, a.image)

    def test_copied_explorer_image_file_is_imported_when_clipboard_has_no_bitmap(self):
        view = self.view()
        finish(view.add_frame())
        frame = view.board.frames[0]
        view.workspace.navigation.select_node(frame.id)
        with patch('koma.editor.image_input.ft.Clipboard', return_value=self.clipboard(files=[str(self.source)])):
            finish(view.image_input.paste())
        self.assertTrue(view.board.frames[0].image)
        self.assertFalse(view.busy)

    def test_platform_without_bitmap_clipboard_can_still_paste_a_copied_file(self):
        view = self.view()
        finish(view.add_frame())
        view.workspace.navigation.select_node(view.board.frames[0].id)
        clipboard = self.clipboard(files=[str(self.source)])
        clipboard.get_image.side_effect = FletUnsupportedPlatformException('bitmap unavailable')
        with patch('koma.editor.image_input.ft.Clipboard', return_value=clipboard):
            finish(view.image_input.paste())
        self.assertTrue(view.board.frames[0].image)

    def test_empty_invalid_or_multiple_images_do_not_replace_existing_content(self):
        view = self.view()
        finish(view.import_paths([self.source]))
        view.workspace.navigation.select_node(view.board.frames[0].id)
        before = view.board
        for clipboard in (self.clipboard(), self.clipboard(b'invalid image'),
                          self.clipboard(files=[str(self.source), str(self.source)])):
            with self.subTest(clipboard=clipboard), patch(
                    'koma.editor.image_input.ft.Clipboard', return_value=clipboard):
                finish(view.image_input.paste())
                self.assertEqual(view.board, before)
                self.assertFalse(view.busy)
                self.assertEqual(view.feedback.state, 'warning')

    def test_no_active_frame_creates_owned_image_node_and_undo_redo_preserve_it(self):
        view = self.view()
        finish(view.add_frame())
        before = view.board
        with patch('koma.editor.image_input.ft.Clipboard', return_value=self.clipboard(self.original)):
            finish(view.image_input.paste())
        self.assertEqual(len(view.board.frames), 2)
        self.assertFalse(view.board.frames[0].image)
        pasted = view.board.frames[-1]
        self.assertTrue(pasted.image)
        self.assertTrue((view.store.images / pasted.image).exists())
        self.assertEqual(view.workspace.navigation.selected, pasted.id)
        self.assertEqual(view.store.load(), view.board)
        finish(view.graph.undo())
        self.assertEqual(view.board, before)
        finish(view.graph.redo())
        self.assertEqual(view.board.frames[-1], pasted)

    def test_destination_is_captured_before_asynchronous_clipboard_read(self):
        view = self.view()
        finish(view.add_frame())
        finish(view.add_frame())
        a, b = view.board.frames
        view.workspace.navigation.select_node(a.id)
        async def read():
            # Simula seleção alterada durante uma leitura de clipboard demorada.
            view.workspace.navigation.apply_selection({b.id}, b.id)
            return self.original
        clipboard = self.clipboard()
        clipboard.get_image.side_effect = read
        with patch('koma.editor.image_input.ft.Clipboard', return_value=clipboard):
            finish(view.image_input.paste())
        self.assertTrue(view.board.frames[0].image)
        self.assertFalse(view.board.frames[1].image)

    def test_n_toggles_properties_but_n_and_ctrl_v_do_not_intercept_text_fields(self):
        view = self.view()
        finish(view.add_frame())
        frame = view.board.frames[0]
        nav = view.workspace.navigation
        nav.select_node(frame.id)
        finish(nav.key_down(Data(key='n')))
        self.assertFalse(view.properties.content.visible)
        finish(nav.key_down(Data(key='n')))
        self.assertTrue(view.properties.content.visible)
        view.properties.title.on_focus(None)
        nav.control_keys.add('Control Left')
        with patch.object(view.image_input, 'paste', new_callable=AsyncMock) as paste:
            finish(nav.key_down(Data(key='n')))
            finish(nav.key_down(Data(key='v')))
            paste.assert_not_awaited()
        self.assertTrue(view.properties.content.visible)

    def test_direct_drag_works_without_properties_open_and_preserves_node_position(self):
        view = self.view()
        finish(view.import_paths([self.source]))
        frame = view.board.frames[0]
        view.properties.toggle()
        viewport = view.cards[frame.id].viewport
        viewport.source = (400, 1200)
        viewport.begin(Data(global_position=Data(x=0, y=0)))
        viewport.move(Data(global_position=Data(x=0, y=-100)))
        finish(viewport.end())
        self.assertGreater(view.board.frames[0].crop_y, 0)
        self.assertEqual((view.board.frames[0].x, view.board.frames[0].y), (frame.x, frame.y))
        self.assertEqual(view.workspace.navigation.selected, frame.id)

    def test_empty_nodes_contain_mode_and_pan_mode_do_not_start_image_drag(self):
        view = self.view()
        finish(view.add_frame())
        frame = view.board.frames[0]
        viewport = view.cards[frame.id].viewport
        event = Data(global_position=Data(x=0, y=0))
        viewport.begin(event)
        self.assertIsNone(viewport.drag)
        finish(view.import_paths([self.source], frame.id))
        finish(view.set_frame_properties(frame.id, image_fit='contain'))
        viewport.begin(event)
        self.assertIsNone(viewport.drag)
        finish(view.set_frame_properties(frame.id, image_fit='cover'))
        view.workspace.navigation.set_mode('pan')
        viewport.begin(event)
        self.assertIsNone(viewport.drag)

    def test_import_bytes_enforces_limits_and_cleans_failed_files(self):
        for value in (b'', b'invalid', 'text'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                import_image_bytes(value, self.store)
        if self.store.images.exists():
            self.assertEqual(list(self.store.images.iterdir()), [])
