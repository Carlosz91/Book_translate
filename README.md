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
- Los trabajos se guardan en `trabajos/` para poder conservar el progreso si una traducción se interrumpe.
- Para convertirlo en una app Android, el servidor debe publicarse en internet con autenticación y la app móvil debe consumir `POST /traducir`.
- No se deben incluir claves de APIs externas dentro de una aplicación móvil.
