import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'app/app.dart';
import 'app/router.dart';
import 'features/garage/presentation/garage_screen.dart';
import 'features/planning/presentation/home_plan_screen.dart';

GoRouter buildAppRouter() => buildRouter(
      planScreen: const HomePlanScreen(),
      garageScreen: const GarageScreen(),
    );

void main() => runApp(ProviderScope(child: GradientApp(router: buildAppRouter())));
