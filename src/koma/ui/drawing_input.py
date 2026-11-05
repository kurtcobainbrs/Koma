"""Pointer streams share drawing commands while owning only their own gesture."""
from koma.ui.event_updates import explicit_updates


class DrawingInput:
    def __init__(self, editor, point, radius, *, temporary_tool):
        self.editor, self.point, self.radius = editor, point, radius
        self.temporary_tool = temporary_tool
        self.reset()

    def reset(self):
        self.origin = self.token = self.tool = None

    def sync(self):
        if self.token is not None and self.token is not self.editor.drag:
            self.reset()

    @explicit_updates
    def down(self, e):
        self.origin = self.point(e)
        self.tool = self.temporary_tool()

    @explicit_updates
    def begin(self, e):
        if self.token is not None and self.token is self.editor.drag:
            return
        point = self.origin if self.origin is not None else self.point(e)
        tool = self.tool if self.origin is not None else self.temporary_tool()
        self.reset()
        if point is not None:
            self.token = self.editor.begin(point, hit_radius=self.radius(), tool=tool)
            self.move(e)

    @explicit_updates
    def move(self, e):
        self.sync()
        if self.token is not None:
            point = self.point(e)
            if point is not None:
                self.editor.move(point)

    @explicit_updates
    async def finish(self, e=None):
        self.sync()
        token = self.token
        if token is not None:
            if e is not None and getattr(e, 'local_position', None) is not None:
                self.move(e)
            self.reset()
            if token is self.editor.drag:
                await self.editor.finish()
        else:
            self.reset()

    @explicit_updates
    async def tap(self, e):
        if self.tool is not None or self.temporary_tool() is not None:
            self.reset()
            return
        self.begin(e)
        await self.finish(e)

    @explicit_updates
    def cancel(self, e=None):
        token = self.token
        self.reset()
        if token is not None and token is self.editor.drag:
            self.editor.cancel()
