"""One timing display contract for the ruler and playback clock."""
def time_text(seconds, fps, options):
    if options['unit'] == 'Frames':
        return f'{round(seconds * fps):0{options["counter_digits"]}d} f'
    return f'{seconds:.{options["seconds_decimals"]}f} s'


def clock_text(position, total, fps, options):
    return time_text(position, fps, options) + ' / ' + time_text(total, fps, options)
