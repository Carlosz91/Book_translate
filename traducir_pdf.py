import os
import json
import re
import time
import pymupdf

from PIL import Image as PILImage

from googletrans import Translator
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
    Image as RLImage
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from tqdm import tqdm


# ============================================================
# CONFIGURACIÓN
# ============================================================

PDF_ENTRADA = "Extreme Ownership.pdf"
PDF_SALIDA = "Extreme Ownership - Español.pdf"

CHECKPOINT = "progreso_traduccion.json"
CARPETA_IMAGENES = "imagenes_extraidas"
VERSION_CHECKPOINT = 2

IDIOMA_ORIGEN = "en"
IDIOMA_DESTINO = "es"

# Cantidad de caracteres enviados por bloque
MAX_CHARS = 3500

# Espera entre peticiones
ESPERA = 0.4

# Tamaño máximo de una imagen en el PDF final (en puntos; A4 = 595 x 842)
ANCHO_MAX_IMAGEN = 480
ALTO_MAX_IMAGEN = 600

# Tamaño mínimo para no descartar íconos/adornos como si fueran imágenes reales
ANCHO_MINIMO_IMAGEN = 60
ALTO_MINIMO_IMAGEN = 60

# Mapeo básico de fuentes típicas del PDF original a fonts de ReportLab
MAPPING_FUENTES = (
    ("times", "Times-Roman"),
    ("georgia", "Times-Roman"),
    ("palatino", "Times-Roman"),
    ("courier", "Courier"),
    ("arial", "Helvetica"),
    ("helvetica", "Helvetica"),
    ("verdana", "Helvetica"),
    ("sans", "Helvetica"),
)


# ============================================================
# CHECKPOINT
# ============================================================

def cargar_progreso():
    if os.path.exists(CHECKPOINT):
        try:
            with open(CHECKPOINT, "r", encoding="utf-8") as f:
                progreso = json.load(f)
                if progreso.get("version", 0) < VERSION_CHECKPOINT:
                    progreso["paginas"] = {}
                    progreso["bloques"] = {}
                    progreso["version"] = VERSION_CHECKPOINT
                # Compatibilidad con checkpoints viejos sin la clave "imagenes"
                if "imagenes" not in progreso:
                    progreso["imagenes"] = {}
                if "estilos" not in progreso:
                    progreso["estilos"] = {}
                if "bloques" not in progreso:
                    progreso["bloques"] = {}
                return progreso
        except Exception:
            pass

    return {
        "paginas": {},
        "bloques": {},
        "imagenes": {},
        "estilos": {},
        "version": VERSION_CHECKPOINT
    }


def guardar_progreso(progreso):
    with open(CHECKPOINT, "w", encoding="utf-8") as f:
        json.dump(
            progreso,
            f,
            ensure_ascii=False,
            indent=2
        )


# ============================================================
# EXTRAER IMÁGENES DE UNA PÁGINA
# ============================================================

def extraer_imagenes_pagina(documento, numero_pagina, carpeta):
    """
    Extrae todas las imágenes de una página del PDF original
    y las guarda como archivos individuales en disco.
    Devuelve la lista de rutas de los archivos guardados,
    en el mismo orden en que aparecen en la página.
    """

    os.makedirs(carpeta, exist_ok=True)

    pagina = documento[numero_pagina]

    lista_imagenes = pagina.get_images(full=True)

    rutas = []

    for indice, img in enumerate(lista_imagenes):

        xref = img[0]

        try:
            base_imagen = documento.extract_image(xref)
        except Exception as e:
            print(
                f"\nNo se pudo extraer una imagen de la "
                f"página {numero_pagina + 1}: {e}"
            )
            continue

        bytes_imagen = base_imagen["image"]
        extension = base_imagen["ext"]

        nombre_archivo = (
            f"pagina_{numero_pagina}_img_{indice}.{extension}"
        )

        ruta_completa = os.path.join(carpeta, nombre_archivo)

        with open(ruta_completa, "wb") as f:
            f.write(bytes_imagen)

        # Descartar imágenes muy chicas (íconos, líneas, adornos)
        try:
            with PILImage.open(ruta_completa) as im:
                ancho, alto = im.size

            if ancho < ANCHO_MINIMO_IMAGEN or alto < ALTO_MINIMO_IMAGEN:
                os.remove(ruta_completa)
                continue

        except Exception:
            # Si no se puede leer como imagen, la descartamos
            if os.path.exists(ruta_completa):
                os.remove(ruta_completa)
            continue

        rutas.append(ruta_completa)

    return rutas


def crear_imagen_flowable(ruta_imagen):
    """
    Crea un flowable Image de reportlab a partir de un archivo,
    escalado para que entre en la página sin deformarse.
    """

    if not ruta_imagen or not os.path.exists(ruta_imagen):
        return None

    try:
        with PILImage.open(ruta_imagen) as im:
            ancho_original, alto_original = im.size
    except Exception as e:
        print(f"\nNo se pudo leer la imagen {ruta_imagen}: {e}")
        return None

    if ancho_original == 0 or alto_original == 0:
        return None

    ratio = ancho_original / alto_original

    ancho = ANCHO_MAX_IMAGEN
    alto = ancho / ratio

    if alto > ALTO_MAX_IMAGEN:
        alto = ALTO_MAX_IMAGEN
        ancho = alto * ratio

    return RLImage(ruta_imagen, width=ancho, height=alto)


# ============================================================
# DIVIDIR TEXTO
# ============================================================

def dividir_texto(texto, max_chars=MAX_CHARS):

    bloques = []

    texto = texto.strip()

    if not texto:
        return bloques

    parrafos = texto.split("\n")

    bloque_actual = ""

    for parrafo in parrafos:

        parrafo = parrafo.strip()

        if not parrafo:
            continue

        if len(bloque_actual) + len(parrafo) + 1 <= max_chars:
            bloque_actual += parrafo + "\n"
        else:

            if bloque_actual:
                bloques.append(bloque_actual.strip())

            # Si un párrafo individual es demasiado grande
            if len(parrafo) > max_chars:

                for i in range(0, len(parrafo), max_chars):
                    bloques.append(
                        parrafo[i:i + max_chars]
                    )

                bloque_actual = ""

            else:
                bloque_actual = parrafo + "\n"

    if bloque_actual:
        bloques.append(bloque_actual.strip())

    return bloques


def mapear_fuente_reportlab(nombre_fuente):
    if not nombre_fuente:
        return "Helvetica"

    nombre = str(nombre_fuente).lower()

    for patron, fuente in MAPPING_FUENTES:
        if patron in nombre:
            return fuente

    return "Helvetica"


def extraer_estilos_pagina(pagina):
    try:
        texto_dict = pagina.get_text("dict")
    except Exception:
        return []

    estilos = []

    for bloque in texto_dict.get("blocks", []):
        for linea in bloque.get("lines", []):
            for span in linea.get("spans", []):
                fuente = mapear_fuente_reportlab(span.get("font"))
                tamano = float(span.get("size") or 11)
                leading = max(tamano * 1.2, tamano + 2)

                estilos.append({
                    "fontName": fuente,
                    "fontSize": tamano,
                    "leading": leading,
                })

    return estilos


# ============================================================
# TRADUCIR
# ============================================================

def traducir_texto(translator, texto, idioma_destino=IDIOMA_DESTINO):

    bloques = dividir_texto(texto)

    traducciones = []

    for bloque in bloques:

        intentos = 0

        while intentos < 5:

            try:

                resultado = translator.translate(
                    bloque,
                    src=IDIOMA_ORIGEN,
                    dest=idioma_destino
                )

                if resultado is None or getattr(resultado, "text", None) is None:
                    raise ValueError("La respuesta del traductor no devolvió texto.")

                traducciones.append(
                    resultado.text
                )

                time.sleep(ESPERA)

                break

            except Exception as e:

                intentos += 1

                print(
                    f"\nError de traducción. "
                    f"Intento {intentos}/5"
                )

                print(e)

                time.sleep(5)

        else:

            raise Exception(
                "No se pudo traducir un bloque."
            )

    return "\n\n".join(traducciones)


def traducir_bloques(translator, bloques, idioma_destino=IDIOMA_DESTINO):
    """Traduce varios bloques por petición y conserva sus separadores."""
    traducciones = []
    grupo = []
    longitud = 0

    def traducir_grupo(grupo_actual):
        if not grupo_actual:
            return

        texto_grupo = "\n\n".join(
            f"[BLOQUE_{indice}]\n{texto}"
            for indice, texto in grupo_actual
        )
        resultado = traducir_texto(
            translator,
            texto_grupo,
            idioma_destino
        )
        partes = re.split(r"\[BLOQUE_\d+\]", resultado)
        partes = [parte.strip() for parte in partes if parte.strip()]

        if len(partes) != len(grupo_actual):
            raise ValueError(
                "La traducción no conservó los separadores de bloques."
            )

        traducciones.extend(partes)

    for indice, bloque in enumerate(bloques):
        texto = bloque["texto"]
        if grupo and longitud + len(texto) > MAX_CHARS:
            traducir_grupo(grupo)
            grupo = []
            longitud = 0

        grupo.append((indice, texto))
        longitud += len(texto)

    traducir_grupo(grupo)
    return traducciones


# ============================================================
# EXTRAER, TRADUCIR Y PROCESAR EL PDF
# ============================================================

def procesar_pdf(pdf_entrada=PDF_ENTRADA, pdf_salida=PDF_SALIDA,
                 checkpoint=CHECKPOINT, carpeta_imagenes=CARPETA_IMAGENES,
                 idioma_destino=IDIOMA_DESTINO, cancel_check=None):

    if not os.path.exists(pdf_entrada):
        print(
            f"No se encontró el archivo:\n"
            f"{pdf_entrada}"
        )
        return

    print("Abriendo PDF...")

    documento = pymupdf.open(pdf_entrada)

    total_paginas = len(documento)

    print(
        f"PDF encontrado: {total_paginas} páginas"
    )

    progreso_original = CHECKPOINT
    carpeta_original = CARPETA_IMAGENES
    globals()["CHECKPOINT"] = checkpoint
    globals()["CARPETA_IMAGENES"] = carpeta_imagenes
    progreso = cargar_progreso()

    translator = Translator()

    paginas_traducidas = progreso["paginas"]
    bloques_traducidos = progreso["bloques"]
    paginas_imagenes = progreso["imagenes"]
    estilos_paginas = progreso["estilos"]

    for numero_pagina in tqdm(
        range(total_paginas),
        desc="Procesando"
    ):

        if cancel_check and cancel_check():
            print("Traducción cancelada por el usuario.")
            documento.close()
            return

        pagina_id = str(numero_pagina)

        # --- Extraer imágenes (si no se hizo ya) ---
        if pagina_id not in paginas_imagenes:

            imagenes_pagina = extraer_imagenes_pagina(
                documento,
                numero_pagina,
                CARPETA_IMAGENES
            )

            paginas_imagenes[pagina_id] = imagenes_pagina

            guardar_progreso(progreso)

        pagina = documento[numero_pagina]

        if pagina_id not in estilos_paginas:
            estilos_paginas[pagina_id] = extraer_estilos_pagina(pagina)
            guardar_progreso(progreso)

        # --- Traducir cada bloque conservando su posición original ---
        if pagina_id in bloques_traducidos:
            continue

        texto = pagina.get_text(
            "text"
        )

        if not texto.strip():

            paginas_traducidas[pagina_id] = ""
            bloques_traducidos[pagina_id] = []

            guardar_progreso(progreso)

            continue

        print(
            f"\nTraduciendo página "
            f"{numero_pagina + 1}/{total_paginas}"
        )

        try:

            bloques = obtener_bloques_texto(pagina)
            traducciones_bloques = traducir_bloques(
                translator,
                bloques,
                idioma_destino
            )

            bloques_traducidos[pagina_id] = traducciones_bloques
            paginas_traducidas[pagina_id] = "\n".join(
                traducciones_bloques
            )

            guardar_progreso(progreso)

        except Exception as e:

            print(
                f"\nERROR en página "
                f"{numero_pagina + 1}"
            )

            print(e)

            guardar_progreso(progreso)

            print(
                "\nEl progreso fue guardado."
            )

            print(
                "Podés volver a ejecutar el script."
            )

            documento.close()

            return

    documento.close()

    if cancel_check and cancel_check():
        print("Traducción cancelada por el usuario.")
        return

    print("\n================================")
    print("TRADUCCIÓN TERMINADA")
    print("================================")

    generar_pdf(
        paginas_traducidas,
        paginas_imagenes,
        pdf_salida,
        estilos_paginas,
        pdf_entrada,
        bloques_traducidos
    )

    globals()["CHECKPOINT"] = progreso_original
    globals()["CARPETA_IMAGENES"] = carpeta_original


# ============================================================
# CREAR PDF FINAL (TEXTO + IMÁGENES)
# ============================================================

def obtener_bloques_texto(pagina):
    bloques = []

    for bloque in pagina.get_text("dict").get("blocks", []):
        if bloque.get("type") != 0 or not bloque.get("lines"):
            continue

        lineas = []
        fuente = "Helvetica"
        tamano = 10

        for linea in bloque["lines"]:
            texto_linea = "".join(
                span.get("text", "") for span in linea.get("spans", [])
            ).strip()
            if texto_linea:
                lineas.append(texto_linea)

            if linea.get("spans"):
                span = linea["spans"][0]
                fuente = mapear_fuente_reportlab(span.get("font"))
                tamano = float(span.get("size") or tamano)

        texto = "\n".join(lineas).strip()
        if texto:
            bloques.append({
                "rect": pymupdf.Rect(bloque["bbox"]),
                "texto": texto,
                "fuente": fuente,
                "tamano": tamano,
            })

    return bloques


def repartir_traduccion(texto, bloques):
    if not bloques:
        return []

    palabras = texto.split()
    pesos = [max(len(bloque["texto"]), 1) for bloque in bloques]
    total_peso = sum(pesos)
    resultado = []
    inicio = 0

    for indice, peso in enumerate(pesos):
        if indice == len(pesos) - 1:
            fin = len(palabras)
        else:
            fin = inicio + round(len(palabras) * peso / total_peso)
        resultado.append(" ".join(palabras[inicio:fin]))
        inicio = fin

    return resultado


def insertar_texto_ajustado(pagina, rect, texto, fuente, tamano):
    if not texto:
        return

    tamano_actual = tamano
    while tamano_actual >= 5:
        sobrante = pagina.insert_textbox(
            rect,
            texto,
            fontname=fuente,
            fontsize=tamano_actual,
            lineheight=1.15,
            align=pymupdf.TEXT_ALIGN_JUSTIFY,
            color=(0, 0, 0)
        )
        if sobrante >= 0:
            return

        # El español suele ocupar más espacio que el texto inglés original.
        tamano_actual -= 0.5


def generar_pdf(paginas, imagenes, archivo_salida, estilos_paginas=None,
                archivo_original=PDF_ENTRADA, bloques_traducidos=None):

    print("\nGenerando PDF conservando el diseño original...")

    original = pymupdf.open(archivo_original)
    salida = pymupdf.open()

    for numero_pagina, pagina_original in enumerate(original):
        pagina_id = str(numero_pagina)
        pagina = salida.new_page(
            width=pagina_original.rect.width,
            height=pagina_original.rect.height
        )
        pagina.show_pdf_page(pagina.rect, original, numero_pagina)

        bloques = obtener_bloques_texto(pagina_original)
        texto_traducido = paginas.get(pagina_id, "")
        traducciones_bloques = (bloques_traducidos or {}).get(pagina_id)

        for bloque in bloques:
            pagina.add_redact_annot(bloque["rect"], fill=(1, 1, 1))

        if bloques:
            pagina.apply_redactions(images=0, graphics=0, text=0)
            traducciones = (
                traducciones_bloques
                if isinstance(traducciones_bloques, list)
                else repartir_traduccion(texto_traducido, bloques)
            )
            for bloque, traduccion in zip(bloques, traducciones):
                insertar_texto_ajustado(
                    pagina,
                    bloque["rect"],
                    traduccion,
                    bloque["fuente"],
                    bloque["tamano"]
                )

    salida.save(archivo_salida, garbage=4, deflate=True)
    salida.close()
    original.close()

    print(
        f"\nPDF creado correctamente:"
    )

    print(
        os.path.abspath(archivo_salida)
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    print("========================================")
    print("   TRADUCTOR DE PDF INGLES -> ESPAÑOL")
    print("           (con imágenes)")
    print("========================================")

    procesar_pdf()