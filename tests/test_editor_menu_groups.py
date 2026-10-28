"""Native submenu trees retain command behavior and refresh recent files."""
from types import SimpleNamespace as Data
from unittest import TestCase
from unittest.mock import AsyncMock, Mock
import flet as ft

from koma.editor.document_tools import DocumentTools
from koma.editor.shortcuts import Action
from koma.editor.editor_menu import _MenuEntry
from koma.ui.menus import MenuGroup, MenuSeparator, menu_item, submenu
from tests import test_storyboard as fixtures
from tests.test_storyboard_selection import finish


class MenuGroupTests(TestCase):
    def test_dynamic_groups_refresh_only_when_their_key_changes_or_they_open(self):
        commands = [menu_item('Um')]
        load = Mock(side_effect=lambda: list(commands))
        source = submenu('Grupo', load=load, key=lambda: len(commands))
        entry = _MenuEntry(source)
        self.assertIsInstance(entry.control, ft.SubmenuButton)
        entry.sync()
        load.assert_called_once()
        commands.append(menu_item('Dois', disabled=True))
        entry.sync()
        self.assertEqual([child.content.value for child in entry.control.controls], ['Um', 'Dois'])
        self.assertTrue(entry.control.controls[1].disabled)
        commands[0].checked = True
        entry.sync()
        self.assertTrue(entry.control.controls[0].trailing.visible)
        self.assertEqual(load.call_count, 2)
        entry.opened()
        self.assertEqual(load.call_count, 3)


class FileMenuTests(TestCase):
    setUp = fixtures.StoryboardTests.setUp
    view = fixtures.StoryboardTests.view

    def test_editor_menus_group_existing_commands_without_positional_state_bindings(self):
        view = self.view()
        chrome = view.chrome
        edit = chrome.edit_commands
        actions = [entry for entry in chrome.edit_menu.items if not isinstance(entry.data, MenuSeparator)]
        self.assertEqual(actions, [edit[action] for action in (
            Action.UNDO, Action.REDO, Action.CUT_NODES, Action.COPY, Action.PASTE,
            Action.DUPLICATE, Action.MOVE, Action.DELETE)])
        panels = next(entry for entry in chrome.view_menu.items if isinstance(entry.data, MenuGroup))
        self.assertEqual(panels.content, 'Painéis')
        self.assertIn(chrome.props_item, panels.data.items)
        self.assertIn(chrome.tools_item, panels.data.items)
        insert_import = next(entry for entry in chrome.add_menu.items if isinstance(entry.data, MenuGroup))
        file_import = next(entry for entry in view.files.menu.items
            if isinstance(entry.data, MenuGroup) and entry.content == 'Importar')
        self.assertEqual(insert_import.data.items, file_import.data.items)
        self.assertTrue(view.graph.commands['disconnect'].disabled)
        # Reordering menu entries cannot change which actions require selection.
        chrome.edit_menu.items.reverse()
        chrome.node_menu.items.reverse()
        finish(view.add_frame())
        chrome.select_all()
        self.assertFalse(edit[Action.DUPLICATE].disabled)
        self.assertFalse(view.graph.commands['disconnect'].disabled)
        chrome.select_none()
        self.assertTrue(edit[Action.DUPLICATE].disabled)
        self.assertTrue(view.graph.commands['disconnect'].disabled)

    def test_file_commands_are_grouped_and_recent_files_open_without_another_dialog(self):
        view = self.view()
        first, second = self.root / 'Cena.koma', self.root / 'Estudo.koma'
        first.touch()
        app = Data(view=view, page=view.page, recent=Data(paths=[str(first), str(second)]), open_project=AsyncMock())
        view.document_tools = DocumentTools(app)
        view.chrome.menus.sync()
        commands, items = view.files.commands, view.files.menu.items
        self.assertIs(items[0], commands['new'])
        self.assertIs(items[1], commands['open'])
        self.assertIs(items[2], view.chrome.recent_menu)
        self.assertEqual(sum(isinstance(item.data, MenuSeparator) for item in items), 3)
        groups = {item.content: item.data for item in items if isinstance(item.data, MenuGroup)}
        self.assertEqual(set(groups), {'Recentes', 'Importar', 'Exportar'})
        self.assertEqual(groups['Exportar'].items, (commands['pdf'], commands['mp4']))
        entry = next(entry for entry in view.chrome.menus.entries if entry.command is view.chrome.recent_menu)
        self.assertEqual([control.content.value for control in entry.control.controls], ['Cena.koma', 'Estudo.koma'])
        self.assertFalse(entry.control.controls[0].disabled)
        self.assertTrue(entry.control.controls[1].disabled)
        self.assertEqual(entry.control.controls[0].tooltip, str(first))
        finish(entry.control.controls[0].on_click(None))
        app.open_project.assert_awaited_once_with(first)
        view.page.pop_dialog.assert_not_called()
        second.touch()
        entry.opened()
        self.assertFalse(entry.control.controls[1].disabled)
        app.recent.paths[:] = [str(second)]
        view.chrome.menus.sync()
        self.assertEqual([control.content.value for control in entry.control.controls], ['Estudo.koma'])

    def test_recent_keyboard_dialog_uses_the_same_file_actions(self):
        view = self.view()
        path = self.root / 'Projeto.koma'
        path.touch()
        app = Data(view=view, page=view.page, recent=Data(paths=[str(path)]), open_project=AsyncMock())
        tools = DocumentTools(app)
        tools.recent()
        popup = view.page.show_dialog.call_args.args[0]
        self.assertEqual(popup.title.value, 'Recentes')
        button = popup.content.controls[-1].controls[0]
        finish(button.on_click(None))
        view.page.pop_dialog.assert_called_once()
        app.open_project.assert_awaited_once_with(path)
