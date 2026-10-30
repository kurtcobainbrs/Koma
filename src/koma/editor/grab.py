"""Movimento modal pelo atalho G; reutiliza o mesmo comando de arraste e histórico."""

from types import SimpleNamespace
from koma.editor.shortcuts import Action


class GrabMove:
    def __init__(self, workspace):
        self.workspace = workspace
        self.active = False
        self.pointer = None
        self.waiting_pointer = False

    def start(self, e=None):
        ws, nav = self.workspace, self.workspace.navigation
        if self.active or ws.drag or not ws.view.editable() or nav.editing_fields or not nav.selection.ids:
            return
        ws.cancel_camera_transition()
        if nav.effective_mode != 'select':
            nav.set_mode('select')
        identifier = nav.selected
        if identifier is None:
            return
        self.waiting_pointer = self.pointer is None
        point = self.pointer or SimpleNamespace(x=0, y=0)
        ws.begin_drag(identifier, SimpleNamespace(global_position=point), update=False)
        self.active = ws.drag is not None
        nav.sync()
        confirm, cancel = ws.view.keymap.label(Action.CONFIRM), ws.view.keymap.label(Action.CANCEL)
        ws.view.notify(f'Mover: clique{" ou " + confirm if confirm else ""} confirma. '
            f'Botão direito{" ou " + cancel if cancel else ""} cancela.')

    def hover(self, e):
        point = getattr(e, 'global_position', None)
        if point is None:
            return
        self.pointer = point
        ws = self.workspace
        if not self.active or ws.drag is None:
            return
        if self.waiting_pointer:
            ws.drag.pointer_x, ws.drag.pointer_y = point.x, point.y
            self.waiting_pointer = False
        ws.update_drag(ws.drag.identifier, e)

    async def confirm(self, e=None):
        ws = self.workspace
        if not self.active or ws.drag is None:
            return
        if e is not None:
            self.hover(e)
        identifier = ws.drag.identifier
        self.active = False
        await ws.end_drag(identifier)
        ws.navigation.focus_keyboard()

    def cancel(self, e=None, *, update=True):
        ws = self.workspace
        if not self.active:
            return
        self.active = self.waiting_pointer = False
        if ws.drag:
            ws.cancel_drag(ws.drag.identifier, update=update)
        if update:
            ws.view.notify('Movimento cancelado.')
