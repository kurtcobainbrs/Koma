"""One transparent overlay renderer for preview and video composition."""
from PIL import Image
from koma.editor.guide_geometry import guide_layer, camera_layer
from koma.editor.camera_models import CAMERA_PRESETS
from koma.exports.drawings import paint_image
from koma.exports.subtitles import render_subtitle


def render_guides(camera, size, options, *, exporting=False):
    image = Image.new('RGBA', size)
    if options['export' if exporting else 'preview']:
        paint_image(image, guide_layer(options))
    if options['camera_export' if exporting else 'camera_preview'] and camera.visible:
        paint_image(image, camera_layer(camera, options))
        if options['camera_label'] and camera.preset != 'none':
            label = CAMERA_PRESETS[camera.preset].label + (f' · {camera.note}' if camera.note else '')
            image.alpha_composite(render_subtitle(label, size, dict(font='Archivo', size=1.8,
                color=options['camera_color'], background='#000000', opacity=60,
                margin=10, align='Esquerda', position='Embaixo')))
    opacity = options['opacity'] / 100
    image.putalpha(image.getchannel('A').point(lambda value: round(value * opacity)))
    return image
