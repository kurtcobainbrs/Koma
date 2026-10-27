"""Menus compactos preservam comandos, atalhos e controles mutáveis do editor."""

from types import SimpleNamespace as Data
from unittest import TestCase

import msgpack
from flet.controls.base_control import BaseControl
from flet.controls.object_patch import ObjectPatch
from flet.messaging.protocol import configure_encode_object_for_msgpack

from tests import test_storyboard as fixtures
from tests.test_storyboard_selection import finish


class ChromeTests(TestCase):
    setUp = fixtures.StoryboardTests.setUp
    view = fixtures.StoryboardTests.view

    def test_collapsed_properties_keep_a_visible_reopen_control_and_selection(self):
        view = self.view()
        finish(view.add_frame())
        props = view.properties
        view.workspace.navigation.select_node(view.board.frames[0].id)
        identifier, board = props.active, view.board
        props.toggle()
        self.assertFalse(props.content.visible)
        self.assertTrue(props.reopen_rail.visible)
        self.assertIn(props.reopen_rail, view.content.controls[1].controls)
        props.reopen_button.on_click(None)
        self.assertTrue(props.content.visible)
        self.assertFalse(props.reopen_rail.visible)
        self.assertEqual(props.active, identifier)
        self.assertIs(view.board, board)

    def test_property_sections_preserve_values_and_release_hidden_text_focus(self):
        view = self.view()
        finish(view.add_frame())
        view.workspace.navigation.select_node(view.board.frames[0].id)
        props = view.properties
        props.script_section.toggle()
        props.notes.value = 'Nota do quadro'
        finish(props.notes.on_change(Data(control=props.notes)))
        props.notes.on_focus(None)
        self.assertTrue(view.workspace.navigation.editing_fields)
        props.script_section.toggle()
        self.assertFalse(props.script_section.body.visible)
        self.assertFalse(view.workspace.navigation.editing_fields)
        props.sync()
        self.assertFalse(props.script_section.expanded)
        props.script_section.toggle()
        self.assertEqual(props.notes.value, 'Nota do quadro')
        self.assertEqual(view.store.load().frames[0].notes, 'Nota do quadro')
        finish(view.add_principal())
        view.workspace.navigation.select_node(view.board.frames[-1].id)
        self.assertFalse(props.timing.visible)
        self.assertFalse(props.image_section.content.visible)
        self.assertTrue(props.color_button.visible)

    def test_card_properties_command_opens_inspector_for_target_in_pan_mode(self):
        view = self.view()
        finish(view.add_frame())
        first = view.board.frames[0].id
        finish(view.add_frame())
        view.properties.toggle()
        view.workspace.navigation.set_mode('pan')
        view.cards[first].sequence.items[-1].on_click(None)
        self.assertEqual(view.workspace.navigation.mode, 'select')
        self.assertEqual(view.properties.active, first)
        self.assertTrue(view.properties.opened)
        self.assertTrue(view.properties.content.visible)

    def test_add_menu_creates_the_existing_node_types_and_history_menu_undoes(self):
        view = self.view()
        chrome = view.chrome
        finish(chrome.add_menu.items[0].on_click(None))
        self.assertEqual(view.board.frames[0].kind, 'main')
        finish(chrome.add_menu.items[1].on_click(None))
        self.assertEqual(len(view.board.frames), 2)
        self.assertFalse(chrome.edit_items[0].disabled)
        finish(chrome.edit_items[0].on_click(None))
        self.assertEqual(len(view.board.frames), 1)
        self.assertFalse(chrome.edit_items[1].disabled)
        finish(chrome.edit_items[1].on_click(None))
        self.assertEqual(len(view.board.frames), 2)

    def test_selection_menus_use_the_same_active_selection_and_disable_empty_actions(self):
        view = self.view()
        finish(view.add_frame())
        finish(view.add_frame())
        chrome = view.chrome
        self.assertTrue(chrome.edit_items[3].disabled)
        chrome.selection_menu.items[0].on_click(None)
        self.assertEqual(view.workspace.navigation.selection.ids, set(view.cards))
        self.assertFalse(chrome.edit_items[3].disabled)
        self.assertTrue(view.workspace.navigation.selection_bar.visible)
        self.assertFalse(view.count.visible)
        chrome.selection_menu.items[2].on_click(None)
        self.assertFalse(view.workspace.navigation.selection.ids)
        self.assertTrue(view.count.visible)

    def test_mode_snap_and_properties_items_follow_keyboard_and_button_changes(self):
        view = self.view()
        chrome = view.chrome
        view.workspace.navigation.buttons['pan'].on_click(None)
        self.assertEqual(view.workspace.navigation.mode, 'pan')
        self.assertNotIn(view.workspace.snap, view.workspace.controls.controls)
        self.assertIs(chrome.right_tools.content.controls[0], view.workspace.snap)
        finish(view.workspace.navigation.key_down(Data(key='v')))
        self.assertEqual(view.workspace.navigation.mode, 'select')
        chrome.snap_item.on_click(None)
        self.assertEqual(chrome.snap_item.checked, view.workspace.snap_enabled)
        finish(view.workspace.navigation.key_down(Data(key='n')))
        self.assertEqual(chrome.props_item.checked, view.properties.opened)
        chrome.tools_item.on_click(None)
        self.assertFalse(view.workspace.navigation.tools.visible)
        self.assertFalse(chrome.tools_item.checked)

    def test_rename_updates_the_discreet_document_label_and_persists(self):
        view = self.view()
        view.chrome.rename()
        popup = view.page.show_dialog.call_args.args[0]
        popup.content.content.value = 'Estudo de câmera'
        finish(popup.actions[-1].on_click(None))
        self.assertEqual(view.document_label, 'Estudo de câmera *')
        self.assertEqual(view.store.load().title, 'Estudo de câmera')

    def test_narrow_windows_keep_one_header_row_and_access_to_view_commands(self):
        view = self.view()
        chrome = view.chrome
        chrome.resized(Data(width=480))
        self.assertTrue(chrome.compact)
        self.assertFalse(hasattr(chrome, "name_box"))
        self.assertFalse(view.count.visible)
        self.assertFalse(view.workspace.navigation.focus_button.visible)
        self.assertEqual(chrome.content.content.height, 28)
        self.assertEqual(len(chrome.view_menu.items), 6)
        chrome.resized(Data(width=1200))
        self.assertFalse(hasattr(chrome, "name_box"))
        self.assertTrue(view.workspace.navigation.focus_button.visible)
        self.assertFalse(chrome.compact)

    def test_status_is_compact_at_rest_and_keeps_progress_and_errors_visible(self):
        view = self.view()
        view.notify('Pronto')
        self.assertFalse(view.chrome.progress_slot.visible)
        view.notify('Exportando…', 'working')
        self.assertTrue(view.chrome.progress_slot.visible)
        view.notify('Falha', 'error')
        self.assertTrue(view.chrome.progress_slot.visible)
        view.notify('Salvo', 'success')
        self.assertFalse(view.chrome.progress_slot.visible)
        self.assertEqual(len(view.content.controls), 3)

    def test_file_recovery_stays_available_when_editor_is_locked_by_invalid_document(self):
        view = self.view()
        view.load_error = 'invalid document'
        view.lock(False)
        self.assertTrue(view.toolbar.disabled)
        self.assertFalse(view.files.menu.disabled)
        self.assertTrue(view.chrome.right_tools.disabled)
        self.assertTrue(view.chrome.play.disabled)

    def test_serialized_menus_remain_mutable_during_selection_mode_and_history_changes(self):
        view = self.view()
        encoder = configure_encode_object_for_msgpack(BaseControl)
        def publish(previous):
            delta, _, _ = ObjectPatch.from_diff(previous, view.content, BaseControl)
            msgpack.packb(delta.to_message(), default=encoder)
        publish(None)
        view.page.update.side_effect = lambda *args: publish(view.content)
        finish(view.add_principal())
        finish(view.add_frame())
        view.chrome.select_all()
        view.workspace.navigation.buttons['pan'].on_click(None)
        view.workspace.navigation.buttons['select'].on_click(None)
        view.chrome.resized(Data(width=480))
        view.chrome.resized(Data(width=1200))
        finish(view.graph.undo())
        finish(view.graph.redo())
