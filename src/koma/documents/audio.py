"""Importação de áudio em PCM portátil e cache regenerável de waveform."""

from array import array
from dataclasses import dataclass
import math
from pathlib import Path
import struct
import sys
from uuid import uuid4
import wave

from koma.editor.media_models import MAX_AUDIO_SECONDS

AUDIO_EXTENSIONS = ('wav', 'mp3', 'flac', 'ogg')
SAMPLE_RATE = 48000
CHANNELS = 2
SAMPLE_WIDTH = 2
MAX_AUDIO_BYTES = 750_000_000
PEAK_FRAMES = SAMPLE_RATE // 200
_HEADER = struct.Struct('<4sQQQI')


def validate_audio(path, duration=None):
    path = Path(path)
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_AUDIO_BYTES:
        raise ValueError('Áudio ausente, vazio ou maior que 750 MB.')
    try:
        with wave.open(str(path), 'rb') as source:
            if (source.getnchannels(), source.getsampwidth(), source.getframerate(), source.getcomptype()) != (CHANNELS, SAMPLE_WIDTH, SAMPLE_RATE, 'NONE'):
                raise ValueError('O áudio do documento precisa estar em WAV PCM normalizado.')
            frames = source.getnframes()
            seconds = frames / SAMPLE_RATE
            if not 0 < seconds <= MAX_AUDIO_SECONDS or (duration is not None and abs(seconds - duration) > 1 / SAMPLE_RATE):
                raise ValueError('Duração do áudio incompatível com o documento.')
            count = 0
            while block := source.readframes(SAMPLE_RATE):
                count += len(block)
            if count != frames * CHANNELS * SAMPLE_WIDTH:
                raise ValueError('Arquivo de áudio truncado.')
            return seconds
    except (wave.Error, EOFError, OSError) as exc:
        raise ValueError(f'Áudio inválido: {path.name}') from exc


def import_audio(source, store, cancelled=lambda: False):
    """Decodifica em blocos; só publica a cópia depois da validação completa."""
    import miniaudio
    source = Path(source).expanduser().resolve()
    if source.suffix.lower().lstrip('.') not in AUDIO_EXTENSIONS or not source.is_file() or not 0 < source.stat().st_size <= MAX_AUDIO_BYTES:
        raise ValueError('Escolha um WAV, MP3, FLAC ou OGG válido, de até 750 MB.')
    store.audio.mkdir(parents=True, exist_ok=True)
    name = f'{uuid4().hex}.wav'
    destination = store.audio / name
    temporary = destination.with_suffix('.tmp')
    stream = None
    try:
        info = miniaudio.get_file_info(str(source))
        if not math.isfinite(info.duration) or not 0 < info.duration <= MAX_AUDIO_SECONDS:
            raise ValueError('O áudio aceita até uma hora de duração.')
        initial = (source.stat().st_size, source.stat().st_mtime_ns)
        stream = miniaudio.stream_file(str(source), nchannels=CHANNELS, sample_rate=SAMPLE_RATE, frames_to_read=SAMPLE_RATE)
        frames = 0
        with wave.open(str(temporary), 'wb') as output:
            output.setparams((CHANNELS, SAMPLE_WIDTH, SAMPLE_RATE, 0, 'NONE', 'not compressed'))
            for samples in stream:
                if cancelled():
                    raise ValueError('Importação de áudio cancelada.')
                frames += len(samples) // CHANNELS
                if frames > MAX_AUDIO_SECONDS * SAMPLE_RATE or frames * CHANNELS * SAMPLE_WIDTH > MAX_AUDIO_BYTES - 44:
                    raise ValueError('O áudio decodificado ultrapassa os limites do projeto.')
                if sys.byteorder != 'little':
                    samples.byteswap()
                output.writeframesraw(samples.tobytes())
        if (source.stat().st_size, source.stat().st_mtime_ns) != initial:
            raise ValueError('O arquivo de áudio mudou durante a importação.')
        duration = validate_audio(temporary)
        temporary.replace(destination)
        waveform = load_waveform(destination, store.waveforms, cancelled)
        return name, duration, waveform
    except (miniaudio.DecodeError, wave.Error, EOFError) as exc:
        raise ValueError('Não foi possível decodificar esse áudio.') from exc
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    finally:
        if stream is not None:
            stream.close()
        temporary.unlink(missing_ok=True)


@dataclass(frozen=True)
class Waveform:
    levels: tuple
    frames: int
    bin_frames: int = PEAK_FRAMES

    def visible_peaks(self, scale, start, offset, width):
        """Escolhe a resolução pela escala e retorna apenas barras visíveis."""
        seconds_per_pixel = scale.seconds(1)
        level = min(len(self.levels) - 1, max(0, math.floor(math.log2(max(1, seconds_per_pixel * SAMPLE_RATE / self.bin_frames)))))
        values = self.levels[level]
        seconds_per_bin = self.bin_frames * 2 ** level / SAMPLE_RATE
        first = max(0, int((scale.seconds(offset) - start) / seconds_per_bin))
        last = min(len(values) // 2, math.ceil((scale.seconds(offset + width) - start) / seconds_per_bin) + 1)
        return tuple((scale.pixels(start + index * seconds_per_bin) - offset,
            values[index * 2] / 32768, values[index * 2 + 1] / 32768) for index in range(first, max(first, last)))


def _pyramid(base, frames):
    levels = [base]
    while len(levels[-1]) > 2:
        previous = levels[-1]
        values = array('h')
        for i in range(0, len(previous), 4):
            values.extend((min(previous[i:i+4:2]), max(previous[i+1:i+4:2])))
        levels.append(values)
    return Waveform(tuple(levels), frames)


def load_waveform(path, cache_directory, cancelled=lambda: False):
    path = Path(path)
    stamp = path.stat()
    cache = Path(cache_directory) / f'{path.stem}.peaks'
    try:
        with cache.open('rb') as incoming:
            magic, size, modified, frames, bins = _HEADER.unpack(incoming.read(_HEADER.size))
            expected = math.ceil(frames / PEAK_FRAMES) * 4
            if (magic, size, modified, bins) != (b'KWF1', stamp.st_size, stamp.st_mtime_ns, PEAK_FRAMES) or not 0 < frames <= SAMPLE_RATE * MAX_AUDIO_SECONDS or cache.stat().st_size != _HEADER.size + expected:
                raise ValueError('Cache desatualizado.')
            base = array('h')
            base.frombytes(incoming.read(expected))
            if sys.byteorder != 'little':
                base.byteswap()
            return _pyramid(base, frames)
    except (OSError, ValueError, struct.error):
        pass
    base = array('h')
    with wave.open(str(path), 'rb') as source:
        if (source.getnchannels(), source.getsampwidth(), source.getframerate()) != (CHANNELS, SAMPLE_WIDTH, SAMPLE_RATE):
            raise ValueError('Áudio não normalizado.')
        frames = source.getnframes()
        while block := source.readframes(PEAK_FRAMES * 200):
            if cancelled():
                raise ValueError('Geração de waveform cancelada.')
            samples = array('h')
            samples.frombytes(block)
            if sys.byteorder != 'little':
                samples.byteswap()
            for i in range(0, len(samples), PEAK_FRAMES * CHANNELS):
                window = samples[i:i + PEAK_FRAMES * CHANNELS]
                base.extend((min(window), max(window)))
    cache.parent.mkdir(parents=True, exist_ok=True)
    temporary = cache.with_name(f'.{uuid4().hex}.tmp')
    try:
        encoded = array('h', base)
        if sys.byteorder != 'little':
            encoded.byteswap()
        with temporary.open('wb') as output:
            output.write(_HEADER.pack(b'KWF1', stamp.st_size, stamp.st_mtime_ns, frames, PEAK_FRAMES))
            output.write(encoded.tobytes())
        temporary.replace(cache)
    finally:
        temporary.unlink(missing_ok=True)
    return _pyramid(base, frames)
