import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme/text_tokens.dart';
import 'garage_providers.dart';

class GarageScreen extends ConsumerWidget {
  const GarageScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final vehiclesAsync = ref.watch(vehiclesProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Garage')),
      body: vehiclesAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (err, stack) => Center(child: Text('Could not load vehicles: $err')),
        data: (vehicles) => ListView.builder(
          itemCount: vehicles.length,
          itemBuilder: (context, index) {
            final v = vehicles[index];
            return ListTile(
              title: Text(v.displayName),
              subtitle: Text('${v.usableKwh.toStringAsFixed(1)} kWh usable'),
              trailing: Text(
                '${v.batteryPct.toStringAsFixed(0)}%',
                style: GradientTextStyles.metricSmall,
              ),
            );
          },
        ),
      ),
    );
  }
}
