import contextlib
import os
import sqlite3
import sys
import tempfile
import time

from PySide6.QtWidgets import QApplication

import escanear_videos as escanear_mod
import operaciones
import visor_videos
from visor_videos import VisorVideos

_CONTADOR = [0]
_FALLOS = [0]


def _paso():
    _CONTADOR[0] += 1
    return _CONTADOR[0]


def ok(mensaje):
    _paso()
    print(f"T{_CONTADOR[0]:02d} OK - {mensaje}")


def falla(mensaje, extra=None):
    _FALLOS[0] += 1
    _paso()
    texto = f"T{_CONTADOR[0]:02d} ERROR - {mensaje}"
    if extra is not None:
        texto += f" ({extra})"
    print(texto)


def verifica(condicion, descripcion, extra=None):
    if condicion:
        ok(descripcion)
    else:
        falla(descripcion, extra)


def _crear_archivo(ruta, contenido="x"):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "wb") as f:
        f.write(contenido.encode())


@contextlib.contextmanager
def _ventana_con(n):
    temp = tempfile.TemporaryDirectory()
    mini = tempfile.TemporaryDirectory()
    videos = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp.name, "catalogo.db")
    ruta_config = os.path.join(temp.name, "config.json")
    conn = sqlite3.connect(ruta_db)
    conn.execute(
        """
        CREATE TABLE videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            ruta TEXT NOT NULL,
            extension TEXT NOT NULL,
            fecha_importacion TEXT NOT NULL,
            duracion_segundos REAL,
            ancho INTEGER,
            alto INTEGER,
            codec_video TEXT,
            cantidad_miniaturas INTEGER,
            tamano_bytes INTEGER
        )
        """
    )
    for i in range(1, n + 1):
        nombre = f"v{i:02d}.mp4"
        conn.execute(
            "INSERT INTO videos (nombre, ruta, extension, fecha_importacion, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas, tamano_bytes) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (nombre, f"C:\\{nombre}", ".mp4", "2026-08-06T00:00:00", 100.0, 1920, 1080, "h264", 1, 1024),
        )
        _crear_archivo(os.path.join(videos.name, nombre))
    conn.commit()
    conn.close()

    original_escaneo = escanear_mod.ruta_carpeta_miniaturas
    original_visor = visor_videos.ruta_carpeta_miniaturas
    escanear_mod.ruta_carpeta_miniaturas = lambda: mini.name
    visor_videos.ruta_carpeta_miniaturas = lambda: mini.name
    try:
        ventana = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        ventana.resize(900, 600)
        ventana.show()

        def esperar(predicado, intentos=300):
            for _ in range(intentos):
                QApplication.processEvents()
                if predicado():
                    return True
                time.sleep(0.02)
            QApplication.processEvents()
            return predicado()

        esperar(lambda: ventana._carga_completada and ventana.gestor.hilo is None)
        ventana.carpeta_seleccionada = videos.name
        yield ventana, videos.name
    finally:
        ventana.close()
        ventana.gestor.cerrar()
        ventana.gestor_previews.cerrar()
        ventana.gestor_operaciones.cerrar()
        escanear_mod.ruta_carpeta_miniaturas = original_escaneo
        visor_videos.ruta_carpeta_miniaturas = original_visor
        temp.cleanup()
        mini.cleanup()
        videos.cleanup()


def _esperar_operaciones(ventana, timeout_ms=8000):
    fin = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < fin:
        QApplication.processEvents()
        if not ventana.gestor_operaciones.activo and ventana.gestor_operaciones.hilo is None:
            return True
        time.sleep(0.02)
    QApplication.processEvents()
    return not ventana.gestor_operaciones.activo and ventana.gestor_operaciones.hilo is None


def main():
    app = QApplication(sys.argv)

    _CONTADOR[0] = 1

    # --- A) función pura operaciones.copiar_archivos ---
    temp = tempfile.TemporaryDirectory()
    origen = os.path.join(temp.name, "origen")
    destino = os.path.join(temp.name, "destino")
    os.makedirs(origen)
    os.makedirs(destino)
    _crear_archivo(os.path.join(origen, "a.mp4"), "aaa")
    _crear_archivo(os.path.join(origen, "b.mp4"), "bbb")
    _crear_archivo(os.path.join(origen, "sub", "c.mp4"), "ccc")
    try:
        res = operaciones.copiar_archivos(origen, ["a.mp4"], destino)
        verifica(
            res == {"copiados": [os.path.join(origen, "a.mp4")], "omitidos": [], "errores": []}
            and os.path.exists(os.path.join(destino, "a.mp4")),
            "copiar_archivos: copia un archivo",
        )
        res = operaciones.copiar_archivos(origen, ["a.mp4", "b.mp4"], destino)
        verifica(
            len(res["copiados"]) == 1
            and len(res["omitidos"]) == 1
            and os.path.exists(os.path.join(destino, "b.mp4")),
            "copiar_archivos: omitido si ya existe (a) y copia el nuevo (b)",
        )
        res = operaciones.copiar_archivos(origen, ["sub/c.mp4"], destino)
        verifica(
            len(res["copiados"]) == 1
            and os.path.exists(os.path.join(destino, "sub", "c.mp4")),
            "copiar_archivos: crea subdirectorios para nombres anidados",
        )
        res = operaciones.copiar_archivos(origen, ["no_existe.mp4"], destino)
        verifica(
            res["copiados"] == [] and len(res["errores"]) == 1,
            "copiar_archivos: archivo inexistente registra error y continúa",
        )
        try:
            operaciones.copiar_archivos(origen, "a.mp4", destino)
            verifica(False, "copiar_archivos rechaza texto en archivos")
        except TypeError:
            ok("copiar_archivos rechaza texto en archivos (TypeError)")
        try:
            operaciones.copiar_archivos("", ["a.mp4"], destino)
            verifica(False, "copiar_archivos rechaza origen vacío")
        except ValueError:
            ok("copiar_archivos rechaza origen vacío (ValueError)")
    finally:
        temp.cleanup()

    # --- B) integración: botón Copiar, diálogo, segundo plano, resumen ---
    with _ventana_con(3) as (ventana, carpeta_videos):
        dest = tempfile.TemporaryDirectory()
        try:
            ventana._al_seleccionar_tarjeta("v01.mp4", False)
            ventana._al_seleccionar_tarjeta("v02.mp4", True)
            QApplication.processEvents()
            verifica(
                ventana.boton_copiar.isEnabled(),
                "botón Copiar habilitado con selección",
            )

            emitidos = []
            ventana.gestor_operaciones.tarea_resultado.connect(
                lambda r: emitidos.append(r)
            )
            visor_videos.QFileDialog.getExistingDirectory = (
                lambda *a, **k: dest.name
            )
            ventana.boton_copiar.click()
            QApplication.processEvents()
            termino = _esperar_operaciones(ventana)
            QApplication.processEvents()
            verifica(
                termino and len(emitidos) == 1,
                "la tarea emite el resumen completo (señal tarea_resultado)",
                extra=len(emitidos),
            )
            verifica(
                emitidos and set(emitidos[0].keys()) == {"copiados", "omitidos", "errores"}
                and len(emitidos[0]["copiados"]) == 2,
                "el resumen emitido contiene copiados/omitidos/errores (2 copiados)",
                extra=emitidos[0] if emitidos else None,
            )
            verifica(
                os.path.exists(os.path.join(dest.name, "v01.mp4"))
                and os.path.exists(os.path.join(dest.name, "v02.mp4")),
                "los archivos se copiaron al destino",
            )
            verifica(
                ventana.estado_escaneo.text()
                == "Copiado: 2 — Omitidos: 0 — Errores: 0",
                "resumen final visible en la interfaz",
                extra=ventana.estado_escaneo.text(),
            )
            verifica(
                not ventana.gestor.activo and not ventana.gestor_previews.activo,
                "la interfaz no quedó bloqueada (gestores independientes)",
            )
        finally:
            dest.cleanup()

    # --- C) cancelación del diálogo: no copia nada ---
    with _ventana_con(2) as (ventana, carpeta_videos):
        dest = tempfile.TemporaryDirectory()
        try:
            ventana._al_seleccionar_tarjeta("v01.mp4", False)
            QApplication.processEvents()
            visor_videos.QFileDialog.getExistingDirectory = lambda *a, **k: ""
            ventana.boton_copiar.click()
            QApplication.processEvents()
            verifica(
                not ventana.gestor_operaciones.activo
                and os.listdir(dest.name) == [],
                "cancelar el diálogo de carpeta no copia nada",
            )
        finally:
            dest.cleanup()

    # --- D) sin selección: botón deshabilitado y clic sin efecto ---
    with _ventana_con(2) as (ventana, carpeta_videos):
        ventana._limpiar_seleccion()
        QApplication.processEvents()
        verifica(
            not ventana.boton_copiar.isEnabled(),
            "sin selección el botón Copiar queda deshabilitado",
        )
        ventana.boton_copiar.click()
        QApplication.processEvents()
        verifica(
            not ventana.gestor_operaciones.activo,
            "clic sin selección no inicia ninguna copia",
        )

    total = _CONTADOR[0] - 1
    errores = _FALLOS[0]
    print(f"TOTAL={total - errores}/{total}")
    if errores == 0:
        print("RESULTADO_FINAL=OK")
    else:
        print("RESULTADO_FINAL=ERROR")
        sys.exit(1)


if __name__ == "__main__":
    main()
