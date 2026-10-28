// Keep portal children inside their owning subtree. Preserve semantics, focus,
// keyboard interaction and value indicators; never disable accessibility.
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

Widget isolateOverlay(Widget child) {
  if (defaultTargetPlatform != TargetPlatform.windows) return child;
  return Overlay.wrap(
    alwaysSizeToContent: true,
    clipBehavior: Clip.none,
    child: Semantics(container: true, child: child),
  );
}

Widget isolateTooltip(Widget child) {
  if (defaultTargetPlatform != TargetPlatform.windows) return child;
  // Tooltips retain the window overlay so their text can extend past the button.
  // A boundary prevents traversal-parent identifiers merging with the anchor.
  return Semantics(container: true, child: child);
}
