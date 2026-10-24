"""Codificação cancelável com arquivo temporário e publicação após sucesso."""

import asyncio
import json
import math
import os
import tempfile
from pathlib import Path

from koma.exports.processes import BlenderProcess, start_external_process
from koma.exports.encoding import QUALITY_OPTIONS, SIZE_OPTIONS


class VideoRunner(BlenderProcess):
    async def run(self, blender, images, destination, fps, quality, max_size, notify, *, expected_destination_stamp=Ellipsis,
                  frame_durations=None):
        if self.running:
            raise ValueError('Uma compilação já está em andamento.')
        if not blender.is_file() or not os.access(blender, os.X_OK):
            raise ValueError('Configure o Blender nas preferências do Koma.')
        if not images or not math.isfinite(fps) or not 1 <= fps <= 240:
            raise ValueError('Selecione imagens e um FPS entre 1 e 240.')
        if frame_durations is not None and (len(frame_durations) != len(images)
                or any(type(value) is not int or value < 1 for value in frame_durations)):
            raise ValueError('Durações de vídeo inválidas.')
        destination = destination.expanduser().resolve()
        if destination.suffix.lower() != '.mp4':
            raise ValueError('O destino deve terminar com .mp4.')
        if not destination.parent.is_dir():
            raise ValueError('A pasta de destino não existe.')
        if destination in {path.resolve() for path in images}:
            raise ValueError('O destino não pode substituir uma imagem de origem.')
        if quality not in QUALITY_OPTIONS or max_size not in SIZE_OPTIONS:
            raise ValueError('Configurações de vídeo inválidas.')
        source_stamps = {path: (path.stat().st_size, path.stat().st_mtime_ns) for path in images}
        def destination_stamp():
            return (destination.stat().st_size, destination.stat().st_mtime_ns) if destination.exists() else None
        initial_destination = destination_stamp()
        if expected_destination_stamp is not Ellipsis and initial_destination != expected_destination_stamp:
            raise ValueError('O destino mudou após a confirmação; o vídeo existente foi preservado.')
        self.logs.mkdir(parents=True, exist_ok=True)
        self.running, self.cancelled = True, False
        temporary = None
        try:
            temporary = tempfile.TemporaryDirectory(prefix='.koma-video-', dir=destination.parent)
            work = Path(temporary.name).resolve()
            output = work / 'video.mp4'
            request = work / 'request.json'
            payload = dict(images=[str(p.resolve()) for p in images], cache=str(work),
                output=str(output), fps=fps, quality=quality, max_size=max_size)
            if frame_durations is not None:
                payload['durations'] = list(frame_durations)
            request.write_text(json.dumps(payload), encoding='utf-8')
            self.log = self.logs / f'video-{work.name}.log'
            with self.log.open('w', encoding='utf-8') as log:
                self.process = await start_external_process(str(blender), '--background', '--factory-startup',
                    '--disable-autoexec', '--python-exit-code', '1', '--python',
                    str(Path(__file__).with_name('blender_probe.py')), '--', str(request),
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
                    creationflags=0x08000000 if os.name == 'nt' else 0)
                if self.cancelled:
                    await self._stop()
                confirmed = False
                while raw := await self.process.stdout.readline():
                    line = raw.decode('utf-8', errors='replace')
                    log.write(line)
                    log.flush()
                    if line.startswith('KOMA_VIDEO:'):
                        try:
                            notify(json.loads(line.split(':', 1)[1]))
                        except (ValueError, TypeError):
                            pass
                    if line.strip() == 'KOMA_VIDEO_FINISHED':
                        confirmed = True
                code = await self.process.wait()
                if self.cancelled:
                    return None
                if code or not confirmed or not output.is_file() or output.stat().st_size < 32:
                    raise ValueError(f'Falha ao gerar o MP4. Consulte o log: {self.log}')
            if self.cancelled:
                return None
            if destination_stamp() != initial_destination:
                raise ValueError('O destino mudou durante a compilação; o vídeo existente foi preservado.')
            if any((path.stat().st_size, path.stat().st_mtime_ns) != stamp for path, stamp in source_stamps.items()):
                raise ValueError('As imagens mudaram durante a compilação. Tente novamente quando a gravação terminar.')
            os.replace(output, destination)
            return destination
        finally:
            await self._stop()
            self.process = None
            self.running = False
            if temporary:
                temporary.cleanup()


def destination_stamp(path):
    try:
        info = Path(path).stat()
        return info.st_size, info.st_mtime_ns
    except FileNotFoundError:
        return None
