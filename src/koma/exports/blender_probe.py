"""Codifica imagens num processo Blender de fábrica; nunca abre um .blend."""

import json
import sys
from pathlib import Path

import bpy


def emit(phase, done, total):
    print('KOMA_VIDEO:' + json.dumps(dict(phase=phase, done=done, total=total)), flush=True)


def main():
    request = json.loads(Path(sys.argv[sys.argv.index('--') + 1]).read_text(encoding='utf-8'))
    images = [Path(path) for path in request['images']]
    durations = request.get('durations')
    total_frames = sum(durations) if durations else len(images)
    scene = bpy.context.scene
    converted = []
    dimensions = None
    for index, source in enumerate(images):
        image = bpy.data.images.load(str(source), check_existing=False)
        if source.suffix.lower() in {'.exr', '.hdr'}:
            target = Path(request['cache']) / f'{index:08d}.png'
            scene.view_settings.view_transform = 'AgX'
            if hasattr(scene.render.image_settings, 'media_type'):
                scene.render.image_settings.media_type = 'IMAGE'
            scene.render.image_settings.file_format = 'PNG'
            scene.render.image_settings.color_mode = 'RGB'
            scene.render.image_settings.color_depth = '8'
            image.save_render(str(target), scene=scene)
            bpy.data.images.remove(image)
            image = bpy.data.images.load(str(target), check_existing=False)
        else:
            target = source
        current = tuple(image.size)
        if not all(current):
            raise ValueError(f'Imagem inválida: {source.name}')
        if dimensions and current != dimensions:
            raise ValueError(f'Resolução diferente na imagem {source.name}.')
        dimensions = current
        converted.append(target)
        bpy.data.images.remove(image)
        emit('Preparando imagens', index + 1, len(images))
    width, height = dimensions
    limit = request['max_size']
    scale = min(1.0, limit / max(width, height)) if limit else 1.0
    scene.render.resolution_x = max(2, int(width * scale) // 2 * 2)
    scene.render.resolution_y = max(2, int(height * scale) // 2 * 2)
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.render.fps = round(request['fps'])
    scene.render.fps_base = scene.render.fps / request['fps']
    scene.frame_start, scene.frame_end = 1, total_frames
    scene.render.use_sequencer = True
    editor = scene.sequence_editor_create()
    strips = getattr(editor, 'strips', None)
    if strips is None:
        strips = editor.sequences
    if durations:
        start = 1
        for index, (source, duration) in enumerate(zip(converted, durations)):
            strip = strips.new_image(name=f'Quadro {index+1:02d}', filepath=str(source), channel=1, frame_start=start)
            strip.frame_final_duration = duration
            start += duration
    else:
        strip = strips.new_image(name='Sequência', filepath=str(converted[0]), channel=1, frame_start=1)
        for source in converted[1:]:
            strip.elements.append(source.name)
        strip.frame_final_duration = len(images)
    if hasattr(scene.render.image_settings, 'media_type'):
        scene.render.image_settings.media_type = 'VIDEO'
    scene.render.image_settings.file_format = 'FFMPEG'
    scene.render.ffmpeg.format = 'MPEG4'
    scene.render.ffmpeg.codec = 'H264'
    scene.render.ffmpeg.constant_rate_factor = request['quality']
    scene.render.ffmpeg.ffmpeg_preset = 'GOOD'
    scene.render.ffmpeg.audio_codec = 'NONE'
    scene.render.filepath = request['output']
    scene.render.use_file_extension = True
    bpy.app.handlers.render_post.append(lambda s, *args: emit('Codificando MP4', s.frame_current, total_frames))
    result = bpy.ops.render.render(animation=True)
    if 'FINISHED' not in result:
        raise RuntimeError('A codificação não foi concluída.')
    print('KOMA_VIDEO_FINISHED', flush=True)


if __name__ == '__main__':
    main()
