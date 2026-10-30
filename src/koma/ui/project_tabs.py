"""Abas de documentos entre a barra de menus e o canvas."""

import flet as ft
from uuid import uuid4

from koma.ui.design import BORDER, COMPACT_CONTROL_HEIGHT, MUTED, SURFACE
from koma.ui.typography import TEXT_BODY, body_style
from koma.ui.components import drag_feedback

TAB_HEIGHT = 30
TAB_LABEL_WIDTH = 160
TAB_CLOSE_WIDTH = 26


class ProjectTabs:
    def __init__(self, application):
        self.application = application
        self.entries = {}
        self.targets = {}
        self.sync_key = None
        self.group = f'koma-project-tabs-{uuid4().hex}'
        self.row = ft.Row(spacing=1, scroll=ft.ScrollMode.AUTO, expand=True)
        self.add = ft.IconButton(icon=ft.Icons.ADD, tooltip='Novo projeto', icon_size=18,
            width=TAB_HEIGHT, height=TAB_HEIGHT, on_click=application.new_document)
        self.end_target = ft.DragTarget(content=self.add, group=self.group, on_accept=self.drop_on(None))
        self.content = ft.Container(bgcolor=ft.Colors.SURFACE_CONTAINER_LOWEST,
            border=ft.Border(bottom=ft.BorderSide(1, BORDER)),
            padding=ft.Padding.symmetric(horizontal=4),
            content=ft.Row([self.row], spacing=0, height=TAB_HEIGHT))
        self.sync()

    def drop_on(self, target):
        def dropped(e):
            if e.src.group != self.group:
                return
            source = next((view for view in self.application.views
                if view.session.directory.name == e.src.data), None)
            if source is not None:
                self.application.move_tab(source, target)
        return dropped

    def create(self, view):
        async def select(e=None):
            await self.application.select_view(view)
        async def close(e=None):
            await self.application.close_tab(view)
        async def rename(e=None):
            if await self.application.select_view(view):
                view.chrome.rename()
        label = ft.Text(view.document_label, size=TEXT_BODY, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
        button = ft.TextButton(content=label, width=TAB_LABEL_WIDTH, height=COMPACT_CONTROL_HEIGHT, on_click=select,
            style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=8)))
        title = ft.GestureDetector(content=button, on_double_tap=rename)
        close_button = ft.IconButton(icon=ft.Icons.CLOSE, tooltip='Fechar projeto', icon_size=15,
            width=TAB_CLOSE_WIDTH, height=TAB_CLOSE_WIDTH, on_click=close)
        box = ft.Container(content=ft.Row([title, close_button], spacing=0, tight=True))
        return box, label, button, close_button

    def sync(self):
        app = self.application
        key = (app.view, app.transitioning, app.closing_attempt,
            tuple((view, view.document_label, view.session.path, view.busy) for view in app.views))
        if key == self.sync_key:
            return False
        self.sync_key = key
        self.entries = {view: entry for view, entry in self.entries.items() if view in app.views}
        self.targets = {view: target for view, target in self.targets.items() if view in app.views}
        for view in app.views:
            if view not in self.entries:
                self.entries[view] = self.create(view)
                drag = ft.Draggable(content=self.entries[view][0], group=self.group,
                    data=view.session.directory.name, axis=ft.Axis.HORIZONTAL,
                    max_simultaneous_drags=1,
                    content_when_dragging=ft.Container(width=TAB_LABEL_WIDTH + TAB_CLOSE_WIDTH,
                        height=TAB_HEIGHT),
                    content_feedback=drag_feedback(ft.Container(bgcolor=SURFACE,
                        width=TAB_LABEL_WIDTH + TAB_CLOSE_WIDTH, height=TAB_HEIGHT,
                        padding=ft.Padding.symmetric(horizontal=8), alignment=ft.Alignment.CENTER_LEFT,
                        content=ft.Text(view.document_label, max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS, color=ft.Colors.ON_SURFACE,
                            style=body_style()))))
                self.targets[view] = ft.DragTarget(content=drag, group=self.group, on_accept=self.drop_on(view))
            box, label, button, close = self.entries[view]
            active = view is app.view
            label.value = view.document_label
            self.targets[view].content.content_feedback.content.content.value = view.document_label
            label.color = ft.Colors.ON_SURFACE if active else MUTED
            button.tooltip = str(view.session.path) if view.session.path else 'Projeto ainda sem arquivo'
            box.bgcolor = SURFACE if active else ft.Colors.SURFACE_CONTAINER_LOWEST
            box.border = ft.Border(right=ft.BorderSide(1, BORDER),
                bottom=ft.BorderSide(2, ft.Colors.PRIMARY if active else ft.Colors.TRANSPARENT))
            close.tooltip = f'Fechar {view.board.title or "projeto"}'
        self.row.controls = [self.targets[view] for view in app.views] + [self.end_target]
        self.content.disabled = app.transitioning or app.closing_attempt or any(view.busy for view in app.views)
        return True
