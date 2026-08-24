import contextlib
import os
import sqlite3
import sys
import tempfile
import time

from PySide6.QtWidgets import QApplication

import escanear_videos as escanear_mod
import visor_videos
from escanear_videos import detectar_diferencias
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
        # Determinista: esperar cola vacía + gestor inactivo + sin pipeline pendiente (escaneo/sync/recarga)
        cola_vacia = ventana._cola_carpetas_escaneo == []
        gestor_quieto = ventana.gestor.hilo is None and not ventana.gestor.activo
        sin_pipeline = not (
            getattr(ventana, "_escaneo_pendiente", False)
            or getattr(ventana, "_tamanos_pendiente", False)
            or getattr(ventana, "_ffprobe_pendiente", False)
            or getattr(ventana, "_guardado_pendiente", False)
            or getattr(ventana, "_miniaturas_pendiente", False)
            or getattr(ventana, "_actualizar_miniaturas_pendiente", False)
            or getattr(ventana, "_sincronizacion_pendiente", False)
            or getattr(ventana, "_recarga_catalogo_pendiente", False)
            or getattr(ventana, "_pagina_pendiente", False)
        )
        if gestor_quieto and cola_vacia and sin_pipeline:
            # también asegurar carga inicial completada al menos una recarga pasó
            return True
        time.sleep(0.02)
    QApplication.processEvents()
    return False


def _nombres(ventana):
    return [n for n, _ in ventana.tarjetas]


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
    carpeta_a = os.path.join(base.name, "A")
    carpeta_b = os.path.join(base.name, "B")
    os.makedirs(carpeta_a)
    os.makedirs(carpeta_b)
    _crear_archivo(os.path.join(carpeta_a, "v01.mp4"))
    _crear_archivo(os.path.join(carpeta_a, "v02.mp4"))
    _crear_archivo(os.path.join(carpeta_b, "v03.mp4"))
    _crear_archivo(os.path.join(carpeta_b, "v04.mkv"))

    # --- A) función pura: protección en detectar_diferencias ---
    temp_db = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp_db.name, "c.db")
    conn = sqlite3.connect(ruta_db)
    _esquema(conn)
    conn.execute(
        "INSERT INTO videos (nombre, ruta, extension, fecha_importacion) VALUES (?,?,?,?)",
        ("v01.mp4", os.path.join(carpeta_a, "v01.mp4"), ".mp4", "x"),
    )
    conn.execute(
        "INSERT INTO videos (nombre, ruta, extension, fecha_importacion) VALUES (?,?,?,?)",
        ("v03.mp4", os.path.join(carpeta_b, "v03.mp4"), ".mp4", "x"),
    )
    conn.execute(
        "INSERT INTO videos (nombre, ruta, extension, fecha_importacion) VALUES (?,?,?,?)",
        ("v03_eliminado.mp4", os.path.join(carpeta_b, "v03_eliminado.mp4"), ".mp4", "x"),
    )
    conn.commit()
    conn.close()
    # en disco: A tiene v01 (v02 existe), B tiene v03; v03_eliminado no existe en disco
    try:
        sin_proteger = detectar_diferencias(carpeta_a, ruta_db)
        # B8.3A scope-seguro: incluso sin protección explícita, registros de otras carpetas no son ausentes (aislamiento por ruta_normalizada)
        verifica(
            "v03.mp4" not in sin_proteger["ausentes_del_disco"]
            and "v03_eliminado.mp4" not in sin_proteger["ausentes_del_disco"],
            "B8.3A sin protección scope-seguro: otras carpetas no son ausentes",
            extra=sin_proteger["ausentes_del_disco"],
        )
        protegido = detectar_diferencias(
            carpeta_a, ruta_db, carpetas_protegidas=[carpeta_b]
        )
        verifica(
            "v03.mp4" not in protegido["ausentes_del_disco"]
            and "v03_eliminado.mp4" not in protegido["ausentes_del_disco"],
            "con protección, los registros de la carpeta protegida no son ausentes",
            extra=protegido["ausentes_del_disco"],
        )
    finally:
        temp_db.cleanup()

    # --- B) sincronización de una carpeta (sin regresión) ---
    with _ventana_con() as (ventana, ruta_db):
        ventana.carpeta_seleccionada = carpeta_a
        ventana.iniciar_escaneo()
        _esperar_escaneo(ventana)
        verifica(
            sorted(_nombres(ventana)) == ["v01.mp4", "v02.mp4"],
            "escaneo inicial de una carpeta",
        )
        os.remove(os.path.join(carpeta_a, "v02.mp4"))
        ventana.iniciar_escaneo()
        _esperar_escaneo(ventana)
        verifica(
            sorted(_nombres(ventana)) == ["v01.mp4"],
            "la sincronización de una carpeta elimina el archivo ausente",
            extra=sorted(_nombres(ventana)),
        )

    # --- C) multicarpeta: eliminación en una carpeta sin tocar la otra ---
    _crear_archivo(os.path.join(carpeta_a, "v02.mp4"))
    with _ventana_con() as (ventana, ruta_db):
        ventana.carpeta_seleccionada = carpeta_a
        ventana.iniciar_escaneo([carpeta_a, carpeta_b])
        _esperar_escaneo(ventana)
        verifica(
            sorted(_nombres(ventana)) == ["v01.mp4", "v02.mp4", "v03.mp4", "v04.mkv"],
            "escaneo multicarpeta inicial (unión)",
        )
        verifica(
            _nombres_bd(ruta_db) == ["v01.mp4", "v02.mp4", "v03.mp4", "v04.mkv"],
            "BD unión inicial A+B",
            extra=_nombres_bd(ruta_db),
        )
        os.remove(os.path.join(carpeta_a, "v02.mp4"))
        ventana.iniciar_escaneo([carpeta_a, carpeta_b])
        _esperar_escaneo(ventana)
        verifica(
            sorted(_nombres(ventana)) == ["v01.mp4", "v03.mp4", "v04.mkv"],
            "el ausente de una carpeta del conjunto se elimina y se conserva la otra carpeta",
            extra=sorted(_nombres(ventana)),
        )
        verifica(
            _nombres_bd(ruta_db) == ["v01.mp4", "v03.mp4", "v04.mkv"],
            "la base refleja la sincronización multicarpeta sin pérdida de la otra carpeta",
        )

    # --- D) el flag temporal _omite_sincronizacion desapareció ---
    with _ventana_con() as (ventana, ruta_db):
        ventana.carpeta_seleccionada = carpeta_a
        ventana.iniciar_escaneo([carpeta_a, carpeta_b])
        _esperar_escaneo(ventana)
        verifica(
            not hasattr(ventana, "_omite_sincronizacion"),
            "no existe el atributo temporal _omite_sincronizacion",
        )
        verifica(
            carpeta_a in ventana.carpetas_escaneadas
            and carpeta_b in ventana.carpetas_escaneadas,
            "con la sincronización activa, cada carpeta se marca como escaneada",
        )

    # --- E) transición de modos: A -> A+B -> A ---
    _crear_archivo(os.path.join(carpeta_a, "v02.mp4"))
    with _ventana_con() as (ventana, ruta_db):
        ventana.carpeta_seleccionada = carpeta_a
        ventana.iniciar_escaneo()
        _esperar_escaneo(ventana)
        verifica(
            sorted(_nombres(ventana)) == ["v01.mp4", "v02.mp4"],
            "transición paso 1: solo A",
        )
        ventana.iniciar_escaneo([carpeta_a, carpeta_b])
        _esperar_escaneo(ventana)
        verifica(
            sorted(_nombres(ventana)) == ["v01.mp4", "v02.mp4", "v03.mp4", "v04.mkv"],
            "transición paso 2: A+B",
        )
        verifica(
            _nombres_bd(ruta_db) == ["v01.mp4", "v02.mp4", "v03.mp4", "v04.mkv"],
            "transición paso 2 BD unión",
            extra=_nombres_bd(ruta_db),
        )
        ventana.iniciar_escaneo()
        _esperar_escaneo(ventana)
        verifica(
            sorted(_nombres(ventana)) == ["v01.mp4", "v02.mp4"],
            "transición paso 3: volver a A restaura el catálogo",
            extra=sorted(_nombres(ventana)),
        )

    # --- F) transición explícita contra SQLite: [A] -> [A,B] -> [A] ---
    base_f = tempfile.TemporaryDirectory()
    carpeta_a_f = os.path.join(base_f.name, "A")
    carpeta_b_f = os.path.join(base_f.name, "B")
    os.makedirs(carpeta_a_f)
    os.makedirs(carpeta_b_f)
    _crear_archivo(os.path.join(carpeta_a_f, "a.mp4"))
    _crear_archivo(os.path.join(carpeta_b_f, "b.mp4"))
    try:
        with _ventana_con() as (ventana, ruta_db):
            ventana.carpeta_seleccionada = carpeta_a_f
            ventana.iniciar_escaneo()
            _esperar_escaneo(ventana)
            verifica(
                _nombres_bd(ruta_db) == ["a.mp4"],
                "fase [A] -> BD exactamente {a.mp4}",
                extra=_nombres_bd(ruta_db),
            )
            ventana.iniciar_escaneo([carpeta_a_f, carpeta_b_f])
            _esperar_escaneo(ventana)
            verifica(
                _nombres_bd(ruta_db) == ["a.mp4", "b.mp4"],
                "fase [A,B] -> BD exactamente {a.mp4, b.mp4}",
                extra=_nombres_bd(ruta_db),
            )
            ventana.iniciar_escaneo()
            _esperar_escaneo(ventana)
            verifica(
                _nombres_bd(ruta_db) == ["a.mp4"],
                "fase [A] final -> BD exactamente {a.mp4} (b desaparece)",
                extra=_nombres_bd(ruta_db),
            )
            verifica(
                sorted(_nombres(ventana)) == ["a.mp4"],
                "fase [A] final vista exactamente {a.mp4}",
                extra=sorted(_nombres(ventana)),
            )
    finally:
        base_f.cleanup()

    # --- G) carpetas solapadas: A padre, B subcarpeta contenida en A ---
    base_g = tempfile.TemporaryDirectory()
    carpeta_a_g = os.path.join(base_g.name, "A")
    carpeta_b_g = os.path.join(carpeta_a_g, "B")
    os.makedirs(carpeta_b_g)
    _crear_archivo(os.path.join(carpeta_a_g, "a.mp4"))
    _crear_archivo(os.path.join(carpeta_b_g, "b.mp4"))
    try:
        with _ventana_con() as (ventana, ruta_db):
            ventana.carpeta_seleccionada = carpeta_a_g
            ventana.incluir_subcarpetas.setChecked(False)
            ventana.iniciar_escaneo([carpeta_a_g, carpeta_b_g])
            _esperar_escaneo(ventana)
            verifica(
                _nombres_bd(ruta_db) == ["a.mp4", "b.mp4"],
                "solapadas A>B: la unión sin duplicados ni cruces",
                extra=_nombres_bd(ruta_db),
            )
            verifica(
                sorted(_nombres(ventana)) == ["a.mp4", "b.mp4"],
                "solapadas vista unión",
                extra=sorted(_nombres(ventana)),
            )
            os.remove(os.path.join(carpeta_b_g, "b.mp4"))
            ventana.iniciar_escaneo([carpeta_a_g, carpeta_b_g])
            _esperar_escaneo(ventana)
            verifica(
                _nombres_bd(ruta_db) == ["a.mp4"],
                "solapadas A>B: el archivo borrado en B desaparece y A se conserva",
                extra=_nombres_bd(ruta_db),
            )
            verifica(
                sorted(_nombres(ventana)) == ["a.mp4"],
                "solapadas vista tras borrar B",
                extra=sorted(_nombres(ventana)),
            )
    finally:
        base_g.cleanup()

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
