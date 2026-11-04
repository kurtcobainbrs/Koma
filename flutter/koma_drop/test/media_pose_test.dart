import 'package:flet/src/flet_backend.dart';
import 'package:flet/src/models/control.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:koma_drop/media_pose.dart';
import 'package:flutter/gestures.dart';

class PoseBackend extends FletBackend {
  PoseBackend() : super(pageUri: Uri.parse('http://localhost'), assetsDir: '', extensions: [], multiView: false);
  final events = <Map<String, dynamic>>[];
  @override
  void triggerControlEvent(Control control, String eventName, [dynamic data]) => events.add({'name': eventName, 'data': data});
}

void main() {
  test('linear and held evaluation matches normalized project poses', () {
    final keys = [
      {'time': 0.0, 'x': 0.0, 'y': 0.0, 'scale': 1.0, 'rotation': 0.0, 'interpolation': 'linear'},
      {'time': 1.0, 'x': 1.0, 'y': 1.0, 'scale': 3.0, 'rotation': 180.0, 'interpolation': 'linear'},
    ];
    expect(evaluateMediaPose(keys, .5, []), [.5, .5, 2, 90]);
    keys.first['interpolation'] = 'hold';
    expect(evaluateMediaPose(keys, .5, []), [0, 0, 1, 0]);
  });

  testWidgets('immediate hover movement supports X constraint and Enter confirmation', (tester) async {
    final backend = PoseBackend();
    final control = Control(id: 1, type: 'koma_media_pose', backend: backend,
        properties: {'editing': true, 'tool': 'move', 'generation': 1, 'start_request': 1});
    await tester.pumpWidget(ChangeNotifierProvider<FletBackend>.value(value: backend,
        child: MaterialApp(home: Align(alignment: Alignment.topLeft,
            child: SizedBox(width: 400, height: 300, child: MediaPoseView(control: control))))));
    await tester.pump();
    final mouse = await tester.createGesture(kind: PointerDeviceKind.mouse);
    await mouse.addPointer(location: const Offset(100, 100));
    await mouse.moveTo(const Offset(100, 100));
    await tester.pump();
    await mouse.moveTo(const Offset(140, 130));
    await tester.pump();
    await tester.sendKeyEvent(LogicalKeyboardKey.keyX);
    await tester.sendKeyEvent(LogicalKeyboardKey.enter);
    await tester.pump();
    final event = backend.events.singleWhere((event) => event['name'] == 'commit');
    expect(event['data']['x'], closeTo(.1, .0001));
    expect(event['data']['y'], 0);
    await mouse.removePointer();
  });

  testWidgets('animation advances between Python updates at display time', (tester) async {
    final backend = PoseBackend();
    final control = Control(id: 1, type: 'koma_media_pose', backend: backend,
        properties: {'playing': true, 'generation': 1, 'maximum_time': 1.0, 'keyframes': [
          {'time': 0.0, 'x': 0.0, 'y': 0.0, 'scale': 1.0, 'rotation': 0.0, 'interpolation': 'linear'},
          {'time': 1.0, 'x': 1.0, 'y': 0.0, 'scale': 1.0, 'rotation': 0.0, 'interpolation': 'linear'},
        ]});
    await tester.pumpWidget(ChangeNotifierProvider<FletBackend>.value(value: backend,
        child: MaterialApp(home: SizedBox(width: 400, height: 300, child: MediaPoseView(control: control)))));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 16));
    double translation() => tester.widgetList<Transform>(find.byType(Transform))
        .map((widget) => widget.transform.storage[12]).fold(0.0, (a, b) => a + b);
    final first = translation();
    await tester.pump(const Duration(milliseconds: 8));
    expect(translation(), greaterThan(first));
    expect(backend.events.where((event) => event['name'] == 'commit'), isEmpty);
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('modal move continues outside the preview and confirms outside it', (tester) async {
    final backend = PoseBackend();
    final control = Control(id: 1, type: 'koma_media_pose', backend: backend,
        properties: {'editing': true, 'tool': 'move', 'generation': 1, 'start_request': 1});
    await tester.pumpWidget(ChangeNotifierProvider<FletBackend>.value(value: backend,
        child: MaterialApp(home: Align(alignment: Alignment.topLeft,
            child: SizedBox(width: 400, height: 300, child: MediaPoseView(control: control))))));
    await tester.pump();
    final mouse = await tester.createGesture(kind: PointerDeviceKind.mouse);
    await mouse.addPointer(location: const Offset(100, 100));
    await mouse.moveTo(const Offset(100, 100));
    await tester.pump();
    await mouse.moveTo(const Offset(550, 120));
    await tester.pump();
    await mouse.down(const Offset(550, 120));
    await mouse.up();
    await tester.pump();
    final event = backend.events.singleWhere((event) => event['name'] == 'commit');
    expect(event['data']['x'], closeTo(1.125, .0001));
    await mouse.removePointer();
    await tester.pumpWidget(const SizedBox());
  });
  for (final tool in ['move', 'scale', 'rotate']) {
    testWidgets('$tool previews locally and confirms only once', (tester) async {
      final backend = PoseBackend();
      final control = Control(id: 1, type: 'koma_media_pose', backend: backend,
          properties: {'editing': true, 'tool': tool, 'generation': 4, 'rect': [0.0, 0.0, 1.0, 1.0]});
      control.properties['content'] = Control(id: 2, type: 'Container', backend: backend, parent: control,
          properties: {'bgcolor': '#FF0000'});
      await tester.pumpWidget(ChangeNotifierProvider<FletBackend>.value(value: backend,
          child: MaterialApp(home: Align(alignment: Alignment.topLeft,
              child: SizedBox(width: 400, height: 300, child: MediaPoseView(control: control))))));
      await tester.pumpAndSettle();
      final gesture = await tester.startGesture(const Offset(100, 100));
      for (var step = 1; step <= 10; step++) {
        await gesture.moveTo(Offset(100 + step * 4, 100));
        await tester.pump();
      }
      expect(backend.events.where((e) => e['name'] == 'begin').length, 1);
      expect(backend.events.where((e) => e['name'] == 'commit'), isEmpty);
      expect(control.properties['x'], isNull);
      await gesture.up();
      await tester.pump();
      final commits = backend.events.where((e) => e['name'] == 'commit').toList();
      expect(commits.length, 1);
      final data = commits.single['data'] as Map;
      expect(data['generation'], 4);
      if (tool == 'move') expect(data['x'], closeTo(.1, .0001));
      if (tool == 'scale') expect(data['scale'], greaterThan(1));
      if (tool == 'rotate') expect(data['rotation'], closeTo(36, .0001));
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('Escape cancels the native gesture without confirming', (tester) async {
    final backend = PoseBackend();
    final control = Control(id: 1, type: 'koma_media_pose', backend: backend,
        properties: {'editing': true, 'tool': 'move', 'generation': 1});
    await tester.pumpWidget(ChangeNotifierProvider<FletBackend>.value(value: backend,
        child: MaterialApp(home: SizedBox(width: 400, height: 300, child: MediaPoseView(control: control)))));
    await tester.pumpAndSettle();
    final gesture = await tester.startGesture(const Offset(100, 100));
    await gesture.moveBy(const Offset(60, 0));
    await tester.pump();
    await tester.sendKeyEvent(LogicalKeyboardKey.escape);
    await gesture.up();
    await tester.pump();
    expect(backend.events.where((e) => e['name'] == 'commit'), isEmpty);
    expect(backend.events.where((e) => e['name'] == 'cancel').length, 1);
  });
}
