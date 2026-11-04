"""Atomic storyboard export using the project's production flow and identifiers."""

import json
from dataclasses import replace
from importlib.resources import files
from datetime import date
from pathlib import Path
from threading import Lock
from uuid import uuid4

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, PageBreak, SimpleDocTemplate, Spacer
from reportlab.platypus.doctemplate import LayoutError
from reportlab.pdfbase.ttfonts import TTFError

from koma.editor.sequences import SequenceIndex
from koma.editor.production_numbers import ProductionNumbers
from koma.exports.pdf_layout import StoryboardSheet, paragraph
from koma.exports.pdf_options import PdfOptions, PAGE_MARGIN
from koma.media_filters import selected_filter

FONT_LOCK = Lock()


def print_sequence(board, preferences=None):
    """Use montage order and canonical scene/shot labels, including muted gaps."""
    from koma.exports.sequence import ExportSequence
    sequence = ExportSequence.from_project(board)
    identity = ProductionNumbers(SequenceIndex(board), preferences.get('identity') if preferences else None)
    codes = {frame.id: identity.code(frame.id) for frame in sequence.frames}
    sections = []
    previous = None
    for frame, reference in zip(sequence.frames, sequence.references):
        root = reference.scene
        key = root.id if root else ''
        if not sections or key != previous:
            sections.append((identity.label(root.id) if root else 'Sequência', []))
            previous = key
        sections[-1][1].append(frame)
    return sequence.frames, codes, sections


def register_print_fonts():
    with FONT_LOCK:
        for name, filename in [('StoryboardBody', 'Archivo-Regular.ttf'), ('StoryboardHeading', 'Archivo-SemiBold.ttf')]:
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, str(files('koma').joinpath('assets', 'fonts', filename))))


def export_pdf(board, store, destination: Path, *, preferences=None, options=None):
    try:
        return build_pdf(board, store, destination, preferences=preferences, options=options)
    except (LayoutError, TTFError) as exc:
        raise ValueError(f'Não foi possível montar o PDF: {exc}') from exc


def build_pdf(board, store, destination: Path, *, preferences=None, options=None):
    board.validate()
    options = options or PdfOptions.from_preferences(preferences)
    options = replace(options, filter_matrix=selected_filter(board.media_filter).matrix)
    options.validate()
    geometry = options.geometry(board.frame_format)
    frames, codes, sections = print_sequence(board, preferences)
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
    page_width, page_height = options.page_size
    margin = PAGE_MARGIN
    width, height = geometry.width, geometry.height
    flow, overflow = [], []
    for scene, scene_frames in sections:
        for offset in range(0, len(scene_frames), geometry.capacity):
            sheet = StoryboardSheet(board, scene, scene_frames[offset:offset + geometry.capacity], codes,
                store, palette, width, height, date.today().strftime('%d/%m/%Y'), options)
            if flow:
                flow.append(PageBreak())
            flow.append(sheet)
            overflow.extend(sheet.overflow)
    if overflow:
        flow.extend([PageBreak(), paragraph('Textos completos', heading), Spacer(1, 12)])
        for frame in overflow:
            flow.append(KeepTogether([paragraph(f'{codes[frame.id]} / {frame.title or "Sem título"}', heading),
                                      Spacer(1, 4)]))
            for key, name, value in [('action', 'Ação / descrição', frame.action), ('audio', 'Diálogo / áudio', frame.audio), ('notes', 'Notas', frame.notes)]:
                if getattr(options, key) and value.strip():
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
        document = SimpleDocTemplate(str(temporary), pagesize=options.page_size, leftMargin=margin, rightMargin=margin,
            topMargin=margin, bottomMargin=margin, title=options.title or board.title, author='Koma App')
        document.build(flow, onFirstPage=decorate, onLaterPages=decorate)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination
