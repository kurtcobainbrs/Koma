"""Exclusive edit ownership; commands act only on an explicitly selected target."""
from dataclasses import dataclass
from collections.abc import Awaitable, Callable


@dataclass(frozen=True)
class SelectionActions:
    clear: Callable[[], bool]
    remove: Callable[[], Awaitable]
    publish: Callable[[], None]


class EditSelection:
    def __init__(self):
        self.actions = {}
        self.owner = None

    def register(self, owner, *, clear, remove, publish):
        self.actions[owner] = SelectionActions(clear, remove, publish)

    def claim(self, owner):
        for target, actions in self.actions.items():
            if target is not owner and actions.clear():
                actions.publish()
        self.owner = owner

    async def remove(self):
        actions = self.actions.get(self.owner)
        if actions:
            await actions.remove()
