"""Canvas and animatic share one inspector/document while retaining their UI state."""
import flet as ft
from koma.ui.components import list_surface
from koma.ui.retained_container import retain_children
from koma.ui.design import SURFACE


class WorkModes:
    def __init__(self, view):
        self.view = view
        self.canvas = ft.Container(content=ft.Column([view.workspace.scope.content,
            list_surface([view.board_area])], expand=True, spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH), expand=True, bgcolor=SURFACE)
        self.animatic = ft.Container(content=view.player.surface, expand=True, bgcolor=SURFACE)
        self.center = ft.Stack([self.canvas, self.animatic], expand=True, fit=ft.StackFit.EXPAND)
        self.upper = ft.Row([self.center, view.properties_splitter.content,
            view.properties.content, view.properties.reopen_rail], expand=True, spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH)
        self.editor = ft.Column([self.upper, view.player.layout.splitter.content,
            view.player.layout.timeline], expand=True, spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        view.player.keyboard.content = self.editor
        # KeyboardListener does not implement Flet's layout expansion contract.
        self.content = ft.Container(content=view.player.keyboard, expand=True)
        self.set_visibility(False)

    def set_visibility(self, animatic):
        # Keep the canvas camera mounted. The Animatic surface must be
        # unmounted when inactive so its observers, focus and portals stop.
        self.active_surface = self.animatic if animatic else self.canvas
        self.animatic.visible = animatic
        self.view.player.layout.timeline.visible = animatic
        self.view.player.layout.splitter.content.visible = animatic

    def show(self, animatic, *, update=True, retain_timeline=False):
        view = self.view
        view.focus.cancel()
        view.properties.end_adjust()
        view.properties.release_field_focus()
        view.workspace.navigation.reset_keys()
        view.workspace.navigation.sync(update=False)
        self.set_visibility(animatic)
        view.external_drop.sync()
        if not animatic:
            view.properties.sync()
        view.chrome.sync()
        if update and view.active and not view.closing:
            stable = [view.workspace.node_layer, view.workspace.background]
            if retain_timeline or not animatic:
                stable.extend(block.thumbnail.canvas for block in view.player.strip.blocks.values())
                stable.extend((view.player.preview.content, view.player.drawing_surface.overlay.content))
            with retain_children(*stable):
                view.page.update(self.center, view.properties.content,
                    view.player.layout.timeline, view.player.layout.splitter.content,
                    view.chrome.content, view.chrome.status)

    def focus(self):
        if self.view.player.opened:
            self.view.player.focus_timeline()
        else:
            self.view.workspace.navigation.focus_keyboard()
