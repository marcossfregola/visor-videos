import contextlib
import os
import sqlite3
import sys
import tempfile
import time

from PySide6.QtWidgets import QApplication

import escanear_videos as escanear_mod
import visor_videos
from visor_videos import VisorVideos, _alcance_efectivo

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


@contextlib.contextmanager
def _ventana_con():
    temp = tempfile.TemporaryDirectory()
    mini = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp.name, "catalogo.db")
    ruta_config = os.path.join(temp.name, "config.json")
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
        yield ventana
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


def _nombres(ventana):
    return [n for n, _ in ventana.tarjetas]


def main():
    app = QApplication(sys.argv)

    _CONTADOR[0] = 1

    base = tempfile.TemporaryDirectory()
    carpeta_a = os.path.join(base.name, "A")
    carpeta_b = os.path.join(base.name, "B")
    os.makedirs(carpeta_a)
    os.makedirs(carpeta_b)
    _crear_archivo(os.path.join(carpeta_a, "v01.mp4"))
    _crear_archivo(os.path.join(carpeta_a, "v02.mp4"))
    _crear_archivo(os.path.join(carpeta_a, "nota.txt"))
    _crear_archivo(os.path.join(carpeta_b, "v03.mp4"))
    _crear_archivo(os.path.join(carpeta_b, "v04.mkv"))
    _crear_archivo(os.path.join(carpeta_b, "leeme.txt"))

    # --- A) modo tradicional: una carpeta ---
    with _ventana_con() as ventana:
        ventana.carpeta_seleccionada = carpeta_a
        ventana.iniciar_escaneo()
        termino = _esperar_escaneo(ventana)
        verifica(
            termino and sorted(_nombres(ventana)) == ["v01.mp4", "v02.mp4"],
            "escaneo tradicional de una carpeta (sin regresión)",
            extra=sorted(_nombres(ventana)),
        )
        verifica(
            carpeta_a in ventana.carpetas_escaneadas,
            "el modo tradicional marca la carpeta como escaneada",
        )

    # --- B) escaneo multicarpeta: unión ---
    with _ventana_con() as ventana:
        ventana.carpeta_seleccionada = carpeta_a
        ventana.iniciar_escaneo([carpeta_a, carpeta_b])
        termino = _esperar_escaneo(ventana)
        verifica(
            termino
            and sorted(_nombres(ventana))
            == ["v01.mp4", "v02.mp4", "v03.mp4", "v04.mkv"],
            "el escaneo multicarpeta produce la unión de videos",
            extra=sorted(_nombres(ventana)),
        )
        verifica(
            termino and not hasattr(ventana, "_omite_sincronizacion"),
            "el flag temporal de omisión de sincronización ya no existe (Etapa 5)",
        )

    # --- C) repetición de carpetas: sin duplicados ---
    with _ventana_con() as ventana:
        ventana.carpeta_seleccionada = carpeta_a
        ventana.iniciar_escaneo([carpeta_a, carpeta_a, carpeta_b])
        termino = _esperar_escaneo(ventana)
        verifica(
            termino
            and sorted(_nombres(ventana))
            == ["v01.mp4", "v02.mp4", "v03.mp4", "v04.mkv"],
            "la repetición de carpetas no genera duplicados",
            extra=sorted(_nombres(ventana)),
        )

    # --- D) carpetas inexistentes en la lista se ignoran ---
    with _ventana_con() as ventana:
        ventana.carpeta_seleccionada = carpeta_a
        inexistente = os.path.join(base.name, "no_existe")
        ventana.iniciar_escaneo([carpeta_a, inexistente, carpeta_b])
        termino = _esperar_escaneo(ventana)
        verifica(
            termino
            and sorted(_nombres(ventana))
            == ["v01.mp4", "v02.mp4", "v03.mp4", "v04.mkv"],
            "las carpetas inexistentes de la lista se ignoran",
            extra=sorted(_nombres(ventana)),
        )

    # --- E) lista vacía o inválida: no escanea ---
    with _ventana_con() as ventana:
        ventana.carpeta_seleccionada = carpeta_a
        ventana.iniciar_escaneo([])
        QApplication.processEvents()
        verifica(
            not ventana.gestor.activo
            and ventana.estado_escaneo.text() == "Sin escanear",
            "lista vacía no inicia ningún escaneo",
            extra=ventana.estado_escaneo.text(),
        )
        ventana.iniciar_escaneo([os.path.join(base.name, "no_existe")])
        QApplication.processEvents()
        verifica(
            not ventana.gestor.activo,
            "lista con solo carpetas inexistentes no inicia escaneo",
        )

    # --- F) el catálogo final refleja la unión (recarga tras el multicarpeta) ---
    with _ventana_con() as ventana:
        ventana.carpeta_seleccionada = carpeta_a
        ventana.iniciar_escaneo([carpeta_a, carpeta_b])
        _esperar_escaneo(ventana)
        QApplication.processEvents()
        conn = sqlite3.connect(
            ventana._ruta_db
        )
        try:
            filas = [
                r[0]
                for r in conn.execute(
                    "SELECT nombre FROM videos ORDER BY nombre"
                )
            ]
        finally:
            conn.close()
        verifica(
            filas == ["v01.mp4", "v02.mp4", "v03.mp4", "v04.mkv"],
            "la base refleja la unión de las carpetas escaneadas",
            extra=filas,
        )

    # --- G) transición de modos: A → A+B (multicarpeta) → A ---
    with _ventana_con() as ventana:
        ventana.carpeta_seleccionada = carpeta_a
        ventana.iniciar_escaneo()
        _esperar_escaneo(ventana)
        verifica(
            sorted(_nombres(ventana)) == ["v01.mp4", "v02.mp4"],
            "paso 1: escanear A produce el catálogo de A",
            extra=sorted(_nombres(ventana)),
        )
        ventana.iniciar_escaneo([carpeta_a, carpeta_b])
        _esperar_escaneo(ventana)
        verifica(
            sorted(_nombres(ventana))
            == ["v01.mp4", "v02.mp4", "v03.mp4", "v04.mkv"],
            "paso 2: escanear A+B (selección) produce la unión",
            extra=sorted(_nombres(ventana)),
        )
        ventana.iniciar_escaneo()
        _esperar_escaneo(ventana)
        verifica(
            sorted(_nombres(ventana)) == ["v01.mp4", "v02.mp4"],
            "paso 3: volver a escanear A restaura el catálogo de A",
            extra=sorted(_nombres(ventana)),
        )

    # --- H) alcance efectivo (función pura) ---
    raiz_h = os.path.join(base.name, "H")
    a_h = os.path.join(raiz_h, "A")
    b_h = os.path.join(a_h, "B")
    c_h = os.path.join(b_h, "C")
    x_h = os.path.join(raiz_h, "X")
    y_h = os.path.join(x_h, "Y")
    videos_v = os.path.join(raiz_h, "Videos")
    videos2_v = os.path.join(raiz_h, "Videos2")
    verifica(
        _alcance_efectivo([a_h, b_h], False) == [a_h, b_h],
        "alcance OFF: [A, B en A] conserva ambas",
    )
    verifica(
        _alcance_efectivo([a_h, b_h], True) == [a_h],
        "alcance ON: [A, B en A] se reduce a [A]",
    )
    verifica(
        _alcance_efectivo([b_h, a_h], True) == [a_h],
        "alcance ON independiente del orden: [B, A] -> [A]",
    )
    verifica(
        _alcance_efectivo([a_h, b_h, c_h], True) == [a_h],
        "alcance ON: tres niveles [A, A\\B, A\\B\\C] -> [A]",
    )
    verifica(
        _alcance_efectivo([a_h, b_h, x_h, y_h], True) == [a_h, x_h],
        "alcance ON: dos padres independientes [A, A\\B, X, X\\Y] -> [A, X]",
    )
    verifica(
        _alcance_efectivo([videos_v, videos2_v], True)
        == [videos_v, videos2_v],
        "prefijos engañosos C:\\Videos y C:\\Videos2 no son padre/hija",
    )

    # --- I) escenario A/B real contra SQLite ---
    base_i = tempfile.TemporaryDirectory()
    carpeta_a_i = os.path.join(base_i.name, "A")
    carpeta_b_i = os.path.join(carpeta_a_i, "B")
    os.makedirs(carpeta_b_i)
    _crear_archivo(os.path.join(carpeta_a_i, "a.mp4"))
    _crear_archivo(os.path.join(carpeta_b_i, "b.mp4"))
    try:
        with _ventana_con() as ventana:
            ventana.carpeta_seleccionada = carpeta_a_i
            ventana.incluir_subcarpetas.setChecked(True)
            ventana.iniciar_escaneo([carpeta_a_i, carpeta_b_i])
            _esperar_escaneo(ventana)
            conn = sqlite3.connect(ventana._ruta_db)
            try:
                nombres = sorted(
                    r[0] for r in conn.execute("SELECT nombre FROM videos")
                )
            finally:
                conn.close()
            esperado_on = sorted(["a.mp4", os.path.join("B", "b.mp4")])
            verifica(
                nombres == esperado_on
                and "b.mp4" not in nombres,
                "ON [A, B en A]: el alcance efectivo es solo A y cada archivo físico se procesa una vez",
                extra=nombres,
            )
        with _ventana_con() as ventana:
            ventana.carpeta_seleccionada = carpeta_a_i
            ventana.incluir_subcarpetas.setChecked(False)
            ventana.iniciar_escaneo([carpeta_a_i, carpeta_b_i])
            _esperar_escaneo(ventana)
            conn = sqlite3.connect(ventana._ruta_db)
            try:
                nombres = sorted(
                    r[0] for r in conn.execute("SELECT nombre FROM videos")
                )
            finally:
                conn.close()
            verifica(
                nombres == ["a.mp4", "b.mp4"],
                "OFF [A, B en A]: el alcance efectivo conserva A y B (a.mp4 y b.mp4 una vez cada uno)",
                extra=nombres,
            )
    finally:
        base_i.cleanup()

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
