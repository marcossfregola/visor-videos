import os
import py_compile
import sqlite3
import sys
import tempfile
import threading

from PySide6.QtCore import QEventLoop, QThread, QTimer, qInstallMessageHandler
from PySide6.QtWidgets import QApplication

from escanear_videos import (
    combinar_registros_con_tamanos,
    guardar_video,
    guardar_videos,
    obtener_tamanos_archivos,
)
from tareas import Estado, GestorTareas, _GESTORES_ACTIVOS
from tareas_videos import TareaTamanosArchivos
from visor_videos import formatear_tamano

QT_MENSAJES = []


def _mensaje_qt(tipo, contexto, texto):
    QT_MENSAJES.append(str(texto))


qInstallMessageHandler(_mensaje_qt)


def _crear_bd(filas):
    temp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp.name, "catalogo.db")
    conn = sqlite3.connect(ruta_db)
    try:
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
        conn.executemany(
            "INSERT INTO videos (nombre, ruta, extension, fecha_importacion, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            filas,
        )
        conn.commit()
    finally:
        conn.close()
    return temp, ruta_db


def _datos(nombre, ruta="C:\\v\\a.mp4", extension=".mp4", fecha="2026-08-02T00:00:00",
           duracion=None, ancho=None, alto=None, codec=None, miniaturas=None):
    return {
        "nombre": nombre,
        "ruta": ruta,
        "extension": extension,
        "fecha_importacion": fecha,
        "duracion_segundos": duracion,
        "ancho": ancho,
        "alto": alto,
        "codec_video": codec,
        "cantidad_miniaturas": miniaturas,
    }


def _crear_carpeta(archivos):
    temp = tempfile.TemporaryDirectory()
    for nombre, tamano in archivos.items():
        ruta = os.path.join(temp.name, nombre)
        with open(ruta, "wb") as f:
            f.write(b"\x00" * tamano)
    return temp


def _leer_tamano(ruta_db, nombre):
    conn = sqlite3.connect(ruta_db)
    try:
        return conn.execute(
            "SELECT tamano_bytes FROM videos WHERE nombre = ?", (nombre,)
        ).fetchone()[0]
    finally:
        conn.close()


class TareaTamanosConHilo(TareaTamanosArchivos):
    def __init__(self, videos, carpeta):
        super().__init__(videos, carpeta)
        self.identificador = None
        self.en_principal = None

    def _trabajo(self):
        self.identificador = threading.get_ident()
        self.en_principal = QThread.isMainThread()
        return super()._trabajo()


class Captura:
    def __init__(self):
        self.eventos = []
        self.resultado = None
        self.error = None
        self.ids = {}

    def al_inicio(self):
        self.eventos.append("inicio")
        self.ids["inicio"] = (threading.get_ident(), QThread.isMainThread())

    def al_resultado(self, valor):
        self.eventos.append("resultado")
        self.resultado = valor
        self.ids["resultado"] = (threading.get_ident(), QThread.isMainThread())

    def al_error(self, mensaje):
        self.eventos.append("error")
        self.error = mensaje
        self.ids["error"] = (threading.get_ident(), QThread.isMainThread())

    def al_finalizada(self):
        self.eventos.append("finalizada")
        self.ids["finalizada"] = (threading.get_ident(), QThread.isMainThread())


def correr(gestor, tarea, timeout_ms=6000):
    captura = Captura()
    gestor.tarea_iniciada.connect(captura.al_inicio)
    gestor.tarea_resultado.connect(captura.al_resultado)
    gestor.tarea_error.connect(captura.al_error)
    gestor.tarea_finalizada.connect(captura.al_finalizada)

    bucle = QEventLoop()
    flags = {"timeout": False}

    def fin():
        bucle.quit()

    def por_si_acaso():
        flags["timeout"] = True
        bucle.quit()

    gestor.tarea_finalizada.connect(fin)
    QTimer.singleShot(timeout_ms, por_si_acaso)

    ok = gestor.iniciar(tarea)
    if ok:
        bucle.exec()
    gestor.tarea_iniciada.disconnect(captura.al_inicio)
    gestor.tarea_resultado.disconnect(captura.al_resultado)
    gestor.tarea_error.disconnect(captura.al_error)
    gestor.tarea_finalizada.disconnect(captura.al_finalizada)
    gestor.tarea_finalizada.disconnect(fin)
    return captura, flags, ok


def test_01():
    modulos = [
        "tareas.py",
        "escanear_videos.py",
        "rutas.py",
        "tareas_videos.py",
        "visor_videos.py",
        "prueba_tamano_archivo.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    temp = _crear_carpeta({"a.bin": 2048, "b.bin": 1024})
    try:
        r = obtener_tamanos_archivos(["a.bin", "b.bin"], temp.name)
        por_ruta = {os.path.basename(x["ruta"]): x["tamano_bytes"] for x in r["resultados"]}
        ok = (
            r["procesados"] == 2
            and r["con_tamano"] == 2
            and r["sin_tamano"] == 0
            and por_ruta["a.bin"] == 2048
            and por_ruta["b.bin"] == 1024
            and r["rutas"] == [os.path.join(temp.name, n) for n in ("a.bin", "b.bin")]
        )
        return ok, f"procesados={r['procesados']} con={r['con_tamano']} sin={r['sin_tamano']}"
    finally:
        temp.cleanup()


def test_03():
    temp = _crear_carpeta({"a.bin": 2048})
    try:
        r = obtener_tamanos_archivos(["a.bin", "no_existe.bin"], temp.name)
        ok = (
            r["procesados"] == 2
            and r["con_tamano"] == 1
            and r["sin_tamano"] == 1
            and r["resultados"][0]["tamano_bytes"] == 2048
            and r["resultados"][1]["tamano_bytes"] is None
            and os.path.basename(r["resultados"][1]["ruta"]) == "no_existe.bin"
        )
        return (
            ok,
            f"procesados={r['procesados']} con={r['con_tamano']} sin={r['sin_tamano']}",
        )
    finally:
        temp.cleanup()


def test_04():
    temp = _crear_carpeta({"vacio.bin": 0, "lleno.bin": 10})
    try:
        r = obtener_tamanos_archivos(["vacio.bin", "lleno.bin"], temp.name)
        por_ruta = {os.path.basename(x["ruta"]): x["tamano_bytes"] for x in r["resultados"]}
        ok = (
            por_ruta["vacio.bin"] == 0
            and por_ruta["vacio.bin"] is not None
            and por_ruta["lleno.bin"] == 10
            and r["con_tamano"] == 2
            and r["sin_tamano"] == 0
        )
        return ok, f"vacio={por_ruta['vacio.bin']!r} con={r['con_tamano']}"
    finally:
        temp.cleanup()


def test_05():
    temp = _crear_carpeta({"a.bin": 1})
    try:
        errores = []
        try:
            obtener_tamanos_archivos(["a.bin"], "")
        except ValueError:
            errores.append("valor")
        try:
            obtener_tamanos_archivos(["a.bin"], os.path.join(temp.name, "no_carpeta"))
        except FileNotFoundError:
            errores.append("ruta")
        try:
            obtener_tamanos_archivos("a.bin", temp.name)
        except TypeError:
            errores.append("texto")
        try:
            obtener_tamanos_archivos(42, temp.name)
        except TypeError:
            errores.append("iterable")
        ok = errores == ["valor", "ruta", "texto", "iterable"]
        return ok, f"errores={errores}"
    finally:
        temp.cleanup()


def test_06():
    resultado = {
        "resultados": [
            {"ruta": "C:\\v\\a.mp4", "tamano_bytes": 2048},
            {"ruta": "C:\\v\\b.mp4", "tamano_bytes": 0},
            {"ruta": "C:\\v\\c.mp4", "tamano_bytes": None},
            {"ruta": "C:\\v\\d.mp4", "tamano_bytes": "no-entero"},
            "basura",
        ]
    }
    registros = [
        {"nombre": "a.mp4", "ruta": "C:\\v\\a.mp4", "tamano_bytes": "antes"},
        {"nombre": "b.mp4", "ruta": "C:\\v\\b.mp4"},
        {"nombre": "c.mp4", "ruta": "C:\\v\\c.mp4"},
        {"nombre": "d.mp4", "ruta": "C:\\v\\d.mp4"},
        {"nombre": "sin.mp4", "ruta": "C:\\v\\sin.mp4"},
    ]
    combinados = combinar_registros_con_tamanos(registros, resultado)
    por_nombre = {r["nombre"]: r["tamano_bytes"] for r in combinados}
    ok = (
        len(combinados) == 5
        and por_nombre["a.mp4"] == 2048
        and por_nombre["b.mp4"] == 0
        and por_nombre["c.mp4"] is None
        and por_nombre["d.mp4"] is None
        and por_nombre["sin.mp4"] is None
        and registros[0]["tamano_bytes"] == "antes"
        and combinados is not registros
    )
    return ok, f"por_nombre={por_nombre}"


def test_07():
    temp_carpeta = _crear_carpeta({"real.mp4": 3000})
    temp_bd, ruta_db = _crear_bd([])
    try:
        ruta_real = os.path.join(temp_carpeta.name, "real.mp4")
        guardar_video(
            _datos("real.mp4", ruta=ruta_real, duracion=1.0, ancho=1, alto=1, codec="c", miniaturas=1),
            ruta_db,
        )
        tamano = _leer_tamano(ruta_db, "real.mp4")
        ok = tamano is None
        return ok, f"tamano={tamano!r} (ruta existente sin clave)"
    finally:
        temp_carpeta.cleanup()
        temp_bd.cleanup()


def test_08():
    temp_carpeta = _crear_carpeta({"a.mp4": 100, "b.mp4": 200})
    temp_bd, ruta_db = _crear_bd([])
    try:
        guardar_videos(
            [
                _datos("a.mp4", ruta=os.path.join(temp_carpeta.name, "a.mp4")),
                _datos("b.mp4", ruta=os.path.join(temp_carpeta.name, "b.mp4")),
            ],
            ruta_db,
        )
        ok = (
            _leer_tamano(ruta_db, "a.mp4") is None
            and _leer_tamano(ruta_db, "b.mp4") is None
        )
        return ok, f"a={_leer_tamano(ruta_db, 'a.mp4')!r} b={_leer_tamano(ruta_db, 'b.mp4')!r}"
    finally:
        temp_carpeta.cleanup()
        temp_bd.cleanup()


def test_09():
    temp_carpeta = _crear_carpeta({"v.mp4": 1234})
    temp_bd, ruta_db = _crear_bd([])
    original_getsize = os.path.getsize
    original_stat = os.stat
    contadores = {"getsize": 0, "stat_video": 0}
    ruta_video = os.path.join(temp_carpeta.name, "v.mp4")

    def _getsize(ruta):
        contadores["getsize"] += 1
        return original_getsize(ruta)

    def _stat(ruta, *a, **k):
        if os.path.abspath(str(ruta)) == os.path.abspath(ruta_video):
            contadores["stat_video"] += 1
        return original_stat(ruta, *a, **k)

    os.path.getsize = _getsize
    os.stat = _stat
    try:
        guardar_video(
            _datos("v.mp4", ruta=ruta_video, duracion=1.0, ancho=1, alto=1, codec="c", miniaturas=1),
            ruta_db,
        )
        tamano = _leer_tamano(ruta_db, "v.mp4")
    finally:
        os.path.getsize = original_getsize
        os.stat = original_stat
    ok = (
        tamano is None
        and contadores["getsize"] == 0
        and contadores["stat_video"] == 0
    )
    return (
        ok,
        f"getsize={contadores['getsize']} stat_video={contadores['stat_video']} tamano={tamano!r}",
    )


def test_10():
    temp = _crear_carpeta({"x.mp4": 5000})
    id_main = threading.get_ident()
    g = GestorTareas()
    try:
        tarea = TareaTamanosConHilo(["x.mp4", "no_existe.mp4"], temp.name)
        cap, fl, ok = correr(g, tarea)
        r = cap.resultado or {}
        ok = (
            ok
            and not fl["timeout"]
            and cap.eventos == ["inicio", "resultado", "finalizada"]
            and tarea.identificador is not None
            and tarea.identificador != id_main
            and tarea.en_principal is False
            and tarea.videos == ["x.mp4", "no_existe.mp4"]
            and tarea.carpeta == temp.name
            and r.get("procesados") == 2
            and r.get("con_tamano") == 1
            and r.get("sin_tamano") == 1
        )
        return (
            ok,
            f"main={id_main} worker={tarea.identificador} en_principal={tarea.en_principal}",
        )
    finally:
        temp.cleanup()


def test_11():
    temp_carpeta = _crear_carpeta({"p.mp4": 4096})
    temp_bd, ruta_db = _crear_bd([])
    try:
        ruta_real = os.path.join(temp_carpeta.name, "p.mp4")
        resultado = obtener_tamanos_archivos(["p.mp4"], temp_carpeta.name)
        registros = combinar_registros_con_tamanos(
            [_datos("p.mp4", ruta=ruta_real, duracion=1.0, ancho=1, alto=1, codec="c", miniaturas=1)],
            resultado,
        )
        guardar_videos(registros, ruta_db)
        tamano = _leer_tamano(ruta_db, "p.mp4")
        ok = registros[0]["tamano_bytes"] == 4096 and tamano == 4096
        return ok, f"tamano={tamano!r}"
    finally:
        temp_carpeta.cleanup()
        temp_bd.cleanup()


def test_12():
    temp = _crear_carpeta({"e.mp4": 777})
    g = GestorTareas()
    try:
        cap, fl, ok = correr(
            g, TareaTamanosArchivos(["e.mp4", "faltante.mp4"], temp.name)
        )
        r = cap.resultado or {}
        ok = (
            ok
            and not fl["timeout"]
            and cap.eventos == ["inicio", "resultado", "finalizada"]
            and cap.error is None
            and r.get("procesados") == 2
            and r.get("con_tamano") == 1
            and r.get("sin_tamano") == 1
            and len(r.get("resultados") or []) == 2
            and r["resultados"][1]["tamano_bytes"] is None
        )
        return (
            ok,
            f"eventos={cap.eventos} con={r.get('con_tamano')} sin={r.get('sin_tamano')}",
        )
    finally:
        temp.cleanup()


def test_13():
    temp_carpeta = _crear_carpeta({"vacio.mp4": 0, "inexistente.mp4": 0})
    os.remove(os.path.join(temp_carpeta.name, "inexistente.mp4"))
    temp_bd, ruta_db = _crear_bd([])
    try:
        ruta_vacio = os.path.join(temp_carpeta.name, "vacio.mp4")
        ruta_falta = os.path.join(temp_carpeta.name, "inexistente.mp4")
        resultado = obtener_tamanos_archivos(["vacio.mp4", "inexistente.mp4"], temp_carpeta.name)
        registros = combinar_registros_con_tamanos(
            [
                _datos("vacio.mp4", ruta=ruta_vacio),
                _datos("inexistente.mp4", ruta=ruta_falta),
            ],
            resultado,
        )
        guardar_videos(registros, ruta_db)
        cero = _leer_tamano(ruta_db, "vacio.mp4")
        nulo = _leer_tamano(ruta_db, "inexistente.mp4")
        ok = (
            resultado["resultados"][0]["tamano_bytes"] == 0
            and registros[0]["tamano_bytes"] == 0
            and cero == 0
            and resultado["resultados"][1]["tamano_bytes"] is None
            and registros[1]["tamano_bytes"] is None
            and nulo is None
            and cero is not None
        )
        return ok, f"vacio={cero!r} inexistente={nulo!r}"
    finally:
        temp_carpeta.cleanup()
        temp_bd.cleanup()


def test_14():
    casos = {
        0: "0 B",
        1023: "1023 B",
        2048: "2.0 KB",
        5 * 1024 * 1024: "5.0 MB",
        3 * 1024 * 1024 * 1024: "3.0 GB",
        None: "Desconocido",
        "abc": "Desconocido",
        -5: "Desconocido",
        True: "Desconocido",
    }
    ok = all(formatear_tamano(valor) == esperado for valor, esperado in casos.items())
    malos = {
        valor: formatear_tamano(valor)
        for valor, esperado in casos.items()
        if formatear_tamano(valor) != esperado
    }
    return ok, f"malos={malos}"


def test_15():
    bucle = QEventLoop()
    QTimer.singleShot(100, bucle.quit)
    bucle.exec()
    avisos = [m for m in QT_MENSAJES if "Destroyed while thread" in m]
    hilos_python = [
        t for t in threading.enumerate() if t is not threading.main_thread()
    ]
    ok = (
        not avisos
        and len(hilos_python) == 0
        and len(_GESTORES_ACTIVOS) == 0
    )
    return (
        ok,
        f"avisos={len(avisos)} python_threads={len(hilos_python)} "
        f"gestores_activos={len(_GESTORES_ACTIVOS)}",
    )


def main():
    app = QApplication(sys.argv)
    pruebas = [
        test_01,
        test_02,
        test_03,
        test_04,
        test_05,
        test_06,
        test_07,
        test_08,
        test_09,
        test_10,
        test_11,
        test_12,
        test_13,
        test_14,
        test_15,
    ]
    resultados = []
    for i, fn in enumerate(pruebas, start=1):
        try:
            ok, detalle = fn()
        except Exception as exc:
            ok, detalle = False, f"excepcion: {type(exc).__name__}: {exc}"
        resultados.append((i, ok, detalle))
        print(f"T{i:02d} {'OK' if ok else 'FALLO'} - {detalle}")

    ok_total = all(ok for _, ok, _ in resultados)
    aprobadas = sum(1 for _, ok, _ in resultados if ok)
    print(f"TOTAL={aprobadas}/15")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")

    qInstallMessageHandler(None)
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
