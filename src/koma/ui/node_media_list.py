"""Paged metadata-only media choices; inactive videos are never opened here."""
import flet as ft
from koma.ui.design import COMPACT_CONTROL_HEIGHT, APP_PADDING, BORDER, MUTED, dialog
from koma.ui.workspace_style import WORKSPACE_STYLE
from koma.ui.image_source import media_thumbnail_source
from koma.ui.typography import TEXT_SMALL
from koma.ui.media_filter import media_filter

MEDIA_PAGE_SIZE = 24
MEDIA_VISIBLE_ROWS = 4


class NodeMediaList:
    def __init__(self, view, identifier=None, on_selected=None):
        self.view, self.identifier, self.on_selected = view, identifier, on_selected
        self.page_number = 0
        self.key = None
        self.active_key = None
        self.rows = ft.Column(spacing=0, scroll=ft.ScrollMode.AUTO)
        self.count = ft.Text(size=TEXT_SMALL, color=MUTED, expand=True)
        self.previous = ft.IconButton(icon=ft.Icons.CHEVRON_LEFT, tooltip='Mídias anteriores',
            width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT, on_click=lambda e: self.page(-1))
        self.next = ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT, tooltip='Próximas mídias',
            width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT, on_click=lambda e: self.page(1))
        self.pagination = ft.Row([self.count, self.previous, self.next], spacing=0)
        self.content = ft.Column([self.rows, self.pagination], spacing=APP_PADDING, tight=True)

    def page(self, delta):
        self.page_number += delta
        self.key = None
        self.sync(self.view.node_media.target(self.identifier))
        self.view.page.update(self.content)

    def sync(self, frame):
        self.content.visible = bool(frame and frame.node_type.image)
        if not frame:
            return
        if frame.id != self.identifier:
            self.page_number = 0
        active_key = frame.id, frame.active_media_id
        if active_key != self.active_key:
            self.page_number = next((i // MEDIA_PAGE_SIZE for i, item in enumerate(frame.media)
                if item.id == frame.active_media_id), 0)
            self.active_key = active_key
        self.identifier = frame.id
        key = (frame.id, frame.media, frame.active_media_id, self.page_number, self.view.session)
        if key == self.key:
            return
        self.page_number = max(0, min(self.page_number, max(0, (len(frame.media) - 1) // MEDIA_PAGE_SIZE)))
        self.key = key
        session = self.view.session
        def choose(media_id):
            async def selected(e):
                if self.view.session is session:
                    await self.view.node_media.activate(frame.id, media_id)
                    if self.on_selected:
                        self.on_selected()
            return selected
        def remove(media_id):
            async def removed(e):
                if self.view.session is session:
                    await self.view.node_media.remove(frame.id, media_id)
            return removed
        entries = frame.media[self.page_number * MEDIA_PAGE_SIZE:(self.page_number + 1) * MEDIA_PAGE_SIZE]
        self.rows.controls = [ft.Container(border=ft.Border(bottom=ft.BorderSide(1, BORDER)), content=ft.Row([
            ft.Container(expand=True, height=WORKSPACE_STYLE.media_row_height, on_click=choose(item.id),
                content=ft.Row([ft.Icon(ft.Icons.RADIO_BUTTON_CHECKED if item.id == frame.active_media_id
                    else ft.Icons.RADIO_BUTTON_UNCHECKED, color=ft.Colors.PRIMARY if item.id == frame.active_media_id else MUTED,
                    size=18),
                media_filter(self.view, ft.Image(src=source, width=WORKSPACE_STYLE.media_thumbnail_width,
                    height=WORKSPACE_STYLE.media_row_height - APP_PADDING * 2, fit=ft.BoxFit.COVER,
                    cache_width=128)) if (source := media_thumbnail_source(self.view, item)) else
                    ft.Icon(ft.Icons.VIDEOCAM_OUTLINED if item.kind == 'video' else ft.Icons.IMAGE_OUTLINED,
                        size=COMPACT_CONTROL_HEIGHT),
                ft.Text(item.label or (('Vídeo' if item.kind == 'video' else 'Imagem') +
                    f' {self.page_number * MEDIA_PAGE_SIZE + index + 1}'), max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS, size=TEXT_SMALL, expand=True)], spacing=APP_PADDING * 2),
                tooltip=item.label or item.asset),
            ft.IconButton(icon=ft.Icons.CLOSE, tooltip='Remover mídia',
                width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT, on_click=remove(item.id))
        ], spacing=0)) for index, item in enumerate(entries)]
        self.rows.height = min(len(entries), MEDIA_VISIBLE_ROWS) * WORKSPACE_STYLE.media_row_height
        count = len(frame.media)
        self.count.value = f'{count} ' + ('mídia' if count == 1 else 'mídias') if count else 'Sem mídia'
        self.previous.visible = self.next.visible = len(frame.media) > MEDIA_PAGE_SIZE
        self.pagination.visible = len(frame.media) > MEDIA_PAGE_SIZE or not frame.media
        self.previous.disabled = self.page_number == 0
        self.next.disabled = (self.page_number + 1) * MEDIA_PAGE_SIZE >= len(frame.media)


class MediaEditor:
    def __init__(self, view, identifier):
        self.view = view
        self.list = NodeMediaList(view, identifier, on_selected=self.close)
        self.popup = dialog(title=ft.Text('Mídias'), content=ft.Container(width=360,
            content=ft.Column([ft.TextButton('Adicionar mídia', icon=ft.Icons.ADD,
                on_click=lambda e: view.node_media.pick(identifier)), self.list.content], tight=True)),
            on_dismiss=lambda e: self.dismissed(),
            on_confirm=lambda e: self.close(), on_cancel=lambda e: self.close(),
            actions=[ft.TextButton('Fechar', on_click=lambda e: self.close())])

    def open(self):
        self.view.node_media.editor = self
        self.list.sync(self.view.node_media.target(self.list.identifier))
        self.view.page.show_dialog(self.popup)

    @property
    def content(self):
        return self.list.content

    def sync(self, frame):
        self.list.sync(frame)

    def close(self):
        if self.popup.open:
            self.view.page.pop_dialog()
        self.dismissed()

    def dismissed(self):
        if self.view.node_media.editor is self:
            self.view.node_media.editor = None
        self.view.player.focus_timeline()
