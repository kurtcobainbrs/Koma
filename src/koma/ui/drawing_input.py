"""Pointer streams share drawing commands while owning only their own gesture."""


class DrawingInput:
    def __init__(self, editor, point, radius, *, tool=None):
        self.editor, self.point, self.radius, self.tool = editor, point, radius, tool
        self.origin = self.token = None

    def reset(self):
        self.origin = self.token = None

    def sync(self):
        if self.token is not None and self.token is not self.editor.drag:
            self.reset()

    def down(self, e):
        self.origin = self.point(e)

    def begin(self, e):
        if self.token is not None and self.token is self.editor.drag:
            return
        point = self.origin if self.origin is not None else self.point(e)
        self.reset()
        if point is not None:
            self.token = self.editor.begin(point, hit_radius=self.radius(), tool=self.tool)
            self.move(e)

    def move(self, e):
        self.sync()
        if self.token is not None:
            point = self.point(e)
            if point is not None:
                self.editor.move(point)

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

    async def tap(self, e):
        self.begin(e)
        await self.finish(e)

    def cancel(self, e=None):
        token = self.token
        self.reset()
        if token is not None and token is self.editor.drag:
            self.editor.cancel()
