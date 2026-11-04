import 'package:flet/src/controls/container.dart';
import 'package:flet/src/flet_backend.dart';
import 'package:flet/src/models/control.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('selection outline passes repeated drags to image; scale handle stays interactive',
      (tester) async {
    final backend = FletBackend(pageUri: Uri.parse('http://localhost'),
        assetsDir: '', extensions: [], multiView: false);
    final border = Control(id: 1, type: 'Container', backend: backend,
        properties: {'ignore_interactions': true, 'bgcolor': '#202020'});
    var selected = false;
    var imageDrags = 0;
    var handleDrags = 0;
    await tester.pumpWidget(MaterialApp(home: Scaffold(body:
        StatefulBuilder(builder: (context, setState) => Align(
            alignment: Alignment.topLeft,
            child: SizedBox(width: 320, height: 180, child: Stack(children: [
              Positioned.fill(child: GestureDetector(
                  behavior: HitTestBehavior.opaque,
                  onPanUpdate: (_) {},
                  onPanEnd: (_) => setState(() { imageDrags++; selected = true; }),
                  child: const ColoredBox(color: Colors.blue))),
              if (selected) Positioned.fill(child: Stack(children: [
                Positioned.fill(child: ContainerControl(control: border)),
                Positioned(right: 0, bottom: 0, width: 20, height: 20,
                    child: GestureDetector(behavior: HitTestBehavior.opaque,
                        onPanUpdate: (_) {}, onPanEnd: (_) { handleDrags++; },
                        child: const SizedBox.expand())),
              ])),
            ])))))));
    for (var i = 0; i < 3; i++) {
      await tester.dragFrom(const Offset(100, 80), const Offset(40, 0));
      await tester.pumpAndSettle();
      expect(imageDrags, i + 1);
    }
    await tester.dragFrom(const Offset(310, 170), const Offset(30, 30));
    await tester.pumpAndSettle();
    expect(handleDrags, 1);
    expect(imageDrags, 3);
    expect(tester.takeException(), isNull);
  });
  for (final zoom in [.5, 1.0, 3.0]) {
    testWidgets('local drag coordinates follow cursor under zoom $zoom', (tester) async {
      var x = 50.0;
      var press = Offset.zero;
      var original = x;
      const imageKey = ValueKey('drag-image');
      await tester.pumpWidget(MaterialApp(home: Scaffold(body:
          StatefulBuilder(builder: (context, setState) => Align(
              alignment: Alignment.topLeft,
              child: Transform.scale(scale: zoom, alignment: Alignment.topLeft,
                  child: SizedBox(width: 300, height: 200,
                      child: Stack(children: [Positioned(left: x, top: 40, width: 100, height: 100,
                          child: GestureDetector(
                              onPanDown: (details) { press = details.localPosition; original = x; },
                              onPanUpdate: (details) => setState(() {
                                    x = original + details.localPosition.dx - press.dx;
                                  }),
                              child: const ColoredBox(key: imageKey, color: Colors.blue)))]))))))));
      final start = tester.getCenter(find.byKey(imageKey));
      final gesture = await tester.startGesture(start);
      for (final distance in [40.0, 80.0, 120.0]) {
        await gesture.moveTo(start + Offset(distance, 0));
        await tester.pump();
        expect(x, closeTo(50 + distance / zoom, .001));
      }
      await gesture.up();
      expect(tester.takeException(), isNull);
    });
  }
}
