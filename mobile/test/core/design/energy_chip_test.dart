import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/app/theme/app_theme.dart';
import 'package:mobile/core/design/energy_chip.dart';

void main() {
  testWidgets('EnergyChip shows signed positive delta and an icon', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: EnergyChip(energyClass: EnergyClass.regen, deltaPct: 2.4),
        ),
      ),
    );

    expect(find.text('+2.4%'), findsOneWidget);
    expect(find.byIcon(Icons.arrow_upward), findsOneWidget);
  });

  testWidgets('EnergyChip shows negative delta without a plus sign', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: EnergyChip(energyClass: EnergyClass.heavy, deltaPct: -5.8),
        ),
      ),
    );

    expect(find.text('-5.8%'), findsOneWidget);
    expect(find.byIcon(Icons.arrow_downward), findsOneWidget);
  });

  testWidgets('EnergyChip golden — light theme', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: GradientTheme.light,
        home: const Scaffold(
          body: Center(
            child: EnergyChip(energyClass: EnergyClass.efficient, deltaPct: -1.3),
          ),
        ),
      ),
    );
    await expectLater(
      find.byType(EnergyChip),
      matchesGoldenFile('goldens/energy_chip_light.png'),
    );
  });

  testWidgets('EnergyChip golden — dark theme', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: GradientTheme.dark,
        home: const Scaffold(
          body: Center(
            child: EnergyChip(energyClass: EnergyClass.efficient, deltaPct: -1.3),
          ),
        ),
      ),
    );
    await expectLater(
      find.byType(EnergyChip),
      matchesGoldenFile('goldens/energy_chip_dark.png'),
    );
  });
}
