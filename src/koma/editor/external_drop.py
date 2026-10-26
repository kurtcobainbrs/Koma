"""Adaptador do evento Flutter para o comando transacional de importação."""

import math
from koma.documents.file_drop import project_drop_path

from koma.ui import drop_runtime
from koma.ui.drop_controls import ImageDropNode, ImageDropScene, ImageDropSurface


class ExternalImageDrop:
    def __init__(self, view):
        self.view = view
        self.control = None

    def scene(self, content):
        return ImageDropScene(content=content) if drop_runtime.enabled() else content

    def node(self, content, identifier):
        return ImageDropNode(content=content, node_id=identifier) if drop_runtime.enabled() else content

    def surface(self, content):
        if not drop_runtime.enabled():
            return content
        self.control = ImageDropSurface(content=content, expand=True, on_dropped=self.handle)
        return self.control

    def sync(self):
        if self.control is not None:
            self.control.session_token = self.view.session.directory.name
            self.control.origin_x = float(self.view.workspace.extent.origin_x)
            self.control.origin_y = float(self.view.workspace.extent.origin_y)
            self.control.disabled = not self.view.editable()

    async def handle(self, e):
        view = self.view
        if (not view.editable() or e.session_token != view.session.directory.name or
                not view.can_accept_drop()):
            if view.active and not view.closing:
                view.notify('Soltura cancelada: o documento mudou ou está ocupado.', 'warning')
            return
        if type(e.protocol) is not int or e.protocol != drop_runtime.PROTOCOL:
            view.notify('Não foi possível interpretar a soltura do arquivo.', 'warning')
            return
        try:
            path = project_drop_path(e.files)
            if path is not None:
                # Compatibilidade com clientes anteriores: o projeto nunca vira imagem.
                opener = getattr(view, 'open_project_path', None)
                if opener is not None:
                    await opener(path)
                else:
                    await view.files.change_document(path=path)
                return
        except (ValueError, OSError, RuntimeError) as exc:
            view.notify(f'Não foi possível abrir: {exc}', 'error')
            return
        values = (e.scene_x, e.scene_y, e.origin_x, e.origin_y)
        if (type(e.protocol) is not int or e.protocol != drop_runtime.PROTOCOL or
                (e.node_id is not None and not isinstance(e.node_id, str)) or
                any(type(n) not in (int, float) or
                not math.isfinite(n) for n in values) or not isinstance(e.files, list) or
                any(not isinstance(path, str) or not path for path in e.files)):
            view.notify('Não foi possível interpretar a soltura da imagem.', 'warning')
            return
        # O Flutter escolheu o widget atingido usando a árvore renderizada.
        # Nunca substituir por seleção ativa se o destino sumir.
        await view.image_input.drop(e.files,
            (e.scene_x - e.origin_x, e.scene_y - e.origin_y), e.node_id)
