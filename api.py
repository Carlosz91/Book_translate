import asyncio
import os
import shutil
import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse

import traducir_pdf


app = FastAPI(title="Traductor de libros PDF")
PORT = int(os.getenv("PORT", "8000"))
JOBS = Path("trabajos")
JOBS.mkdir(exist_ok=True)
IDIOMAS_DISPONIBLES = {
    "es": "Español",
    "en": "Inglés",
    "fr": "Francés",
    "de": "Alemán",
    "it": "Italiano",
    "pt": "Portugués",
    "ja": "Japonés",
    "ko": "Coreano",
    "zh-cn": "Chino simplificado",
}
ESTADOS = {}


@app.get("/")
def inicio():
    return FileResponse(
        "index.html",
        media_type="text/html",
        headers={"Cache-Control": "no-store"}
    )


@app.get("/manifest.webmanifest")
def manifiesto():
    return FileResponse(
        "manifest.webmanifest",
        media_type="application/manifest+json",
        headers={"Cache-Control": "no-store"}
    )


@app.get("/sw.js")
def service_worker():
    return FileResponse(
        "sw.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-store"}
    )


async def ejecutar_traduccion(job_id, trabajo, idioma):
    entrada = trabajo / "entrada.pdf"
    salida = trabajo / "traducido.pdf"
    checkpoint = trabajo / "progreso.json"
    imagenes = trabajo / "imagenes"

    try:
        ESTADOS[job_id]["estado"] = "traduciendo"
        await asyncio.to_thread(
            traducir_pdf.procesar_pdf,
            str(entrada),
            str(salida),
            str(checkpoint),
            str(imagenes),
            idioma,
            lambda: ESTADOS.get(job_id, {}).get("estado") == "cancelando"
        )
        if ESTADOS[job_id].get("estado") == "cancelando":
            ESTADOS[job_id].update({"estado": "cancelado"})
            return
        if not salida.exists():
            raise RuntimeError("No se pudo generar el PDF traducido.")
        ESTADOS[job_id].update({
            "estado": "terminado",
            "archivo": str(salida),
            "nombre": f"libro-traducido-{idioma}.pdf"
        })
    except Exception as error:
        ESTADOS[job_id].update({
            "estado": "error",
            "error": str(error)
        })


@app.post("/traducir")
async def traducir(
    archivo: UploadFile = File(...),
    idioma: str = Form("es")
):
    if not archivo.filename or not archivo.filename.lower().endswith(".pdf"):
        return JSONResponse(
            {"error": "Solo se aceptan archivos PDF."},
            status_code=400
        )

    idioma = idioma.lower().strip()
    if idioma not in IDIOMAS_DISPONIBLES:
        return JSONResponse(
            {"error": "Idioma no disponible.", "disponibles": IDIOMAS_DISPONIBLES},
            status_code=400
        )

    trabajo = Path(tempfile.mkdtemp(prefix="pdf_", dir=JOBS))
    job_id = uuid.uuid4().hex
    entrada = trabajo / "entrada.pdf"

    with entrada.open("wb") as destino:
        shutil.copyfileobj(archivo.file, destino)

    ESTADOS[job_id] = {"estado": "pendiente", "idioma": idioma}
    asyncio.create_task(ejecutar_traduccion(job_id, trabajo, idioma))

    return {"id": job_id, "estado": "pendiente"}


@app.get("/trabajos/{job_id}")
def estado_trabajo(job_id: str):
    estado = ESTADOS.get(job_id)
    if estado is None:
        return JSONResponse({"error": "Trabajo no encontrado."}, status_code=404)
    return estado


@app.post("/trabajos/{job_id}/cancelar")
def cancelar_trabajo(job_id: str):
    estado = ESTADOS.get(job_id)
    if estado is None:
        return JSONResponse({"error": "Trabajo no encontrado."}, status_code=404)
    if estado["estado"] in {"terminado", "error", "cancelado"}:
        return JSONResponse({"error": "El trabajo ya terminó."}, status_code=409)
    estado["estado"] = "cancelando"
    return {"id": job_id, "estado": "cancelando"}


@app.get("/trabajos/{job_id}/descarga")
def descargar_trabajo(job_id: str):
    estado = ESTADOS.get(job_id)
    if estado is None:
        return JSONResponse({"error": "Trabajo no encontrado."}, status_code=404)
    if estado.get("estado") != "terminado":
        return JSONResponse({"error": "El trabajo todavía no terminó."}, status_code=409)

    return FileResponse(
        estado["archivo"],
        media_type="application/pdf",
        filename=estado["nombre"]
    )