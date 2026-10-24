"""Exportação atômica em folhas de seis quadros, com detalhes completos ao final."""

import json
from importlib.resources import files
from datetime import date
from pathlib import Path
from threading import Lock
from uuid import uuid4

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, PageBreak, SimpleDocTemplate, Spacer
from reportlab.platypus.doctemplate import LayoutError
from reportlab.pdfbase.ttfonts import TTFError

from koma.editor.graph import ordered
from koma.editor.scenes import principal
from koma.exports.pdf_layout import StoryboardSheet, paragraph

FONT_LOCK = Lock()


def register_print_fonts():
    with FONT_LOCK:
        for name, filename in [('StoryboardBody', 'Archivo-Regular.ttf'), ('StoryboardHeading', 'Archivo-SemiBold.ttf')]:
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, str(files('koma').joinpath('assets', 'fonts', filename))))


def export_pdf(board, store, destination: Path):
    try:
        return build_pdf(board, store, destination)
    except (LayoutError, TTFError) as exc:
        raise ValueError(f'Não foi possível montar o PDF: {exc}') from exc


def build_pdf(board, store, destination: Path):
    board.validate()
    frames = tuple(frame for frame in board.frames if frame.node_type.timed)
    if not frames:
        raise ValueError('Adicione pelo menos um quadro antes de exportar.')
    if destination.suffix.lower() != '.pdf':
        destination = destination.with_suffix('.pdf')
    for frame in frames:
        if frame.image and not (store.images / frame.image).is_file():
            raise ValueError(f'A imagem de “{frame.title or "quadro sem título"}” está indisponível. Troque a imagem antes de exportar.')
    register_print_fonts()
    palette = {name: colors.HexColor(value) for name, value in json.loads(
        files('koma').joinpath('assets', 'storyboard-print.json').read_text(encoding='utf-8')).items()}
    body = ParagraphStyle('StoryBody', fontName='StoryboardBody', fontSize=10, leading=14,
                          textColor=palette['ink'], spaceAfter=5)
    heading = ParagraphStyle('StoryHeading', parent=body, fontName='StoryboardHeading', fontSize=12, leading=16)
    label = ParagraphStyle('StoryLabel', parent=body, fontName='StoryboardHeading', fontSize=9,
                           leading=12, textColor=palette['muted'], spaceBefore=3, spaceAfter=2)
    page_width, page_height = landscape(A4)
    margin = 24
    width, height = page_width - 2 * margin - 12, page_height - 2 * margin - 12
    sequence = tuple(f for f in ordered(board).frames if f.node_type.timed)
    numbers = {frame.id: index for index, frame in enumerate(sequence, 1)}
    sections = {}
    for frame in sequence:
        root = principal(board, frame.id)
        key = root.id if root else ''
        if key not in sections:
            sections[key] = (root.title.strip() or 'Cena' if root else 'Quadros livres' if any(
                f.node_type.starts_scene for f in board.frames) else 'Sequência', [])
        sections[key][1].append(frame)
    flow, overflow = [], []
    for scene, scene_frames in sections.values():
        for offset in range(0, len(scene_frames), 6):
            sheet = StoryboardSheet(board, scene, scene_frames[offset:offset + 6], numbers,
                store, palette, width, height, date.today().strftime('%d/%m/%Y'))
            if flow:
                flow.append(PageBreak())
            flow.append(sheet)
            overflow.extend(sheet.overflow)
    if overflow:
        flow.extend([PageBreak(), paragraph('Textos completos', heading), Spacer(1, 12)])
        for frame in overflow:
            flow.append(KeepTogether([paragraph(f'{numbers[frame.id]:02d} / {frame.title or "Sem título"}', heading),
                                      Spacer(1, 4)]))
            for name, value in [('Ação / descrição', frame.action), ('Diálogo / áudio', frame.audio), ('Notas', frame.notes)]:
                if value.strip():
                    flow.extend([paragraph(name, label), paragraph(value, body)])
            flow.append(Spacer(1, 12))

    def decorate(canvas, document):
        canvas.saveState()
        canvas.setFillColor(palette['background'])
        canvas.rect(0, 0, page_width, page_height, stroke=0, fill=1)
        canvas.setFillColor(palette['muted'])
        canvas.setFont('StoryboardBody', 7)
        canvas.drawString(margin + 6, 12, board.title.strip() or 'Storyboard')
        canvas.drawRightString(page_width - margin - 6, 12, f'{document.page:02d}')
        canvas.restoreState()

    temporary = destination.with_name(f'.{uuid4().hex}.pdf')
    try:
        document = SimpleDocTemplate(str(temporary), pagesize=landscape(A4), leftMargin=margin, rightMargin=margin,
            topMargin=margin, bottomMargin=margin, title=board.title, author='Koma App')
        document.build(flow, onFirstPage=decorate, onLaterPages=decorate)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination
