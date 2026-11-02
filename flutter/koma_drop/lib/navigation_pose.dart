/// Immutable, view-only camera math; independent of project and node data.
library;

class NavigationPose {
  const NavigationPose({this.zoom = 1, this.x = 0, this.y = 0});
  final double zoom, x, y;

  NavigationPose zoomAt(double factor, double ax, double ay, double minimum, double maximum) {
    if (![factor, ax, ay].every((v) => v.isFinite) || factor <= 0) return this;
    final next = (zoom * factor).clamp(minimum, maximum).toDouble();
    if (next == zoom) return this;
    final ratio = next / zoom;
    return NavigationPose(zoom: next, x: ax - (ax - x) * ratio, y: ay - (ay - y) * ratio);
  }

  NavigationPose pan(double dx, double dy) {
    if (!dx.isFinite || !dy.isFinite) return this;
    return NavigationPose(zoom: zoom, x: (x + dx).clamp(-1e7, 1e7).toDouble(),
        y: (y + dy).clamp(-1e7, 1e7).toDouble());
  }
}

class ZoomBatch {
  double factor = 1, anchor = 0;
  bool busy = false;
  bool get pending => factor != 1;

  void add(double value, double position) {
    if (!value.isFinite || value <= 0 || !position.isFinite) return;
    factor = (factor * value).clamp(.001, 1000).toDouble();
    anchor = position;
  }

  ({double factor, double anchor})? take() {
    if (busy || !pending) return null;
    final result = (factor: factor, anchor: anchor);
    factor = 1;
    busy = true;
    return result;
  }

  void acknowledge() => busy = false;
  void clear() { factor = 1; busy = false; }
}
