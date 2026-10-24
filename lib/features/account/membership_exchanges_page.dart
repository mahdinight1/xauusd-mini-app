import 'package:dio/dio.dart';
import 'package:flutter/material.dart';

import '../../core/services/app_storage.dart';
import '../../core/services/market_api.dart';
import '../../core/theme/app_theme.dart';
import 'auth_page.dart';

class MembershipExchangesPage extends StatefulWidget {
  const MembershipExchangesPage({super.key});

  @override
  State<MembershipExchangesPage> createState() => _MembershipExchangesPageState();
}

class _MembershipExchangesPageState extends State<MembershipExchangesPage> with SingleTickerProviderStateMixin {
  final _apiKey = TextEditingController();
  final _apiSecret = TextEditingController();
  late final TabController _tabs;

  bool _checkingAuth = true;
  bool _signedIn = false;
  bool _loading = false;
  bool _connecting = false;
  bool _obscureKey = true;
  bool _obscureSecret = true;
  String? _message;
  bool _messageError = false;
  Map<String, dynamic>? _entitlement;
  Map<String, dynamic>? _plans;
  List<Map<String, dynamic>> _connections = [];

  bool get _fa => Localizations.localeOf(context).languageCode == 'fa';
  bool get _demoBillingEnabled => (_plans?['billing_mode'] as String? ?? 'demo') == 'demo';
  String t(String fa, String en) => _fa ? fa : en;

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 2, vsync: this);
    _load();
  }

  @override
  void dispose() {
    _tabs.dispose();
    _apiKey.dispose();
    _apiSecret.dispose();
    super.dispose();
  }

  void _showMessage(String message, {bool error = false}) {
    if (mounted) setState(() { _message = message; _messageError = error; });
  }

  String _errorMessage(Object error) {
    if (error is DioException) {
      final data = error.response?.data;
      if (data is Map && data['detail'] is String) return data['detail'] as String;
      if (error.response?.statusCode == 401) return t('ابتدا وارد حساب شو.', 'Sign in is required.');
      if (error.response?.statusCode == 503) return t('سرویس هنوز پیکربندی نشده است؛ جزئیات در راهنمای بک‌اند است.', 'The service is not configured yet; see the backend setup guide.');
    }
    return t('عملیات انجام نشد. اتصال و تنظیمات سرور را بررسی کن.', 'Operation failed. Check the network and server configuration.');
  }

  Future<void> _load() async {
    if (mounted) setState(() { _loading = true; _checkingAuth = true; _message = null; });
    final token = await AppStorage.authToken();
    if (token == null || token.isEmpty) {
      if (mounted) setState(() { _signedIn = false; _checkingAuth = false; _loading = false; });
      return;
    }
    try {
      final values = await Future.wait([
        MarketApi.instance.fetchSubscriptionPlans(),
        MarketApi.instance.fetchSubscriptionEntitlement(),
        MarketApi.instance.fetchExchangeConnections(),
      ]);
      if (!mounted) return;
      _plans = values[0];
      _entitlement = values[1];
      final connections = values[2]['items'];
      _connections = connections is List ? connections.whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList() : [];
      setState(() { _signedIn = true; _checkingAuth = false; _loading = false; });
    } catch (error) {
      if (!mounted) return;
      if (error is DioException && error.response?.statusCode == 401) {
        await AppStorage.saveAuthToken(null);
        setState(() { _signedIn = false; _checkingAuth = false; _loading = false; });
      } else {
        setState(() { _signedIn = true; _checkingAuth = false; _loading = false; _message = _errorMessage(error); _messageError = true; });
      }
    }
  }

  Future<void> _openAuth() async {
    final result = await Navigator.of(context).push<bool>(MaterialPageRoute<bool>(builder: (_) => const AuthPage()));
    if (result == true) await _load();
  }

  Future<void> _activateDemoSubscription(String tier) async {
    if (!_signedIn) { await _openAuth(); return; }
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(t('پرداخت آزمایشی', 'Demo checkout')),
        content: Text(t(
          'این فقط شبیه‌سازی پرداخت برای طرح ${tier.toUpperCase()} است. هیچ پولی دریافت نمی‌شود و در صورت تأیید، دسترسی آزمایشی ۳۰ روزه فعال می‌شود.',
          'This simulates checkout for the ${tier.toUpperCase()} plan. No money will be charged; confirming grants 30 days of test access.',
        )),
        actions: [
          TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: Text(t('انصراف', 'Cancel'))),
          FilledButton(onPressed: () => Navigator.pop(dialogContext, true), child: Text(t('شبیه‌سازی پرداخت', 'Simulate payment'))),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    setState(() { _loading = true; _message = null; });
    try {
      final result = await MarketApi.instance.activateDemoSubscription(tier: tier);
      final entitlement = result['entitlement'];
      if (mounted) {
        setState(() {
          if (entitlement is Map) _entitlement = Map<String, dynamic>.from(entitlement);
          _loading = false;
        });
        _showMessage(result['already_active'] == true
            ? t('این اشتراک دمو از قبل فعال است؛ مدت آن تمدید نشد.', 'This demo subscription is already active; its duration was not extended.')
            : t('اشتراک دمو برای ۳۰ روز فعال شد. هیچ مبلغی دریافت نشد.', 'Demo subscription activated for 30 days. No money was charged.'));
      }
    } catch (error) {
      if (mounted) {
        setState(() => _loading = false);
        _showMessage(_errorMessage(error), error: true);
      }
    }
  }

  Future<void> _connectExchange() async {
    if (!_signedIn) { await _openAuth(); return; }
    if (_apiKey.text.trim().isEmpty || _apiSecret.text.trim().isEmpty) {
      _showMessage(t('API Key و Secret را وارد کن.', 'Enter both API Key and Secret.'), error: true);
      return;
    }
    setState(() { _connecting = true; _message = null; });
    try {
      final result = await MarketApi.instance.connectBinance(apiKey: _apiKey.text.trim(), apiSecret: _apiSecret.text.trim());
      _apiKey.clear();
      _apiSecret.clear();
      final connection = result['connection'];
      if (mounted) {
        setState(() {
          if (connection is Map) {
            _connections.removeWhere((item) => item['exchange'] == 'binance');
            _connections.add(Map<String, dynamic>.from(connection));
          }
        });
        _showMessage(t('اتصال فقط‌خواندنی تأیید و روی سرور رمزگذاری شد.', 'Read-only connection verified and encrypted on the server.'));
      }
    } catch (error) {
      _showMessage(_errorMessage(error), error: true);
    } finally {
      if (mounted) setState(() => _connecting = false);
    }
  }

  Future<void> _testExchange() async {
    setState(() => _connecting = true);
    try {
      await MarketApi.instance.testBinanceConnection();
      await _load();
      _showMessage(t('اتصال صرافی دوباره بررسی شد.', 'Exchange connection was re-checked.'));
    } catch (error) {
      _showMessage(_errorMessage(error), error: true);
    } finally { if (mounted) setState(() => _connecting = false); }
  }

  Future<void> _disconnectExchange() async {
    final confirm = await showDialog<bool>(context: context, builder: (ctx) => AlertDialog(
      title: Text(t('قطع اتصال صرافی؟', 'Disconnect exchange?')),
      content: Text(t('اعتبارنامهٔ رمزگذاری‌شده از سرور حذف می‌شود. اگر کلید افشا شده، آن را در پنل صرافی نیز لغو کن.', 'The encrypted credentials will be removed from this server. If the key may be exposed, also revoke it in the exchange portal.')),
      actions: [TextButton(onPressed: () => Navigator.pop(ctx, false), child: Text(t('لغو', 'Cancel'))), FilledButton(onPressed: () => Navigator.pop(ctx, true), child: Text(t('قطع اتصال', 'Disconnect')))],
    ));
    if (confirm != true) return;
    try {
      await MarketApi.instance.disconnectBinance();
      if (mounted) setState(() => _connections.removeWhere((item) => item['exchange'] == 'binance'));
      _showMessage(t('اتصال حذف شد.', 'Connection removed.'));
    } catch (error) { _showMessage(_errorMessage(error), error: true); }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(t('حساب، اشتراک و صرافی', 'Account, subscription & exchange')),
        bottom: TabBar(controller: _tabs, tabs: [Tab(icon: const Icon(Icons.workspace_premium_rounded), text: t('اشتراک ویژه', 'Membership')), Tab(icon: const Icon(Icons.account_balance_rounded), text: t('اتصال صرافی', 'Exchange'))]),
        actions: [IconButton(onPressed: _load, tooltip: t('تازه‌سازی', 'Refresh'), icon: const Icon(Icons.refresh_rounded))],
      ),
      body: _checkingAuth || _loading
          ? const Center(child: CircularProgressIndicator())
          : !_signedIn
              ? _signedOutView()
              : TabBarView(controller: _tabs, children: [_membershipTab(), _exchangeTab()]),
    );
  }

  Widget _signedOutView() => Center(child: Padding(padding: const EdgeInsets.all(24), child: Column(mainAxisSize: MainAxisSize.min, children: [
    const Icon(Icons.lock_outline_rounded, size: 58, color: AppTheme.accent),
    const SizedBox(height: 16),
    Text(t('ورود لازم است', 'Sign in required'), style: Theme.of(context).textTheme.headlineSmall),
    const SizedBox(height: 8),
    Text(t('برای گواهی‌ها، اشتراک‌ها و ذخیرهٔ امن اتصال صرافی، حساب NEXTRADE بساز یا وارد شو.', 'Create or sign in to a NEXTRADE account to manage subscriptions and securely store exchange connections.'), textAlign: TextAlign.center),
    const SizedBox(height: 18), FilledButton.icon(onPressed: _openAuth, icon: const Icon(Icons.login_rounded), label: Text(t('ورود / ثبت‌نام', 'Sign in / Register'))),
  ])));

  Widget _membershipTab() {
    final tier = (_entitlement?['tier'] as String?) ?? 'free';
    final planItems = (_plans?['plans'] as List?)?.whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList() ?? [];
    return ListView(padding: const EdgeInsets.all(16), children: [
      _messageCard(),
      Container(padding: const EdgeInsets.all(18), decoration: BoxDecoration(gradient: const LinearGradient(colors: [Color(0xFF183345), Color(0xFF121923)]), borderRadius: BorderRadius.circular(20), border: Border.all(color: const Color(0xFF31556A))), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [const Icon(Icons.workspace_premium_rounded, color: AppTheme.accent, size: 30), const SizedBox(width: 10), Expanded(child: Text(t('سطح دسترسی فعلی', 'Current entitlement'), style: Theme.of(context).textTheme.titleLarge)), Container(padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5), decoration: BoxDecoration(color: const Color(0x2238BDF8), borderRadius: BorderRadius.circular(999)), child: Text(tier.toUpperCase(), style: const TextStyle(fontWeight: FontWeight.w900, color: AppTheme.accent)))]),
        const SizedBox(height: 8),
        Text((_entitlement?['active'] == true) ? '${t('معتبر تا', 'Valid until')}: ${_entitlement?['expires_at'] ?? '—'}' : t('حساب فعلی روی سطح رایگان است. فقط entitlement تأییدشدهٔ سرور دسترسی ویژه را فعال می‌کند.', 'Your account is on the free tier. Only a server-verified entitlement enables paid features.'), style: Theme.of(context).textTheme.bodySmall),
      ])),
     SizedBox(
  width: double.infinity,
  child: FilledButton.icon(
    onPressed: _connecting ? null : _connectExchange,
    icon: _connecting
        ? const SizedBox(
            width: 16,
            height: 16,
            child: CircularProgressIndicator(strokeWidth: 2),
          )
        : const Icon(Icons.link_rounded),
    label: Text(
      t('اعتبارسنجی و اتصال امن', 'Validate and connect securely'),
    ),
  ),
),
      const SizedBox(height: 10),
      Container(padding: const EdgeInsets.all(12), decoration: BoxDecoration(color: const Color(0x2238BDF8), borderRadius: BorderRadius.circular(12)), child: Text(_demoBillingEnabled
          ? t('پرداخت در حالت DEMO است؛ Google Play و درگاه پرداخت غیرفعال‌اند. دسترسی آزمایشی فقط از سرور اعطا می‌شود و پس از ۳۰ روز منقضی می‌شود.', 'Billing is in DEMO mode; Google Play and payment processing are disabled. Demo access is granted by the server and expires after 30 days.')
          : t('حالت سرور روی پرداخت واقعی تنظیم شده، اما پرداخت واقعی در این نسخهٔ Flutter فعال نشده است.', 'The server is set to real billing, but real billing is not implemented in this Flutter build.'), style: Theme.of(context).textTheme.bodySmall)),
    ]);
  }

  Widget _exchangeTab() {
    final connection = _connections.where((item) => item['exchange'] == 'binance').firstOrNull;
    final connected = connection != null && connection['status'] == 'connected';
    return ListView(padding: const EdgeInsets.all(16), children: [
      _messageCard(),
      Container(padding: const EdgeInsets.all(16), decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(18), border: Border.all(color: const Color(0xFF263241))), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [const Icon(Icons.verified_user_rounded, color: AppTheme.positive, size: 28), const SizedBox(width: 10), Expanded(child: Text(t('اتصال فقط‌خواندنی Binance Spot', 'Binance Spot read-only connection'), style: Theme.of(context).textTheme.titleLarge))]),
        const SizedBox(height: 9),
        Text(t('کلیدی بساز که فقط Reading داشته باشد. مجوز معامله و برداشت را خاموش نگه دار. بک‌اند سطح دسترسی را بررسی می‌کند و کلیدها را با رمزگذاری سمت سرور نگه می‌دارد.', 'Create an API key with read/account access only. Disable trading and withdrawals. The backend checks permissions and encrypts credentials at rest.'), style: Theme.of(context).textTheme.bodySmall),
        const SizedBox(height: 14),
        TextField(controller: _apiKey, autocorrect: false, enableSuggestions: false, decoration: InputDecoration(labelText: t('API Key', 'API Key'), prefixIcon: const Icon(Icons.key_rounded), suffixIcon: IconButton(onPressed: () => setState(() => _obscureKey = !_obscureKey), icon: Icon(_obscureKey ? Icons.visibility : Icons.visibility_off)),), obscureText: _obscureKey),
        const SizedBox(height: 10),
        TextField(controller: _apiSecret, autocorrect: false, enableSuggestions: false, decoration: InputDecoration(labelText: t('API Secret', 'API Secret'), prefixIcon: const Icon(Icons.password_rounded), suffixIcon: IconButton(onPressed: () => setState(() => _obscureSecret = !_obscureSecret), icon: Icon(_obscureSecret ? Icons.visibility : Icons.visibility_off))), obscureText: _obscureSecret),
        const SizedBox(height: 14),
        SizedBox(width: double.infinity, child: FilledButton.icon(onPressed: _connecting ? null : _connectExchange, icon: _connecting ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.link_rounded), label: Text(t('اعتبارسنجی و اتصال امن', 'Validate and connect securely'))),
        const SizedBox(height: 7),
        Text(t('کلید فقط هنگام ارسال درخواست در حافظهٔ صفحه است؛ پس از موفقیت فیلدها پاک می‌شوند. برای محیط تولید از HTTPS استفاده کن.', 'Credentials are cleared from the form after submission. Production deployments must use HTTPS.'), style: Theme.of(context).textTheme.bodySmall),
      ])),
      const SizedBox(height: 16),
      Text(t('اتصال ذخیره‌شده', 'Stored connection'), style: Theme.of(context).textTheme.titleLarge),
      const SizedBox(height: 8),
      if (connection == null) Text(t('هنوز صرافی متصل نشده است.', 'No exchange is connected yet.')) else Container(padding: const EdgeInsets.all(15), decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(16), border: Border.all(color: const Color(0xFF263241))), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [const Icon(Icons.account_balance_rounded, size: 26, color: AppTheme.accent), const SizedBox(width: 9), Expanded(child: Text('Binance · ${connection['key_fingerprint'] ?? '—'}', style: const TextStyle(fontWeight: FontWeight.w800))), Icon(connected ? Icons.check_circle_rounded : Icons.error_outline_rounded, color: connected ? AppTheme.positive : AppTheme.negative)]),
        const SizedBox(height: 8),
        Text(t('مجوز: فقط‌خواندنی، بدون معامله و برداشت', 'Permission: read-only, no trade or withdrawal')), 
        Text('${t('آخرین بررسی', 'Last checked')}: ${connection['last_checked_at'] ?? '—'}', style: Theme.of(context).textTheme.bodySmall),
        const SizedBox(height: 10),
        Wrap(spacing: 8, runSpacing: 8, children: [OutlinedButton.icon(onPressed: _connecting ? null : _testExchange, icon: const Icon(Icons.refresh_rounded), label: Text(t('آزمایش اتصال', 'Test connection'))), OutlinedButton.icon(onPressed: _disconnectExchange, icon: const Icon(Icons.link_off_rounded), label: Text(t('قطع اتصال', 'Disconnect')))]),
      ])),
      const SizedBox(height: 14),
      Container(padding: const EdgeInsets.all(14), decoration: BoxDecoration(color: const Color(0x221F8A70), borderRadius: BorderRadius.circular(14), border: Border.all(color: const Color(0x5534D399))), child: Text(t('این نسخه سفارش واقعی ارسال نمی‌کند و کلید را برای معامله یا برداشت به‌کار نمی‌گیرد. اگر صرافی مجوزهای کلید را دقیقاً گزارش نکند یا endpoint بررسی دسترسی در دسترس نباشد، اتصال رد می‌شود.', 'This release never places real orders and does not trade or withdraw. If the exchange cannot confirm key restrictions, the connection is rejected.'), style: Theme.of(context).textTheme.bodySmall)),
    ]);
  }

  Widget _messageCard() {
    if (_message == null) return const SizedBox.shrink();
    return Padding(padding: const EdgeInsets.only(bottom: 12), child: Container(padding: const EdgeInsets.all(12), decoration: BoxDecoration(color: _messageError ? const Color(0x22F87171) : const Color(0x2222C55E), borderRadius: BorderRadius.circular(12)), child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [Icon(_messageError ? Icons.error_outline_rounded : Icons.check_circle_outline_rounded, color: _messageError ? AppTheme.negative : AppTheme.positive, size: 19), const SizedBox(width: 8), Expanded(child: Text(_message!, style: Theme.of(context).textTheme.bodySmall))])));
  }
}

extension _FirstOrNull<T> on Iterable<T> {
  T? get firstOrNull => isEmpty ? null : first;
}
