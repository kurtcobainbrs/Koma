"""Shared field choices for live reference data and MP4 export."""
import flet as ft
from koma.exports.reference_overlay import REFERENCE_FIELDS


class ReferenceFields:
    def __init__(self, view, *, on_change=None):
        self.view, self.on_change = view, on_change
        self.fields = {key: ft.Checkbox(label=label, value=key in view.preferences.options.reference_fields,
            expand=True, visual_density=ft.VisualDensity.COMPACT, on_change=self.changed)
            for key, label in REFERENCE_FIELDS.items()}
        choices = list(self.fields.values())
        self.content = ft.Column([ft.Row(choices[index:index + 2], spacing=4)
            for index in range(0, len(choices), 2)], spacing=0, tight=True)

    @property
    def selected(self):
        return tuple(key for key, control in self.fields.items() if control.value)

    def changed(self, e=None):
        self.view.preferences.update(reference_fields=self.selected)
        if self.on_change:
            self.on_change()
