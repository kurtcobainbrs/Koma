"""Histórico por documento em memória; snapshots imutáveis compartilham imagens."""

from time import monotonic


class StoryHistory:
    def __init__(self, limit=100):
        self.limit = limit
        self.past, self.future = [], []
        self.past_labels, self.future_labels = [], []
        self.last_key, self.last_time = None, 0

    def record(self, board, key=None, label='Editar projeto'):
        now = monotonic()
        if key is None or key != self.last_key or now - self.last_time > 1:
            self.past.append(board)
            self.past_labels.append(label)
            del self.past[:-self.limit]
            del self.past_labels[:-self.limit]
        self.future.clear()
        self.future_labels.clear()
        self.last_key, self.last_time = key, now

    def undo(self, board):
        if not self.past:
            return board
        self.future.append(board)
        self.future_labels.append(self.past_labels.pop() if self.past_labels else 'Editar projeto')
        self.last_key = None
        return self.past.pop()

    def redo(self, board):
        if not self.future:
            return board
        self.past.append(board)
        self.past_labels.append(self.future_labels.pop() if self.future_labels else 'Editar projeto')
        self.last_key = None
        return self.future.pop()

    @property
    def undo_description(self):
        return 'Desfazer ' + self.past_labels[-1].lower() if self.past_labels else 'Desfazer'

    @property
    def redo_description(self):
        return 'Refazer ' + self.future_labels[-1].lower() if self.future_labels else 'Refazer'
