import os
import py_compile
import sqlite3
import sys
import tempfile
import time

import escanear_videos as escanear_mod
import tareas_videos as tv
from escanear_videos import (
    _metadata_reutilizable,
    _normalizar_ruta_absoluta,
    conectar_bd,
    guardar_marcador,
    guardar_videos,
    listar_registros_por_nombres,
    listar_videos,
    obtener_tamanos_archivos,
)


def _crear_video(ruta, bytes_tamano=100):
    with open(ruta, "wb") as f:
        f.write(b"x" * bytes_tamano)
    return ruta


def _crear_carpeta(nombres):
    temp = tempfile.TemporaryDirectory()
    rutas = {}
    for nombre in nombres:
        rutas[nombre] = _crear_video(os.path.join(temp.name, nombre))
    return temp, rutas


def _registro_bd(nombre, ruta, duracion, ancho, alto, codec, tamano, mtime_ns):
    return {
        "nombre": nombre,
        "ruta": ruta,
        "extension": os.path.splitext(nombre)[1].lower(),
        "fecha_importacion": "f",
        "duracion_segundos": duracion,
        "ancho": ancho,
        "alto": alto,
        "codec_video": codec,
        "cantidad_miniaturas": 1,
        "tamano_bytes": tamano,
        "mtime_ns": mtime_ns,
    }


def _insertar_registro(ruta_db, datos):
    # B8.3: ruta_normalizada es NOT NULL en post-cutover, incluirla si falta
    from rutas import normalizar_ruta_clave
    conn = conectar_bd(ruta_db)
    try:
        ruta_norm = datos.get("ruta_normalizada")
        if not ruta_norm:
            try:
                ruta_norm = normalizar_ruta_clave(datos["ruta"])
            except Exception:
                ruta_norm = datos["ruta"]
        conn.execute(
            """
            INSERT INTO videos (nombre, ruta, ruta_normalizada, extension, fecha_importacion, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas, tamano_bytes, mtime_ns)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datos["nombre"],
                datos["ruta"],
                ruta_norm,
                datos["extension"],
                datos["fecha_importacion"],
                datos["duracion_segundos"],
                datos["ancho"],
                datos["alto"],
                datos["codec_video"],
                datos["cantidad_miniaturas"],
                datos["tamano_bytes"],
                datos["mtime_ns"],
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _leer(ruta_db, nombre):
    conn = conectar_bd(ruta_db)
    try:
        return conn.execute(
            "SELECT id, nombre, ruta, duracion_segundos, ancho, alto, codec_video, tamano_bytes, mtime_ns FROM videos WHERE nombre = ?",
            (nombre,),
        ).fetchone()
    finally:
        conn.close()


def _video_id(ruta_db, nombre):
    for fila in listar_videos(ruta_db):
        if fila[0] == nombre:
            return fila[8]
    return None


def _stat(ruta):
    st = os.stat(ruta)
    return {"ruta": ruta, "tamano_bytes": st.st_size, "mtime_ns": st.st_mtime_ns}


def _crear_bd_antigua(nombre, ruta):
    temp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp.name, "catalogo.db")
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
    conn.execute(
        "INSERT INTO videos (nombre, ruta, extension, fecha_importacion, duracion_segundos) VALUES (?, ?, '.mp4', 'f', 10.0)",
        (nombre, ruta),
    )
    conn.commit()
    conn.close()
    return temp, ruta_db


class _ControladorFfprobe:
    def __init__(self):
        self.n = 0
        self._original = tv.obtener_datos_ffprobe

    def _ffprobe(self, ruta):
        self.n += 1
        return {
            "duracion_segundos": 10.0,
            "ancho": 640,
            "alto": 360,
            "codec_video": "h264",
        }

    def activar(self):
        tv.obtener_datos_ffprobe = self._ffprobe

    def desactivar(self):
        tv.obtener_datos_ffprobe = self._original


def test_01_py_compile():
    ok = True
    detalles = []
    for archivo in [
        "escanear_videos.py",
        "tareas_videos.py",
        "visor_videos.py",
        "prueba_reutilizacion_metadata_b453.py",
    ]:
        try:
            py_compile.compile(archivo, doraise=True)
        except py_compile.PyCompileError as exc:
            ok = False
            detalles.append(f"{archivo}: {exc}")
    return ok, "; ".join(detalles) or "py_compile OK"


def test_02_migracion_bd_antigua():
    temp, ruta_db = _crear_bd_antigua("a.mp4", r"C:\v\a.mp4")
    try:
        conn = conectar_bd(ruta_db)
        try:
            columnas = {fila[1] for fila in conn.execute("PRAGMA table_info(videos)")}
        finally:
            conn.close()
        fila = _leer(ruta_db, "a.mp4")
        ok = (
            "mtime_ns" in columnas
            and fila is not None
            and fila[0] == 1
            and fila[3] == 10.0
        )
        return ok, f"columnas={sorted(columnas)} fila={fila}"
    finally:
        temp.cleanup()


def test_03_migracion_idempotente():
    temp, ruta_db = _crear_bd_antigua("a.mp4", r"C:\v\a.mp4")
    try:
        conn = conectar_bd(ruta_db)
        conn.close()
        conn = conectar_bd(ruta_db)
        try:
            columnas = [fila[1] for fila in conn.execute("PRAGMA table_info(videos)")]
        finally:
            conn.close()
        fila = _leer(ruta_db, "a.mp4")
        ok = (
            columnas.count("mtime_ns") == 1
            and fila is not None
            and fila[0] == 1
            and fila[8] is None
        )
        return ok, f"mtime_ns_x{columnas.count('mtime_ns')} fila={fila}"
    finally:
        temp.cleanup()


def test_04_registro_null_requiere_ffprobe():
    temp, rutas = _crear_carpeta(["a.mp4"])
    temp_bd = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp_bd.name, "c.db")
    try:
        conn = conectar_bd(ruta_db)
        conn.close()
        _insertar_registro(
            ruta_db,
            _registro_bd(
                "a.mp4", rutas["a.mp4"], 10.0, 640, 360, "h264", 100, None
            ),
        )
        control = _ControladorFfprobe()
        control.activar()
        try:
            tarea = tv.TareaFFprobe(
                [rutas["a.mp4"]],
                nombres=["a.mp4"],
                stats={"resultados": [_stat(rutas["a.mp4"])]},
                ruta_db=ruta_db,
            )
            resultado = tarea._trabajo()
        finally:
            control.desactivar()
        ok = control.n == 1 and resultado["con_datos"] == 1
        return ok, f"ffprobe={control.n}"
    finally:
        temp.cleanup()
        temp_bd.cleanup()


def test_05_archivo_identico_cero_ffprobe():
    temp, rutas = _crear_carpeta(["a.mp4"])
    temp_bd = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp_bd.name, "c.db")
    try:
        st = _stat(rutas["a.mp4"])
        conn = conectar_bd(ruta_db)
        conn.close()
        _insertar_registro(
            ruta_db,
            _registro_bd(
                "a.mp4", rutas["a.mp4"], 10.0, 640, 360, "h264",
                st["tamano_bytes"], st["mtime_ns"],
            ),
        )
        control = _ControladorFfprobe()
        control.activar()
        try:
            tarea = tv.TareaFFprobe(
                [rutas["a.mp4"]],
                nombres=["a.mp4"],
                stats={"resultados": [st]},
                ruta_db=ruta_db,
            )
            resultado = tarea._trabajo()
        finally:
            control.desactivar()
        ok = (
            control.n == 0
            and resultado["con_datos"] == 1
            and resultado["resultados"][0]["datos"]["duracion_segundos"] == 10.0
        )
        return ok, f"ffprobe={control.n} datos={resultado['resultados'][0]['datos']}"
    finally:
        temp.cleanup()
        temp_bd.cleanup()


def _probar_cambio(stat_override):
    temp, rutas = _crear_carpeta(["a.mp4"])
    temp_bd = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp_bd.name, "c.db")
    control = _ControladorFfprobe()
    try:
        st = _stat(rutas["a.mp4"])
        conn = conectar_bd(ruta_db)
        conn.close()
        _insertar_registro(
            ruta_db,
            _registro_bd(
                "a.mp4", rutas["a.mp4"], 10.0, 640, 360, "h264",
                st["tamano_bytes"], st["mtime_ns"],
            ),
        )
        st_mod = dict(st)
        st_mod.update(stat_override)
        control.activar()
        tarea = tv.TareaFFprobe(
            [rutas["a.mp4"]],
            nombres=["a.mp4"],
            stats={"resultados": [st_mod]},
            ruta_db=ruta_db,
        )
        tarea._trabajo()
        return control.n
    finally:
        control.desactivar()
        temp.cleanup()
        temp_bd.cleanup()


def test_06_tamano_cambia():
    n = _probar_cambio({"tamano_bytes": 99999})
    return n == 1, f"ffprobe={n}"


def test_07_mtime_cambia():
    n = _probar_cambio({"mtime_ns": 123456789})
    return n == 1, f"ffprobe={n}"


def test_08_ambos_cambian():
    n = _probar_cambio({"tamano_bytes": 111, "mtime_ns": 222})
    return n == 1, f"ffprobe={n}"


def test_09_ruta_cambia():
    temp, rutas = _crear_carpeta(["a.mp4"])
    temp_bd = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp_bd.name, "c.db")
    try:
        st = _stat(rutas["a.mp4"])
        conn = conectar_bd(ruta_db)
        conn.close()
        _insertar_registro(
            ruta_db,
            _registro_bd(
                "a.mp4", r"C:\A\video.mp4", 10.0, 640, 360, "h264",
                st["tamano_bytes"], st["mtime_ns"],
            ),
        )
        control = _ControladorFfprobe()
        control.activar()
        try:
            tarea = tv.TareaFFprobe(
                [rutas["a.mp4"]],
                nombres=["a.mp4"],
                stats={"resultados": [st]},
                ruta_db=ruta_db,
            )
            tarea._trabajo()
        finally:
            control.desactivar()
        ok = control.n == 1
        return ok, f"ffprobe={control.n}"
    finally:
        temp.cleanup()
        temp_bd.cleanup()


def test_10_archivo_nuevo():
    temp, rutas = _crear_carpeta(["a.mp4"])
    temp_bd = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp_bd.name, "c.db")
    try:
        conn = conectar_bd(ruta_db)
        conn.close()
        st = _stat(rutas["a.mp4"])
        control = _ControladorFfprobe()
        control.activar()
        try:
            tarea = tv.TareaFFprobe(
                [rutas["a.mp4"]],
                nombres=["a.mp4"],
                stats={"resultados": [st]},
                ruta_db=ruta_db,
            )
            tarea._trabajo()
        finally:
            control.desactivar()
        ok = control.n == 1
        return ok, f"ffprobe={control.n}"
    finally:
        temp.cleanup()
        temp_bd.cleanup()


def test_11_metadata_invalida():
    temp, rutas = _crear_carpeta(["a.mp4"])
    temp_bd = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp_bd.name, "c.db")
    try:
        st = _stat(rutas["a.mp4"])
        conn = conectar_bd(ruta_db)
        conn.close()
        _insertar_registro(
            ruta_db,
            _registro_bd(
                "a.mp4", rutas["a.mp4"], None, 640, 360, "h264",
                st["tamano_bytes"], st["mtime_ns"],
            ),
        )
        control = _ControladorFfprobe()
        control.activar()
        try:
            tarea = tv.TareaFFprobe(
                [rutas["a.mp4"]],
                nombres=["a.mp4"],
                stats={"resultados": [st]},
                ruta_db=ruta_db,
            )
            tarea._trabajo()
        finally:
            control.desactivar()
        ok = control.n == 1
        return ok, f"ffprobe={control.n}"
    finally:
        temp.cleanup()
        temp_bd.cleanup()


def test_12_metadata_reutilizada_exacta():
    temp, rutas = _crear_carpeta(["a.mp4"])
    temp_bd = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp_bd.name, "c.db")
    try:
        st = _stat(rutas["a.mp4"])
        conn = conectar_bd(ruta_db)
        conn.close()
        _insertar_registro(
            ruta_db,
            _registro_bd(
                "a.mp4", rutas["a.mp4"], 25.5, 1280, 720, "hevc",
                st["tamano_bytes"], st["mtime_ns"],
            ),
        )
        control = _ControladorFfprobe()
        control.activar()
        try:
            tarea = tv.TareaFFprobe(
                [rutas["a.mp4"]],
                nombres=["a.mp4"],
                stats={"resultados": [st]},
                ruta_db=ruta_db,
            )
            resultado = tarea._trabajo()
        finally:
            control.desactivar()
        datos = resultado["resultados"][0]["datos"]
        ok = (
            control.n == 0
            and datos == {
                "duracion_segundos": 25.5,
                "ancho": 1280,
                "alto": 720,
                "codec_video": "hevc",
            }
        )
        return ok, f"ffprobe={control.n} datos={datos}"
    finally:
        temp.cleanup()
        temp_bd.cleanup()


def test_13_persistir_mtime_ns():
    temp, rutas = _crear_carpeta(["a.mp4"])
    temp_bd = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp_bd.name, "c.db")
    try:
        conn = conectar_bd(ruta_db)
        conn.close()
        st = _stat(rutas["a.mp4"])
        guardar_videos(
            [
                _registro_bd(
                    "a.mp4", rutas["a.mp4"], 10.0, 640, 360, "h264",
                    st["tamano_bytes"], st["mtime_ns"],
                )
            ],
            ruta_db,
        )
        fila = _leer(ruta_db, "a.mp4")
        ok = fila is not None and fila[8] == st["mtime_ns"]
        return ok, f"mtime_ns={fila[8] if fila else None} esperado={st['mtime_ns']}"
    finally:
        temp.cleanup()
        temp_bd.cleanup()


def test_14_video_id_preservado():
    temp, rutas = _crear_carpeta(["a.mp4"])
    temp_bd = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp_bd.name, "c.db")
    try:
        conn = conectar_bd(ruta_db)
        conn.close()
        guardar_videos(
            [
                _registro_bd(
                    "a.mp4", rutas["a.mp4"], 10.0, 640, 360, "h264", 100, 1
                )
            ],
            ruta_db,
        )
        id_antes = _video_id(ruta_db, "a.mp4")
        st = _stat(rutas["a.mp4"])
        guardar_videos(
            [
                _registro_bd(
                    "a.mp4", rutas["a.mp4"], 12.0, 640, 360, "h264",
                    st["tamano_bytes"], st["mtime_ns"],
                )
            ],
            ruta_db,
        )
        id_despues = _video_id(ruta_db, "a.mp4")
        ok = id_antes is not None and id_antes == id_despues
        return ok, f"id_antes={id_antes} id_despues={id_despues}"
    finally:
        temp.cleanup()
        temp_bd.cleanup()


def test_15_marcadores_intactos():
    temp, rutas = _crear_carpeta(["a.mp4"])
    temp_bd = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp_bd.name, "c.db")
    try:
        conn = conectar_bd(ruta_db)
        conn.close()
        guardar_videos(
            [
                _registro_bd(
                    "a.mp4", rutas["a.mp4"], 10.0, 640, 360, "h264", 100, 1
                )
            ],
            ruta_db,
        )
        video_id = _video_id(ruta_db, "a.mp4")
        marcador_id = guardar_marcador(video_id, 5.0, ruta_db)
        st = _stat(rutas["a.mp4"])
        guardar_videos(
            [
                _registro_bd(
                    "a.mp4", rutas["a.mp4"], 12.0, 640, 360, "h264",
                    st["tamano_bytes"], st["mtime_ns"],
                )
            ],
            ruta_db,
        )
        conn = conectar_bd(ruta_db)
        try:
            marcadores = conn.execute(
                "SELECT id, video_id, tiempo FROM marcadores_video"
            ).fetchall()
        finally:
            conn.close()
        ok = marcadores == [(marcador_id, video_id, 5.0)]
        return ok, f"marcadores={marcadores}"
    finally:
        temp.cleanup()
        temp_bd.cleanup()


def test_16_lote_mixto():
    temp, rutas = _crear_carpeta(
        ["v00.mp4", "v01.mp4", "v02.mp4", "v03.mp4", "v04.mp4",
         "v05.mp4", "v06.mp4", "v07.mp4", "v08.mp4", "v09.mp4"]
    )
    temp_bd = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp_bd.name, "c.db")
    try:
        conn = conectar_bd(ruta_db)
        conn.close()
        nombres = sorted(rutas.keys())
        stats_items = []
        registros = []
        for indice, nombre in enumerate(nombres):
            st = _stat(rutas[nombre])
            stats_items.append(st)
            tamano = st["tamano_bytes"]
            mtime = st["mtime_ns"]
            if indice == 7:  # tamaño cambiado
                tamano = tamano + 1
            if indice == 8:  # mtime cambiado
                mtime = mtime + 1
            registros.append(
                _registro_bd(
                    nombre, rutas[nombre], 10.0, 640, 360, "h264",
                    tamano, mtime,
                )
            )
        # v09 no se inserta (nuevo)
        for registro in registros[:9]:
            _insertar_registro(ruta_db, registro)
        control = _ControladorFfprobe()
        control.activar()
        try:
            tarea = tv.TareaFFprobe(
                [rutas[n] for n in nombres],
                nombres=nombres,
                stats={"resultados": stats_items},
                ruta_db=ruta_db,
            )
            resultado = tarea._trabajo()
        finally:
            control.desactivar()
        # v00..v06 idénticos (7); v07 tamaño; v08 mtime; v09 nuevo => 3
        ok = (
            control.n == 3
            and resultado["con_datos"] == 10
            and resultado["con_error"] == 0
        )
        return ok, f"ffprobe={control.n} con_datos={resultado['con_datos']}"
    finally:
        temp.cleanup()
        temp_bd.cleanup()


def test_17_lote_121_sin_cambios():
    base = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    base.close()
    _crear_video(base.name, 200)
    temp = tempfile.TemporaryDirectory()
    temp_bd = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp_bd.name, "c.db")
    try:
        nombres = []
        rutas = {}
        for i in range(121):
            nombre = f"v{i:03d}.mp4"
            ruta = os.path.join(temp.name, nombre)
            os.link(base.name, ruta)
            nombres.append(nombre)
            rutas[nombre] = ruta
        conn = conectar_bd(ruta_db)
        conn.close()
        stats_items = []
        registros = []
        for nombre in nombres:
            st = _stat(rutas[nombre])
            stats_items.append(st)
            registros.append(
                _registro_bd(
                    nombre, rutas[nombre], 10.0, 640, 360, "h264",
                    st["tamano_bytes"], st["mtime_ns"],
                )
            )
        guardar_videos(registros, ruta_db)
        control = _ControladorFfprobe()
        control.activar()
        try:
            tarea = tv.TareaFFprobe(
                [rutas[n] for n in nombres],
                nombres=nombres,
                stats={"resultados": stats_items},
                ruta_db=ruta_db,
            )
            resultado = tarea._trabajo()
        finally:
            control.desactivar()
        ok = control.n == 0 and resultado["con_datos"] == 121
        return ok, f"ffprobe={control.n} con_datos={resultado['con_datos']}"
    finally:
        temp.cleanup()
        temp_bd.cleanup()
        if os.path.exists(base.name):
            os.remove(base.name)


def test_18_consulta_por_lote():
    base = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    base.close()
    _crear_video(base.name, 200)
    temp = tempfile.TemporaryDirectory()
    temp_bd = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp_bd.name, "c.db")
    try:
        nombres = []
        rutas = {}
        for i in range(121):
            nombre = f"v{i:03d}.mp4"
            ruta = os.path.join(temp.name, nombre)
            os.link(base.name, ruta)
            nombres.append(nombre)
            rutas[nombre] = ruta
        conn = conectar_bd(ruta_db)
        conn.close()
        guardar_videos(
            [
                _registro_bd(n, rutas[n], 10.0, 640, 360, "h264", 200, 1)
                for n in nombres
            ],
            ruta_db,
        )
        original_connect = sqlite3.connect
        estado = {"selects": 0}

        class _Conexion(sqlite3.Connection):
            def execute(self, sql, *args, **kwargs):
                if (
                    isinstance(sql, str)
                    and sql.lstrip().upper().startswith("SELECT")
                ):
                    estado["selects"] += 1
                return super().execute(sql, *args, **kwargs)

        def _connect(ruta, *args, **kwargs):
            return original_connect(ruta, factory=_Conexion, *args, **kwargs)

        sqlite3.connect = _connect
        try:
            mapa = listar_registros_por_nombres(nombres, ruta_db)
        finally:
            sqlite3.connect = original_connect
        ok = estado["selects"] == 1 and len(mapa) == 121
        return ok, f"selects={estado['selects']} encontrados={len(mapa)}"
    finally:
        temp.cleanup()
        temp_bd.cleanup()
        if os.path.exists(base.name):
            os.remove(base.name)


def test_19_un_stat_por_archivo():
    temp, rutas = _crear_carpeta(["a.mp4", "b.mp4", "c.mp4", "d.mp4", "e.mp4"])
    original_stat = os.stat
    estado = {"n": 0}

    def _stat(ruta, *a, **k):
        estado["n"] += 1
        return original_stat(ruta, *a, **k)

    os.stat = _stat
    try:
        resultado = obtener_tamanos_archivos(sorted(rutas.keys()), temp.name)
    finally:
        os.stat = original_stat
    todos = all(
        item.get("mtime_ns") is not None and item.get("tamano_bytes") is not None
        for item in resultado["resultados"]
    )
    ok = estado["n"] == 5 and todos
    return ok, f"stat={estado['n']} mtime_ok={todos}"


def test_20_normalizacion_ruta():
    a = _normalizar_ruta_absoluta(r"C:\A\Video.mp4")
    b = _normalizar_ruta_absoluta(r"c:\a\video.mp4")
    c = _normalizar_ruta_absoluta(r"D:\B\video.mp4")
    ok = a == b and a != c
    return ok, f"a={a} b={b} c={c}"


def main():
    pruebas = [
        test_01_py_compile,
        test_02_migracion_bd_antigua,
        test_03_migracion_idempotente,
        test_04_registro_null_requiere_ffprobe,
        test_05_archivo_identico_cero_ffprobe,
        test_06_tamano_cambia,
        test_07_mtime_cambia,
        test_08_ambos_cambian,
        test_09_ruta_cambia,
        test_10_archivo_nuevo,
        test_11_metadata_invalida,
        test_12_metadata_reutilizada_exacta,
        test_13_persistir_mtime_ns,
        test_14_video_id_preservado,
        test_15_marcadores_intactos,
        test_16_lote_mixto,
        test_17_lote_121_sin_cambios,
        test_18_consulta_por_lote,
        test_19_un_stat_por_archivo,
        test_20_normalizacion_ruta,
    ]
    resultados = []
    for indice, fn in enumerate(pruebas, start=1):
        try:
            ok, detalle = fn()
        except Exception as exc:
            ok, detalle = False, f"excepcion: {type(exc).__name__}: {exc}"
        resultados.append((indice, ok, detalle))
        print(f"P{indice:02d} {'OK' if ok else 'FALLO'} - {detalle}")
    ok_total = all(ok for _, ok, _ in resultados)
    aprobadas = sum(1 for _, ok, _ in resultados if ok)
    print(f"TOTAL={aprobadas}/{len(pruebas)}")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
