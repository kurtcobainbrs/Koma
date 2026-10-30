"""Application-owned byte cache; eviction never touches imported media or documents."""
from collections import OrderedDict

PREVIEW_SIDES = {'Automática': 1280, 'Baixa': 480, 'Média': 720, 'Alta': 1920}


class PreviewCache(OrderedDict):
    def __init__(self, megabytes):
        super().__init__()
        self.limit = megabytes * 1024 * 1024

    def resize(self, megabytes):
        self.limit = megabytes * 1024 * 1024
        self.trim()

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self.move_to_end(key)
        self.trim()

    def trim(self):
        total = sum(len(value) for value in self.values())
        while self and total > self.limit:
            _, value = self.popitem(last=False)
            total -= len(value)
