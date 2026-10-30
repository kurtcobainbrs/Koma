"""In-process H.264/AAC MP4 encoding; never buffers the complete timeline."""
from fractions import Fraction
from time import monotonic
import av
from koma.documents.audio import SAMPLE_RATE
from koma.documents.videos import DECODE_THREADS
from koma.exports.video_audio import AudioMixer, AUDIO_BIT_RATE

QUALITY_CRF = {'HIGH': '18', 'MEDIUM': '23', 'LOW': '28'}
ENCODER_PRESET = 'veryfast'
PROGRESS_INTERVAL = .1


def encode(source, destination, fps, quality, max_size, audio_tracks, cancelled, notify):
    width, height = source.size
    scale = min(1, max_size / max(width, height)) if max_size else 1
    size = tuple(max(2, int(value * scale) // 2 * 2) for value in (width, height))
    rate = Fraction(str(fps)).limit_denominator(100000)
    pictures = source.pictures(size, float(rate), cancelled)
    total_samples = round(source.count * SAMPLE_RATE / rate)
    audio = AudioMixer(audio_tracks, total_samples).blocks(cancelled) if audio_tracks else iter(())
    last_progress = 0
    try:
        with av.open(str(destination), 'w', format='mp4', options={'movflags': '+faststart'}) as output:
            video = output.add_stream('libx264', rate=rate)
            video.width, video.height = size
            video.pix_fmt, video.time_base = 'yuv420p', 1 / rate
            video.codec_context.thread_count = DECODE_THREADS
            video.options = {'crf': QUALITY_CRF[quality], 'preset': ENCODER_PRESET}
            sound = None
            if audio_tracks:
                sound = output.add_stream('aac', rate=SAMPLE_RATE)
                sound.layout, sound.bit_rate = 'stereo', AUDIO_BIT_RATE
            pending = next(audio, None)
            done = 0
            for index, picture in enumerate(pictures):
                if cancelled():
                    return False
                frame = av.VideoFrame.from_image(picture)
                frame.pts, frame.time_base = index, 1 / rate
                for packet in video.encode(frame):
                    output.mux(packet)
                while pending is not None and pending.pts * rate < (index + 1) * SAMPLE_RATE:
                    if cancelled():
                        return False
                    for packet in sound.encode(pending):
                        output.mux(packet)
                    pending = next(audio, None)
                done = index + 1
                now = monotonic()
                if done == source.count or now - last_progress >= PROGRESS_INTERVAL:
                    notify(dict(phase='Codificando MP4', done=done, total=source.count))
                    last_progress = now
            if cancelled():
                return False
            if done != source.count:
                raise ValueError('A leitura das mídias terminou antes do fim do animatic.')
            for packet in video.encode():
                output.mux(packet)
            if sound is not None:
                for packet in sound.encode():
                    output.mux(packet)
        if cancelled():
            return False
        with av.open(str(destination)) as result:
            video = result.streams.video[0]
            if (video.frames != source.count or (video.width, video.height) != size
                    or video.average_rate != rate or bool(result.streams.audio) != bool(audio_tracks)):
                raise ValueError('O MP4 gerado não corresponde à sequência solicitada.')
        return True
    except av.error.FFmpegError as exc:
        raise ValueError('Não foi possível codificar o MP4.') from exc
    finally:
        pictures.close()
        if hasattr(audio, 'close'):
            audio.close()
