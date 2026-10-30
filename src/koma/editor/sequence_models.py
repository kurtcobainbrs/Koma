"""Node-owned composition metadata; member nodes remain the sole data owners."""
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class SequenceState:
    members: tuple[str, ...] = ()
    collapsed: bool = True
    entry: str | None = None
    exit: str | None = None

    def validate(self):
        if type(self.collapsed) is not bool or not isinstance(self.members, tuple):
            raise ValueError('Estado de sequência inválido.')
        if any(not isinstance(key, str) or not re.fullmatch(r'[a-f0-9]{32}', key) for key in self.members):
            raise ValueError('Membro de sequência inválido.')
        if len(set(self.members)) != len(self.members):
            raise ValueError('Há quadros repetidos na sequência.')
        if any(key is not None and key not in self.members for key in (self.entry, self.exit)):
            raise ValueError('Entrada e Saída devem apontar para membros da sequência.')

    def remap(self, identifiers):
        return SequenceState(tuple(identifiers[key] for key in self.members), self.collapsed,
            identifiers.get(self.entry), identifiers.get(self.exit))

    @classmethod
    def from_document(cls, value, limit):
        if value is None:
            return None
        if (not isinstance(value, dict) or set(value) not in ({'members', 'collapsed'}, {'members', 'collapsed', 'entry', 'exit'})
                or not isinstance(value['members'], list) or len(value['members']) > limit):
            raise ValueError('Composição de sequência inválida.')
        state = cls(tuple(value['members']), value['collapsed'], value.get('entry'), value.get('exit'))
        state.validate()
        return state
