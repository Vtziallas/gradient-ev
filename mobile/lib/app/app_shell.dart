import 'package:flutter/material.dart';

/// Bottom-nav shell for the top-level tabs (MobileArchitecture.md §2).
/// Deep-linkable per-tab routes (e.g. `/route/:id`) land in later plans;
/// each tab is a single screen for now.
class AppShellTab {
  const AppShellTab({required this.label, required this.icon, required this.screen});

  final String label;
  final IconData icon;
  final Widget screen;
}

class AppShell extends StatefulWidget {
  const AppShell({super.key, required this.tabs});

  final List<AppShellTab> tabs;

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _index,
        children: [for (final tab in widget.tabs) tab.screen],
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _index,
        onTap: (i) => setState(() => _index = i),
        items: [
          for (final tab in widget.tabs)
            BottomNavigationBarItem(icon: Icon(tab.icon), label: tab.label),
        ],
      ),
    );
  }
}
