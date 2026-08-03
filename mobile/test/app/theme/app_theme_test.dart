import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/app/theme/app_theme.dart';
import 'package:mobile/app/theme/color_tokens.dart';

void main() {
  test('dark theme uses dark-first surface and background tokens', () {
    final theme = GradientTheme.dark;
    expect(theme.brightness, Brightness.dark);
    expect(theme.scaffoldBackgroundColor, GradientColors.darkBackground);
    expect(theme.colorScheme.surface, GradientColors.darkSurface);
  });

  test('light theme uses light surface and background tokens', () {
    final theme = GradientTheme.light;
    expect(theme.brightness, Brightness.light);
    expect(theme.scaffoldBackgroundColor, GradientColors.lightBackground);
    expect(theme.colorScheme.surface, GradientColors.lightSurface);
  });

  test('metric text style uses tabular figures', () {
    expect(
      GradientTheme.dark.textTheme.displayLarge?.fontFeatures,
      contains(const FontFeature.tabularFigures()),
    );
  });
}
