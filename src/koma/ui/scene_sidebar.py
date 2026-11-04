"""Cached scene navigation; drag changes the document's scene order once on drop."""
import flet as ft
from koma.editor.project_timeline import reordered_scenes
from koma.editor.timing import duration_text
from koma.ui.design import APP_PADDING, PAGE_PADDING, BORDER, MUTED, SELECTION, CONTROL_HEIGHT
from koma.ui.typography import TEXT_BODY, TEXT_SMALL
from koma.ui.image_source import thumbnail_source
from koma.ui.workspace_style import WORKSPACE_STYLE
from koma.ui.event_updates import explicit_updates
from koma.ui.retained_container import RetainedListView
from koma.ui.media_filter import media_filter


class SceneSidebar:
    def __init__(self, player):
        self.player, self.view = player, player.view
        self.key = None
        self.active = None
        self.rows, self.offsets = {}, {}
        self.pending = {}
        self.snapshot = None
        self.drag_group = f'scene-order-{self.view.session.directory.name}'
        self.list = RetainedListView(hold_updates=lambda: False, expand=True, spacing=APP_PADDING,
            item_extent=WORKSPACE_STYLE.media_row_height)
        self.project = ft.OutlinedButton('Montagem', icon=ft.Icons.VIEW_TIMELINE_OUTLINED,
            height=CONTROL_HEIGHT, tooltip='Montagem das cenas do projeto',
            on_click=lambda e: player.select_scene(None))
        self.content = ft.Container(width=WORKSPACE_STYLE.scenes_width, padding=APP_PADDING,
            border=ft.Border(right=ft.BorderSide(1, BORDER)), content=ft.Column([
                ft.Row([ft.Text('Cenas', size=TEXT_BODY, expand=True),
                    ft.IconButton(ft.Icons.CHEVRON_LEFT, width=CONTROL_HEIGHT, height=CONTROL_HEIGHT,
                        tooltip='Recolher cenas', on_click=self.toggle)]), self.project, self.list],
                spacing=APP_PADDING, horizontal_alignment=ft.CrossAxisAlignment.STRETCH))
        self.reopen = ft.IconButton(ft.Icons.VIEW_LIST_OUTLINED, width=CONTROL_HEIGHT,
            tooltip='Mostrar cenas', visible=False, on_click=self.toggle)
        self.configure()

    def configure(self):
        options = self.view.settings.configuration.values['animatic']
        self.content.width, self.content.visible = options['scenes_width'], options['scenes_visible']
        self.reopen.visible = not self.content.visible

    @explicit_updates
    def toggle(self, e=None):
        if not self.player.presenting:
            return
        self.content.visible = not self.content.visible
        self.reopen.visible = not self.content.visible
        self.player.layout.scene_splitter.content.visible = self.content.visible
        self.view.page.update(self.content, self.reopen, self.player.layout.scene_splitter.content)

    def sync(self):
        key = (id(self.view.board), tuple(self.view.settings.configuration.values['identity'].items()))
        if key != self.key:
            self.pending.clear()
            index = self.view.sequences.index
            controls, rows = [], {}
            for root in self.view.board.frames:
                if not root.node_type.starts_scene:
                    continue
                frames, cursor = [], index.following.get(root.id)
                while cursor in index.nodes and not index.nodes[cursor].node_type.starts_scene:
                    frames.extend(frame for frame in index.playback(cursor) if not frame.muted)
                    cursor = index.following.get(cursor)
                if root.muted:
                    frames = []
                total = max(sum(frame.duration for frame in frames),
                    *(track.start + track.duration for track in self.view.board.audio_tracks if track.scene_id == root.id), 0) if frames else 0
                image = next((frame.image for frame in frames if frame.image), '')
                source = thumbnail_source(self.view, image) if image else None
                preview = media_filter(self.view, ft.Image(src=source, width=WORKSPACE_STYLE.media_thumbnail_width,
                    height=CONTROL_HEIGHT, fit=ft.BoxFit.COVER)) if source else ft.Icon(ft.Icons.MOVIE_OUTLINED, color=MUTED)
                label = self.view.production.label(root.id)
                row = ft.Container(padding=APP_PADDING, height=WORKSPACE_STYLE.media_row_height,
                    opacity=.5 if root.muted else 1,
                    content=ft.GestureDetector(on_tap_down=lambda e, identifier=root.id: self.pick(identifier),
                        on_double_tap=lambda e, identifier=root.id: self.player.select_scene(identifier),
                        content=ft.Row([preview, ft.Column([
                            ft.Text(label, size=TEXT_SMALL, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(f'{duration_text(total, self.view.board.fps)} s', size=TEXT_SMALL, color=MUTED)],
                            expand=True, spacing=0, alignment=ft.MainAxisAlignment.CENTER)], spacing=APP_PADDING)),
                    tooltip=f'{label} · duplo clique abre a cena; arraste para reordenar')
                rows[root.id] = row
                target = root.id
                async def dropped(e, identifier=target):
                    await self.drop(e, identifier)
                controls.append(ft.DragTarget(group=self.drag_group, on_accept=dropped,
                    content=ft.Draggable(group=self.drag_group, data=root.id, on_drag_start=self.begin,
                        max_simultaneous_drags=1, content=row,
                        content_feedback=ft.Container(padding=PAGE_PADDING, content=ft.Text(label, size=TEXT_SMALL)))))
            self.rows, self.list.controls, self.key = rows, controls, key
            self.active = None
        self.sync_active()

    def current_scene(self):
        player = self.player
        if player.project_mode and player.timeline and 0 <= player.current < len(player.timeline.references):
            root = player.timeline.references[player.current].scene
            return root.id if root else None
        return player.scene_anchor

    def sync_active(self):
        active = self.current_scene()
        if active == self.active:
            return []
        controls = []
        for key in {self.active, active} - {None}:
            if key in self.rows:
                self.rows[key].bgcolor = SELECTION if key == active else None
                controls.append(self.rows[key])
                self.pending[key] = self.rows[key]
        self.active = active
        return controls

    def take_updates(self):
        self.sync_active()
        controls = tuple(self.pending.values()) if self.content.visible else ()
        self.pending.clear()
        return controls

    def pick(self, identifier):
        player = self.player
        if player.project_mode:
            offset = player.timeline.scene_offsets.get(identifier)
            if offset is not None:
                frame = player.timeline.frames[player.timeline.index_at(offset)]
                player.select_node(frame.id, seek=True)
            else:
                player.select_scene(identifier)
        else:
            player.select_scene(identifier)

    @explicit_updates
    def begin(self, e=None):
        self.snapshot = (self.view.board, self.view.session) if self.player.presenting and self.view.editable() and not self.player.editing else None

    async def drop(self, e, target):
        snapshot, self.snapshot = self.snapshot, None
        source = getattr(e, 'src', None)
        if (snapshot is None or snapshot[0] is not self.view.board or snapshot[1] is not self.view.session
                or not self.player.presenting or not self.view.editable() or self.player.editing or source is None or source.group != self.drag_group):
            return
        board = reordered_scenes(self.view.board, e.src.data, target,
            after=e.local_position.y > WORKSPACE_STYLE.media_row_height / 2)
        if board is not self.view.board:
            await self.view.graph.commit(board, label='Reordenar cenas')
            self.player.render()
