"""Choose shared local presentation assets for the native desktop client."""
from koma.ui import drop_runtime

INACTIVE_THUMBNAILS = 32


def trim_thumbnails(view):
    keep = {frame.image for frame in view.board.frames if frame.image}
    keep.update(tuple(view.thumbnails)[-INACTIVE_THUMBNAILS:])
    for name in tuple(view.thumbnails):
        if name not in keep:
            del view.thumbnails[name]


def thumbnail_source(view, name):
    data = view.thumbnails.get(name)
    if data and drop_runtime.enabled():
        # UUID-named assets are immutable and already prepared by the store.
        # Reusing a file source also reuses Flutter's decoded image cache.
        return str(view.store.thumbnails / name)
    return data


def media_thumbnail_source(view, media):
    """Imported/restored media already own a cached poster; never open a video here."""
    if not media.image:
        return None
    if drop_runtime.enabled():
        return str(view.store.thumbnails / media.image)
    return view.thumbnails.get(media.image)
