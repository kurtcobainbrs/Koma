import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:koma_drop/media_filter.dart';

void main() {
  testWidgets('matrix keeps transparent pixels and produces neutral media', (tester) async {
    final key = GlobalKey();
    await tester.pumpWidget(MaterialApp(home: Align(alignment: Alignment.topLeft,
        child: RepaintBoundary(key: key, child: MediaColorTransform(
            matrix: const [.299, .587, .114, 0, 0, .299, .587, .114, 0, 0,
                .299, .587, .114, 0, 0, 0, 0, 0, 1, 0],
            child: const SizedBox(width: 20, height: 10, child: Align(alignment: Alignment.topLeft,
                child: ColoredBox(color: Colors.red, child: SizedBox(width: 10, height: 10)))))))));
    await tester.pumpAndSettle();
    final boundary = key.currentContext!.findRenderObject() as RenderRepaintBoundary;
    final image = await tester.runAsync(() => boundary.toImage(pixelRatio: 1));
    final data = (await tester.runAsync(() => image!.toByteData(format: ui.ImageByteFormat.rawRgba)))!;
    expect(data.getUint8(0), data.getUint8(1));
    expect(data.getUint8(1), data.getUint8(2));
    expect(data.getUint8(3), 255);
    expect(data.getUint8(15 * 4 + 3), 0);
    image!.dispose();
  });
}
