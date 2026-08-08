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

  /// A step lighter than [darkSurface] — used for M3's
  /// `surfaceContainerHighest`/`surfaceContainer` roles so containers (e.g.
  /// the map placeholder) read as visibly distinct from a plain surface.
  static const Color darkSurfaceContainer = Color(0xFF232A33);

  /// Muted divider/border tone — between [darkSurface] and [darkOnSurface],
  /// used for M3's `outline`/`outlineVariant` roles so borders read as
  /// subtle dividers rather than full-contrast text.
  static const Color darkOutline = Color(0xFF3A424E);

  static const Color lightBackground = Color(0xFFF7F8FA);
  static const Color lightSurface = Color(0xFFFFFFFF);
  static const Color lightOnSurface = Color(0xFF14171C);
  static const Color lightOnSurfaceMuted = Color(0xFF5B6472);

  /// A step between [lightSurface] and [lightBackground] — used for M3's
  /// `surfaceContainerHighest`/`surfaceContainer` roles so containers (e.g.
  /// the map placeholder) are visibly distinct from the scaffold background.
  static const Color lightSurfaceContainer = Color(0xFFECEFF3);

  /// Muted divider/border tone — between [lightSurface] and
  /// [lightOnSurfaceMuted], used for M3's `outline`/`outlineVariant` roles.
  static const Color lightOutline = Color(0xFFD3D8DE);
}
