"""One validated image format shared by the document, previews and exports."""

from dataclasses import dataclass
from math import gcd
from fractions import Fraction
import re

MIN_DIMENSION = 64
MAX_DIMENSION = 8192
MAX_PIXELS = 33_554_432
PREVIEW_MAX_SIDE = 1280


@dataclass(frozen=True)
class FrameFormat:
    width: int = 1920
    height: int = 1080

    def validate(self):
        if any(type(value) is not int or not MIN_DIMENSION <= value <= MAX_DIMENSION
               or value % 2 for value in self.size) or self.width * self.height > MAX_PIXELS:
            raise ValueError('Use dimensões pares de 64 a 8192 px, com até 32 megapixels.')

    @property
    def size(self):
        return self.width, self.height

    @property
    def aspect_ratio(self):
        return self.width / self.height

    @property
    def ratio_label(self):
        divisor = gcd(self.width, self.height)
        return f'{self.width // divisor}:{self.height // divisor}'

    def fit(self, width, height):
        scale = min(width / self.width, height / self.height)
        return self.width * scale, self.height * scale

    def preview_size(self):
        scale = min(1, PREVIEW_MAX_SIDE / max(self.size))
        return max(1, round(self.width * scale)), max(1, round(self.height * scale))

    def with_ratio(self, text):
        parts = re.split(r'[:x×/]', text.strip().lower().replace(',', '.'))
        if len(parts) != 2 or any(not re.fullmatch(r'\d+(?:\.\d+)?', part.strip()) for part in parts):
            raise ValueError('Informe uma proporção como 16:9, 9:16 ou 2.39:1.')
        left, right = (Fraction(part.strip()) for part in parts)
        if left <= 0 or right <= 0:
            raise ValueError('Os dois valores da proporção devem ser maiores que zero.')
        ratio = left / right
        width, height = ratio.numerator, ratio.denominator
        # An even multiplier preserves the exact ratio and encoder compatibility.
        minimum = (MIN_DIMENSION + min(width, height) - 1) // min(width, height)
        multiplier = max(minimum, round(max(self.size) / max(width, height)))
        multiplier += multiplier % 2
        result = FrameFormat(width * multiplier, height * multiplier)
        result.validate()
        return result


FORMAT_PRESETS = (
    ('Horizontal · 16:9', FrameFormat()),
    ('Vertical · 9:16', FrameFormat(1080, 1920)),
    ('Quadrado · 1:1', FrameFormat(1080, 1080)),
    ('Clássico · 4:3', FrameFormat(1440, 1080)),
)
