"""Folhas de apresentação com seis quadros; geometria independente da interface."""

from xml.sax.saxutils import escape

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Flowable, Paragraph

from koma.editor.framing import placement


def paragraph(value, style):
    text = ''.join(c for c in value if c >= ' ' or c in '\n\t')
    return Paragraph(escape(text).replace('\n', '<br/>'), style)


def fitted(value, style, width, height):
    result = paragraph(value, style)
    if result.wrap(width, height)[1] <= height:
        return result, False
    low, high = 0, len(value)
    while low < high:
        middle = (low + high + 1) // 2
        if paragraph(value[:middle].rstrip() + '…', style).wrap(width, height)[1] <= height:
            low = middle
        else:
            high = middle - 1
    return paragraph(value[:low].rstrip() + '…', style), True


def duration(seconds):
    minutes, remainder = divmod(seconds, 60)
    return f'{int(minutes):02d}:{remainder:04.1f}'


class StoryboardSheet(Flowable):
    def __init__(self, board, scene, frames, numbers, store, palette, width, height, date):
        super().__init__()
        self.width, self.height = width, height
        self.board, self.scene, self.frames, self.numbers = board, scene, frames, numbers
        self.store, self.palette, self.date = store, palette, date
        self.body = ParagraphStyle('CardBody', fontName='StoryboardBody', fontSize=7,
            leading=9, textColor=palette['muted'])
        self.title = ParagraphStyle('CardTitle', parent=self.body,
            fontName='StoryboardHeading', fontSize=8, leading=10, textColor=palette['ink'])
        self.overflow = []
        self.cards = []
        card_width = (width - 24) / 3
        card_height = (height - 96) / 2
        text_width = card_width - 16
        for frame in frames:
            title, clipped = fitted(frame.title.strip() or 'Sem título', self.title, text_width, 10)
            lines = []
            for label, value, rows in [('AÇÃO', frame.action, 2), ('ÁUDIO', frame.audio, 1), ('NOTAS', frame.notes, 1)]:
                text, shortened = fitted(f'{label}: {value.strip() or "-"}', self.body, text_width, 9 * rows)
                clipped |= shortened
                lines.append((text, 9 * rows))
            self.cards.append((frame, title, lines, clipped))
            if clipped:
                self.overflow.append(frame)
        self.card_width, self.card_height = card_width, card_height

    def draw_text(self, value, x, top, width, height, style=None):
        text, _ = fitted(value, style or self.body, width, height)
        _, used = text.wrap(width, height)
        text.drawOn(self.canv, x, top - used)

    def draw(self):
        c, p, h, w = self.canv, self.palette, self.height, self.width
        c.setFillColor(p['accent'])
        c.setFont('StoryboardHeading', 16)
        c.drawString(0, h - 15, 'KOMA')
        c.setFillColor(p['ink'])
        c.drawString(57, h - 15, 'STORYBOARD')
        c.setFont('StoryboardBody', 8)
        c.setFillColor(p['muted'])
        c.drawRightString(w, h - 13, 'SEQUÊNCIA VISUAL')
        box_y, box_h = h - 71, 36
        main_w = w * .43
        c.setFillColor(p['title_background'])
        c.roundRect(0, box_y, main_w, box_h, 3, stroke=0, fill=1)
        light = ParagraphStyle('HeaderLight', parent=self.title, fontSize=10, leading=12, textColor=p['paper'])
        self.draw_text(self.board.title.strip() or 'Storyboard', 10, box_y + 28, main_w - 20, 12, light)
        scene_style = ParagraphStyle('SceneLight', parent=self.body, textColor=p['paper'])
        self.draw_text(self.scene or 'Sequência', 10, box_y + 12, main_w - 20, 9, scene_style)
        meta_w = (w - main_w - 24) / 3
        metadata = [('DATA', self.date), ('QUADROS', str(len(self.frames))),
                    ('DURAÇÃO', duration(sum(f.duration for f in self.frames)))]
        for index, (label, value) in enumerate(metadata):
            x = main_w + 8 + index * (meta_w + 8)
            c.setFillColor(p['paper'])
            c.roundRect(x, box_y, meta_w, box_h, 3, stroke=0, fill=1)
            self.draw_text(label, x + 10, box_y + 28, meta_w - 20, 10, self.title)
            self.draw_text(value, x + 10, box_y + 14, meta_w - 20, 9)
        for index, (frame, title, lines, clipped) in enumerate(self.cards):
            x = (index % 3) * (self.card_width + 12)
            top = h - 84 - (index // 3) * (self.card_height + 12)
            self.draw_card(frame, title, lines, clipped, x, top)

    def draw_card(self, frame, title, lines, clipped, x, top):
        c, p = self.canv, self.palette
        width, height = self.card_width, self.card_height
        c.setFillColor(p['paper'])
        c.rect(x, top - height, width, height, stroke=0, fill=1)
        ix, iw = x + 8, width - 16
        ih = iw * 9 / 16
        iy = top - 8 - ih
        c.setFillColor(p['placeholder'])
        c.rect(ix, iy, iw, ih, stroke=0, fill=1)
        if frame.image:
            reader = ImageReader(str(self.store.images / frame.image))
            dw, dh, dx, dy = placement(reader.getSize(), (iw, ih), frame.image_fit, frame.crop_x, frame.crop_y)
            c.saveState()
            path = c.beginPath()
            path.rect(ix, iy, iw, ih)
            c.clipPath(path, stroke=0)
            c.drawImage(reader, ix + dx, iy + ih - dh - dy, dw, dh, mask='auto')
            c.restoreState()
        else:
            c.setFillColor(p['muted'])
            c.setFont('StoryboardBody', 9)
            c.drawCentredString(ix + iw / 2, iy + ih / 2, 'Sem imagem')
        c.setFillColor(p['accent'])
        c.rect(ix, top - 28, 25, 20, stroke=0, fill=1)
        c.setFillColor(p['paper'])
        c.setFont('StoryboardHeading', 10)
        c.drawCentredString(ix + 12.5, top - 22, f'{self.numbers[frame.id]:02d}')
        c.setStrokeColor(p['rule'])
        c.line(ix, iy - 6, ix + iw, iy - 6)
        c.setStrokeColor(p['accent'])
        c.setLineWidth(1.2)
        c.line(ix, iy - 6, ix + 28, iy - 6)
        title.wrap(iw, 10)
        title.drawOn(c, ix, iy - 20)
        cursor = iy - 25
        for text, reserved in lines:
            _, used = text.wrap(iw, reserved)
            text.drawOn(c, ix, cursor - used)
            cursor -= reserved
        self.draw_text(f'DURAÇÃO: {duration(frame.duration)}', ix, top - height + 15, iw, 9)
        if clipped:
            c.setFillColor(p['muted'])
            c.setFont('StoryboardBody', 6)
            c.drawRightString(ix + iw, top - height + 6, 'Texto completo nos detalhes')
