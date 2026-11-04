/// Secondary-button pan uses the existing InteractiveViewer controller locally.
library;
import 'dart:math' as math;

import 'package:flet/flet.dart';
import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'gesture_modifiers.dart';

class CanvasGesturesExtension extends FletExtension {
  @override
  Widget? createWidget(Key? key, Control control) =>
      control.type == 'koma_secondary_pan'
          ? _SecondaryPan(key: key, control: control) : null;
}

class _SecondaryPan extends StatefulWidget {
  const _SecondaryPan({super.key, required this.control});
  final Control control;
  @override
  State<_SecondaryPan> createState() => _SecondaryPanState();
}

class _SecondaryPanState extends State<_SecondaryPan> {
  TransformationController? _camera;
  RenderBox? _viewport;
  Rect? _boundary;
  Offset? _origin, _last, _scenePress;
  bool _moved = false;
  bool _zooming = false;
  double _minimum = .05, _maximum = 16;
  int? _pointer;

  bool _matches(String property) {
    return matchesGestureModifiers(widget.control, property);
  }

  bool get _allowed => !widget.control.disabled && widget.control.getBool('pan_enabled', true)!
      && !_matches('reserved_modifiers');
  bool get _zoomAllowed => !widget.control.disabled && widget.control.getBool('zoom_enabled', true)!
      && _matches('zoom_modifiers');

  // Read the public InteractiveViewer API, without depending on Flet's private
  // State or control IDs. The existing viewer retains its zoom and pan methods.
  bool _findCamera() {
    Element? viewerElement;
    void visit(Element element) {
      if (element.widget is InteractiveViewer) {
        viewerElement ??= element;
        return;
      }
      element.visitChildElements(visit);
    }
    context.visitChildElements(visit);
    final element = viewerElement;
    if (element == null) return false;
    final viewer = element.widget as InteractiveViewer;
    final viewport = element.findRenderObject();
    RenderBox? scene;
    void findScene(Element child) {
      if (identical(child.widget, viewer.child)) {
        final box = child.findRenderObject();
        if (box is RenderBox) scene = box;
      } else {
        child.visitChildElements(findScene);
      }
    }
    element.visitChildElements(findScene);
    if (viewer.transformationController == null || viewport is! RenderBox ||
        scene == null || !scene!.hasSize) return false;
    _camera = viewer.transformationController;
    _minimum = viewer.minScale;
    _maximum = viewer.maxScale;
    _viewport = viewport;
    _boundary = viewer.boundaryMargin.inflateRect(Offset.zero & scene!.size);
    return true;
  }

  void _down(PointerDownEvent event) {
    final zooming = event.buttons == kPrimaryMouseButton && _zoomAllowed;
    if ((!zooming && (event.buttons != kSecondaryMouseButton || !_allowed)) || !_findCamera()) return;
    _zooming = zooming;
    _origin = _last = event.position;
    _pointer = event.pointer;
    _scenePress = _camera!.toScene(_viewport!.globalToLocal(event.position));
    _moved = false;
  }

  void _move(PointerEvent event) {
    if (_origin == null || _camera == null || event.pointer != _pointer) return;
    final threshold = widget.control.getDouble('drag_threshold', kTouchSlop)!;
    if (!_moved && (event.position - _origin!).distance < threshold) return;
    _moved = true;
    final matrix = _camera!.value.clone();
    final scale = matrix.getMaxScaleOnAxis();
    final translation = matrix.getTranslation();
    final delta = event.position - _last!;
    _last = event.position;
    if (_zooming) {
      final sensitivity = widget.control.getDouble('zoom_sensitivity', 1)!;
      final target = (scale * math.exp((delta.dx - delta.dy) * sensitivity / 240)).clamp(_minimum, _maximum);
      final anchor = _viewport!.globalToLocal(_origin!);
      final ratio = target / scale;
      matrix.scaleByDouble(ratio, ratio, ratio, 1);
      translation.x = anchor.dx - _scenePress!.dx * target;
      translation.y = anchor.dy - _scenePress!.dy * target;
      matrix.setTranslation(translation);
      _camera!.value = matrix;
      return;
    }
    final bounds = _boundary!;
    final size = _viewport!.size;
    final minX = size.width - bounds.right * scale;
    final maxX = -bounds.left * scale;
    final minY = size.height - bounds.bottom * scale;
    final maxY = -bounds.top * scale;
    if (minX <= maxX) translation.x = (translation.x + delta.dx).clamp(minX, maxX);
    if (minY <= maxY) translation.y = (translation.y + delta.dy).clamp(minY, maxY);
    matrix.setTranslation(translation);
    _camera!.value = matrix;
  }

  void _end(PointerEvent event, {bool cancelled = false}) {
    if (_origin == null || event.pointer != _pointer) return;
    if (!cancelled) _move(event);
    final matrix = _camera!.value;
    final translation = matrix.getTranslation();
    final origin = _origin!;
    _origin = _last = null;
    _pointer = null;
    if (cancelled && !_moved) return;
    widget.control.triggerEvent('navigation', {
      'moved': _moved || cancelled || _zooming,
      'zoom': matrix.getMaxScaleOnAxis(),
      'translation_x': translation.x, 'translation_y': translation.y,
      'local_position': {'x': _scenePress!.dx, 'y': _scenePress!.dy},
      'global_position': {'x': origin.dx, 'y': origin.dy},
    });
  }

  @override
  Widget build(BuildContext context) => LayoutControl(control: widget.control,
    child: RawGestureDetector(
      gestures: {
        EagerGestureRecognizer: GestureRecognizerFactoryWithHandlers<EagerGestureRecognizer>(
          () => EagerGestureRecognizer(allowedButtonsFilter: (buttons) =>
              buttons == kSecondaryMouseButton && _allowed || buttons == kPrimaryMouseButton && _zoomAllowed), (_) {}),
      },
      child: Listener(onPointerDown: _down, onPointerMove: _move,
        onPointerUp: _end, onPointerCancel: (event) => _end(event, cancelled: true),
        child: widget.control.buildWidget('content') ?? const SizedBox()),
    ));
}
