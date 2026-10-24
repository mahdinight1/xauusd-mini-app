import 'package:dio/dio.dart';
import 'package:flutter/material.dart';

import '../../core/services/app_storage.dart';
import '../../core/services/market_api.dart';
import '../../core/theme/app_theme.dart';

class AuthPage extends StatefulWidget {
  const AuthPage({super.key});

  @override
  State<AuthPage> createState() => _AuthPageState();
}

class _AuthPageState extends State<AuthPage> {
  final _formKey = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _register = false;
  bool _busy = false;
  bool _obscure = true;
  String? _error;

  bool get _fa => Localizations.localeOf(context).languageCode == 'fa';
  String t(String fa, String en) => _fa ? fa : en;

  @override
  void dispose() {
    _name.dispose();
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  String _friendlyError(Object error) {
    if (error is DioException) {
      final body = error.response?.data;
      if (body is Map && body['detail'] is String) return body['detail'] as String;
      if (error.response?.statusCode == 401) return t('ایمیل یا رمز عبور نادرست است.', 'Email or password is incorrect.');
      if (error.response?.statusCode == 503) return t('احراز هویت سرور پیکربندی نشده است. راهنمای بک‌اند را بررسی کن.', 'Server authentication is not configured. Check the backend setup guide.');
      return t('ارتباط با سرور برقرار نشد.', 'The backend request failed.');
    }
    return t('خطای غیرمنتظره رخ داد.', 'An unexpected error occurred.');
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() { _busy = true; _error = null; });
    try {
      final result = _register
          ? await MarketApi.instance.registerUser(displayName: _name.text.trim(), email: _email.text.trim(), password: _password.text)
          : await MarketApi.instance.loginUser(email: _email.text.trim(), password: _password.text);
      final token = result['access_token'];
      if (token is! String || token.isEmpty) throw const FormatException('Missing access token');
      await AppStorage.saveAuthToken(token);
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } catch (error) {
      if (mounted) setState(() => _error = _friendlyError(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(t('حساب NEXTRADE', 'NEXTRADE account'))),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 440),
            child: Form(
              key: _formKey,
              child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                Container(
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(22), border: Border.all(color: const Color(0xFF263747))),
                  child: Column(children: [
                    const Icon(Icons.shield_lock_rounded, size: 44, color: AppTheme.accent),
                    const SizedBox(height: 10),
                    Text(_register ? t('ساخت حساب امن', 'Create a secure account') : t('ورود امن', 'Secure sign in'), style: Theme.of(context).textTheme.headlineSmall, textAlign: TextAlign.center),
                    const SizedBox(height: 7),
                    Text(t('پیشرفت آموزشی، گواهی‌ها و اتصال صرافی به حساب کاربری متصل می‌شوند.', 'Learning progress, certificates, and exchange connections are tied to your account.'), textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodySmall),
                  ]),
                ),
                const SizedBox(height: 20),
                if (_register) ...[
                  TextFormField(controller: _name, textInputAction: TextInputAction.next, decoration: InputDecoration(labelText: t('نام نمایشی', 'Display name'), prefixIcon: const Icon(Icons.person_outline_rounded)), validator: (v) => (v == null || v.trim().length < 2) ? t('حداقل ۲ نویسه وارد کن.', 'Enter at least 2 characters.') : null),
                  const SizedBox(height: 12),
                ],
                TextFormField(controller: _email, keyboardType: TextInputType.emailAddress, textInputAction: TextInputAction.next, autocorrect: false, decoration: InputDecoration(labelText: t('ایمیل', 'Email'), prefixIcon: const Icon(Icons.email_outlined)), validator: (v) => (v == null || !v.contains('@') || v.length > 254) ? t('ایمیل معتبر وارد کن.', 'Enter a valid email address.') : null),
                const SizedBox(height: 12),
                TextFormField(controller: _password, obscureText: _obscure, textInputAction: TextInputAction.done, onFieldSubmitted: (_) => _submit(), decoration: InputDecoration(labelText: t('رمز عبور', 'Password'), prefixIcon: const Icon(Icons.key_rounded), suffixIcon: IconButton(onPressed: () => setState(() => _obscure = !_obscure), icon: Icon(_obscure ? Icons.visibility : Icons.visibility_off))), validator: (v) => (v == null || (_register ? v.length < 10 : v.isEmpty)) ? t('رمز عبور هنگام ثبت‌نام باید حداقل ۱۰ نویسه باشد.', 'Password must be at least 10 characters when registering.') : null),
                if (_register) Padding(padding: const EdgeInsets.only(top: 6), child: Text(t('از رمز عبور منحصربه‌فرد استفاده کن و آن را با کسی به اشتراک نگذار.', 'Use a unique password and never share it.'), style: Theme.of(context).textTheme.bodySmall)),
                if (_error != null) ...[
                  const SizedBox(height: 12),
                  Container(padding: const EdgeInsets.all(12), decoration: BoxDecoration(color: const Color(0x22F87171), borderRadius: BorderRadius.circular(12)), child: Text(_error!, style: const TextStyle(color: AppTheme.negative))),
                ],
                const SizedBox(height: 18),
                SizedBox(height: 50, child: FilledButton.icon(onPressed: _busy ? null : _submit, icon: _busy ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.lock_open_rounded), label: Text(_busy ? t('در حال بررسی…', 'Working…') : (_register ? t('ثبت‌نام', 'Register') : t('ورود', 'Sign in'))))),
                TextButton(onPressed: _busy ? null : () => setState(() { _register = !_register; _error = null; }), child: Text(_register ? t('قبلاً حساب ساخته‌ای؟ ورود', 'Already registered? Sign in') : t('حساب نداری؟ ثبت‌نام کن', 'New to NEXTRADE? Register'))),
              ]),
            ),
          ),
        ),
      ),
    );
  }
}
