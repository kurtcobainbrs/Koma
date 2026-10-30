"""Prova reproduzível de importação, pacote portátil, waveform e MP4 com som."""

import argparse
from array import array
import asyncio
import json
import math
from pathlib import Path
import struct
from uuid import uuid4
import wave

from PIL import Image, ImageDraw

from koma.audio_transport import AudioTransport
from koma.documents.audio import import_audio
from koma.documents.images import import_image
from koma.documents.session import DocumentSession
from koma.editor.media_models import AudioTrack, TimelineMarker
from koma.editor.models import Storyboard, StoryFrame, StoryLink
from koma.editor.timeline import Timeline
from koma.exports.video_export import prepare_frames, timeline_frame_counts
from koma.exports.video_runner import VideoRunner
from koma.exports.video_frames import FileFrames


def boxes(data, start=0, end=None):
    end = len(data) if end is None else end
    while start + 8 <= end:
        size, kind = struct.unpack_from('>I4s', data, start)
        header = 8
        if size == 1:
            size = struct.unpack_from('>Q', data, start + 8)[0]
            header = 16
        elif size == 0:
            size = end - start
        if size < header or start + size > end:
            raise ValueError('Estrutura MP4 inválida.')
        yield kind, start + header, start + size
        start += size


def handlers(path):
    data = path.read_bytes()
    result = []
    def visit(start, end):
        for kind, payload, limit in boxes(data, start, end):
            if kind in (b'moov', b'trak', b'mdia'):
                visit(payload, limit)
            elif kind == b'hdlr':
                result.append(data[payload + 8:payload + 12].decode('ascii'))
    visit(0, len(data))
    return result


async def validate(directory, video=False):
    directory.mkdir(parents=True, exist_ok=True)
    report = {'ok': False, 'checks': {}}
    session = DocumentSession(directory / 'data')
    reopened = None
    try:
        source = directory / 'tone.wav'
        rate = 16000
        samples = array('h', (round(5000 * math.sin(2 * math.pi * 440 * index / rate)) for index in range(rate)))
        with wave.open(str(source), 'wb') as output:
            output.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
            output.writeframes(samples.tobytes())
        name, duration, waveform = await asyncio.to_thread(import_audio, source, session.store)
        report['checks']['decode_normalize_waveform'] = {'duration': duration, 'levels': len(waveform.levels)}
        frames = []
        main = StoryFrame(kind='main', title='Cena com áudio', x=0, y=0)
        for index, color in enumerate(('#304E67', '#493357')):
            image = Image.new('RGB', (1280, 720), color)
            ImageDraw.Draw(image).rectangle((300, 180, 980, 540), outline='white', width=10)
            path = directory / f'image-{index}.png'
            image.save(path)
            asset, _ = import_image(path, session.store)
            frames.append(StoryFrame(title=f'Quadro {index+1}', image=asset, duration=.5, x=(index + 1) * 480, y=0))
        track = AudioTrack(asset=name, title='Tom de validação', duration=duration, start=.25, scene_id=main.id)
        board = Storyboard(title='Áudio · Waveform · Marcadores', frames=(main, *frames),
            links=(StoryLink(main.id, frames[0].id), StoryLink(frames[0].id, frames[1].id)),
            audio_tracks=(track,), markers=(TimelineMarker(title='Entrada', position=.25, scene_id=main.id),
                TimelineMarker(title='Corte', position=.75, scene_id=main.id)))
        bundle = session.save(board, directory / 'audio-timeline.koma')
        reopened = DocumentSession.open(bundle, directory / 'portable')
        assert reopened.board == board
        report['checks']['portable_roundtrip'] = 'passed'
        import miniaudio
        transport = AudioTransport(device_factory=lambda **options: miniaudio.PlaybackDevice(backends=[miniaudio.Backend.NULL], **options))
        try:
            timeline = Timeline(reopened.board, main.id)
            transport.update(timeline, reopened.store, True, .5)
            await asyncio.to_thread(lambda: transport.executor.submit(lambda: None).result(timeout=10))
            assert not transport.error, transport.error
        finally:
            await asyncio.to_thread(transport.close)
        report['checks']['native_audio_backend_null'] = 'passed'
        if video:
            target = directory / 'frames'
            target.mkdir(exist_ok=True)
            paths = await asyncio.to_thread(prepare_frames, timeline.frames, reopened.store, target, (1280, 720))
            runner = VideoRunner(directory / 'logs')
            result = await runner.run(FileFrames(tuple(paths), tuple(timeline_frame_counts(timeline, 24))),
                directory / 'audio-timeline.mp4', 24, 'HIGH', 1280, lambda event: None,
                audio_tracks=[dict(path=str((reopened.store.audio / name).resolve()), start=track.start, volume=track.volume)])
            streams = handlers(result)
            assert 'vide' in streams and 'soun' in streams, streams
            report['checks']['real_mp4_video_and_audio'] = streams
        report['ok'] = True
        report['bundle'] = str(bundle)
    finally:
        if reopened:
            reopened.close()
        session.close()
        (directory / 'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, default=Path('build') / f'audio-validation-{uuid4().hex[:8]}')
    parser.add_argument('--video', action='store_true')
    args = parser.parse_args()
    asyncio.run(validate(args.directory.resolve(), video=args.video))
