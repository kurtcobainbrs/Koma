"""Um único inspetor para o node ativo; não cria campos para toda a seleção."""

import flet as ft
from dataclasses import replace

from koma.ui.design import BORDER, CONTROL_HEIGHT, MUTED, RADIUS, SURFACE, input_style
from koma.ui.typography import FONT_HEADING, TEXT_BODY, TEXT_SMALL
from koma.editor.models import TEXT_LIMIT, SUBTITLE_LIMIT, SUPPORTED_FPS
from koma.editor.scenes import principal
from koma.ui.color_picker import ColorPicker
from koma.ui.theme import load_theme
from koma.editor.shortcuts import Action
from koma.editor.timing import duration_text, parse_duration
from koma.expressions import MAX_EXPRESSION_LENGTH


class FrameProperties:
    def __init__(self, view):
        self.view = view
        self.active = self.adjusting = None
        self.opened = True
        self.heading = ft.Text('Quadro ativo', size=TEXT_BODY, font_family=FONT_HEADING)
        self.title = self.field('Título', 'title', limit=200)
        self.duration = self.field('Duração (segundos)', 'duration', limit=MAX_EXPRESSION_LENGTH)
        self.duration_frames = self.field('Duração (frames)', 'duration_frames', limit=MAX_EXPRESSION_LENGTH)
        for field in (self.duration, self.duration_frames):
            field.tooltip = 'Aceita contas: +, -, *, / e parênteses. Exemplo: 24*2. Enter mostra o resultado.'
        self.duration.on_submit = self.edit('duration', normalize=True)
        self.duration_frames.on_submit = self.edit('duration_frames', normalize=True)
        self.fps = ft.Dropdown(label='FPS do projeto', value=str(view.board.fps),
            options=[ft.DropdownOption(str(value)) for value in SUPPORTED_FPS],
            on_select=self.fps_changed, tooltip='Alterar o FPS mantém a duração em segundos.', **input_style())
        self.timing_hint = ft.Text('Frames e segundos são sincronizados. Frações de frame são arredondadas no MP4.',
            size=TEXT_SMALL, color=MUTED)
        self.action = self.field('Ação / descrição', 'action', multiline=True)
        self.audio = self.field('Diálogo / áudio', 'audio', multiline=True)
        self.subtitle = self.field('Legendas', 'subtitle', multiline=True, limit=SUBTITLE_LIMIT)
        self.subtitle.tooltip = 'Exibida na parte inferior do animatic e incluída no MP4 durante este quadro.'
        self.notes = self.field('Notas', 'notes', multiline=True)
        self.fit = ft.Dropdown(label='Imagem', value='cover', options=[
            ft.DropdownOption('cover', 'Preencher e enquadrar'), ft.DropdownOption('contain', 'Mostrar inteira')],
            on_select=self.fit_changed, **input_style())
        self.center = ft.TextButton('Centralizar', height=CONTROL_HEIGHT, on_click=self.reset_crop)
        self.image_button = ft.OutlinedButton('Escolher imagem', icon=ft.Icons.IMAGE_OUTLINED,
            height=CONTROL_HEIGHT, on_click=self.pick_image)
        self.scene_info = ft.Text(size=TEXT_SMALL, color=MUTED)
        self.color_button = ft.OutlinedButton('Cor da cena', icon=ft.Icons.PALETTE_OUTLINED,
            height=CONTROL_HEIGHT, on_click=self.pick_color, visible=False)
        self.empty = ft.Text('Selecione um quadro para editar suas propriedades.', color=MUTED, size=TEXT_SMALL)
        self.image_hint = ft.Text('Arraste a imagem no card para enquadrar. Use Colar imagem para substituir a imagem do ativo.', size=TEXT_SMALL, color=MUTED)
        self.fields = ft.Column([self.scene_info, self.title, self.color_button, self.duration, self.duration_frames,
            self.timing_hint, self.image_button, self.fit,
            self.center,
            self.image_hint,
            self.subtitle, self.action, self.audio, self.notes], visible=False, spacing=10,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.toggle_button = ft.IconButton(icon=ft.Icons.TUNE, tooltip=view.keymap.describe('Propriedades do quadro ativo', Action.PROPERTIES),
            on_click=self.toggle, width=CONTROL_HEIGHT, height=CONTROL_HEIGHT)
        self.content = ft.Container(width=292, padding=12, bgcolor=SURFACE, border=ft.Border.all(1, BORDER),
            border_radius=RADIUS, content=ft.Column([
                ft.Row([self.heading, ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT, tooltip='Recolher propriedades',
                    on_click=self.toggle, width=28, height=28)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                self.fps, self.empty, self.fields], expand=True, scroll=ft.ScrollMode.AUTO, spacing=12,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH))

    def field(self, label, key, multiline=False, limit=TEXT_LIMIT):
        style = input_style()
        if multiline:
            style.pop('height', None)
        return ft.TextField(label=label, multiline=multiline, min_lines=2 if multiline else None,
            max_lines=5 if multiline else 1, max_length=limit, counter=ft.Container(width=0, height=0),
            on_change=self.edit(key), on_focus=self.focus(key, True), on_blur=self.focus(key, False), **style)

    def focus(self, key, focused):
        def changed(e):
            if self.active:
                self.view.workspace.navigation.field_focus(self.active, key, focused)
        return changed

    def sync(self):
        self.fps.value = str(self.view.board.fps)
        identifier = self.view.workspace.navigation.selected
        if identifier != self.active:
            self.end_adjust()
            if self.active:
                self.view.workspace.navigation.editing_fields = {item for item in
                    self.view.workspace.navigation.editing_fields if item[0] != self.active}
            self.active = identifier
        frame = next((frame for frame in self.view.board.frames if frame.id == identifier), None)
        self.fields.visible, self.empty.visible = bool(frame), not bool(frame)
        self.heading.value = 'Quadro ativo'
        if frame:
            root = principal(self.view.board, frame.id)
            self.scene_info.value = f'Cena: {root.title or "Sem título"}' if root else 'Sem Node Principal'
            is_main = frame.node_type.starts_scene
            self.color_button.visible = is_main
            self.duration.visible = self.audio.visible = frame.node_type.timed
            self.duration_frames.visible = self.timing_hint.visible = frame.node_type.timed
            self.subtitle.visible = frame.node_type.timed
            for control in (self.image_button, self.fit, self.center, self.image_hint):
                control.visible = frame.node_type.image
            index = [item.id for item in self.view.board.frames if item.node_type.timed].index(frame.id)+1 if frame.node_type.timed else 0
            self.heading.value = ('Node Principal' if is_main else f'Quadro {index:02d} · propriedades'
                if frame.node_type.timed else frame.node_type.label)
            for key in ('title', 'action', 'audio', 'notes', 'subtitle'):
                getattr(self, key).value = getattr(frame, key)
            self.duration.value = duration_text(frame.duration, self.view.board.fps)
            self.duration_frames.value = duration_text(frame.duration, self.view.board.fps, frames=True)
            self.duration.error_text = None
            self.duration_frames.error_text = None
            self.fit.value = frame.image_fit
            self.center.disabled = frame.image_fit != 'cover' or not bool(frame.image)
        self.content.disabled = not self.view.editable()

    def toggle(self, e=None):
        self.opened = not self.opened
        self.content.visible = self.opened
        self.toggle_button.tooltip = self.view.keymap.describe(
            'Recolher propriedades' if self.opened else 'Mostrar propriedades do quadro ativo', Action.PROPERTIES)
        if not self.opened:
            self.end_adjust()
        self.view.page.update(self.content, self.toggle_button)
        if hasattr(self.view, 'chrome'):
            self.view.chrome.sync()
            self.view.page.update(self.view.chrome.content)
        self.view.workspace.navigation.focus_keyboard()

    def end_adjust(self):
        identifier, self.adjusting = self.adjusting, None
        if identifier in self.view.cards:
            viewport = self.view.cards[identifier].viewport
            viewport.cancel()
            viewport.layout()
            self.view.page.update(viewport.content)

    def edit(self, key, *, normalize=False):
        async def changed(e):
            identifier = self.active
            if not identifier or not self.view.editable():
                return
            value = e.control.value or ''
            if key in ('duration', 'duration_frames'):
                field = getattr(self, key)
                try:
                    value = parse_duration(value, self.view.board.fps, frames=key == 'duration_frames')
                except ValueError as exc:
                    field.error_text = str(exc)
                    self.view.page.update(field)
                    return
                field.error_text = None
                key_name = 'duration'
            else:
                key_name = key
            await self.view.set_frame_properties(identifier, coalesce_key=(identifier, key), **{key_name: value})
            if key in ('duration', 'duration_frames') and self.active == identifier:
                other = self.duration_frames if key == 'duration' else self.duration
                current = next((frame for frame in self.view.board.frames if frame.id == identifier), None)
                if current is None:
                    return
                other.value = duration_text(current.duration, self.view.board.fps, frames=key == 'duration')
                other.error_text = None
                if normalize:
                    field.value = duration_text(current.duration, self.view.board.fps, frames=key == 'duration_frames')
                self.view.page.update(field, other)
        return changed

    async def fps_changed(self, e=None):
        if not self.view.editable():
            return
        try:
            fps = int(self.fps.value)
            board = replace(self.view.board, fps=fps)
            board.validate()
        except (TypeError, ValueError):
            self.fps.value = str(self.view.board.fps)
            self.view.page.update(self.fps)
            return
        self.view.changed(board)
        self.view.refresh()
        self.view.page.update(self.view.content)
        await self.view.persist()

    async def fit_changed(self, e):
        self.end_adjust()
        await self.view.set_frame_properties(self.active, image_fit=self.fit.value)
        self.sync()
        self.view.page.update(self.content)

    async def reset_crop(self, e):
        self.end_adjust()
        await self.view.set_frame_properties(self.active, crop_x=0, crop_y=0)

    async def pick_image(self, e):
        if self.active:
            self.end_adjust()
            await self.view.pick_image(self.active)

    def pick_color(self, e):
        frame = next((frame for frame in self.view.board.frames if frame.id == self.active), None)
        if not frame or not frame.node_type.starts_scene or not self.view.editable():
            return
        def apply(color):
            self.view.page.run_task(self.view.set_frame_properties, frame.id, scene_color=color)
        ColorPicker(self.view.page, 'Cor do Node Principal',
            frame.scene_color or load_theme().colors['primary'], apply).open()
