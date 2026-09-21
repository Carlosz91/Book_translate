import 'dart:convert';
import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:open_filex/open_filex.dart';
import 'package:path_provider/path_provider.dart';

const apiBaseUrl = String.fromEnvironment('API_BASE_URL', defaultValue: 'https://web-production-eaa09e.up.railway.app');
const idiomas = <String, String>{'es': 'Español', 'en': 'Inglés', 'fr': 'Francés', 'de': 'Alemán', 'it': 'Italiano', 'pt': 'Portugués', 'ja': 'Japonés', 'ko': 'Coreano', 'zh-cn': 'Chino simplificado'};

void main() => runApp(const BookTranslateApp());

class BookTranslateApp extends StatelessWidget {
  const BookTranslateApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    debugShowCheckedModeBanner: false,
    title: 'Traductor de libros',
    theme: ThemeData(colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xff1f514b)), scaffoldBackgroundColor: const Color(0xfff1eee7), useMaterial3: true),
    home: const TranslatorPage(),
  );
}

class TranslatorPage extends StatefulWidget {
  const TranslatorPage({super.key});
  @override State<TranslatorPage> createState() => _TranslatorPageState();
}

class _TranslatorPageState extends State<TranslatorPage> {
  PlatformFile? selectedFile;
  String language = 'es';
  String status = 'Selecciona un libro PDF para comenzar.';
  String? jobId;
  bool busy = false;

  Future<void> chooseFile() async {
    final result = await FilePicker.platform.pickFiles(type: FileType.custom, allowedExtensions: ['pdf'], withData: false);
    if (result != null && mounted) setState(() { selectedFile = result.files.single; status = 'Listo para traducir.'; });
  }

  Future<void> translate() async {
    if (selectedFile?.path == null || busy) return;
    setState(() { busy = true; status = 'Subiendo el libro...'; });
    try {
      final request = http.MultipartRequest('POST', Uri.parse('$apiBaseUrl/traducir'))
        ..fields['idioma'] = language
        ..files.add(await http.MultipartFile.fromPath('archivo', selectedFile!.path!, filename: selectedFile!.name));
      final response = await request.send();
      final body = jsonDecode(await response.stream.bytesToString());
      if (response.statusCode != 200) throw Exception(body['error'] ?? 'No se pudo iniciar la traducción.');
      jobId = body['id'] as String;
      await pollStatus();
    } catch (error) {
      if (mounted) setState(() => status = error.toString());
      finish();
    }
  }

  Future<void> pollStatus() async {
    while (busy && jobId != null) {
      await Future<void>.delayed(const Duration(seconds: 2));
      if (!busy) return;
      final response = await http.get(Uri.parse('$apiBaseUrl/trabajos/$jobId'));
      final body = jsonDecode(response.body) as Map<String, dynamic>;
      final current = body['estado'] as String? ?? 'traduciendo';
      if (mounted) setState(() => status = current == 'pendiente' ? 'Preparando el libro...' : 'Traduciendo. Puedes esperar aquí...');
      if (current == 'terminado') { await downloadResult(); return; }
      if (current == 'cancelado' || current == 'error') throw Exception(body['error'] ?? 'La traducción no se completó.');
    }
  }

  Future<void> downloadResult() async {
    final response = await http.get(Uri.parse('$apiBaseUrl/trabajos/$jobId/descarga'));
    if (response.statusCode != 200) throw Exception('No se pudo descargar el PDF traducido.');
    final directory = await getApplicationDocumentsDirectory();
    final file = File('${directory.path}/libro-traducido-$language.pdf');
    await file.writeAsBytes(response.bodyBytes);
    if (mounted) setState(() => status = 'Traducción terminada.');
    await OpenFilex.open(file.path);
    finish();
  }

  Future<void> cancel() async {
    if (jobId == null) return;
    setState(() => status = 'Cancelando...');
    await http.post(Uri.parse('$apiBaseUrl/trabajos/$jobId/cancelar'));
    finish('Traducción cancelada.');
  }

  void finish([String? finalStatus]) {
    if (mounted) setState(() { busy = false; jobId = null; if (finalStatus != null) status = finalStatus; });
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Traductor de libros PDF')),
    body: SafeArea(child: Center(child: SingleChildScrollView(padding: const EdgeInsets.all(20), child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 620), child: Card(child: Padding(padding: const EdgeInsets.all(24), child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      const Text('Traducir un libro', style: TextStyle(fontSize: 32, fontWeight: FontWeight.w600)),
      const SizedBox(height: 8), const Text('Conserva las páginas, imágenes y distribución del PDF original.'),
      const SizedBox(height: 24),
      OutlinedButton.icon(onPressed: busy ? null : chooseFile, icon: const Icon(Icons.picture_as_pdf_outlined), label: Text(selectedFile?.name ?? 'Elegir PDF')),
      const SizedBox(height: 16),
      DropdownButtonFormField<String>(initialValue: language, decoration: const InputDecoration(labelText: 'Idioma de destino', border: OutlineInputBorder()), items: idiomas.entries.map((entry) => DropdownMenuItem(value: entry.key, child: Text(entry.value))).toList(), onChanged: busy ? null : (value) => setState(() => language = value!)),
      const SizedBox(height: 20),
      if (busy) ...[const Center(child: CircularProgressIndicator()), const SizedBox(height: 12), Text(status, textAlign: TextAlign.center), const SizedBox(height: 12), OutlinedButton.icon(onPressed: cancel, icon: const Icon(Icons.close), label: const Text('Cancelar'))] else ...[FilledButton.icon(onPressed: selectedFile == null ? null : translate, icon: const Icon(Icons.translate), label: const Text('Traducir PDF')), const SizedBox(height: 12), Text(status, textAlign: TextAlign.center)],
    ]))))))),
  );
}
