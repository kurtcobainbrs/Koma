"""Small staged editor and badge for the link owned by a reference image."""
import flet as ft
from koma.ui.design import dialog, input_style
from koma.ui.typography import TEXT_SMALL

LINK_BADGE_SIZE = 20


def link_badge(actions, identifier):
    async def open_link(e):
        await actions.open_link(identifier)
    return ft.Container(top=3, right=3, visible=False, width=LINK_BADGE_SIZE, height=LINK_BADGE_SIZE,
        bgcolor=ft.Colors.with_opacity(.65, ft.Colors.BLACK), border_radius=3,
        content=ft.IconButton(ft.Icons.PUBLIC, icon_size=13, icon_color=ft.Colors.WHITE,
            width=LINK_BADGE_SIZE, height=LINK_BADGE_SIZE, padding=0, tooltip='Abrir link',
            style=ft.ButtonStyle(animation_duration=0), on_click=open_link))


class ReferenceLinkEditor:
    def __init__(self, canvas):
        self.canvas = canvas
        self.popup = None

    def open(self, e=None):
        canvas, view = self.canvas, self.canvas.view
        if not canvas.active or not view.editable() or canvas.gesture or len(canvas.selection.ids) != 1:
            return
        identifier = next(iter(canvas.selection.ids))
        item = next((item for item in view.board.references if item.id == identifier), None)
        if item is None:
            return
        expected, session = view.board, view.session
        self.field = ft.TextField(value=item.url, hint_text='https://…', autofocus=True, **input_style())
        status = ft.Text(size=TEXT_SMALL, color=ft.Colors.ERROR, visible=False)

        def cancel(e=None):
            view.page.pop_dialog()
            canvas.focus()

        async def confirm(e=None):
            try:
                if view.session is not session:
                    raise ValueError('O projeto mudou. Abra o link novamente.')
                if await canvas.actions.set_link(identifier, self.field.value, expected=expected):
                    cancel()
            except ValueError as exc:
                status.value, status.visible = str(exc), True
                view.page.update(status)
            except OSError:
                status.value, status.visible = 'Não foi possível salvar o link.', True
                view.page.update(status)

        async def remove(e=None):
            self.field.value = ''
            await confirm(e)

        self.popup = dialog(title=ft.Text('Link'), content=ft.Container(width=440,
                content=ft.Column([self.field, status], tight=True, spacing=4)),
            on_confirm=confirm, on_cancel=cancel,
            actions=[ft.TextButton('Remover', on_click=remove, disabled=not item.url),
                ft.TextButton('Cancelar', on_click=cancel), ft.FilledButton('Salvar', on_click=confirm)])
        view.page.show_dialog(self.popup)
