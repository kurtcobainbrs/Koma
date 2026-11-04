"""Validated print options and proportional layout shared by preview and PDF."""
from dataclasses import dataclass
from math import floor
from reportlab.lib.pagesizes import A4, A3, LETTER, landscape, portrait

PAPERS = {'A4': A4, 'A3': A3, 'Carta': LETTER}
ORIENTATIONS = {'Horizontal': landscape, 'Vertical': portrait}
ROW_MODES = {'Automático': 0, '1': 1, '2': 2, '3': 3, '4': 4}
MAX_COLUMNS = 4
PAGE_MARGIN = 24
FRAME_PADDING = 6
SHEET_HEADER = 84
CARD_GAP = 12
CARD_PADDING = 8
MAX_AUTO_ROWS = 4


@dataclass(frozen=True)
class PdfOptions:
    title: str = 'KOMA STORYBOARD'
    subtitle: str = 'SEQUÊNCIA VISUAL'
    paper: str = 'A4'
    orientation: str = 'Horizontal'
    columns: int = 3
    rows: int = 0
    filter_matrix: tuple | None = None
    action: bool = True
    audio: bool = True
    notes: bool = True
    duration: bool = True
    drawing: bool = True
    details: bool = True

    @classmethod
    def from_preferences(cls, preferences=None):
        section = preferences.get('pdf', {}) if preferences else {}
        values = {key: section[key] for key in cls.__dataclass_fields__ if key in section and key not in ('rows', 'filter_matrix')}
        if section.get('rows', 'Automático') not in ROW_MODES:
            raise ValueError('Escolha as linhas do PDF.')
        values['rows'] = ROW_MODES[section.get('rows', 'Automático')]
        result = cls(**values)
        result.validate()
        return result

    def validate(self):
        if self.paper not in PAPERS or self.orientation not in ORIENTATIONS:
            raise ValueError('Escolha o tamanho e a orientação da página.')
        if type(self.columns) is not int or not 1 <= self.columns <= MAX_COLUMNS or type(self.rows) is not int or not 0 <= self.rows <= MAX_AUTO_ROWS:
            raise ValueError('Use de 1 a 4 colunas e até 4 linhas.')
        for key in ('title', 'subtitle'):
            if not isinstance(getattr(self, key), str) or len(getattr(self, key)) > 256:
                raise ValueError('Use até 256 caracteres no cabeçalho.')
        for key in ('action', 'audio', 'notes', 'duration', 'drawing', 'details'):
            if type(getattr(self, key)) is not bool:
                raise ValueError('Escolha quais informações incluir no PDF.')

    @property
    def page_size(self):
        return ORIENTATIONS[self.orientation](PAPERS[self.paper])

    @property
    def text_height(self):
        return 35 + 18 * self.action + 9 * self.audio + 9 * self.notes + 12 * self.duration

    def geometry(self, frame_format, width=None, height=None):
        self.validate()
        page_width, page_height = self.page_size
        width = page_width - 2 * (PAGE_MARGIN + FRAME_PADDING) if width is None else width
        height = page_height - 2 * (PAGE_MARGIN + FRAME_PADDING) if height is None else height
        card_width = (width - CARD_GAP * (self.columns - 1)) / self.columns
        available = height - SHEET_HEADER
        preferred = (card_width - 2 * CARD_PADDING) / frame_format.aspect_ratio + self.text_height
        rows = self.rows or max(1, min(MAX_AUTO_ROWS, floor((available + CARD_GAP) / (preferred + CARD_GAP))))
        card_height = (available - CARD_GAP * (rows - 1)) / rows
        if card_height <= self.text_height + CARD_PADDING:
            raise ValueError('Pouco espaço para as imagens. Reduza as linhas ou use uma página maior.')
        image_width, image_height = frame_format.fit(card_width - 2 * CARD_PADDING, card_height - self.text_height)
        return SheetGeometry(width, height, self.columns, rows, card_width, card_height, image_width, image_height)


@dataclass(frozen=True)
class SheetGeometry:
    width: float
    height: float
    columns: int
    rows: int
    card_width: float
    card_height: float
    image_width: float
    image_height: float

    @property
    def capacity(self):
        return self.columns * self.rows


PDF_DEFAULTS = PdfOptions()
