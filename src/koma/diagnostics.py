"""Diagnóstico offline executável sem Python instalado na máquina de validação."""

import asyncio
import json
import platform
import sys
import traceback
from dataclasses import replace
from importlib.resources import files
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageDraw

from koma.documents.images import import_image
from koma.documents.session import DocumentSession
from koma.editor import graph
from koma.editor.history import StoryHistory
from koma.editor.models import Storyboard, StoryFrame, StoryLink
from koma.exports.pdf_export import export_pdf
from koma.exports.subtitles import render_subtitle
from koma.exports.video_export import frame_counts, prepare_frames
from koma.exports.video_runner import VideoRunner


async def check(report_path, blender=None):
    report_path = Path(report_path).resolve()
    work = report_path.parent / f'artifacts-{uuid4().hex[:8]}'
    work.mkdir(parents=True)
    report = {'ok': False, 'frozen': bool(getattr(sys, 'frozen', False)),
              'platform': platform.platform(), 'python': platform.python_version(), 'checks': {},
              'artifacts': str(work)}
    session = None
    try:
        for relative in ('assets/fonts/Archivo-Regular.ttf', 'assets/fonts/Archivo-Medium.ttf',
                         'assets/fonts/Archivo-SemiBold.ttf', 'assets/storyboard-print.json',
                         'assets/storyboard-subtitles.json', 'themes/koma-dark.json', 'exports/blender_probe.py'):
            if not files('koma').joinpath(relative).is_file():
                raise ValueError(f'Recurso ausente: {relative}')
        if report['frozen']:
            client = Path(sys._MEIPASS) / 'desktop/flet/flet.exe'
            if not client.is_file():
                raise ValueError('Cliente Flet ausente do pacote.')
            report['client'] = str(client)
        report['checks']['resources'] = 'passed'
        session = DocumentSession(work / 'data')
        source = work / 'importar.png'
        image = Image.new('RGB', (1280, 720), '#304E67')
        ImageDraw.Draw(image).rectangle((300, 180, 980, 540), outline='white', width=12)
        image.save(source)
        name, _ = import_image(source, session.store)
        main = StoryFrame(kind='main', title='Cena de validação', x=0, y=0)
        a = StoryFrame(image=name, title='Quadro 1', duration=.5, subtitle='Olá · Koma App', x=480, y=0)
        b = replace(a, id=uuid4().hex, title='Quadro 2', duration=.75, x=960)
        board = graph.ordered(Storyboard('Validação Windows', (main, a, b),
            (StoryLink(main.id, a.id), StoryLink(a.id, b.id))))
        history = StoryHistory()
        history.record(board)
        assert history.undo(replace(board, title='Alterado')) == board
        session.board = board
        bundle = session.save(board, work / 'exemplo.koma')
        reopened = DocumentSession.open(bundle, work / 'reopened')
        try:
            assert reopened.board == board
        finally:
            reopened.close()
        report['checks']['document_graph_history_images'] = 'passed'
        export_pdf(board, session.store, work / 'exemplo.pdf')
        if not (work / 'exemplo.pdf').read_bytes().startswith(b'%PDF-'):
            raise ValueError('PDF não foi gerado.')
        report['checks']['pdf'] = 'passed'
        render_subtitle(a.subtitle, (1280, 720)).save(work / 'legenda.png')
        frames = work / 'frames'
        frames.mkdir()
        prepared = prepare_frames((a, b), session.store, frames, (1280, 720))
        report['checks']['framing_subtitles'] = 'passed'
        report['checks']['mp4'] = 'not_requested'
        if blender is not None:
            runner = VideoRunner(work / 'logs')
            result = await runner.run(Path(blender).resolve(), prepared, work / 'exemplo.mp4',
                24, 'HIGH', 1280, lambda event: None, frame_durations=frame_counts((a, b), 24))
            if result is None:
                raise ValueError('MP4 cancelado.')
            report['checks']['mp4'] = 'passed'
        report['ok'] = True
    except Exception:
        report['error'] = traceback.format_exc()
    finally:
        if session is not None:
            session.close()
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if report['ok'] else 1


def run(report_path, blender=None):
    return asyncio.run(check(report_path, blender))
