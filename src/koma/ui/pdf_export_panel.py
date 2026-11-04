"""Compact staged print controls with a shared-geometry, media-free preview."""
import flet as ft
import flet.canvas as cv
from koma.exports.pdf_options import PdfOptions, SHEET_HEADER, CARD_GAP, CARD_PADDING, PAGE_MARGIN, FRAME_PADDING
from koma.media_filters import selected_filter
from koma.preference_catalog import CATEGORIES
from koma.ui.preference_input import preference_input
from koma.ui.design import dialog, APP_PADDING, BORDER, MUTED
from koma.ui.form_layout import FORM_LAYOUT
from koma.ui.typography import TEXT_SMALL
from koma.ui.event_updates import explicit_updates


PDF_CATEGORY = next(category for category in CATEGORIES if category.key == 'pdf')


class PdfExportPanel:
    def __init__(self, view):
        self.view, self.board, self.session = view, view.board, view.session
        self.controls = {}
        rows, toggles = [], []
        for field in PDF_CATEGORY.fields:
            control, content = preference_input(view.page, field,
                view.settings.configuration.values['pdf'][field.key], on_change=self.changed, on_submit=self.confirm)
            self.controls[field.key] = control
            if field.kind == 'bool':
                toggles.append(ft.Container(content=content, expand=True))
            else:
                rows.append(content)
        rows.extend(ft.Row(toggles[i:i + 2], spacing=APP_PADDING) for i in range(0, len(toggles), 2))
        self.remember = ft.Checkbox(label='Usar como padrão', value=False, visual_density=ft.VisualDensity.COMPACT)
        self.status = ft.Text(size=TEXT_SMALL, color=ft.Colors.ERROR, visible=False)
        self.diagram = cv.Canvas(width=220, height=190)
        self.summary = ft.Text(size=TEXT_SMALL, color=MUTED)
        self.preview = ft.Column([self.diagram, self.summary], spacing=APP_PADDING, tight=True)
        self.fields = ft.Column(rows, spacing=FORM_LAYOUT.spacing, tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.body = ft.Container(width=700, content=ft.Column([
            ft.Row([ft.Container(expand=True, content=self.fields),
                ft.VerticalDivider(width=1, color=BORDER), self.preview], spacing=APP_PADDING * 2,
                vertical_alignment=ft.CrossAxisAlignment.START), self.remember, self.status],
            tight=True, spacing=APP_PADDING, scroll=ft.ScrollMode.AUTO))
        self.popup = dialog(title=ft.Text('Exportar PDF'), content=self.body,
            on_confirm=self.confirm, on_cancel=self.cancel,
            actions=[ft.TextButton('Cancelar', on_click=self.cancel), ft.FilledButton('Exportar', on_click=self.confirm)])
        self.render_preview()

    def preferences(self):
        values = self.view.settings.configuration.editable()
        values['pdf'] = {field.key: field.parse(self.controls[field.key].value) for field in PDF_CATEGORY.fields}
        return values

    def open(self):
        self.view.player.pause_for_edit()
        self.view.page.show_dialog(self.popup)

    @explicit_updates
    def changed(self, e=None):
        self.render_preview()
        self.view.page.update(self.preview, self.status)

    def render_preview(self):
        try:
            values = self.preferences()
            options = PdfOptions.from_preferences(values)
            geometry = options.geometry(self.board.frame_format)
        except ValueError as exc:
            self.status.value, self.status.visible = str(exc), True
            return
        self.status.visible = False
        pw, ph = options.page_size
        scale = min(self.diagram.width / pw, self.diagram.height / ph)
        inset = PAGE_MARGIN + FRAME_PADDING
        shapes = [cv.Rect(0, 0, pw * scale, ph * scale, paint=ft.Paint(color='#FFFFFF'))]
        for index in range(geometry.capacity):
            x = inset + (index % geometry.columns) * (geometry.card_width + CARD_GAP)
            y = inset + SHEET_HEADER + (index // geometry.columns) * (geometry.card_height + CARD_GAP)
            shapes.append(cv.Rect(x * scale, y * scale, geometry.card_width * scale,
                geometry.card_height * scale, paint=ft.Paint(color='#E4E4E4')))
            shapes.append(cv.Rect((x + (geometry.card_width - geometry.image_width) / 2) * scale,
                (y + CARD_PADDING + (geometry.card_height - options.text_height - geometry.image_height) / 2) * scale,
                geometry.image_width * scale, geometry.image_height * scale, paint=ft.Paint(color='#838383')))
        self.diagram.shapes = shapes
        self.summary.value = (f'{geometry.columns} × {geometry.rows} · {geometry.capacity} por página\n'
            f'{self.board.frame_format.ratio_label} · {selected_filter(self.board.media_filter).label}')

    async def confirm(self, e=None):
        try:
            values = self.preferences()
            options = PdfOptions.from_preferences(values)
            options.geometry(self.board.frame_format)
            if self.view.board is not self.board or self.view.session is not self.session:
                raise ValueError('O projeto mudou. Abra a exportação novamente.')
            if self.remember.value:
                await self.view.settings.configuration.commit(values)
                if self.view.board is not self.board or self.view.session is not self.session:
                    raise ValueError('O projeto mudou. Abra a exportação novamente.')
            self.view.page.pop_dialog()
            await self.view.export_pdf_file(options=options, preferences=values)
        except (ValueError, OSError) as exc:
            self.status.value, self.status.visible = str(exc), True
            self.view.page.update(self.status)

    def cancel(self, e=None):
        self.view.page.pop_dialog()
        self.view.focus_editor()
