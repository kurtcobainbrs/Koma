"""Superfície da janela para projetos; imagens continuam no canvas existente."""

from koma.documents.file_drop import project_drop_path
from koma.ui import drop_runtime
from koma.ui.drop_controls import ImageDropSurface


class ProjectDrop:
    def __init__(self, application):
        self.application = application
        self.control = None

    def surface(self, content):
        if not drop_runtime.enabled():
            return content
        self.control = ImageDropSurface(content=content, documents_only=True, expand=True, on_dropped=self.handle)
        self.sync()
        return self.control

    def sync(self):
        if self.control is not None:
            app = self.application
            previous = (self.control.session_token, self.control.disabled)
            self.control.session_token = app.view.session.directory.name
            self.control.disabled = (app.transitioning or app.closing_attempt or app.view.closing
                or any(view.busy for view in app.views))
            return previous != (self.control.session_token, self.control.disabled)
        return False

    async def handle(self, e):
        app = self.application
        if (type(e.protocol) is not int or e.protocol != drop_runtime.PROTOCOL
                or e.session_token != app.view.session.directory.name
                or app.transitioning or app.closing_attempt or any(view.busy for view in app.views)
                or app.view.closing):
            return
        try:
            path = project_drop_path(e.files)
            if path is not None:
                await app.open_project(path)
        except (OSError, ValueError, RuntimeError) as exc:
            app.view.notify(f'Não foi possível abrir: {exc}', 'error')
