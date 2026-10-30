import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('motion stacks pass empty-space input through and keep nodes interactive', (tester) async {
    var backgroundClicks = 0;
    var boxDrags = 0;
    var nodeClicks = 0;
    Widget scene({required bool decorated}) {
      final nodes = Stack(children: [
        Positioned(left: 200, top: 100, width: 100, height: 80,
          child: GestureDetector(onTap: () => nodeClicks++,
            child: const ColoredBox(color: Colors.blue))),
      ]);
      final Widget motion = decorated
        ? Container(decoration: const BoxDecoration(), child: nodes)
        : Stack(children: [Positioned.fill(child: nodes)]);
      return MaterialApp(home: Scaffold(body: SizedBox(width: 600, height: 400,
        child: Stack(children: [
          Positioned.fill(child: GestureDetector(
            onTap: () => backgroundClicks++, onPanStart: (_) => boxDrags++,
            child: const ColoredBox(color: Colors.transparent))),
          Positioned.fill(child: motion),
        ]))));
    }
    // Reproduce the lost background input with Flet's decorated Container shape.
    await tester.pumpWidget(scene(decorated: true));
    await tester.tapAt(const Offset(40, 40));
    await tester.dragFrom(const Offset(40, 40), const Offset(120, 80));
    expect(backgroundClicks, 0);
    expect(boxDrags, 0);
    // The layout-only replacement must restore both background gestures.
    await tester.pumpWidget(scene(decorated: false));
    await tester.tapAt(const Offset(40, 40));
    await tester.dragFrom(const Offset(40, 40), const Offset(120, 80));
    expect(backgroundClicks, 1);
    expect(boxDrags, 1);
    await tester.tapAt(const Offset(250, 140));
    expect(nodeClicks, 1);
    expect(backgroundClicks, 1);
  });
}
