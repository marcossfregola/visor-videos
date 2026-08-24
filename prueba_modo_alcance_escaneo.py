import contextlib
import os
import sqlite3
import sys
import tempfile
import time

from PySide6.QtWidgets import QApplication

import configuracion
import escanear_videos as escanear_mod
import visor_videos
from configuracion import (
    MODO_ALCANCE_SELECCION,
    MODO_ALCANCE_SOLO,
    MODO_ALCANCE_SUBCARPETAS,
    guardar_modo_alcance,
    obtener_modo_alcance,
)
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


def _esquema(conn):
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


def _set_modo(ventana, modo):
    indice = ventana.combo_modo_alcance.findData(modo)
    ventana.combo_modo_alcance.setCurrentIndex(indice)
    QApplication.processEvents()


@contextlib.contextmanager
def _ventana_con(ruta_config):
    temp = tempfile.TemporaryDirectory()
    mini = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp.name, "catalogo.db")
    conn = sqlite3.connect(ruta_db)
    _esquema(conn)
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
        yield ventana, ruta_db
    finally:
        ventana.close()
        ventana.gestor.cerrar()
        ventana.gestor_previews.cerrar()
        ventana.gestor_operaciones.cerrar()
        escanear_mod.ruta_carpeta_miniaturas = original_escaneo
        visor_videos.ruta_carpeta_miniaturas = original_visor
        temp.cleanup()
        mini.cleanup()


def _esperar_escaneo(ventana, timeout_ms=30000):
    fin = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < fin:
        QApplication.processEvents()
        if (
            ventana.gestor.hilo is None
            and not ventana.gestor.activo
            and ventana._cola_carpetas_escaneo == []
        ):
            return True
        time.sleep(0.02)
    QApplication.processEvents()
    return False


def _nombres_bd(ruta_db):
    conn = sqlite3.connect(ruta_db)
    try:
        return sorted(
            r[0] for r in conn.execute("SELECT nombre FROM videos")
        )
    finally:
        conn.close()


def main():
    app = QApplication(sys.argv)

    _CONTADOR[0] = 1

    base = tempfile.TemporaryDirectory()
    cfg = os.path.join(base.name, "config.json")
    carpeta_a = os.path.join(base.name, "A")
    carpeta_b = os.path.join(carpeta_a, "B")
    carpeta_c = os.path.join(base.name, "C")
    os.makedirs(carpeta_b)
    os.makedirs(carpeta_c)
    _crear_archivo(os.path.join(carpeta_a, "a.mp4"))
    _crear_archivo(os.path.join(carpeta_b, "b.mp4"))
    _crear_archivo(os.path.join(carpeta_c, "c.mp4"))

    # --- A) modo "Solo carpeta actual" ---
    with _ventana_con(cfg) as (ventana, ruta_db):
        _set_modo(ventana, MODO_ALCANCE_SOLO)
        ventana.carpeta_seleccionada = carpeta_a
        ventana.iniciar_escaneo()
        _esperar_escaneo(ventana)
        verifica(
            _nombres_bd(ruta_db) == ["a.mp4"],
            "modo Solo carpeta actual: solo los archivos directos de A",
            extra=_nombres_bd(ruta_db),
        )

    # --- B) modo "Carpeta actual y todas las subcarpetas" ---
    with _ventana_con(cfg) as (ventana, ruta_db):
        _set_modo(ventana, MODO_ALCANCE_SUBCARPETAS)
        ventana.carpeta_seleccionada = carpeta_a
        ventana.iniciar_escaneo()
        _esperar_escaneo(ventana)
        verifica(
            _nombres_bd(ruta_db) == sorted(["a.mp4", os.path.join("B", "b.mp4")]),
            "modo Carpeta actual + subcarpetas: incluye B\\b.mp4",
            extra=_nombres_bd(ruta_db),
        )

    # --- C) modo "Selección personalizada" ---
    with _ventana_con(cfg) as (ventana, ruta_db):
        ventana.seleccion_carpetas.seleccionar(carpeta_a)
        ventana.seleccion_carpetas.seleccionar(carpeta_c)
        _set_modo(ventana, MODO_ALCANCE_SELECCION)
        ventana.carpeta_seleccionada = carpeta_a
        verifica(
            ventana.toggle_modo_seleccion.isChecked(),
            "al elegir Selección personalizada se activa el modo de selección del árbol",
        )
        ventana.iniciar_escaneo()
        _esperar_escaneo(ventana)
        verifica(
            _nombres_bd(ruta_db) == sorted(["a.mp4", os.path.join("B", "b.mp4"), "c.mp4"]),
            "modo Selección personalizada: escanea la unión de la selección",
            extra=_nombres_bd(ruta_db),
        )

    # --- D) persistencia del modo ---
    guardar_modo_alcance(MODO_ALCANCE_SUBCARPETAS, cfg)
    with _ventana_con(cfg) as (ventana, _):
        verifica(
            ventana._modo_alcance == MODO_ALCANCE_SUBCARPETAS
            and ventana.combo_modo_alcance.currentData()
            == MODO_ALCANCE_SUBCARPETAS,
            "el modo seleccionado se restaura al iniciar",
        )

    # --- E) migración desde configuraciones antiguas ---
    conn = sqlite3.connect(os.path.join(base.name, "migra.db"))
    _esquema(conn)
    conn.close()
    ruta_migra = os.path.join(base.name, "migra_config.json")
    with open(ruta_migra, "w", encoding="utf-8") as f:
        import json

        json.dump({"incluir_subcarpetas": True}, f)
    verifica(
        obtener_modo_alcance(ruta_migra) == MODO_ALCANCE_SUBCARPETAS,
        "migración: incluir_subcarpetas=True -> modo subcarpetas",
    )
    with open(ruta_migra, "w", encoding="utf-8") as f:
        import json

        json.dump({"incluir_subcarpetas": False}, f)
    verifica(
        obtener_modo_alcance(ruta_migra) == MODO_ALCANCE_SOLO,
        "migración: incluir_subcarpetas=False -> modo solo carpeta",
    )
    with open(ruta_migra, "w", encoding="utf-8") as f:
        import json

        json.dump({}, f)
    verifica(
        obtener_modo_alcance(ruta_migra) == MODO_ALCANCE_SOLO,
        "config sin modo ni subcarpetas -> default solo carpeta",
    )

    # --- F) compatibilidad Etapas 4-5: espejo incluir_subcarpetas ---
    with _ventana_con(cfg) as (ventana, ruta_db):
        ventana.incluir_subcarpetas.setChecked(True)
        QApplication.processEvents()
        verifica(
            ventana._modo_alcance == MODO_ALCANCE_SUBCARPETAS,
            "espejo: incluir_subcarpetas.setChecked(True) -> modo subcarpetas",
        )
        ventana.incluir_subcarpetas.setChecked(False)
        QApplication.processEvents()
        verifica(
            ventana._modo_alcance == MODO_ALCANCE_SOLO,
            "espejo: incluir_subcarpetas.setChecked(False) -> modo solo",
        )
        # multi carpeta con recursividad ON: A + A\B -> alcance efectivo [A]
        ventana.incluir_subcarpetas.setChecked(True)
        QApplication.processEvents()
        ventana.carpeta_seleccionada = carpeta_a
        ventana.iniciar_escaneo([carpeta_a, carpeta_b])
        _esperar_escaneo(ventana)
        verifica(
            _nombres_bd(ruta_db) == sorted(["a.mp4", os.path.join("B", "b.mp4")]),
            "multicarpeta con recursividad ON: A + A\\B -> [A] (sin duplicados)",
            extra=_nombres_bd(ruta_db),
        )

    # --- G) transiciones críticas en la misma ventana entre los tres modos ---
    with _ventana_con(cfg) as (ventana, ruta_db):
        ventana.carpeta_seleccionada = carpeta_a
        _set_modo(ventana, MODO_ALCANCE_SOLO)
        ventana.iniciar_escaneo()
        _esperar_escaneo(ventana)
        verifica(
            _nombres_bd(ruta_db) == ["a.mp4"],
            "transición 1: Solo carpeta -> {a.mp4}",
            extra=_nombres_bd(ruta_db),
        )
        _set_modo(ventana, MODO_ALCANCE_SUBCARPETAS)
        ventana.iniciar_escaneo()
        _esperar_escaneo(ventana)
        verifica(
            _nombres_bd(ruta_db) == sorted(
                ["a.mp4", os.path.join("B", "b.mp4")]
            ),
            "transición 2: Carpeta + subcarpetas -> {a.mp4, B\\b.mp4}",
            extra=_nombres_bd(ruta_db),
        )
        ventana.seleccion_carpetas.seleccionar(carpeta_c)
        _set_modo(ventana, MODO_ALCANCE_SELECCION)
        ventana.iniciar_escaneo()
        _esperar_escaneo(ventana)
        verifica(
            _nombres_bd(ruta_db) == sorted(
                ["a.mp4", os.path.join("B", "b.mp4"), "c.mp4"]
            ),
            "transición 3: Selección personalizada -> {a.mp4, B\\b.mp4, c.mp4}",
            extra=_nombres_bd(ruta_db),
        )
        _set_modo(ventana, MODO_ALCANCE_SOLO)
        ventana.iniciar_escaneo()
        _esperar_escaneo(ventana)
        # B8.3: c.mp4 en C no es subcarpeta de A, se preserva; B\b sí es subcarpeta y se elimina al volver a solo
        verifica(
            _nombres_bd(ruta_db) == sorted(["a.mp4", "c.mp4"]),
            "transición 4: volver a Solo carpeta conserva c.mp4 (fuera de A) y solo a.mp4 de A",
            extra=_nombres_bd(ruta_db),
        )

    base.cleanup()

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
