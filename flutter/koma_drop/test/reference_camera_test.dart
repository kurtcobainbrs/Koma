import 'package:flet/src/controls/interactive_viewer.dart';
import 'package:flet/src/flet_backend.dart';
import 'package:flet/src/models/control.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:koma_drop/spatial_view.dart';
import 'package:flet/src/controls/container.dart';
import 'package:koma_drop/secondary_pan.dart';
import 'package:flutter/services.dart';
import 'package:flutter/gestures.dart';
import 'package:koma_drop/navigation_view.dart';

class RecordingNavigationBackend extends FletBackend {
  RecordingNavigationBackend() : super(pageUri: Uri.parse('http://localhost'),
      assetsDir: '', extensions: [], multiView: false);
  final events = <Map<String, dynamic>>[];
  @override
  void triggerControlEvent(Control control, String eventName, [dynamic data]) {
    events.add({'name': eventName, 'data': data});
  }
}

void main() {
  testWidgets('wheel camera is reported and survives a mode remount', (tester) async {
    final backend = RecordingNavigationBackend();
    final control = Control(id: 80, type: 'koma_spatial_view', backend: backend,
        properties: {'camera_zoom': 1.0, 'camera_x': -1000.0,
          'camera_y': -800.0, 'camera_revision': 0});
    Widget build(bool visible) => ChangeNotifierProvider<FletBackend>.value(value: backend,
        child: MaterialApp(home: SizedBox(width: 600, height: 400,
            child: visible ? SpatialView(control: control) : const SizedBox())));
    await tester.pumpWidget(build(true));
    await tester.pumpAndSettle();
    backend.events.clear();
    await tester.sendEventToBinding(const PointerScrollEvent(position: Offset(200, 150),
        scrollDelta: Offset(0, -120)));
    await tester.pumpAndSettle();
    final pose = backend.events.lastWhere((event) => event['name'] == 'pose')['data'] as Map;
    expect(pose['zoom'], greaterThan(1));
    // Mirror the server's camera-pose contract, then leave and return to Refs.
    control.properties.addAll({'camera_zoom': pose['zoom'],
      'camera_x': pose['x'], 'camera_y': pose['y']});
    await tester.pumpWidget(build(false));
    await tester.pumpWidget(build(true));
    await tester.pumpAndSettle();
    final matrix = tester.widget<InteractiveViewer>(find.byType(InteractiveViewer))
        .transformationController!.value;
    expect(matrix.getMaxScaleOnAxis(), closeTo(pose['zoom'] as double, .0001));
    expect(matrix.storage[12], pose['x']);
    expect(matrix.storage[13], pose['y']);
    expect(tester.takeException(), isNull);
  });
  for (final mode in ['preview', 'timeline']) {
    testWidgets('animatic $mode supports anchored modifier drag zoom', (tester) async {
      final backend = RecordingNavigationBackend();
      final control = Control(id: 30, type: 'koma_navigation', backend: backend,
          properties: {'mode': mode, 'zoom_modifiers': ['Alt+Shift']});
      control.properties['content'] = Control(id: 31, type: 'Container', parent: control,
          backend: backend, properties: {'width': 600.0, 'height': 400.0, 'bgcolor': '#202020'});
      await tester.pumpWidget(ChangeNotifierProvider<FletBackend>.value(value: backend,
          child: MaterialApp(home: Scaffold(body: SizedBox(width: 600, height: 400,
              child: NavigationView(control: control))))));
      await tester.pumpAndSettle();
      await tester.sendKeyDownEvent(LogicalKeyboardKey.altLeft);
      await tester.sendKeyDownEvent(LogicalKeyboardKey.shiftLeft);
      final gesture = await tester.startGesture(const Offset(200, 150));
      await gesture.moveTo(const Offset(260, 150));
      await tester.pump();
      await gesture.up();
      await tester.pump();
      await tester.sendKeyUpEvent(LogicalKeyboardKey.shiftLeft);
      await tester.sendKeyUpEvent(LogicalKeyboardKey.altLeft);
      final event = backend.events.lastWhere((event) => event['name'] == (mode == 'preview' ? 'pose' : 'zoom'));
      final data = event['data'] as Map;
      if (mode == 'preview') {
        final zoom = data['zoom'] as double;
        expect(zoom, greaterThan(1));
        expect((200 - (data['x'] as double)) / zoom, closeTo(200, .001));
        expect((150 - (data['y'] as double)) / zoom, closeTo(150, .001));
      } else {
        expect(data['factor'], greaterThan(1));
        expect(data['anchor_x'], 200);
      }
      expect(tester.takeException(), isNull);
    });
  }
  testWidgets('modifier drag zoom keeps the press anchor and does not edit content', (tester) async {
    final backend = FletBackend(pageUri: Uri.parse('http://localhost'),
        assetsDir: '', extensions: [SpatialExtension(), CanvasGesturesExtension()], multiView: false);
    final wrapper = Control(id: 20, type: 'koma_secondary_pan', backend: backend,
        properties: {'zoom_modifiers': ['Alt+Shift'], 'zoom_enabled': true});
    final viewer = Control(id: 21, type: 'koma_spatial_view', parent: wrapper, backend: backend,
        properties: {'camera_zoom': 1.0, 'camera_x': 0.0, 'camera_y': 0.0});
    final scene = Control(id: 22, type: 'Stack', parent: viewer, backend: backend,
        properties: {'width': 2000.0, 'height': 2000.0, 'controls': <Control>[]});
    viewer.properties['content'] = scene;
    wrapper.properties['content'] = viewer;
    await tester.pumpWidget(ChangeNotifierProvider<FletBackend>.value(value: backend,
        child: MaterialApp(home: Scaffold(body: SizedBox(width: 600, height: 400,
            child: CanvasGesturesExtension().createWidget(null, wrapper)!)))));
    await tester.pumpAndSettle();
    final native = tester.widget<InteractiveViewer>(find.byType(InteractiveViewer));
    final camera = native.transformationController!;
    final anchor = camera.toScene(const Offset(200, 150));
    await tester.sendKeyDownEvent(LogicalKeyboardKey.altLeft);
    await tester.sendKeyDownEvent(LogicalKeyboardKey.shiftLeft);
    final gesture = await tester.startGesture(const Offset(200, 150));
    await gesture.moveTo(const Offset(260, 150));
    await tester.pump();
    expect(camera.value.getMaxScaleOnAxis(), greaterThan(1));
    expect((camera.toScene(const Offset(200, 150)) - anchor).distance, lessThan(.001));
    await gesture.up();
    await tester.sendKeyUpEvent(LogicalKeyboardKey.shiftLeft);
    await tester.sendKeyUpEvent(LogicalKeyboardKey.altLeft);
    expect(tester.takeException(), isNull);
  });
  testWidgets('absolute camera shows references on first frame and refits in one patch', (tester) async {
    final backend = FletBackend(pageUri: Uri.parse('http://localhost'),
        assetsDir: '', extensions: [SpatialExtension()], multiView: false);
    const origin = 100288.0;
    const x = origin + 400, y = origin + 400;
    final viewer = Control(id: 10, type: 'koma_spatial_view', backend: backend,
        properties: {'camera_zoom': 1.5, 'camera_x': 300 - (x + 160) * 1.5,
          'camera_y': 200 - (y + 90) * 1.5, 'camera_revision': 0});
    final scene = Control(id: 11, type: 'Stack', parent: viewer, backend: backend,
        properties: {'width': 220576.0, 'height': 220576.0,
          '_internals': {'host_positioned': true}});
    final image = Control(id: 12, type: 'Container', parent: scene, backend: backend,
        properties: {'left': x, 'top': y, 'width': 320.0, 'height': 180.0, 'bgcolor': '#123456'});
    scene.properties['controls'] = [image];
    viewer.properties['content'] = scene;
    Widget build() => ChangeNotifierProvider<FletBackend>.value(value: backend,
        child: MaterialApp(home: Scaffold(body: SizedBox(width: 600, height: 400,
            child: SpatialView(control: viewer)))));
    Future<void> visibleImage() async {
      await tester.pumpAndSettle();
      final rect = tester.getRect(find.byWidgetPredicate((widget) => widget is ContainerControl && widget.control.id == 12));
      expect(rect.left, greaterThanOrEqualTo(0));
      expect(rect.right, lessThanOrEqualTo(600));
      expect(rect.top, greaterThanOrEqualTo(0));
      expect(rect.bottom, lessThanOrEqualTo(400));
      expect(tester.takeException(), isNull);
    }
    await tester.pumpWidget(build());
    await visibleImage();
    viewer.properties.addAll({'camera_zoom': 1.0, 'camera_x': 300 - x - 160,
      'camera_y': 200 - y - 90, 'camera_revision': 1});
    await tester.pumpWidget(build());
    await visibleImage();
  });
  testWidgets('reference camera fits through real Flet invoke methods with pan disabled', (tester) async {
    final backend = FletBackend(pageUri: Uri.parse('http://localhost'),
        assetsDir: '', extensions: [], multiView: false);
    final viewer = Control(id: 1, type: 'InteractiveViewer', backend: backend,
        properties: {
          'pan_enabled': false, 'constrained': false,
          'min_scale': .05, 'max_scale': 16.0,
          'boundary_margin': {'left': 100000.0, 'right': 100000.0, 'top': 100000.0, 'bottom': 100000.0},
          'alignment': {'x': -1.0, 'y': -1.0},
        });
    final scene = Control(id: 2, type: 'Stack', parent: viewer, backend: backend,
        properties: {'width': 3200.0, 'height': 2400.0, 'controls': <Control>[],
          '_internals': {'host_positioned': true}});
    final image = Control(id: 3, type: 'Container', parent: scene, backend: backend,
        properties: {'left': 1000.0, 'top': 800.0, 'width': 320.0, 'height': 180.0, 'bgcolor': '#123456'});
    scene.properties['controls'] = [image];
    viewer.properties['content'] = scene;
    await tester.pumpWidget(ChangeNotifierProvider<FletBackend>.value(value: backend,
        child: MaterialApp(home: Scaffold(body:
        SizedBox(width: 600, height: 400, child: InteractiveViewerControl(control: viewer))))));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    await viewer.invokeMethod('reset', {}, const Duration(seconds: 1));
    await viewer.invokeMethod('zoom', {'factor': 1.5}, const Duration(seconds: 1));
    await viewer.invokeMethod('pan', {'dx': -960.0, 'dy': -756.6666666667, 'dz': 0.0}, const Duration(seconds: 1));
    await tester.pumpAndSettle();
    final native = tester.widget<InteractiveViewer>(find.byType(InteractiveViewer));
    final matrix = native.transformationController!.value;
    expect(matrix.getMaxScaleOnAxis(), closeTo(1.5, .001));
    expect(matrix.storage[12], closeTo(-1440, .001));
    expect(matrix.storage[13], closeTo(-1135, .001));
    expect(tester.takeException(), isNull);
  });
}
