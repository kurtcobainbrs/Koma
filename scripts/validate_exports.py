"""Gera amostras de integração com Blender real, sem depender do AppAkira."""

import argparse
import asyncio
import json
from pathlib import Path

from PIL import Image, ImageDraw

from koma.documents.images import import_image
from koma.documents.session import DocumentSession
from koma.documents.bundle import destination_stamp
from koma.editor.animatic import Timeline
from koma.editor.models import Storyboard, StoryFrame, StoryLink
from koma.exports.pdf_export import export_pdf
from koma.exports.video_export import frame_counts, prepare_frames
from koma.exports.video_runner import VideoRunner


async def validate(blender, output):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    session = DocumentSession(output / 'data')
    try:
        frames = []
        for index, color in enumerate(('#304E67', '#895F48')):
            source = output / f'source-{index}.png'
            image = Image.new('RGB', (1280, 720), color)
            ImageDraw.Draw(image).rectangle((300, 180, 980, 540), outline='white', width=12)
            image.save(source)
            name, _ = import_image(source, session.store)
            frames.append(StoryFrame(title=f'Quadro {index + 1}', image=name, x=480 * (index + 1), y=0,
                duration=.5 + index * .25, subtitle='Enquadramento e legenda · Koma App',
                action='Ação com acentuação, enquadramento e imagem própria.',
                notes='Texto de validação. ' * (200 if index else 1)))
        main = StoryFrame(kind='main', title='Cena de validação', x=0, y=0)
        board = Storyboard('Validação Koma', (main, *frames),
            (StoryLink(main.id, frames[0].id), StoryLink(frames[0].id, frames[1].id)))
        session.board = board
        session.save(board, output / 'validation.koma', expected_stamp=destination_stamp(output / 'validation.koma'))
        pdf = export_pdf(board, session.store, output / 'validation.pdf')
        prepared = output / 'frames'
        prepared.mkdir(exist_ok=True)
        timeline = Timeline(board, main.id)
        paths = prepare_frames(timeline.frames, session.store, prepared, (1280, 720))
        counts = frame_counts(timeline.frames, 24)
        runner = VideoRunner(output / 'logs')
        video = await runner.run(blender, paths, output / 'validation.mp4', 24, 'HIGH', 1280,
            lambda event: None, frame_durations=counts)
        if video is None:
            raise RuntimeError('A exportação foi cancelada.')
        # Reabre o pacote em outra sessão e compara os dados completos.
        reopened = DocumentSession.open(output / 'validation.koma', output / 'reopen-data')
        try:
            assert reopened.board == board
        finally:
            reopened.close()
        result = {'pdf': str(pdf), 'mp4': str(video), 'fps': 24, 'resolution': [1280, 720],
            'frames': counts, 'total_frames': sum(counts), 'duration_seconds': sum(counts) / 24}
        (output / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False))
    finally:
        session.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--blender', required=True, type=Path)
    parser.add_argument('--output', type=Path, default=Path('build/validation'))
    args = parser.parse_args()
    asyncio.run(validate(args.blender, args.output))
