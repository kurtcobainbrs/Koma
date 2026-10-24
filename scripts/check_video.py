"""Executar no Blender para verificar o MP4 produzido pela integração."""
import json
import sys
from pathlib import Path
import bpy

clip = bpy.data.movieclips.load(str(Path(sys.argv[-1]).resolve()))
result = {'resolution': list(clip.size), 'frames': clip.frame_duration, 'fps': clip.fps}
assert result == {'resolution': [1280, 720], 'frames': 30, 'fps': 24.0}, result
print('KOMA_VALIDATED:' + json.dumps(result), flush=True)
