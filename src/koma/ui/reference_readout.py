"""Compact metadata lines; tabular counters retain their measured widths."""
import flet as ft
from koma.exports.reference_overlay import ReferenceTypography, reference_font, reference_rows, style as reference_style
from koma.ui.typography import TEXT_SMALL, FONT_HEADING
from koma.ui.design import APP_PADDING


class ReferenceReadout:
    def __init__(self):
        self.key = None
        self.cells = {}
        self.row = ft.Column(spacing=0, tight=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.rows_key = None
        self.alignment = ft.MainAxisAlignment.START
        self.content = ft.Container(left=APP_PADDING, right=APP_PADDING, top=APP_PADDING,
            padding=ft.Padding.symmetric(horizontal=APP_PADDING), bgcolor=ft.Colors.with_opacity(.7, ft.Colors.BLACK),
            content=self.row, visible=False, ignore_interactions=True,
            clip_behavior=ft.ClipBehavior.HARD_EDGE)
        self.metrics = ReferenceTypography(reference_font(TEXT_SMALL))
        self.layout_key = None
        self.font_size = TEXT_SMALL

    def sync(self, values, fields, options=None, size=None):
        fields = tuple(field for field in fields if values.get(field))
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
            self.alignment = {'Esquerda': ft.MainAxisAlignment.START,
                'Centro': ft.MainAxisAlignment.CENTER, 'Direita': ft.MainAxisAlignment.END}[options['align']]
            self.layout_key = (style_key, size)
        self.cells = {field: self.cells.get(field) or ft.Container(content=ft.Text(size=TEXT_SMALL,
            font_family=FONT_HEADING, weight=ft.FontWeight.W_400,
            style=ft.TextStyle(letter_spacing=0, height=reference_style()['line_height_ratio']), color=ft.Colors.WHITE))
            for field in fields}
        available = max(1, (size or (1280, 720))[0] - 2 * (self.content.left or 0) - APP_PADDING * 2)
        rows, widths, gap = reference_rows([values[field] for field in fields], self.metrics, available)
        rows_key = fields, rows, widths, gap, self.alignment
        if rows_key != self.rows_key:
            self.row.controls = [ft.Row([self.cells[fields[index]] for index in row], spacing=gap,
                tight=True, alignment=self.alignment, vertical_alignment=ft.CrossAxisAlignment.START) for row in rows]
            self.rows_key = rows_key
        for index, (field, cell) in enumerate(self.cells.items()):
            text = values[field]
            cell.content.value = text
            cell.content.size = self.font_size
            if options:
                cell.content.color = options['color']
                cell.content.font_family = FONT_HEADING if options['font'] == 'Archivo' else options['font']
            cell.width = widths[index]
            cell.content.no_wrap = self.metrics.getlength(text) <= available
        self.content.tooltip = ' · '.join(values[field] for field in fields)
        return True
