import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'theme/app_theme.dart';

class GradientApp extends ConsumerWidget {
  const GradientApp({super.key, required this.router});

  final GoRouter router;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp.router(
      title: 'Gradient',
      theme: GradientTheme.light,
      darkTheme: GradientTheme.dark,
      routerConfig: router,
    );
  }
}
