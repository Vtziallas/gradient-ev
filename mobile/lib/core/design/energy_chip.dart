import 'package:flutter/material.dart';

import '../theme/color_tokens.dart';
import '../theme/text_tokens.dart';

enum EnergyClass { regen, efficient, medium, heavy, charge }

extension EnergyClassStyle on EnergyClass {
  Color get color {
    switch (this) {
      case EnergyClass.regen:
        return EnergyColors.regen;
      case EnergyClass.efficient:
        return EnergyColors.efficient;
      case EnergyClass.medium:
        return EnergyColors.medium;
      case EnergyClass.heavy:
        return EnergyColors.heavy;
      case EnergyClass.charge:
        return EnergyColors.charge;
    }
  }

  IconData get icon {
    // Energy classes are never color-only (UX.md §1) — icon differentiates
    // for color-blind users.
    switch (this) {
      case EnergyClass.regen:
        return Icons.arrow_upward;
      case EnergyClass.efficient:
        return Icons.check_circle_outline;
      case EnergyClass.medium:
        return Icons.remove;
      case EnergyClass.heavy:
        return Icons.arrow_downward;
      case EnergyClass.charge:
        return Icons.bolt;
    }
  }
}

/// A chapter chip for the Energy Timeline (UX.md §2 "Route result"
/// wireframe): class + signed delta% + cause icon.
class EnergyChip extends StatelessWidget {
  const EnergyChip({
    super.key,
    required this.energyClass,
    required this.deltaPct,
  });

  final EnergyClass energyClass;
  final double deltaPct;

  @override
  Widget build(BuildContext context) {
    final sign = deltaPct >= 0 ? '+' : '';
    final label = '$sign${deltaPct.toStringAsFixed(1)}%';
    return Semantics(
      label: '${energyClass.name} $label',
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: energyClass.color.withValues(alpha: 0.18),
          borderRadius: BorderRadius.circular(999),
          border: Border.all(color: energyClass.color, width: 1),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(energyClass.icon, size: 14, color: energyClass.color),
            const SizedBox(width: 4),
            Text(
              label,
              style: GradientTextStyles.metricSmall.copyWith(color: energyClass.color),
            ),
          ],
        ),
      ),
    );
  }
}
