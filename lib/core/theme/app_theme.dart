import 'package:flutter/material.dart';

class AppTheme {
  static const background = Color(0xFF0B0F14);
  static const surface = Color(0xFF121923);
  static const surface2 = Color(0xFF192330);
  static const accent = Color(0xFF38BDF8);
  static const positive = Color(0xFF22C55E);
  static const negative = Color(0xFFF87171);
  static const muted = Color(0xFF94A3B8);

  static ThemeData get dark => ThemeData(
        useMaterial3: true,
        brightness: Brightness.dark,
        scaffoldBackgroundColor: background,
        colorScheme: const ColorScheme.dark(
          primary: accent,
          secondary: Color(0xFF67E8F9),
          surface: surface,
          error: negative,
        ),
        cardColor: surface,
        dividerColor: const Color(0xFF263241),
        appBarTheme: const AppBarTheme(
          backgroundColor: background,
          foregroundColor: Color(0xFFF3F4F6),
          elevation: 0,
          centerTitle: false,
        ),
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: surface2,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(14),
            borderSide: BorderSide.none,
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(14),
            borderSide: const BorderSide(color: Color(0xFF263241)),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(14),
            borderSide: const BorderSide(color: accent),
          ),
        ),
        navigationBarTheme: const NavigationBarThemeData(
          backgroundColor: Color(0xFF101720),
          indicatorColor: Color(0xFF163B4D),
          labelTextStyle: WidgetStatePropertyAll(
            TextStyle(fontSize: 11, fontWeight: FontWeight.w600),
          ),
        ),
        textTheme: const TextTheme(
          headlineMedium: TextStyle(fontSize: 25, fontWeight: FontWeight.w800, letterSpacing: -0.5),
          titleLarge: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
          titleMedium: TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
          bodyMedium: TextStyle(fontSize: 13, height: 1.5),
          bodySmall: TextStyle(fontSize: 11, height: 1.45, color: muted),
        ),
      );
}
