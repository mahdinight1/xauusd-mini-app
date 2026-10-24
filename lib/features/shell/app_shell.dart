import 'package:flutter/material.dart';
import '../../core/l10n/app_strings.dart';
import '../../core/theme/app_theme.dart';
import '../academy/academy_page.dart';
import '../account/membership_exchanges_page.dart';
import '../charts/chart_page.dart';
import '../dashboard/dashboard_page.dart';
import '../demo/demo_page.dart';
import '../markets/markets_page.dart';
import '../settings/settings_page.dart';
import '../signals/signals_page.dart';
import '../tools/tools_page.dart';

class AppShell extends StatefulWidget {
  const AppShell({super.key, required this.locale, required this.onLocaleChanged});
  final Locale locale;
  final ValueChanged<Locale> onLocaleChanged;
  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  int _index = 0;
  void _goTo(int value) => setState(() => _index = value);

  @override
  Widget build(BuildContext context) {
    final s = AppStrings.of(context);
    final pages = <Widget>[
      DashboardPage(onOpenMarkets: () => _goTo(1), onOpenSignals: () => _goTo(2), onOpenDemo: () => _goTo(3), onOpenAcademy: () => _goTo(4), onOpenCharts: () => _openCharts(context)),
      const MarketsPage(), const SignalsPage(), const DemoPage(), const AcademyPage(),
    ];
    final labels = [s.t('dashboard'), s.t('markets'), s.t('signals'), s.t('demo'), s.t('academy')];
    final icons = [Icons.dashboard_rounded, Icons.show_chart_rounded, Icons.bolt_rounded, Icons.account_balance_wallet_rounded, Icons.school_rounded];
    return Scaffold(
      appBar: AppBar(
        titleSpacing: 16,
        title: Row(mainAxisSize: MainAxisSize.min, children: [
          Container(width: 34, height: 34, decoration: BoxDecoration(borderRadius: BorderRadius.circular(11), gradient: const LinearGradient(colors: [AppTheme.accent, Color(0xFF2563EB)]), boxShadow: const [BoxShadow(color: Color(0x3338BDF8), blurRadius: 14)]), child: const Icon(Icons.show_chart_rounded, color: Colors.white, size: 22)),
          const SizedBox(width: 10),
          const Text('NEXTRADE', style: TextStyle(fontWeight: FontWeight.w900, letterSpacing: 1.1, fontSize: 18)),
        ]),
        actions: [
          IconButton(tooltip: s.isPersian ? 'حساب و اشتراک' : 'Account & membership', onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const MembershipExchangesPage())), icon: const Icon(Icons.workspace_premium_rounded)),
          IconButton(tooltip: s.t('tools'), onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const ToolsPage())), icon: const Icon(Icons.event_note_rounded)),
          IconButton(tooltip: s.t('settings'), onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => SettingsPage(locale: widget.locale, onLocaleChanged: widget.onLocaleChanged))), icon: const Icon(Icons.tune_rounded)),
          const SizedBox(width: 6),
        ],
      ),
      body: IndexedStack(index: _index, children: pages),
      bottomNavigationBar: NavigationBar(selectedIndex: _index, onDestinationSelected: _goTo, destinations: List.generate(labels.length, (i) => NavigationDestination(icon: Icon(icons[i]), selectedIcon: Icon(icons[i], color: AppTheme.accent), label: labels[i]))),
    );
  }

  void _openCharts(BuildContext context) => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const ChartPage()));
}

