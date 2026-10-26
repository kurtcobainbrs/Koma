"""Saída de áudio isolada; comandos serializados fora da thread da interface."""

from array import array
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from time import monotonic
import wave

from koma.documents.audio import SAMPLE_RATE, CHANNELS, SAMPLE_WIDTH


def pcm_stream(path, position, start, duration, volume=1):
    """Gera silêncio e PCM a partir da mesma posição absoluta do player."""
    with wave.open(str(path), 'rb') as source:
        source.setpos(min(source.getnframes(), max(0, round((position - start) * SAMPLE_RATE))))
        silence = max(0, round((start - position) * SAMPLE_RATE))
        remaining = max(0, round((duration - position) * SAMPLE_RATE))
        requested = yield b''
        while remaining > 0:
            count = min(requested, remaining)
            empty = min(silence, count)
            silence -= empty
            data = source.readframes(count - empty)
            if volume != 1 and data:
                samples = array('h')
                samples.frombytes(data)
                data = array('h', (max(-32768, min(32767, round(sample * volume))) for sample in samples)).tobytes()
            block = bytes(empty * CHANNELS * SAMPLE_WIDTH) + data
            block += bytes(count * CHANNELS * SAMPLE_WIDTH - len(block))
            remaining -= count
            requested = yield block


class AudioTransport:
    def __init__(self, device_factory=None, clock=monotonic):
        self.factory = device_factory
        self.clock = clock
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='koma-audio')
        self.lock = Lock()
        self.serial = 0
        self.key = None
        self.anchor = 0
        self.device = self.stream = None
        self.error = ''
        self.closed = False

    def update(self, timeline, store, playing, position):
        track = next((track for track in timeline.audio_tracks if not track.muted and track.volume > 0), None) if timeline else None
        key = (track, store.directory, bool(playing and track))
        now = self.clock()
        if key == self.key and (not key[-1] or abs(position - (now - self.anchor)) < .15):
            return
        previous = self.key
        self.key = key
        self.anchor = now - position
        if not key[-1] and (previous is None or not previous[-1]):
            return
        self._submit(track, store, bool(playing and track), position, timeline.total if timeline else 0, now)

    def _submit(self, track, store, playing, position, total, requested):
        with self.lock:
            if self.closed:
                return
            self.serial += 1
            serial = self.serial
        self.executor.submit(self._apply, serial, track, store, playing, position, total, requested)

    def _dispose(self):
        if self.device is not None:
            self.device.close()
            self.device = None
        if self.stream is not None:
            self.stream.close()
            self.stream = None

    def _apply(self, serial, track, store, playing, position, total, requested):
        with self.lock:
            if serial != self.serial:
                return
        try:
            self._dispose()
            if not playing:
                return
            import miniaudio
            factory = self.factory or miniaudio.PlaybackDevice
            self.device = factory(nchannels=CHANNELS, sample_rate=SAMPLE_RATE, buffersize_msec=50)
            with self.lock:
                if serial != self.serial:
                    self._dispose()
                    return
            position = min(total, position + self.clock() - requested)
            if position >= total:
                self._dispose()
                return
            self.stream = pcm_stream(store.audio / track.asset, position, track.start, total, track.volume)
            next(self.stream)
            self.device.start(self.stream)
        except Exception as exc:
            self.error = f'Não foi possível reproduzir o áudio: {exc}'
            self._dispose()

    def stop(self):
        if self.key is None or not self.key[-1]:
            return
        self.key = None
        self._submit(None, None, False, 0, 0, self.clock())

    def close(self):
        with self.lock:
            if self.closed:
                return
            self.closed = True
            self.serial += 1
        self.executor.submit(self._dispose)
        self.executor.shutdown(wait=True)
