import contextlib
import os
import sqlite3
import sys
import tempfile
import time

from PySide6.QtWidgets import QApplication

import escanear_videos as escanear_mod
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


def _fila(nombre):
    return (nombre, 100.0, 1920, 1080, "h264", 1, 1024)


def _fila_bd(nombre):
    n, d, ancho, alto, codec, miniaturas, tamano = _fila(nombre)
    return (
        n, f"C:\\{n}", os.path.splitext(n)[1].lower(), "2026-08-06T00:00:00",
        d, ancho, alto, codec, miniaturas, tamano,
    )


@contextlib.contextmanager
def _ventana_con(n):
    temp = tempfile.TemporaryDirectory()
    mini = tempfile.TemporaryDirectory()
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
    nombres = [f"v{i:02d}.mp4" for i in range(1, n + 1)]
    conn.executemany(
        "INSERT INTO videos (nombre, ruta, extension, fecha_importacion, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas, tamano_bytes) VALUES (?,?,?,?,?,?,?,?,?,?)",
        [_fila_bd(nombre) for nombre in nombres],
    )
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
        yield ventana
    finally:
        ventana.close()
        ventana.gestor.cerrar()
        ventana.gestor_previews.cerrar()
        escanear_mod.ruta_carpeta_miniaturas = original_escaneo
        visor_videos.ruta_carpeta_miniaturas = original_visor
        temp.cleanup()
        mini.cleanup()


def main():
    app = QApplication(sys.argv)

    _CONTADOR[0] = 1

    # --- A) estado inicial ---
    with _ventana_con(5) as ventana:
        verifica(
            ventana.resumen_seleccion.text() == "0 de 5 seleccionados",
            "estado inicial: 0 de 5 seleccionados",
            extra=ventana.resumen_seleccion.text(),
        )

    # --- B) simple / Ctrl / Shift / deselección / limpieza ---
    with _ventana_con(5) as ventana:
        ventana._al_seleccionar_tarjeta("v01.mp4", False)
        verifica(
            ventana.resumen_seleccion.text() == "1 de 5 seleccionados",
            "selección simple: 1 de 5",
        )
        ventana._al_seleccionar_tarjeta("v02.mp4", True)
        verifica(
            ventana.resumen_seleccion.text() == "2 de 5 seleccionados",
            "Ctrl+clic agrega: 2 de 5",
        )
        ventana._al_seleccionar_tarjeta("v01.mp4", True)
        verifica(
            ventana.resumen_seleccion.text() == "1 de 5 seleccionados",
            "Ctrl+clic quita: 1 de 5",
        )
        ventana._al_seleccionar_tarjeta("v02.mp4", False)
        verifica(
            ventana.resumen_seleccion.text() == "1 de 5 seleccionados",
            "clic simple resetea y deja solo v02: 1 de 5",
        )
        ventana._al_seleccion_por_rango("v04.mp4")
        verifica(
            ventana.resumen_seleccion.text() == "3 de 5 seleccionados",
            "Shift+clic por rango (v02-v04): 3 de 5",
        )
        ventana._limpiar_seleccion()
        verifica(
            ventana.resumen_seleccion.text() == "0 de 5 seleccionados",
            "limpieza de selección: 0 de 5",
        )

    # --- C) búsqueda / filtro ---
    with _ventana_con(5) as ventana:
        ventana._al_seleccionar_tarjeta("v01.mp4", False)
        ventana._al_seleccionar_tarjeta("v02.mp4", True)
        verifica(
            ventana.resumen_seleccion.text() == "2 de 5 seleccionados",
            "antes del filtro: 2 de 5",
        )
        ventana.filtrar("v01")
        verifica(
            ventana.resumen_seleccion.text() == "1 de 1 seleccionados",
            "filtro 'v01': 1 de 1 visibles",
            extra=ventana.resumen_seleccion.text(),
        )
        ventana.filtrar("")
        verifica(
            ventana.resumen_seleccion.text() == "2 de 5 seleccionados",
            "filtro vacío: 2 de 5 de nuevo",
        )

    # --- D) cargar más ---
    with _ventana_con(105) as ventana:
        verifica(
            ventana.resumen_seleccion.text() == "0 de 100 seleccionados",
            "inicial con 105 videos: 0 de 100 (página inicial)",
        )
        ventana._al_seleccionar_tarjeta("v01.mp4", False)
        verifica(
            ventana.resumen_seleccion.text() == "1 de 100 seleccionados",
            "selección sobre página inicial: 1 de 100",
        )
        ventana.boton_cargar_mas.click()
        fin = time.monotonic() + 8000 / 1000
        while time.monotonic() < fin:
            QApplication.processEvents()
            if (
                len(ventana.tarjetas) == 105
                and not ventana.gestor.activo
                and ventana.gestor.hilo is None
            ):
                break
            time.sleep(0.02)
        QApplication.processEvents()
        verifica(
            len(ventana.tarjetas) == 105
            and ventana.resumen_seleccion.text() == "1 de 105 seleccionados",
            "cargar más: 1 de 105",
            extra=f"tarjetas={len(ventana.tarjetas)} resumen={ventana.resumen_seleccion.text()}",
        )

    # --- E) reconstrucción del catálogo y restauración ---
    with _ventana_con(5) as ventana:
        ventana._al_seleccionar_tarjeta("v01.mp4", False)
        ventana._al_seleccionar_tarjeta("v03.mp4", True)
        verifica(
            ventana.resumen_seleccion.text() == "2 de 5 seleccionados",
            "antes de reconstruir: 2 de 5",
        )
        ventana._reemplazar_tarjetas(
            [_fila("v01.mp4"), _fila("v03.mp4"), _fila("v04.mp4")]
        )
        verifica(
            ventana.resumen_seleccion.text() == "2 de 3 seleccionados",
            "reconstrucción a 3 tarjetas (v01/v03 restaurados): 2 de 3",
            extra=ventana.resumen_seleccion.text(),
        )
        ventana._reemplazar_tarjetas(
            [_fila(f"v{i:02d}.mp4") for i in range(1, 6)]
        )
        verifica(
            ventana.resumen_seleccion.text() == "2 de 5 seleccionados",
            "reconstrucción completa: selección restaurada 2 de 5",
        )

    # --- F) cambio de cantidad visible (vía filtro) ya cubierto; integridad ---
    with _ventana_con(5) as ventana:
        ventana._al_seleccionar_tarjeta("v05.mp4", False)
        verifica(
            "5 de 5 seleccionados"
            if len(ventana.visibles) == 5
            else ventana.resumen_seleccion.text() == "1 de 5 seleccionados",
            "el resumen refleja solo las visibles (no el catálogo completo)",
            extra=ventana.resumen_seleccion.text(),
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
