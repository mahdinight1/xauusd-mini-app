import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:nextrade/main.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('starts in Persian and renders the main dashboard', (tester) async {
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(const NextraApp());
    await tester.pumpAndSettle();

    expect(find.text('NEXTRADE'), findsWidgets);
    expect(find.text('ایستگاه معاملاتی شما'), findsOneWidget);
    expect(find.text('بازارها'), findsOneWidget);
  });
}
