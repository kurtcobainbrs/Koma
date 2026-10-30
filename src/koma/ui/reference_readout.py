"""Fixed-width metadata cells; live text never changes the position of its neighbors."""
import flet as ft
from koma.exports.reference_overlay import ReferenceTypography, reference_font
from koma.ui.typography import TEXT_SMALL, FONT_HEADING
from koma.ui.design import APP_PADDING
from koma.ui.workspace_style import WORKSPACE_STYLE


class ReferenceReadout:
    def __init__(self):
        self.key = None
        self.cells = {}
        self.row = ft.Row(spacing=APP_PADDING, wrap=True, run_spacing=0)
        self.content = ft.Container(left=APP_PADDING, right=APP_PADDING, top=APP_PADDING,
            padding=ft.Padding.symmetric(horizontal=APP_PADDING), bgcolor=ft.Colors.with_opacity(.7, ft.Colors.BLACK),
            content=self.row, visible=False, ignore_interactions=True,
            clip_behavior=ft.ClipBehavior.HARD_EDGE)
        self.metrics = ReferenceTypography(reference_font(TEXT_SMALL))
        self.layout_key = None
        self.font_size = TEXT_SMALL

    def sync(self, values, fields, options=None, size=None):
        style_key = tuple(options.items()) if options else ()
        key = (fields, tuple(values.get(field, '') for field in fields), style_key, size)
        if key == self.key:
            return False
        self.key = key
        self.content.visible = bool(fields and values)
        if not self.content.visible:
            return True
        if options and self.layout_key != (style_key, size):
            from koma.exports.presentation_style import text_font
            height = (size or (1280, 720))[1]
            self.font_size = max(1, round(height * options['size'] / 100))
            self.metrics = ReferenceTypography(text_font(self.font_size, options['font']))
            width = (size or (1280, 720))[0]
            margin = max(0, min(round(height * options['margin'] / 100), (width - 1) // 2, (height - 1) // 2))
            self.content.left = self.content.right = margin
            self.content.top = margin if options['position'] == 'Em cima' else None
            self.content.bottom = margin if options['position'] == 'Embaixo' else None
            self.content.bgcolor = ft.Colors.with_opacity(options['opacity'] / 100, options['background'])
            self.row.alignment = {'Esquerda': ft.MainAxisAlignment.START,
                'Centro': ft.MainAxisAlignment.CENTER, 'Direita': ft.MainAxisAlignment.END}[options['align']]
            self.layout_key = (style_key, size)
        self.cells = {field: self.cells.get(field) or ft.Container(content=ft.Text(size=TEXT_SMALL,
            font_family=FONT_HEADING, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, color=ft.Colors.WHITE))
            for field in fields}
        self.row.controls = list(self.cells.values())
        for field, cell in self.cells.items():
            text = values[field]
            cell.content.value = text
            cell.content.size = self.font_size
            if options:
                cell.content.color = options['color']
                cell.content.font_family = FONT_HEADING if options['font'] == 'Archivo' else options['font']
            # Reserve the widest digit in each numeric cell. Names are bounded
            # in the readout and remain available in the complete tooltip.
            width = min(WORKSPACE_STYLE.reference_cell_maximum, self.metrics.getlength(text))
            cell.width = width + APP_PADDING
        self.content.tooltip = ' · '.join(values[field] for field in fields)
        return True
