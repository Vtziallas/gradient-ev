import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'app_shell.dart';

/// Placeholder for tabs not yet built as their own feature. Replaced
/// task-by-task (garage in Task 6, planning in Task 7 — Settings stays a
/// placeholder beyond this plan).
class _PlaceholderScreen extends StatelessWidget {
  const _PlaceholderScreen(this.label);

  final String label;

  @override
  Widget build(BuildContext context) {
    return Scaffold(body: Center(child: Text('$label — coming soon')));
  }
}

GoRouter buildRouter({required Widget planScreen, required Widget garageScreen}) {
  return GoRouter(
    initialLocation: '/',
    routes: [
      GoRoute(
        path: '/',
        builder: (context, state) => AppShell(
          tabs: [
            AppShellTab(label: 'Plan', icon: Icons.map_outlined, screen: planScreen),
            AppShellTab(label: 'Garage', icon: Icons.directions_car_outlined, screen: garageScreen),
            const AppShellTab(
              label: 'Settings',
              icon: Icons.settings_outlined,
              screen: _PlaceholderScreen('Settings'),
            ),
          ],
        ),
      ),
    ],
  );
}
