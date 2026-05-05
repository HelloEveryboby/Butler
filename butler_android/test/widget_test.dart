import 'package:flutter_test/flutter_test.dart';
import 'package:butler_android/main.dart';

void main() {
  testWidgets('Butler App Smoke Test', (WidgetTester tester) async {
    // Build our app and trigger a frame.
    await tester.pumpWidget(const ButlerApp());

    // Verify that Butler System title is present
    expect(find.text('Butler System'), findsOneWidget);

    // Verify that the Go button is present
    expect(find.text('Go'), findsOneWidget);
  });
}
