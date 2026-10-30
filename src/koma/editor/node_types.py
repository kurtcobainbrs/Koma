"""Catálogo de tipos e capacidades, sem dependência da interface ou persistência."""

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class NodeType:
    kind: str
    label: str
    header: str
    image: bool = False
    timed: bool = False
    starts_scene: bool = False
    accepts_input: bool = True
    title_prefix: str = ''
    contains_frames: bool = False


NODE_TYPES = MappingProxyType({spec.kind: spec for spec in (
    NodeType('main', 'Início de cena', 'PRINCIPAL', starts_scene=True,
             accepts_input=False, title_prefix='Cena'),
    NodeType('frame', 'Quadro', 'QUADRO', image=True, timed=True),
    NodeType('sequence', 'Sequência', 'SEQUÊNCIA', title_prefix='Sequência', contains_frames=True),
)})


def node_type(kind):
    try:
        return NODE_TYPES[kind]
    except (KeyError, TypeError):
        raise ValueError('Tipo de node inválido.') from None
