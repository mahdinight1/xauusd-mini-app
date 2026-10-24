import 'package:flutter/material.dart';
import '../../core/l10n/app_strings.dart';
import '../../core/services/market_api.dart';
import '../../core/theme/app_theme.dart';

class SignalsPage extends StatefulWidget {
  const SignalsPage({super.key});
  @override
  State<SignalsPage> createState() => _SignalsPageState();
}

class _SignalsPageState extends State<SignalsPage> {
  String _symbol = 'BTCUSDT';
  String _interval = '15m';
  bool _loading = false;
  String? _error;
  Map<String, dynamic>? _analysis;
  static const _symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'ADAUSDT'];
  static const _intervals = ['1m', '5m', '15m', '30m', '1h', '4h', '1d'];

  String _symbolLabel(String value) => value.endsWith('USDT') ? '${value.substring(0, value.length - 4)}/USDT' : value;
  String _fmt(dynamic raw) {
    if (raw is! num) return '—';
    final value = raw.toDouble();
    if (value.abs() >= 1000) return value.toStringAsFixed(2);
    if (value.abs() >= 1) return value.toStringAsFixed(4);
    return value.toStringAsFixed(6);
  }

  Future<void> _analyze() async {
    setState(() { _loading = true; _error = null; });
    try {
      final result = await MarketApi.instance.analyze(symbol: _symbol, interval: _interval);
      if (!mounted) return;
      setState(() => _analysis = result);
    } catch (_) {
      if (!mounted) return;
      setState(() => _error = AppStrings.of(context).isPersian
          ? 'تحلیل دریافت نشد. آدرس بک‌اند، اینترنت و اتصال منبع بازار را بررسی کن.'
          : 'Analysis unavailable. Check the backend URL, network, and market-data provider.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = AppStrings.of(context);
    final fa = s.isPersian;
    final result = _analysis;
    final direction = result?['direction']?.toString() ?? 'NO_TRADE';
    final isLong = direction == 'LONG';
    final isShort = direction == 'SHORT';
    final directionColor = isLong ? AppTheme.positive : isShort ? AppTheme.negative : AppTheme.muted;
    final levels = result?['levels'] is Map ? Map<String, dynamic>.from(result!['levels'] as Map) : null;
    final reasons = result?['reasons'] is List ? (result!['reasons'] as List).map((v) => v.toString()).toList() : <String>[];
    final indicators = result?['indicators'] is Map ? Map<String, dynamic>.from(result!['indicators'] as Map) : <String, dynamic>{};

    return ListView(padding: const EdgeInsets.fromLTRB(16, 10, 16, 28), children: [
      Text(s.t('signals'), style: Theme.of(context).textTheme.headlineMedium),
      const SizedBox(height: 6),
      Text(fa ? 'تحلیل قواعدمحور با کندل‌های واقعی بازار' : 'Rule-based analysis using real market candles', style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: AppTheme.muted)),
      const SizedBox(height: 17),
      Container(padding: const EdgeInsets.all(14), decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(18), border: Border.all(color: const Color(0xFF263241))), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [Expanded(child: Text(fa ? 'تحلیل دستی' : 'Manual analysis', style: Theme.of(context).textTheme.titleLarge)), Icon(Icons.analytics_outlined, color: AppTheme.accent)]),
        const SizedBox(height: 12),
        Row(children: [
          Expanded(child: DropdownButtonFormField<String>(value: _symbol, isExpanded: true, decoration: InputDecoration(labelText: fa ? 'بازار' : 'Market', contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 12)), items: _symbols.map((v) => DropdownMenuItem(value: v, child: Text(_symbolLabel(v)))).toList(), onChanged: _loading ? null : (v) { if (v != null) setState(() => _symbol = v); })),
          const SizedBox(width: 10),
          Expanded(child: DropdownButtonFormField<String>(value: _interval, isExpanded: true, decoration: InputDecoration(labelText: fa ? 'تایم‌فریم' : 'Timeframe', contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 12)), items: _intervals.map((v) => DropdownMenuItem(value: v, child: Text(v))).toList(), onChanged: _loading ? null : (v) { if (v != null) setState(() => _interval = v); })),
        ]),
        const SizedBox(height: 12),
        SizedBox(width: double.infinity, child: FilledButton.icon(onPressed: _loading ? null : _analyze, icon: _loading ? const SizedBox(width: 17, height: 17, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.bolt_rounded), label: Text(_loading ? (fa ? 'در حال تحلیل…' : 'Analyzing…') : (fa ? 'تحلیل بازار' : 'Analyze market')))),
        if (_error != null) ...[const SizedBox(height: 12), Text(_error!, style: Theme.of(context).textTheme.bodySmall?.copyWith(color: AppTheme.negative))],
      ])),
      const SizedBox(height: 16),
      if (result == null && !_loading && _error == null) Container(padding: const EdgeInsets.all(22), decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(22), border: Border.all(color: const Color(0xFF263241))), child: Column(children: [Container(width: 64, height: 64, decoration: BoxDecoration(color: AppTheme.accent.withOpacity(.10), borderRadius: BorderRadius.circular(20)), child: const Icon(Icons.query_stats_rounded, color: AppTheme.accent, size: 32)), const SizedBox(height: 14), Text(fa ? 'هنوز تحلیلی اجرا نشده' : 'No analysis run yet', style: Theme.of(context).textTheme.titleLarge), const SizedBox(height: 7), Text(fa ? 'نماد و تایم‌فریم را انتخاب کن و تحلیل را اجرا کن. اگر داده کافی یا معتبر نباشد، سیستم ورود ساختگی نمی‌سازد.' : 'Choose a symbol and timeframe, then run the analysis. If market data is missing or insufficient, the engine will not invent an entry.', textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: AppTheme.muted))])),
      if (result != null) ...[
        Container(padding: const EdgeInsets.all(16), decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(20), border: Border.all(color: directionColor.withOpacity(.45))), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [Expanded(child: Text('${_symbolLabel(_symbol)} · $_interval', style: Theme.of(context).textTheme.titleMedium)), Container(padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6), decoration: BoxDecoration(color: directionColor.withOpacity(.12), borderRadius: BorderRadius.circular(30)), child: Text(direction, style: TextStyle(color: directionColor, fontWeight: FontWeight.w900, fontSize: 12)))]),
          const SizedBox(height: 13),
          Row(crossAxisAlignment: CrossAxisAlignment.end, children: [Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(fa ? 'امتیاز هم‌گرایی' : 'Confluence score', style: Theme.of(context).textTheme.bodySmall), const SizedBox(height: 3), Text('${_fmt(result['score'])}/100', style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w900))])), Chip(label: Text(result['quality']?.toString() ?? 'NO_TRADE'), side: BorderSide(color: directionColor.withOpacity(.5)), backgroundColor: directionColor.withOpacity(.10))]),
          const SizedBox(height: 12),
          ClipRRect(borderRadius: BorderRadius.circular(6), child: LinearProgressIndicator(value: ((result['score'] is num ? (result['score'] as num).toDouble() : 0.0) / 100).clamp(0, 1).toDouble(), minHeight: 7, backgroundColor: const Color(0xFF273442), color: directionColor)),
          const SizedBox(height: 12),
          Wrap(spacing: 8, runSpacing: 8, children: [
            _ScoreChip(label: fa ? 'امتیاز خرید' : 'Long score', value: _fmt(result['long_score']), color: AppTheme.positive),
            _ScoreChip(label: fa ? 'امتیاز فروش' : 'Short score', value: _fmt(result['short_score']), color: AppTheme.negative),
            _ScoreChip(label: fa ? 'رژیم بازار' : 'Market regime', value: result['market_regime']?.toString() ?? '—', color: AppTheme.accent),
          ]),
          const SizedBox(height: 10),
          Text(fa ? 'راهبرد: قواعد هم‌گرایی EMA، RSI، MACD، ADX، VWAP، حجم و ساختار کوتاه‌مدت' : 'Strategy: EMA, RSI, MACD, ADX, VWAP, volume, and short-term structure confluence', style: Theme.of(context).textTheme.bodySmall),
        ])),
        const SizedBox(height: 14),
        if (levels != null) ...[
          Text(fa ? 'قیمت‌های محاسبه‌شده' : 'Calculated trade levels', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 8),
          Container(padding: const EdgeInsets.all(14), decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(18), border: Border.all(color: const Color(0xFF263241))), child: Column(children: [
            _LevelRow(label: fa ? 'ورود (Entry)' : 'Entry', value: _fmt(levels['entry']), color: AppTheme.accent, direction: Directionality.of(context)),
            _LevelRow(label: fa ? 'حد ضرر (SL)' : 'Stop-loss', value: _fmt(levels['stop_loss']), color: AppTheme.negative, direction: Directionality.of(context)),
            const Divider(height: 20),
            _LevelRow(label: 'TP1 · 1R', value: _fmt(levels['tp1']), color: AppTheme.positive, direction: Directionality.of(context)),
            _LevelRow(label: 'TP2 · 2R', value: _fmt(levels['tp2']), color: AppTheme.positive, direction: Directionality.of(context)),
            _LevelRow(label: 'TP3 · 3R', value: _fmt(levels['tp3']), color: AppTheme.positive, direction: Directionality.of(context)),
            const Divider(height: 20),
            _LevelRow(label: fa ? 'ریسک پیشنهادی' : 'Suggested risk', value: '${_fmt(levels['suggested_risk_percent'])}%', color: AppTheme.muted, direction: Directionality.of(context)),
            const SizedBox(height: 8),
            Text(levels['method']?.toString() ?? '', style: Theme.of(context).textTheme.bodySmall),
          ])),
        ] else Container(padding: const EdgeInsets.all(14), decoration: BoxDecoration(color: const Color(0xFF1B1A16), borderRadius: BorderRadius.circular(16), border: Border.all(color: const Color(0xFF51452A))), child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [const Icon(Icons.block_rounded, color: Color(0xFFFBBF24)), const SizedBox(width: 9), Expanded(child: Text(fa ? 'شرایط ورود معتبر تأیید نشد؛ بنابراین قیمت ورود، حد ضرر و اهداف معاملاتی ارائه نشده‌اند.' : 'No valid entry setup passed the rules; entry, stop-loss, and targets are intentionally not provided.', style: Theme.of(context).textTheme.bodyMedium))])),
        const SizedBox(height: 14),
        Text(fa ? 'دلایل تحلیل' : 'Analysis rationale', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 8),
        Container(padding: const EdgeInsets.all(14), decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(16), border: Border.all(color: const Color(0xFF263241))), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: reasons.map((reason) => Padding(padding: const EdgeInsets.only(bottom: 8), child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [const Icon(Icons.check_circle_outline_rounded, size: 17, color: AppTheme.accent), const SizedBox(width: 8), Expanded(child: Text(reason, style: Theme.of(context).textTheme.bodyMedium))]))).toList())),
        const SizedBox(height: 14),
        Text(fa ? 'اندیکاتورهای کلیدی' : 'Key indicators', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 8),
        Wrap(spacing: 8, runSpacing: 8, children: ['RSI14', 'EMA20', 'EMA50', 'MACD histogram', 'ATR14', 'ADX14', 'VWAP20'].map((key) => Container(padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8), decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(12), border: Border.all(color: const Color(0xFF263241))), child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [Text(key, style: Theme.of(context).textTheme.bodySmall), const SizedBox(height: 4), Text(_fmt(indicators[_indicatorKey(key)]), style: const TextStyle(fontWeight: FontWeight.w800))]))).toList()),
        const SizedBox(height: 14),
        Container(padding: const EdgeInsets.all(14), decoration: BoxDecoration(color: const Color(0xFF1B1A16), borderRadius: BorderRadius.circular(16), border: Border.all(color: const Color(0xFF51452A))), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Row(children: [const Icon(Icons.warning_amber_rounded, color: Color(0xFFFBBF24)), const SizedBox(width: 8), Expanded(child: Text(fa ? 'راهبرد آزمایشی و اعتبارسنجی‌نشده' : 'Experimental, unvalidated strategy', style: const TextStyle(fontWeight: FontWeight.w800, color: Color(0xFFFBBF24))))]), const SizedBox(height: 7), Text(fa ? 'امتیاز، احتمال برد نیست. این الگوریتم هنوز بک‌تست و اعتبارسنجی آماری قابل اتکا ندارد. کارمزد، لغزش قیمت و عمق دفتر سفارش در سطوح لحاظ نشده‌اند؛ سفارش واقعی اجرا نمی‌شود.' : 'The score is not a win probability. This algorithm has not undergone reliable backtesting or statistical calibration. Fees, slippage, and order-book depth are not included in levels; no real orders are placed.', style: Theme.of(context).textTheme.bodySmall?.copyWith(color: const Color(0xFFD6C9AA)))])),
      ],
    ]);
  }

  String _indicatorKey(String display) => switch (display) {
        'RSI14' => 'rsi14', 'EMA20' => 'ema20', 'EMA50' => 'ema50', 'MACD histogram' => 'macd_histogram', 'ATR14' => 'atr14', 'ADX14' => 'adx14', 'VWAP20' => 'vwap20', _ => display,
      };
}

class _ScoreChip extends StatelessWidget {
  const _ScoreChip({required this.label, required this.value, required this.color});
  final String label;
  final String value;
  final Color color;
  @override
  Widget build(BuildContext context) => Container(padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 7), decoration: BoxDecoration(color: color.withOpacity(.09), borderRadius: BorderRadius.circular(12), border: Border.all(color: color.withOpacity(.25))), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(label, style: Theme.of(context).textTheme.bodySmall), const SizedBox(height: 3), Text(value, style: TextStyle(color: color, fontWeight: FontWeight.w800, fontSize: 12))]));
}

class _LevelRow extends StatelessWidget {
  const _LevelRow({required this.label, required this.value, required this.color, required this.direction});
  final String label;
  final String value;
  final Color color;
  final TextDirection direction;
  @override
  Widget build(BuildContext context) => Padding(padding: const EdgeInsets.symmetric(vertical: 7), child: Row(textDirection: direction, children: [Expanded(child: Text(label, style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: AppTheme.muted))), Text(value, style: TextStyle(fontWeight: FontWeight.w900, color: color, fontSize: 15))]));
}
