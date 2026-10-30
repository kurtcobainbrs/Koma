"""Live metadata, updated independently of image preview and timeline geometry."""
import flet as ft
from koma.editor.reference_data import ReferenceData
from koma.ui.reference_readout import ReferenceReadout
from koma.ui.reference_fields import ReferenceFields
from koma.ui.design import dialog


class ReferencePresentation:
    def __init__(self, player):
        self.player = player
        self.data = ReferenceData(player)
        self.preview = ReferenceReadout()

    @property
    def fields(self):
        return self.player.view.preferences.options.reference_fields

    def sync(self):
        fields = self.fields
        if fields:
            self.data.sync()
        values = self.data.values(self.player.current, self.player.position) if fields else {}
        self.sync_preview(values, fields)

    def sync_preview(self, values, fields):
        player = self.player
        size = (player.screen.width, player.screen.height) if player.screen.width and player.screen.height else player.view.board.frame_format.preview_size()
        self.preview.sync(values, fields, player.view.settings.configuration.values['reference'], size)

    def sync_current(self):
        fields = self.fields
        if not fields or not self.player.timeline:
            return []
        self.data.sync()
        values = self.data.values(self.player.current, self.player.position)
        self.sync_preview(values, fields)
        return [self.preview.content]

    def refresh(self):
        if not self.player.presenting or not self.player.timeline:
            return
        self.sync()
        self.player.view.page.update(self.preview.content)

    def open_fields(self, e=None):
        view = self.player.view
        choices = ReferenceFields(view)
        def close(e=None):
            view.page.pop_dialog()
            self.player.focus_timeline()
        view.page.show_dialog(dialog(title=ft.Text('Dados de referência'),
            content=ft.Container(width=390, content=choices.content), scrollable=True,
            on_confirm=close, on_cancel=close, actions=[ft.TextButton('Fechar', on_click=close)]))
