import 'package:flutter/material.dart';

/// Energy palette — contract with server-side energy classes and renderers.
/// Source: docs/UX.md §1. Same accent hues used for light and dark; only
/// surface/text tokens differ per theme (formal contrast-on-terrain
/// validation deferred — out of scope for this skeleton).
class EnergyColors {
  const EnergyColors._();

  static const Color regen = Color(0xFF2FBF71);
  static const Color efficient = Color(0xFFE8C547);
  static const Color medium = Color(0xFFF28C28);
  static const Color heavy = Color(0xFFE4572E);
  static const Color charge = Color(0xFF3D9BE9);
}

/// Surface/background tokens. Dark-first per UX.md §1 ("driving context").
class GradientColors {
  const GradientColors._();

  static const Color darkBackground = Color(0xFF0E1116);
  static const Color darkSurface = Color(0xFF181C22);
  static const Color darkOnSurface = Color(0xFFF2F4F7);
  static const Color darkOnSurfaceMuted = Color(0xFF9AA4B2);

  static const Color lightBackground = Color(0xFFF7F8FA);
  static const Color lightSurface = Color(0xFFFFFFFF);
  static const Color lightOnSurface = Color(0xFF14171C);
  static const Color lightOnSurfaceMuted = Color(0xFF5B6472);
}
