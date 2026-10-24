import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import '../../core/l10n/app_strings.dart';
import '../../core/services/app_storage.dart';
import '../../core/theme/app_theme.dart';

class SettingsPage extends StatefulWidget {
  const SettingsPage({super.key, required this.locale, required this.onLocaleChanged});
  final Locale locale;
  final ValueChanged<Locale> onLocaleChanged;
  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage> {
  final _urlController = TextEditingController();
  bool _loaded = false;
  bool _checking = false;
  String? _result;
  bool? _connectionOk;

  @override
  void initState() { super.initState(); _load(); }
  Future<void> _load() async { _urlController.text = await AppStorage.apiBaseUrl(); if (mounted) setState(() => _loaded = true); }
  @override
  void dispose() { _urlController.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    final s = AppStrings.of(context);
    return Scaffold(appBar: AppBar(title: Text(s.t('settings'))), body: !_loaded ? const Center(child: CircularProgressIndicator()) : ListView(padding: const EdgeInsets.all(16), children: [
      _sectionHeading(context, s.t('language')),
      Container(padding: const EdgeInsets.all(5), decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(16), border: Border.all(color: const Color(0xFF263241))), child: Row(children: [Expanded(child: _languageButton(context, 'فارسی', 'fa')), Expanded(child: _languageButton(context, 'English', 'en'))])),
      const SizedBox(height: 22),
      _sectionHeading(context, s.t('server')),
      Container(padding: const EdgeInsets.all(16), decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(19), border: Border.all(color: const Color(0xFF263241))), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(s.t('serverUrl'), style: Theme.of(context).textTheme.titleMedium), const SizedBox(height: 9), TextField(controller: _urlController, keyboardType: TextInputType.url, decoration: const InputDecoration(prefixIcon: Icon(Icons.link_rounded), hintText: 'https://api.example.com')), const SizedBox(height: 9), Text(s.t('serverHelp'), style: Theme.of(context).textTheme.bodySmall), const SizedBox(height: 13), SizedBox(width: double.infinity, child: FilledButton.icon(onPressed: _checking ? null : _testConnection, icon: _checking ? const SizedBox(width: 17, height: 17, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.wifi_tethering_rounded), label: Text(s.t('testConnection')))), if (_result != null) ...[const SizedBox(height: 10), Row(children: [Icon(_connectionOk == true ? Icons.check_circle_rounded : Icons.error_outline_rounded, color: _connectionOk == true ? AppTheme.positive : AppTheme.negative, size: 18), const SizedBox(width: 8), Expanded(child: Text(_result!, style: Theme.of(context).textTheme.bodySmall?.copyWith(color: _connectionOk == true ? AppTheme.positive : AppTheme.negative)))])]])),
      const SizedBox(height: 22),
      _sectionHeading(context, s.t('providerLabel')),
      Container(padding: const EdgeInsets.all(16), decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(19), border: Border.all(color: const Color(0xFF263241))), child: Row(children: [const Icon(Icons.cloud_done_rounded, color: AppTheme.positive, size: 24), const SizedBox(width: 12), Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(s.t('providerName'), style: const TextStyle(fontWeight: FontWeight.w700)), const SizedBox(height: 4), Text(s.t('sourceUnavailableBody'), style: Theme.of(context).textTheme.bodySmall)])), const Icon(Icons.info_outline_rounded, color: AppTheme.accent)])),
      const SizedBox(height: 22),
      Container(padding: const EdgeInsets.all(16), decoration: BoxDecoration(color: const Color(0xFF17212C), borderRadius: BorderRadius.circular(17), border: Border.all(color: const Color(0xFF2B3C4D))), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(s.t('legalTitle'), style: Theme.of(context).textTheme.titleMedium), const SizedBox(height: 6), Text(s.t('legalBody'), style: Theme.of(context).textTheme.bodySmall)])),
    ]));
  }

  Widget _sectionHeading(BuildContext context, String title) => Padding(padding: const EdgeInsets.only(bottom: 10), child: Text(title, style: Theme.of(context).textTheme.titleLarge));
  Widget _languageButton(BuildContext context, String label, String code) {
    final selected = Localizations.localeOf(context).languageCode == code;
    return InkWell(borderRadius: BorderRadius.circular(12), onTap: () => widget.onLocaleChanged(Locale(code)), child: Container(padding: const EdgeInsets.symmetric(vertical: 13), decoration: BoxDecoration(color: selected ? const Color(0x2238BDF8) : Colors.transparent, borderRadius: BorderRadius.circular(12), border: selected ? Border.all(color: const Color(0x8838BDF8)) : null), child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [if (selected) const Icon(Icons.check_circle_rounded, size: 16, color: AppTheme.accent), if (selected) const SizedBox(width: 6), Text(label, style: TextStyle(fontWeight: selected ? FontWeight.w800 : FontWeight.w500, color: selected ? AppTheme.accent : null))])));
  }

  Future<void> _testConnection() async {
    final s = AppStrings.of(context);
    final raw = _urlController.text.trim().replaceAll(RegExp(r'/+$'), '');
    final parsed = Uri.tryParse(raw);
    if (parsed == null || !parsed.hasScheme || !(raw.startsWith('http://') || raw.startsWith('https://'))) {
      setState(() { _result = s.t('connectionFailed'); _connectionOk = false; }); return;
    }
    setState(() { _checking = true; _result = null; });
    await AppStorage.saveApiBaseUrl(raw);
    try {
      final response = await Dio(BaseOptions(connectTimeout: const Duration(seconds: 4), receiveTimeout: const Duration(seconds: 4))).get('$raw/health');
      if (!mounted) return;
      final ok = response.statusCode == 200;
      setState(() { _connectionOk = ok; _result = ok ? s.t('connectionSuccess') : s.t('connectionFailed'); });
    } catch (_) {
      if (!mounted) return;
      setState(() { _connectionOk = false; _result = s.t('connectionFailed'); });
    } finally { if (mounted) setState(() => _checking = false); }
  }
}
