"""Conversão e validação de duração compartilhadas pelos editores de quadros."""

import math

from koma.editor.models import MIN_DURATION, MAX_DURATION, SUPPORTED_FPS
from koma.expressions import arithmetic_value


def parse_duration(text, fps, *, frames=False):
    if type(fps) is not int or fps not in SUPPORTED_FPS:
        raise ValueError('FPS do projeto inválido.')
    message = (f'Use de {fps * MIN_DURATION:g} a {fps * MAX_DURATION:g} frames.' if frames else
        'Use de 1/60 a 3600 segundos.')
    try:
        value = arithmetic_value(str(text))
        seconds = value / fps if frames else value
        if not math.isfinite(seconds) or not MIN_DURATION <= seconds <= MAX_DURATION:
            raise ValueError()
        return seconds
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f'{message} Aceita contas como 24*2 ou (48+12)/2.') from exc


def duration_text(seconds, fps, *, frames=False):
    return f'{seconds * fps if frames else seconds:.12g}'
