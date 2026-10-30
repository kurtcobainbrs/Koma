import 'dart:convert';
import 'dart:io';
import 'package:flet/flet.dart';
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

void main() {
  testWidgets('Windows real editor stops inactive animatic layout and keeps canvas interactive', (tester) async {
    debugDefaultTargetPlatformOverride = TargetPlatform.windows;
    addTearDown(() => debugDefaultTargetPlatformOverride = null);
    final semantics = tester.ensureSemantics();
    final fixture = jsonDecode(File('../../build/workflow-checks/animatic-layout.json').readAsStringSync())['production'];
    final backend = FletBackend(pageUri: Uri.parse('http://localhost'), assetsDir: '', extensions: [], multiView: false);
    await tester.binding.setSurfaceSize(const Size(1600, 900));
    final root = Control.fromMap(fixture['workspace'], backend);
    await tester.pumpWidget(ChangeNotifierProvider<FletBackend>.value(value: backend,
      child: MaterialApp(home: Scaffold(body: ControlWidget(control: root)))));
    await tester.pump();
    expect(tester.takeException(), isNull);
    final controller = tester.widget<InteractiveViewer>(find.byType(InteractiveViewer)).transformationController;
    for (var cycle = 0; cycle < 3; cycle++) {
      for (final active in [false, true]) {
        for (final id in fixture['mode_ids'].values) {
          backend.controlsIndex.get(id)!.updateProperties({'visible': active}, python: false, notify: true);
        }
        await tester.pump();
        expect(tester.takeException(), isNull);
        expect(find.byKey(const ValueKey('real-preview')), active ? findsOneWidget : findsNothing);
        expect(tester.widget<InteractiveViewer>(find.byType(InteractiveViewer)).transformationController, same(controller));
      }
    }
    for (final id in fixture['mode_ids'].values) {
      backend.controlsIndex.get(id)!.updateProperties({'visible': false}, python: false, notify: true);
    }
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));
    expect(tester.takeException(), isNull);
    expect(tester.binding.hasScheduledFrame, isFalse);
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.binding.setSurfaceSize(null);
    backend.dispose();
    semantics.dispose();
    debugDefaultTargetPlatformOverride = null;
  }, timeout: const Timeout(Duration(seconds: 30)));
  testWidgets('production animatic layout keeps timeline inside the viewport', (tester) async {
    final fixture = jsonDecode(File('../../build/workflow-checks/animatic-layout.json').readAsStringSync());
    final backend = FletBackend(pageUri: Uri.parse('http://localhost'), assetsDir: '',
      extensions: [], multiView: false);
    final root = Control.fromMap(fixture['control'], backend);
    for (final size in [const Size(1600, 900), const Size(960, 600)]) {
      await tester.binding.setSurfaceSize(size);
      await tester.pumpWidget(ChangeNotifierProvider<FletBackend>.value(value: backend,
        child: MaterialApp(home: Scaffold(body: ControlWidget(control: root)))));
      await tester.pump();
      expect(tester.takeException(), isNull);
      final header = tester.getRect(find.byKey(const ValueKey('header')));
      final preview = tester.getRect(find.byKey(const ValueKey('preview')));
      final timeline = tester.getRect(find.byKey(const ValueKey('timeline')));
      final inspector = tester.getRect(find.byKey(const ValueKey('inspector')));
      expect(timeline.height, fixture['timeline_height']);
      expect(timeline.left, 0);
      expect(timeline.right, size.width);
      expect(inspector.bottom, lessThanOrEqualTo(timeline.top));
      expect(preview.right, lessThanOrEqualTo(inspector.left));
      expect(timeline.bottom, lessThanOrEqualTo(size.height));
      expect(timeline.top, greaterThanOrEqualTo(preview.bottom));
      expect(preview.top, greaterThanOrEqualTo(header.bottom));
      expect(preview.height, greaterThan(0));
    }
    final controller = tester.widget<InteractiveViewer>(find.byType(InteractiveViewer)).transformationController!;
    final camera = controller.value.clone()..setTranslationRaw(12, 34, 0);
    controller.value = camera;
    final animatic = backend.controlsIndex.get(fixture['mode_ids']['animatic'])!;
    for (var cycle = 0; cycle < 4; cycle++) {
      for (final active in [true, false]) {
        animatic.updateProperties({'visible': active}, python: false, notify: true);
        await tester.pump();
        expect(tester.takeException(), isNull);
        final current = tester.widget<InteractiveViewer>(find.byType(InteractiveViewer)).transformationController!;
        expect(identical(current, controller), isTrue);
        expect(current.value, camera);
        expect(find.byKey(const ValueKey('preview')), active ? findsOneWidget : findsNothing);
        final hit = find.byKey(const ValueKey('canvas-hit'));
        final canvasTarget = tester.renderObject(hit);
        final targets = tester.hitTestOnBinding(tester.getCenter(hit)).path;
        expect(targets.any((entry) => identical(entry.target, canvasTarget)), !active);
      }
    }
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.binding.setSurfaceSize(null);
    backend.dispose();
  });
  testWidgets('card sockets match wire anchors', (tester) async {
    final fixture = jsonDecode(File('../../build/workflow-checks/animatic-layout.json').readAsStringSync());
    final backend = FletBackend(pageUri: Uri.parse('http://localhost'), assetsDir: '',
      extensions: [], multiView: false);
    Future<void> mount(Map<String, dynamic> data, Size size) async {
      await tester.binding.setSurfaceSize(size);
      await tester.pumpWidget(ChangeNotifierProvider<FletBackend>.value(value: backend,
        child: MaterialApp(theme: ThemeData(useMaterial3: true),
          home: Scaffold(body: ControlWidget(control: Control.fromMap(data, backend))))));
      await tester.pump();
      expect(tester.takeException(), isNull);
    }
    await mount(fixture['production']['cards'], const Size(1600, 900));
    for (var i = 0; i < fixture['production']['ports'].length; i++) {
      final card = tester.getRect(find.byKey(ValueKey('card-$i')));
      final output = tester.getRect(find.byKey(ValueKey('output-$i')));
      final anchor = fixture['production']['ports'][i];
      expect(output.center.dx - card.left, closeTo(anchor[0], .01));
      expect(output.center.dy - card.top, closeTo(anchor[1], .01));
    }
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.binding.setSurfaceSize(null);
    backend.dispose();
  }, timeout: const Timeout(Duration(seconds: 25)));
}
