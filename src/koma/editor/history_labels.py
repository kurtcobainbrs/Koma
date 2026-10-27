"""Describe document changes independently of menus and input gestures."""


def change_label(before, after):
    old = {frame.id: frame for frame in before.frames}
    new = {frame.id: frame for frame in after.frames}
    if new.keys() - old.keys():
        return 'Adicionar nodes'
    if old.keys() - new.keys():
        return 'Excluir nodes'
    if before.frame_format != after.frame_format:
        return 'Alterar formato'
    if before.fps != after.fps:
        return 'Alterar FPS'
    if before.title != after.title:
        return 'Renomear projeto'
    if before.audio_tracks != after.audio_tracks:
        return 'Editar áudio'
    if before.markers != after.markers:
        return 'Editar marcadores'
    labels = {'x': 'Mover nodes', 'y': 'Mover nodes', 'duration': 'Alterar duração',
        'image': 'Trocar imagem', 'crop_x': 'Enquadrar imagem', 'crop_y': 'Enquadrar imagem',
        'image_fit': 'Alterar enquadramento', 'muted': 'Mutar nodes', 'title': 'Renomear node',
        'subtitle': 'Editar legenda', 'action': 'Editar ação', 'audio': 'Editar diálogo',
        'notes': 'Editar notas', 'scene_color': 'Alterar cor da cena'}
    for identifier in old.keys() & new.keys():
        for key, label in labels.items():
            if getattr(old[identifier], key) != getattr(new[identifier], key):
                return label
    if tuple(old) != tuple(new):
        return 'Reordenar quadros'
    if before.links != after.links:
        return 'Editar conexões'
    if before.groups != after.groups:
        return 'Editar molduras'
    return 'Editar projeto'
