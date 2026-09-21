# Traductor de libros PDF

Aplicación local para traducir libros PDF y conservar las páginas, imágenes y distribución del documento original.

## Ejecutar la aplicación

Instala las dependencias:

```powershell
python -m pip install -r requirements.txt
```

Inicia el servidor:

```powershell
python -m uvicorn api:app --host 127.0.0.1 --port 8000
```

Abre en el navegador:

http://127.0.0.1:8000

Selecciona un PDF en inglés y pulsa `Traducir PDF`. El resultado se descargará cuando termine.

Idiomas disponibles: español, inglés, francés, alemán, italiano, portugués, japonés, coreano y chino simplificado.

## Notas

- El motor actual usa `googletrans`; puede tener límites o timeouts porque no es una API oficial.
- Railway usa Python 3.12 mediante `runtime.txt`, porque `googletrans` todavía depende de módulos retirados en Python 3.13+.
- Los trabajos se guardan en `trabajos/` para poder conservar el progreso si una traducción se interrumpe.
- Para convertirlo en una app Android, el servidor debe publicarse en internet con autenticación y la app móvil debe consumir `POST /traducir`.
- No se deben incluir claves de APIs externas dentro de una aplicación móvil.

## Aplicación Android

La carpeta `mobile_app/` contiene la aplicación Flutter para Google Play. Usa el mismo backend y permite elegir PDF, idioma, cancelar trabajos y abrir el resultado.

Cuando Railway tenga un dominio público, genera el APK de prueba así:

```powershell
cd mobile_app
flutter pub get
flutter build apk --release --dart-define=API_BASE_URL=https://TU-DOMINIO.up.railway.app
```

Para Google Play se debe generar un App Bundle firmado:

```powershell
flutter build appbundle --release --dart-define=API_BASE_URL=https://TU-DOMINIO.up.railway.app
```

El archivo para Play Console quedará en `mobile_app/build/app/outputs/bundle/release/app-release.aab`.
