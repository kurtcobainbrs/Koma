"""Asset traversal shared by save/open, recovery and clipboard."""
from koma.editor.node_media import board_assets


def validate_assets(board, store):
    from koma.documents.bundle import validate_image
    from koma.documents.videos import inspect_video
    from koma.documents.audio import validate_audio
    for folder, name in board_assets(board):
        path = getattr(store, folder) / name
        if folder == 'images':
            validate_image(path)
        elif folder == 'videos':
            inspect_video(path, decode=False)
        else:
            validate_audio(path)
