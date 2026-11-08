import 'package:flutter/material.dart';

/// Colours are tokens, not decoration: green means official and safe actions, amber means a deadline,
/// red means closing today or a warning. Everything else is ink on paper.
class Palette {
  const Palette({
    required this.paper,
    required this.surface,
    required this.ink,
    required this.muted,
    required this.line,
    required this.green,
    required this.greenSoft,
    required this.amber,
    required this.amberSoft,
    required this.red,
    required this.redSoft,
    required this.blue,
  });
  final Color paper, surface, ink, muted, line, green, greenSoft, amber, amberSoft, red, redSoft, blue;

  static const light = Palette(
    paper: Color(0xFFF6F4EF),
    surface: Color(0xFFFFFFFF),
    ink: Color(0xFF1B2230),
    muted: Color(0xFF5B6474),
    line: Color(0xFFE3DFD6),
    green: Color(0xFF0B5D4B),
    greenSoft: Color(0xFFE1F0EA),
    amber: Color(0xFF9A5507),
    amberSoft: Color(0xFFFAEFDC),
    red: Color(0xFFB42318),
    redSoft: Color(0xFFFCE9E7),
    blue: Color(0xFF1F4E8C),
  );
  static const dark = Palette(
    paper: Color(0xFF111315),
    surface: Color(0xFF1A1D21),
    ink: Color(0xFFECE9E3),
    muted: Color(0xFFA3A9B4),
    line: Color(0xFF2D3137),
    green: Color(0xFF6CC7AC),
    greenSoft: Color(0xFF16302A),
    amber: Color(0xFFF0B354),
    amberSoft: Color(0xFF3A2C14),
    red: Color(0xFFF2877C),
    redSoft: Color(0xFF3B1D1A),
    blue: Color(0xFF8DB4EE),
  );
}

extension PaletteX on BuildContext {
  Palette get pal => Theme.of(this).brightness == Brightness.dark ? Palette.dark : Palette.light;
}

const tabular = [FontFeature.tabularFigures()];

ThemeData buildTheme(Brightness b, {String? fontFamily}) {
  final p = b == Brightness.dark ? Palette.dark : Palette.light;
  final scheme = ColorScheme(
    brightness: b,
    primary: p.green,
    onPrimary: b == Brightness.dark ? const Color(0xFF0B1A16) : Colors.white,
    secondary: p.amber,
    onSecondary: Colors.white,
    error: p.red,
    onError: Colors.white,
    surface: p.surface,
    onSurface: p.ink,
    surfaceContainerHighest: p.paper,
    outline: p.line,
  );
  final base = ThemeData(useMaterial3: true, colorScheme: scheme, brightness: b, fontFamily: fontFamily);
  final text = base.textTheme.apply(bodyColor: p.ink, displayColor: p.ink);
  return base.copyWith(
    scaffoldBackgroundColor: p.paper,
    textTheme: text.copyWith(
      headlineSmall: text.headlineSmall?.copyWith(fontWeight: FontWeight.w700, letterSpacing: -0.3, height: 1.2),
      titleLarge: text.titleLarge?.copyWith(fontWeight: FontWeight.w700, letterSpacing: -0.2),
      titleMedium: text.titleMedium?.copyWith(fontWeight: FontWeight.w600, height: 1.3),
      bodyMedium: text.bodyMedium?.copyWith(height: 1.45),
      labelSmall: text.labelSmall?.copyWith(letterSpacing: 0.6, fontWeight: FontWeight.w600),
    ),
    appBarTheme: AppBarTheme(
      backgroundColor: p.paper,
      foregroundColor: p.ink,
      elevation: 0,
      scrolledUnderElevation: 0,
      centerTitle: false,
      titleTextStyle: text.titleLarge?.copyWith(fontWeight: FontWeight.w700),
    ),
    cardTheme: CardTheme(
      color: p.surface,
      elevation: 0,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10), side: BorderSide(color: p.line)),
    ),
    dividerTheme: DividerThemeData(color: p.line, space: 1, thickness: 1),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: p.surface,
      indicatorColor: p.greenSoft,
      height: 66,
      labelTextStyle: WidgetStatePropertyAll(text.labelMedium?.copyWith(fontWeight: FontWeight.w600)),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size(64, 52),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        textStyle: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, fontFamily: fontFamily),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size(64, 48),
        foregroundColor: p.ink,
        side: BorderSide(color: p.line),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      ),
    ),
    segmentedButtonTheme: SegmentedButtonThemeData(
      style: ButtonStyle(
        backgroundColor: WidgetStateProperty.resolveWith((s) => s.contains(WidgetState.selected) ? p.greenSoft : p.surface),
        foregroundColor: WidgetStateProperty.resolveWith((s) => s.contains(WidgetState.selected) ? p.green : p.ink),
        side: WidgetStatePropertyAll(BorderSide(color: p.line)),
      ),
    ),
    chipTheme: ChipThemeData(
      backgroundColor: p.surface,
      selectedColor: p.greenSoft,
      side: BorderSide(color: p.line),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      labelStyle: text.labelLarge,
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: p.surface,
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: p.line)),
      enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: p.line)),
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
    ),
    listTileTheme: ListTileThemeData(iconColor: p.muted, minVerticalPadding: 12),
  );
}
