import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme/text_tokens.dart';
import '../../garage/presentation/garage_providers.dart';

/// Home/Plan screen skeleton (UX.md §2 "Home / Plan" wireframe). Search and
/// the 3D map are placeholders — real route planning needs the backend API
/// (API.md) and Mapbox integration, both out of scope for this plan (see
/// plan Non-Goals). See this file's task in the plan for the documented
/// cross-feature provider import exception.
class HomePlanScreen extends ConsumerWidget {
  const HomePlanScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final vehiclesAsync = ref.watch(vehiclesProvider);

    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              vehiclesAsync.when(
                loading: () => const _GarageChip(label: 'Loading vehicle…'),
                error: (err, stack) => const _GarageChip(label: 'Vehicle unavailable'),
                data: (vehicles) => _GarageChip(
                  label: vehicles.isEmpty
                      ? 'No vehicle selected'
                      : '⚡ ${vehicles.first.batteryPct.toStringAsFixed(0)}%  ·  ${vehicles.first.displayName}',
                ),
              ),
              const SizedBox(height: 16),
              const TextField(
                decoration: InputDecoration(
                  prefixIcon: Icon(Icons.search),
                  hintText: 'Where to?',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 12),
              const Wrap(
                spacing: 8,
                children: [
                  Chip(label: Text('Home')),
                  Chip(label: Text('Work')),
                  Chip(label: Text('Meteora')),
                ],
              ),
              const SizedBox(height: 16),
              Expanded(
                child: Container(
                  width: double.infinity,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(12),
                    color: Theme.of(context).colorScheme.surfaceContainerHighest,
                  ),
                  child: const Center(child: Text('3D map — coming soon')),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _GarageChip extends StatelessWidget {
  const _GarageChip({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Text(label, style: GradientTextStyles.metricSmall);
  }
}
