import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app/app.dart';
import 'app/router.dart';
import 'features/garage/presentation/garage_screen.dart';
import 'features/planning/presentation/home_plan_screen.dart';

void main() {
  final router = buildRouter(
    planScreen: const HomePlanScreen(),
    garageScreen: const GarageScreen(),
  );
  runApp(ProviderScope(child: GradientApp(router: router)));
}
