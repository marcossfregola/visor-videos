import contextlib
import os
import py_compile
import sqlite3
import sys
import tempfile
import threading
import time

from PySide6.QtCore import QEventLoop, QThread, QTimer
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QLabel

import escanear_videos as escanear_mod
import tareas_videos as tv
import visor_videos
from escanear_videos import (
    CANTIDAD_PREVIEWS,
    calcular_tiempo_preview,
    contar_miniaturas,
    generar_previews_faltantes,
    miniatura_reutilizable,
    previews_existentes,
    previews_faltantes,
    ruta_preview,
)
from tareas import GestorTareas
from tareas_videos import TareaPreviewsProgresivas
from visor_videos import Tarjeta, VisorVideos


def _filas(nombres):
    filas = []
    for i, nombre in enumerate(nombres, start=1):
        filas.append(
            (
                nombre,
                os.path.join("C:\\", nombre),
                os.path.splitext(nombre)[1].lower(),
                "2026-08-03T00:00:00",
                float(i % 5),
                i,
                i,
                "h264",
                i % 3,
            )
        )
    return filas


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


def _carpeta_con(nombres):
    temp = tempfile.TemporaryDirectory()
    for nombre in nombres:
        with open(os.path.join(temp.name, nombre), "w", encoding="utf-8") as f:
            f.write("contenido")
    return temp


@contextlib.contextmanager
def _miniaturas_temporales():
    temp = tempfile.TemporaryDirectory()
    original_escaneo = escanear_mod.ruta_carpeta_miniaturas
    original_visor = visor_videos.ruta_carpeta_miniaturas
    escanear_mod.ruta_carpeta_miniaturas = lambda: temp.name
    visor_videos.ruta_carpeta_miniaturas = lambda: temp.name
    try:
        yield temp.name
    finally:
        escanear_mod.ruta_carpeta_miniaturas = original_escaneo
        visor_videos.ruta_carpeta_miniaturas = original_visor
        temp.cleanup()


def _generar_exitoso(ruta_video, destino, indice=None):
    imagen = QImage(50, 30, QImage.Format_RGB32)
    imagen.fill(QColor("green"))
    if not imagen.save(destino):
        with open(destino, "wb") as f:
            f.write(b"preview")
    return True


def _pixmaps_de(tarjeta):
    return [
        l.pixmap()
        for l in tarjeta.findChildren(QLabel)
        if l.pixmap() is not None and not l.pixmap().isNull()
    ]


def _previews_pixmaps(tarjeta):
    return sum(
        1
        for l in tarjeta._etiquetas_previews
        if l.pixmap() is not None and not l.pixmap().isNull()
    )


def _previews_placeholder(tarjeta):
    return sum(
        1
        for l in tarjeta._etiquetas_previews
        if l.pixmap() is None and l.text() == "Generando preview…"
    )


def _previews_archivos(carpeta):
    return sorted(f for f in os.listdir(carpeta) if "_preview_" in f)


def _procesar(ms):
    bucle = QEventLoop()
    QTimer.singleShot(ms, bucle.quit)
    bucle.exec()


def _esperar(predicado, timeout_ms=8000, paso_ms=20):
    fin = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < fin:
        QApplication.processEvents()
        if predicado():
            return True
        time.sleep(paso_ms / 1000)
    QApplication.processEvents()
    return predicado()


def _crear_png(ruta, ancho=100, alto=60, color="blue"):
    imagen = QImage(ancho, alto, QImage.Format_RGB32)
    imagen.fill(QColor(color))
    return imagen.save(ruta)


def _esperar_previews_ventana(ventana, cantidad_archivos):
    def listo(v=ventana, total=cantidad_archivos):
        return len(_previews_archivos(v.carpeta_miniaturas_test)) >= total

    ventana.carpeta_miniaturas_test = escanear_mod.ruta_carpeta_miniaturas()
    _esperar(listo, timeout_ms=10000)
    _procesar(150)
    return (
        not ventana.gestor_previews.activo
        and not ventana._cola_previews
        and len(_previews_archivos(escanear_mod.ruta_carpeta_miniaturas()))
        >= cantidad_archivos
    )


def _limpiar(ventana):
    if ventana is None:
        return
    if ventana.gestor.hilo is not None:
        ventana.gestor.cerrar()
    ventana.deleteLater()
    for _ in range(5):
        QApplication.processEvents()


def test_01():
    modulos = [
        "escanear_videos.py",
        "tareas_videos.py",
        "visor_videos.py",
        "tareas.py",
        "rutas.py",
        "prueba_previews_progresivas.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    ok = (
        CANTIDAD_PREVIEWS == 3
        and ruta_preview("peli.mp4", 1)
        == os.path.join(escanear_mod.ruta_carpeta_miniaturas(), "peli_preview_01.jpg")
        and ruta_preview("peli.mp4", 2)
        == os.path.join(escanear_mod.ruta_carpeta_miniaturas(), "peli_preview_02.jpg")
        and ruta_preview("peli.mp4", 3)
        == os.path.join(escanear_mod.ruta_carpeta_miniaturas(), "peli_preview_03.jpg")
        and ruta_preview("peli.mp4", 2) != ruta_preview("peli.mp4", 1)
    )
    return (
        ok,
        f"cantidad={CANTIDAD_PREVIEWS} ruta1={ruta_preview('peli.mp4', 1)}",
    )


def test_03():
    with _miniaturas_temporales() as carpeta:
        carpeta_videos = _carpeta_con(["peli.mp4"])
        try:
            for nombre in ["peli_01.jpg", "peli_preview_01.jpg", "peli_preview_02.jpg"]:
                with open(os.path.join(carpeta, nombre), "wb") as f:
                    f.write(b"x")
            ruta_video = os.path.join(carpeta_videos.name, "peli.mp4")
            principal = visor_videos.miniatura_principal
            faltantes = previews_faltantes("peli.mp4")
            existentes = previews_existentes("peli.mp4")
            contadas = contar_miniaturas("peli.mp4")
            reutilizable = miniatura_reutilizable("peli.mp4", ruta_video)
            ok = (
                faltantes == [3]
                and existentes == [
                    os.path.join(carpeta, "peli_preview_01.jpg"),
                    os.path.join(carpeta, "peli_preview_02.jpg"),
                ]
                and contadas == 1
                and reutilizable == os.path.join(carpeta, "peli_01.jpg")
                and principal("peli.mp4") == os.path.join(carpeta, "peli_01.jpg")
            )
        finally:
            carpeta_videos.cleanup()
    return (
        ok,
        f"faltantes={faltantes} existentes={[os.path.basename(p) for p in existentes]} "
        f"contadas={contadas} reutilizable={os.path.basename(reutilizable)}",
    )


def test_04():
    valores = [calcular_tiempo_preview(None), calcular_tiempo_preview(0)]
    normales = [
        calcular_tiempo_preview(100, i) for i in range(1, CANTIDAD_PREVIEWS + 1)
    ]
    crecientes = all(
        normales[i] < normales[i + 1] for i in range(len(normales) - 1)
    )
    acotados = all(0.1 <= v <= 95.0 for v in normales)
    fuera = (
        calcular_tiempo_preview(100, 0)
        == calcular_tiempo_preview(100, 4)
        == calcular_tiempo_preview(100)
    )
    ok = (
        valores == [1.0, 1.0]
        and crecientes
        and acotados
        and fuera
        and normales == [25.0, 50.0, 75.0]
    )
    return (
        ok,
        f"sin_duracion={valores} normales={normales} "
        f"crecientes={crecientes} acotados={acotados} fuera={fuera}",
    )


def test_05():
    with _miniaturas_temporales() as carpeta:
        videos = ["roto.mp4", "falta.mp4"]
        carpeta_videos = _carpeta_con(["roto.mp4"])
        try:
            resumen = generar_previews_faltantes(videos, carpeta_videos.name)
            archivos = sorted(os.listdir(carpeta))
            ok = (
                resumen["procesados"] == 2
                and resumen["con_previews"] == 0
                and resumen["sin_previews"] == 2
                and resumen["generados"] == 0
                and resumen["errores"] >= 3
                and archivos == []
            )
        finally:
            carpeta_videos.cleanup()
    return (
        ok,
        f"procesados={resumen['procesados']} con={resumen['con_previews']} "
        f"sin={resumen['sin_previews']} generados={resumen['generados']} "
        f"errores={resumen['errores']} archivos={archivos}",
    )


def test_06():
    with _miniaturas_temporales() as carpeta:
        carpeta_videos = _carpeta_con(["peli.mp4"])
        original = escanear_mod.generar_preview
        llamadas = {"n": 0}
        try:
            def _generar(ruta_video, destino, indice=None):
                llamadas["n"] += 1
                return _generar_exitoso(ruta_video, destino, indice)

            escanear_mod.generar_preview = _generar
            resumen = generar_previews_faltantes(["peli.mp4"], carpeta_videos.name)
            archivos = sorted(os.listdir(carpeta))
            completos = previews_faltantes("peli.mp4")
        finally:
            escanear_mod.generar_preview = original
            carpeta_videos.cleanup()
        esperados = sorted(
            ["peli_preview_01.jpg", "peli_preview_02.jpg", "peli_preview_03.jpg"]
        )
        ok = (
            llamadas["n"] == 3
            and resumen["generados"] == 3
            and resumen["errores"] == 0
            and resumen["completos"] == 1
            and resumen["con_previews"] == 1
            and archivos == esperados
            and completos == []
        )
    return (
        ok,
        f"llamadas={llamadas['n']} generados={resumen['generados']} "
        f"archivos={archivos} completos={completos}",
    )


def test_07():
    with _miniaturas_temporales() as carpeta:
        carpeta_videos = _carpeta_con(["peli.mp4"])
        original = escanear_mod.generar_preview
        try:
            def _generar(ruta_video, destino, indice=None):
                return _generar_exitoso(ruta_video, destino, indice)

            escanear_mod.generar_preview = _generar
            generar_previews_faltantes(["peli.mp4"], carpeta_videos.name)
            totales = sorted(
                os.path.basename(p) for p in previews_existentes("peli.mp4")
            )
        finally:
            escanear_mod.generar_preview = original

        errores = {"llamadas": 0}

        def _prohibido(ruta_video, destino, indice=None):
            errores["llamadas"] += 1
            raise AssertionError("no debe regenerarse una preview existente")

        escanear_mod.generar_preview = _prohibido
        try:
            segundo = generar_previews_faltantes(["peli.mp4"], carpeta_videos.name)
            tras_segundo = sorted(
                os.path.basename(p) for p in previews_existentes("peli.mp4")
            )
        finally:
            escanear_mod.generar_preview = original
            carpeta_videos.cleanup()
        esperado = [
            "peli_preview_01.jpg",
            "peli_preview_02.jpg",
            "peli_preview_03.jpg",
        ]
        ok = (
            errores["llamadas"] == 0
            and segundo["generados"] == 0
            and segundo["reutilizados"] == 0
            and totales == tras_segundo == esperado
        )
    return (
        ok,
        f"regeneradas={errores['llamadas']} generados={segundo['generados']} "
        f"totales={totales}",
    )


def test_08():
    with _miniaturas_temporales() as carpeta:
        carpeta_videos = _carpeta_con(["peli.mp4"])
        original = escanear_mod.generar_preview
        try:
            def _generar(ruta_video, destino, indice=None):
                return _generar_exitoso(ruta_video, destino, indice)

            escanear_mod.generar_preview = _generar
            with open(os.path.join(carpeta, "peli_preview_01.jpg"), "wb") as f:
                f.write(b"ya")
            resumen = generar_previews_faltantes(["peli.mp4"], carpeta_videos.name)
            generados = _previews_archivos(carpeta)
        finally:
            escanear_mod.generar_preview = original
            carpeta_videos.cleanup()
        ok = (
            resumen["generados"] == 2
            and resumen["reutilizados"] == 0
            and generados
            == ["peli_preview_01.jpg", "peli_preview_02.jpg", "peli_preview_03.jpg"]
        )
    return (
        ok,
        f"generados={resumen['generados']} generados_archivos={generados}",
    )


def test_09():
    with _miniaturas_temporales():
        carpeta_videos = _carpeta_con(["peli.mp4"])
        original = escanear_mod.generar_preview
        info = {"llamadas": 0, "ident": None, "principal": None}
        try:
            def _generar(ruta_video, destino, indice=None):
                info["llamadas"] += 1
                info["ident"] = threading.get_ident()
                info["principal"] = QThread.isMainThread()
                return _generar_exitoso(ruta_video, destino, indice)

            escanear_mod.generar_preview = _generar
            gestor = GestorTareas()
            eventos = []
            resultado = {}
            gestor.tarea_iniciada.connect(lambda: eventos.append("inicio"))
            gestor.tarea_resultado.connect(
                lambda r: (resultado.update(r), eventos.append("resultado"))
            )
            gestor.tarea_finalizada.connect(lambda: eventos.append("finalizada"))
            tarea = TareaPreviewsProgresivas(["peli.mp4"], carpeta_videos.name)
            aceptada = gestor.iniciar(tarea)
            _esperar(lambda g=gestor: not g.activo and g.hilo is None)
            finalizado = not gestor.activo and gestor.hilo is None
            gestor.cerrar()
        finally:
            escanear_mod.generar_preview = original
            carpeta_videos.cleanup()
        ok = (
            aceptada
            and eventos == ["inicio", "resultado", "finalizada"]
            and resultado.get("generados") == 3
            and info["llamadas"] == 3
            and info["principal"] is False
            and finalizado
        )
    return (
        ok,
        f"eventos={eventos} generados={resultado.get('generados')} "
        f"llamadas={info['llamadas']} principal={info['principal']}",
    )


def test_10():
    with _miniaturas_temporales() as carpeta:
        for nombre in ["peli_01.jpg"] + [
            f"peli_preview_{i:02d}.jpg" for i in range(1, 4)
        ]:
            _crear_png(os.path.join(carpeta, nombre))
        temp, ruta_db = _crear_bd(_filas(["peli.mp4", "otra.mp4"]))
        try:
            ventana = VisorVideos(ruta_db=ruta_db)
            _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
            tarjeta = dict(ventana.tarjetas)["peli.mp4"]
            rutas = visor_videos.previews_de("peli.mp4")
            actualizado = tarjeta.actualizar_previews(rutas)
            pixmaps = _pixmaps_de(tarjeta)
            otra = dict(ventana.tarjetas)["otra.mp4"]
            pixmaps_otra = _pixmaps_de(otra)
            previews_peli = _previews_pixmaps(tarjeta)
            previews_otra = _previews_pixmaps(otra)
            ventana.close()
            ventana.gestor.cerrar()
        finally:
            temp.cleanup()
        ok = (
            actualizado
            and len(pixmaps) == 4
            and pixmaps_otra == []
            and previews_peli == 3
            and previews_otra == 0
        )
    return (
        ok,
        f"actualizado={actualizado} pixmaps={len(pixmaps)} "
        f"previews_peli={previews_peli} previews_otra={previews_otra}",
    )


def test_11():
    with _miniaturas_temporales() as carpeta:
        for nombre in ["peli_preview_01.jpg", "peli_preview_02.jpg"]:
            with open(os.path.join(carpeta, nombre), "wb") as f:
                f.write(b"x")
        con = previews_existentes("peli.mp4")
        sin = previews_existentes("otra.mp4")
        ok = (
            len(con) == 2
            and con == [
                os.path.join(carpeta, "peli_preview_01.jpg"),
                os.path.join(carpeta, "peli_preview_02.jpg"),
            ]
            and sin == []
        )
    return ok, f"con={[os.path.basename(p) for p in con]} sin={sin}"


def test_12():
    with _miniaturas_temporales():
        carpeta_videos = _carpeta_con(["peli.mp4"])
        original = escanear_mod.generar_preview
        try:
            def _generar(ruta_video, destino, indice=None):
                return _generar_exitoso(ruta_video, destino, indice)

            escanear_mod.generar_preview = _generar
            resumen = generar_previews_faltantes(["peli.mp4"], carpeta_videos.name)
            claves = sorted(resumen.keys())
            detalle = resumen["resultados"][0]
            claves_detalle = sorted(detalle.keys())
            ok = (
                claves
                == [
                    "completos",
                    "con_previews",
                    "errores",
                    "generados",
                    "procesados",
                    "resultados",
                    "reutilizados",
                    "rutas",
                    "sin_previews",
                ]
                and claves_detalle
                == [
                    "completos",
                    "errores",
                    "generados",
                    "nombre",
                    "previews",
                    "reutilizados",
                    "ruta",
                ]
                and detalle["nombre"] == "peli.mp4"
                and detalle["completos"]
            )
        finally:
            escanear_mod.generar_preview = original
            carpeta_videos.cleanup()
    return (
        ok,
        f"claves={claves} detalle={claves_detalle}",
    )


def test_13():
    with _miniaturas_temporales() as carpeta_min:
        carpeta = _carpeta_con(["a.mp4", "b.mp4", "c.mp4"])
        temp, ruta_db = _crear_bd(_filas(["a.mp4", "b.mp4", "c.mp4"]))
        try:
            def _generar(ruta_video, destino, indice=None):
                return _generar_exitoso(ruta_video, destino, indice)

            original = escanear_mod.generar_preview
            escanear_mod.generar_preview = _generar
            ventana = VisorVideos(ruta_db=ruta_db)
            _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
            ventana.carpeta_seleccionada = carpeta.name
            ventana._programar_previews()
            terminado = _esperar_previews_ventana(ventana, 9)
            generadas = {
                nombre: _previews_pixmaps(tarjeta)
                for nombre, tarjeta in ventana.tarjetas
            }
            archivos = _previews_archivos(carpeta_min)
            ventana.close()
            _limpiar(ventana)
            ok = (
                terminado
                and all(cantidad == 3 for cantidad in generadas.values())
                and len(archivos) == 9
            )
        finally:
            escanear_mod.generar_preview = original
            carpeta.cleanup()
            temp.cleanup()
    return (
        ok,
        f"generadas={generadas} archivos={len(archivos)} terminado={terminado}",
    )


def test_14():
    with _miniaturas_temporales() as carpeta_min:
        carpeta = _carpeta_con(["v01.mp4", "v02.mp4", "v03.mp4", "v04.mp4"])
        temp, ruta_db = _crear_bd(
            _filas(["v01.mp4", "v02.mp4", "v03.mp4", "v04.mp4"])
        )
        try:
            def _generar(ruta_video, destino, indice=None):
                return _generar_exitoso(ruta_video, destino, indice)

            original = escanear_mod.generar_preview
            escanear_mod.generar_preview = _generar
            ventana = VisorVideos(ruta_db=ruta_db)
            _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
            ventana.carpeta_seleccionada = carpeta.name
            ventana._programar_previews()
            terminado = _esperar_previews_ventana(ventana, 12)
            sin_placeholder = all(
                _previews_placeholder(tarjeta) == 0
                for _, tarjeta in ventana.tarjetas
            )
            principal_libre = ventana.gestor.hilo is None
            archivos = _previews_archivos(carpeta_min)
            ventana.close()
            _limpiar(ventana)
            ok = terminado and sin_placeholder and principal_libre and len(archivos) == 12
        finally:
            escanear_mod.generar_preview = original
            carpeta.cleanup()
            temp.cleanup()
    return (
        ok,
        f"terminado={terminado} sin_placeholder={sin_placeholder} "
        f"principal_libre={principal_libre} archivos={len(archivos)}",
    )


def test_15():
    with _miniaturas_temporales() as carpeta_min:
        carpeta = _carpeta_con(["peli.mp4"])
        original = escanear_mod.generar_preview
        info = {"n": 0, "prohibido": False}
        try:
            def _generar(ruta_video, destino, indice=None):
                info["n"] += 1
                return _generar_exitoso(ruta_video, destino, indice)

            escanear_mod.generar_preview = _generar
            with open(os.path.join(carpeta_min, "peli_preview_01.jpg"), "wb") as f:
                f.write(b"1")
            resumen_parcial = generar_previews_faltantes(["peli.mp4"], carpeta.name)
            primer_pase = info["n"]
        finally:
            escanear_mod.generar_preview = original

        try:
            def _prohibido(ruta_video, destino, indice=None):
                info["prohibido"] = True
                raise AssertionError("no debe regenerar")

            escanear_mod.generar_preview = _prohibido
            resumen_final = generar_previews_faltantes(["peli.mp4"], carpeta.name)
        finally:
            escanear_mod.generar_preview = original
            carpeta.cleanup()
        ok = (
            resumen_parcial["generados"] == 2
            and primer_pase == 2
            and resumen_final["generados"] == 0
            and not info["prohibido"]
        )
    return (
        ok,
        f"primer_pase={primer_pase} parcial={resumen_parcial['generados']} "
        f"final={resumen_final['generados']} prohibido={info['prohibido']}",
    )


def test_16():
    with _miniaturas_temporales():
        carpeta = _carpeta_con(["a.mp4"])
        gestor = GestorTareas()
        try:
            tarea_texto = False
            tarea_carpeta = False
            try:
                generar_previews_faltantes("a.mp4", carpeta.name)
            except TypeError:
                tarea_texto = True
            try:
                generar_previews_faltantes(["a.mp4"], "")
            except ValueError:
                tarea_carpeta = True
            tarea = TareaPreviewsProgresivas("a.mp4", carpeta.name)
            aceptada = gestor.iniciar(tarea)
            _esperar(lambda g=gestor: not g.activo and g.hilo is None)
            finalizado = not gestor.activo and gestor.hilo is None
            gestor.cerrar()
        finally:
            carpeta.cleanup()
        ok = tarea_texto and tarea_carpeta and aceptada and finalizado
    return (
        ok,
        f"texto={tarea_texto} carpeta_vacia={tarea_carpeta} "
        f"aceptada={aceptada} finalizado={finalizado}",
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
        test_16,
    ]
    resultados = []
    for i, fn in enumerate(pruebas, start=1):
        try:
            ok, detalle = fn()
        except Exception as exc:
            ok, detalle = False, f"excepcion: {type(exc).__name__}: {exc}"
        resultados.append((i, ok, detalle))
        print(f"P{i:02d} {'OK' if ok else 'FALLO'} - {detalle}")

    ok_total = all(ok for _, ok, _ in resultados)
    aprobadas = sum(1 for _, ok, _ in resultados if ok)
    print(f"TOTAL={aprobadas}/16")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
