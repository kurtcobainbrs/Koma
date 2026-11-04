"""Non-destructive media transforms shared by display and export."""
from dataclasses import dataclass

LUMA = (.299, .587, .114)
GRAYSCALE_MATRIX = (*LUMA, 0., 0., *LUMA, 0., 0., *LUMA, 0., 0., 0., 0., 0., 1., 0.)


@dataclass(frozen=True)
class FilterSpec:
    label: str
    matrix: tuple | None = None


FILTERS = {'none': FilterSpec('Sem filtro'), 'grayscale': FilterSpec('Preto e branco', GRAYSCALE_MATRIX)}


def selected_filter(key='none'):
    if not isinstance(key, str) or key not in FILTERS:
        raise ValueError('Escolha um filtro da lista.')
    return FILTERS[key]


def filter_media(image, key='none'):
    return transform_media(image, selected_filter(key).matrix)


def transform_media(image, matrix):
    if matrix is None:
        return image
    rgb = tuple(matrix[i] for row in (0, 5, 10) for i in (row, row + 1, row + 2, row + 4))
    result = image.convert('RGB').convert('RGB', rgb).convert('RGBA')
    if 'A' in image.getbands():
        result.putalpha(image.getchannel('A'))
    return result


def grayscale(image):
    """Return neutral RGB with the original alpha; never modify the source."""
    return transform_media(image, GRAYSCALE_MATRIX)
