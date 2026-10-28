// Inspect the serialized semantics updates, not just the visible widget tree.
import 'dart:ui' as ui;
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import '../../compat/overlay_boundary.dart';

class RecordingBinding extends AutomatedTestWidgetsFlutterBinding {
  final children = <int, List<int>>{};
  final orphaned = <int>{};

  @override
  ui.SemanticsUpdateBuilder createSemanticsUpdateBuilder() => _Recorder(this);
}

class _Recorder implements ui.SemanticsUpdateBuilder {
  _Recorder(this.binding);
  final RecordingBinding binding;
  final updated = <int>{};

  @override
  dynamic noSuchMethod(Invocation invocation) {
    if (invocation.memberName == #updateNode) {
      final args = invocation.namedArguments;
      final id = args[#id] as int;
      binding.children[id] =
          List<int>.from(args[#childrenInTraversalOrder] as Iterable);
      updated.add(id);
    }
    return null;
  }

  @override
  ui.SemanticsUpdate build() {
    final claimed = binding.children.values.expand((ids) => ids).toSet();
    // The engine's semantics protocol reserves node 0 as the root.
    binding.orphaned
        .addAll(updated.where((id) => id != 0 && !claimed.contains(id)));
    return ui.SemanticsUpdateBuilder().build();
  }

}

void main() {
  final binding = RecordingBinding();
  for (final isolated in [false, true]) {
    testWidgets('dialog overlay semantics (isolated: $isolated)',
        (tester) async {
      binding.children.clear();
      binding.orphaned.clear();
      Widget boundary(Widget child) => isolated ? isolateOverlay(child) : child;
      debugDefaultTargetPlatformOverride = TargetPlatform.windows;
      final semantics = tester.ensureSemantics();
      var value = .3;
      Widget dialog(BuildContext context) {
        return AlertDialog(
            content: StatefulBuilder(builder: (context, setState) {
          return Column(mainAxisSize: MainAxisSize.min, children: [
            boundary(Slider(
                value: value,
                label: '$value',
                onChanged: (next) => setState(() => value = next))),
            Row(mainAxisSize: MainAxisSize.min, children: [
              for (final label in ['First tool', 'Second tool'])
                (isolated ? isolateTooltip : (Widget child) => child)(Tooltip(
                    message: label,
                    child: IconButton(
                        icon: const Icon(Icons.edit), onPressed: () {}))),
            ]),
          ]);
        }));
      }

      await tester.pumpWidget(MaterialApp(home: Builder(builder: (context) {
        return Scaffold(
            body: TextButton(
                onPressed: () =>
                    showDialog<void>(context: context, builder: dialog),
                child: const Text('Open')));
      })));
      await tester.tap(find.text('Open'));
      await tester.pumpAndSettle();
      await tester.drag(find.byType(Slider), const Offset(50, 0));
      await tester.pumpAndSettle();
      expect(value, greaterThan(.3));
      final mouse =
          await tester.createGesture(kind: ui.PointerDeviceKind.mouse);
      await mouse.addPointer();
      for (final button in find.byType(IconButton).evaluate()) {
        await mouse.moveTo(tester.getCenter(find.byWidget(button.widget)));
        await tester.pump(const Duration(seconds: 1));
      }
      await mouse.removePointer();
      await tester.pumpAndSettle();
      semantics.dispose();
      debugDefaultTargetPlatformOverride = null;
      expect(binding.orphaned, isolated ? isEmpty : isNotEmpty,
          reason:
              'Every serialized node must belong to a parent before reaching the Windows AXTree.');
      expect(tester.takeException(), isNull);
    });
  }
}
