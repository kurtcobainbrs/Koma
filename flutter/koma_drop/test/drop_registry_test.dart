import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:koma_drop/drop_registry.dart';

Widget fixture(DropRegistry registry, {double scale = .5, bool overlay = false,
    bool overlap = false, bool reversed = false}) {
  Widget node(String id, double x) => Positioned(
    left: x, top: 100, width: 120, height: 100,
    child: DropAnchor(key: ValueKey(id), nodeId: id,
      child: const ColoredBox(color: Colors.blue)),
  );
  final nodes = [node('first', 100), node('second', overlap ? 100 : 400)];
  return Directionality(textDirection: TextDirection.ltr, child: Align(
    alignment: Alignment.topLeft, child: SizedBox(width: 800, height: 600,
      child: DropScope(registry: registry, child: Stack(children: [
        Positioned.fill(child: InteractiveViewer(
          alignment: Alignment.topLeft, constrained: false,
          boundaryMargin: const EdgeInsets.all(10000),
          transformationController: TransformationController(
            Matrix4.identity()..translateByDouble(50, 40, 0, 1)..scaleByDouble(scale, scale, 1, 1)),
          child: DropAnchor(child: SizedBox(width: 1200, height: 900,
            child: Stack(children: [
              const Positioned.fill(child: ColoredBox(color: Colors.black)),
              ...reversed ? nodes.reversed : nodes,
            ]))),
        )),
        if (overlay) const Positioned(left: 250, top: 80, width: 100, height: 100,
          child: ColoredBox(color: Colors.red)),
      ])),
    ),
  ));
}

void main() {
  testWidgets('Windows DPI does not change logical widget hit coordinates', (tester) async {
    tester.view.devicePixelRatio = 2;
    tester.view.physicalSize = const Size(1600, 1200);
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.view.resetPhysicalSize);
    final registry = DropRegistry();
    await tester.pumpWidget(fixture(registry));
    expect(registry.resolve(const Offset(280, 115), tester.view.viewId)?.nodeId, 'second');
    tester.view.physicalSize = const Size(1200, 900);
    await tester.pump();
    expect(registry.resolve(const Offset(280, 115), tester.view.viewId)?.nodeId, 'second');
  });
  testWidgets('second visible node is resolved using Flutter zoom and pan', (tester) async {
    final registry = DropRegistry();
    await tester.pumpWidget(fixture(registry));
    final result = registry.resolve(const Offset(280, 115), tester.view.viewId);
    expect(result?.nodeId, 'second');
    expect(result?.scenePosition.dx, closeTo(460, .001));
    expect(result?.scenePosition.dy, closeTo(150, .001));
  });

  testWidgets('blank canvas resolves a scene position without a node', (tester) async {
    final registry = DropRegistry();
    await tester.pumpWidget(fixture(registry));
    final result = registry.resolve(const Offset(350, 250), tester.view.viewId);
    expect(result, isNotNull);
    expect(result!.nodeId, isNull);
    expect(result.scenePosition, const Offset(600, 420));
  });

  testWidgets('actual frontmost hit wins after nodes are reordered', (tester) async {
    final registry = DropRegistry();
    await tester.pumpWidget(fixture(registry, overlap: true));
    expect(registry.resolve(const Offset(125, 115), tester.view.viewId)?.nodeId, 'second');
    await tester.pumpWidget(fixture(registry, overlap: true, reversed: true));
    expect(registry.resolve(const Offset(125, 115), tester.view.viewId)?.nodeId, 'first');
  });

  testWidgets('toolbar covering a node is not a canvas drop', (tester) async {
    final registry = DropRegistry();
    await tester.pumpWidget(fixture(registry, overlay: true));
    expect(registry.resolve(const Offset(280, 115), tester.view.viewId), isNull);
  });

  testWidgets('new zoom and layout do not use stale model camera values', (tester) async {
    final registry = DropRegistry();
    await tester.pumpWidget(fixture(registry, scale: 1));
    expect(registry.resolve(const Offset(510, 190), tester.view.viewId)?.nodeId, 'second');
    await tester.pumpWidget(fixture(registry, scale: .5));
    for (var i = 0; i < 10; i++) {
      expect(registry.resolve(const Offset(280, 115), tester.view.viewId)?.nodeId, 'second');
    }
  });

  testWidgets('unmounted and separate canvases cannot receive stale hits', (tester) async {
    final old = DropRegistry();
    await tester.pumpWidget(fixture(old));
    final current = DropRegistry();
    await tester.pumpWidget(KeyedSubtree(key: const ValueKey('new-tab'), child: fixture(current)));
    expect(old.nodes, isEmpty);
    expect(old.scene, isNull);
    expect(old.resolve(const Offset(280, 115), tester.view.viewId), isNull);
    expect(current.resolve(const Offset(280, 115), tester.view.viewId)?.nodeId, 'second');
  });
}
