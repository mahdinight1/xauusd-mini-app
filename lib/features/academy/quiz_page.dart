import 'package:dio/dio.dart';
import 'package:flutter/material.dart';

import '../../core/services/market_api.dart';
import '../../core/theme/app_theme.dart';

class QuizPage extends StatefulWidget {
  const QuizPage({super.key, required this.payload, required this.finalExam});
  final Map<String, dynamic> payload;
  final bool finalExam;

  @override
  State<QuizPage> createState() => _QuizPageState();
}

class _QuizPageState extends State<QuizPage> {
  final Map<String, int> _answers = {};
  Map<String, dynamic>? _result;
  bool _submitting = false;
  String? _error;

  bool get _fa => Localizations.localeOf(context).languageCode == 'fa';
  String t(String fa, String en) => _fa ? fa : en;
  List<Map<String, dynamic>> get _questions => (widget.payload['questions'] as List? ?? const [])
      .whereType<Map>().map((q) => Map<String, dynamic>.from(q)).toList();

  Future<void> _submit() async {
    if (_answers.length != _questions.length) {
      setState(() => _error = t('به همهٔ سؤال‌ها پاسخ بده.', 'Answer every question before submitting.'));
      return;
    }
    setState(() { _submitting = true; _error = null; });
    try {
      final result = await MarketApi.instance.submitAcademyQuiz(
        attemptId: widget.payload['attempt_id'] as String,
        answers: _answers,
        finalExam: widget.finalExam,
      );
      if (mounted) setState(() => _result = result);
    } catch (error) {
      if (!mounted) return;
      final message = error is DioException && error.response?.data is Map
          ? (error.response!.data as Map)['detail']?.toString()
          : null;
      setState(() => _error = message ?? t('ارسال پاسخ‌ها انجام نشد.', 'Could not submit answers.'));
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final questions = _questions;
    return Scaffold(
      appBar: AppBar(title: Text(widget.finalExam ? t('آزمون نهایی', 'Final examination') : t('آزمون بخش', 'Module quiz'))),
      body: _result == null ? _questionForm(questions) : _resultView(questions),
      bottomNavigationBar: _result == null ? SafeArea(child: Padding(padding: const EdgeInsets.all(14), child: SizedBox(height: 50, child: FilledButton.icon(onPressed: _submitting ? null : _submit, icon: _submitting ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.fact_check_rounded), label: Text(_submitting ? t('در حال ارزیابی…', 'Grading…') : t('ثبت و ارزیابی پاسخ‌ها', 'Submit answers')))))) : null,
    );
  }

  Widget _questionForm(List<Map<String, dynamic>> questions) {
    return ListView(padding: const EdgeInsets.all(16), children: [
      Container(padding: const EdgeInsets.all(14), decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(15), border: Border.all(color: const Color(0xFF263241))), child: Row(children: [const Icon(Icons.quiz_rounded, color: AppTheme.accent), const SizedBox(width: 10), Expanded(child: Text(t('برای قبولی، حداقل ${widget.payload['pass_percent'] ?? 75}٪ لازم است.', 'Pass threshold: ${widget.payload['pass_percent'] ?? 75}%.'))), Text('${_answers.length}/${questions.length}', style: const TextStyle(color: AppTheme.accent, fontWeight: FontWeight.w900))])),
      if (_error != null) Padding(padding: const EdgeInsets.only(top: 12), child: Text(_error!, style: const TextStyle(color: AppTheme.negative))),
      const SizedBox(height: 12),
      ...List.generate(questions.length, (index) {
        final question = questions[index];
        final id = question['id'] as String;
        final options = (question['options'] as List? ?? const []).whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList();
        return Container(margin: const EdgeInsets.only(bottom: 12), padding: const EdgeInsets.fromLTRB(14, 15, 14, 10), decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(17), border: Border.all(color: const Color(0xFF263241))), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('${index + 1}. ${question['question'] ?? ''}', style: const TextStyle(fontWeight: FontWeight.w800, height: 1.4)),
          const SizedBox(height: 8),
          ...options.map((option) => RadioListTile<int>(
            contentPadding: EdgeInsets.zero,
            dense: true,
            value: (option['value'] as num).toInt(),
            groupValue: _answers[id],
            onChanged: _result == null ? (value) => setState(() { if (value != null) _answers[id] = value; }) : null,
            title: Text(option['label']?.toString() ?? '', style: Theme.of(context).textTheme.bodyMedium),
            activeColor: AppTheme.accent,
          )),
        ]));
      }),
    ]);
  }

  Widget _resultView(List<Map<String, dynamic>> questions) {
    final result = _result!;
    final passed = result['passed'] == true;
    final review = (result['review'] as List? ?? const []).whereType<Map>().map((item) => Map<String, dynamic>.from(item)).toList();
    final byId = {for (final question in questions) question['id'] as String: question};
    return ListView(padding: const EdgeInsets.all(16), children: [
      Container(padding: const EdgeInsets.all(20), decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(20), border: Border.all(color: passed ? const Color(0x8834D399) : const Color(0x88F87171))), child: Column(children: [
        Icon(passed ? Icons.verified_rounded : Icons.restart_alt_rounded, size: 48, color: passed ? AppTheme.positive : AppTheme.negative),
        const SizedBox(height: 10),
        Text(passed ? t('آزمون را قبول شدی', 'Assessment passed') : t('این بار قبول نشدی', 'Assessment not passed'), style: Theme.of(context).textTheme.headlineSmall, textAlign: TextAlign.center),
        const SizedBox(height: 8),
        Text('${result['correct_count']}/${result['total']} · ${(result['percent'] as num?)?.toStringAsFixed(1) ?? '0.0'}%', style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w900, color: AppTheme.accent)),
        const SizedBox(height: 8),
        Text(passed ? t('نتیجه در حساب آموزشی ثبت شد.', 'The result was recorded in your learning account.') : t('مباحث نادرست را مرور کن و دوباره آزمون بده.', 'Review the incorrect topics and retake the assessment.'), textAlign: TextAlign.center),
        if (result['certificate'] is Map) ...[
          const SizedBox(height: 12),
          Container(width: double.infinity, padding: const EdgeInsets.all(12), decoration: BoxDecoration(color: const Color(0x2238BDF8), borderRadius: BorderRadius.circular(12)), child: Column(children: [Text(t('گواهی دوره صادر شد', 'Course certificate issued'), style: const TextStyle(fontWeight: FontWeight.w900)), const SizedBox(height: 5), Text((result['certificate'] as Map)['certificate_number']?.toString() ?? '—', style: const TextStyle(letterSpacing: 1.3, color: AppTheme.accent, fontWeight: FontWeight.w900))])),
        ] else if (widget.finalExam && passed) Padding(padding: const EdgeInsets.only(top: 10), child: Text(t('آزمون نهایی قبول شد، اما گواهی تا تکمیل تمام پیش‌نیازهای دوره صادر نمی‌شود.', 'The final exam was passed, but the certificate remains unavailable until all course prerequisites are complete.'), textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodySmall)),
      ])),
      const SizedBox(height: 18),
      Text(t('بازبینی پاسخ‌ها', 'Answer review'), style: Theme.of(context).textTheme.titleLarge),
      const SizedBox(height: 8),
      ...review.map((item) {
        final q = byId[item['question_id']?.toString()];
        return Container(margin: const EdgeInsets.only(bottom: 9), padding: const EdgeInsets.all(13), decoration: BoxDecoration(color: AppTheme.surface, borderRadius: BorderRadius.circular(14), border: Border.all(color: item['correct'] == true ? const Color(0x5534D399) : const Color(0x55F87171))), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(q?['question']?.toString() ?? item['question_id']?.toString() ?? '', style: const TextStyle(fontWeight: FontWeight.w800)),
          const SizedBox(height: 5),
          Text('${t('پاسخ درست', 'Correct answer')}: ${_optionLabel(q, item['correct_answer'])}'),
          if (item['explanation'] is String) Padding(padding: const EdgeInsets.only(top: 5), child: Text(item['explanation'].toString(), style: Theme.of(context).textTheme.bodySmall)),
        ]));
      }),
      const SizedBox(height: 10),
      FilledButton.icon(onPressed: () => Navigator.of(context).pop(true), icon: const Icon(Icons.arrow_back_rounded), label: Text(t('بازگشت به آکادمی', 'Back to academy'))),
    ]);
  }

  String _optionLabel(Map<String, dynamic>? question, dynamic value) {
    final options = (question?['options'] as List? ?? const []).whereType<Map>();
    for (final option in options) {
      if ((option['value'] as num?)?.toInt() == (value as num?)?.toInt()) return option['label']?.toString() ?? '';
    }
    return '—';
  }
}
