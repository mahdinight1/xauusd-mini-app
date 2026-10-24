import 'package:dio/dio.dart';
import 'app_storage.dart';

class MarketApi {
  MarketApi._();
  static final MarketApi instance = MarketApi._();

  Future<Dio> _client() async {
    final base = (await AppStorage.apiBaseUrl()).trim().replaceAll(RegExp(r'/+$'), '');
    if (base.isEmpty) throw const FormatException('Backend URL is empty');
    final token = await AppStorage.authToken();
    return Dio(BaseOptions(
      baseUrl: base,
      connectTimeout: const Duration(seconds: 7),
      receiveTimeout: const Duration(seconds: 15),
      sendTimeout: const Duration(seconds: 7),
      headers: <String, dynamic>{
        'Accept': 'application/json',
        if (token != null && token.isNotEmpty) 'Authorization': 'Bearer $token',
      },
    ));
  }

  Map<String, dynamic> _map(dynamic value, String message) {
    if (value is Map) return Map<String, dynamic>.from(value);
    throw FormatException(message);
  }

  Future<Map<String, dynamic>> fetchCandles({String symbol = 'BTCUSDT', String interval = '1m', int limit = 300}) async {
    final client = await _client();
    final response = await client.get<Map<String, dynamic>>('/v1/market/candles', queryParameters: {'symbol': symbol, 'interval': interval, 'limit': limit});
    return _map(response.data, 'Backend returned an invalid candle response');
  }

  Future<Map<String, dynamic>> fetchIndicators({String symbol = 'BTCUSDT', String interval = '15m'}) async {
    final client = await _client();
    final response = await client.get<Map<String, dynamic>>('/v1/market/indicators/$symbol', queryParameters: {'interval': interval});
    final data = _map(response.data, 'Backend returned invalid indicator data');
    if (data['indicators'] is! Map) throw const FormatException('Backend returned invalid indicator data');
    return data;
  }

  Future<Map<String, dynamic>> analyze({String symbol = 'BTCUSDT', String interval = '15m'}) async {
    final client = await _client();
    final response = await client.post<Map<String, dynamic>>('/v1/analyze/$symbol', queryParameters: {'interval': interval});
    final data = _map(response.data, 'Backend returned invalid analysis data');
    if (data['direction'] is! String) throw const FormatException('Backend returned invalid analysis data');
    return data;
  }

  Future<List<Map<String, dynamic>>> markets({String? symbols}) async {
    final client = await _client();
    final response = await client.get<Map<String, dynamic>>('/v1/markets', queryParameters: symbols == null ? null : {'symbols': symbols});
    final items = response.data?['items'];
    if (items is! List) throw const FormatException('Backend returned invalid market list');
    return items.whereType<Map>().map((item) => Map<String, dynamic>.from(item)).toList();
  }

  Future<Map<String, dynamic>> createDemoAccount({required double initialCapital, List<String> symbols = const ['BTCUSDT', 'ETHUSDT'], String interval = '15m', double riskPercent = 1.0, double feeBps = 10.0}) async {
    final client = await _client();
    final response = await client.post<Map<String, dynamic>>('/v1/demo/accounts', data: {
      'initial_capital': initialCapital, 'symbols': symbols, 'interval': interval,
      'risk_percent': riskPercent, 'fee_bps': feeBps,
    });
    return _map(response.data, 'Backend returned invalid demo account');
  }

  Future<Map<String, dynamic>> fetchDemoAccount(String accountId) async {
    final client = await _client();
    final response = await client.get<Map<String, dynamic>>('/v1/demo/accounts/$accountId');
    return _map(response.data, 'Backend returned invalid demo account');
  }

  Future<Map<String, dynamic>> setDemoAuto(String accountId, bool enabled) async {
    final client = await _client();
    final response = await client.post<Map<String, dynamic>>('/v1/demo/accounts/$accountId/auto', data: {'enabled': enabled});
    return _map(response.data, 'Backend returned invalid demo account');
  }

  Future<Map<String, dynamic>> scanDemoAccount(String accountId) async {
    final client = await _client();
    final response = await client.post<Map<String, dynamic>>('/v1/demo/accounts/$accountId/scan');
    return _map(response.data, 'Backend returned invalid scan result');
  }

  Future<Map<String, dynamic>> resetDemoAccount(String accountId) async {
    final client = await _client();
    final response = await client.post<Map<String, dynamic>>('/v1/demo/accounts/$accountId/reset');
    return _map(response.data, 'Backend returned invalid demo account');
  }

  Future<List<Map<String, dynamic>>> fetchDemoPositions(String accountId, {String? status, int limit = 200}) async {
    final client = await _client();
    final response = await client.get<Map<String, dynamic>>('/v1/demo/accounts/$accountId/positions', queryParameters: {if (status != null) 'status': status, 'limit': limit});
    final items = response.data?['items'];
    if (items is! List) throw const FormatException('Backend returned invalid positions');
    return items.whereType<Map>().map((item) => Map<String, dynamic>.from(item)).toList();
  }

  Future<List<Map<String, dynamic>>> fetchDemoEvents(String accountId, {int limit = 100}) async {
    final client = await _client();
    final response = await client.get<Map<String, dynamic>>('/v1/demo/accounts/$accountId/events', queryParameters: {'limit': limit});
    final items = response.data?['items'];
    if (items is! List) throw const FormatException('Backend returned invalid demo events');
    return items.whereType<Map>().map((item) => Map<String, dynamic>.from(item)).toList();
  }

  Future<Map<String, dynamic>> runBacktest({required bool walkForward, String symbol = 'BTCUSDT', String interval = '1h', String? accountId, int candlesLimit = 500, int folds = 4, double initialCapital = 10000, double riskPercent = 1, double feeBps = 10, double slippageBps = 2}) async {
    final client = await _client();
    final response = await client.post<Map<String, dynamic>>(walkForward ? '/v1/walk-forward' : '/v1/backtest', data: {
      'symbol': symbol, 'interval': interval, 'account_id': accountId, 'candles_limit': candlesLimit,
      'folds': folds, 'train_fraction': 0.55, 'initial_capital': initialCapital,
      'risk_percent': riskPercent, 'fee_bps': feeBps, 'slippage_bps': slippageBps,
    });
    return _map(response.data, 'Backend returned invalid backtest result');
  }

  Future<List<Map<String, dynamic>>> fetchBacktestHistory({int limit = 20}) async {
    final client = await _client();
    final response = await client.get<Map<String, dynamic>>('/v1/backtest/history', queryParameters: {'limit': limit});
    final items = response.data?['items'];
    if (items is! List) throw const FormatException('Backend returned invalid backtest history');
    return items.whereType<Map>().map((item) => Map<String, dynamic>.from(item)).toList();
  }

  Future<Map<String, dynamic>> fetchEconomicCalendar({required DateTime from, required DateTime to, String? importance, String? country}) async {
    final client = await _client();
    final response = await client.get<Map<String, dynamic>>('/v1/calendar/economic', queryParameters: {
      'from': '${from.toUtc().year.toString().padLeft(4, '0')}-${from.toUtc().month.toString().padLeft(2, '0')}-${from.toUtc().day.toString().padLeft(2, '0')}',
      'to': '${to.toUtc().year.toString().padLeft(4, '0')}-${to.toUtc().month.toString().padLeft(2, '0')}-${to.toUtc().day.toString().padLeft(2, '0')}',
      'importance': importance, 'country': country,
    });
    return _map(response.data, 'Backend returned invalid calendar data');
  }

  Future<Map<String, dynamic>> fetchNotificationStatus() async {
    final client = await _client();
    final response = await client.get<Map<String, dynamic>>('/v1/notifications/status');
    return _map(response.data, 'Backend returned invalid notification status');
  }

  Future<List<Map<String, dynamic>>> fetchNotifications(String accountId, {int limit = 100}) async {
    final client = await _client();
    final response = await client.get<Map<String, dynamic>>('/v1/demo/accounts/$accountId/notifications', queryParameters: {'limit': limit});
    final items = response.data?['items'];
    if (items is! List) throw const FormatException('Backend returned invalid notifications');
    return items.whereType<Map>().map((item) => Map<String, dynamic>.from(item)).toList();
  }

  Future<Map<String, dynamic>> fetchNotificationPreferences(String accountId) async {
    // There is intentionally no public GET without an account; preferences are kept on-device until read via this endpoint.
    final client = await _client();
    final response = await client.get<Map<String, dynamic>>('/v1/demo/accounts/$accountId/notification-preferences');
    return _map(response.data, 'Backend returned invalid notification preferences');
  }

  Future<Map<String, dynamic>> saveNotificationPreferences(String accountId, Map<String, dynamic> values) async {
    final client = await _client();
    final response = await client.put<Map<String, dynamic>>('/v1/demo/accounts/$accountId/notification-preferences', data: values);
    return _map(response.data, 'Backend returned invalid notification preferences');
  }

  Future<void> markNotificationRead(String accountId, String notificationId) async {
    final client = await _client();
    await client.post<Map<String, dynamic>>('/v1/demo/accounts/$accountId/notifications/$notificationId/read');
  }


  // Identity
  Future<Map<String, dynamic>> registerUser({required String displayName, required String email, required String password}) async {
    final client = await _client();
    final response = await client.post<Map<String, dynamic>>('/v1/auth/register', data: {
      'display_name': displayName, 'email': email, 'password': password,
    });
    return _map(response.data, 'Backend returned invalid registration response');
  }

  Future<Map<String, dynamic>> loginUser({required String email, required String password}) async {
    final client = await _client();
    final response = await client.post<Map<String, dynamic>>('/v1/auth/login', data: {
      'email': email, 'password': password,
    });
    return _map(response.data, 'Backend returned invalid login response');
  }

  Future<Map<String, dynamic>> currentUser() async {
    final client = await _client();
    final response = await client.get<Map<String, dynamic>>('/v1/auth/me');
    return _map(response.data, 'Backend returned invalid user response');
  }

  Future<void> logoutUser() async {
    final client = await _client();
    try { await client.post<Map<String, dynamic>>('/v1/auth/logout'); }
    finally { await AppStorage.saveAuthToken(null); }
  }

  // Academy
  Future<Map<String, dynamic>> fetchAcademyModules() async {
    final client = await _client();
    final response = await client.get<Map<String, dynamic>>('/v1/academy/modules');
    return _map(response.data, 'Backend returned invalid academy modules');
  }

  Future<Map<String, dynamic>> fetchAcademyProgress() async {
    final client = await _client();
    final response = await client.get<Map<String, dynamic>>('/v1/academy/progress');
    return _map(response.data, 'Backend returned invalid academy progress');
  }

  Future<Map<String, dynamic>> completeLesson({required int moduleId, required String lessonId}) async {
    final client = await _client();
    final response = await client.post<Map<String, dynamic>>('/v1/academy/modules/$moduleId/lessons/$lessonId/complete', data: {'completed': true});
    return _map(response.data, 'Backend returned invalid lesson completion response');
  }

  Future<Map<String, dynamic>> startModuleQuiz(int moduleId) async {
    final client = await _client();
    final response = await client.post<Map<String, dynamic>>('/v1/academy/modules/$moduleId/quiz/start');
    return _map(response.data, 'Backend returned invalid module quiz');
  }

  Future<Map<String, dynamic>> startFinalExam() async {
    final client = await _client();
    final response = await client.post<Map<String, dynamic>>('/v1/academy/final-exam/start');
    return _map(response.data, 'Backend returned invalid final exam');
  }

  Future<Map<String, dynamic>> submitAcademyQuiz({required String attemptId, required Map<String, int> answers, required bool finalExam}) async {
    final client = await _client();
    final path = finalExam ? '/v1/academy/final-exam/$attemptId/submit' : '/v1/academy/quiz/$attemptId/submit';
    final response = await client.post<Map<String, dynamic>>(path, data: {'answers': answers});
    return _map(response.data, 'Backend returned invalid quiz result');
  }

  Future<Map<String, dynamic>> fetchMyCertificate() async {
    final client = await _client();
    final response = await client.get<Map<String, dynamic>>('/v1/academy/certificates/me');
    return _map(response.data, 'Backend returned invalid certificate response');
  }

  // Read-only exchange management. Secrets are sent only over the configured API connection and are not stored on-device.
  Future<Map<String, dynamic>> fetchExchangeConnections() async {
    final client = await _client();
    final response = await client.get<Map<String, dynamic>>('/v1/exchanges/connections');
    return _map(response.data, 'Backend returned invalid exchange connections');
  }

  Future<Map<String, dynamic>> connectBinance({required String apiKey, required String apiSecret}) async {
    final client = await _client();
    final response = await client.post<Map<String, dynamic>>('/v1/exchanges/binance/connect', data: {'api_key': apiKey, 'api_secret': apiSecret});
    return _map(response.data, 'Backend returned invalid exchange connection');
  }

  Future<Map<String, dynamic>> testBinanceConnection() async {
    final client = await _client();
    final response = await client.post<Map<String, dynamic>>('/v1/exchanges/binance/test');
    return _map(response.data, 'Backend returned invalid exchange test result');
  }

  Future<void> disconnectBinance() async {
    final client = await _client();
    await client.delete<Map<String, dynamic>>('/v1/exchanges/binance');
  }

  // Subscription plans / server-side entitlement. A client purchase alone never grants access.
  Future<Map<String, dynamic>> fetchSubscriptionPlans() async {
    final client = await _client();
    final response = await client.get<Map<String, dynamic>>('/v1/subscriptions/plans');
    return _map(response.data, 'Backend returned invalid subscription plans');
  }

  Future<Map<String, dynamic>> fetchSubscriptionEntitlement() async {
    final client = await _client();
    final response = await client.get<Map<String, dynamic>>('/v1/subscriptions/me');
    return _map(response.data, 'Backend returned invalid subscription entitlement');
  }

  // Demo billing deliberately grants only a time-limited, server-recorded test entitlement.
  // It does not contact Google Play or collect money.
  Future<Map<String, dynamic>> activateDemoSubscription({required String tier}) async {
    final client = await _client();
    final response = await client.post<Map<String, dynamic>>('/v1/subscriptions/demo/activate', data: {'tier': tier});
    return _map(response.data, 'Backend returned invalid demo subscription response');
  }

  Future<Map<String, dynamic>> verifyGooglePlayPurchase({required String productId, required String purchaseToken}) async {
    final client = await _client();
    final response = await client.post<Map<String, dynamic>>('/v1/subscriptions/google-play/verify', data: {
      'product_id': productId, 'purchase_token': purchaseToken,
    });
    return _map(response.data, 'Backend returned invalid purchase verification response');
  }
}
