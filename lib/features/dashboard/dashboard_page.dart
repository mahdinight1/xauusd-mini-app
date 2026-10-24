import 'package:flutter/material.dart';
import '../../core/l10n/app_strings.dart';
import '../../core/theme/app_theme.dart';
import '../../core/services/app_storage.dart';

class DashboardPage extends StatefulWidget {
  const DashboardPage({super.key, required this.onOpenMarkets, required this.onOpenSignals, required this.onOpenDemo, required this.onOpenAcademy, required this.onOpenCharts});
  final VoidCallback onOpenMarkets, onOpenSignals, onOpenDemo, onOpenAcademy, onOpenCharts;
  @override
  State<DashboardPage> createState() => _DashboardPageState();
}

class _DashboardPageState extends State<DashboardPage> {
  double? _capital;
  String _apiUrl = 'http://10.0.2.2:8000';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final values = await Future.wait([AppStorage.demoCapital(), AppStorage.apiBaseUrl()]);
    if (!mounted) return;
    setState(() { _capital = values[0] as double?; _apiUrl = values[1] as String; });
  }

  @override
  Widget build(BuildContext context) {
    final s = AppStrings.of(context);
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 10, 16, 28),
      children: [
        Text(s.t('welcome'), style: Theme.of(context).textTheme.headlineMedium),
        const SizedBox(height: 6),
        Text(s.t('tagline'), style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: AppTheme.muted)),
        const SizedBox(height: 20),
        _MarketStatusCard(onTap: widget.onOpenMarkets),
        const SizedBox(height: 14),
        Row(children: [
          Expanded(child: _StatCard(icon: Icons.account_balance_wallet_outlined, label: s.t('demoAccount'), value: _capital == null ? s.t('notCreated') : _formatAmount(_capital!), accent: AppTheme.accent, foot: s.t('virtualOnly'), onTap: widget.onOpenDemo)),
          const SizedBox(width: 12),
          Expanded(child: _StatCard(icon: Icons.bolt_rounded, label: s.t('latestSignals'), value: '0', accent: const Color(0xFFC4B5FD), foot: s.t('noSignals'), onTap: widget.onOpenSignals)),
        ]),
        const SizedBox(height: 22),
        _SectionHeader(title: s.t('watchlist'), action: s.t('viewAll'), onTap: widget.onOpenMarkets),
        const SizedBox(height: 10),
        const _SymbolTile(symbol: 'BTC/USDT', name: 'Bitcoin'),
        const _SymbolTile(symbol: 'ETH/USDT', name: 'Ethereum'),
        const _SymbolTile(symbol: 'SOL/USDT', name: 'Solana'),
        const SizedBox(height: 22),
        _SectionHeader(title: s.t('quickAccess')),
        const SizedBox(height: 10),
        Row(children: [
          Expanded(child: _QuickTile(icon: Icons.show_chart_rounded, title: s.t('advancedCharts'), subtitle: s.t('chartsNotice'), onTap: widget.onOpenCharts)),
          const SizedBox(width: 12),
          Expanded(child: _QuickTile(icon: Icons.school_rounded, title: s.t('tradingAcademy'), subtitle: s.t('learningPath'), onTap: widget.onOpenAcademy)),
        ]),
        const SizedBox(height: 18),
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(color: const Color(0xFF14212D), borderRadius: BorderRadius.circular(18), border: Border.all(color: const Color(0xFF254458))),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Icon(Icons.shield_outlined, color: AppTheme.accent), const SizedBox(width: 12),
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(s.t('legalTitle'), style: Theme.of(context).textTheme.titleMedium), const SizedBox(height: 5), Text(s.t('legalBody'), style: Theme.of(context).textTheme.bodySmall)])),
          ]),
        ),
        const SizedBox(height: 10),
        Text('${s.t('server')}: $_apiUrl', style: Theme.of(context).textTheme.bodySmall, textAlign: TextAlign.center, maxLines: 1, overflow: TextOverflow.ellipsis),
      ],
    );
  }

  String _formatAmount(double value) => value.toStringAsFixed(2);
}

class _MarketStatusCard extends StatelessWidget {
  const _MarketStatusCard({required this.onTap});
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) {
    final s = AppStrings.of(context);
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(22),
      child: Container(
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(22),
          gradient: const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFF172B3A), Color(0xFF121923)]),
          border: Border.all(color: const Color(0xFF2C4E61)),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [const Icon(Icons.wifi_off_rounded, color: AppTheme.muted, size: 18), const SizedBox(width: 8), Text(s.t('marketStatus'), style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w800, letterSpacing: 1.2, color: AppTheme.muted)), const Spacer(), const _StatusPill()],),
          const SizedBox(height: 18),
          Text(s.t('notConnected'), style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 7),
          Text(s.t('connectProvider'), style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: AppTheme.muted)),
          const SizedBox(height: 14),
          Row(children: [Text(s.t('noFabricatedData'), style: Theme.of(context).textTheme.bodySmall), const Spacer(), const Icon(Icons.arrow_forward_rounded, color: AppTheme.accent, size: 18)]),
        ]),
      ),
    );
  }
}

class _StatusPill extends StatelessWidget {
  const _StatusPill();
  @override
  Widget build(BuildContext context) {
    final s = AppStrings.of(context);
    return Container(padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5), decoration: BoxDecoration(color: const Color(0x22F87171), borderRadius: BorderRadius.circular(30)), child: Text(s.t('disconnected'), style: const TextStyle(color: AppTheme.negative, fontSize: 10, fontWeight: FontWeight.w700)));
  }
}

class _StatCard extends StatelessWidget {
  const _StatCard({required this.icon, required this.label, required this.value, required this.accent, required this.foot, required this.onTap});
  final IconData icon; final String label, value, foot; final Color accent; final VoidCallback onTap;
  @override
  Widget build(BuildContext context) => InkWell(onTap: onTap, borderRadius: BorderRadius.circular(20), child: Container(padding: const EdgeInsets.all(15), decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(20), border: Border.all(color: const Color(0xFF263241))), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Icon(icon, color: accent), const SizedBox(height: 12), Text(label, style: Theme.of(context).textTheme.bodySmall), const SizedBox(height: 6), Text(value, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800)), const SizedBox(height: 5), Text(foot, maxLines: 2, overflow: TextOverflow.ellipsis, style: Theme.of(context).textTheme.bodySmall)])));
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.title, this.action, this.onTap});
  final String title; final String? action; final VoidCallback? onTap;
  @override
  Widget build(BuildContext context) => Row(children: [Expanded(child: Text(title, style: Theme.of(context).textTheme.titleLarge)), if (action != null) TextButton(onPressed: onTap, child: Text(action!))]);
}

class _SymbolTile extends StatelessWidget {
  const _SymbolTile({required this.symbol, required this.name});
  final String symbol, name;
  @override
  Widget build(BuildContext context) => Container(margin: const EdgeInsets.only(bottom: 8), padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 12), decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(15), border: Border.all(color: const Color(0xFF202D3B))), child: Row(children: [Container(width: 38, height: 38, decoration: BoxDecoration(color: AppTheme.surface2, borderRadius: BorderRadius.circular(12)), child: Icon(symbol.startsWith('BTC') ? Icons.currency_bitcoin_rounded : Icons.show_chart_rounded, color: AppTheme.accent)), const SizedBox(width: 11), Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(symbol, style: const TextStyle(fontWeight: FontWeight.w800)), Text(name, style: Theme.of(context).textTheme.bodySmall)])), Text('—', style: Theme.of(context).textTheme.titleMedium?.copyWith(color: AppTheme.muted))]));
}

class _QuickTile extends StatelessWidget {
  const _QuickTile({required this.icon, required this.title, required this.subtitle, required this.onTap});
  final IconData icon; final String title, subtitle; final VoidCallback onTap;
  @override
  Widget build(BuildContext context) => InkWell(onTap: onTap, borderRadius: BorderRadius.circular(18), child: Container(height: 125, padding: const EdgeInsets.all(15), decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(18), border: Border.all(color: const Color(0xFF263241))), child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [Icon(icon, color: AppTheme.accent, size: 25), Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(title, style: const TextStyle(fontWeight: FontWeight.w700)), const SizedBox(height: 3), Text(subtitle, style: Theme.of(context).textTheme.bodySmall, maxLines: 1, overflow: TextOverflow.ellipsis)])])));
}
