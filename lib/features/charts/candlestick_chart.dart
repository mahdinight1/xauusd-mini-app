import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../../core/theme/app_theme.dart';
import 'candle.dart';

class CandlestickChart extends StatefulWidget {
  const CandlestickChart({
    super.key,
    required this.candles,
    required this.visibleBars,
    required this.endOffset,
    required this.showEma20,
    required this.showEma50,
    required this.showBollinger,
    required this.showSupertrend,
    required this.showIchimoku,
    required this.showDonchian,
    this.signalLevels,
    required this.onViewChanged,
  });

  final List<Candle> candles;
  final int visibleBars;
  final int endOffset;
  final bool showEma20;
  final bool showEma50;
  final bool showBollinger;
  final bool showSupertrend;
  final bool showIchimoku;
  final bool showDonchian;
  final Map<String, dynamic>? signalLevels;
  final void Function(int visibleBars, int endOffset) onViewChanged;

  @override
  State<CandlestickChart> createState() => _CandlestickChartState();
}

class _CandlestickChartState extends State<CandlestickChart> {
  int _startBars = 80;
  int _startOffset = 0;
  Offset _startFocal = Offset.zero;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(builder: (context, constraints) {
      final width = constraints.maxWidth.isFinite ? constraints.maxWidth : 360.0;
      return GestureDetector(
        behavior: HitTestBehavior.opaque,
        onScaleStart: (details) {
          _startBars = widget.visibleBars;
          _startOffset = widget.endOffset;
          _startFocal = details.focalPoint;
        },
        onScaleUpdate: (details) {
          final nextBars = (_startBars / details.scale).round().clamp(30, 220).toInt();
          final horizontalShift = details.focalPoint.dx - _startFocal.dx;
          final shiftBars = (-horizontalShift / math.max(width, 1).toDouble() * _startBars).round();
          widget.onViewChanged(
            nextBars,
            (_startOffset + shiftBars).clamp(0, math.max(0, widget.candles.length - 30)).toInt(),
          );
        },
        child: CustomPaint(
          size: Size(width, 340),
          painter: _CandlestickPainter(
            candles: widget.candles,
            visibleBars: widget.visibleBars,
            endOffset: widget.endOffset,
            showEma20: widget.showEma20,
            showEma50: widget.showEma50,
            showBollinger: widget.showBollinger,
            showSupertrend: widget.showSupertrend,
            showIchimoku: widget.showIchimoku,
            showDonchian: widget.showDonchian,
            signalLevels: widget.signalLevels,
          ),
        ),
      );
    });
  }
}

class _CandlestickPainter extends CustomPainter {
  _CandlestickPainter({
    required this.candles,
    required this.visibleBars,
    required this.endOffset,
    required this.showEma20,
    required this.showEma50,
    required this.showBollinger,
    required this.showSupertrend,
    required this.showIchimoku,
    required this.showDonchian,
    required this.signalLevels,
  });

  final List<Candle> candles;
  final int visibleBars;
  final int endOffset;
  final bool showEma20;
  final bool showEma50;
  final bool showBollinger;
  final bool showSupertrend;
  final bool showIchimoku;
  final bool showDonchian;
  final Map<String, dynamic>? signalLevels;

  @override
  void paint(Canvas canvas, Size size) {
    final bg = Paint()..color = AppTheme.surface;
    canvas.drawRRect(RRect.fromRectAndRadius(Offset.zero & size, const Radius.circular(18)), bg);
    if (candles.isEmpty || size.width <= 0 || size.height <= 0) {
      _drawText(canvas, 'Waiting for real market candles…', const Offset(16, 24), AppTheme.muted, 12);
      return;
    }

    final end = (candles.length - endOffset).clamp(1, candles.length).toInt();
    final start = math.max(0, end - visibleBars).toInt();
    final slice = candles.sublist(start, end);
    if (slice.isEmpty) return;

    final highs = slice.map((c) => c.high).toList();
    final lows = slice.map((c) => c.low).toList();
    final ema20 = _ema(candles.map((c) => c.close).toList(), 20);
    final ema50 = _ema(candles.map((c) => c.close).toList(), 50);
    final bands = _bollinger(candles.map((c) => c.close).toList(), 20);
    final supertrend = _supertrendSeries(candles);
    final ichimoku = _ichimokuSeries(candles);
    final donchian = _donchianSeries(candles, 20);
    if (showSupertrend) for (var i = start; i < end; i++) { if (supertrend.$1[i] != null) { highs.add(supertrend.$1[i]!); lows.add(supertrend.$1[i]!); } }
    if (showIchimoku) for (var i = start; i < end; i++) { if (ichimoku.$1[i] != null) { highs.add(ichimoku.$1[i]!); lows.add(ichimoku.$1[i]!); } if (ichimoku.$2[i] != null) { highs.add(ichimoku.$2[i]!); lows.add(ichimoku.$2[i]!); } }
    if (showDonchian) for (var i = start; i < end; i++) { if (donchian.$1[i] != null) highs.add(donchian.$1[i]!); if (donchian.$2[i] != null) lows.add(donchian.$2[i]!); }
    if (showEma20) for (var i = start; i < end; i++) { if (ema20[i] != null) { highs.add(ema20[i]!); lows.add(ema20[i]!); } }
    if (showEma50) for (var i = start; i < end; i++) { if (ema50[i] != null) { highs.add(ema50[i]!); lows.add(ema50[i]!); } }
    if (showBollinger) {
      for (var i = start; i < end; i++) {
        if (bands.$1[i] != null) highs.add(bands.$1[i]!);
        if (bands.$2[i] != null) lows.add(bands.$2[i]!);
      }
    }
    if (signalLevels != null) {
      for (final key in const ['entry', 'stop_loss', 'tp1', 'tp2', 'tp3']) {
        final raw = signalLevels![key];
        if (raw is num && raw.toDouble().isFinite) {
          highs.add(raw.toDouble());
          lows.add(raw.toDouble());
        }
      }
    }
    var minPrice = lows.reduce((a, b) => a < b ? a : b);
    var maxPrice = highs.reduce((a, b) => a > b ? a : b);
    if (maxPrice <= minPrice) { maxPrice += 1; minPrice -= 1; }
    final pricePad = (maxPrice - minPrice) * .08;
    minPrice -= pricePad;
    maxPrice += pricePad;

    const left = 12.0;
    const right = 12.0;
    const top = 12.0;
    final priceBottom = size.height * .74;
    final volumeTop = size.height * .81;
    final volumeBottom = size.height - 17;
    final plotWidth = size.width - left - right;
    final plotHeight = priceBottom - top;
    double y(double price) => top + ((maxPrice - price) / (maxPrice - minPrice)) * plotHeight;
    double x(int localIndex) => left + (localIndex + .5) * plotWidth / slice.length;

    final grid = Paint()..color = const Color(0xFF273442)..strokeWidth = .7;
    for (var i = 0; i <= 4; i++) {
      final gy = top + plotHeight * i / 4;
      canvas.drawLine(Offset(left, gy), Offset(size.width - right, gy), grid);
      final value = maxPrice - (maxPrice - minPrice) * i / 4;
      _drawText(canvas, _formatPrice(value), Offset(size.width - 76, gy + 2), AppTheme.muted, 9);
    }

    final candleWidth = math.max(1.2, plotWidth / slice.length * .62).toDouble();
    final wickUp = Paint()..color = AppTheme.positive..strokeWidth = 1.1;
    final wickDown = Paint()..color = AppTheme.negative..strokeWidth = 1.1;
    final bodyUp = Paint()..color = AppTheme.positive;
    final bodyDown = Paint()..color = AppTheme.negative;
    for (var i = 0; i < slice.length; i++) {
      final c = slice[i];
      final cx = x(i);
      final positive = c.close >= c.open;
      final color = positive ? AppTheme.positive : AppTheme.negative;
      canvas.drawLine(Offset(cx, y(c.high)), Offset(cx, y(c.low)), positive ? wickUp : wickDown);
      final bodyTop = y(math.max(c.open, c.close).toDouble());
      final bodyBottom = y(math.min(c.open, c.close).toDouble());
      canvas.drawRect(Rect.fromLTRB(cx - candleWidth / 2, bodyTop, cx + candleWidth / 2, math.max(bodyTop + 1.5, bodyBottom).toDouble()), positive ? bodyUp : bodyDown);
      final volumeMax = math.max(1.0, slice.map((e) => e.volume).reduce((a, b) => a > b ? a : b)).toDouble();
      final volumeHeight = (c.volume / volumeMax) * (volumeBottom - volumeTop);
      canvas.drawRect(Rect.fromLTRB(cx - candleWidth / 2, volumeBottom - volumeHeight, cx + candleWidth / 2, volumeBottom), Paint()..color = color.withOpacity(.50));
    }

    if (showBollinger) {
      _drawSeries(canvas, start, end, bands.$1, x, y, const Color(0xFF7C83FD), 1.0);
      _drawSeries(canvas, start, end, bands.$2, x, y, const Color(0xFF7C83FD), 1.0);
      final middle = _sma(candles.map((c) => c.close).toList(), 20);
      _drawSeries(canvas, start, end, middle, x, y, const Color(0x668C92FF), .8);
    }
    if (showEma20) _drawSeries(canvas, start, end, ema20, x, y, const Color(0xFF38BDF8), 1.4);
    if (showEma50) _drawSeries(canvas, start, end, ema50, x, y, const Color(0xFFFBBF24), 1.4);
    if (showSupertrend) _drawSeries(canvas, start, end, supertrend.$1, x, y, const Color(0xFF34D399), 1.7);
    if (showIchimoku) {
      _drawSeries(canvas, start, end, ichimoku.$1, x, y, const Color(0xFFFB7185), 1.0);
      _drawSeries(canvas, start, end, ichimoku.$2, x, y, const Color(0xFFA78BFA), 1.0);
    }
    if (showDonchian) {
      _drawSeries(canvas, start, end, donchian.$1, x, y, const Color(0xFF60A5FA), .8);
      _drawSeries(canvas, start, end, donchian.$2, x, y, const Color(0xFF60A5FA), .8);
    }

    if (signalLevels != null) {
      const levelSpecs = <(String, String, Color)>[
        ('entry', 'ENTRY', AppTheme.accent),
        ('stop_loss', 'SL', AppTheme.negative),
        ('tp1', 'TP1', AppTheme.positive),
        ('tp2', 'TP2', AppTheme.positive),
        ('tp3', 'TP3', AppTheme.positive),
      ];
      for (final spec in levelSpecs) {
        final raw = signalLevels![spec.$1];
        if (raw is! num) continue;
        final levelY = y(raw.toDouble());
        final paint = Paint()..color = spec.$3.withOpacity(spec.$1 == 'tp3' ? .45 : .75)..strokeWidth = .9;
        canvas.drawLine(Offset(left, levelY), Offset(size.width - right, levelY), paint);
        _drawText(canvas, '${spec.$2} ${_formatPrice(raw.toDouble())}', Offset(left + 3, levelY - 12), spec.$3, 9, bold: true);
      }
    }

    final last = slice.last.close;
    final lastY = y(last);
    final lastLine = Paint()..color = AppTheme.accent.withOpacity(.75)..strokeWidth = .8;
    canvas.drawLine(Offset(left, lastY), Offset(size.width - right, lastY), lastLine);
    _drawText(canvas, _formatPrice(last), Offset(left + 3, lastY - 13), AppTheme.accent, 10, bold: true);
    _drawText(canvas, 'VOL', Offset(left + 1, volumeTop - 12), AppTheme.muted, 8);
  }

  void _drawSeries(Canvas canvas, int start, int end, List<double?> values,
      double Function(int) x, double Function(double) y, Color color, double strokeWidth) {
    final path = Path();
    var started = false;
    for (var i = start; i < end; i++) {
      final value = values[i];
      if (value == null) { started = false; continue; }
      final offset = Offset(x(i - start), y(value));
      if (!started) { path.moveTo(offset.dx, offset.dy); started = true; } else { path.lineTo(offset.dx, offset.dy); }
    }
    canvas.drawPath(path, Paint()..color = color..style = PaintingStyle.stroke..strokeWidth = strokeWidth..strokeCap = StrokeCap.round);
  }

  List<double?> _sma(List<double> values, int period) {
    final result = List<double?>.filled(values.length, null);
    for (var i = period - 1; i < values.length; i++) {
      var sum = 0.0;
      for (var j = i - period + 1; j <= i; j++) { sum += values[j]; }
      result[i] = sum / period;
    }
    return result;
  }

  List<double?> _ema(List<double> values, int period) {
    final result = List<double?>.filled(values.length, null);
    if (values.length < period) return result;
    var previous = values.take(period).reduce((a, b) => a + b) / period;
    result[period - 1] = previous;
    final alpha = 2 / (period + 1);
    for (var i = period; i < values.length; i++) {
      previous = values[i] * alpha + previous * (1 - alpha);
      result[i] = previous;
    }
    return result;
  }

  (List<double?>, List<double?>) _bollinger(List<double> values, int period) {
    final upper = List<double?>.filled(values.length, null);
    final lower = List<double?>.filled(values.length, null);
    final mid = _sma(values, period);
    for (var i = period - 1; i < values.length; i++) {
      final window = values.sublist(i - period + 1, i + 1);
      final average = mid[i]!;
      final variance = window.map((v) => (v - average) * (v - average)).reduce((a, b) => a + b) / window.length;
      final deviation = math.sqrt(variance) * 2;
      upper[i] = average + deviation;
      lower[i] = average - deviation;
    }
    return (upper, lower);
  }

  (List<double?>, List<int?>) _supertrendSeries(List<Candle> source, {int period = 10, double multiplier = 3}) {
    final length = source.length;
    final result = List<double?>.filled(length, null);
    final trends = List<int?>.filled(length, null);
    final tr = List<double>.filled(length, 0);
    for (var i = 0; i < length; i++) {
      final previousClose = i == 0 ? source[i].close : source[i - 1].close;
      tr[i] = math.max(source[i].high - source[i].low, math.max((source[i].high - previousClose).abs(), (source[i].low - previousClose).abs())).toDouble();
    }
    if (length < period) return (result, trends);
    final atrValues = List<double?>.filled(length, null);
    var currentAtr = tr.take(period).reduce((a, b) => a + b) / period;
    atrValues[period - 1] = currentAtr;
    for (var i = period; i < length; i++) {
      currentAtr = ((period - 1) * currentAtr + tr[i]) / period;
      atrValues[i] = currentAtr;
    }
    final upper = List<double?>.filled(length, null);
    final lower = List<double?>.filled(length, null);
    for (var i = period - 1; i < length; i++) {
      final c = source[i];
      final middle = (c.high + c.low) / 2;
      final basicUpper = middle + multiplier * atrValues[i]!;
      final basicLower = middle - multiplier * atrValues[i]!;
      final previousClose = i == 0 ? c.close : source[i - 1].close;
      final prevUpper = i > 0 ? upper[i - 1] : null;
      final prevLower = i > 0 ? lower[i - 1] : null;
      upper[i] = prevUpper == null || basicUpper < prevUpper || previousClose > prevUpper ? basicUpper : prevUpper;
      lower[i] = prevLower == null || basicLower > prevLower || previousClose < prevLower ? basicLower : prevLower;
      if (i == period - 1 || trends[i - 1] == null) {
        trends[i] = c.close >= middle ? 1 : -1;
      } else if (trends[i - 1] == -1 && c.close > (prevUpper ?? basicUpper)) {
        trends[i] = 1;
      } else if (trends[i - 1] == 1 && c.close < (prevLower ?? basicLower)) {
        trends[i] = -1;
      } else {
        trends[i] = trends[i - 1];
      }
      result[i] = trends[i] == 1 ? lower[i] : upper[i];
    }
    return (result, trends);
  }

  (List<double?>, List<double?>) _ichimokuSeries(List<Candle> source) {
    final spanA = List<double?>.filled(source.length, null);
    final spanB = List<double?>.filled(source.length, null);
    double? midpoint(int end, int period) {
      if (end + 1 < period) return null;
      var high = source[end - period + 1].high;
      var low = source[end - period + 1].low;
      for (var i = end - period + 1; i <= end; i++) {
        high = math.max(high, source[i].high).toDouble();
        low = math.min(low, source[i].low).toDouble();
      }
      return (high + low) / 2;
    }
    for (var i = 0; i < source.length; i++) {
      final tenkan = midpoint(i, 9);
      final kijun = midpoint(i, 26);
      spanA[i] = tenkan == null || kijun == null ? null : (tenkan + kijun) / 2;
      spanB[i] = midpoint(i, 52);
    }
    return (spanA, spanB);
  }

  (List<double?>, List<double?>) _donchianSeries(List<Candle> source, int period) {
    final upper = List<double?>.filled(source.length, null);
    final lower = List<double?>.filled(source.length, null);
    for (var i = period; i < source.length; i++) {
      var high = source[i - period].high;
      var low = source[i - period].low;
      for (var j = i - period; j < i; j++) {
        high = math.max(high, source[j].high).toDouble();
        low = math.min(low, source[j].low).toDouble();
      }
      upper[i] = high;
      lower[i] = low;
    }
    return (upper, lower);
  }

  void _drawText(Canvas canvas, String text, Offset offset, Color color, double size, {bool bold = false}) {
    final painter = TextPainter(
      text: TextSpan(text: text, style: TextStyle(color: color, fontSize: size, fontWeight: bold ? FontWeight.w800 : FontWeight.w500)),
      textDirection: TextDirection.ltr,
      maxLines: 1,
    )..layout(maxWidth: 130);
    painter.paint(canvas, offset);
  }

  String _formatPrice(double value) => value >= 1000 ? value.toStringAsFixed(1) : value >= 1 ? value.toStringAsFixed(3) : value.toStringAsFixed(6);

  @override
  bool shouldRepaint(covariant _CandlestickPainter oldDelegate) =>
      oldDelegate.candles != candles || oldDelegate.visibleBars != visibleBars || oldDelegate.endOffset != endOffset ||
      oldDelegate.showEma20 != showEma20 || oldDelegate.showEma50 != showEma50 || oldDelegate.showBollinger != showBollinger || oldDelegate.showSupertrend != showSupertrend || oldDelegate.showIchimoku != showIchimoku || oldDelegate.showDonchian != showDonchian || oldDelegate.signalLevels != signalLevels;
}
