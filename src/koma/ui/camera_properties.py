"""Staged camera metadata editing; one node-owned transaction for a selection."""
import flet as ft
from koma.editor.camera_models import CAMERA_PRESETS, CameraMotion, MAX_CAMERA_NOTE
from koma.editor.batch_properties import property_targets
from koma.ui.design import dialog, input_style, COMPACT_CONTROL_HEIGHT


class CameraProperties:
    def __init__(self, view):
        self.view = view
        self.content = ft.OutlinedButton('Definir movimento…', icon=ft.Icons.VIDEOCAM_OUTLINED,
            height=COMPACT_CONTROL_HEIGHT, on_click=self.open)

    def sync(self):
        targets = property_targets(self.view.board, self.view.edit_selection.ids, 'camera')
        cameras = {frame.camera for frame in targets}
        self.content.disabled = not targets or not self.view.editable()
        self.content.content = (CAMERA_PRESETS[next(iter(cameras)).preset].label if len(cameras) == 1
            else 'Vários movimentos' if cameras else 'Definir movimento…')

    def open(self, e=None):
        view = self.view
        if not view.editable() or view.player.editing:
            return
        targets = property_targets(view.board, view.edit_selection.ids, 'camera')
        if not targets:
            return
        board, session = view.board, view.session
        identifiers = tuple(frame.id for frame in targets)
        cameras = {frame.camera for frame in targets}
        camera = targets[0].camera
        preset = ft.Dropdown(label='Movimento', value=camera.preset if len(cameras) == 1 else None,
            options=[ft.DropdownOption(key, spec.label) for key, spec in CAMERA_PRESETS.items()], **input_style())
        note = ft.TextField(label='Nota', value=camera.note if len(cameras) == 1 else '', max_length=MAX_CAMERA_NOTE,
            counter=ft.Container(width=0, height=0), **input_style())
        visible = ft.Checkbox(label='Mostrar indicação', value=all(frame.camera.visible for frame in targets))
        async def confirm(e=None):
            try:
                changed = CameraMotion(preset.value, note.value or '', bool(visible.value))
                changed.validate()
                if view.board is not board or view.session is not session:
                    raise ValueError('O projeto mudou. Abra a edição de câmera novamente.')
                view.page.pop_dialog()
                await view.set_frames_properties({key: {'camera': changed} for key in identifiers}, label='Definir câmera')
                self.sync()
                view.page.update(self.content)
                view.focus_editor()
            except ValueError as exc:
                view.notify(str(exc), 'warning')
        def cancel(e=None):
            view.page.pop_dialog()
            view.focus_editor()
        view.page.show_dialog(dialog(title=ft.Text('Câmera'),
            content=ft.Container(width=360, content=ft.Column([preset, note, visible], tight=True, spacing=8)),
            on_confirm=confirm, on_cancel=cancel,
            actions=[ft.TextButton('Cancelar', on_click=cancel), ft.FilledButton('Aplicar', on_click=confirm)]))
