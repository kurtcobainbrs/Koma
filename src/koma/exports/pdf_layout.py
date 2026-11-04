"""Proportional print sheets; layout independent from editor controls."""

from xml.sax.saxutils import escape

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Flowable, Paragraph

from koma.editor.framing import placement
from koma.exports.drawings import paint_pdf
from koma.exports.pdf_options import PdfOptions, CARD_GAP, CARD_PADDING, SHEET_HEADER
from koma.media_filters import transform_media
from PIL import Image, ImageOps


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
    def __init__(self, board, scene, frames, codes, store, palette, width, height, date, options=None):
        super().__init__()
        self.width, self.height = width, height
        self.board, self.scene, self.frames, self.codes = board, scene, frames, codes
        self.store, self.palette, self.date = store, palette, date
        self.options = options or PdfOptions()
        self.geometry = self.options.geometry(board.frame_format, width, height)
        self.body = ParagraphStyle('CardBody', fontName='StoryboardBody', fontSize=7,
            leading=9, textColor=palette['muted'])
        self.title = ParagraphStyle('CardTitle', parent=self.body,
            fontName='StoryboardHeading', fontSize=8, leading=10, textColor=palette['ink'])
        self.overflow = []
        self.cards = []
        card_width, card_height = self.geometry.card_width, self.geometry.card_height
        text_width = card_width - 16
        for frame in frames:
            title, clipped = fitted(frame.title.strip() or 'Sem título', self.title, text_width, 10)
            lines = []
            for key, label, value, rows in [('action', 'AÇÃO', frame.action, 2), ('audio', 'ÁUDIO', frame.audio, 1), ('notes', 'NOTAS', frame.notes, 1)]:
                if not getattr(self.options, key):
                    continue
                text, shortened = fitted(f'{label}: {value.strip() or "-"}', self.body, text_width, 9 * rows)
                clipped |= shortened
                lines.append((text, 9 * rows))
            self.cards.append((frame, title, lines, clipped))
            if clipped and self.options.details:
                self.overflow.append(frame)
        self.card_width, self.card_height = card_width, card_height

    def draw_text(self, value, x, top, width, height, style=None):
        text, _ = fitted(value, style or self.body, width, height)
        _, used = text.wrap(width, height)
        text.drawOn(self.canv, x, top - used)

    def draw(self):
        c, p, h, w = self.canv, self.palette, self.height, self.width
        c.setFillColor(p['ink'])
        header_style = ParagraphStyle('SheetTitle', parent=self.title, fontSize=16, leading=18)
        self.draw_text(self.options.title, 0, h, w * .7, 20, header_style)
        self.draw_text(self.options.subtitle, w * .72, h - 3, w * .28, 16)
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
            x = (index % self.geometry.columns) * (self.card_width + CARD_GAP)
            top = h - SHEET_HEADER - (index // self.geometry.columns) * (self.card_height + CARD_GAP)
            self.draw_card(frame, title, lines, clipped, x, top)

    def draw_card(self, frame, title, lines, clipped, x, top):
        c, p = self.canv, self.palette
        width, height = self.card_width, self.card_height
        c.setFillColor(p['paper'])
        c.rect(x, top - height, width, height, stroke=0, fill=1)
        ix, iw = x + CARD_PADDING, width - 2 * CARD_PADDING
        ih = height - self.options.text_height
        iy = top - CARD_PADDING - ih
        c.setFillColor(p['placeholder'])
        vw, vh = self.geometry.image_width, self.geometry.image_height
        vx, vy = ix + (iw - vw) / 2, iy + (ih - vh) / 2
        c.rect(vx, vy, vw, vh, stroke=0, fill=1)
        if frame.image:
            path = self.store.images / frame.image
            transform = frame.active_media.transform
            if self.options.filter_matrix is not None or transform.flip_x or transform.flip_y:
                with Image.open(path) as original:
                    media = ImageOps.exif_transpose(original).convert('RGBA')
                    if transform.flip_x:
                        media = ImageOps.mirror(media)
                    if transform.flip_y:
                        media = ImageOps.flip(media)
                    media.thumbnail((max(1, round(vw * 3)), max(1, round(vh * 3))), Image.Resampling.LANCZOS)
                    reader = ImageReader(transform_media(media, self.options.filter_matrix) if self.options.filter_matrix is not None else media)
            else:
                reader = ImageReader(str(path))
            dw, dh, dx, dy = placement(reader.getSize(), (vw, vh), frame.image_fit, frame.crop_x, frame.crop_y)
            c.saveState()
            path = c.beginPath()
            path.rect(vx, vy, vw, vh)
            c.clipPath(path, stroke=0)
            pose = frame.active_media.transform.at(0)
            c.translate(vx + vw * (.5 + pose.x), vy + vh * (.5 - pose.y))
            c.rotate(-pose.rotation)
            c.scale(pose.scale, pose.scale)
            c.drawImage(reader, dx - vw / 2, vh / 2 - dh - dy, dw, dh, mask='auto')
            c.restoreState()
        else:
            c.setFillColor(p['muted'])
            c.setFont('StoryboardBody', 9)
            c.drawCentredString(ix + iw / 2, iy + ih / 2, 'Sem imagem')
        if self.options.drawing:
            paint_pdf(c, frame.drawing, vx, vy, vw, vh)
        code = self.codes[frame.id]
        badge_width = min(iw, max(25, c.stringWidth(code, 'StoryboardHeading', 8) + 12))
        c.setFillColor(p['accent'])
        c.rect(ix, top - 26, badge_width, 18, stroke=0, fill=1)
        badge_style = ParagraphStyle('ShotCode', parent=self.title, textColor=p['paper'])
        self.draw_text(code, ix + 6, top - 12, badge_width - 12, 10, badge_style)
        c.setStrokeColor(p['rule'])
        c.line(ix, iy - 6, ix + iw, iy - 6)
        c.setStrokeColor(p['accent'])
        c.setLineWidth(1.2)
        c.line(ix, iy - 6, ix + 28, iy - 6)
        title.wrap(iw, 10)
        title.drawOn(c, ix, iy - 20)
        cursor = iy - 22
        for text, reserved in lines:
            _, used = text.wrap(iw, reserved)
            text.drawOn(c, ix, cursor - used)
            cursor -= reserved
        if self.options.duration:
            self.draw_text(f'DURAÇÃO: {duration(frame.duration)}', ix, top - height + 15, iw, 9)
