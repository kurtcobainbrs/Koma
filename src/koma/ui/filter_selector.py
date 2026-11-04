"""Project-owned filter selection; the interface only edits the document."""
from dataclasses import replace
from koma.media_filters import FILTERS
from koma.ui.choice_input import ChoiceInput
from koma.ui.design import COMPACT_CONTROL_HEIGHT


class FilterSelector:
    def __init__(self, view):
        self.view = view
        self.key = None
        self.input = ChoiceInput('Filtro', view.board.media_filter,
            tuple(FILTERS), labels={key: spec.label for key, spec in FILTERS.items()}, on_change=self.choose)
        # Shared compact menu, without a second label in the main toolbar.
        self.content = self.input.button
        self.content.width = COMPACT_CONTROL_HEIGHT * 6

    async def choose(self, e=None):
        view = self.view
        if not view.editable():
            self.sync()
            return
        key = self.input.value
        if key not in FILTERS:
            return
        if key != view.board.media_filter:
            view.changed(replace(view.board, media_filter=key), label='Alterar filtro')
            await view.persist()

    def sync(self):
        self.input.value = self.view.board.media_filter
        if self.key != self.view.board.media_filter:
            self.key = self.view.board.media_filter
            from koma.ui.media_filter import refresh_media_filters
            refresh_media_filters(self.view)
        self.content.disabled = self.view.references.active
