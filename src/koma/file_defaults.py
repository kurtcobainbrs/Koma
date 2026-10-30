"""Validated filename templates; paths remain the file picker's responsibility."""
from string import Formatter


def validate_template(pattern):
    try:
        parts = tuple(Formatter().parse(pattern))
    except ValueError:
        raise ValueError('Use um nome com {project}, {scene} ou {shot}.') from None
    if any(field is not None and (field not in ('project', 'scene', 'shot') or spec or conversion)
           for _, field, spec, conversion in parts):
        raise ValueError('Use apenas {project}, {scene} e {shot} no nome.')
    return pattern


def export_name(view, scene, timeline=None):
    from koma.editor.file_actions import file_name
    pattern = validate_template(view.settings.configuration.values['files']['filename'])
    current = view.player.selection.active if view.player.opened else view.workspace.navigation.selected
    root = getattr(timeline, 'root', None)
    if root:
        scene = view.production.code(root.id)
    return file_name(pattern.format(project=view.board.title or 'Projeto', scene=scene,
        shot=view.production.code(current) if current in view.production.shots else ''))
