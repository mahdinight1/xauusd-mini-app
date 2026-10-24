import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../../core/l10n/app_strings.dart';
import '../../core/services/market_api.dart';
import '../../core/theme/app_theme.dart';
import 'candle.dart';
import 'candlestick_chart.dart';

class ChartPage extends StatefulWidget {
  const ChartPage({super.key});

  @override
  State<ChartPage> createState() => _ChartPageState();
}

class _ChartPageState extends State<ChartPage> {
  String _symbol = 'BTCUSDT';
  String _interval = '1m';
  List<Candle> _candles = [];
  Map<String, dynamic> _indicators = {};
  bool _loading = true;
  bool _analyzing = false;
  bool _live = false;
  Map<String, dynamic>? _analysis;
  bool _showEma20 = true;
  bool _showEma50 = true;
  bool _showBollinger = false;
  bool _showSupertrend = true;
  bool _showIchimoku = false;
  bool _showDonchian = false;
  String? _error;
  int _visibleBars = 80;
  int _endOffset = 0;
  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _subscription;
  Timer? _reconnectTimer;
  Timer? _indicatorTimer;
  Timer? _heartbeatTimer;
  DateTime? _lastStreamEventAt;
  DateTime? _streamConnectedAt;
  bool _disposed = false;
  bool _reconnectScheduled = false;

  static const _symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'ADAUSDT'];
  static const _intervals = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '12h', '1d', '1w'];

  @override
  void initState() {
    super.initState();
    _loadInitial();
  }

  @override
  void dispose() {
    _disposed = true;
    _reconnectTimer?.cancel();
    _reconnectScheduled = false;
    _indicatorTimer?.cancel();
    _heartbeatTimer?.cancel();
    _subscription?.cancel();
    _channel?.sink.close();
    super.dispose();
  }

  Future<void> _loadInitial() async {
    await _loadCandles();
    if (_disposed) return;
    _connectLive();
    _indicatorTimer?.cancel();
    _indicatorTimer = Timer.periodic(const Duration(seconds: 30), (_) => _refreshIndicators(silent: true));
  }

  Future<void> _loadCandles() async {
    setState(() {
      _loading = true;
      _error = null;
      _live = false;
    });
    try {
      final result = await MarketApi.instance.fetchCandles(symbol: _symbol, interval: _interval, limit: 300);
      final items = (result['candles'] as List).whereType<Map>().map((item) => Candle.fromJson(Map<String, dynamic>.from(item))).toList();
      if (_disposed) return;
      setState(() {
        _candles = items;
        _loading = false;
        _endOffset = 0;
      });
      await _refreshIndicators(silent: true);
    } catch (error) {
      if (_disposed) return;
      setState(() {
        _loading = false;
        _error = _friendlyError(error);
      });
    }
  }

  Future<void> _refreshIndicators({bool silent = false}) async {
    try {
      final response = await MarketApi.instance.fetchIndicators(symbol: _symbol, interval: _interval);
      if (!_disposed && response['indicators'] is Map) {
        setState(() => _indicators = Map<String, dynamic>.from(response['indicators'] as Map));
      }
    } catch (_) {
      if (!silent && mounted) setState(() => _error = 'Indicator data unavailable.');
    }
  }

  void _connectLive() {
    if (_disposed) return;
    try {
      _lastStreamEventAt = null;
      _streamConnectedAt = DateTime.now();
      final uri = Uri.parse('wss://data-stream.binance.vision/ws/${_symbol.toLowerCase()}@kline_$_interval');
      final channel = WebSocketChannel.connect(uri);
      _heartbeatTimer ??= Timer.periodic(const Duration(seconds: 5), (_) {
        final reference = _lastStreamEventAt ?? _streamConnectedAt;
        if (reference != null && DateTime.now().difference(reference).inSeconds > 12) {
          _scheduleReconnect();
        }
      });
      _channel = channel;
      _subscription = channel.stream.listen(
        _handleLiveMessage,
        onError: (_) => _scheduleReconnect(),
        onDone: _scheduleReconnect,
        cancelOnError: true,
      );
    } catch (_) {
      _scheduleReconnect();
    }
  }

  void _scheduleReconnect() {
    if (_disposed || _reconnectScheduled) return;
    _reconnectScheduled = true;
    _lastStreamEventAt = null;
    _streamConnectedAt = DateTime.now();
    if (mounted) setState(() => _live = false);
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(const Duration(seconds: 3), () {
      if (_disposed) return;
      _subscription?.cancel();
      _channel?.sink.close();
      _reconnectScheduled = false;
      _connectLive();
    });
  }

  void _handleLiveMessage(dynamic message) {
    try {
      final dynamic decoded = jsonDecode(message is String ? message : utf8.decode(message as List<int>));
      final Map<String, dynamic> payload = Map<String, dynamic>.from(decoded as Map);
      final dynamic rawKline = payload['k'];
      if (rawKline is! Map) return;
      final candle = Candle.fromStreamKline(Map<String, dynamic>.from(rawKline));
      if (_disposed) return;
      _lastStreamEventAt = DateTime.now();
      setState(() {
        final updated = List<Candle>.from(_candles);
        final index = updated.indexWhere((item) => item.openTime == candle.openTime);
        if (index >= 0) {
          updated[index] = candle;
        } else {
          updated.add(candle);
        }
        _candles = updated.length > 500 ? updated.sublist(updated.length - 500) : updated;
        _live = true;
        if (_candles.length >= 60) _error = null;
      });
    } catch (_) {
      // Ignore malformed stream events; never turn them into fabricated candles.
    }
  }

  Future<void> _changePair(String? symbol) async {
    if (symbol == null || symbol == _symbol) return;
    setState(() => _symbol = symbol);
    await _restartFeed();
  }

  Future<void> _changeInterval(String? interval) async {
    if (interval == null || interval == _interval) return;
    setState(() => _interval = interval);
    await _restartFeed();
  }

  Future<void> _restartFeed() async {
    _reconnectTimer?.cancel();
    _reconnectScheduled = false;
    _indicatorTimer?.cancel();
    _heartbeatTimer?.cancel();
    _heartbeatTimer = null;
    await _subscription?.cancel();
    await _channel?.sink.close();
    _channel = null;
    _lastStreamEventAt = null;
    _streamConnectedAt = null;
    if (mounted) setState(() { _candles = []; _indicators = {}; _analysis = null; _endOffset = 0; });
    await _loadCandles();
    if (_disposed) return;
    _connectLive();
    _indicatorTimer = Timer.periodic(const Duration(seconds: 30), (_) => _refreshIndicators(silent: true));
  }

  Future<void> _analyzeForChart() async {
    setState(() { _analyzing = true; _error = null; });
    try {
      final result = await MarketApi.instance.analyze(symbol: _symbol, interval: _interval);
      if (_disposed) return;
      final hasLevels = result['levels'] is Map;
      setState(() {
        _analysis = result;
        if (!hasLevels) _error = AppStrings.of(context).isPersian
            ? 'موتور تحلیل برای این وضعیت ورود معتبر پیدا نکرد؛ سطح معاملاتی روی نمودار رسم نشد.'
            : 'No valid entry setup was found; no trade levels were drawn.';
      });
    } catch (_) {
      if (!_disposed) setState(() => _error = AppStrings.of(context).isPersian
          ? 'تحلیل ناموفق بود. اتصال بک‌اند و منبع داده را بررسی کن.'
          : 'Analysis failed. Check backend connectivity and market data.');
    } finally {
      if (!_disposed) setState(() => _analyzing = false);
    }
  }

  void _viewChanged(int visibleBars, int endOffset) {
    setState(() {
      _visibleBars = visibleBars;
      _endOffset = endOffset;
    });
  }

  String _friendlyError(Object error) {
    if (error.toString().contains('SocketException') || error.toString().contains('connection')) {
      return 'Backend unreachable. Set the deployed API URL in Settings and start the backend.';
    }
    return 'Could not load real candle history. Check the backend URL, network, and provider status.';
  }

  String _pairLabel(String symbol) => symbol.endsWith('USDT') ? '${symbol.substring(0, symbol.length - 4)}/USDT' : symbol;
  String _fmt(dynamic raw) {
    if (raw is! num) return '—';
    final value = raw.toDouble();
    if (value.abs() >= 1000) return value.toStringAsFixed(2);
    if (value.abs() >= 1) return value.toStringAsFixed(4);
    return value.toStringAsFixed(6);
  }

  @override
  Widget build(BuildContext context) {
    final s = AppStrings.of(context);
    final latest = _candles.isEmpty ? null : _candles.last.close;
    return Scaffold(
      appBar: AppBar(
        title: Text(s.t('advancedCharts')),
        actions: [IconButton(tooltip: s.t('refresh'), onPressed: _loading ? null : _restartFeed, icon: const Icon(Icons.refresh_rounded))],
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(14, 8, 14, 26),
        children: [
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(18), border: Border.all(color: const Color(0xFF263241))),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Expanded(child: DropdownButtonHideUnderline(child: DropdownButton<String>(isExpanded: true, value: _symbol, items: _symbols.map((v) => DropdownMenuItem(value: v, child: Text(_pairLabel(v), style: const TextStyle(fontWeight: FontWeight.w800)))).toList(), onChanged: _changePair))),
                const SizedBox(width: 12),
                Container(padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 6), decoration: BoxDecoration(color: (_live ? AppTheme.positive : AppTheme.muted).withOpacity(.12), borderRadius: BorderRadius.circular(30)), child: Row(mainAxisSize: MainAxisSize.min, children: [Container(width: 7, height: 7, decoration: BoxDecoration(color: _live ? AppTheme.positive : AppTheme.muted, shape: BoxShape.circle)), const SizedBox(width: 6), Text(_live ? (s.isPersian ? 'زنده' : 'LIVE') : (s.isPersian ? 'اتصال…' : 'CONNECTING'), style: TextStyle(fontSize: 10, color: _live ? AppTheme.positive : AppTheme.muted, fontWeight: FontWeight.w800))])),
              ]),
              const SizedBox(height: 8),
              Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
                Expanded(child: Text(latest == null ? '—' : _fmt(latest), style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w900, letterSpacing: -.6))),
                Text(s.isPersian ? 'منبع: بایننس اسپات' : 'Source: Binance Spot', style: Theme.of(context).textTheme.bodySmall),
              ]),
              const SizedBox(height: 12),
              SingleChildScrollView(scrollDirection: Axis.horizontal, child: Row(children: _intervals.map((v) => Padding(padding: const EdgeInsetsDirectional.only(end: 7), child: ChoiceChip(label: Text(v), selected: v == _interval, onSelected: (_) => _changeInterval(v)))).toList())),
            ]),
          ),
          const SizedBox(height: 12),
          if (_error != null) Container(padding: const EdgeInsets.all(12), margin: const EdgeInsets.only(bottom: 12), decoration: BoxDecoration(color: const Color(0xFF2B1D1D), borderRadius: BorderRadius.circular(14), border: Border.all(color: const Color(0xFF754040))), child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [const Icon(Icons.warning_amber_rounded, color: AppTheme.negative), const SizedBox(width: 8), Expanded(child: Text(_error!, style: Theme.of(context).textTheme.bodySmall?.copyWith(color: const Color(0xFFFECACA))))])),
          SizedBox(width: double.infinity, child: FilledButton.icon(
            onPressed: _analyzing || _loading ? null : _analyzeForChart,
            icon: _analyzing ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.analytics_rounded),
            label: Text(_analyzing ? (s.isPersian ? 'در حال تحلیل…' : 'Analyzing…') : (s.isPersian ? 'تحلیل و نمایش ورود / SL / TP' : 'Analyze & overlay Entry / SL / TP')),
          )),
          if (_analysis != null) Container(margin: const EdgeInsets.only(top: 9), padding: const EdgeInsets.all(12), decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(14), border: Border.all(color: const Color(0xFF263241))), child: Row(children: [Expanded(child: Text('${_analysis!['direction']} · ${s.isPersian ? 'امتیاز' : 'Score'} ${_fmt(_analysis!['score'])}/100', style: const TextStyle(fontWeight: FontWeight.w800))), Text(_analysis!['quality']?.toString() ?? 'NO_TRADE', style: TextStyle(color: _analysis!['direction'] == 'LONG' ? AppTheme.positive : _analysis!['direction'] == 'SHORT' ? AppTheme.negative : AppTheme.muted, fontWeight: FontWeight.w900))])),
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.all(7),
            decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(18), border: Border.all(color: const Color(0xFF263241))),
            child: Column(children: [
              Row(children: [Expanded(child: Text(s.isPersian ? 'نمودار کندلی' : 'Candlestick chart', style: Theme.of(context).textTheme.titleMedium)), Text(s.isPersian ? 'برای زوم دو انگشت' : 'Pinch to zoom', style: Theme.of(context).textTheme.bodySmall)]),
              const SizedBox(height: 7),
              if (_loading) const SizedBox(height: 340, child: Center(child: CircularProgressIndicator())) else
                CandlestickChart(candles: _candles, visibleBars: _visibleBars, endOffset: _endOffset, showEma20: _showEma20, showEma50: _showEma50, showBollinger: _showBollinger, showSupertrend: _showSupertrend, showIchimoku: _showIchimoku, showDonchian: _showDonchian, signalLevels: _analysis?['levels'] is Map ? Map<String, dynamic>.from(_analysis!['levels'] as Map) : null, onViewChanged: _viewChanged),
              const SizedBox(height: 8),
              Wrap(spacing: 7, runSpacing: 6, children: [
                FilterChip(label: const Text('EMA 20'), selected: _showEma20, onSelected: (v) => setState(() => _showEma20 = v), avatar: const CircleAvatar(radius: 4, backgroundColor: AppTheme.accent)),
                FilterChip(label: const Text('EMA 50'), selected: _showEma50, onSelected: (v) => setState(() => _showEma50 = v), avatar: const CircleAvatar(radius: 4, backgroundColor: Color(0xFFFBBF24))),
                FilterChip(label: const Text('Bollinger'), selected: _showBollinger, onSelected: (v) => setState(() => _showBollinger = v), avatar: const CircleAvatar(radius: 4, backgroundColor: Color(0xFF7C83FD))),
                FilterChip(label: const Text('Supertrend'), selected: _showSupertrend, onSelected: (v) => setState(() => _showSupertrend = v), avatar: const CircleAvatar(radius: 4, backgroundColor: Color(0xFF34D399))),
                FilterChip(label: const Text('Ichimoku'), selected: _showIchimoku, onSelected: (v) => setState(() => _showIchimoku = v), avatar: const CircleAvatar(radius: 4, backgroundColor: Color(0xFFFB7185))),
                FilterChip(label: const Text('Donchian'), selected: _showDonchian, onSelected: (v) => setState(() => _showDonchian = v), avatar: const CircleAvatar(radius: 4, backgroundColor: Color(0xFF60A5FA))),
              ]),
            ]),
          ),
          const SizedBox(height: 16),
          Text(s.isPersian ? 'اندیکاتورهای تکنیکال' : 'Technical indicators', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 10),
          GridView.count(
            crossAxisCount: 2,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            childAspectRatio: 1.75,
            mainAxisSpacing: 8,
            crossAxisSpacing: 8,
            children: [
              _IndicatorTile(title: 'RSI (14)', value: _fmt(_indicators['rsi14']), note: _rsiLabel(_indicators['rsi14'], s.isPersian)),
              _IndicatorTile(title: 'MACD histogram', value: _fmt(_indicators['macd_histogram']), note: _signedLabel(_indicators['macd_histogram'], s.isPersian)),
              _IndicatorTile(title: 'ATR (14)', value: _fmt(_indicators['atr14']), note: s.isPersian ? 'نوسان واقعی' : 'Volatility measure'),
              _IndicatorTile(title: 'ADX (14)', value: _fmt(_indicators['adx14']), note: _adxLabel(_indicators['adx14'], s.isPersian)),
              _IndicatorTile(title: 'EMA 20', value: _fmt(_indicators['ema20']), note: s.isPersian ? 'میانگین نمایی' : 'Exponential mean'),
              _IndicatorTile(title: 'EMA 50', value: _fmt(_indicators['ema50']), note: s.isPersian ? 'روند میان‌مدت' : 'Medium trend'),
              _IndicatorTile(title: 'Bollinger upper', value: _fmt(_indicators['bollinger_upper']), note: s.isPersian ? 'باند بالایی' : 'Upper band'),
              _IndicatorTile(title: 'VWAP (20)', value: _fmt(_indicators['vwap20']), note: s.isPersian ? 'حجم‌وزن اخیر' : 'Recent volume-weighted'),
              _IndicatorTile(title: 'Stoch RSI K / D', value: '${_fmt(_indicators['stoch_rsi_k'])} / ${_fmt(_indicators['stoch_rsi_d'])}', note: s.isPersian ? 'مومنتوم نسبی' : 'Relative momentum'),
              _IndicatorTile(title: 'Supertrend', value: _indicators['supertrend_direction']?.toString() ?? '—', note: _fmt(_indicators['supertrend']),),
              _IndicatorTile(title: 'Ichimoku Kijun', value: _fmt(_indicators['ichimoku_kijun_sen']), note: s.isPersian ? 'خط پایه' : 'Base line'),
              _IndicatorTile(title: 'Donchian upper', value: _fmt(_indicators['donchian_upper20_prev']), note: _indicators['donchian_breakout_up'] == true ? (s.isPersian ? 'شکست رو به بالا' : 'Upside breakout') : (s.isPersian ? 'سقف کانال' : 'Channel high')),
            ],
          ),
          const SizedBox(height: 12),
          Container(padding: const EdgeInsets.all(13), decoration: BoxDecoration(color: const Color(0xFF1B1A16), borderRadius: BorderRadius.circular(15), border: Border.all(color: const Color(0xFF51452A))), child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [const Icon(Icons.info_outline_rounded, color: Color(0xFFFBBF24)), const SizedBox(width: 8), Expanded(child: Text(s.isPersian ? 'کندل زنده از جریان عمومی بازار می‌آید. اندیکاتورها از کندل‌های بسته‌شدهٔ بک‌اند محاسبه می‌شوند و ممکن است تا ۳۰ ثانیه با آخرین کندل باز اختلاف داشته باشند. این داده‌ها توصیهٔ مالی نیستند.' : 'The live candle comes from the public market stream. Indicators use closed candles from the backend and may lag the currently forming candle by up to 30 seconds. This is not financial advice.', style: Theme.of(context).textTheme.bodySmall?.copyWith(color: const Color(0xFFD6C9AA))))])),
        ],
      ),
    );
  }

  String _rsiLabel(dynamic value, bool fa) {
    if (value is! num) return '—';
    if (value >= 70) return fa ? 'اشباع خرید' : 'Overbought zone';
    if (value <= 30) return fa ? 'اشباع فروش' : 'Oversold zone';
    return fa ? 'مومنتوم' : 'Momentum';
  }

  String _signedLabel(dynamic value, bool fa) {
    if (value is! num) return '—';
    if (value > 0) return fa ? 'مثبت' : 'Positive';
    if (value < 0) return fa ? 'منفی' : 'Negative';
    return fa ? 'خنثی' : 'Neutral';
  }

  String _adxLabel(dynamic value, bool fa) {
    if (value is! num) return '—';
    return value >= 25 ? (fa ? 'روند قوی‌تر' : 'Stronger trend') : (fa ? 'روند ضعیف/خنثی' : 'Weak/ranging');
  }
}

class _IndicatorTile extends StatelessWidget {
  const _IndicatorTile({required this.title, required this.value, required this.note});
  final String title;
  final String value;
  final String note;
  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(15), border: Border.all(color: const Color(0xFF263241))),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisAlignment: MainAxisAlignment.center, children: [
          Text(title, maxLines: 1, overflow: TextOverflow.ellipsis, style: Theme.of(context).textTheme.bodySmall),
          const SizedBox(height: 7),
          Text(value, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900)),
          const SizedBox(height: 3),
          Text(note, maxLines: 1, overflow: TextOverflow.ellipsis, style: Theme.of(context).textTheme.bodySmall),
        ]),
      );
}
