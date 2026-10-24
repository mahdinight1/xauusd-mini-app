import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'core/l10n/app_strings.dart';
import 'core/services/app_storage.dart';
import 'core/theme/app_theme.dart';
import 'features/shell/app_shell.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const NextraApp());
}

class NextraApp extends StatefulWidget {
  const NextraApp({super.key});

  @override
  State<NextraApp> createState() => _NextraAppState();
}

class _NextraAppState extends State<NextraApp> {
  Locale _locale = const Locale('fa');
  bool _ready = false;

  @override
  void initState() {
    super.initState();
    _loadLocale();
  }

  Future<void> _loadLocale() async {
    final code = await AppStorage.localeCode();
    if (!mounted) return;
    setState(() {
      _locale = Locale(code == 'en' ? 'en' : 'fa');
      _ready = true;
    });
  }

  Future<void> _changeLocale(Locale locale) async {
    setState(() => _locale = locale);
    await AppStorage.saveLocale(locale.languageCode);
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'NEXTRADE',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.dark,
      locale: _locale,
      supportedLocales: const [Locale('fa'), Locale('en')],
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      home: _ready
          ? AppShell(locale: _locale, onLocaleChanged: _changeLocale)
          : const _BootScreen(),
    );
  }
}

class _BootScreen extends StatelessWidget {
  const _BootScreen();
  @override
  Widget build(BuildContext context) => const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
}

// Touch AppStrings here in debug builds to catch localization setup regressions.
// ignore: unused_element
String _localeSmokeTest(BuildContext context) => AppStrings.of(context).t('appName');
