"""Owned reference images, independent from narrative nodes and their timing."""
from dataclasses import dataclass, field
from uuid import uuid4
import math
import re

MAX_REFERENCES = 500
MIN_REFERENCE_SIZE = 16
MAX_REFERENCE_SIZE = 20000
MAX_REFERENCE_POSITION = 100000
REFERENCE_GAP = 24


@dataclass(frozen=True)
class ReferenceImage:
    id: str = field(default_factory=lambda: uuid4().hex)
    asset: str = ''
    title: str = ''
    x: float = 0
    y: float = 0
    width: float = 320
    height: float = 180

    def validate(self):
        if not isinstance(self.id, str) or not re.fullmatch(r'[a-f0-9]{32}', self.id):
            raise ValueError('Identificador de referência inválido.')
        if not isinstance(self.asset, str) or not re.fullmatch(r'[a-f0-9]{32}\.png', self.asset):
            raise ValueError('Imagem de referência inválida.')
        if not isinstance(self.title, str) or len(self.title) > 200:
            raise ValueError('Nome de referência inválido.')
        for value, low, high in ((self.x, -MAX_REFERENCE_POSITION, MAX_REFERENCE_POSITION),
                (self.y, -MAX_REFERENCE_POSITION, MAX_REFERENCE_POSITION),
                (self.width, MIN_REFERENCE_SIZE, MAX_REFERENCE_SIZE),
                (self.height, MIN_REFERENCE_SIZE, MAX_REFERENCE_SIZE)):
            if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError('Posição ou tamanho da referência inválidos.')
