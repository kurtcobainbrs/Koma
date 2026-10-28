"""Project-wide settings, separate from the active node inspector."""

from dataclasses import replace

import flet as ft

from koma.editor.models import SUPPORTED_FPS
from koma.editor.frame_format import FrameFormat, FORMAT_PRESETS
from koma.ui.design import dialog, input_style


class ProjectProperties:
    def __init__(self, view):
        self.view = view
        self.fps = ft.Dropdown(label='FPS', value=str(view.board.fps),
            options=[ft.DropdownOption(str(value)) for value in SUPPORTED_FPS],
            tooltip='Alterar o FPS mantém a duração dos quadros em segundos.', **input_style())
        self.formats = {str(index): value for index, (_, value) in enumerate(FORMAT_PRESETS)}
        self.preset = ft.Dropdown(label='Formato', options=[
            *[ft.DropdownOption(str(index), label) for index, (label, _) in enumerate(FORMAT_PRESETS)],
            ft.DropdownOption('custom', 'Personalizado')], on_select=self.preset_changed, **input_style())
        self.ratio = ft.TextField(label='Proporção', max_length=32,
            counter=ft.Container(width=0, height=0),
            tooltip='16:9, 9:16, 1:1 ou uma proporção livre, como 2.39:1. Enter aplica as alterações.',
            **input_style())
        self.width = ft.TextField(label='Largura (px)', expand=True, max_length=5,
            counter=ft.Container(width=0, height=0), on_change=self.dimensions_changed, **input_style())
        self.height = ft.TextField(label='Altura (px)', expand=True, max_length=5,
            counter=ft.Container(width=0, height=0), on_change=self.dimensions_changed, **input_style())
        for field in (self.width, self.height):
            field.tooltip = 'Dimensão em pixels: número par entre 64 e 8192.'

    def sync(self):
        self.fps.value = str(self.view.board.fps)
        format = self.view.board.frame_format
        self.width.value, self.height.value = str(format.width), str(format.height)
        self.width.error_text = self.height.error_text = None
        self.preset.value = next((key for key, value in self.formats.items() if value == format), 'custom')
        self.ratio.value = format.ratio_label
        self.ratio.error_text = None

    def dimensions_changed(self, e=None):
        self.preset.value = 'custom'
        self.width.error_text = self.height.error_text = None
        try:
            format = self.read_format()
            self.ratio.value = format.ratio_label
            self.ratio.error_text = None
        except ValueError:
            pass  # Incomplete input is validated on Apply.
        self.view.page.update(self.preset, self.ratio, self.width, self.height)

    def read_format(self):
        try:
            format = FrameFormat(int(self.width.value or ''), int(self.height.value or ''))
        except ValueError:
            raise ValueError('Informe largura e altura como números inteiros.') from None
        format.validate()
        return format

    def chosen_format(self, format=None):
        format = format or self.read_format()
        ratio = (self.ratio.value or '').strip()
        return format if ratio == format.ratio_label else format.with_ratio(ratio)

    def preset_changed(self, e=None):
        format = self.formats.get(self.preset.value)
        if format:
            self.width.value, self.height.value = str(format.width), str(format.height)
            self.width.error_text = self.height.error_text = None
            self.ratio.value = format.ratio_label
            self.ratio.error_text = None
            self.view.page.update(self.width, self.height, self.ratio)

    def open(self, e=None):
        if not self.view.editable():
            return
        self.sync()
        self.view.page.show_dialog(dialog(title=ft.Text('Projeto'), on_confirm=self.apply,
            content=ft.Column([self.preset, self.ratio, ft.Row([self.width, self.height]), self.fps],
                width=320, tight=True, spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
            actions=[ft.TextButton('Cancelar', on_click=lambda e: self.view.page.pop_dialog()),
                ft.FilledButton('Aplicar', on_click=self.apply)]))

    async def apply(self, e=None):
        view = self.view
        if not view.editable():
            return
        try:
            format = self.read_format()
        except (TypeError, ValueError) as exc:
            self.width.error_text = str(exc)
            view.page.update(self.width)
            return
        try:
            format = self.chosen_format(format)
        except ValueError as exc:
            self.ratio.error_text = str(exc)
            view.page.update(self.ratio)
            return
        try:
            board = replace(view.board, fps=int(self.fps.value), frame_format=format)
            board.validate()
        except (TypeError, ValueError) as exc:
            self.fps.error_text = str(exc)
            view.page.update(self.fps)
            return
        view.properties.end_adjust()
        view.changed(board)
        view.refresh()
        view.page.pop_dialog()
        view.page.update(view.content)
        await view.persist()

    async def fps_changed(self, e=None):
        view = self.view
        if not view.editable():
            return
        try:
            board = replace(view.board, fps=int(self.fps.value))
            board.validate()
        except (TypeError, ValueError):
            self.sync()
            view.page.update(self.fps)
            return
        view.changed(board)
        view.refresh()
        view.page.update(view.content)
        await view.persist()
