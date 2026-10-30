"""Read the integration MP4 using the same packaged codec library."""
import json
import sys
from pathlib import Path
import av

with av.open(str(Path(sys.argv[-1]).resolve())) as container:
    stream = container.streams.video[0]
    result = {'resolution': [stream.width, stream.height],
        'frames': sum(1 for _ in container.decode(stream)), 'fps': float(stream.average_rate)}
assert result == {'resolution': [1280, 720], 'frames': 30, 'fps': 24.0}, result
print('KOMA_VALIDATED:' + json.dumps(result), flush=True)
