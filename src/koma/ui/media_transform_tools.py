"""Compact controls for the active media and its local-time keyframes."""
import flet as ft
from dataclasses import replace
from koma.editor.media_animation import MediaPose, INTERPOLATIONS, MAX_TRANSLATION, MIN_SCALE, MAX_SCALE, MAX_ROTATION
from koma.expressions import arithmetic_value
from koma.ui.design import COMPACT_CONTROL_HEIGHT, APP_PADDING, BORDER, MUTED
from koma.ui.choice_input import ChoiceInput
from koma.ui.event_updates import explicit_updates
from koma.ui.scrub_number import ScrubNumber
from koma.ui.workspace_style import WORKSPACE_STYLE
from koma.ui.typography import TEXT_BODY, TEXT_SMALL, FONT_HEADING


class MediaTransformTools:
    def __init__(self, editor):
        self.editor = editor
        self.focused = False
        self.field_key = None
        self.field_owner = None
        self.field_text = {}
        self.value_drag = None
        self.toggle = self.button(ft.Icons.CHEVRON_LEFT, 'Mostrar transformação', lambda e: editor.activate())
        self.tools = {key: self.button(icon, label, lambda e, value=key: editor.choose_tool(value))
            for key, icon, label in (('move', ft.Icons.OPEN_WITH, 'Mover · G'),
                ('scale', ft.Icons.OPEN_IN_FULL, 'Escalonar · S'), ('rotate', ft.Icons.ROTATE_RIGHT, 'Girar · R'))}
        specs = (('x', 'X (%)', -MAX_TRANSLATION * 100, MAX_TRANSLATION * 100, .1),
            ('y', 'Y (%)', -MAX_TRANSLATION * 100, MAX_TRANSLATION * 100, .1),
            ('scale', 'Escala (%)', MIN_SCALE * 100, MAX_SCALE * 100, .2),
            ('rotation', 'Rotação (°)', -MAX_ROTATION, MAX_ROTATION, .2))
        self.scrubs = {key: ScrubNumber(editor.view.page, label=label, minimum=low, maximum=high,
            sensitivity=sensitivity, on_begin=self.begin_value,
            on_preview=lambda value, channel=key: self.preview_value(channel, value), on_commit=self.finish_value,
            on_cancel=self.cancel_value, on_submit=self.apply, on_focus=self.focus, on_blur=self.blur)
            for key, label, low, high, sensitivity in specs}
        self.fields = {key: scrub.entry for key, scrub in self.scrubs.items()}
        self.key = self.button(ft.Icons.DIAMOND_OUTLINED, 'Gravar keyframe · I', lambda e: editor.set_key())
        self.delete_key = self.button(ft.Icons.DELETE_OUTLINE, 'Excluir keyframe atual · Alt+I',
            lambda e: editor.set_key(remove_only=True))
        self.auto = self.button(ft.Icons.RADIO_BUTTON_UNCHECKED, 'Auto Key', self.toggle_auto)
        self.previous = self.button(ft.Icons.FAST_REWIND, 'Keyframe anterior', lambda e: editor.jump(-1))
        self.next = self.button(ft.Icons.FAST_FORWARD, 'Próximo keyframe', lambda e: editor.jump(1))
        self.interpolation = ChoiceInput('Interpolação', editor.interpolation, tuple(INTERPOLATIONS),
            labels=INTERPOLATIONS, on_change=self.change_interpolation, icon=ft.Icons.LINEAR_SCALE)
        self.animation = ft.Row([self.auto, self.key, self.delete_key, self.interpolation.button], tight=True, spacing=0)
        fields = [ft.Row([ft.Text(label, size=TEXT_BODY, expand=True), self.scrubs[key].content], spacing=APP_PADDING)
            for key, label, *_ in specs]
        self.temporary_hint = ft.Text('Prévia não gravada', size=TEXT_SMALL, color=MUTED, visible=False)
        self.detail = ft.Column([ft.Row(list(self.tools.values()), spacing=0), *fields,
            self.temporary_hint], tight=True, spacing=APP_PADDING)
        self.panel = ft.Container(width=WORKSPACE_STYLE.media_panel_width, padding=APP_PADDING * 2,
            border=ft.Border(left=ft.BorderSide(1, BORDER)), visible=False,
            content=ft.Column([ft.Row([ft.Text('Transformação', size=TEXT_BODY, font_family=FONT_HEADING, expand=True),
                self.button(ft.Icons.CHEVRON_RIGHT, 'Recolher transformação', lambda e: editor.activate(False))]), self.detail],
                spacing=APP_PADDING, scroll=ft.ScrollMode.AUTO))
        self.content = self.toggle

    def button(self, icon, tooltip, action):
        return ft.IconButton(icon, tooltip=tooltip, on_click=action,
            width=COMPACT_CONTROL_HEIGHT, height=COMPACT_CONTROL_HEIGHT, icon_size=18)

    def focus(self, e=None):
        self.focused = True
        self.editor.player.pause_for_edit()

    def blur(self, e=None):
        self.focused = False

    def cancel_fields(self):
        self.focused = False
        self.field_key = None
        for scrub in self.scrubs.values():
            scrub.set_editing(False)
        self.sync()
        self.editor.view.page.update(self.panel)

    def begin_value(self):
        if self.editor.player.editing or not self.editor.view.editable():
            return False
        self.editor.player.pause_for_edit()
        self.value_drag = (self.editor.owner(), self.editor.effective_pose(), self.editor.temporary)
        self.editor.player.set_gesture_locked(True)
        return True

    def preview_value(self, channel, value):
        if self.value_drag and self.editor.owner() == self.value_drag[0]:
            pose = replace(self.value_drag[1], **{channel: value / (1 if channel == 'rotation' else 100)})
            self.editor.show_temporary(pose)

    async def finish_value(self, value):
        drag, self.value_drag = self.value_drag, None
        if drag and self.editor.owner() == drag[0]:
            await self.editor.apply_pose(self.editor.effective_pose())
        self.editor.player.set_gesture_locked(False)

    def cancel_value(self):
        drag, self.value_drag = self.value_drag, None
        if drag:
            self.editor.temporary = drag[2]
            self.editor.cancel()

    async def apply(self, e=None):
        frame = self.editor.frame()
        if not frame or not frame.active_media:
            return
        try:
            owner = (self.editor.view.session, frame.id, frame.active_media.id, self.editor.time())
            if owner != self.field_owner:
                raise ValueError('O quadro ou tempo mudou. Edite os valores novamente.')
            original = self.editor.effective_pose()
            values = {key: (getattr(original, key) if field.value == self.field_text.get(key)
                else arithmetic_value(field.value or '') / (1 if key == 'rotation' else 100))
                for key, field in self.fields.items()}
            pose = MediaPose(**values)
            self.focused = False
            return await self.editor.apply_pose(pose) is not False
        except ValueError as exc:
            self.editor.view.notify(str(exc), 'warning')
            return False

    @explicit_updates
    def toggle_auto(self, e=None):
        self.editor.auto_key = not self.editor.auto_key
        self.sync()
        self.editor.view.page.update(self.animation)

    async def change_interpolation(self, e=None):
        self.editor.interpolation = self.interpolation.value
        frame = self.editor.frame()
        if not frame or not frame.active_media:
            return
        transform = frame.active_media.transform
        keys = tuple(replace(key, interpolation=self.editor.interpolation) if abs(key.time - self.editor.time()) < 1e-8 else key
            for key in transform.keyframes)
        await self.editor.commit(frame, replace(transform, keyframes=keys), label='Alterar interpolação')

    def sync(self):
        editor, frame = self.editor, self.editor.frame()
        self.panel.visible = editor.panel_open
        if hasattr(editor.player, 'layout'):
            editor.player.layout.media_splitter.content.visible = editor.panel_open
            editor.player.layout.media_reopen.visible = not editor.panel_open
        self.toggle.selected = editor.panel_open
        self.toggle.style = ft.ButtonStyle(animation_duration=0, bgcolor=ft.Colors.PRIMARY_CONTAINER if editor.panel_open else None)
        self.toggle.disabled = not frame or not frame.active_media
        for key, button in self.tools.items():
            button.selected = editor.enabled and key == editor.tool
            button.style = ft.ButtonStyle(animation_duration=0, bgcolor=ft.Colors.PRIMARY_CONTAINER if button.selected else None)
        self.auto.icon = ft.Icons.RADIO_BUTTON_CHECKED if editor.auto_key else ft.Icons.RADIO_BUTTON_UNCHECKED
        self.auto.icon_color = ft.Colors.ERROR if editor.auto_key else MUTED
        self.auto.tooltip = 'Auto Key · ' + ('Ligado' if editor.auto_key else 'Desligado')
        transform = frame.active_media.transform if frame and frame.active_media else None
        time = editor.time()
        pose = editor.effective_pose()
        self.temporary_hint.visible = editor.temporary is not None
        field_key = (pose, time, id(frame))
        if not self.focused and field_key != self.field_key:
            for key, field in self.fields.items():
                field.value = f'{getattr(pose, key) * (1 if key == "rotation" else 100):.4g}'
                self.field_text[key] = field.value
                self.scrubs[key].sync()
            self.field_owner = (editor.view.session, frame.id, frame.active_media.id, time) if frame and frame.active_media else None
            self.field_key = field_key
        current = next((key for key in transform.keyframes if abs(key.time - time) < 1e-8), None) if transform else None
        self.key.icon = ft.Icons.DIAMOND if current else ft.Icons.DIAMOND_OUTLINED
        self.key.tooltip = ('Atualizar' if current else 'Gravar') + ' keyframe · I'
        self.delete_key.disabled = current is None
        self.interpolation.button.disabled = current is None
        self.interpolation.value = current.interpolation if current else editor.interpolation
        keys = transform.keyframes if transform else ()
        self.previous.disabled = not any(key.time < (frame.duration if editor.player.playing else time) for key in keys)
        self.next.disabled = not any((editor.player.playing or key.time > time) and key.time < frame.duration for key in keys)
