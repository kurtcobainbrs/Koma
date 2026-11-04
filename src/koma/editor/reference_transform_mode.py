"""Keyboard transforms reuse reference drag preview, commit and cancellation."""
from types import SimpleNamespace as Data
from koma.ui.event_updates import explicit_updates


class ReferenceTransformMode:
    def __init__(self, workspace):
        self.workspace = workspace
        self.active = False
        self.point = None
        self.waiting = False

    def start(self, *, scale=False):
        ws = self.workspace
        if self.active or ws.gesture or not ws.selection.ids or not ws.view.editable():
            return
        ws.set_pan(False)
        self.waiting = self.point is None
        ws.object_pointer = None
        ws.begin(None, Data(global_position=self.point or Data(x=0, y=0)), resize=scale)
        if ws.gesture is None:
            return
        self.active = True
        ws.gesture['modal'] = True
        ws.sync_modal_input()
        ws.focus()

    @explicit_updates
    def hover(self, e):
        point = getattr(e, 'global_position', None)
        if point is None:
            return
        self.point = point
        ws = self.workspace
        if not self.active or not ws.gesture:
            return
        if self.waiting:
            ws.gesture['pointer'] = (point.x, point.y)
            self.waiting = False
        ws.move(Data(global_position=point))

    async def confirm(self, e=None):
        if not self.active:
            return
        if e is not None:
            self.hover(e)
        self.reset()
        await self.workspace.finish()
        self.workspace.focus()

    def reset(self):
        self.active = self.waiting = False
        self.workspace.sync_modal_input()
