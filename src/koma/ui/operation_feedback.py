"""Rodapé de operação compartilhado pelas ferramentas."""

import flet as ft

from koma.ui.design import BORDER, COMPACT_CONTROL_HEIGHT, CONTROL_HEIGHT, MUTED, PROGRESS, PROGRESS_ERROR, PROGRESS_HEIGHT, RADIUS, SURFACE, dialog, progress_bar
from koma.ui.typography import TEXT_BODY, TEXT_SMALL


class OperationFeedback:
    STATES = {
        'info': ('Pronto', ft.Icons.INFO_OUTLINE),
        'working': ('Em andamento', ft.Icons.HOURGLASS_TOP),
        'success': ('Concluído', ft.Icons.CHECK_CIRCLE_OUTLINE),
        'warning': ('Atenção', ft.Icons.INFO_OUTLINE),
        'error': ('Erro', ft.Icons.ERROR_OUTLINE),
        'cancelled': ('Cancelado', ft.Icons.STOP_CIRCLE_OUTLINED),
    }

    def __init__(self, message='Pronto.', details=None, *, compact=False, page=None):
        self.state = 'info'
        self.compact, self.page = compact, page
        self.icon = ft.Icon(ft.Icons.INFO_OUTLINE, size=18, color=MUTED)
        self.label = ft.Text(size=TEXT_SMALL, weight=ft.FontWeight.W_600, color=MUTED)
        self.text = ft.Text(message, size=TEXT_BODY, selectable=True,
                            max_lines=1 if compact else None,
                            overflow=ft.TextOverflow.ELLIPSIS if compact else None)
        self.notices = ft.Column(spacing=4, visible=False)
        self.progress = progress_bar(value=0, visible=False)
        self.details = ft.ExpansionTile(title=ft.Text('Detalhes e logs', size=TEXT_SMALL, color=MUTED),
            controls=details or [], dense=True, min_tile_height=28, tile_padding=0,
            controls_padding=8, visible=bool(details) and not compact, expanded=False)
        self.details_button = ft.IconButton(icon=ft.Icons.ARTICLE_OUTLINED,
            tooltip='Detalhes e logs', width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT,
            icon_size=16, visible=bool(details) and compact, on_click=self.show_details)
        self.content = ft.Container(bgcolor=SURFACE, border=ft.Border.all(1, BORDER),
            border_radius=RADIUS, padding=ft.Padding.symmetric(horizontal=8, vertical=2) if compact else 10,
            content=ft.Column([
                ft.Row([self.icon, self.label, ft.Container(content=self.text, expand=True),
                        *([self.details_button] if compact else [])], spacing=8,
                       height=COMPACT_CONTROL_HEIGHT if compact else None,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER if compact else ft.CrossAxisAlignment.START),
                self.notices,
                ft.Container(height=PROGRESS_HEIGHT, content=self.progress) if compact else self.progress,
                *([] if compact else [self.details]),
            ], spacing=2 if compact else 4, horizontal_alignment=ft.CrossAxisAlignment.STRETCH))
        self.set_state('info')

    def show_details(self, e):
        if self.page is not None:
            self.page.show_dialog(dialog(title=ft.Text('Detalhes e logs'),
                content=ft.Column(self.details.controls, tight=True, width=540, scroll=ft.ScrollMode.AUTO),
                actions=[ft.TextButton('Fechar', height=CONTROL_HEIGHT,
                                      on_click=lambda e: self.page.pop_dialog())]))

    def sync(self):
        self.notices.visible = any(control.visible for control in self.notices.controls)
        if self.state == 'error' and not self.progress.value:
            self.progress.value = 1.0  # A failure before the first frame is still visible.
        if self.compact:
            self.text.tooltip = self.text.value

    def add_notice(self, control):
        self.notices.controls.append(control)
        self.sync()

    def set_state(self, state):
        if state == 'working' and self.state == 'error':
            self.progress.value = 0
        self.state = state
        self.label.value, self.icon.icon = self.STATES[state]
        self.icon.color = self.label.color = (
            PROGRESS_ERROR if state == 'error' else PROGRESS if state in {'working', 'success'} else MUTED)
        self.progress.color = PROGRESS_ERROR if state == 'error' else PROGRESS
        self.progress.visible = state in {'working', 'error'}
        self.sync()

    def set(self, message, state=None):
        self.text.value = message
        if state:
            self.set_state(state)
        self.sync()
