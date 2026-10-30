import 'package:flet/flet.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

void main() {
  testWidgets('changing input capture preserves descendant native state', (tester) async {
    final backend = FletBackend(pageUri: Uri.parse('http://localhost'), assetsDir: '', extensions: [], multiView: false);
    final root = Control.fromMap({'_c': 'Container', '_i': 80001, 'ignore_interactions': false,
      'content': {'_c': 'TextField', '_i': 80002, 'key': 'preserved-input', 'value': 'Sample'}}, backend);
    await tester.pumpWidget(ChangeNotifierProvider<FletBackend>.value(value: backend,
      child: MaterialApp(home: Scaffold(body: ControlWidget(control: root)))));
    final finder = find.byType(TextField);
    final initial = tester.state(finder);
    for (final ignored in [true, false, true, false]) {
      root.updateProperties({'ignore_interactions': ignored}, python: false, notify: true);
      await tester.pump();
      expect(tester.takeException(), isNull);
      expect(tester.state(finder), same(initial));
    }
    await tester.pumpWidget(const SizedBox.shrink());
    backend.dispose();
  });
}
