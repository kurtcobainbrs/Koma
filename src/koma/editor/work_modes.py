"""Canvas and animatic share one inspector/document while retaining their UI state."""
import flet as ft
from koma.ui.components import list_surface
from koma.ui.retained_container import retain_children
from koma.ui.design import SURFACE
from koma.editor.shortcuts import Action


class WorkModes:
    def execute(self, action):
        actions = {Action.MODE_CANVAS: self.show_canvas,
            Action.MODE_ANIMATIC: self.view.player.open,
            Action.MODE_REFS: self.show_references}
        handler = actions.get(action)
        if handler is None:
            return False
        if self.view.editable() and not self.view.player.editing:
            if (action == Action.MODE_CANVAS and self.active_surface is self.canvas
                    or action == Action.MODE_ANIMATIC and self.view.player.opened
                    or action == Action.MODE_REFS and self.view.references.active):
                return True
            handler()
        return True

    def __init__(self, view):
        self.view = view
        self.canvas = ft.Container(content=ft.Column([view.workspace.scope.content,
            list_surface([view.board_area])], expand=True, spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH), expand=True, bgcolor=SURFACE)
        self.animatic = ft.Container(content=view.player.surface, expand=True, bgcolor=SURFACE)
        self.references = ft.Container(content=view.references.content, expand=True, visible=False, bgcolor=SURFACE)
        self.center = ft.Stack([self.canvas, self.animatic, self.references], expand=True, fit=ft.StackFit.EXPAND)
        self.inspector = ft.Row([view.properties_splitter.content,
            view.properties.content, view.properties.reopen_rail], spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH)
        self.upper = ft.Row([self.center, self.inspector], expand=True, spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH)
        self.editor = ft.Column([self.upper, view.player.layout.splitter.content,
            view.player.layout.timeline], expand=True, spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        view.player.keyboard.content = self.editor
        # KeyboardListener does not implement Flet's layout expansion contract.
        self.content = ft.Container(content=view.player.keyboard, expand=True)
        self.set_visibility(False)

    def set_visibility(self, animatic):
        self.view.references.active = False
        self.view.references.suspend_camera()
        self.references.visible = False
        self.canvas.visible = True
        self.inspector.visible = True
        # Keep the canvas camera mounted. The Animatic surface must be
        # unmounted when inactive so its observers, focus and portals stop.
        self.active_surface = self.animatic if animatic else self.canvas
        self.animatic.visible = animatic
        self.view.player.layout.timeline.visible = animatic
        self.view.player.layout.splitter.content.visible = animatic

    def show(self, animatic, *, update=True, retain_timeline=False):
        view = self.view
        if view.references.gesture:
            view.references.cancel()
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
                view.page.update(self.upper,
                    view.player.layout.timeline, view.player.layout.splitter.content,
                    view.chrome.content, view.chrome.status)

    def show_references(self, e=None):
        view = self.view
        if not view.editable():
            return
        if view.player.opened:
            view.player.close()
        view.workspace.cancel_gestures()
        view.properties.release_field_focus()
        view.references.active = True
        self.inspector.visible = False
        view.references.modifiers.clear()
        view.references.configure()
        view.references.sync()
        self.canvas.visible = True
        self.animatic.visible = False
        self.references.visible = True
        self.active_surface = self.references
        view.player.layout.timeline.visible = False
        view.player.layout.splitter.content.visible = False
        view.chrome.sync()
        view.external_drop.sync()
        with retain_children(view.workspace.node_layer, view.workspace.background,
                *(card.content for card in view.references.cards.values())):
            view.page.update(self.upper, view.player.layout.timeline,
                view.player.layout.splitter.content, view.chrome.content, view.chrome.status)
        view.references.focus()
        view.references.restore()

    def show_canvas(self, e=None):
        if self.view.player.opened:
            self.view.player.close()
        else:
            self.show(False)
            self.focus()

    def focus(self):
        if self.view.references.active:
            self.view.references.focus()
        elif self.view.player.opened:
            self.view.player.focus_timeline()
        else:
            self.view.workspace.navigation.focus_keyboard()
