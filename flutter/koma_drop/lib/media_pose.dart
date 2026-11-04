import 'dart:math' as math;
import 'package:flet/flet.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter/scheduler.dart';
import 'package:flutter/gestures.dart';

List<double> evaluateMediaPose(List<dynamic> keys, double seconds, List<double> fallback) {
  if (keys.isEmpty) return fallback;
  List<double> pose(dynamic key) => [for (final name in ['x', 'y', 'scale', 'rotation']) (key[name] as num).toDouble()];
  var low = 0, high = keys.length;
  while (low < high) {
    final mid = (low + high) ~/ 2;
    if ((keys[mid]['time'] as num) <= seconds) { low = mid + 1; } else { high = mid; }
  }
  if (low == 0) return pose(keys.first);
  final left = keys[low - 1];
  if (low == keys.length || left['interpolation'] == 'hold') return pose(left);
  final right = keys[low];
  final ratio = (seconds - (left['time'] as num)) / ((right['time'] as num) - (left['time'] as num));
  final a = pose(left), b = pose(right);
  return [for (var i = 0; i < 4; i++) a[i] + (b[i] - a[i]) * ratio];
}

class MediaPoseExtension extends FletExtension {
  @override
  Widget? createWidget(Key? key, Control control) => control.type == 'koma_media_pose'
      ? MediaPoseView(key: key ?? ValueKey(control.id), control: control) : null;
}

class MediaPoseView extends StatefulWidget {
  const MediaPoseView({super.key, required this.control});
  final Control control;
  @override
  State<MediaPoseView> createState() => _MediaPoseState();
}

class _MediaPoseState extends State<MediaPoseView> with SingleTickerProviderStateMixin {
  final focus = FocusNode();
  Offset? start;
  bool dragging = false;
  bool pending = false;
  int generation = -1;
  double x = 0, y = 0, scale = 1, angle = 0;
  List<double> initial = [0, 0, 1, 0];
  Object? contentToken;
  Widget? mediaChild;
  late final Ticker ticker;
  int playbackRevision = -1;
  bool playbackActive = false;
  List<dynamic> keys = [];
  double anchor = 0;
  Matrix4? pointerMatrix;
  double gestureWidth = 1, gestureHeight = 1;
  int? pointer;
  bool modal = false;
  Offset? lastHover;
  int startRequest = 0;
  bool routing = false;
  String? axis;
  Offset? lastPoint;

  void beginAt(Offset? point, double width, double height, Matrix4 matrix, {bool immediate = false}) {
    dragging = true;
    modal = immediate;
    pointerMatrix = matrix;
    start = point == null ? null : MatrixUtils.transformPoint(matrix, point);
    gestureWidth = width; gestureHeight = height;
    initial = [x, y, scale, angle];
    axis = null;
    lastPoint = point;
    focus.requestFocus();
    report('begin');
    if (!routing) {
      routing = true;
      GestureBinding.instance.pointerRouter.addGlobalRoute(globalPointer);
    }
  }

  void stopRouting() {
    if (routing) {
      GestureBinding.instance.pointerRouter.removeGlobalRoute(globalPointer);
      routing = false;
    }
  }

  void globalPointer(PointerEvent event) {
    if (!dragging) return;
    if (modal) {
      if (event is PointerHoverEvent || event is PointerMoveEvent) moveAt(event.position);
      if (event is PointerDownEvent) {
        if (event.buttons == kPrimaryMouseButton) { end(true); }
        else if (event.buttons == kSecondaryMouseButton) { end(false); }
      }
    } else if (event.pointer == pointer) {
      if (event is PointerMoveEvent) moveAt(event.position);
      else if (event is PointerUpEvent) { end(true); }
      else if (event is PointerCancelEvent) { end(false); }
    }
  }

  void moveAt(Offset point) {
    lastPoint = point;
    if (!dragging || pointerMatrix == null) return;
    final local = MatrixUtils.transformPoint(pointerMatrix!, point);
    if (start == null) { start = local; return; }
    final delta = local - start!;
    final c = widget.control;
    final tool = c.getString('tool', 'move');
    setState(() {
      if (tool == 'move') {
        final limit = c.getDouble('max_translation', 10)!;
        x = (initial[0] + (axis == 'y' ? 0 : delta.dx / gestureWidth)).clamp(-limit, limit);
        y = (initial[1] + (axis == 'x' ? 0 : delta.dy / gestureHeight)).clamp(-limit, limit);
      } else if (tool == 'scale') {
        scale = (initial[2] * math.exp((delta.dx - delta.dy) / math.min(gestureWidth, gestureHeight)))
            .clamp(c.getDouble('min_scale', .01)!, c.getDouble('max_scale', 100)!);
      } else if (tool == 'rotate') {
        final limit = c.getDouble('max_rotation', 36000)!;
        angle = (initial[3] + delta.dx / gestureWidth * 360).clamp(-limit, limit);
      }
    });
  }

  @override
  void initState() {
    super.initState();
    ticker = createTicker((elapsed) {
      if (!mounted || dragging || pending) return;
      final seconds = math.min(widget.control.getDouble('maximum_time', 3600)!, anchor + elapsed.inMicroseconds / 1000000);
      final pose = evaluateMediaPose(keys, seconds, [x, y, scale, angle]);
      if (pose[0] == x && pose[1] == y && pose[2] == scale && pose[3] == angle) return;
      setState(() { x = pose[0]; y = pose[1]; scale = pose[2]; angle = pose[3]; });
    });
  }

  void readPose() {
    final c = widget.control;
    x = c.getDouble('x', 0)!;
    y = c.getDouble('y', 0)!;
    scale = c.getDouble('zoom', 1)!;
    angle = c.getDouble('angle', 0)!;
  }

  void report(String event) => widget.control.triggerEvent(event,
      {'generation': generation, 'x': x, 'y': y, 'scale': scale, 'rotation': angle});

  void end(bool commit) {
    if (!dragging) return;
    dragging = false;
    stopRouting();
    modal = false;
    axis = null;
    pending = commit;
    if (!commit) { x = initial[0]; y = initial[1]; scale = initial[2]; angle = initial[3]; }
    report(commit ? 'commit' : 'cancel');
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final c = widget.control;
    final next = c.getInt('generation', 0)!;
    final changed = next != generation;
    final revision = c.getInt('playback_revision', 0)!;
    final playing = c.getBool('playing', false)!;
    if (changed) { generation = next; dragging = false; pending = false; stopRouting(); }
    // Presentation/gesture generations are not playback seeks. Parent updates
    // must never replay a stale server pose or restart the display-frame clock.
    if (changed || revision != playbackRevision) keys = c.get<List<dynamic>>('keyframes', [])!;
    if (revision != playbackRevision || playbackActive != playing) {
      playbackRevision = revision;
      playbackActive = playing;
      ticker.stop();
      anchor = c.getDouble('seconds', 0)!;
      if (playing) {
        final pose = evaluateMediaPose(keys, anchor, [x, y, scale, angle]);
        x = pose[0]; y = pose[1]; scale = pose[2]; angle = pose[3];
        ticker.start();
      }
    }
    if (!dragging && !pending && (!playing || keys.isEmpty)) readPose();
    final nextContent = c.get('content');
    if (mediaChild == null || !identical(contentToken, nextContent)) {
      contentToken = nextContent;
      mediaChild = RepaintBoundary(child: c.buildWidget('content') ?? const SizedBox());
    }
    final child = mediaChild!;
    return LayoutControl(control: c, child: LayoutBuilder(builder: (context, constraints) {
      final width = constraints.maxWidth, height = constraints.maxHeight;
      final request = c.getInt('start_request', 0)!;
      if (request != startRequest) {
        startRequest = request;
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted && c.getBool('editing', false)! && !dragging && !pending) {
            beginAt(lastHover, width, height, context.findRenderObject()!.getTransformTo(null)..invert(), immediate: true);
          }
        });
      }
      final rect = c.get<List<dynamic>>('rect', [0, 0, 1, 1])!;
      final positionedMedia = ClipRect(child: Transform.translate(offset: Offset(x * width, y * height),
          // Filter the image itself, not a raster snapshot of the whole media
          // subtree. An ImageFilter on this transform creates an offscreen
          // texture that must be regenerated as the outer canvas zoom changes.
          child: Transform.rotate(angle: angle * math.pi / 180, child: Transform.scale(scale: scale,
              child: SizedBox(width: width, height: height, child: Stack(clipBehavior: Clip.none, children: [
                Positioned(left: (rect[0] as num) * width, top: (rect[1] as num) * height,
                    width: (rect[2] as num) * width, height: (rect[3] as num) * height,
                    child: Transform.flip(flipX: c.getBool('flip_x', false)!,
                        flipY: c.getBool('flip_y', false)!, child: child))
              ]))))));
      final media = Stack(fit: StackFit.expand, children: [positionedMedia,
        if (dragging && axis != null) IgnorePointer(child: CustomPaint(
            painter: _AxisGuide(axis!, Offset(width * (.5 + initial[0]), height * (.5 + initial[1]))))),
      ]);
      if (!c.getBool('editing', false)!) return media;
      return Focus(focusNode: focus, onKeyEvent: (_, event) {
        if (event is KeyDownEvent && dragging) {
          if (c.getString('tool', 'move') == 'move' &&
              (event.logicalKey == LogicalKeyboardKey.keyX || event.logicalKey == LogicalKeyboardKey.keyY)) {
            final requested = event.logicalKey == LogicalKeyboardKey.keyX ? 'x' : 'y';
            setState(() { axis = axis == requested ? null : requested; });
            if (lastPoint != null) moveAt(lastPoint!);
            return KeyEventResult.handled;
          }
          if (event.logicalKey == LogicalKeyboardKey.escape) { end(false); return KeyEventResult.handled; }
          if (event.logicalKey == LogicalKeyboardKey.enter) { end(true); return KeyEventResult.handled; }
        }
        return KeyEventResult.ignored;
      }, child: MouseRegion(onEnter: (e) => lastHover = e.position, onExit: (_) => lastHover = null,
          onHover: (e) { lastHover = e.position; },
          child: Listener(behavior: HitTestBehavior.opaque,
          onPointerDown: (e) {
            if (modal && dragging) {
              if (e.buttons == kPrimaryMouseButton) { end(true); }
              else if (e.buttons == kSecondaryMouseButton) { end(false); }
              return;
            }
            if (pending || e.buttons != kPrimaryMouseButton) return;
            final keyboard = HardwareKeyboard.instance;
            if (keyboard.isAltPressed || keyboard.isControlPressed || keyboard.isMetaPressed) return;
            pointer = e.pointer;
            beginAt(e.position, width, height, context.findRenderObject()!.getTransformTo(null)..invert());
          }, child: media)));
    }));
  }

  @override
  void dispose() { stopRouting(); ticker.dispose(); focus.dispose(); super.dispose(); }
}

class _AxisGuide extends CustomPainter {
  _AxisGuide(this.axis, this.origin);
  final String axis;
  final Offset origin;
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..color = (axis == 'x' ? Colors.redAccent : Colors.greenAccent).withValues(alpha: .65)..strokeWidth = 1;
    canvas.drawLine(axis == 'x' ? Offset(0, origin.dy) : Offset(origin.dx, 0),
        axis == 'x' ? Offset(size.width, origin.dy) : Offset(origin.dx, size.height), paint);
  }
  @override
  bool shouldRepaint(_AxisGuide oldDelegate) => axis != oldDelegate.axis || origin != oldDelegate.origin;
}
