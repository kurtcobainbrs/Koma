"""Superfície da janela para projetos; imagens continuam no canvas existente."""

from koma.documents.file_drop import project_drop_path
from koma.ui import drop_runtime
from koma.ui.drop_controls import ImageDropSurface
from koma.documents.audio import AUDIO_EXTENSIONS
from pathlib import Path


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
            if not isinstance(e.files, list) or not e.files or any(not isinstance(path, str) or not path for path in e.files):
                raise ValueError('Lista de arquivos inválida.')
            audio = [path for path in e.files if Path(path).suffix.lower().lstrip('.') in AUDIO_EXTENSIONS]
            if audio:
                if len(e.files) != 1:
                    raise ValueError('Solte um arquivo de áudio por vez.')
                player = app.view.player
                if not player.opened:
                    player.open()
                if player.opened:
                    await player.media.import_path(audio[0])
                else:
                    app.view.notify('Crie ou selecione uma cena com quadros para receber o áudio.', 'warning')
                return
            path = project_drop_path(e.files)
            if path is not None:
                await app.open_project(path)
        except (OSError, ValueError, RuntimeError) as exc:
            app.view.notify(f'Não foi possível abrir: {exc}', 'error')
