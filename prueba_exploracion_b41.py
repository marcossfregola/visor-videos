import contextlib
import json
import os
import py_compile
import sqlite3
import sys
import tempfile
import time

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPixmap
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

import escanear_videos as escanear_mod
import visor_videos
from exploracion_temporal import (
    normalizar_posicion,
    posicion_a_tiempo,
    preview_mas_cercana,
    tiempo_a_posicion,
)
from scrubber import FranjaExploracion, MiniaturaMarcador
from visor_videos import Tarjeta, VisorVideos

_CONFIG_TEMPORAL = tempfile.TemporaryDirectory()
os.environ["VISOR_CONFIG"] = os.path.join(_CONFIG_TEMPORAL.name, "configuracion.json")

_CANTIDAD_ORIGINAL_PREVIEWS = escanear_mod.CANTIDAD_PREVIEWS


def _filas(nombres, duraciones, carpeta="C:\\"):
    filas = []
    for indice, (nombre, duracion) in enumerate(
        zip(nombres, duraciones), start=1
    ):
        filas.append(
            (
                nombre,
                os.path.join(carpeta, nombre),
                os.path.splitext(nombre)[1].lower(),
                "2026-08-03T00:00:00",
                float(duracion),
                1920,
                1080,
                "h264",
                indice % 3,
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


def _crear_previews(carpeta, prefijo, cantidad, ancho=80, alto=45):
    creadas = []
    for indice in range(1, cantidad + 1):
        ruta = os.path.join(carpeta, f"{prefijo}_preview_{indice:02d}.jpg")
        imagen = QImage(ancho, alto, QImage.Format_RGB32)
        imagen.fill(QColor(30 + indice * 20, 60, 120))
        imagen.save(ruta, "JPEG")
        creadas.append(ruta)
    return creadas


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


def _esperar(predicado, timeout_ms=8000, paso_ms=20):
    fin = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < fin:
        QApplication.processEvents()
        if predicado():
            return True
        time.sleep(paso_ms / 1000)
    QApplication.processEvents()
    return predicado()


@contextlib.contextmanager
def _config_con_previews(cantidad):
    ruta = os.environ["VISOR_CONFIG"]
    original = None
    if os.path.isfile(ruta):
        with open(ruta, encoding="utf-8") as f:
            original = f.read()
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(json.dumps({"cantidad_previews": cantidad}))
    try:
        yield
    finally:
        if original is None:
            if os.path.isfile(ruta):
                os.remove(ruta)
        else:
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(original)


def _mouse_move(widget, x):
    return _mouse_move_en(widget, x, widget.height() // 2)


def _mouse_move_en(widget, x, y):
    evento = QMouseEvent(
        QEvent.MouseMove,
        QPointF(float(x), float(y)),
        Qt.NoButton,
        Qt.NoButton,
        Qt.NoModifier,
    )
    QApplication.sendEvent(widget, evento)


def _mouse_press(widget, x):
    evento = QMouseEvent(
        QEvent.MouseButtonPress,
        QPointF(float(x), 5.0),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    QApplication.sendEvent(widget, evento)


def _clic_derecho(widget, x=5):
    evento = QMouseEvent(
        QEvent.MouseButtonPress,
        QPointF(float(x), 5.0),
        Qt.RightButton,
        Qt.RightButton,
        Qt.NoModifier,
    )
    QApplication.sendEvent(widget, evento)


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
        "exploracion_temporal.py",
        "scrubber.py",
        "visor_videos.py",
        "prueba_exploracion_b41.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    casos = [
        (0, 100, 50, 0.0),
        (100, 100, 50, 50.0),
        (50, 100, 50, 25.0),
        (25, 200, 80, 10.0),
        (0, 320, 100, 0.0),
    ]
    for posicion, ancho, duracion, esperado in casos:
        valor = posicion_a_tiempo(posicion, ancho, duracion)
        if valor != esperado:
            return False, f"x={posicion} ancho={ancho} dur={duracion}: {valor} != {esperado}"
    return True, "x=0->0, x=ancho->duracion, punto medio y proporcionales OK"


def test_03():
    fuera = [
        (posicion_a_tiempo(-5, 100, 50), 0.0),
        (posicion_a_tiempo(150, 100, 50), 50.0),
        (posicion_a_tiempo(0, 0, 50), None),
        (posicion_a_tiempo(10, None, 50), None),
        (posicion_a_tiempo(10, "100", 50), None),
        (posicion_a_tiempo(10, 100, 0), None),
        (posicion_a_tiempo(10, 100, None), None),
        (posicion_a_tiempo(10, 100, -1), None),
        (posicion_a_tiempo("5", 100, 50), None),
        (posicion_a_tiempo(None, 100, 50), None),
    ]
    for valor, esperado in fuera:
        if valor != esperado:
            return False, f"{valor} != {esperado}"
    return True, "clamp fuera de rango y anchos/duraciones invalidos OK"


def test_04():
    casos = [
        (normalizar_posicion(-3, 100), 0.0),
        (normalizar_posicion(0, 100), 0.0),
        (normalizar_posicion(50, 100), 50.0),
        (normalizar_posicion(100, 100), 100.0),
        (normalizar_posicion(130, 100), 100.0),
        (normalizar_posicion(10, 0), None),
        (normalizar_posicion(None, 100), None),
    ]
    for valor, esperado in casos:
        if valor != esperado:
            return False, f"{valor} != {esperado}"
    return True, "normalizacion_posicion OK"


def test_05():
    instantes = [25.0, 50.0, 75.0]
    casos = [
        (preview_mas_cercana(instantes, 60.0), 1),
        (preview_mas_cercana(instantes, 20.0), 0),
        (preview_mas_cercana(instantes, 80.0), 2),
        (preview_mas_cercana(instantes, 25.0), 0),
        (preview_mas_cercana(instantes, 75.0), 2),
        (preview_mas_cercana(instantes, 37.5), 0),
        (preview_mas_cercana([25.0, None, 75.0], 70.0), 2),
        (preview_mas_cercana([], 10.0), None),
        (preview_mas_cercana([None, None], 10.0), None),
        (preview_mas_cercana(instantes, None), None),
    ]
    for valor, esperado in casos:
        if valor != esperado:
            return False, f"{valor} != {esperado}"
    return True, "seleccion anterior/posterior/mas cercana, empate y ausencia OK"


def _franja_mostrada(duracion):
    contenedor = QWidget()
    contenedor.setLayout(QVBoxLayout())
    franja = FranjaExploracion()
    contenedor.layout().addWidget(franja)
    contenedor.resize(220, 60)
    contenedor.show()
    franja.set_duracion(duracion)
    _esperar(lambda f=franja: f.width() > 0)
    return contenedor, franja


def test_06():
    contenedor, franja = _franja_mostrada(100.0)
    try:
        recibidos = []
        franja.instante_seleccionado.connect(recibidos.append)
        ancho = franja.width()
        _mouse_move(franja, 0)
        v0 = franja.instante()
        _mouse_move(franja, ancho)
        v_fin = franja.instante()
        _mouse_move(franja, ancho / 2)
        v_medio = franja.instante()
        ok = (
            v0 == 0.0
            and v_fin == 100.0
            and abs(v_medio - 50.0) < 1e-6
            and len(recibidos) == 3
            and recibidos[0] == 0.0
            and recibidos[1] == 100.0
        )
    finally:
        contenedor.close()
    return ok, f"v0={v0} v_fin={v_fin} v_medio={v_medio} señal={len(recibidos)}"


def test_07():
    contenedor, franja = _franja_mostrada(100.0)
    try:
        franja.set_instante(25.0)
        ok_marcador = franja.instante() == 25.0
        _mouse_move(franja, franja.width() * 0.6)
        ok_movimiento = abs(franja.instante() - 60.0) < 1e-6
        grab = franja.grab()
        ok_render = not grab.isNull()
    finally:
        contenedor.close()
    return (
        ok_marcador and ok_movimiento and ok_render,
        f"marcador={ok_marcador} movimiento={ok_movimiento} render={ok_render}",
    )


def test_08():
    for duracion in (0, None, -1):
        contenedor, franja = _franja_mostrada(duracion)
        try:
            recibidos = []
            franja.instante_seleccionado.connect(recibidos.append)
            _mouse_move(franja, franja.width() // 2)
            ok = franja.instante() is None and recibidos == []
        finally:
            contenedor.close()
        if not ok:
            return False, f"duracion={duracion!r}: instante={franja.instante()} recibidos={recibidos}"
    return True, "duracion invalida: sin señal y sin instante"


def _ventana_con_previews(nombres, duraciones, carpeta_min, cantidad=3):
    for nombre, duracion in zip(nombres, duraciones):
        _crear_previews(carpeta_min, os.path.splitext(nombre)[0], cantidad)
    temp, ruta_db = _crear_bd(_filas(nombres, duraciones))
    ventana = VisorVideos(ruta_db=ruta_db)
    ventana.resize(900, 600)
    ventana.show()
    _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
    _esperar(lambda: ventana.contenedor.findChildren(Tarjeta))
    return temp, ventana


def test_09():
    escanear_mod.configurar_cantidad_previews(3)
    try:
        with _miniaturas_temporales() as carpeta_min:
            temp, ventana = _ventana_con_previews(
                ["a.mp4", "b.mp4"], [100.0, 80.0], carpeta_min
            )
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                ok = (
                    not tarjeta._expandida
                    and tarjeta._contenedor_exploracion.isHidden()
                    and tarjeta._boton_expandir.text() == "Expandir"
                )
                tarjeta.expandir()
                ok = ok and tarjeta._expandida
                ok = ok and not tarjeta._contenedor_exploracion.isHidden()
                ok = ok and tarjeta._boton_expandir.text() == "Colapsar"
                ok = ok and tarjeta._franja.duracion() == 100.0
                ok = ok and tarjeta._franja.instante() == 0.0
                tarjeta.colapsar()
                ok = ok and not tarjeta._expandida
                ok = ok and tarjeta._contenedor_exploracion.isHidden()
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return ok, "colapsada por defecto, expandir muestra, colapsar oculta"
    finally:
        escanear_mod.configurar_cantidad_previews(_CANTIDAD_ORIGINAL_PREVIEWS)


def test_10():
    escanear_mod.configurar_cantidad_previews(3)
    try:
        with _miniaturas_temporales() as carpeta_min:
            temp, ventana = _ventana_con_previews(
                ["a.mp4", "b.mp4"], [100.0, 80.0], carpeta_min
            )
            try:
                ta = dict(ventana.tarjetas)["a.mp4"]
                tb = dict(ventana.tarjetas)["b.mp4"]
                ta._boton_expandir.click()
                ok = ta._expandida and not tb._expandida
                tb.expandir()
                ok = ok and tb._expandida and not ta._expandida
                ok = ok and ta._contenedor_exploracion.isHidden()
                ok = ok and not tb._contenedor_exploracion.isHidden()
                ok = ok and dict(ventana.tarjetas)["a.mp4"] is ta
                ok = ok and dict(ventana.tarjetas)["b.mp4"] is tb
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return ok, "solo una tarjeta expandida, sin reconstruir tarjetas"
    finally:
        escanear_mod.configurar_cantidad_previews(_CANTIDAD_ORIGINAL_PREVIEWS)


def test_11():
    escanear_mod.configurar_cantidad_previews(3)
    try:
        with _miniaturas_temporales() as carpeta_min:
            temp, ventana = _ventana_con_previews(
                ["a.mp4"], [100.0], carpeta_min
            )
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                tarjeta.expandir()
                _esperar(lambda: tarjeta._franja.width() > 0)
                ancho = tarjeta._franja.width()
                disponibles = tarjeta._previews_exploracion
                if len(disponibles) != 3:
                    return False, f"previews_disponibles={len(disponibles)}"
                _mouse_move(tarjeta._franja, tarjeta._franja.width() * 0.60)
                idx60 = preview_mas_cercana(
                    [d["instante"] for d in disponibles],
                    tarjeta._franja.instante(),
                )
                pix60 = tarjeta._imagen_exploracion.pixmap()
                ok60 = (
                    pix60 is not None
                    and not pix60.isNull()
                    and pix60.cacheKey()
                    == disponibles[idx60]["pixmap_escalado"].cacheKey()
                )
                _mouse_move(tarjeta._franja, tarjeta._franja.width() * 0.20)
                idx20 = preview_mas_cercana(
                    [d["instante"] for d in disponibles],
                    tarjeta._franja.instante(),
                )
                pix20 = tarjeta._imagen_exploracion.pixmap()
                ok20 = (
                    pix20 is not None
                    and not pix20.isNull()
                    and pix20.cacheKey()
                    == disponibles[idx20]["pixmap_escalado"].cacheKey()
                )
                texto = tarjeta._franja.texto_tiempo()
                ok_tiempo = texto.startswith("0:")
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return (
                ok60 and ok20 and ok_tiempo,
                f"idx60={idx60} idx20={idx20} tiempo={texto}",
            )
    finally:
        escanear_mod.configurar_cantidad_previews(_CANTIDAD_ORIGINAL_PREVIEWS)


def test_12():
    escanear_mod.configurar_cantidad_previews(3)
    try:
        with _miniaturas_temporales() as carpeta_min:
            temp, ventana = _ventana_con_previews(
                ["a.mp4"], [100.0], carpeta_min
            )
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                tarjeta.expandir()
                _esperar(lambda: tarjeta._franja.width() > 0)

                llamadas_ffmpeg = {"n": 0}

                def _prohibido_ffmpeg(*_args, **_kwargs):
                    llamadas_ffmpeg["n"] += 1
                    raise AssertionError("no debe invocarse FFmpeg")

                original_generar = escanear_mod.generar_preview
                escanear_mod.generar_preview = _prohibido_ffmpeg

                class QPixmapContador(QPixmap):
                    construcciones = 0

                    def __init__(self, *args, **kwargs):
                        type(self).construcciones += 1
                        super().__init__(*args, **kwargs)

                original_qpixmap = visor_videos.QPixmap
                visor_videos.QPixmap = QPixmapContador
                try:
                    base = QPixmapContador.construcciones
                    ancho = tarjeta._franja.width()
                    for fraccion in (0.1, 0.3, 0.5, 0.7, 0.9):
                        _mouse_move(tarjeta._franja, int(ancho * fraccion))
                    QApplication.processEvents()
                    ok_ffmpeg = llamadas_ffmpeg["n"] == 0
                    ok_qpixmap = QPixmapContador.construcciones == base
                    identidad = (
                        tarjeta._imagen_exploracion.pixmap()
                        is not None
                        and not tarjeta._imagen_exploracion.pixmap().isNull()
                    )
                finally:
                    visor_videos.QPixmap = original_qpixmap
                    escanear_mod.generar_preview = original_generar
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return (
                ok_ffmpeg and ok_qpixmap and identidad,
                f"ffmpeg={llamadas_ffmpeg['n']} qpixmap_nuevas={QPixmapContador.construcciones - base} identidad={identidad}",
            )
    finally:
        escanear_mod.configurar_cantidad_previews(_CANTIDAD_ORIGINAL_PREVIEWS)


def test_13():
    escanear_mod.configurar_cantidad_previews(3)
    try:
        with _miniaturas_temporales():
            temp, ruta_db = _crear_bd(_filas(["sin_preview.mp4"], [100.0]))
            ventana = VisorVideos(ruta_db=ruta_db)
            ventana.resize(900, 600)
            ventana.show()
            _esperar(
                lambda v=ventana: v._carga_completada and v.gestor.hilo is None
            )
            _esperar(lambda: ventana.contenedor.findChildren(Tarjeta))
            try:
                tarjeta = dict(ventana.tarjetas)["sin_preview.mp4"]
                tarjeta.expandir()
                _esperar(lambda: tarjeta._franja.width() > 0)
                ok_franja = tarjeta._franja.duracion() == 100.0
                ok_vacio = tarjeta._previews_exploracion == []
                _mouse_move(tarjeta._franja, tarjeta._franja.width() // 2)
                ok_sin_fallo = True
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return (
                ok_franja and ok_vacio and ok_sin_fallo,
                f"franja={ok_franja} vacio={ok_vacio}",
            )
    finally:
        escanear_mod.configurar_cantidad_previews(_CANTIDAD_ORIGINAL_PREVIEWS)


def test_14():
    escanear_mod.configurar_cantidad_previews(3)
    try:
        with _miniaturas_temporales() as carpeta_min:
            temp, ventana = _ventana_con_previews(
                ["a.mp4", "b.mp4"], [100.0, 80.0], carpeta_min
            )
            abiertos = []
            original_abrir = visor_videos.abrir_video_con_aplicacion_predeterminada

            def _abrir(nombre, carpeta):
                abiertos.append(nombre)

            visor_videos.abrir_video_con_aplicacion_predeterminada = _abrir
            try:
                ta = dict(ventana.tarjetas)["a.mp4"]
                tb = dict(ventana.tarjetas)["b.mp4"]
                _mouse_press(ta, 5)
                ok_seleccion = "a.mp4" in ventana._nombres_seleccionados
                tb.expandir()
                ok_seleccion_conservada = (
                    "a.mp4" in ventana._nombres_seleccionados
                )
                evento_doble = QMouseEvent(
                    QEvent.MouseButtonDblClick,
                    QPointF(5.0, 5.0),
                    Qt.LeftButton,
                    Qt.LeftButton,
                    Qt.NoModifier,
                )
                QApplication.sendEvent(ta, evento_doble)
                ok_doble = abiertos == ["a.mp4"]
            finally:
                visor_videos.abrir_video_con_aplicacion_predeterminada = original_abrir
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return (
                ok_seleccion and ok_seleccion_conservada and ok_doble,
                f"seleccion={ok_seleccion} conservada={ok_seleccion_conservada} doble={abiertos}",
            )
    finally:
        escanear_mod.configurar_cantidad_previews(_CANTIDAD_ORIGINAL_PREVIEWS)


def test_15():
    escanear_mod.configurar_cantidad_previews(3)
    try:
        with _miniaturas_temporales() as carpeta_min:
            temp, ventana = _ventana_con_previews(
                ["a.mp4"], [100.0], carpeta_min
            )
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                etiqueta = tarjeta._etiquetas_previews[0]
                QApplication.sendEvent(etiqueta, QEvent(QEvent.Enter))
                QApplication.processEvents()
                ok_entrar = (
                    ventana._vista_pendiente is etiqueta._pixmap_original
                    and ventana._timer_vista_mostrar.isActive()
                )
                QApplication.sendEvent(etiqueta, QEvent(QEvent.Leave))
                QApplication.processEvents()
                ok_salir = ventana._vista_pendiente is None
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return (
                ok_entrar and ok_salir,
                f"entrar={ok_entrar} salir={ok_salir}",
            )
    finally:
        escanear_mod.configurar_cantidad_previews(_CANTIDAD_ORIGINAL_PREVIEWS)


def test_16():
    contenedor, franja = _franja_mostrada(100.0)
    try:
        recibidos = []
        franja.instante_seleccionado.connect(recibidos.append)
        ancho = franja.width()
        alto = franja.height()
        _mouse_move(franja, 0)
        v_izq = franja.instante()
        _mouse_move(franja, ancho)
        v_der = franja.instante()
        _mouse_move(franja, ancho / 2)
        v_centro = franja.instante()
        _mouse_move(franja, -50)
        v_clamp_izq = franja.instante()
        _mouse_move(franja, ancho + 50)
        v_clamp_der = franja.instante()
        _mouse_move_en(franja, ancho / 4, 4)
        v_arriba = franja.instante()
        _mouse_move_en(franja, ancho / 4, alto - 4)
        v_abajo = franja.instante()
        ok = (
            v_izq == 0.0
            and v_der == 100.0
            and abs(v_centro - 50.0) < 1e-6
            and v_clamp_izq == 0.0
            and v_clamp_der == 100.0
            and abs(v_arriba - 25.0) < 1e-6
            and abs(v_abajo - 25.0) < 1e-6
            and len(recibidos) == 7
        )
    finally:
        contenedor.close()
    return (
        ok,
        f"izq={v_izq} der={v_der} centro={v_centro} "
        f"clamp=({v_clamp_izq},{v_clamp_der}) vert=({v_arriba},{v_abajo})",
    )


def test_17():
    escanear_mod.configurar_cantidad_previews(3)
    try:
        with _miniaturas_temporales() as carpeta_min:
            temp, ventana = _ventana_con_previews(
                ["a.mp4"], [100.0], carpeta_min
            )
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                tarjeta.expandir()
                _esperar(lambda: tarjeta._franja.width() > 0)
                _esperar(lambda: not tarjeta._imagen_exploracion.isHidden())
                superficie = tarjeta._franja
                img = tarjeta._imagen_exploracion
                ancho_sup = superficie.width()
                ancho_img = img.width()
                disponibles = tarjeta._previews_exploracion

                _mouse_move(superficie, 0)
                ok_izq = img.x() >= 0 and img.x() == 0
                _mouse_move(superficie, ancho_sup)
                ok_der = (img.x() + img.width()) <= ancho_sup
                _mouse_move(superficie, ancho_sup / 2)
                ok_centro = abs((img.x() + ancho_img / 2) - ancho_sup / 2) <= 2

                idx = preview_mas_cercana(
                    [d["instante"] for d in disponibles],
                    superficie.instante(),
                )
                pix = img.pixmap()
                ok_preview = (
                    pix is not None
                    and not pix.isNull()
                    and pix.cacheKey()
                    == disponibles[idx]["pixmap_escalado"].cacheKey()
                )
                ok_bordes = True
                for fraccion in (0.05, 0.25, 0.5, 0.75, 0.95):
                    _mouse_move(superficie, ancho_sup * fraccion)
                    if img.x() < 0 or (img.x() + img.width()) > ancho_sup:
                        ok_bordes = False
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return (
                ok_izq and ok_der and ok_centro and ok_preview and ok_bordes,
                f"x={img.x()} ancho_img={ancho_img} ancho_sup={ancho_sup}",
            )
    finally:
        escanear_mod.configurar_cantidad_previews(_CANTIDAD_ORIGINAL_PREVIEWS)


def test_18():
    escanear_mod.configurar_cantidad_previews(3)
    try:
        with _miniaturas_temporales() as carpeta_min:
            temp, ventana = _ventana_con_previews(
                ["a.mp4"], [100.0], carpeta_min
            )
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                tarjeta.expandir()
                _esperar(lambda: tarjeta._franja.width() > 0)
                superficie = tarjeta._franja
                ancho = superficie.width()
                tiempos = []
                for fraccion in (0.1, 0.35, 0.7, 0.9):
                    x = ancho * fraccion
                    _mouse_press(superficie, x)
                    tiempos.append(
                        round(posicion_a_tiempo(x, ancho, 100.0), 6)
                    )
                esperados = sorted(set(tiempos))
                tiempos_marcados = [m["tiempo"] for m in tarjeta._marcadores]
                ok_conteo = len(tarjeta._marcadores) == 4
                ok_orden = tiempos_marcados == sorted(tiempos_marcados)
                ok_tiempos = all(
                    abs(a - b) < 1e-6
                    for a, b in zip(tiempos_marcados, esperados)
                )
                x_dup = ancho * 0.9
                _mouse_press(superficie, x_dup)
                _mouse_press(superficie, x_dup)
                ok_dedup = len(tarjeta._marcadores) == 4
                instantes_preview = [
                    d["instante"] for d in tarjeta._previews_exploracion
                ]
                ok_tiempo_real = (
                    tarjeta._marcadores[0]["tiempo"] not in instantes_preview
                )
                antes = [m["tiempo"] for m in tarjeta._marcadores]
                _mouse_move(superficie, ancho * 0.5)
                ok_no_interfiere = (
                    [m["tiempo"] for m in tarjeta._marcadores] == antes
                    and superficie.instante() is not None
                )
                ok_superficie = sorted(tarjeta._franja._marcadores) == sorted(
                    antes
                )
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return (
                ok_conteo
                and ok_orden
                and ok_tiempos
                and ok_dedup
                and ok_tiempo_real
                and ok_no_interfiere
                and ok_superficie,
                f"marcadores={tarjeta._marcadores}",
            )
    finally:
        escanear_mod.configurar_cantidad_previews(_CANTIDAD_ORIGINAL_PREVIEWS)


def test_19():
    escanear_mod.configurar_cantidad_previews(3)
    try:
        with _miniaturas_temporales() as carpeta_min:
            temp, ventana = _ventana_con_previews(
                ["a.mp4"], [100.0], carpeta_min
            )
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                tarjeta.expandir()
                _esperar(lambda: tarjeta._franja.width() > 0)
                superficie = tarjeta._franja
                ancho = superficie.width()
                _mouse_press(superficie, ancho * 0.25)
                _mouse_press(superficie, ancho * 0.75)
                guardados = [m["tiempo"] for m in tarjeta._marcadores]
                _mouse_move(superficie, ancho * 0.5)
                ok_mover = [m["tiempo"] for m in tarjeta._marcadores] == guardados
                tarjeta.colapsar()
                ok_colapso = [m["tiempo"] for m in tarjeta._marcadores] == guardados
                tarjeta.expandir()
                _esperar(lambda: tarjeta._franja.width() > 0)
                ok_re_expand = [m["tiempo"] for m in tarjeta._marcadores] == guardados
                ok_superficie = sorted(tarjeta._franja._marcadores) == sorted(
                    guardados
                )
                ventana._limpiar_seleccion()
                _mouse_press(superficie, ancho * 0.5)
                ok_sin_seleccion = (
                    "a.mp4" not in ventana._nombres_seleccionados
                )
                _mouse_press(tarjeta, 5)
                ok_seleccion = "a.mp4" in ventana._nombres_seleccionados
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return (
                ok_mover
                and ok_colapso
                and ok_re_expand
                and ok_superficie
                and ok_sin_seleccion
                and ok_seleccion,
                f"guardados={guardados} seleccion={ok_seleccion} sin={ok_sin_seleccion}",
            )
    finally:
        escanear_mod.configurar_cantidad_previews(_CANTIDAD_ORIGINAL_PREVIEWS)


def test_20():
    escanear_mod.configurar_cantidad_previews(3)
    try:
        with _miniaturas_temporales() as carpeta_min, _config_con_previews(9):
            temp, ventana = _ventana_con_previews(
                ["clip.mp4"], [100.0], carpeta_min, cantidad=9
            )
            try:
                tarjeta = dict(ventana.tarjetas)["clip.mp4"]
                tarjeta.expandir()
                _esperar(lambda: tarjeta._franja.width() > 0)
                _esperar(
                    lambda: tarjeta._franja.width()
                    <= ventana.area.viewport().width(),
                    timeout_ms=8000,
                )
                superficie = tarjeta._franja
                ancho = superficie.width()
                viewport = ventana.area.viewport().width()
                ok_cabe = ancho <= viewport
                _mouse_move(superficie, 0)
                ok_izq = superficie.instante() == 0.0
                _mouse_move(superficie, ancho)
                ok_der = abs(superficie.instante() - 100.0) < 1e-6
                _mouse_move(superficie, ancho * 0.98)
                inst_98 = superficie.instante()
                ok_98 = abs(inst_98 - 98.0) < 1e-6
                img = tarjeta._imagen_exploracion
                ok_bordes = img.x() >= 0 and (img.x() + img.width()) <= ancho
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return (
                ok_cabe and ok_izq and ok_der and ok_98 and ok_bordes,
                f"ancho_sup={ancho} viewport={viewport} inst_98={inst_98:.2f}",
            )
    finally:
        escanear_mod.configurar_cantidad_previews(_CANTIDAD_ORIGINAL_PREVIEWS)


def test_21():
    escanear_mod.configurar_cantidad_previews(3)
    try:
        with _miniaturas_temporales() as carpeta_min, _config_con_previews(9):
            temp, ventana = _ventana_con_previews(
                ["clip.mp4"], [100.0], carpeta_min, cantidad=9
            )
            try:
                tarjeta = dict(ventana.tarjetas)["clip.mp4"]
                tarjeta.expandir()
                _esperar(lambda: tarjeta._franja.width() > 0)
                superficie = tarjeta._franja
                ancho = superficie.width()
                disponibles = tarjeta._previews_exploracion
                if len(disponibles) != 9:
                    return False, f"previews_disponibles={len(disponibles)}"
                instantes = [d["instante"] for d in disponibles]
                ok = True
                detalle = []
                for frac in (0.0, 0.10, 0.25, 0.50, 0.75, 0.90, 1.0):
                    _mouse_move(superficie, ancho * frac)
                    instante = superficie.instante()
                    idx_esp = preview_mas_cercana(instantes, instante)
                    pix = tarjeta._imagen_exploracion.pixmap()
                    ok_inst = abs(instante - 100.0 * frac) < 1e-6
                    ok_prev = (
                        pix is not None
                        and not pix.isNull()
                        and idx_esp is not None
                        and pix.cacheKey()
                        == disponibles[idx_esp]["pixmap_escalado"].cacheKey()
                    )
                    detalle.append(
                        f"{frac*100:.0f}%->{instante:.1f}s#p{idx_esp+1}"
                    )
                    ok = ok and ok_inst and ok_prev
                return ok, " | ".join(detalle)
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
    finally:
        escanear_mod.configurar_cantidad_previews(_CANTIDAD_ORIGINAL_PREVIEWS)


def test_22():
    escanear_mod.configurar_cantidad_previews(3)
    try:
        with _miniaturas_temporales() as carpeta_min:
            temp, ventana = _ventana_con_previews(
                ["a.mp4"], [100.0], carpeta_min
            )
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                tarjeta.expandir()
                _esperar(lambda: tarjeta._franja.width() > 0)
                superficie = tarjeta._franja
                ancho = superficie.width()
                disponibles = tarjeta._previews_exploracion

                class QPixmapContador(QPixmap):
                    lecturas_disco = 0
                    totales = 0

                    def __init__(self, *a, **k):
                        type(self).totales += 1
                        if a and isinstance(a[0], str):
                            type(self).lecturas_disco += 1
                        super().__init__(*a, **k)

                original_qpixmap = visor_videos.QPixmap
                visor_videos.QPixmap = QPixmapContador
                llamadas_ffmpeg = {"n": 0}
                original_generar = escanear_mod.generar_preview

                def _prohibido(*_a, **_k):
                    llamadas_ffmpeg["n"] += 1
                    raise AssertionError("no debe invocarse FFmpeg")

                escanear_mod.generar_preview = _prohibido
                try:
                    for fraccion in (0.2, 0.5, 0.8):
                        _mouse_press(superficie, ancho * fraccion)
                    QApplication.processEvents()
                    ok_conteo = len(tarjeta._marcadores) == 3
                    ok_sin_lectura = QPixmapContador.lecturas_disco == 0
                    ok_ffmpeg = llamadas_ffmpeg["n"] == 0

                    ok_tiempos = True
                    ok_pixmap = True
                    for fraccion, marcador in zip(
                        (0.2, 0.5, 0.8), tarjeta._marcadores
                    ):
                        instante = posicion_a_tiempo(
                            ancho * fraccion, ancho, 100.0
                        )
                        if abs(marcador["tiempo"] - instante) > 1e-6:
                            ok_tiempos = False
                        idx = preview_mas_cercana(
                            [d["instante"] for d in disponibles], instante
                        )
                        pix = marcador.get("pixmap")
                        if pix is None:
                            ok_pixmap = False
                        elif idx is not None and pix.cacheKey() != disponibles[
                            idx
                        ]["pixmap_escalado"].cacheKey():
                            ok_pixmap = False

                    ok_etiquetas = all(
                        m.get("etiqueta") is not None
                        and not m["etiqueta"].isHidden()
                        for m in tarjeta._marcadores
                    )
                    antes = [m["tiempo"] for m in tarjeta._marcadores]
                    _mouse_move(superficie, ancho * 0.4)
                    ok_tras_mover = [
                        m["tiempo"] for m in tarjeta._marcadores
                    ] == antes
                    tarjeta.colapsar()
                    tarjeta.expandir()
                    _esperar(lambda: tarjeta._franja.width() > 0)
                    ok_tras_expandir = len(tarjeta._marcadores) == 3
                    ok_tras_render = all(
                        m.get("etiqueta") is not None
                        and not m["etiqueta"].isHidden()
                        for m in tarjeta._marcadores
                    )
                finally:
                    visor_videos.QPixmap = original_qpixmap
                    escanear_mod.generar_preview = original_generar
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return (
                ok_conteo
                and ok_sin_lectura
                and ok_ffmpeg
                and ok_tiempos
                and ok_pixmap
                and ok_etiquetas
                and ok_tras_mover
                and ok_tras_expandir
                and ok_tras_render,
                f"n={len(tarjeta._marcadores)} "
                f"lecturas_disco={QPixmapContador.lecturas_disco} "
                f"totales={QPixmapContador.totales} ffmpeg={llamadas_ffmpeg['n']}",
            )
    finally:
        escanear_mod.configurar_cantidad_previews(_CANTIDAD_ORIGINAL_PREVIEWS)


def test_23():
    escanear_mod.configurar_cantidad_previews(3)
    try:
        with _miniaturas_temporales() as carpeta_min:
            temp, ventana = _ventana_con_previews(
                ["a.mp4"], [100.0], carpeta_min
            )
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                tarjeta.expandir()
                _esperar(lambda: tarjeta._franja.width() > 0)
                superficie = tarjeta._franja
                ancho = superficie.width()
                for fraccion in (0.2, 0.5, 0.8):
                    _mouse_press(superficie, ancho * fraccion)
                QApplication.processEvents()
                originales = [m["tiempo"] for m in tarjeta._marcadores]
                if len(originales) != 3:
                    return False, f"creados={len(originales)}"
                central = tarjeta._marcadores[1]["etiqueta"]
                _clic_derecho(central)
                QApplication.processEvents()
                restantes = [m["tiempo"] for m in tarjeta._marcadores]
                ok_conteo = len(restantes) == 2
                ok_tiempos = restantes == [originales[0], originales[2]]
                ok_marca = sorted(tarjeta._franja._marcadores) == sorted(
                    restantes
                )
                etiquetas = tarjeta._franja.findChildren(MiniaturaMarcador)
                ok_labels = len(etiquetas) == 2
                ok_otras = all(
                    m.get("etiqueta") is not None
                    and not m["etiqueta"].isHidden()
                    for m in tarjeta._marcadores
                )
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return (
                ok_conteo
                and ok_tiempos
                and ok_marca
                and ok_labels
                and ok_otras,
                f"restantes={restantes} labels={len(etiquetas)}",
            )
    finally:
        escanear_mod.configurar_cantidad_previews(_CANTIDAD_ORIGINAL_PREVIEWS)


def test_24():
    escanear_mod.configurar_cantidad_previews(3)
    try:
        with _miniaturas_temporales() as carpeta_min:
            temp, ventana = _ventana_con_previews(
                ["a.mp4"], [100.0], carpeta_min
            )
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                tarjeta.expandir()
                _esperar(lambda: tarjeta._franja.width() > 0)
                superficie = tarjeta._franja
                ancho = superficie.width()
                for fraccion in (0.2, 0.5, 0.8):
                    _mouse_press(superficie, ancho * fraccion)
                QApplication.processEvents()
                originales = [m["tiempo"] for m in tarjeta._marcadores]

                _clic_derecho(tarjeta._marcadores[0]["etiqueta"])
                QApplication.processEvents()
                ok_primero = [m["tiempo"] for m in tarjeta._marcadores] == originales[1:]

                _clic_derecho(tarjeta._marcadores[-1]["etiqueta"])
                QApplication.processEvents()
                ok_ultimo = [m["tiempo"] for m in tarjeta._marcadores] == originales[1:2]

                _mouse_move(superficie, ancho * 0.5)
                ok_mover = abs(superficie.instante() - 50.0) < 1e-6

                tarjeta.colapsar()
                tarjeta.expandir()
                _esperar(lambda: tarjeta._franja.width() > 0)
                ok_reexpand = [m["tiempo"] for m in tarjeta._marcadores] == originales[1:2]

                _clic_derecho(tarjeta._marcadores[0]["etiqueta"])
                QApplication.processEvents()
                ok_vacio = (
                    tarjeta._marcadores == []
                    and tarjeta._franja._marcadores == []
                )

                _mouse_press(superficie, ancho * 0.4)
                QApplication.processEvents()
                ok_crear = len(tarjeta._marcadores) == 1
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return (
                ok_primero
                and ok_ultimo
                and ok_mover
                and ok_reexpand
                and ok_vacio
                and ok_crear,
                f"restantes={[m['tiempo'] for m in tarjeta._marcadores]}",
            )
    finally:
        escanear_mod.configurar_cantidad_previews(_CANTIDAD_ORIGINAL_PREVIEWS)


def test_25():
    escanear_mod.configurar_cantidad_previews(3)
    try:
        with _miniaturas_temporales() as carpeta_min:
            ruta_config = os.environ["VISOR_CONFIG"]

            def _snapshot():
                config = None
                if os.path.isfile(ruta_config):
                    with open(ruta_config, "rb") as f:
                        config = f.read()
                archivos = sorted(os.listdir(carpeta_min))
                return config, archivos

            temp, ventana = _ventana_con_previews(
                ["a.mp4"], [100.0], carpeta_min
            )
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                tarjeta.expandir()
                _esperar(lambda: tarjeta._franja.width() > 0)
                superficie = tarjeta._franja
                ancho = superficie.width()
                for fraccion in (0.25, 0.75):
                    _mouse_press(superficie, ancho * fraccion)
                QApplication.processEvents()
                n_antes = len(tarjeta._marcadores)

                class MenuContador(visor_videos.QMenu):
                    creados = 0

                    def __init__(self, *a, **k):
                        type(self).creados += 1
                        super().__init__(*a, **k)

                    def exec(self, *a, **k):
                        return None

                class QPixmapContador(QPixmap):
                    lecturas = 0

                    def __init__(self, *a, **k):
                        if a and isinstance(a[0], str):
                            type(self).lecturas += 1
                        super().__init__(*a, **k)

                original_menu = visor_videos.QMenu
                original_qpixmap = visor_videos.QPixmap
                original_generar = escanear_mod.generar_preview
                visor_videos.QMenu = MenuContador
                visor_videos.QPixmap = QPixmapContador
                llamadas_ffmpeg = {"n": 0}

                def _prohibido(*_a, **_k):
                    llamadas_ffmpeg["n"] += 1
                    raise AssertionError("no debe invocarse FFmpeg")

                escanear_mod.generar_preview = _prohibido
                try:
                    _clic_derecho(superficie, int(ancho * 0.1))
                    QApplication.processEvents()
                    ok_no_crea = len(tarjeta._marcadores) == n_antes

                    ventana._limpiar_seleccion()
                    menu_antes = MenuContador.creados
                    snapshot_antes = _snapshot()
                    _clic_derecho(tarjeta._marcadores[0]["etiqueta"])
                    QApplication.processEvents()
                    ok_elimina = len(tarjeta._marcadores) == n_antes - 1
                    ok_no_selecciona = (
                        "a.mp4" not in ventana._nombres_seleccionados
                    )
                    ok_no_menu = MenuContador.creados == menu_antes
                    ok_ffmpeg = llamadas_ffmpeg["n"] == 0
                    ok_sin_lectura = QPixmapContador.lecturas == 0
                    ok_snapshot = snapshot_antes == _snapshot()
                finally:
                    visor_videos.QMenu = original_menu
                    visor_videos.QPixmap = original_qpixmap
                    escanear_mod.generar_preview = original_generar
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return (
                ok_no_crea
                and ok_elimina
                and ok_no_selecciona
                and ok_no_menu
                and ok_ffmpeg
                and ok_sin_lectura
                and ok_snapshot,
                f"menu={MenuContador.creados - menu_antes} "
                f"ffmpeg={llamadas_ffmpeg['n']} lecturas={QPixmapContador.lecturas}",
            )
    finally:
        escanear_mod.configurar_cantidad_previews(_CANTIDAD_ORIGINAL_PREVIEWS)


def test_26():
    escanear_mod.configurar_cantidad_previews(3)
    try:
        with _miniaturas_temporales() as carpeta_min:
            temp, ventana = _ventana_con_previews(
                ["a.mp4"], [100.0], carpeta_min
            )
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                tarjeta.expandir()
                _esperar(lambda: tarjeta._franja.width() > 0)
                superficie = tarjeta._franja
                ancho = superficie.width()
                _mouse_press(superficie, ancho * 0.3)
                _mouse_press(superficie, ancho * 0.7)
                QApplication.processEvents()
                originales = [m["tiempo"] for m in tarjeta._marcadores]
                if len(originales) != 2:
                    return False, f"creados={len(originales)}"
                x_tick = tiempo_a_posicion(
                    originales[1], ancho, 100.0
                )

                class MenuContador(visor_videos.QMenu):
                    def __init__(self, *a, **k):
                        super().__init__(*a, **k)

                    def exec(self, *a, **k):
                        return None

                original_menu = visor_videos.QMenu
                visor_videos.QMenu = MenuContador
                try:
                    _clic_derecho(superficie, x_tick)
                    QApplication.processEvents()
                    restantes = [m["tiempo"] for m in tarjeta._marcadores]
                    ok_tick = len(restantes) == 1 and restantes == [
                        originales[0]
                    ]
                    x_vacio = tiempo_a_posicion(
                        (originales[0] + originales[1]) / 2, ancho, 100.0
                    )
                    _clic_derecho(superficie, x_vacio)
                    QApplication.processEvents()
                    ok_no_tick = len(tarjeta._marcadores) == 1
                finally:
                    visor_videos.QMenu = original_menu
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return (
                ok_tick and ok_no_tick,
                f"restantes={restantes}",
            )
    finally:
        escanear_mod.configurar_cantidad_previews(_CANTIDAD_ORIGINAL_PREVIEWS)


def test_27():
    escanear_mod.configurar_cantidad_previews(3)
    try:
        with _miniaturas_temporales() as carpeta_min, _config_con_previews(9):
            temp, ventana = _ventana_con_previews(
                ["clip.mp4"], [100.0], carpeta_min, cantidad=9
            )
            try:
                tarjeta = dict(ventana.tarjetas)["clip.mp4"]
                tarjeta.expandir()
                _esperar(lambda: tarjeta._franja.width() > 0)
                superficie = tarjeta._franja
                ancho = superficie.width()
                disponibles = tarjeta._previews_exploracion
                instantes = [d["instante"] for d in disponibles]
                img = tarjeta._imagen_exploracion

                # --- inicial ---
                ok_inicial_instante = superficie.instante() == 0.0
                idx0 = preview_mas_cercana(instantes, 0.0)
                pix0 = img.pixmap()
                ok_inicial_elegida = (
                    pix0 is not None
                    and pix0.cacheKey()
                    == disponibles[idx0]["pixmap_escalado"].cacheKey()
                )
                ok_inicial_x = img.x() == 0
                ok_inicial_sin_hueco = (
                    img.width() == pix0.width()
                )

                # --- scrubbing: separar elegida vs posicion ---
                ok = True
                detalle = []
                for frac in (0.0, 0.25, 0.50, 0.75, 1.0):
                    _mouse_move(superficie, ancho * frac)
                    instante = superficie.instante()
                    if abs(instante - 100.0 * frac) > 1e-6:
                        ok = False
                    idx = preview_mas_cercana(instantes, instante)
                    pix = img.pixmap()
                    ok_elegida = (
                        pix is not None
                        and pix.cacheKey()
                        == disponibles[idx]["pixmap_escalado"].cacheKey()
                    )
                    maximo = max(0, ancho - img.width())
                    izquierda = max(
                        0.0, min(instante / 100.0 * ancho - img.width() / 2.0, float(maximo))
                    )
                    ok_posicion = img.x() == int(izquierda)
                    detalle.append(
                        f"{frac*100:.0f}%:elegida=p{idx+1}:x={img.x()}:esp={int(izquierda)}"
                    )
                    ok = ok and ok_elegida and ok_posicion
                return (
                    ok_inicial_instante
                    and ok_inicial_elegida
                    and ok_inicial_x
                    and ok_inicial_sin_hueco
                    and ok,
                    " | ".join(detalle),
                )
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
    finally:
        escanear_mod.configurar_cantidad_previews(_CANTIDAD_ORIGINAL_PREVIEWS)


def test_28():
    escanear_mod.configurar_cantidad_previews(3)
    try:
        with _miniaturas_temporales() as carpeta_min, _config_con_previews(9):
            for nombre in ["clip.mp4"]:
                _crear_previews(
                    carpeta_min, os.path.splitext(nombre)[0], 9, ancho=360, alto=640
                )
            temp, ruta_db = _crear_bd(_filas(["clip.mp4"], [100.0]))
            ventana = VisorVideos(ruta_db=ruta_db)
            ventana.resize(900, 620)
            ventana.show()
            _esperar(
                lambda v=ventana: v._carga_completada and v.gestor.hilo is None
            )
            _esperar(lambda: ventana.contenedor.findChildren(Tarjeta))
            try:
                tarjeta = dict(ventana.tarjetas)["clip.mp4"]
                tarjeta.expandir()
                _esperar(lambda: tarjeta._franja.width() > 0)
                superficie = tarjeta._franja
                img = tarjeta._imagen_exploracion
                pix = img.pixmap()
                ok_instante = superficie.instante() == 0.0
                ok_x = img.x() == 0
                ok_label_ajustado = pix is not None and not pix.isNull() and img.width() == pix.width()
                pix_w = pix.width() if pix is not None else None
                ok_menor_320 = img.width() < 320
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return (
                ok_instante
                and ok_x
                and ok_label_ajustado
                and ok_menor_320,
                f"label_w={img.width()} pixmap_w={pix_w} x={img.x()}",
            )
    finally:
        escanear_mod.configurar_cantidad_previews(_CANTIDAD_ORIGINAL_PREVIEWS)


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
        test_17,
        test_18,
        test_19,
        test_20,
        test_21,
        test_22,
        test_23,
        test_24,
        test_25,
        test_26,
        test_27,
        test_28,
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
    print(f"TOTAL={aprobadas}/{len(pruebas)}")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
