import 'package:flutter_test/flutter_test.dart';

import 'package:book_translate/main.dart';

void main() {
  testWidgets('muestra la pantalla del traductor', (WidgetTester tester) async {
    await tester.pumpWidget(const BookTranslateApp());

    expect(find.text('Traducir un libro'), findsOneWidget);
    expect(find.text('Elegir PDF'), findsOneWidget);
    expect(find.text('Traducir PDF'), findsOneWidget);
  });
}
