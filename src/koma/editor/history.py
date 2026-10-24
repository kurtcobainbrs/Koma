"""Histórico por documento em memória; snapshots imutáveis compartilham imagens."""

from time import monotonic


class StoryHistory:
    def __init__(self, limit=100):
        self.limit = limit
        self.past, self.future = [], []
        self.last_key, self.last_time = None, 0

    def record(self, board, key=None):
        now = monotonic()
        if key is None or key != self.last_key or now - self.last_time > 1:
            self.past.append(board)
            del self.past[:-self.limit]
        self.future.clear()
        self.last_key, self.last_time = key, now

    def undo(self, board):
        if not self.past:
            return board
        self.future.append(board)
        self.last_key = None
        return self.past.pop()

    def redo(self, board):
        if not self.future:
            return board
        self.past.append(board)
        self.last_key = None
        return self.future.pop()
