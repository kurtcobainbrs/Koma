"""Um único inspetor para o node ativo; não cria campos para toda a seleção."""

import flet as ft
from dataclasses import replace

from koma.ui.design import APP_PADDING, BORDER, CONTROL_HEIGHT, COMPACT_CONTROL_HEIGHT, MUTED, PANEL_PADDING, RADIUS, SURFACE, input_style
from koma.ui.typography import FONT_HEADING, TEXT_BODY, TEXT_SMALL
from koma.editor.models import TEXT_LIMIT, SUBTITLE_LIMIT
from koma.ui.collapsible_section import CollapsibleSection
from koma.ui.node_path import path_text
from koma.ui.color_picker import ColorPicker
from koma.ui.theme import load_theme
from koma.editor.shortcuts import Action
from koma.editor.timing import duration_text, parse_duration
from koma.expressions import MAX_EXPRESSION_LENGTH
from koma.ui.node_media_list import NodeMediaList
from koma.editor.batch_properties import property_targets, apply_properties
from koma.ui.workspace_style import WORKSPACE_STYLE


class FrameProperties:
    def __init__(self, view):
        self.view = view
        self.active = self.adjusting = None
        self.opened = True
        self.heading = ft.Text('Quadro ativo', size=TEXT_BODY, font_family=FONT_HEADING)
        self.title = self.field('Título', 'title', limit=200)
        self.duration = self.field('Segundos', 'duration', limit=MAX_EXPRESSION_LENGTH)
        self.duration_frames = self.field('Frames', 'duration_frames', limit=MAX_EXPRESSION_LENGTH)
        for field in (self.duration, self.duration_frames):
            field.expand = True
            field.tooltip = ('Frames e segundos são sincronizados. Aceita contas: 24*2. '
                'Enter mostra o resultado. O MP4 arredonda frações de frame.')
        self.duration.on_submit = self.edit('duration', normalize=True)
        self.duration_frames.on_submit = self.edit('duration_frames', normalize=True)
        self.timing = ft.Row([self.duration_frames, self.duration], spacing=6)
        self.action = self.field('Ação / descrição', 'action', multiline=True)
        self.audio = self.field('Diálogo', 'audio', multiline=True)
        self.subtitle = self.field('Legenda', 'subtitle', multiline=True, limit=SUBTITLE_LIMIT)
        self.subtitle.tooltip = 'Exibida na parte inferior do animatic e incluída no MP4 durante este quadro.'
        self.notes = self.field('Notas', 'notes', multiline=True)
        self.fit = ft.Dropdown(label='Enquadramento', value='cover', options=[
            ft.DropdownOption('cover', 'Preencher e enquadrar'), ft.DropdownOption('contain', 'Mostrar inteira')],
            on_select=self.fit_changed, **input_style())
        self.fit.expand = True
        self.center = ft.IconButton(icon=ft.Icons.CENTER_FOCUS_STRONG,
            tooltip='Centralizar imagem', width=CONTROL_HEIGHT, height=CONTROL_HEIGHT, on_click=self.reset_crop)
        self.image_button = ft.IconButton(icon=ft.Icons.ADD, width=COMPACT_CONTROL_HEIGHT,
            height=COMPACT_CONTROL_HEIGHT, on_click=self.pick_image)
        self.image_button.tooltip = 'Adicionar imagens ou vídeos'
        self.scene_info = ft.Text(size=TEXT_SMALL, color=MUTED, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
        self.color_button = ft.OutlinedButton('Cor da cena', icon=ft.Icons.PALETTE_OUTLINED,
            height=CONTROL_HEIGHT, on_click=self.pick_color, visible=False)
        self.empty = ft.Text('Selecione um quadro para editar suas propriedades.', color=MUTED, size=TEXT_SMALL)
        self.fit.tooltip = 'Arraste a imagem no quadro para ajustar o enquadramento.'
        self.media_list = NodeMediaList(view)
        self.image_section = CollapsibleSection(view.page, 'Mídias', [self.media_list.content,
            ft.Row([self.fit, self.center], spacing=4)], on_change=self.image_section_changed, actions=(self.image_button,))
        self.script_section = CollapsibleSection(view.page, 'Roteiro',
            [self.subtitle, self.action, self.audio, self.notes], expanded=False,
            on_change=self.script_section_changed)
        self.drawing_count = ft.Text(size=TEXT_SMALL, color=MUTED)
        self.drawing_visibility = ft.TextButton('Mostrar', icon=ft.Icons.LAYERS_OUTLINED,
            height=COMPACT_CONTROL_HEIGHT, on_click=self.toggle_drawing)
        self.drawing_clear = ft.TextButton('Limpar', icon=ft.Icons.DELETE_OUTLINE,
            height=COMPACT_CONTROL_HEIGHT, on_click=lambda e: self.set_drawing(strokes=()))
        self.drawing_section = CollapsibleSection(view.page, 'Desenho', [self.drawing_count,
            ft.Row([self.drawing_visibility, self.drawing_clear], spacing=APP_PADDING)], expanded=False)
        self.fields = ft.Column([self.title, self.color_button, self.timing,
            self.image_section.content, self.script_section.content, self.drawing_section.content], visible=False, spacing=8,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.toggle_button = ft.IconButton(icon=ft.Icons.TUNE, tooltip=view.keymap.describe('Propriedades do quadro ativo', Action.PROPERTIES),
            on_click=self.toggle, width=CONTROL_HEIGHT, height=CONTROL_HEIGHT)
        self.reopen_button = ft.IconButton(icon=ft.Icons.CHEVRON_LEFT, on_click=self.toggle,
            tooltip=view.keymap.describe('Abrir propriedades', Action.PROPERTIES),
            width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT)
        self.reopen_rail = ft.Container(width=COMPACT_CONTROL_HEIGHT, visible=False,
            bgcolor=SURFACE, border=ft.Border.all(1, BORDER), border_radius=RADIUS,
            content=ft.Column([self.reopen_button], spacing=0))
        self.content = ft.Container(width=WORKSPACE_STYLE.inspector_width, padding=PANEL_PADDING, bgcolor=SURFACE,
            border=ft.Border(left=ft.BorderSide(1, BORDER)), content=ft.Column([
                ft.Row([self.heading, ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT, tooltip='Recolher propriedades',
                    on_click=self.toggle, width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT)],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                self.scene_info, self.empty, self.fields], expand=True, scroll=ft.ScrollMode.AUTO, spacing=8,
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
                self.view.field_focus(self.active, key, focused)
                if not focused and self.view.player.opened:
                    self.view.player.sync_inspector()
        return changed

    def sync(self):
        for key in ('title', 'action', 'audio', 'notes', 'subtitle', 'duration', 'duration_frames'):
            getattr(self, key).hint_text = None
        self.image_button.disabled = False
        identifier = self.view.edit_selection.active
        if identifier != self.active:
            self.end_adjust()
            if self.active:
                self.view.workspace.navigation.editing_fields = {item for item in
                    self.view.workspace.navigation.editing_fields if item[0] != self.active}
            self.active = identifier
        frame = next((frame for frame in self.view.board.frames if frame.id == identifier), None)
        self.fields.visible, self.empty.visible = bool(frame), not bool(frame)
        self.scene_info.visible = False
        self.heading.value = 'Quadro ativo'
        if frame:
            self.sync_path()
            is_main = frame.node_type.starts_scene
            self.color_button.visible = is_main
            self.timing.visible = self.audio.visible = frame.node_type.timed
            self.subtitle.visible = frame.node_type.timed
            self.image_section.content.visible = frame.node_type.image
            drawings = property_targets(self.view.board, self.view.edit_selection.ids, 'drawing')
            self.drawing_section.content.visible = bool(drawings)
            count = sum(len(item.drawing.strokes) for item in drawings)
            self.drawing_count.value = f'{count} ' + ('traço' if count == 1 else 'traços')
            visible = bool(drawings) and all(item.drawing.visible for item in drawings)
            self.drawing_visibility.content = 'Ocultar' if visible else 'Mostrar'
            self.drawing_visibility.icon = ft.Icons.VISIBILITY_OFF if visible else ft.Icons.VISIBILITY
            self.drawing_clear.disabled = not count
            index = [item.id for item in self.view.board.frames if item.node_type.timed].index(frame.id)+1 if frame.node_type.timed else 0
            self.heading.value = ('Início de cena' if is_main else f'Quadro {index:02d}'
                if frame.node_type.timed else frame.node_type.label)
            for key in ('title', 'action', 'audio', 'notes', 'subtitle'):
                getattr(self, key).value = getattr(frame, key)
            self.duration.value = duration_text(frame.duration, self.view.board.fps)
            self.duration_frames.value = duration_text(frame.duration, self.view.board.fps, frames=True)
            self.duration.error_text = None
            self.duration_frames.error_text = None
            self.fit.value = frame.image_fit
            self.media_list.sync(frame)
            self.media_list.content.disabled = len(self.view.edit_selection.ids) > 1
            self.image_button.disabled = False
            self.center.disabled = frame.image_fit != 'cover' or not bool(frame.image)
            identifiers = self.view.edit_selection.ids
            if len(identifiers) > 1:
                self.heading.value = f'{len(identifiers)} nodes'
                self.scene_info.value = 'Edição da seleção · campos vazios indicam valores diferentes'
                selected = [item for item in self.view.board.frames if item.id in identifiers]
                self.timing.visible = self.audio.visible = self.subtitle.visible = any(item.node_type.timed for item in selected)
                self.image_section.content.visible = any(item.node_type.image for item in selected)
                self.color_button.visible = any(item.node_type.starts_scene for item in selected)
                self.image_button.disabled = True
                fits = {item.image_fit for item in selected if item.node_type.image}
                self.fit.value = next(iter(fits)) if len(fits) == 1 else None
                self.center.disabled = not any(item.node_type.image and item.image and item.image_fit == 'cover' for item in selected)
                for key in ('title', 'action', 'audio', 'notes', 'subtitle', 'duration'):
                    targets = property_targets(self.view.board, identifiers, key)
                    values = {getattr(item, key) for item in targets}
                    field = getattr(self, key)
                    field.hint_text = 'Vários valores' if len(values) != 1 else None
                    if len(values) != 1:
                        field.value = ''
                    elif key == 'duration':
                        field.value = duration_text(next(iter(values)), self.view.board.fps)
                        self.duration_frames.value = duration_text(next(iter(values)), self.view.board.fps, frames=True)
                    else:
                        field.value = next(iter(values))
                    if key == 'duration' and len(values) != 1:
                        self.duration_frames.value = ''
        self.content.disabled = not self.view.editable() or self.view.player.editing

    def sync_path(self):
        selection = self.view.edit_selection
        text = path_text(self.view.sequences.index, selection.active)
        visible = bool(text) and len(selection.ids) == 1
        changed = (self.scene_info.value, self.scene_info.visible) != (text, visible)
        self.scene_info.value = self.scene_info.tooltip = text
        self.scene_info.visible = visible
        return changed

    def toggle(self, e=None):
        self.opened = not self.opened
        self.content.visible = self.opened
        self.reopen_rail.visible = not self.opened
        if hasattr(self.view, 'properties_splitter'):
            self.view.properties_splitter.content.visible = self.opened
        self.toggle_button.tooltip = self.view.keymap.describe(
            'Recolher propriedades' if self.opened else 'Mostrar propriedades do quadro ativo', Action.PROPERTIES)
        if not self.opened:
            self.end_adjust()
            self.release_field_focus()
        self.view.page.update(self.content, self.toggle_button, self.reopen_rail)
        if hasattr(self.view, 'properties_splitter'):
            self.view.page.update(self.view.properties_splitter.content)
        if hasattr(self.view, 'chrome'):
            self.view.chrome.sync()
            self.view.page.update(self.view.chrome.content)
        self.view.focus_editor()

    def release_field_focus(self, keys=None):
        navigation = self.view.workspace.navigation
        navigation.editing_fields = {item for item in navigation.editing_fields
            if item[0] != self.active or (keys is not None and item[1] not in keys)}

    def image_section_changed(self, expanded):
        if not expanded:
            self.end_adjust()

    def script_section_changed(self, expanded):
        if not expanded:
            self.release_field_focus({'subtitle', 'action', 'audio', 'notes'})
            self.view.focus_editor()

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
            if not identifier or not self.view.editable() or self.view.player.editing:
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
            identifiers = self.view.edit_selection.ids or {identifier}
            if len(identifiers) > 1:
                await apply_properties(self.view, identifiers, {key_name: value},
                    coalesce_key=(tuple(sorted(identifiers)), key))
            else:
                await self.view.set_frame_properties(identifier, coalesce_key=(identifier, key), **{key_name: value})
            if key in ('duration', 'duration_frames') and self.active == identifier:
                other = self.duration_frames if key == 'duration' else self.duration
                current = next(iter(property_targets(self.view.board, identifiers, 'duration')), None)
                if current is None:
                    return
                other.value = duration_text(current.duration, self.view.board.fps, frames=key == 'duration')
                other.error_text = None
                if normalize:
                    field.value = duration_text(current.duration, self.view.board.fps, frames=key == 'duration_frames')
                self.view.page.update(field, other)
        return changed

    async def fit_changed(self, e):
        self.end_adjust()
        await apply_properties(self.view, self.view.edit_selection.ids or {self.active}, {'image_fit': self.fit.value})
        self.sync()
        self.view.page.update(self.content)

    async def reset_crop(self, e):
        self.end_adjust()
        await apply_properties(self.view, self.view.edit_selection.ids or {self.active}, {'crop_x': 0, 'crop_y': 0})

    async def pick_image(self, e):
        if self.active:
            self.end_adjust()
            await self.view.node_media.pick(self.active)

    async def set_drawing(self, **values):
        if not self.view.editable() or self.view.player.editing:
            return
        targets = property_targets(self.view.board, self.view.edit_selection.ids, 'drawing')
        await self.view.set_frames_properties({frame.id: {'drawing': replace(frame.drawing, **values)}
            for frame in targets}, label='Editar desenho')
        self.sync()
        self.view.page.update(self.content)

    async def toggle_drawing(self, e=None):
        targets = property_targets(self.view.board, self.view.edit_selection.ids, 'drawing')
        await self.set_drawing(visible=not all(frame.drawing.visible for frame in targets))

    def pick_color(self, e):
        identifiers = self.view.edit_selection.ids or {self.active}
        frame = next(iter(property_targets(self.view.board, identifiers, 'scene_color')), None)
        if not frame or not frame.node_type.starts_scene or not self.view.editable():
            return
        def apply(color):
            self.view.page.run_task(apply_properties, self.view, identifiers, {'scene_color': color})
        ColorPicker(self.view.page, 'Cor do Node Principal',
            frame.scene_color or load_theme().colors['primary'], apply).open()
