"""Stream a normalized PCM range without modifying the project asset."""
import wave


def extract(source, destination, offset, duration, cancelled=lambda: False):
    with wave.open(str(source), 'rb') as original:
        rate = original.getframerate()
        first = min(original.getnframes(), max(0, round(offset * rate)))
        remaining = min(original.getnframes() - first, max(1, round(duration * rate)))
        original.setpos(first)
        with wave.open(str(destination), 'wb') as output:
            output.setparams(original.getparams())
            while remaining > 0:
                if cancelled():
                    raise ValueError('Exportação cancelada.')
                count = min(remaining, rate)
                output.writeframes(original.readframes(count))
                remaining -= count
    return destination
