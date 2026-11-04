"""Apply an absolute InteractiveViewer camera with bounded native requests."""
from flet.controls.exceptions import FletException
import logging

CAMERA_TIMEOUT = 5
logger = logging.getLogger(__name__)


async def apply_viewer_camera(viewer, zoom, x, y, *, current, publish=None):
    try:
        from koma.ui.spatial_view import SpatialView
        if isinstance(viewer, SpatialView):
            if not current():
                return False
            viewer.set_camera(zoom, x, y)
            (publish or (lambda control: control.update()))(viewer)
            return True
        for name, arguments in (('reset', {}), ('zoom', {'factor': zoom}),
                ('pan', {'dx': x / zoom, 'dy': y / zoom, 'dz': 0})):
            if not current():
                return False
            await viewer._invoke_method(name, arguments=arguments, timeout=CAMERA_TIMEOUT)
        return current()
    except (TimeoutError, RuntimeError, FletException) as exc:
        logger.warning('Native camera request failed (%s)', type(exc).__name__)
        return False
