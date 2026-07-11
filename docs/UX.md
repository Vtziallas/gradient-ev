# Gradient — UX, Wireframes & Component Hierarchy

## 1. Design language

**Premium instrument, not a map with buttons.** Dark-first (driving context), one accent
system = the energy palette itself. Typography: SF Pro / Roboto with a tabular-numerals
display face for all metrics (numbers are the product). Motion: physics-based (spring)
transitions; energy values never "teleport" — they count. Every metric is tappable →
"Why?" sheet with the engine's `reasons[]`. Accessibility: WCAG AA contrast; energy classes
are never color-only (icons + patterns for color-blind users); full dynamic type.

Energy palette (contract with renderers, Architecture.md §6):
`regen #2FBF71 · efficient #E8C547 · medium #F28C28 · heavy #E4572E · charge #3D9BE9`
(dark and light variants defined in tokens; validated for contrast on terrain).

## 2. Core screens (wireframes)

### Home / Plan
```
┌──────────────────────────────┐
│ ⚡ 82%  ·  Tesla Model 3 LR ▾ │   garage chip: battery + vehicle switcher
│ ┌──────────────────────────┐ │
│ │ 🔍 Where to?             │ │
│ └──────────────────────────┘ │
│  Recent: Home · Work · Meteora│
│ ┌──────────────────────────┐ │
│ │        MAP (3D tilt)     │ │   chargers as availability-colored pins
│ │      ●———— you           │ │
│ └──────────────────────────┘ │
│  Range ring: 231 km ±14      │   worst-case ring dashed
└──────────────────────────────┘
```

### Route result (the signature screen)
```
┌──────────────────────────────┐
│ ◀ Athens → Kalambaka  356 km │
│ ┌──────────────────────────┐ │
│ │   3D TERRAIN FLY-THROUGH │ │   auto-plays once; energy-colored ribbon
│ │   ▲▲ red climb  🟢 descent│ │   exaggeration slider ┃ camera modes ⧉
│ └──────────────────────────┘ │
│ ENERGY TIMELINE              │
│ 🟢+2.4 🟡-1.3 🔴-5.8 🔵⚡ 🟢+3.1│   horizontally scrollable chapters,
│  ────────────●───────────    │   scrubber linked to 3D camera
│ Arrive 21% (worst 17%) ●●●●○ │   confidence dots; tap → Why sheet
│ ⚡ 1 stop · 24 min · €14.20  │
│ [ Fastest | Efficient | Cheap]│   comparison tabs (score matrix)
│ ▶ START                      │
└──────────────────────────────┘
```

### Drive mode (HUD)
```
┌──────────────────────────────┐
│  ⬆ maneuver: A1 exit 12 2km  │   Mapbox nav strip
│ ┌──────────────────────────┐ │
│ │   follow-cam 3D map      │ │
│ │   ribbon ahead colored   │ │
│ │        ◤72–79◢           │ │   Smart Speed Bubble, tap → reasons
│ └──────────────────────────┘ │
│ ┃🟢                          │   edge rail = upcoming energy timeline
│ ┃🔴 summit in 3.4 km  -5.8%  │
│ 64% now → 21% arrival ●●●●○  │   smoothed, never jumps
└──────────────────────────────┘
```

### Trip report (Eco Coach)
```
│ Efficiency 93/100  ▲ +2      │
│ ⚡ used 12.4 kWh · 🟢 regen 2.1│
│ "On the Domokos climb, 74     │
│  km/h would have saved 1.1%"  │
│ Missed regen: 2.8 kWh (3 hard │
│  braking events → map pins)   │
│ Achievements: 🏔 Mountain Exp. │
```

Other screens: Garage (vehicle cards + spec sheet + degradation slider), Charger detail
(connectors, live status, price, reliability %, amenities row, community reports),
Community sheet (report kinds as big icon buttons), Leaderboards, Settings/Privacy.

## 3. Component hierarchy (route result)

```
RouteResultScreen
├── RouteHeaderBar (origin→dest, distance, close)
├── Terrain3DView                    ← feature route3d
│   ├── MapboxTerrainCanvas | RibbonRenderer (stage 2)
│   ├── CameraModeToggle  ├── ExaggerationSlider
│   └── TerrainHud (elevation, slope, summit distance)
├── EnergyTimelineRail               ← feature timeline
│   ├── ChapterChip (class, Δ%, cause icon) ×N
│   └── TimelineScrubber (bound to camera playhead)
├── PredictionCard
│   ├── ArrivalSocDial (point + worst-case arc)
│   ├── ConfidenceDots  └── WhySheet (reasons[])
├── ChargingPlanStrip → ChargeStopCard ×N
├── CandidateTabs (score matrix chips)
└── StartDriveButton
```

All components consume `RouteEnergyBundle` slices via Riverpod selectors; no component
computes energy — display only (contract: physics lives server-side + engine subset).

## 4. Key interaction rules

- Fly-through auto-plays **once** per new route (3.5 s max), skippable; never on re-open.
- Scrubbing the timeline moves the 3D camera and the HUD numbers in lockstep.
- Speed bubble appears only when band ≠ current speed ±3 km/h and conditions warrant
  (grade/wind/traffic); silent otherwise — no nagging.
- Worst-case leads whenever worst-case arrival < 15% (safety rule, engine-enforced).
- Every prediction number exposes "Why?" — trust is the brand.
