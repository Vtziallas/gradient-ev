import 'package:flutter/material.dart';

import '../../core/theme/color_tokens.dart';
import '../../core/theme/text_tokens.dart';

class GradientTheme {
  const GradientTheme._();

  static ThemeData get dark => _themeFrom(
        brightness: Brightness.dark,
        background: GradientColors.darkBackground,
        surface: GradientColors.darkSurface,
        surfaceContainer: GradientColors.darkSurfaceContainer,
        onSurface: GradientColors.darkOnSurface,
        onSurfaceMuted: GradientColors.darkOnSurfaceMuted,
        outline: GradientColors.darkOutline,
      );

  static ThemeData get light => _themeFrom(
        brightness: Brightness.light,
        background: GradientColors.lightBackground,
        surface: GradientColors.lightSurface,
        surfaceContainer: GradientColors.lightSurfaceContainer,
        onSurface: GradientColors.lightOnSurface,
        onSurfaceMuted: GradientColors.lightOnSurfaceMuted,
        outline: GradientColors.lightOutline,
      );

  static ThemeData _themeFrom({
    required Brightness brightness,
    required Color background,
    required Color surface,
    required Color surfaceContainer,
    required Color onSurface,
    required Color onSurfaceMuted,
    required Color outline,
  }) {
    final colorScheme = ColorScheme(
      brightness: brightness,
      primary: EnergyColors.charge,
      onPrimary: Colors.white,
      secondary: EnergyColors.efficient,
      onSecondary: Colors.black,
      error: EnergyColors.heavy,
      onError: Colors.white,
      surface: surface,
      onSurface: onSurface,
      surfaceContainerHighest: surfaceContainer,
      surfaceContainer: surfaceContainer,
      outline: outline,
      outlineVariant: outline,
    );

    return ThemeData(
      brightness: brightness,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: background,
      textTheme: TextTheme(
        displayLarge: GradientTextStyles.metricLarge.copyWith(color: onSurface),
        labelLarge: GradientTextStyles.metricSmall.copyWith(color: onSurface),
        bodyMedium: GradientTextStyles.body.copyWith(color: onSurface),
        labelMedium: GradientTextStyles.label.copyWith(color: onSurfaceMuted),
      ),
      useMaterial3: true,
    );
  }
}
