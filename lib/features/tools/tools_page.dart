import 'package:dio/dio.dart';
import 'package:flutter/material.dart';

import '../../core/l10n/app_strings.dart';
import '../../core/services/app_storage.dart';
import '../../core/services/market_api.dart';
import '../../core/theme/app_theme.dart';

class ToolsPage extends StatelessWidget {
  const ToolsPage({super.key});

  @override
  Widget build(BuildContext context) {
    final s = AppStrings.of(context);
    return DefaultTabController(
      length: 3,
      child: Scaffold(
        appBar: AppBar(
          title: Text(s.t('tools')),
          bottom: TabBar(tabs: [
            Tab(icon: const Icon(Icons.event_note_rounded), text: s.t('economicCalendar')),
            Tab(icon: const Icon(Icons.science_rounded), text: s.t('backtesting')),
            Tab(icon: const Icon(Icons.notifications_active_outlined), text: s.t('notifications')),
          ]),
        ),
        body: const TabBarView(children: [_CalendarTab(), _BacktestTab(), _NotificationsTab()]),
      ),
    );
  }
}

class _CalendarTab extends StatefulWidget {
  const _CalendarTab();
  @override
  State<_CalendarTab> createState() => _CalendarTabState();
}

class _CalendarTabState extends State<_CalendarTab> {
  List<Map<String, dynamic>> _items = [];
  bool _loading = false;
  String? _error;
  String _importance = 'all';
  String? _source;
  String? _retrieved;

  @override
  void initState() { super.initState(); _load(); }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    final now = DateTime.now().toUtc();
    final from = DateTime.utc(now.year, now.month, now.day);
    try {
      final result = await MarketApi.instance.fetchEconomicCalendar(from: from, to: from.add(const Duration(days: 7)), importance: _importance == 'all' ? null : _importance);
      if (!mounted) return;
      final raw = result['items'];
      setState(() {
        _items = raw is List ? raw.whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList() : [];
        _source = result['source']?.toString();
        _retrieved = result['retrieved_at']?.toString();
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() { _error = _errorMessage(error); _loading = false; });
    }
  }

  String _errorMessage(Object error) {
    if (error is DioException) {
      final data = error.response?.data;
      if (data is Map && data['detail'] != null) return data['detail'].toString();
      if (error.response?.statusCode == 503) return AppStrings.of(context).t('calendarConfigHelp');
    }
    return AppStrings.of(context).isPersian ? 'دریافت تقویم ناموفق بود. اتصال و تنظیمات سرور را بررسی کن.' : 'Could not load calendar. Check server connectivity and configuration.';
  }

  @override
  Widget build(BuildContext context) {
    final s = AppStrings.of(context);
    return RefreshIndicator(onRefresh: _load, child: ListView(padding: const EdgeInsets.all(14), children: [
      Container(padding: const EdgeInsets.all(14), decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(16), border: Border.all(color: const Color(0xFF263241))), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [Expanded(child: Text(s.t('economicCalendar'), style: Theme.of(context).textTheme.titleLarge)), IconButton(onPressed: _loading ? null : _load, icon: const Icon(Icons.refresh_rounded))]),
        Text(AppStrings.of(context).isPersian ? 'هفت روز آینده · زمان‌بندی‌شده توسط منبع بیرونی' : 'Next seven days · scheduled by an external provider', style: Theme.of(context).textTheme.bodySmall?.copyWith(color: AppTheme.muted)),
        const SizedBox(height: 12),
        Row(children: [Text(s.t('importance')), const SizedBox(width: 10), Expanded(child: DropdownButtonFormField<String>(value: _importance, decoration: const InputDecoration(isDense: true, contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 8)), items: [DropdownMenuItem(value: 'all', child: Text(s.t('allImpacts'))), DropdownMenuItem(value: 'low', child: Text(s.t('lowImpact'))), DropdownMenuItem(value: 'medium', child: Text(s.t('mediumImpact'))), DropdownMenuItem(value: 'high', child: Text(s.t('highImpact')))], onChanged: (value) { if (value == null) return; setState(() => _importance = value); _load(); }))]),
        if (_source != null) ...[const SizedBox(height: 8), Text('${s.t('source')}: $_source', style: Theme.of(context).textTheme.bodySmall)],
        if (_retrieved != null) Text('${AppStrings.of(context).isPersian ? 'آخرین دریافت' : 'Fetched'}: $_retrieved', style: Theme.of(context).textTheme.bodySmall),
      ])),
      if (_loading) const Padding(padding: EdgeInsets.all(24), child: Center(child: CircularProgressIndicator())),
      if (_error != null) _statusCard(_error!, warning: true),
      if (!_loading && _error == null && _items.isEmpty) _statusCard(s.t('noCalendar')),
      ..._items.map((event) => _eventCard(event)),
      const SizedBox(height: 12),
      _statusCard(s.t('calendarConfigHelp')),
    ]));
  }

  Widget _eventCard(Map<String, dynamic> event) {
    final level = (event['importance'] ?? 'unknown').toString().toLowerCase();
    final color = level == 'high' ? AppTheme.negative : level == 'medium' ? const Color(0xFFFBBF24) : AppTheme.accent;
    final timeRaw = event['scheduled_at']?.toString();
    String timeLabel = timeRaw ?? '—';
    try {
      if (event['time_zone_status'] == 'provider_timezone_unspecified') {
        timeLabel = timeRaw!;
      } else {
        timeLabel = DateTime.parse(timeRaw!).toLocal().toString().substring(0, 16);
      }
    } catch (_) {}
    final fa = AppStrings.of(context).isPersian;
    return Container(margin: const EdgeInsets.only(top: 8), padding: const EdgeInsets.all(14), decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(15), border: Border.all(color: const Color(0xFF263241))), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(crossAxisAlignment: CrossAxisAlignment.start, children: [Expanded(child: Text(event['event']?.toString() ?? '—', style: const TextStyle(fontWeight: FontWeight.w800))), Container(padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4), decoration: BoxDecoration(color: color.withOpacity(.12), borderRadius: BorderRadius.circular(99)), child: Text(level.toUpperCase(), style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.w900)))]),
      const SizedBox(height: 7),
      Text('$timeLabel · ${event['country'] ?? '—'}${event['currency'] == null ? '' : ' · ${event['currency']}'}', style: Theme.of(context).textTheme.bodySmall?.copyWith(color: AppTheme.muted)),
      const SizedBox(height: 9),
      Wrap(spacing: 14, runSpacing: 6, children: [if (event['previous'] != null) Text('${fa ? 'قبلی' : 'Previous'}: ${event['previous']}'), if (event['forecast'] != null) Text('${fa ? 'پیش‌بینی' : 'Forecast'}: ${event['forecast']}'), if (event['actual'] != null) Text('${fa ? 'واقعی' : 'Actual'}: ${event['actual']}', style: const TextStyle(fontWeight: FontWeight.w800))]),
    ]));
  }
}

class _BacktestTab extends StatefulWidget {
  const _BacktestTab();
  @override
  State<_BacktestTab> createState() => _BacktestTabState();
}

class _BacktestTabState extends State<_BacktestTab> {
  final _symbol = TextEditingController(text: 'BTCUSDT');
  String _interval = '1h';
  bool _running = false;
  Map<String, dynamic>? _result;
  String? _error;
  List<Map<String, dynamic>> _history = [];

  @override
  void initState() { super.initState(); _loadHistory(); }
  @override
  void dispose() { _symbol.dispose(); super.dispose(); }

  Future<void> _loadHistory() async {
    try { final history = await MarketApi.instance.fetchBacktestHistory(); if (mounted) setState(() => _history = history); } catch (_) {}
  }

  Future<void> _run(bool walkForward) async {
    setState(() { _running = true; _error = null; _result = null; });
    try {
      final result = await MarketApi.instance.runBacktest(walkForward: walkForward, symbol: _symbol.text.trim().toUpperCase(), interval: _interval, candlesLimit: walkForward ? 800 : 500);
      if (!mounted) return;
      setState(() => _result = result);
      await _loadHistory();
    } catch (error) {
      if (!mounted) return;
      final detail = error is DioException && error.response?.data is Map ? (error.response!.data as Map)['detail']?.toString() : null;
      setState(() => _error = detail ?? error.toString());
    } finally { if (mounted) setState(() => _running = false); }
  }

  @override
  Widget build(BuildContext context) {
    final s = AppStrings.of(context);
    final result = _result;
    final metrics = result?['aggregate_out_of_sample'] is Map ? Map<String, dynamic>.from(result!['aggregate_out_of_sample'] as Map) : result;
    return ListView(padding: const EdgeInsets.all(14), children: [
      Container(padding: const EdgeInsets.all(15), decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(17), border: Border.all(color: const Color(0xFF263241))), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(s.t('backtesting'), style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 12),
        Row(children: [Expanded(child: TextField(controller: _symbol, textCapitalization: TextCapitalization.characters, decoration: InputDecoration(labelText: s.t('symbol')))), const SizedBox(width: 10), SizedBox(width: 115, child: DropdownButtonFormField<String>(value: _interval, decoration: const InputDecoration(labelText: 'TF'), items: const ['5m', '15m', '1h', '4h', '1d'].map((value) => DropdownMenuItem(value: value, child: Text(value))).toList(), onChanged: (value) { if (value != null) setState(() => _interval = value); }))]),
        const SizedBox(height: 12),
        SizedBox(width: double.infinity, child: FilledButton.icon(onPressed: _running ? null : () => _run(false), icon: const Icon(Icons.play_arrow_rounded), label: Text(_running ? s.t('running') : s.t('runBacktest')))),
        const SizedBox(height: 8),
        SizedBox(width: double.infinity, child: OutlinedButton.icon(onPressed: _running ? null : () => _run(true), icon: const Icon(Icons.view_timeline_rounded), label: Text(s.t('runWalkForward')))),
        const SizedBox(height: 8),
        Text(AppStrings.of(context).isPersian ? 'کارمزد پیش‌فرض: ۱۰ bps · لغزش: ۲ bps · ریسک: ۱٪ · ورود در بازشدن کندل بعدی' : 'Default fee: 10 bps · slippage: 2 bps · risk: 1% · entry at next candle open', style: Theme.of(context).textTheme.bodySmall?.copyWith(color: AppTheme.muted)),
      ])),
      if (_error != null) _statusCard(_error!, warning: true),
      if (result != null) ...[
        const SizedBox(height: 16), Text(s.t('backtestResults'), style: Theme.of(context).textTheme.titleLarge),
        if (result['status'] != 'completed') _statusCard(result['message']?.toString() ?? result['status']?.toString() ?? '—', warning: true)
        else ...[
          const SizedBox(height: 9),
          GridView.count(crossAxisCount: 2, mainAxisSpacing: 8, crossAxisSpacing: 8, shrinkWrap: true, physics: const NeverScrollableScrollPhysics(), childAspectRatio: 1.75, children: [
            _metric(s.t('trades'), '${metrics?['trade_count'] ?? 0}'),
            _metric(s.t('winRate'), _pct(metrics?['win_rate_percent'])),
            _metric(s.t('netPnl'), _numText(metrics?['net_pnl'] ?? metrics?['net_pnl_sum_across_folds'])),
            _metric(s.t('profitFactor'), metrics?['profit_factor']?.toString() ?? '—'),
            _metric(s.t('maxDrawdown'), _pct(metrics?['max_drawdown_percent'])),
            _metric(s.t('expectancy'), _numText(metrics?['expectancy_per_trade'])),
          ]),
          const SizedBox(height: 10),
          _statusCard(AppStrings.of(context).isPersian ? 'راهبرد اعتبارسنجی‌نشده است. نتایج گذشته تضمین‌کنندهٔ عملکرد آینده نیستند. در حالت Walk-Forward هر بازه سرمایهٔ اولیهٔ مستقل دارد.' : 'The strategy remains unvalidated. Historical results do not guarantee future performance. Walk-forward folds each restart from the same initial capital.'),
          if (result['folds'] is List) ...[
            const SizedBox(height: 10), ...((result['folds'] as List).whereType<Map>().map((fold) => ListTile(dense: true, leading: const Icon(Icons.timeline_rounded, color: AppTheme.accent), title: Text('${s.t('folds')} ${fold['fold']}'), subtitle: Text('${s.t('trades')}: ${fold['metrics']?['trade_count'] ?? 0} · ${s.t('winRate')}: ${_pct(fold['metrics']?['win_rate_percent'])}'), trailing: Text(_numText(fold['metrics']?['net_pnl']), style: const TextStyle(fontWeight: FontWeight.w800))))),
          ],
        ],
      ],
      const SizedBox(height: 18),
      Row(children: [Expanded(child: Text(AppStrings.of(context).isPersian ? 'تاریخچهٔ اجراها' : 'Run history', style: Theme.of(context).textTheme.titleLarge)), IconButton(onPressed: _loadHistory, icon: const Icon(Icons.refresh_rounded))]),
      ..._history.take(10).map((run) => ListTile(dense: true, contentPadding: EdgeInsets.zero, leading: const Icon(Icons.history_rounded, color: AppTheme.accent), title: Text('${run['run_type']} · ${run['symbol']} · ${run['interval']}'), subtitle: Text(run['created_at']?.toString() ?? ''), trailing: const Icon(Icons.chevron_right_rounded), onTap: () { final storedResult = run['result']; if (storedResult is Map) setState(() => _result = {'run_id': run['id'], ...Map<String, dynamic>.from(storedResult)}); })),
    ]);
  }

  Widget _metric(String title, String value) => Container(padding: const EdgeInsets.all(12), decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(14), border: Border.all(color: const Color(0xFF263241))), child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisAlignment: MainAxisAlignment.center, children: [Text(title, style: Theme.of(context).textTheme.bodySmall), const SizedBox(height: 5), Text(value, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w900))]));
  String _numText(dynamic value) => value == null ? '—' : value is num ? value.toStringAsFixed(2) : value.toString();
  String _pct(dynamic value) => value == null ? '—' : '${_numText(value)}%';
}

class _NotificationsTab extends StatefulWidget {
  const _NotificationsTab();
  @override
  State<_NotificationsTab> createState() => _NotificationsTabState();
}

class _NotificationsTabState extends State<_NotificationsTab> {
  String? _accountId;
  List<Map<String, dynamic>> _items = [];
  Map<String, dynamic> _preferences = {'enabled': true, 'push_enabled': false, 'enabled_events': ['trade_opened', 'tp_hit', 'stop_hit', 'trade_closed', 'calendar_high']};
  Map<String, dynamic> _status = {};
  bool _loading = false;
  String? _error;

  @override
  void initState() { super.initState(); _load(); }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    try {
      final id = await AppStorage.demoAccountId();
      final status = await MarketApi.instance.fetchNotificationStatus();
      if (id == null || id.isEmpty) {
        if (!mounted) return;
        setState(() { _accountId = null; _status = status; _items = []; _loading = false; });
        return;
      }
      final values = await Future.wait<dynamic>([
        MarketApi.instance.fetchNotifications(id),
        MarketApi.instance.fetchNotificationPreferences(id),
      ]);
      if (!mounted) return;
      setState(() {
        _accountId = id;
        _items = values[0] as List<Map<String, dynamic>>;
        _preferences = Map<String, dynamic>.from(values[1] as Map);
        _status = status;
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() { _error = error is DioException && error.response?.data is Map ? (error.response!.data as Map)['detail']?.toString() : error.toString(); _loading = false; });
    }
  }

  Future<void> _save(Map<String, dynamic> next) async {
    final id = _accountId;
    if (id == null) return;
    setState(() => _preferences = next);
    try {
      final saved = await MarketApi.instance.saveNotificationPreferences(id, next);
      if (mounted) setState(() => _preferences = saved);
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(error.toString())));
      await _load();
    }
  }

  Future<void> _markRead(Map<String, dynamic> item) async {
    final id = _accountId;
    final notificationId = item['id']?.toString();
    if (id == null || notificationId == null || item['read_at'] != null) return;
    try {
      await MarketApi.instance.markNotificationRead(id, notificationId);
      await _load();
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(error.toString())));
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = AppStrings.of(context);
    final fa = s.isPersian;
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_accountId == null) return ListView(padding: const EdgeInsets.all(18), children: [_statusCard(s.t('noRemoteAccount')), _statusCard(s.t('notificationsInfo')), if (_error != null) _statusCard(_error!, warning: true)]);
    final events = (_preferences['enabled_events'] as List? ?? []).map((e) => e.toString()).toSet();
    return RefreshIndicator(onRefresh: _load, child: ListView(padding: const EdgeInsets.all(14), children: [
      Row(children: [Expanded(child: Text(s.t('notifications'), style: Theme.of(context).textTheme.titleLarge)), IconButton(onPressed: _load, icon: const Icon(Icons.refresh_rounded))]),
      if (_error != null) _statusCard(_error!, warning: true),
      SwitchListTile.adaptive(contentPadding: EdgeInsets.zero, value: _preferences['enabled'] == true, title: Text(s.t('notificationsEnabled')), onChanged: (value) => _save({..._preferences, 'enabled': value})),
      SwitchListTile.adaptive(contentPadding: EdgeInsets.zero, value: _preferences['push_enabled'] == true, title: Text(s.t('pushEnabled')), subtitle: Text((_status['push_configured'] == true) ? (fa ? 'بک‌اند آماده است؛ ثبت توکن دستگاه در اپ هنوز پیاده‌سازی نشده، بنابراین Push فعلاً غیرفعال است.' : 'Backend is configured, but in-app device-token registration is not implemented; Push remains unavailable.') : (fa ? 'برای Push واقعی به تنظیم Firebase در بک‌اند و ثبت توکن دستگاه در اپ نیاز است.' : 'Real push requires Firebase backend configuration and in-app device-token registration.'), style: Theme.of(context).textTheme.bodySmall), onChanged: null),
      _statusCard(s.t('notificationsInfo')),
      const SizedBox(height: 16),
      Text(fa ? 'انواع رویدادها' : 'Event types', style: Theme.of(context).textTheme.titleMedium),
      ...[
        ('trade_opened', fa ? 'باز شدن موقعیت دمو' : 'Demo trade opened'),
        ('tp_hit', fa ? 'رسیدن به تارگت' : 'Take-profit reached'),
        ('stop_hit', fa ? 'فعال شدن حد ضرر' : 'Stop-loss reached'),
        ('trade_closed', fa ? 'بسته شدن معامله' : 'Trade closed'),
        ('calendar_high', fa ? 'رویداد اقتصادی مهم' : 'High-impact economic event'),
      ].map((option) => CheckboxListTile(contentPadding: EdgeInsets.zero, value: events.contains(option.$1), title: Text(option.$2), onChanged: (checked) { final nextEvents = {...events}; if (checked == true) { nextEvents.add(option.$1); } else { nextEvents.remove(option.$1); } _save({..._preferences, 'enabled_events': nextEvents.toList()}); })),
      const SizedBox(height: 15),
      Text(fa ? 'آخرین اعلان‌ها' : 'Recent notifications', style: Theme.of(context).textTheme.titleLarge),
      if (_items.isEmpty) _statusCard(fa ? 'هنوز اعلانی ثبت نشده است.' : 'No notifications recorded yet.'),
      ..._items.map((item) => InkWell(onTap: item['read_at'] == null ? () => _markRead(item) : null, borderRadius: BorderRadius.circular(14), child: Container(margin: const EdgeInsets.only(top: 7), padding: const EdgeInsets.all(13), decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(14), border: Border.all(color: const Color(0xFF263241))), child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [Icon(item['read_at'] == null ? Icons.notifications_active_outlined : Icons.notifications_none_rounded, color: AppTheme.accent), const SizedBox(width: 10), Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(item['title']?.toString() ?? '', style: const TextStyle(fontWeight: FontWeight.w800)), const SizedBox(height: 4), Text(item['body']?.toString() ?? ''), const SizedBox(height: 4), Text(item['created_at']?.toString() ?? '', style: Theme.of(context).textTheme.bodySmall?.copyWith(color: AppTheme.muted)), if (item['read_at'] == null) Padding(padding: const EdgeInsets.only(top: 4), child: Text(fa ? 'برای علامت‌گذاری به‌عنوان خوانده‌شده لمس کن' : 'Tap to mark as read', style: const TextStyle(fontSize: 11, color: AppTheme.accent))) ]))])))),
    ]));
  }
}

Widget _statusCard(String text, {bool warning = false}) => Container(margin: const EdgeInsets.only(top: 10), padding: const EdgeInsets.all(13), decoration: BoxDecoration(color: warning ? const Color(0x22FBBF24) : AppTheme.surface, borderRadius: BorderRadius.circular(14), border: Border.all(color: warning ? const Color(0x667E6424) : const Color(0xFF263241))), child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [Icon(warning ? Icons.info_outline_rounded : Icons.shield_outlined, size: 19, color: warning ? const Color(0xFFFBBF24) : AppTheme.accent), const SizedBox(width: 9), Expanded(child: Text(text, style: const TextStyle(fontSize: 12)))]));
