"""Sequence commands reuse the document's history, persistence and node actions."""
from dataclasses import replace
from koma.editor.sequences import SequenceIndex, compose, dissolve, append_to_sequence
from koma.editor.models import StoryFrame
from koma.editor.geometry import next_position


class SequenceActions:
    def __init__(self, view):
        self.view = view
        self.source = self._index = None

    @property
    def index(self):
        if self.source is not self.view.board:
            self.source = self.view.board
            self._index = SequenceIndex(self.source)
        identity = self.view.settings.configuration.values['identity']
        if self._index._production is None or self._index._production.options != identity:
            from koma.editor.production_numbers import ProductionNumbers
            self._index._production = ProductionNumbers(self._index, identity)
        return self._index

    async def create(self, *, spec, position=None):
        view = self.view
        if not view.editable():
            return
        try:
            count = sum(frame.kind == spec.kind for frame in view.board.frames) + 1
            board, identifier = compose(view.board, view.workspace.navigation.selection.ids,
                spec=spec, title=f'{spec.title_prefix} {count:02d}', position=position or view.workspace.scope.next_position())
            if view.workspace.scope.active and identifier not in SequenceIndex(board).parents:
                board = view.workspace.scope.attach_new(board, (identifier,))
            await view.graph.commit(board, label='Criar sequência')
            view.workspace.navigation.select_node(identifier, focus=True)
        except ValueError as exc:
            view.notify(str(exc), 'warning')

    async def toggle(self, identifier):
        await self.view.workspace.scope.show(identifier)

    async def reveal(self, identifiers):
        await self.view.workspace.scope.reveal(identifiers)

    def sync_ancestors(self, identifier):
        controls = []
        for key in self.index.ancestors(identifier):
            card = self.view.cards.get(key)
            if card and card.content.visible:
                card.sync(self.index.nodes[key])
                controls.append(card.content)
        if controls:
            self.view.page.update(*controls)

    async def access(self, identifier):
        await self.view.workspace.scope.show(identifier)

    async def dissolve(self, identifier):
        node = self.index.nodes.get(identifier)
        if self.view.editable() and node and node.sequence:
            await self.view.graph.commit(dissolve(self.view.board, identifier), label='Dissolver sequência')

    async def add_frame(self, identifier):
        view = self.view
        if not view.editable():
            return
        try:
            node = self.index.nodes.get(identifier)
            if not node or node.sequence is None:
                return
            x, y = next_position(tuple(self.index.nodes[key] for key in node.sequence.members))
            frame = StoryFrame(x=x, y=y)
            board = append_to_sequence(replace(view.board, frames=(*view.board.frames, frame)), identifier, (frame.id,))
            await view.graph.commit(board, label='Adicionar quadro à sequência')
            await view.workspace.scope.show(identifier)
            view.workspace.navigation.select_node(frame.id, focus=True)
        except ValueError as exc:
            view.notify(str(exc), 'warning')
