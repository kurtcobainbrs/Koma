import 'package:flutter/widgets.dart';
import 'package:flet/flet.dart';
import 'package:koma_drop/koma_drop.dart' as koma;
import 'package:koma_drop/desktop_menus.dart';
import 'package:koma_drop/secondary_pan.dart';
import 'package:koma_drop/dialog_actions.dart';
import 'package:koma_drop/navigation_view.dart';

// The command-line protocol matches the official Flet 1.0.5 desktop client.
Future<void> main(List<String> args) async {
  await setupDesktop();
  WidgetsFlutterBinding.ensureInitialized();
  if (args.isEmpty) throw ArgumentError('The Flet page URL is required.');
  if (args.length > 1) await File(args[1]).writeAsString('$pid');
  final extension = koma.Extension();
  extension.ensureInitialized();
  runApp(FletApp(
    title: 'Koma', pageUrl: args[0], assetsDir: args.length > 2 ? args[2] : '',
    extensions: [extension, DesktopMenusExtension(), CanvasGesturesExtension(), DialogActionsExtension(), NavigationExtension()], errorsHandler: FletAppErrorsHandler(),
  ));
}
