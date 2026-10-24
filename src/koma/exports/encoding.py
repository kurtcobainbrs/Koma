"""Padrões de codificação compartilhados pela fila e pela ferramenta de vídeo."""

from dataclasses import dataclass


QUALITY_OPTIONS = {'HIGH': 'Alta', 'MEDIUM': 'Média', 'LOW': 'Baixa'}
SIZE_OPTIONS = {0: 'Original', 1920: '1920 px', 1280: '1280 px'}


@dataclass(frozen=True)
class VideoEncoding:
    quality: str = 'HIGH'
    max_size: int = 1920


DEFAULT_ENCODING = VideoEncoding()


def video_progress(event):
    total = max(1, event.get('total', 1))
    done = event.get('done', 0)
    encoding = event.get('phase') == 'Codificando MP4'
    return min(1.0, max(0.0, (0.5 if encoding else 0.0) + 0.5 * done / total))
