# Gradient Mobile Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the Flutter mobile app's foundation — project bootstrap, design tokens/theme, an app shell with navigation, and two vertical feature slices (garage, planning) built against fake in-memory data — so the clean-architecture pattern from MobileArchitecture.md is proven end-to-end and later plans can add real features against a working skeleton.

**Architecture:** Flutter + Riverpod (classic `Provider`/`FutureProvider`, no codegen — see Non-Goals), feature-first clean architecture (`domain` / `data` / `presentation` per feature) exactly as laid out in MobileArchitecture.md §2, `go_router` for top-level routing wrapping a bottom-nav `AppShell`. No backend exists yet (the FastAPI layer is a separate, not-yet-started plan), so this plan's data layer is entirely in-memory fakes.

**Tech Stack:** Flutter 3.27 (stable channel), Dart 3.6, `flutter_riverpod`, `go_router`, `dio`, `flutter_test` (unit/widget/golden — no extra packages).

## Global Constraints

- Project root: `mobile/` (sibling to `backend/` and `docs/`). App code in `mobile/lib/`, tests in `mobile/test/`, mirroring `lib/`'s folder structure 1:1 (e.g. `lib/app/theme/app_theme.dart` → `test/app/theme/app_theme_test.dart`).
- Folder structure and dependency rule per MobileArchitecture.md §2: `app/` (bootstrap, router, theme), `core/` (shared kernel, kept small), `features/<name>/{domain,data,presentation}/`. Presentation → domain ← data. Features import `core` and other features' **domain** interfaces only — one documented exception exists in Task 7 (see that task's note); no other cross-feature presentation imports are permitted.
- Energy palette (UX.md §1, exact hex, same values for light and dark accents in this skeleton): `regen #2FBF71 · efficient #E8C547 · medium #F28C28 · heavy #E4572E · charge #3D9BE9`. Energy classes are never color-only — every energy-classed UI element pairs color with an icon (UX.md §1, accessibility).
- Dark-first: the dark theme is the primary design target (UX.md §1 "driving context").
- All metric/number text (battery %, kWh, distances) uses a tabular-numerals text style (`FontFeature.tabularFigures()`), per UX.md §1 "numbers are the product".
- State management: Riverpod `Provider`/`FutureProvider`/`ConsumerWidget` (classic API). No `@riverpod` codegen, no `build_runner` anywhere in this plan — see Non-Goals.
- No real network calls. `ApiClient` (Task 4) exists and is tested, but no feature wires it to a live endpoint yet — features use in-memory fake repositories.
- Run everything from `mobile/`: `flutter pub get`, `flutter test <path>`, `flutter analyze`. **`flutter analyze` must be clean before every commit.**
- Commit messages: `feat(mobile): …` / `test(mobile): …`, mirroring the backend's `feat(engine)`/`test(engine)` convention.

## Non-Goals (explicitly deferred — do not implement in this plan)

- **Mapbox 3D terrain / route rendering** (`route3d` feature) — needs API keys and native SDK setup; `HomePlanScreen`'s map area is a static placeholder container.
- **Drive mode, voice cues, background location, Mapbox Navigation.**
- **Local persistence (Drift/SQLite) and the offline outbox sync pattern** — deferred until offline behavior is actually being built, to avoid taking on a native `sqlite3` binary dependency in a foundational skeleton plan. `core/db/` is not created here.
- **`freezed` / `riverpod_generator` codegen** — this plan uses plain immutable Dart classes and classic Riverpod providers instead. Revisit when a domain model actually needs union types, or when the team wants codegen ergonomics badly enough to pay the `build_runner` tax.
- **Auth, charging, trips/history, community, gamification features; Settings beyond a nav placeholder.**
- **Real API integration** — `FakeVehicleRepository` stands in until the FastAPI backend (a separate future plan) exists and a `DioVehicleRepository` can be added.
- Formal cross-platform golden-image CI calibration — the Task 3 goldens are generated on the implementer's machine. Flutter's widget-test font rendering is normally OS-independent (fixed test font, no real system fonts loaded), but flag it if CI ever runs on a materially different Flutter version and goldens need regenerating.

## File Structure

```
mobile/
├── pubspec.yaml                                  # flutter_riverpod, go_router, dio added (Task 1)
├── analysis_options.yaml                         # flutter create default (flutter_lints)
├── lib/
│   ├── main_dev.dart                             # entrypoint (Task 1, rewired Task 5 & 7)
│   ├── app/
│   │   ├── app.dart                              # GradientApp — MaterialApp.router (Task 5)
│   │   ├── app_shell.dart                        # bottom-nav IndexedStack shell (Task 5)
│   │   ├── router.dart                           # go_router config (Task 5)
│   │   └── theme/
│   │       ├── color_tokens.dart                 # EnergyColors, GradientColors (Task 2)
│   │       ├── text_tokens.dart                  # GradientTextStyles (Task 2)
│   │       └── app_theme.dart                    # GradientTheme.light/.dark (Task 2)
│   ├── core/
│   │   ├── design/
│   │   │   └── energy_chip.dart                  # EnergyClass, EnergyChip widget (Task 3)
│   │   └── network/
│   │       ├── api_flavor.dart                   # ApiFlavor enum + baseUrl (Task 4)
│   │       └── api_client.dart                   # ApiClient, applyAuthHeader (Task 4)
│   └── features/
│       ├── garage/
│       │   ├── domain/
│       │   │   ├── vehicle.dart                  # Vehicle entity (Task 6)
│       │   │   └── vehicle_repository.dart        # VehicleRepository interface (Task 6)
│       │   ├── data/
│       │   │   └── fake_vehicle_repository.dart   # in-memory impl (Task 6)
│       │   └── presentation/
│       │       ├── garage_providers.dart          # vehicleRepositoryProvider, vehiclesProvider (Task 6)
│       │       └── garage_screen.dart             # GarageScreen (Task 6)
│       └── planning/
│           └── presentation/
│               └── home_plan_screen.dart          # HomePlanScreen (Task 7)
└── test/                                          # mirrors lib/ 1:1, see per-task Test: paths
```

---

### Task 1: Project bootstrap

**Files:**
- Create: `mobile/` (via `flutter create`)
- Modify: `mobile/pubspec.yaml` (add `flutter_riverpod`, `go_router`, `dio`)
- Create: `mobile/lib/main_dev.dart`
- Delete: `mobile/lib/main.dart`, `mobile/test/widget_test.dart`
- Test: `mobile/test/main_dev_test.dart`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: a working Flutter project at `mobile/` with `flutter_riverpod`, `go_router`, `dio` resolvable, and `GradientDevApp` (a throwaway smoke-test widget, replaced in Task 5).

- [ ] **Step 1: Scaffold the Flutter project**

Run from the repo root:

```bash
flutter create --platforms=android,ios --org com.gradientev --project-name mobile mobile
```

- [ ] **Step 2: Verify the default scaffold builds and tests**

```bash
cd mobile
flutter test
```

Expected: 1 test passed (the default counter-app widget test) — this only confirms the toolchain works before we replace it.

- [ ] **Step 3: Add dependencies**

```bash
flutter pub add flutter_riverpod go_router dio
```

Expected: `pubspec.yaml`'s `dependencies:` section gains `flutter_riverpod`, `go_router`, `dio` with resolved version constraints; `flutter pub get` runs as part of `pub add` and succeeds.

- [ ] **Step 4: Create the folder skeleton**

```bash
mkdir -p lib/app/theme lib/core/design lib/core/network \
  lib/features/garage/domain lib/features/garage/data lib/features/garage/presentation \
  lib/features/planning/presentation \
  test/app/theme test/core/design test/core/network \
  test/features/garage/data test/features/garage/presentation \
  test/features/planning/presentation
```

(Run from `mobile/`.)

- [ ] **Step 5: Write the failing test**

`mobile/test/main_dev_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/main_dev.dart';

void main() {
  testWidgets('GradientDevApp renders bootstrap placeholder', (tester) async {
    await tester.pumpWidget(const ProviderScope(child: GradientDevApp()));
    expect(find.text('Gradient — bootstrap OK'), findsOneWidget);
  });
}
```

- [ ] **Step 6: Run test to verify it fails**

Run: `flutter test test/main_dev_test.dart`
Expected: FAIL — `lib/main_dev.dart` does not exist (or `GradientDevApp` is undefined).

- [ ] **Step 7: Implement `main_dev.dart`**

`mobile/lib/main_dev.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

void main() {
  runApp(const ProviderScope(child: GradientDevApp()));
}

class GradientDevApp extends StatelessWidget {
  const GradientDevApp({super.key});

  @override
  Widget build(BuildContext context) {
    return const MaterialApp(
      title: 'Gradient (dev)',
      home: Scaffold(
        body: Center(child: Text('Gradient — bootstrap OK')),
      ),
    );
  }
}
```

- [ ] **Step 8: Run test to verify it passes**

Run: `flutter test test/main_dev_test.dart`
Expected: 1 PASS

- [ ] **Step 9: Remove the default template files**

```bash
rm lib/main.dart test/widget_test.dart
```

- [ ] **Step 10: Analyze and commit**

```bash
flutter analyze
git add mobile
git commit -m "feat(mobile): bootstrap Flutter project with core dependencies"
```

Expected: `flutter analyze` reports "No issues found!".

---

### Task 2: Design tokens & theme

**Files:**
- Create: `mobile/lib/app/theme/color_tokens.dart`
- Create: `mobile/lib/app/theme/text_tokens.dart`
- Create: `mobile/lib/app/theme/app_theme.dart`
- Test: `mobile/test/app/theme/app_theme_test.dart`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `EnergyColors` (regen/efficient/medium/heavy/charge), `GradientColors` (dark/light background/surface/onSurface/onSurfaceMuted), `GradientTextStyles` (metricLarge/metricSmall/body/label), `GradientTheme.dark`/`GradientTheme.light` (`ThemeData`) — consumed by Task 3 (chip colors/text style), Task 5 (`MaterialApp.router` theme/darkTheme), Task 6 (metric text style).

- [ ] **Step 1: Write the failing test**

`mobile/test/app/theme/app_theme_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/app/theme/app_theme.dart';
import 'package:mobile/app/theme/color_tokens.dart';

void main() {
  test('dark theme uses dark-first surface and background tokens', () {
    final theme = GradientTheme.dark;
    expect(theme.brightness, Brightness.dark);
    expect(theme.scaffoldBackgroundColor, GradientColors.darkBackground);
    expect(theme.colorScheme.surface, GradientColors.darkSurface);
  });

  test('light theme uses light surface and background tokens', () {
    final theme = GradientTheme.light;
    expect(theme.brightness, Brightness.light);
    expect(theme.scaffoldBackgroundColor, GradientColors.lightBackground);
    expect(theme.colorScheme.surface, GradientColors.lightSurface);
  });

  test('metric text style uses tabular figures', () {
    expect(
      GradientTheme.dark.textTheme.displayLarge?.fontFeatures,
      contains(const FontFeature.tabularFigures()),
    );
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/app/theme/app_theme_test.dart`
Expected: FAIL — `package:mobile/app/theme/app_theme.dart` not found.

- [ ] **Step 3: Implement the color tokens**

`mobile/lib/app/theme/color_tokens.dart`:

```dart
import 'package:flutter/material.dart';

/// Energy palette — contract with server-side energy classes and renderers.
/// Source: docs/UX.md §1. Same accent hues used for light and dark; only
/// surface/text tokens differ per theme (formal contrast-on-terrain
/// validation deferred — out of scope for this skeleton).
class EnergyColors {
  const EnergyColors._();

  static const Color regen = Color(0xFF2FBF71);
  static const Color efficient = Color(0xFFE8C547);
  static const Color medium = Color(0xFFF28C28);
  static const Color heavy = Color(0xFFE4572E);
  static const Color charge = Color(0xFF3D9BE9);
}

/// Surface/background tokens. Dark-first per UX.md §1 ("driving context").
class GradientColors {
  const GradientColors._();

  static const Color darkBackground = Color(0xFF0E1116);
  static const Color darkSurface = Color(0xFF181C22);
  static const Color darkOnSurface = Color(0xFFF2F4F7);
  static const Color darkOnSurfaceMuted = Color(0xFF9AA4B2);

  static const Color lightBackground = Color(0xFFF7F8FA);
  static const Color lightSurface = Color(0xFFFFFFFF);
  static const Color lightOnSurface = Color(0xFF14171C);
  static const Color lightOnSurfaceMuted = Color(0xFF5B6472);
}
```

- [ ] **Step 4: Implement the text tokens**

`mobile/lib/app/theme/text_tokens.dart`:

```dart
import 'package:flutter/material.dart';

/// Typography tokens. UX.md §1 calls for a tabular-numerals display face
/// for all metrics ("numbers are the product") — enforced here via
/// [FontFeature.tabularFigures] rather than a bespoke font.
class GradientTextStyles {
  const GradientTextStyles._();

  static const TextStyle metricLarge = TextStyle(
    fontSize: 40,
    fontWeight: FontWeight.w700,
    fontFeatures: [FontFeature.tabularFigures()],
    height: 1.05,
  );

  static const TextStyle metricSmall = TextStyle(
    fontSize: 16,
    fontWeight: FontWeight.w600,
    fontFeatures: [FontFeature.tabularFigures()],
  );

  static const TextStyle body = TextStyle(
    fontSize: 15,
    fontWeight: FontWeight.w400,
  );

  static const TextStyle label = TextStyle(
    fontSize: 13,
    fontWeight: FontWeight.w500,
    letterSpacing: 0.2,
  );
}
```

- [ ] **Step 5: Implement the theme**

`mobile/lib/app/theme/app_theme.dart`:

```dart
import 'package:flutter/material.dart';

import 'color_tokens.dart';
import 'text_tokens.dart';

class GradientTheme {
  const GradientTheme._();

  static ThemeData get dark => _themeFrom(
        brightness: Brightness.dark,
        background: GradientColors.darkBackground,
        surface: GradientColors.darkSurface,
        onSurface: GradientColors.darkOnSurface,
        onSurfaceMuted: GradientColors.darkOnSurfaceMuted,
      );

  static ThemeData get light => _themeFrom(
        brightness: Brightness.light,
        background: GradientColors.lightBackground,
        surface: GradientColors.lightSurface,
        onSurface: GradientColors.lightOnSurface,
        onSurfaceMuted: GradientColors.lightOnSurfaceMuted,
      );

  static ThemeData _themeFrom({
    required Brightness brightness,
    required Color background,
    required Color surface,
    required Color onSurface,
    required Color onSurfaceMuted,
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
```

- [ ] **Step 6: Run test to verify it passes**

Run: `flutter test test/app/theme/app_theme_test.dart`
Expected: 3 PASS

- [ ] **Step 7: Analyze and commit**

```bash
flutter analyze
git add lib/app/theme test/app/theme
git commit -m "feat(mobile): design tokens and light/dark theme"
```

---

### Task 3: EnergyChip reusable widget

**Files:**
- Create: `mobile/lib/core/design/energy_chip.dart`
- Test: `mobile/test/core/design/energy_chip_test.dart`
- Generated (via `--update-goldens`, then committed): `mobile/test/core/design/goldens/energy_chip_light.png`, `mobile/test/core/design/goldens/energy_chip_dark.png`

**Interfaces:**
- Consumes: `EnergyColors`, `GradientTextStyles`, `GradientTheme` from Task 2.
- Produces: `EnergyClass` enum (`regen`, `efficient`, `medium`, `heavy`, `charge`) with `.color`/`.icon` extension getters, and `EnergyChip(energyClass:, deltaPct:)` widget — consumed by later plans building the Energy Timeline (UX.md §2/§3 `ChapterChip`).

- [ ] **Step 1: Write the failing tests**

`mobile/test/core/design/energy_chip_test.dart`:

```dart
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/core/design/energy_chip_test.dart`
Expected: FAIL — `package:mobile/core/design/energy_chip.dart` not found.

- [ ] **Step 3: Implement the widget**

`mobile/lib/core/design/energy_chip.dart`:

```dart
import 'package:flutter/material.dart';

import '../../app/theme/color_tokens.dart';
import '../../app/theme/text_tokens.dart';

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
          color: energyClass.color.withOpacity(0.18),
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
```

- [ ] **Step 4: Run the non-golden tests to verify they pass**

Run: `flutter test test/core/design/energy_chip_test.dart --plain-name "shows"`
Expected: 2 PASS (the two `find.text`/`find.byIcon` tests; goldens fail with "golden file does not exist" until the next step).

- [ ] **Step 5: Generate the golden files**

```bash
flutter test --update-goldens test/core/design/energy_chip_test.dart
```

Expected: creates `test/core/design/goldens/energy_chip_light.png` and `energy_chip_dark.png`.

- [ ] **Step 6: Run the full test file to verify all four pass**

Run: `flutter test test/core/design/energy_chip_test.dart`
Expected: 4 PASS.

- [ ] **Step 7: Analyze and commit**

```bash
flutter analyze
git add lib/core/design test/core/design
git commit -m "feat(mobile): EnergyChip design-system component with light/dark goldens"
```

---

### Task 4: Core network client

**Files:**
- Create: `mobile/lib/core/network/api_flavor.dart`
- Create: `mobile/lib/core/network/api_client.dart`
- Test: `mobile/test/core/network/api_client_test.dart`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `ApiFlavor` enum (`dev`/`staging`/`prod`) with `.baseUrl`, `ApiClient(flavor:, authTokenProvider:)` wrapping a `Dio` instance, and the pure function `applyAuthHeader(RequestOptions, String? token)`. No feature wires this to a real endpoint in this plan (see Non-Goals) — it exists and is tested so later plans have a place to add real repositories.

- [ ] **Step 1: Write the failing test**

`mobile/test/core/network/api_client_test.dart`:

```dart
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/core/network/api_client.dart';
import 'package:mobile/core/network/api_flavor.dart';

void main() {
  test('dev flavor resolves to the local backend base URL', () {
    expect(ApiFlavor.dev.baseUrl, 'http://localhost:8000');
  });

  test('prod flavor resolves to the production base URL', () {
    expect(ApiFlavor.prod.baseUrl, 'https://api.gradient.app');
  });

  test('ApiClient configures dio with the flavor base URL and one interceptor', () {
    final client = ApiClient(flavor: ApiFlavor.staging);
    expect(client.dio.options.baseUrl, 'https://staging-api.gradient.app');
    expect(client.dio.interceptors, hasLength(1));
  });

  test('applyAuthHeader attaches a bearer token when present', () {
    final options = RequestOptions(path: '/health');
    applyAuthHeader(options, 'test-token');
    expect(options.headers['Authorization'], 'Bearer test-token');
  });

  test('applyAuthHeader leaves headers untouched when token is null', () {
    final options = RequestOptions(path: '/health');
    applyAuthHeader(options, null);
    expect(options.headers.containsKey('Authorization'), isFalse);
  });

  test('applyAuthHeader leaves headers untouched when token is empty', () {
    final options = RequestOptions(path: '/health');
    applyAuthHeader(options, '');
    expect(options.headers.containsKey('Authorization'), isFalse);
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/core/network/api_client_test.dart`
Expected: FAIL — `package:mobile/core/network/api_client.dart` (and `api_flavor.dart`) not found.

- [ ] **Step 3: Implement `api_flavor.dart`**

`mobile/lib/core/network/api_flavor.dart`:

```dart
enum ApiFlavor { dev, staging, prod }

extension ApiFlavorBaseUrl on ApiFlavor {
  String get baseUrl {
    switch (this) {
      case ApiFlavor.dev:
        return 'http://localhost:8000';
      case ApiFlavor.staging:
        return 'https://staging-api.gradient.app';
      case ApiFlavor.prod:
        return 'https://api.gradient.app';
    }
  }
}
```

- [ ] **Step 4: Implement `api_client.dart`**

`mobile/lib/core/network/api_client.dart`:

```dart
import 'package:dio/dio.dart';

import 'api_flavor.dart';

/// Attaches a bearer token to [options] if [token] is non-null and
/// non-empty. Pure and independently testable — the dio interceptor below
/// is a thin adapter around this.
void applyAuthHeader(RequestOptions options, String? token) {
  if (token != null && token.isNotEmpty) {
    options.headers['Authorization'] = 'Bearer $token';
  }
}

/// Thin dio wrapper: flavor-scoped base URL + auth-token interceptor.
/// Endpoint methods (API.md) land in feature-level repositories in later
/// plans — this class owns only cross-cutting request config.
class ApiClient {
  ApiClient({required ApiFlavor flavor, String? Function()? authTokenProvider})
      : _authTokenProvider = authTokenProvider,
        dio = Dio(BaseOptions(baseUrl: flavor.baseUrl)) {
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          applyAuthHeader(options, _authTokenProvider?.call());
          handler.next(options);
        },
      ),
    );
  }

  final Dio dio;
  final String? Function()? _authTokenProvider;
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `flutter test test/core/network/api_client_test.dart`
Expected: 6 PASS

- [ ] **Step 6: Analyze and commit**

```bash
flutter analyze
git add lib/core/network test/core/network
git commit -m "feat(mobile): flavor-scoped API client with auth interceptor"
```

---

### Task 5: App shell — navigation and bootstrap

**Files:**
- Create: `mobile/lib/app/app_shell.dart`
- Create: `mobile/lib/app/router.dart`
- Create: `mobile/lib/app/app.dart`
- Modify: `mobile/lib/main_dev.dart`
- Delete: `mobile/test/main_dev_test.dart` (superseded by `router_test.dart`, which exercises the same bootstrap through `GradientApp`)
- Test: `mobile/test/app/app_shell_test.dart`, `mobile/test/app/router_test.dart`

**Interfaces:**
- Consumes: `GradientTheme` from Task 2.
- Produces: `AppShell(tabs:)` + `AppShellTab(label:, icon:, screen:)`, `buildRouter({required Widget planScreen, required Widget garageScreen})` returning a `GoRouter`, and `GradientApp(router:)` (a `ConsumerWidget` wrapping `MaterialApp.router`). Task 7 modifies `main_dev.dart` again to pass the real `HomePlanScreen`.

- [ ] **Step 1: Write the failing `AppShell` test**

`mobile/test/app/app_shell_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/app/app_shell.dart';

void main() {
  testWidgets('AppShell shows the first tab and switches on nav tap', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: AppShell(
          tabs: const [
            AppShellTab(label: 'Plan', icon: Icons.map_outlined, screen: Text('PLAN SCREEN')),
            AppShellTab(label: 'Garage', icon: Icons.directions_car_outlined, screen: Text('GARAGE SCREEN')),
          ],
        ),
      ),
    );

    expect(find.text('PLAN SCREEN'), findsOneWidget);
    expect(find.text('GARAGE SCREEN'), findsNothing);

    await tester.tap(find.text('Garage'));
    await tester.pumpAndSettle();

    expect(find.text('GARAGE SCREEN'), findsOneWidget);
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/app/app_shell_test.dart`
Expected: FAIL — `package:mobile/app/app_shell.dart` not found.

- [ ] **Step 3: Implement `app_shell.dart`**

`mobile/lib/app/app_shell.dart`:

```dart
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `flutter test test/app/app_shell_test.dart`
Expected: 1 PASS

- [ ] **Step 5: Write the failing router/app test**

`mobile/test/app/router_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/app/app.dart';
import 'package:mobile/app/router.dart';

void main() {
  testWidgets('GradientApp boots to the Plan tab via the router', (tester) async {
    final router = buildRouter(
      planScreen: const Text('PLAN'),
      garageScreen: const Text('GARAGE'),
    );
    await tester.pumpWidget(ProviderScope(child: GradientApp(router: router)));
    await tester.pumpAndSettle();
    expect(find.text('PLAN'), findsOneWidget);
  });

  testWidgets('GradientApp switches to Garage on nav tap', (tester) async {
    final router = buildRouter(
      planScreen: const Text('PLAN'),
      garageScreen: const Text('GARAGE'),
    );
    await tester.pumpWidget(ProviderScope(child: GradientApp(router: router)));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Garage'));
    await tester.pumpAndSettle();

    expect(find.text('GARAGE'), findsOneWidget);
  });
}
```

- [ ] **Step 6: Run test to verify it fails**

Run: `flutter test test/app/router_test.dart`
Expected: FAIL — `package:mobile/app/router.dart` and `package:mobile/app/app.dart` not found.

- [ ] **Step 7: Implement `router.dart`**

`mobile/lib/app/router.dart`:

```dart
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
```

- [ ] **Step 8: Implement `app.dart`**

`mobile/lib/app/app.dart`:

```dart
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
```

- [ ] **Step 9: Rewire `main_dev.dart`**

`mobile/lib/main_dev.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app/app.dart';
import 'app/router.dart';

void main() {
  final router = buildRouter(
    planScreen: const Scaffold(body: Center(child: Text('Plan — coming soon'))),
    garageScreen: const Scaffold(body: Center(child: Text('Garage — coming soon'))),
  );
  runApp(ProviderScope(child: GradientApp(router: router)));
}
```

- [ ] **Step 10: Delete the now-superseded bootstrap test**

```bash
rm test/main_dev_test.dart
```

(`GradientDevApp` no longer exists; `router_test.dart` from Step 5 covers the same "app boots" concern through `GradientApp`.)

- [ ] **Step 11: Run tests to verify they pass**

Run: `flutter test test/app`
Expected: 3 PASS (`app_shell_test.dart`'s 1 + `router_test.dart`'s 2)

- [ ] **Step 12: Analyze and commit**

```bash
flutter analyze
git add lib/app lib/main_dev.dart test/app
git rm test/main_dev_test.dart
git commit -m "feat(mobile): app shell, router, and MaterialApp bootstrap"
```

---

### Task 6: Garage feature slice

**Files:**
- Create: `mobile/lib/features/garage/domain/vehicle.dart`
- Create: `mobile/lib/features/garage/domain/vehicle_repository.dart`
- Create: `mobile/lib/features/garage/data/fake_vehicle_repository.dart`
- Create: `mobile/lib/features/garage/presentation/garage_providers.dart`
- Create: `mobile/lib/features/garage/presentation/garage_screen.dart`
- Modify: `mobile/lib/main_dev.dart` (wire the real `GarageScreen`)
- Test: `mobile/test/features/garage/data/fake_vehicle_repository_test.dart`, `mobile/test/features/garage/presentation/garage_screen_test.dart`

**Interfaces:**
- Consumes: `GradientTextStyles` from Task 2; `buildRouter`/`GradientApp` from Task 5 (only `main_dev.dart` touches these, to pass the new screen).
- Produces: `Vehicle` entity, `VehicleRepository` interface, `FakeVehicleRepository`, `vehicleRepositoryProvider` (`Provider<VehicleRepository>`), `vehiclesProvider` (`FutureProvider<List<Vehicle>>`), `GarageScreen` widget. Task 7 consumes `vehicleRepositoryProvider` and `vehiclesProvider` from `garage_providers.dart` (see Task 7's note on this being a documented, temporary exception to the domain-only cross-feature import rule).

- [ ] **Step 1: Write the failing repository test**

`mobile/test/features/garage/data/fake_vehicle_repository_test.dart`:

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/features/garage/data/fake_vehicle_repository.dart';
import 'package:mobile/features/garage/domain/vehicle.dart';

void main() {
  test('default seed returns two vehicles', () async {
    final repo = FakeVehicleRepository();
    final vehicles = await repo.listVehicles();
    expect(vehicles, hasLength(2));
    expect(vehicles.first.displayName, 'Tesla Model 3 LR');
  });

  test('custom seed is returned unmodified', () async {
    const seed = [Vehicle(id: 'x', displayName: 'X', batteryPct: 50, usableKwh: 60)];
    final repo = FakeVehicleRepository(seed);
    final vehicles = await repo.listVehicles();
    expect(vehicles, seed);
  });

  test('returned list is unmodifiable', () async {
    final repo = FakeVehicleRepository();
    final vehicles = await repo.listVehicles();
    expect(() => vehicles.add(vehicles.first), throwsUnsupportedError);
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/features/garage/data/fake_vehicle_repository_test.dart`
Expected: FAIL — `vehicle.dart`/`fake_vehicle_repository.dart` not found.

- [ ] **Step 3: Implement the domain layer**

`mobile/lib/features/garage/domain/vehicle.dart`:

```dart
/// Domain entity — a plain immutable class (no codegen in this skeleton;
/// see plan Non-Goals for why `freezed` is deferred).
class Vehicle {
  const Vehicle({
    required this.id,
    required this.displayName,
    required this.batteryPct,
    required this.usableKwh,
  });

  final String id;
  final String displayName;
  final double batteryPct;
  final double usableKwh;

  @override
  bool operator ==(Object other) =>
      other is Vehicle &&
      other.id == id &&
      other.displayName == displayName &&
      other.batteryPct == batteryPct &&
      other.usableKwh == usableKwh;

  @override
  int get hashCode => Object.hash(id, displayName, batteryPct, usableKwh);
}
```

`mobile/lib/features/garage/domain/vehicle_repository.dart`:

```dart
import 'vehicle.dart';

abstract class VehicleRepository {
  Future<List<Vehicle>> listVehicles();
}
```

- [ ] **Step 4: Implement the fake data layer**

`mobile/lib/features/garage/data/fake_vehicle_repository.dart`:

```dart
import '../domain/vehicle.dart';
import '../domain/vehicle_repository.dart';

/// In-memory repository — stands in for the API-backed implementation
/// until the backend (BackendArchitecture.md) exists. Replace with a
/// dio-backed implementation once `GET /vehicles` ships.
class FakeVehicleRepository implements VehicleRepository {
  FakeVehicleRepository([List<Vehicle>? seed])
      : _vehicles = seed ??
            const [
              Vehicle(
                id: 'tesla-model3-lr',
                displayName: 'Tesla Model 3 LR',
                batteryPct: 82,
                usableKwh: 75,
              ),
              Vehicle(
                id: 'ioniq5-awd',
                displayName: 'Hyundai Ioniq 5 AWD',
                batteryPct: 64,
                usableKwh: 77.4,
              ),
            ];

  final List<Vehicle> _vehicles;

  @override
  Future<List<Vehicle>> listVehicles() async => List.unmodifiable(_vehicles);
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `flutter test test/features/garage/data/fake_vehicle_repository_test.dart`
Expected: 3 PASS

- [ ] **Step 6: Write the failing `GarageScreen` test**

`mobile/test/features/garage/presentation/garage_screen_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/features/garage/data/fake_vehicle_repository.dart';
import 'package:mobile/features/garage/domain/vehicle.dart';
import 'package:mobile/features/garage/presentation/garage_providers.dart';
import 'package:mobile/features/garage/presentation/garage_screen.dart';

void main() {
  testWidgets('GarageScreen lists vehicles from the repository', (tester) async {
    final repo = FakeVehicleRepository(const [
      Vehicle(id: 'a', displayName: 'Test EV', batteryPct: 77, usableKwh: 60),
    ]);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [vehicleRepositoryProvider.overrideWithValue(repo)],
        child: const MaterialApp(home: GarageScreen()),
      ),
    );

    await tester.pump(); // let the FutureProvider resolve
    expect(find.text('Test EV'), findsOneWidget);
    expect(find.text('77%'), findsOneWidget);
  });
}
```

- [ ] **Step 7: Run test to verify it fails**

Run: `flutter test test/features/garage/presentation/garage_screen_test.dart`
Expected: FAIL — `garage_providers.dart`/`garage_screen.dart` not found.

- [ ] **Step 8: Implement the presentation layer**

`mobile/lib/features/garage/presentation/garage_providers.dart`:

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/fake_vehicle_repository.dart';
import '../domain/vehicle.dart';
import '../domain/vehicle_repository.dart';

final vehicleRepositoryProvider = Provider<VehicleRepository>((ref) {
  return FakeVehicleRepository();
});

final vehiclesProvider = FutureProvider<List<Vehicle>>((ref) {
  return ref.watch(vehicleRepositoryProvider).listVehicles();
});
```

`mobile/lib/features/garage/presentation/garage_screen.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme/text_tokens.dart';
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
```

- [ ] **Step 9: Run test to verify it passes**

Run: `flutter test test/features/garage`
Expected: 4 PASS (3 repository + 1 screen)

- [ ] **Step 10: Wire `GarageScreen` into `main_dev.dart`**

`mobile/lib/main_dev.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app/app.dart';
import 'app/router.dart';
import 'features/garage/presentation/garage_screen.dart';

void main() {
  final router = buildRouter(
    planScreen: const Scaffold(body: Center(child: Text('Plan — coming soon'))),
    garageScreen: const GarageScreen(),
  );
  runApp(ProviderScope(child: GradientApp(router: router)));
}
```

- [ ] **Step 11: Run the app-level tests to confirm nothing broke**

Run: `flutter test test/app`
Expected: 3 PASS (unchanged — `router_test.dart` passes its own screens, independent of `main_dev.dart`'s wiring)

- [ ] **Step 12: Analyze and commit**

```bash
flutter analyze
git add lib/features/garage lib/main_dev.dart test/features/garage
git commit -m "feat(mobile): garage feature slice with fake vehicle repository"
```

---

### Task 7: Planning feature stub — Home/Plan screen

**Files:**
- Create: `mobile/lib/features/planning/presentation/home_plan_screen.dart`
- Modify: `mobile/lib/main_dev.dart` (wire the real `HomePlanScreen`)
- Test: `mobile/test/features/planning/presentation/home_plan_screen_test.dart`

**Interfaces:**
- Consumes: `vehicleRepositoryProvider`/`vehiclesProvider` from `garage/presentation/garage_providers.dart` (Task 6), `GradientTextStyles` from Task 2.
- Produces: `HomePlanScreen` widget, wired as the router's Plan tab in `main_dev.dart`.

**Documented layering exception:** `HomePlanScreen` imports `../../garage/presentation/garage_providers.dart` — a presentation-layer file from another feature. This violates the "features import `core` and other features' domain interfaces only" rule stated in Global Constraints. It's accepted here as a deliberate, temporary shortcut: `vehiclesProvider` is really server-cache/data-layer state (a `FutureProvider` over a repository), not a UI concern, and it's the only practical way to show the garage chip on the Plan screen without inventing a speculative shared "current vehicle" service ahead of need. Fix properly (e.g. a `selectedVehicleProvider` in a shared location) when a second feature needs the same data, or when this becomes a real pain point — don't generalize it now.

- [ ] **Step 1: Write the failing tests**

`mobile/test/features/planning/presentation/home_plan_screen_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/features/garage/data/fake_vehicle_repository.dart';
import 'package:mobile/features/garage/domain/vehicle.dart';
import 'package:mobile/features/garage/presentation/garage_providers.dart';
import 'package:mobile/features/planning/presentation/home_plan_screen.dart';

void main() {
  testWidgets('HomePlanScreen shows the garage chip, search field, and recents', (tester) async {
    final repo = FakeVehicleRepository(const [
      Vehicle(id: 'a', displayName: 'Test EV', batteryPct: 82, usableKwh: 75),
    ]);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [vehicleRepositoryProvider.overrideWithValue(repo)],
        child: const MaterialApp(home: HomePlanScreen()),
      ),
    );

    await tester.pump();

    expect(find.textContaining('82%'), findsOneWidget);
    expect(find.textContaining('Test EV'), findsOneWidget);
    expect(find.text('Where to?'), findsOneWidget);
    expect(find.text('Home'), findsOneWidget);
    expect(find.text('3D map — coming soon'), findsOneWidget);
  });

  testWidgets('HomePlanScreen shows a fallback when there is no vehicle', (tester) async {
    final repo = FakeVehicleRepository(const []);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [vehicleRepositoryProvider.overrideWithValue(repo)],
        child: const MaterialApp(home: HomePlanScreen()),
      ),
    );

    await tester.pump();
    expect(find.text('No vehicle selected'), findsOneWidget);
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/features/planning/presentation/home_plan_screen_test.dart`
Expected: FAIL — `package:mobile/features/planning/presentation/home_plan_screen.dart` not found.

- [ ] **Step 3: Implement `home_plan_screen.dart`**

`mobile/lib/features/planning/presentation/home_plan_screen.dart`:

```dart
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `flutter test test/features/planning/presentation/home_plan_screen_test.dart`
Expected: 2 PASS

- [ ] **Step 5: Wire `HomePlanScreen` into `main_dev.dart`**

`mobile/lib/main_dev.dart`:

```dart
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
```

- [ ] **Step 6: Run the full test suite to confirm nothing broke**

Run: `flutter test`
Expected: all tests pass (Tasks 1–7 combined: main_dev bootstrap test was removed in Task 5, so this is app_shell(1) + router(2) + theme(3) + energy_chip(4) + api_client(6) + garage repo(3) + garage screen(1) + home_plan_screen(2) = 22 tests).

- [ ] **Step 7: Analyze and commit**

```bash
flutter analyze
git add lib/features/planning lib/main_dev.dart test/features/planning
git commit -m "feat(mobile): planning feature stub — Home/Plan screen"
```

---

## Self-Review Notes (for the plan author, not a task)

- **Spec coverage:** MobileArchitecture.md's stack (Flutter, Riverpod, go_router, dio) is covered; folder structure (§2) is covered for `app/`, `core/design`, `core/network`, and two features; state management (§3) is covered by classic Riverpod providers, documented as a simplification vs. the spec's codegen preference. UX.md §1 (energy palette, tabular numerals, icon+color) is covered by Tasks 2–3. UX.md's Home/Plan wireframe (§2) is covered by Task 7. Everything else in MobileArchitecture.md (§4 offline-first, §5 3D route view, §6 drive mode, §7 degraded states, §8 cross-language golden tests) is explicitly deferred in Non-Goals — these need their own future plans.
- **Placeholder scan:** no TBD/TODO markers; every step has literal code or an exact shell command.
- **Type consistency:** `Vehicle(id, displayName, batteryPct, usableKwh)` used identically in Tasks 6 and 7; `vehicleRepositoryProvider`/`vehiclesProvider` names and types match between their Task 6 definition and Task 7's consumption; `buildRouter({planScreen, garageScreen})` signature matches between Task 5's definition and Tasks 6–7's `main_dev.dart` call sites.
