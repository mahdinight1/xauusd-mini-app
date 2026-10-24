import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../core/services/app_storage.dart';
import '../../core/services/market_api.dart';
import '../../core/theme/app_theme.dart';
import '../account/auth_page.dart';
import '../account/membership_exchanges_page.dart';
import 'quiz_page.dart';

class AcademyPage extends StatefulWidget {
  const AcademyPage({super.key});

  @override
  State<AcademyPage> createState() => _AcademyPageState();
}

class _AcademyPageState extends State<AcademyPage> {
  bool _loading = true;
  bool _signedIn = false;
  String? _error;
  Map<String, dynamic>? _catalog;
  Map<String, dynamic>? _progress;
  Map<String, dynamic>? _certificateDetails;
  Set<String> _completedLessonKeys = {};
  Set<int> _passedModules = {};

  bool get _fa => Localizations.localeOf(context).languageCode == 'fa';
  String t(String fa, String en) => _fa ? fa : en;
  List<Map<String, dynamic>> get _modules => (_catalog?['modules'] as List? ?? const [])
      .whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList();

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    if (mounted) setState(() { _loading = true; _error = null; });
    final token = await AppStorage.authToken();
    if (token == null || token.isEmpty) {
      if (mounted) setState(() { _signedIn = false; _loading = false; });
      return;
    }
    try {
      final values = await Future.wait([
        MarketApi.instance.fetchAcademyModules(),
        MarketApi.instance.fetchAcademyProgress(),
        MarketApi.instance.fetchMyCertificate(),
      ]);
      if (!mounted) return;
      _catalog = values[0];
      _progress = values[1];
      _certificateDetails = values[2]['issued'] == true ? values[2] : null;
      final lessonRows = (_progress?['completed_lessons'] as List? ?? const []).whereType<Map>();
      _completedLessonKeys = lessonRows.map((row) => '${row['module_id']}:${row['lesson_id']}').toSet();
      _passedModules = (_progress?['passed_module_quizzes'] as List? ?? const []).whereType<num>().map((e) => e.toInt()).toSet();
      setState(() { _signedIn = true; _loading = false; });
    } catch (error) {
      if (!mounted) return;
      if (error is DioException && error.response?.statusCode == 401) {
        await AppStorage.saveAuthToken(null);
        setState(() { _signedIn = false; _loading = false; });
      } else {
        final detail = error is DioException && error.response?.data is Map ? (error.response!.data as Map)['detail']?.toString() : null;
        setState(() { _error = detail ?? t('بارگذاری آکادمی انجام نشد. سرور و تنظیمات حساب را بررسی کن.', 'Could not load the academy. Check the backend and account settings.'); _loading = false; _signedIn = true; });
      }
    }
  }

  Future<void> _openAuth() async {
    final signedIn = await Navigator.of(context).push<bool>(MaterialPageRoute<bool>(builder: (_) => const AuthPage()));
    if (signedIn == true) await _load();
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (!_signedIn) return _signedOutView();
    final title = _catalog?['course_title']?.toString() ?? t('آکادمی ترید NEXTRADE', 'NEXTRADE Trading Academy');
    final total = (_progress?['total_lesson_count'] as num?)?.toInt() ?? _modules.fold<int>(0, (sum, module) => sum + ((module['lessons'] as List?)?.length ?? 0));
    final complete = (_progress?['completed_lesson_count'] as num?)?.toInt() ?? 0;
    final percent = (_progress?['completed_percent'] as num?)?.toDouble() ?? (total == 0 ? 0.0 : complete / total * 100);
    final hasCertificate = _progress?['certificate'] is Map;
    final totalModules = _modules.length;
    final finalPassed = _progress?['final_exam_passed'] == true;
    final canFinal = complete == total && _passedModules.length == totalModules;
    final activeTier = (_catalog?['active_tier'] ?? 'free').toString();
    final hasPremium = activeTier == 'premium';

    return RefreshIndicator(onRefresh: _load, child: ListView(padding: const EdgeInsets.fromLTRB(16, 10, 16, 24), children: [
      Text(t('آکادمی ترید', 'Trading academy'), style: Theme.of(context).textTheme.headlineMedium),
      const SizedBox(height: 6),
      Text(title, style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: AppTheme.muted)),
      const SizedBox(height: 16),
      if (_error != null) _notice(_error!, error: true),
      Container(padding: const EdgeInsets.all(18), decoration: BoxDecoration(gradient: const LinearGradient(colors: [Color(0xFF173143), Color(0xFF121923)]), borderRadius: BorderRadius.circular(21), border: Border.all(color: const Color(0xFF2A485B))), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [const Icon(Icons.school_rounded, color: AppTheme.accent), const SizedBox(width: 9), Expanded(child: Text(t('پیشرفت دوره', 'Course progress'), style: Theme.of(context).textTheme.titleLarge)), Text('${percent.toStringAsFixed(0)}%', style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w900, color: AppTheme.accent))]),
        const SizedBox(height: 14),
        ClipRRect(borderRadius: BorderRadius.circular(99), child: LinearProgressIndicator(value: total == 0 ? 0 : complete / total, minHeight: 7, backgroundColor: const Color(0xFF263747), valueColor: const AlwaysStoppedAnimation(AppTheme.accent))),
        const SizedBox(height: 9),
        Text('$complete / $total ${t('درس تکمیل‌شده', 'lessons completed')} · ${_passedModules.length}/$totalModules ${t('آزمون بخش قبول‌شده', 'module quizzes passed')}', style: Theme.of(context).textTheme.bodySmall),
        const SizedBox(height: 9),
        Text(t('برای گواهی باید همهٔ درس‌ها تکمیل، همهٔ آزمون‌های بخش قبول و آزمون نهایی با حداقل ۸۰٪ گذرانده شود.', 'Certificate requirements: complete every lesson, pass every module quiz, and score at least 80% on the final exam.'), style: Theme.of(context).textTheme.bodySmall),
      ])),
      const SizedBox(height: 16),
      if (hasCertificate) _certificateCard(_certificateDetails ?? Map<String, dynamic>.from(_progress!['certificate'] as Map)),
      Container(margin: const EdgeInsets.only(bottom: 12), decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(16), border: Border.all(color: const Color(0xFF263241))), child: ListTile(
        leading: Icon(Icons.fact_check_rounded, color: canFinal ? AppTheme.accent : AppTheme.muted),
        title: Text(t('آزمون نهایی دوره', 'Final course examination'), style: const TextStyle(fontWeight: FontWeight.w800)),
        subtitle: Text(finalPassed
            ? t('آزمون نهایی قبول شده است.', 'Final exam passed.')
            : !hasPremium
                ? t('نیازمند Premium؛ پس از تکمیل دوره، حد نصاب ۸۰٪', 'Premium required; 80% pass mark after course completion')
                : canFinal
                    ? t('۲۰ سؤال تصادفی · حد نصاب ۸۰٪', '20 randomized questions · 80% pass mark')
                    : t('ابتدا همهٔ درس‌ها و آزمون‌های بخش را تکمیل کن.', 'Complete every lesson and module quiz first.')),
        trailing: Icon(hasPremium && canFinal ? Icons.chevron_right_rounded : Icons.lock_outline_rounded),
        onTap: !hasPremium ? _openMembership : canFinal ? _startFinalExam : null,
      )),
      const SizedBox(height: 6),
      Text(t('مسیر یادگیری', 'Learning path'), style: Theme.of(context).textTheme.titleLarge),
      const SizedBox(height: 8),
      ..._modules.map(_moduleCard),
      const SizedBox(height: 12),
      Text(t('گواهی دوره توسط NEXTRADE صادر می‌شود و از طریق شناسهٔ یکتا و endpoint راستی‌آزمایی آنلاین قابل بررسی است؛ این گواهی مجوز دولتی یا اعتبارنامهٔ حرفه‌ای نیست.', 'The NEXTRADE certificate has a unique number and online verification endpoint. It is a platform course-completion record, not a government license or professional accreditation.'), style: Theme.of(context).textTheme.bodySmall),
    ]));
  }

  Widget _signedOutView() => Center(child: Padding(padding: const EdgeInsets.all(24), child: Column(mainAxisSize: MainAxisSize.min, children: [
    const Icon(Icons.school_rounded, size: 58, color: AppTheme.accent),
    const SizedBox(height: 16),
    Text(t('آکادمی با پیشرفت آنلاین', 'Learning progress and certification'), style: Theme.of(context).textTheme.headlineSmall, textAlign: TextAlign.center),
    const SizedBox(height: 8),
    Text(t('برای ثبت درس‌ها، آزمون‌های قابل‌ارزیابی و صدور گواهی، وارد حساب NEXTRADE شو یا ثبت‌نام کن.', 'Sign in or register to persist lessons, take scored exams, and issue a verifiable course certificate.'), textAlign: TextAlign.center),
    const SizedBox(height: 18),
    FilledButton.icon(onPressed: _openAuth, icon: const Icon(Icons.login_rounded), label: Text(t('ورود / ثبت‌نام', 'Sign in / Register'))),
  ])));

  Widget _moduleCard(Map<String, dynamic> module) {
    final id = (module['id'] as num).toInt();
    final lessons = (module['lessons'] as List? ?? const []).whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList();
    final doneCount = lessons.where((lesson) => _completedLessonKeys.contains('$id:${lesson['id']}')).length;
    final passed = _passedModules.contains(id);
    final locked = module['locked'] == true;
    final requiredTier = (module['required_tier'] ?? 'premium').toString().toUpperCase();
    final canQuiz = !locked && doneCount == lessons.length;
    return Container(
      margin: const EdgeInsets.only(bottom: 9),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: passed ? const Color(0x5534D399) : const Color(0xFF263241)),
      ),
      child: ExpansionTile(
        leading: CircleAvatar(
          backgroundColor: passed ? const Color(0x2234D399) : AppTheme.surface2,
          child: locked
              ? const Icon(Icons.lock_outline_rounded, color: AppTheme.muted)
              : passed
                  ? const Icon(Icons.check_rounded, color: AppTheme.positive)
                  : Text(id.toString().padLeft(2, '0'), style: const TextStyle(color: AppTheme.muted, fontWeight: FontWeight.w900)),
        ),
        title: Text(module['title']?.toString() ?? '', style: const TextStyle(fontWeight: FontWeight.w800)),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 5),
          child: Text(
            locked
                ? '${module['description'] ?? ''}\n${t('نیازمند اشتراک', 'Requires')} $requiredTier'
                : '${module['description'] ?? ''}\n$doneCount/${lessons.length} ${t('درس', 'lessons')} · ${passed ? t('آزمون قبول‌شده', 'quiz passed') : t('آزمون بخش', 'module quiz')}',
            maxLines: 3,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ),
        children: locked
            ? [
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 4, 16, 14),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                    Text(t('این بخش قفل است. محتوای درس و آزمون پس از فعال‌سازی سطح لازم در دسترس قرار می‌گیرد.', 'This module is locked. Lessons and assessment unlock after the required subscription is verified.'), style: Theme.of(context).textTheme.bodySmall),
                    const SizedBox(height: 10),
                    OutlinedButton.icon(onPressed: _openMembership, icon: const Icon(Icons.workspace_premium_rounded), label: Text(t('مشاهدهٔ اشتراک‌ها', 'View subscriptions'))),
                  ]),
                ),
              ]
            : [
                ...lessons.map((lesson) {
                  final lessonId = lesson['id'].toString();
                  final done = _completedLessonKeys.contains('$id:$lessonId');
                  return ListTile(
                    contentPadding: const EdgeInsetsDirectional.only(start: 18, end: 16),
                    leading: Icon(done ? Icons.task_alt_rounded : Icons.menu_book_rounded, color: done ? AppTheme.positive : AppTheme.accent),
                    title: Text(lesson['title']?.toString() ?? ''),
                    subtitle: Text('${lesson['minutes'] ?? 8} ${t('دقیقه', 'min')}'),
                    trailing: const Icon(Icons.chevron_right_rounded),
                    onTap: () => _openLesson(id, module, lesson, done),
                  );
                }),
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 4, 16, 14),
                  child: SizedBox(
                    width: double.infinity,
                    child: FilledButton.icon(
                      onPressed: canQuiz ? () => _startModuleQuiz(id) : null,
                      icon: Icon(passed ? Icons.verified_rounded : Icons.quiz_rounded),
                      label: Text(passed ? t('آزمون قبول شده', 'Module quiz passed') : t('شروع آزمون بخش', 'Start module quiz')),
                    ),
                  ),
                ),
              ],
      ),
    );
  }

  Future<void> _openMembership() async {
    await Navigator.of(context).push<void>(MaterialPageRoute<void>(builder: (_) => const MembershipExchangesPage()));
    if (mounted) await _load();
  }

  Future<void> _openLesson(int moduleId, Map<String, dynamic> module, Map<String, dynamic> lesson, bool alreadyDone) async {
    final result = await showDialog<bool>(context: context, builder: (ctx) => AlertDialog(
      title: Text(lesson['title']?.toString() ?? ''),
      content: SizedBox(width: 520, child: SingleChildScrollView(child: SelectableText(lesson['content']?.toString() ?? '', style: Theme.of(context).textTheme.bodyMedium?.copyWith(height: 1.55)))),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx, false), child: Text(t('بستن', 'Close'))),
        FilledButton.icon(onPressed: alreadyDone ? () => Navigator.pop(ctx, false) : () => Navigator.pop(ctx, true), icon: Icon(alreadyDone ? Icons.check_circle_rounded : Icons.task_alt_rounded), label: Text(alreadyDone ? t('تکمیل شده', 'Completed') : t('ثبت تکمیل درس', 'Mark lesson complete'))),
      ],
    ));
    if (result != true) return;
    try {
      await MarketApi.instance.completeLesson(moduleId: moduleId, lessonId: lesson['id'].toString());
      await _load();
    } catch (error) { if (mounted) _noticeDialog(_displayError(error)); }
  }

  Future<void> _startModuleQuiz(int moduleId) async {
    try {
      final payload = await MarketApi.instance.startModuleQuiz(moduleId);
      if (!mounted) return;
      final submitted = await Navigator.of(context).push<bool>(MaterialPageRoute<bool>(builder: (_) => QuizPage(payload: payload, finalExam: false)));
      if (submitted == true) await _load();
    } catch (error) { if (mounted) _noticeDialog(_displayError(error)); }
  }

  Future<void> _startFinalExam() async {
    try {
      final payload = await MarketApi.instance.startFinalExam();
      if (!mounted) return;
      final submitted = await Navigator.of(context).push<bool>(MaterialPageRoute<bool>(builder: (_) => QuizPage(payload: payload, finalExam: true)));
      if (submitted == true) await _load();
    } catch (error) { if (mounted) _noticeDialog(_displayError(error)); }
  }

  String _displayError(Object error) {
    if (error is DioException && error.response?.data is Map) return (error.response!.data as Map)['detail']?.toString() ?? t('درخواست ناموفق بود.', 'Request failed.');
    return t('درخواست ناموفق بود. اتصال سرور را بررسی کن.', 'Request failed. Check the backend connection.');
  }

  Future<void> _noticeDialog(String message) => showDialog<void>(context: context, builder: (ctx) => AlertDialog(content: Text(message), actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: Text(t('تأیید', 'OK')))]));

  Widget _notice(String message, {bool error = false}) => Container(margin: const EdgeInsets.only(bottom: 12), padding: const EdgeInsets.all(12), decoration: BoxDecoration(color: error ? const Color(0x22F87171) : const Color(0x2222C55E), borderRadius: BorderRadius.circular(12)), child: Text(message, style: TextStyle(color: error ? AppTheme.negative : AppTheme.positive)));

  Widget _certificateCard(Map<String, dynamic> certificate) => Container(margin: const EdgeInsets.only(bottom: 12), padding: const EdgeInsets.all(16), decoration: BoxDecoration(gradient: const LinearGradient(colors: [Color(0xFF302B18), Color(0xFF151A20)]), borderRadius: BorderRadius.circular(17), border: Border.all(color: const Color(0x997CA34B))), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    Row(children: [const Icon(Icons.workspace_premium_rounded, color: Color(0xFFF5C451), size: 30), const SizedBox(width: 10), Expanded(child: Text(t('گواهی دوره صادرشده', 'Course certificate issued'), style: Theme.of(context).textTheme.titleLarge))]),
    const SizedBox(height: 8),
    Text(certificate['course_title']?.toString() ?? '', style: Theme.of(context).textTheme.bodySmall),
    const SizedBox(height: 8),
    SelectableText(certificate['certificate_number']?.toString() ?? '—', style: const TextStyle(letterSpacing: 1.3, fontWeight: FontWeight.w900, color: Color(0xFFF5C451))),
    Text('${t('نمرهٔ نهایی', 'Final score')}: ${certificate['final_score'] ?? '—'}% · ${certificate['issued_at'] ?? ''}', style: Theme.of(context).textTheme.bodySmall),
    const SizedBox(height: 8),
    if (certificate['status'] != null) Text('${t('وضعیت', 'Status')}: ${certificate['status']}', style: Theme.of(context).textTheme.bodySmall),
    const SizedBox(height: 8),
    Wrap(spacing: 8, runSpacing: 8, children: [
      OutlinedButton.icon(
        onPressed: certificate['verification_url'] is String ? () => _copyCertificateLink(certificate['verification_url'] as String, printable: false) : null,
        icon: const Icon(Icons.verified_user_outlined),
        label: Text(t('کپی لینک راستی‌آزمایی', 'Copy verification link')),
      ),
      OutlinedButton.icon(
        onPressed: certificate['printable_url'] is String ? () => _copyCertificateLink(certificate['printable_url'] as String, printable: true) : null,
        icon: const Icon(Icons.print_outlined),
        label: Text(t('کپی لینک نسخهٔ چاپی', 'Copy printable version link')),
      ),
    ]),
    Text(t('لینک نسخهٔ چاپی را در مرورگر باز کن و گزینهٔ Print / Save as PDF را بزن. این گواهی، مدرک تکمیل دورهٔ پلتفرم است نه مجوز رسمی.', 'Open the printable link in a browser and use Print / Save as PDF. This proves platform course completion, not an official license.'), style: Theme.of(context).textTheme.bodySmall),
  ]));

  Future<void> _copyCertificateLink(String url, {required bool printable}) async {
    await Clipboard.setData(ClipboardData(text: url));
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(printable
        ? t('لینک نسخهٔ چاپی کپی شد؛ آن را در مرورگر باز کن.', 'Printable certificate link copied; open it in a browser.')
        : t('لینک راستی‌آزمایی کپی شد.', 'Verification link copied.'))));
  }
}
