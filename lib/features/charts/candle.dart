class Candle {
  const Candle({
    required this.openTime,
    required this.closeTime,
    required this.open,
    required this.high,
    required this.low,
    required this.close,
    required this.volume,
    this.closed = false,
  });

  final int openTime;
  final int closeTime;
  final double open;
  final double high;
  final double low;
  final double close;
  final double volume;
  final bool closed;

  factory Candle.fromJson(Map<String, dynamic> json) => Candle(
        openTime: _int(json['open_time']),
        closeTime: _int(json['close_time']),
        open: _double(json['open']),
        high: _double(json['high']),
        low: _double(json['low']),
        close: _double(json['close']),
        volume: _double(json['volume']),
        closed: json['closed'] == true,
      );

  factory Candle.fromStreamKline(Map<String, dynamic> kline) => Candle(
        openTime: _int(kline['t']),
        closeTime: _int(kline['T']),
        open: _double(kline['o']),
        high: _double(kline['h']),
        low: _double(kline['l']),
        close: _double(kline['c']),
        volume: _double(kline['v']),
        closed: kline['x'] == true,
      );

  Map<String, dynamic> toJson() => {
        'open_time': openTime,
        'close_time': closeTime,
        'open': open,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
        'closed': closed,
      };

  static int _int(dynamic value) {
    if (value is int) return value;
    return int.tryParse(value.toString()) ?? 0;
  }

  static double _double(dynamic value) {
    if (value is num) return value.toDouble();
    return double.tryParse(value.toString()) ?? 0;
  }
}
