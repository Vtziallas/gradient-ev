import 'package:flutter/material.dart';

/// Typography tokens. UX.md §1 calls for a tabular-numerals display face
/// for all metrics ("numbers are the product") — enforced here via
/// [FontFeature.tabularFigures] rather than a bespoke font.
class GradientTextStyles {
  const GradientTextStyles._();

  static const TextStyle metricLarge = TextStyle(
    fontSize: 40,
    fontWeight: FontWeight.w700,
    fontFeatures: [FontFeature.tabularFigures()],
    height: 1.05,
  );

  static const TextStyle metricSmall = TextStyle(
    fontSize: 16,
    fontWeight: FontWeight.w600,
    fontFeatures: [FontFeature.tabularFigures()],
  );

  static const TextStyle body = TextStyle(
    fontSize: 15,
    fontWeight: FontWeight.w400,
  );

  static const TextStyle label = TextStyle(
    fontSize: 13,
    fontWeight: FontWeight.w500,
    letterSpacing: 0.2,
  );
}
