/// Local preview camera and middle-button timeline pan, with bounded zoom requests.
library;
import 'dart:math' as math;
import 'dart:async';
import 'package:flet/flet.dart';
import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';
import 'package:flutter/services.dart';
import 'navigation_pose.dart';

class NavigationExtension extends FletExtension {
  @override
  Widget? createWidget(Key? key, Control control) => control.type == 'koma_navigation'
      ? NavigationView(key: key, control: control) : null;
}

class NavigationView extends StatefulWidget {
  const NavigationView({super.key, required this.control});
  final Control control;
  @override
  State<NavigationView> createState() => _NavigationViewState();
}

class _NavigationViewState extends State<NavigationView> {
  final _camera = ValueNotifier(const NavigationPose());
  ScrollableState? _scroll;
  Offset? _last;
  int? _pointer;
  final _batch = ZoomBatch();
  bool _scheduled = false;
  Timer? _idle;
  bool _wheelActive = false;
  int _revision = -1, _generation = -1, _scrollRequest = -1;
  double _trackpadZoom = 1;
  bool get _spatial => widget.control.getString('mode', 'preview') == 'preview';
  bool get _enabled => !widget.control.disabled && widget.control.getBool('navigation_enabled', true)!;

  @override
  void initState() {
    super.initState();
    _camera.value = NavigationPose(zoom: widget.control.getDouble('initial_zoom', 1)!,
        x: widget.control.getDouble('initial_x', 0)!, y: widget.control.getDouble('initial_y', 0)!);
    widget.control.addInvokeMethodListener(_invoke);
  }

  Future<dynamic> _invoke(String name, dynamic args) async {
    if (name == 'fit') _fit();
    return null;
  }

  ScrollPosition? _position() {
    final ancestor = Scrollable.maybeOf(context, axis: Axis.horizontal);
    if (ancestor != null) { _scroll = ancestor; return ancestor.position; }
    if (_scroll?.mounted == true) return _scroll!.position;
    _scroll = null;
    void visit(Element element) {
      if (_scroll != null) return;
      if (element is StatefulElement && element.state is ScrollableState) {
        final state = element.state as ScrollableState;
        if (axisDirectionToAxis(state.position.axisDirection) == Axis.horizontal) {
          _scroll = state;
          return;
        }
      }
      element.visitChildElements(visit);
    }
    context.visitChildElements(visit);
    return _scroll?.position;
  }

  void _jump(double offset) {
    final position = _position();
    if (position == null || !position.hasContentDimensions || !offset.isFinite) return;
    position.jumpTo(offset.clamp(position.minScrollExtent, position.maxScrollExtent));
  }

  void _schedule() {
    if (_scheduled || _batch.busy || !_batch.pending || _spatial) return;
    _scheduled = true;
    SchedulerBinding.instance.addPostFrameCallback((_) {
      _scheduled = false;
      if (!mounted || !_enabled) return;
      final request = _batch.take();
      if (request == null) return;
      widget.control.triggerEvent('zoom', {'factor': request.factor, 'anchor_x': request.anchor,
        'pixels': _position()?.pixels ?? 0, 'generation': _generation});
    });
    SchedulerBinding.instance.scheduleFrame();
  }

  void _zoom(double factor, Offset anchor) {
    if (!_enabled || !factor.isFinite || factor <= 0) return;
    if (_spatial) {
      _camera.value = _camera.value.zoomAt(factor, anchor.dx, anchor.dy,
        widget.control.getDouble('minimum_zoom', .25)!, widget.control.getDouble('maximum_zoom', 16)!);
    } else {
      _batch.add(factor, anchor.dx - (widget.control.getBool('content_coordinates', false)! ? (_position()?.pixels ?? 0) : 0));
      _schedule();
    }
  }

  void _signal(PointerSignalEvent event) {
    if (!_enabled || event is! PointerScrollEvent) return;
    GestureBinding.instance.pointerSignalResolver.register(event, (_) {
      if (!_wheelActive) widget.control.triggerEvent('engage');
      _wheelActive = true;
      _idle?.cancel();
      _idle = Timer(const Duration(milliseconds: 120), () { _wheelActive = false; _reportPose(); });
      if (!_spatial && (HardwareKeyboard.instance.isShiftPressed || event.scrollDelta.dy == 0)) {
        final delta = event.scrollDelta.dx != 0 ? event.scrollDelta.dx : event.scrollDelta.dy;
        _jump((_position()?.pixels ?? 0) + delta * widget.control.getDouble('pan_speed', 1)!);
      } else {
        final sensitivity = widget.control.getDouble('wheel_sensitivity', 1)!;
        _zoom(math.exp(-event.scrollDelta.dy * sensitivity / 240), event.localPosition);
      }
    });
  }

  void _down(PointerDownEvent event) {
    if (!_enabled) return;
    if (event.buttons != kMiddleMouseButton) { _reportPose(); return; }
    _last = event.position;
    _pointer = event.pointer;
    widget.control.triggerEvent('engage');
    if (!_spatial) _position();
  }

  void _move(PointerMoveEvent event) {
    if (_last == null || event.pointer != _pointer || !_enabled) return;
    final delta = (event.position - _last!) * widget.control.getDouble('pan_speed', 1)!;
    _last = event.position;
    if (_spatial) {
      _camera.value = _camera.value.pan(delta.dx, delta.dy);
    } else {
      _jump((_position()?.pixels ?? 0) - delta.dx);
    }
  }

  void _end(PointerEvent event) {
    if (event.pointer == _pointer) { _pointer = null; _last = null; _reportPose(); }
  }

  void _reportPose() {
    if (!mounted || !_spatial) return;
    final pose = _camera.value;
    widget.control.triggerEvent('pose', {'zoom': pose.zoom, 'x': pose.x, 'y': pose.y, 'generation': _generation});
  }

  void _fit() { _camera.value = const NavigationPose(); _reportPose(); }

  void _configure() {
    final generation = widget.control.getInt('generation', 0)!;
    if (generation != _generation) {
      _generation = generation;
      _batch.clear(); _scroll = null;
    }
    if (!_enabled) { _batch.clear(); _last = null; _pointer = null; }
    if (_spatial) {
      _camera.value = _camera.value.zoomAt(1, 0, 0,
        widget.control.getDouble('minimum_zoom', .25)!, widget.control.getDouble('maximum_zoom', 16)!);
    }
    final revision = widget.control.getInt('revision', 0)!;
    final request = widget.control.getInt('scroll_request', 0)!;
    if (!_spatial && (revision != _revision || request != _scrollRequest)) {
      _revision = revision; _scrollRequest = request;
      SchedulerBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;
        _jump(widget.control.getDouble('scroll_offset', 0)!);
        _batch.acknowledge();
        _schedule();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    _configure();
    final child = RepaintBoundary(child: widget.control.buildWidget('content') ?? const SizedBox());
    final body = _spatial ? ValueListenableBuilder<NavigationPose>(valueListenable: _camera,
        child: child, builder: (context, pose, content) => Stack(fit: StackFit.expand, children: [
          Transform(transform: Matrix4.identity()..translateByDouble(pose.x, pose.y, 0, 1)
              ..scaleByDouble(pose.zoom, pose.zoom, 1, 1), child: content),
          Positioned(right: 4, bottom: 4, child: Row(mainAxisSize: MainAxisSize.min, children: [
            Text('${(pose.zoom * 100).round()}%', style: const TextStyle(fontSize: 11)),
            IconButton(tooltip: 'Enquadrar prévia · F', visualDensity: VisualDensity.compact,
              onPressed: _fit, icon: const Icon(Icons.fit_screen, size: 18)),
          ])),
        ])) : child;
    return LayoutControl(control: widget.control, child: ClipRect(child: MouseRegion(
      onEnter: (_) => widget.control.triggerEvent('activate'),
      onExit: (_) { _reportPose(); widget.control.triggerEvent('deactivate'); },
      child: RawGestureDetector(gestures: {
        EagerGestureRecognizer: GestureRecognizerFactoryWithHandlers<EagerGestureRecognizer>(
          () => EagerGestureRecognizer(allowedButtonsFilter: (buttons) => buttons == kMiddleMouseButton && _enabled), (_) {}),
      }, child: Listener(behavior: HitTestBehavior.translucent,
        onPointerSignal: _signal, onPointerDown: _down, onPointerMove: _move,
        onPointerUp: _end, onPointerCancel: _end,
        onPointerPanZoomStart: (_) => _trackpadZoom = _camera.value.zoom,
        onPointerPanZoomUpdate: (event) {
          if (!_spatial || !_enabled) return;
          _zoom(_trackpadZoom * event.scale / _camera.value.zoom, event.localPosition);
          _camera.value = _camera.value.pan(event.panDelta.dx, event.panDelta.dy);
        }, onPointerPanZoomEnd: (_) => _reportPose(), child: body)))));
  }

  @override
  void dispose() {
    widget.control.removeInvokeMethodListener(_invoke);
    _idle?.cancel();
    _camera.dispose();
    super.dispose();
  }
}
