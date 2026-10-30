"""Directory field with the native folder picker and optional direct entry."""
import asyncio
import flet as ft
from koma.paths import initial_directory
from koma.ui.design import input_style
from koma.ui.form_layout import FORM_LAYOUT, form_row


class PathInput:
    def __init__(self, page, label, value, *, on_change, on_submit=None):
        self.page, self.label, self.on_change = page, label, on_change
        self.entry = ft.TextField(value=value, width=FORM_LAYOUT.text_width,
            on_change=on_change, on_submit=on_submit, **input_style(FORM_LAYOUT.row_height))
        self.button = ft.IconButton(ft.Icons.FOLDER_OPEN, tooltip='Escolher pasta', on_click=self.choose,
            width=FORM_LAYOUT.row_height, height=FORM_LAYOUT.row_height)
        self.content = form_row(label, self.entry, self.button)

    @property
    def value(self):
        return self.entry.value

    @value.setter
    def value(self, value):
        self.entry.value = value

    @property
    def error_text(self):
        return self.entry.error_text

    @error_text.setter
    def error_text(self, value):
        self.entry.error_text = value

    async def choose(self, e=None):
        folder = await asyncio.to_thread(initial_directory, self.value)
        selected = await ft.FilePicker().get_directory_path(dialog_title=self.label, initial_directory=folder)
        if selected:
            self.value = selected
            self.on_change(None)
