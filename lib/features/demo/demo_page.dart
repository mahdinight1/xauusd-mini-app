import 'package:dio/dio.dart';
import 'package:flutter/material.dart';

import '../../core/l10n/app_strings.dart';
import '../../core/services/app_storage.dart';
import '../../core/services/market_api.dart';
import '../../core/theme/app_theme.dart';

class DemoPage extends StatefulWidget {
  const DemoPage({super.key});
  @override
  State<DemoPage> createState() => _DemoPageState();
}

class _DemoPageState extends State<DemoPage> {
  String? _accountId;
  Map<String, dynamic>? _account;
  List<Map<String, dynamic>> _openPositions = [];
  List<Map<String, dynamic>> _closedPositions = [];
  List<Map<String, dynamic>> _events = [];
  bool _loading = true;
  bool _busy = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    try {
      final id = await AppStorage.demoAccountId();
      if (id == null || id.isEmpty) {
        if (!mounted) return;
        setState(() { _accountId = null; _account = null; _openPositions = []; _closedPositions = []; _events = []; _loading = false; });
        return;
      }
      final values = await Future.wait<dynamic>([
        MarketApi.instance.fetchDemoAccount(id),
        MarketApi.instance.fetchDemoPositions(id, status: 'OPEN'),
        MarketApi.instance.fetchDemoPositions(id, status: 'CLOSED', limit: 50),
        MarketApi.instance.fetchDemoEvents(id, limit: 100),
      ]);
      if (!mounted) return;
      setState(() {
        _accountId = id;
        _account = Map<String, dynamic>.from(values[0] as Map);
        _openPositions = values[1] as List<Map<String, dynamic>>;
        _closedPositions = values[2] as List<Map<String, dynamic>>;
        _events = values[3] as List<Map<String, dynamic>>;
        _loading = false;
      });
      final capital = (_account?['initial_capital'] as num?)?.toDouble();
      if (capital != null) await AppStorage.saveDemoCapital(capital);
    } catch (error) {
      if (!mounted) return;
      setState(() { _loading = false; _error = _friendlyError(error); });
    }
  }

  String _friendlyError(Object error) {
    if (error is DioException) {
      final detail = error.response?.data is Map ? (error.response!.data as Map)['detail']?.toString() : null;
      return detail ?? (Localizations.localeOf(context).languageCode == 'fa' ? 'اتصال به بک‌اند ممکن نشد. آدرس سرور را در تنظیمات بررسی کن.' : 'Could not reach the backend. Check the server URL in Settings.');
    }
    return error.toString();
  }

  @override
  Widget build(BuildContext context) {
    final s = AppStrings.of(context);
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_account == null) {
      return ListView(padding: const EdgeInsets.all(18), children: [
        Text(s.t('demoAccount'), style: Theme.of(context).textTheme.headlineMedium),
        const SizedBox(height: 8),
        Text(s.t('virtualOnly'), style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: AppTheme.muted)),
        if (_error != null) _errorCard(_error!),
        const SizedBox(height: 24),
        _createCard(context),
      ]);
    }
    final account = _account!;
    final fa = s.isPersian;
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(padding: const EdgeInsets.fromLTRB(16, 10, 16, 26), children: [
        Row(children: [Expanded(child: Text(s.t('demoAccount'), style: Theme.of(context).textTheme.headlineMedium)), IconButton(onPressed: _busy ? null : _load, icon: const Icon(Icons.refresh_rounded))]),
        const SizedBox(height: 4),
        Text(fa ? 'حساب مجازی ذخیره‌شده روی بک‌اند' : 'Persistent virtual ledger stored by the backend', style: Theme.of(context).textTheme.bodySmall?.copyWith(color: AppTheme.muted)),
        if (_error != null) _errorCard(_error!),
        const SizedBox(height: 15),
        Container(padding: const EdgeInsets.all(20), decoration: BoxDecoration(gradient: const LinearGradient(colors: [Color(0xFF14384A), Color(0xFF121923)]), borderRadius: BorderRadius.circular(23), border: Border.all(color: const Color(0xFF2C5265))), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [const Icon(Icons.account_balance_wallet_outlined, color: AppTheme.accent), const SizedBox(width: 8), Expanded(child: Text(s.t('virtualPortfolio'), style: const TextStyle(fontWeight: FontWeight.w700))), _badge('DEMO')]),
          const SizedBox(height: 18),
          Text(s.t('currentBalance'), style: Theme.of(context).textTheme.bodySmall),
          const SizedBox(height: 4),
          Text(_money(account['equity']), style: const TextStyle(fontSize: 31, fontWeight: FontWeight.w900, letterSpacing: -.5)),
          const SizedBox(height: 7),
          Text('${s.t('initialCapital')}: ${_money(account['initial_capital'])}', style: Theme.of(context).textTheme.bodySmall),
          const SizedBox(height: 3),
          Text('${fa ? 'بازده خالص' : 'Net return'}: ${_percent(account['net_return_percent'])}', style: TextStyle(color: _num(account['net_return_percent']) >= 0 ? AppTheme.positive : AppTheme.negative, fontWeight: FontWeight.w800)),
        ])),
        const SizedBox(height: 12),
        Row(children: [Expanded(child: _metric(context, s.t('realizedPnl'), _money(account['realized_pnl']), _num(account['realized_pnl']) >= 0 ? AppTheme.positive : AppTheme.negative)), const SizedBox(width: 9), Expanded(child: _metric(context, s.t('unrealizedPnl'), _money(account['unrealized_pnl']), _num(account['unrealized_pnl']) >= 0 ? AppTheme.positive : AppTheme.negative))]),
        const SizedBox(height: 9),
        Row(children: [Expanded(child: _metric(context, s.t('openPositions'), '${account['open_count'] ?? 0}', AppTheme.accent)), const SizedBox(width: 9), Expanded(child: _metric(context, s.t('closedTrades'), '${account['closed_count'] ?? 0}', AppTheme.accent))]),
        const SizedBox(height: 16),
        Container(padding: const EdgeInsets.symmetric(horizontal: 15, vertical: 10), decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(17), border: Border.all(color: const Color(0xFF263241))), child: SwitchListTile.adaptive(contentPadding: EdgeInsets.zero, value: account['auto_enabled'] == true, onChanged: _busy ? null : _setAuto, title: Text(fa ? 'معاملهٔ خودکار دمو' : 'Automatic demo trading', style: const TextStyle(fontWeight: FontWeight.w800)), subtitle: Text(fa ? 'فقط معاملات مجازی؛ بدون سفارش واقعی' : 'Virtual trades only; no real exchange orders', style: Theme.of(context).textTheme.bodySmall), secondary: const Icon(Icons.autorenew_rounded, color: AppTheme.accent))),
        const SizedBox(height: 10),
        SizedBox(width: double.infinity, child: FilledButton.icon(onPressed: _busy ? null : _scanNow, icon: _busy ? const SizedBox(width: 17, height: 17, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.radar_rounded), label: Text(fa ? 'بررسی بازار و اجرای دمو' : 'Scan market and simulate'))),
        const SizedBox(height: 22),
        _sectionTitle(fa ? 'موقعیت‌های باز' : 'Open positions'),
        if (_openPositions.isEmpty) _emptyCard(fa ? 'موقعیت بازی وجود ندارد' : 'No open positions') else ..._openPositions.map((position) => _positionCard(position, fa)),
        const SizedBox(height: 22),
        _sectionTitle(fa ? 'تاریخچهٔ معاملات بسته‌شده' : 'Closed-trade history'),
        if (_closedPositions.isEmpty) _emptyCard(fa ? 'هنوز معامله‌ای بسته نشده است' : 'No closed trades yet') else ..._closedPositions.take(15).map((position) => _positionCard(position, fa)),
        const SizedBox(height: 22),
        _sectionTitle(fa ? 'رویدادهای دفترکل' : 'Ledger events'),
        if (_events.isEmpty) _emptyCard(fa ? 'رویدادی ثبت نشده است' : 'No ledger events yet') else ..._events.take(20).map((event) => _eventTile(event, fa)),
        const SizedBox(height: 18),
        OutlinedButton.icon(onPressed: _busy ? null : _resetDialog, icon: const Icon(Icons.restart_alt_rounded), label: Text(s.t('resetDemo')), style: OutlinedButton.styleFrom(foregroundColor: AppTheme.negative, side: const BorderSide(color: Color(0x66F87171)), padding: const EdgeInsets.symmetric(vertical: 14))),
        const SizedBox(height: 12),
        Text(s.t('demoNote'), textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodySmall),
      ]),
    );
  }

  Widget _createCard(BuildContext context) {
    final s = AppStrings.of(context);
    return Container(padding: const EdgeInsets.all(22), decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(22), border: Border.all(color: const Color(0xFF263241))), child: Column(children: [Container(width: 65, height: 65, decoration: BoxDecoration(color: AppTheme.accent.withOpacity(.1), borderRadius: BorderRadius.circular(20)), child: const Icon(Icons.account_balance_wallet_outlined, color: AppTheme.accent, size: 32)), const SizedBox(height: 15), Text(s.t('notCreated'), style: Theme.of(context).textTheme.titleLarge), const SizedBox(height: 8), Text(s.t('demoNote'), textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodySmall), const SizedBox(height: 18), FilledButton.icon(onPressed: _busy ? null : _createDialog, icon: const Icon(Icons.add_rounded), label: Text(s.t('createDemo')), style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(48)))]));
  }

  Widget _metric(BuildContext context, String label, String value, Color color) => Container(padding: const EdgeInsets.all(14), decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(17), border: Border.all(color: const Color(0xFF263241))), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(label, style: Theme.of(context).textTheme.bodySmall), const SizedBox(height: 7), Text(value, style: TextStyle(fontSize: 19, fontWeight: FontWeight.w800, color: color))]));

  Widget _badge(String label) => Container(padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4), decoration: BoxDecoration(color: const Color(0x2238BDF8), borderRadius: BorderRadius.circular(99)), child: Text(label, style: const TextStyle(color: AppTheme.accent, fontWeight: FontWeight.w900, fontSize: 10)));

  Widget _sectionTitle(String title) => Padding(padding: const EdgeInsets.only(bottom: 9), child: Text(title, style: Theme.of(context).textTheme.titleLarge));
  Widget _emptyCard(String text) => Container(padding: const EdgeInsets.all(17), decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(15), border: Border.all(color: const Color(0xFF263241))), child: Row(children: [const Icon(Icons.hourglass_empty_rounded, color: AppTheme.muted), const SizedBox(width: 10), Expanded(child: Text(text, style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: AppTheme.muted)))]));
  Widget _errorCard(String text) => Container(margin: const EdgeInsets.only(top: 12), padding: const EdgeInsets.all(12), decoration: BoxDecoration(color: const Color(0x22F87171), borderRadius: BorderRadius.circular(13), border: Border.all(color: const Color(0x6671F871))), child: Text(text, style: Theme.of(context).textTheme.bodySmall));

  Widget _positionCard(Map<String, dynamic> position, bool fa) {
    final isLong = position['direction'] == 'LONG';
    final isOpen = position['status'] == 'OPEN';
    final pnl = _num(position['realized_pnl']) - _num(position['fees']);
    final color = isLong ? AppTheme.positive : AppTheme.negative;
    return Container(margin: const EdgeInsets.only(bottom: 9), padding: const EdgeInsets.all(14), decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(16), border: Border.all(color: const Color(0xFF263241))), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [Text('${position['symbol'] ?? '—'}', style: const TextStyle(fontWeight: FontWeight.w900)), const SizedBox(width: 8), _badge(position['direction']?.toString() ?? '—'), const Spacer(), Text(position['status']?.toString() ?? '', style: TextStyle(color: isOpen ? AppTheme.accent : AppTheme.muted, fontWeight: FontWeight.w700, fontSize: 11))]),
      const SizedBox(height: 10),
      Wrap(spacing: 12, runSpacing: 7, children: [Text('${fa ? 'ورود' : 'Entry'}: ${_price(position['entry'])}'), Text('SL: ${_price(position['stop_loss'])}', style: const TextStyle(color: AppTheme.negative)), Text('TP1: ${_price(position['tp1'])}', style: const TextStyle(color: AppTheme.positive)), Text('TP2: ${_price(position['tp2'])}', style: const TextStyle(color: AppTheme.positive)), Text('TP3: ${_price(position['tp3'])}', style: const TextStyle(color: AppTheme.positive))]),
      if (isOpen) ...[const SizedBox(height: 8), Text('${fa ? 'قیمت فعلی' : 'Current'}: ${_price(position['current_price'])} · ${fa ? 'مانده' : 'Remaining'}: ${_num(position['remaining_qty']).toStringAsFixed(6)}')]
      else ...[const SizedBox(height: 7), Text('${fa ? 'سود/زیان خالص' : 'Net P&L'}: ${_money(pnl)}', style: TextStyle(fontWeight: FontWeight.w800, color: pnl >= 0 ? AppTheme.positive : AppTheme.negative))],
      const SizedBox(height: 6), Text('${fa ? 'کارمزد ثبت‌شده' : 'Fees'}: ${_money(position['fees'])}', style: Theme.of(context).textTheme.bodySmall),
    ]));
  }

  Widget _eventTile(Map<String, dynamic> event, bool fa) => Container(margin: const EdgeInsets.only(bottom: 6), decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(12), border: Border.all(color: const Color(0xFF263241))), child: ListTile(dense: true, leading: Icon(_eventIcon(event['event_type']?.toString() ?? ''), color: AppTheme.accent, size: 20), title: Text('${event['event_type'] ?? ''} · ${event['symbol'] ?? ''}', style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 12)), subtitle: Text('${_price(event['price'])} · ${event['created_at'] ?? ''}', maxLines: 2, overflow: TextOverflow.ellipsis), trailing: Text(_money(event['pnl']), style: TextStyle(fontSize: 11, color: _num(event['pnl']) >= 0 ? AppTheme.positive : AppTheme.negative))));
  IconData _eventIcon(String type) => type == 'trade_opened' ? Icons.login_rounded : type == 'tp_hit' ? Icons.flag_rounded : type == 'stop_hit' ? Icons.stop_circle_outlined : Icons.receipt_long_rounded;

  double _num(dynamic value) => value is num ? value.toDouble() : double.tryParse(value?.toString() ?? '') ?? 0;
  String _money(dynamic value) => _num(value).toStringAsFixed(2);
  String _price(dynamic value) => value == null ? '—' : _num(value).toStringAsPrecision(8).replaceFirst(RegExp(r'\.?0+$'), '');
  String _percent(dynamic value) => value == null ? '—' : '${_num(value).toStringAsFixed(2)}%';

  Future<void> _createDialog() async {
    final s = AppStrings.of(context);
    final controller = TextEditingController(text: '10000');
    final value = await showDialog<double>(context: context, builder: (ctx) => AlertDialog(title: Text(s.t('createDemo')), content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [Text(s.t('initialCapital')), const SizedBox(height: 8), TextField(controller: controller, keyboardType: const TextInputType.numberWithOptions(decimal: true), decoration: InputDecoration(labelText: s.t('amount')))]), actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: Text(s.t('cancel'))), FilledButton(onPressed: () { final amount = double.tryParse(controller.text.trim().replaceAll(',', '.')); if (amount != null && amount > 0 && amount <= 1000000000000) Navigator.pop(ctx, amount); }, child: Text(s.t('create')))]));
    controller.dispose();
    if (value == null) return;
    setState(() { _busy = true; _error = null; });
    try {
      final account = await MarketApi.instance.createDemoAccount(initialCapital: value);
      final id = account['id']?.toString();
      if (id == null || id.isEmpty) throw const FormatException('Missing demo account ID');
      await AppStorage.saveDemoAccountId(id);
      await AppStorage.saveDemoCapital(value);
      if (!mounted) return;
      setState(() { _accountId = id; _account = account; });
      await _load();
    } catch (error) {
      if (mounted) setState(() => _error = _friendlyError(error));
    } finally { if (mounted) setState(() => _busy = false); }
  }

  Future<void> _setAuto(bool enabled) async {
    final id = _accountId;
    if (id == null) return;
    setState(() { _busy = true; _error = null; });
    try { await MarketApi.instance.setDemoAuto(id, enabled); await _load(); }
    catch (error) { if (mounted) setState(() => _error = _friendlyError(error)); }
    finally { if (mounted) setState(() => _busy = false); }
  }

  Future<void> _scanNow() async {
    final id = _accountId;
    if (id == null) return;
    setState(() { _busy = true; _error = null; });
    try {
      final result = await MarketApi.instance.scanDemoAccount(id);
      final results = result['results'];
      final fa = AppStrings.of(context).isPersian;
      final opened = results is List ? results.whereType<Map>().where((item) => item['status'] == 'position_opened').length : 0;
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(fa ? 'بررسی انجام شد؛ موقعیت جدید: $opened' : 'Scan complete; new positions: $opened')));
      await _load();
    } catch (error) { if (mounted) setState(() => _error = _friendlyError(error)); }
    finally { if (mounted) setState(() => _busy = false); }
  }

  Future<void> _resetDialog() async {
    final s = AppStrings.of(context);
    final yes = await showDialog<bool>(context: context, builder: (ctx) => AlertDialog(title: Text(s.t('resetDemo')), content: Text(s.t('resetConfirm')), actions: [TextButton(onPressed: () => Navigator.pop(ctx, false), child: Text(s.t('cancel'))), FilledButton(onPressed: () => Navigator.pop(ctx, true), child: Text(s.t('confirm')))]));
    if (yes != true || _accountId == null) return;
    setState(() { _busy = true; _error = null; });
    try { await MarketApi.instance.resetDemoAccount(_accountId!); await _load(); }
    catch (error) { if (mounted) setState(() => _error = _friendlyError(error)); }
    finally { if (mounted) setState(() => _busy = false); }
  }
}
