import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class AppStorage {
  static const _localeKey = 'locale_code';
  static const _demoCapitalKey = 'demo_initial_capital';
  static const _academyKey = 'academy_completed_modules';
  static const _apiBaseKey = 'api_base_url';
  static const _demoAccountIdKey = 'demo_remote_account_id';
  static const _authTokenKey = 'nextrade_access_token';
  static const FlutterSecureStorage _secureStorage = FlutterSecureStorage();

  /// Session token is stored in Android Keystore-backed secure storage, never in preferences.
  static Future<String?> authToken() => _secureStorage.read(key: _authTokenKey);

  static Future<void> saveAuthToken(String? token) async {
    if (token == null || token.trim().isEmpty) {
      await _secureStorage.delete(key: _authTokenKey);
    } else {
      await _secureStorage.write(key: _authTokenKey, value: token.trim());
    }
  }

  static Future<String> localeCode() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_localeKey) ?? 'fa';
  }

  static Future<void> saveLocale(String code) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_localeKey, code);
  }

  static Future<double?> demoCapital() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getDouble(_demoCapitalKey);
  }

  static Future<void> saveDemoCapital(double? amount) async {
    final prefs = await SharedPreferences.getInstance();
    if (amount == null) {
      await prefs.remove(_demoCapitalKey);
    } else {
      await prefs.setDouble(_demoCapitalKey, amount);
    }
  }

  static Future<Set<int>> completedModules() async {
    final prefs = await SharedPreferences.getInstance();
    return (prefs.getStringList(_academyKey) ?? <String>[])
        .map(int.tryParse).whereType<int>().toSet();
  }

  static Future<void> saveCompletedModules(Set<int> values) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setStringList(_academyKey, values.map((e) => e.toString()).toList());
  }

  static Future<String?> demoAccountId() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_demoAccountIdKey);
  }

  static Future<void> saveDemoAccountId(String? value) async {
    final prefs = await SharedPreferences.getInstance();
    if (value == null || value.trim().isEmpty) {
      await prefs.remove(_demoAccountIdKey);
    } else {
      await prefs.setString(_demoAccountIdKey, value.trim());
    }
  }

  static Future<String> apiBaseUrl() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_apiBaseKey) ?? 'http://10.0.2.2:8000';
  }

  static Future<void> saveApiBaseUrl(String value) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_apiBaseKey, value.trim());
  }
}
