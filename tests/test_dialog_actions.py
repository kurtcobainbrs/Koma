"""Explicit dialog contracts, independent of labels and native animation timing."""
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace as Data
import flet as ft

from koma.ui.dialog_actions import ActionDialog, action_dialog
from koma.ui.color_picker import ColorPicker
from tests.test_workflow_integration import inline


class DialogActionTests(unittest.TestCase):
    def setUp(self):
        native = patch('koma.ui.dialog_actions.drop_runtime.enabled', return_value=True)
        native.start()
        self.addCleanup(native.stop)

    @inline
    async def test_color_outside_accepts_and_escape_cancels_without_double_settlement(self):
        page, accept, cancel = Mock(), Mock(), Mock()
        picker = ColorPicker(page, 'Qualquer título', '#FF0000', accept, on_cancel=cancel)
        self.assertIsInstance(picker.dialog, ActionDialog)
        picker.dialog.open = True
        picker.select('#123456')
        await picker.dialog.on_outside(None)
        picker.dismiss(None)
        await picker.dialog.on_cancel(None)
        accept.assert_called_once_with('#123456')
        cancel.assert_not_called()
        page.pop_dialog.assert_called_once()
        other = ColorPicker(page, 'Outra cor', '#FF0000', accept, on_cancel=cancel)
        other.dialog.open = True
        await other.dialog.on_cancel(None)
        other.dismiss(None)
        cancel.assert_called_once()
        self.assertEqual(accept.call_count, 1)

    @inline
    async def test_enter_and_button_share_explicit_action_and_multiline_is_preserved(self):
        field = ft.TextField(value='Editado')
        multiline_submit = Mock()
        multiline = ft.TextField(multiline=True, on_submit=multiline_submit)
        calls = []
        async def accept(e):
            calls.append(field.value)
        button = ft.FilledButton('Texto sem significado lógico', on_click=accept)
        popup = action_dialog(content=ft.Column([ft.Row([field]), multiline]), actions=[button], on_confirm=accept)
        popup.open = True
        await field.on_submit(Data(control=field))
        await popup.on_confirm(Data(control=popup))
        await button.on_click(Data(control=button))
        self.assertEqual(calls, ['Editado'] * 3)
        self.assertIs(multiline.on_submit, multiline_submit)

    @inline
    async def test_closed_or_in_flight_dialog_rejects_duplicate_confirmation(self):
        calls = []
        async def accept(e):
            calls.append('confirm')
            await popup.on_confirm(e)
        popup = action_dialog(content=ft.Text('Teste'), on_confirm=accept)
        popup.open = True
        await popup.on_confirm(None)
        self.assertEqual(calls, ['confirm'])
        popup.open = False
        await popup.on_confirm(None)
        self.assertEqual(calls, ['confirm'])

    @inline
    async def test_cancel_and_outside_have_independent_configurable_actions(self):
        confirmed, cancelled, outside = Mock(), Mock(), Mock()
        popup = action_dialog(content=ft.Text('Teste'), on_confirm=confirmed, on_cancel=cancelled, on_outside=outside)
        popup.open = True
        await popup.on_cancel(None)
        await popup.on_outside(None)
        confirmed.assert_not_called()
        cancelled.assert_called_once()
        outside.assert_called_once()

    @inline
    async def test_no_default_choice_does_not_guess_from_button_labels(self):
        action = Mock()
        popup = action_dialog(content=ft.Text('Escolha explícita'), on_confirm=False,
            actions=[ft.FilledButton('Aplicar', on_click=action)])
        popup.open = True
        await popup.on_confirm(None)
        action.assert_not_called()
