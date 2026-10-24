import 'dart:async';
import 'package:flutter/material.dart';
import '../../core/l10n/app_strings.dart';
import '../../core/services/market_api.dart';
import '../../core/theme/app_theme.dart';

class MarketsPage extends StatefulWidget {
  const MarketsPage({super.key});
  @override
  State<MarketsPage> createState() => _MarketsPageState();
}

class _MarketsPageState extends State<MarketsPage> {
  final _search = TextEditingController();
  bool _favoritesOnly = false;
  bool _loading = true;
  String? _error;
  List<Map<String, dynamic>> _quotes = [];
  final Set<String> _favorites = {'BTCUSDT', 'ETHUSDT'};
  Timer? _refreshTimer;

  @override
  void initState() {
    super.initState();
    _refresh();
    _refreshTimer = Timer.periodic(const Duration(seconds: 12), (_) => _refresh(silent: true));
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    _search.dispose();
    super.dispose();
  }

  Future<void> _refresh({bool silent = false}) async {
    if (!silent && mounted) setState(() { _loading = true; _error = null; });
    try {
      final result = await MarketApi.instance.markets();
      if (!mounted) return;
      setState(() { _quotes = result; _loading = false; _error = null; });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        if (_quotes.isEmpty) _error = AppStrings.of(context).isPersian
            ? 'دریافت قیمت واقعی ممکن نشد. آدرس بک‌اند و اتصال شبکه را بررسی کن.'
            : 'Could not retrieve real prices. Check the backend URL and network.';
      });
    }
  }

  String _format(dynamic raw) {
    if (raw is! num) return '—';
    final value = raw.toDouble();
    if (value.abs() >= 1000) return value.toStringAsFixed(2);
    if (value.abs() >= 1) return value.toStringAsFixed(4);
    return value.toStringAsFixed(6);
  }

  String _pairLabel(String symbol) => symbol.endsWith('USDT') ? '${symbol.substring(0, symbol.length - 4)}/USDT' : symbol;
  String _assetName(String symbol) => switch (symbol) {
        'BTCUSDT' => 'Bitcoin', 'ETHUSDT' => 'Ethereum', 'SOLUSDT' => 'Solana',
        'BNBUSDT' => 'BNB', 'XRPUSDT' => 'XRP', 'ADAUSDT' => 'Cardano', _ => symbol,
      };

  @override
  Widget build(BuildContext context) {
    final s = AppStrings.of(context);
    final fa = s.isPersian;
    final query = _search.text.toLowerCase().replaceAll('/', '');
    final visible = _quotes.where((item) {
      final symbol = item['symbol']?.toString() ?? '';
      final name = _assetName(symbol);
      return (!_favoritesOnly || _favorites.contains(symbol)) && ('$symbol $name'.toLowerCase().contains(query));
    }).toList();
    return RefreshIndicator(
      onRefresh: () => _refresh(),
      child: ListView(padding: const EdgeInsets.fromLTRB(16, 10, 16, 24), children: [
        Row(children: [Expanded(child: Text(s.t('markets'), style: Theme.of(context).textTheme.headlineMedium)), IconButton(onPressed: _loading ? null : _refresh, tooltip: s.t('refresh'), icon: const Icon(Icons.refresh_rounded))]),
        const SizedBox(height: 14),
        TextField(controller: _search, onChanged: (_) => setState(() {}), decoration: InputDecoration(hintText: s.t('searchMarkets'), prefixIcon: const Icon(Icons.search_rounded), suffixIcon: _search.text.isEmpty ? null : IconButton(onPressed: () { _search.clear(); setState(() {}); }, icon: const Icon(Icons.close_rounded)))),
        const SizedBox(height: 12),
        Align(alignment: AlignmentDirectional.centerStart, child: Wrap(spacing: 8, children: [FilterChip(label: Text(s.t('allMarkets')), selected: !_favoritesOnly, onSelected: (_) => setState(() => _favoritesOnly = false)), FilterChip(label: Text(s.t('favorites')), selected: _favoritesOnly, onSelected: (_) => setState(() => _favoritesOnly = true))])),
        const SizedBox(height: 12),
        Container(padding: const EdgeInsets.all(12), decoration: BoxDecoration(color: const Color(0xFF142A25), borderRadius: BorderRadius.circular(14), border: Border.all(color: const Color(0xFF285344))), child: Row(children: [const Icon(Icons.cloud_done_rounded, color: AppTheme.positive), const SizedBox(width: 9), Expanded(child: Text(fa ? 'منبع: دادهٔ عمومی بایننس اسپات · به‌روزرسانی دوره‌ای' : 'Source: Binance Spot public feed · periodic refresh', style: Theme.of(context).textTheme.bodySmall))])),
        const SizedBox(height: 16),
        Row(children: [Expanded(child: Text(s.t('symbol'), style: Theme.of(context).textTheme.bodySmall)), Text(s.t('price'), style: Theme.of(context).textTheme.bodySmall), const SizedBox(width: 12)]),
        const SizedBox(height: 8),
        if (_loading && _quotes.isEmpty) const Padding(padding: EdgeInsets.all(28), child: Center(child: CircularProgressIndicator())),
        if (_error != null) Container(padding: const EdgeInsets.all(14), decoration: BoxDecoration(color: const Color(0xFF2B1D1D), borderRadius: BorderRadius.circular(14)), child: Text(_error!, style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: AppTheme.negative))),
        ...visible.map((item) {
          final symbol = item['symbol']?.toString() ?? '';
          final change = item['change_24h_percent'] is num ? (item['change_24h_percent'] as num).toDouble() : null;
          final positive = (change ?? 0) >= 0;
          return Container(margin: const EdgeInsets.only(bottom: 8), padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12), decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(16), border: Border.all(color: const Color(0xFF263241))), child: Row(children: [
            Container(width: 40, height: 40, decoration: BoxDecoration(color: AppTheme.surface2, borderRadius: BorderRadius.circular(13)), child: Icon(symbol.startsWith('BTC') ? Icons.currency_bitcoin_rounded : Icons.show_chart_rounded, color: AppTheme.accent)),
            const SizedBox(width: 11),
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(_pairLabel(symbol), style: const TextStyle(fontWeight: FontWeight.w800)), Text(_assetName(symbol), style: Theme.of(context).textTheme.bodySmall), if (change != null) Text('${change >= 0 ? '+' : ''}${change.toStringAsFixed(2)}%', style: TextStyle(fontSize: 11, color: positive ? AppTheme.positive : AppTheme.negative, fontWeight: FontWeight.w700))])),
            Column(crossAxisAlignment: CrossAxisAlignment.end, children: [Text(_format(item['last_price']), style: const TextStyle(fontWeight: FontWeight.w800)), if (item['volume_24h'] is num) Text('${fa ? 'حجم' : 'Vol'} ${_format(item['volume_24h'])}', style: Theme.of(context).textTheme.bodySmall)]),
            IconButton(visualDensity: VisualDensity.compact, onPressed: () => setState(() => _favorites.contains(symbol) ? _favorites.remove(symbol) : _favorites.add(symbol)), icon: Icon(_favorites.contains(symbol) ? Icons.star_rounded : Icons.star_outline_rounded, color: _favorites.contains(symbol) ? const Color(0xFFFBBF24) : AppTheme.muted)),
          ]));
        }),
        if (!_loading && visible.isEmpty && _error == null) Padding(padding: const EdgeInsets.all(24), child: Center(child: Text(fa ? 'بازاری پیدا نشد' : 'No markets found'))),
      ]),
    );
  }
}
