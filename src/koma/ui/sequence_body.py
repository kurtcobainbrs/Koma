"""Compact composite-node presentation; all values come from its member nodes."""
import flet as ft
from koma.ui.design import APP_PADDING, COMPACT_CONTROL_HEIGHT, MUTED
from koma.ui.typography import TEXT_SMALL


class SequenceBody:
    def __init__(self, view, identifier):
        self.view, self.identifier = view, identifier
        self.info = ft.Text(size=TEXT_SMALL, color=MUTED)
        self.access = ft.TextButton('Abrir', icon=ft.Icons.OPEN_IN_NEW,
            height=COMPACT_CONTROL_HEIGHT, on_click=self.access_clicked)
        self.add = ft.IconButton(icon=ft.Icons.ADD, tooltip='Adicionar quadro',
            width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT, on_click=self.add_clicked)
        self.content = ft.Container(height=COMPACT_CONTROL_HEIGHT * 2 + APP_PADDING * 4,
            padding=APP_PADDING, on_click=lambda e: view.workspace.navigation.node_click(identifier),
            content=ft.GestureDetector(on_double_tap=self.access_clicked, content=ft.Column([self.info,
                ft.Row([self.access, self.add], spacing=0)], spacing=APP_PADDING)))

    def sync(self, frame):
        index = self.view.sequences.index
        count = len(index.leaves((frame.id,)))
        self.info.value = f'{count} ' + ('quadro' if count == 1 else 'quadros')

    async def access_clicked(self, e):
        await self.view.sequences.access(self.identifier)

    async def add_clicked(self, e):
        await self.view.sequences.add_frame(self.identifier)
