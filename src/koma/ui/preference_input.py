"""One field factory for application preferences and staged export options."""
import flet as ft
from koma.ui.color_input import ColorInput
from koma.ui.number_input import NumberInput
from koma.ui.choice_input import ChoiceInput
from koma.ui.path_input import PathInput
from koma.ui.design import input_style
from koma.ui.form_layout import FORM_LAYOUT, form_row


def preference_input(page, field, value, *, on_change, on_submit):
    if field.kind == 'color':
        control = ColorInput(page, field.label, value, validate=field.parse, on_change=on_change, on_submit=on_submit)
    elif field.kind == 'path':
        control = PathInput(page, field.label, value, on_change=on_change, on_submit=on_submit)
    elif field.kind in ('int', 'float') and not field.choices:
        control = NumberInput(page, field.label, value, validate=field.parse,
            minimum=field.minimum, maximum=field.maximum, integer=field.kind == 'int',
            slider=field.slider, on_change=on_change, on_submit=on_submit)
    elif field.kind == 'bool':
        control = ft.Checkbox(label=field.label, value=value,
            visual_density=ft.VisualDensity.COMPACT, on_change=on_change)
    elif field.choices:
        control = ChoiceInput(field.label, value, field.choices, labels=dict(field.choice_labels), on_change=on_change)
    else:
        control = ft.TextField(value=str(value), width=FORM_LAYOUT.text_width,
            on_change=on_change, on_submit=on_submit, **input_style(FORM_LAYOUT.row_height))
    content = control.content if isinstance(control, (ColorInput, NumberInput, ChoiceInput, PathInput)) else control
    if isinstance(control, (ft.TextField, ft.Dropdown)):
        content = form_row(field.label, control)
    return control, content
