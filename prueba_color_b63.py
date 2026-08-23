"""Pruebas específicas de B6.3 — clasificación visual de marcadores y segmentos.

Cubre comportamiento real (no solo textos) sobre las cinco capas:
modelo (paleta, asignación, persistencia, migración), configuración
(nombres globales), tareas, UI (selector, menús con submenús realmente
accionables tras `gc.collect`, encolado, restauración y rollback) y
render (píxeles deterministas con color / NULL histórico).
"""

import contextlib
import gc
import os
import py_compile
import sqlite3
import sys
import tempfile
import time

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QImage, QMouseEvent, QPointingDevice
from PySide6.QtWidgets import QApplication, QLineEdit, QVBoxLayout, QWidget

import configuracion
import escanear_videos as escanear_mod
import tareas_videos as tv
import visor_videos
from configuracion import (
    LIMITE_LONGITUD_NOMBRE_COLOR,
    NOMBRES_COLORES_POR_DEFECTO,
    guardar_nombre_color,
    obtener_nombres_colores,
    texto_color,
)
from escanear_videos import (
    CLAVES_COLOR_CLASIFICACION,
    COLORES_CLASIFICACION,
    asignar_color_marcador,
    asignar_color_segmento,
    color_rgb,
    conectar_bd,
    guardar_marcador,
    guardar_segmento,
    guardar_videos,
    listar_marcadores,
    listar_segmentos,
    listar_videos,
)
from exploracion_temporal import tiempo_a_posicion
from scrubber import (
    FranjaExploracion,
    _ALTO_PISTA,
    _MARGEN,
)
from visor_videos import Tarjeta, VisorVideos

_CONFIG_TEMPORAL = tempfile.TemporaryDirectory()
os.environ["VISOR_CONFIG"] = os.path.join(_CONFIG_TEMPORAL.name, "configuracion.json")


def _esperar(predicado, timeout_ms=10000, paso_ms=20):
    fin = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < fin:
        QApplication.processEvents()
        if predicado():
            return True
        time.sleep(paso_ms / 1000)
    QApplication.processEvents()
    return predicado()


def _limpiar(ventana):
    if ventana is None:
        return
    for gestor in (
        getattr(ventana, "gestor", None),
        getattr(ventana, "gestor_marcadores", None),
        getattr(ventana, "gestor_segmentos", None),
    ):
        if gestor is not None:
            gestor.cerrar()
    ventana.deleteLater()
    for _ in range(5):
        QApplication.processEvents()


def _registro(nombre, duracion=100.0):
    return {
        "nombre": nombre,
        "ruta": f"C:\\v\\{nombre}",
        "extension": os.path.splitext(nombre)[1].lower(),
        "fecha_importacion": "f",
        "duracion_segundos": duracion,
        "ancho": 640,
        "alto": 360,
        "codec_video": "h264",
        "cantidad_miniaturas": 3,
        "tamano_bytes": 1000,
    }


def _crear_bd_con_videos(nombres):
    temp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp.name, "catalogo.db")
    conn = conectar_bd(ruta_db)
    conn.close()
    guardar_videos([_registro(n) for n in nombres], ruta_db)
    return temp, ruta_db


def _video_id(ruta_db, nombre):
    for fila in listar_videos(ruta_db):
        if fila[0] == nombre:
            return fila[8]
    return None


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


def _abrir_ventana(ruta_db):
    ventana = VisorVideos(ruta_db=ruta_db)
    ventana.resize(900, 620)
    ventana.show()
    _esperar(
        lambda v=ventana: v._carga_completada and v.gestor.hilo is None
    )
    return ventana


def _enviar(widget, tipo, x, boton):
    evento = QMouseEvent(
        tipo,
        QPointF(float(x), 6.0),
        boton,
        boton,
        Qt.NoModifier,
        QPointingDevice.primaryPointingDevice(),
    )
    QApplication.sendEvent(widget, evento)


def _press(widget, x):
    _enviar(widget, QEvent.MouseButtonPress, x, Qt.LeftButton)
    _enviar(widget, QEvent.MouseButtonRelease, x, Qt.LeftButton)


def _press_derecho(widget, x):
    _enviar(widget, QEvent.MouseButtonPress, x, Qt.RightButton)


def _expandir(tarjeta):
    tarjeta.expandir()
    _esperar(lambda: tarjeta._franja.width() > 0)


def _drenar_marcadores(ventana, timeout_ms=15000):
    return _esperar(
        lambda: not ventana.gestor_marcadores.activo
        and not ventana._cola_marcadores,
        timeout_ms=timeout_ms,
    )


def _drenar_segmentos(ventana, timeout_ms=15000):
    return _esperar(
        lambda: not ventana.gestor_segmentos.activo
        and not ventana._cola_segmentos,
        timeout_ms=timeout_ms,
    )


def _crear_marcador_persistido(ventana, tarjeta, x):
    base = len(tarjeta._marcadores)
    _press(tarjeta._franja, x)
    if not _esperar(lambda: len(tarjeta._marcadores) > base):
        return None
    _drenar_marcadores(ventana)
    for marcador in tarjeta._marcadores:
        if abs(marcador["tiempo"] - x) < 1e-6:
            return marcador
    return tarjeta._marcadores[-1]


def _crear_segmento_persistido(ventana, tarjeta, x1, x2):
    tarjeta._boton_segmento.setChecked(True)
    franja = tarjeta._franja
    base = len(tarjeta._segmentos)
    _press(franja, x1)
    if not _esperar(lambda: tarjeta._extremo_segmento is not None):
        return None
    _press(franja, x2)
    if not _esperar(lambda: len(tarjeta._segmentos) > base):
        return None
    _drenar_segmentos(ventana)
    return tarjeta._segmentos[-1]


def _accion_de_submenu(menu, titulo, texto):
    accion = None
    for acc in menu.actions():
        sub = acc.menu()
        if sub is not None and sub.title() == titulo:
            for a in sub.actions():
                if a.text() == texto:
                    accion = a
    return accion


def test_01():
    """Los módulos modificados por B6.3 compilan."""
    modulos = [
        "configuracion.py",
        "escanear_videos.py",
        "tareas_videos.py",
        "visor_videos.py",
        "scrubber.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    """Paleta cerrada: 6 claves estables con RGB, sin claves extra."""
    claves = [clave for clave, *_resto in COLORES_CLASIFICACION]
    ok = (
        len(COLORES_CLASIFICACION) == 6
        and set(claves) == {
            "rojo", "naranja", "amarillo", "verde", "azul", "violeta"
        }
        and CLAVES_COLOR_CLASIFICACION == frozenset(claves)
        and all(color_rgb(c) is not None for c in claves)
        and all(
            isinstance(rgb, tuple)
            and len(rgb) == 3
            and all(isinstance(v, int) and 0 <= v <= 255 for v in rgb)
            for rgb in (color_rgb(c) for c in claves)
        )
        and color_rgb("magenta") is None
        and color_rgb(None) is None
    )
    rgb = {c: color_rgb(c) for c in claves}
    return ok, f"paleta={rgb}"


def test_03():
    """Persistir con color válido y rechazar claves inválidas."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_v = _video_id(ruta_db, "a.mp4")
        m = guardar_marcador(id_v, 10.0, ruta_db, color="verde")
        s = guardar_segmento(id_v, 20.0, 40.0, ruta_db, color="azul")
        ok_guardado = (
            listar_marcadores(id_v, ruta_db) == [(m, id_v, 10.0, "verde")]
            and listar_segmentos(id_v, ruta_db) == [(s[0], 20.0, 40.0, "azul")]
        )
        rechazo = []
        for etiqueta, fn in [
            ("marcador", lambda: guardar_marcador(id_v, 1.0, ruta_db, color="magenta")),
            ("segmento", lambda: guardar_segmento(id_v, 1.0, 2.0, ruta_db, color="magenta")),
            ("asignar_marcador", lambda: asignar_color_marcador(m, "magenta", ruta_db)),
            ("asignar_segmento", lambda: asignar_color_segmento(s[0], "cyan", ruta_db)),
            ("tipo_marcador", lambda: guardar_marcador(id_v, 1.0, ruta_db, color=123)),
        ]:
            try:
                fn()
                rechazo.append(f"{etiqueta}=NO_RECHAZO")
            except (ValueError, TypeError):
                rechazo.append(f"{etiqueta}=ok")
        ok = ok_guardado and all(r.endswith("=ok") for r in rechazo)
        return ok, f"guardado={ok_guardado} rechazos={rechazo}"
    finally:
        temp.cleanup()


def test_04():
    """asignar_color_marcador: asignar, quitar y persistencia SQLite."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_v = _video_id(ruta_db, "a.mp4")
        m = guardar_marcador(id_v, 5.0, ruta_db)
        fila = asignar_color_marcador(m, "rojo", ruta_db)
        ok_asigna = fila == (m, id_v, 5.0, "rojo")
        ok_persiste = listar_marcadores(id_v, ruta_db) == [(m, id_v, 5.0, "rojo")]
        fila2 = asignar_color_marcador(m, None, ruta_db)
        ok_quita = fila2 == (m, id_v, 5.0, None)
        ok_persiste_nulo = listar_marcadores(id_v, ruta_db) == [(m, id_v, 5.0, None)]
        return (
            ok_asigna and ok_persiste and ok_quita and ok_persiste_nulo,
            f"asigna={ok_asigna} persiste={ok_persiste} quita={ok_quita} nulo={ok_persiste_nulo}",
        )
    finally:
        temp.cleanup()


def test_05():
    """asignar_color_segmento: asignar, quitar y persistencia SQLite."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_v = _video_id(ruta_db, "a.mp4")
        s = guardar_segmento(id_v, 30.0, 60.0, ruta_db)
        fila = asignar_color_segmento(s[0], "violeta", ruta_db)
        ok_asigna = fila == (s[0], 30.0, 60.0, "violeta")
        ok_persiste = listar_segmentos(id_v, ruta_db) == [(s[0], 30.0, 60.0, "violeta")]
        fila2 = asignar_color_segmento(s[0], None, ruta_db)
        ok_quita = fila2 == (s[0], 30.0, 60.0, None)
        ok_persiste_nulo = listar_segmentos(id_v, ruta_db) == [(s[0], 30.0, 60.0, None)]
        return (
            ok_asigna and ok_persiste and ok_quita and ok_persiste_nulo,
            f"asigna={ok_asigna} persiste={ok_persiste} quita={ok_quita} nulo={ok_persiste_nulo}",
        )
    finally:
        temp.cleanup()


def test_06():
    """Id inexistente → None; históricos sin color quedan NULL."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_v = _video_id(ruta_db, "a.mp4")
        m = guardar_marcador(id_v, 5.0, ruta_db)
        s = guardar_segmento(id_v, 1.0, 2.0, ruta_db)
        ok_ausente = (
            asignar_color_marcador(999999, "rojo", ruta_db) is None
            and asignar_color_segmento(999999, "verde", ruta_db) is None
        )
        ok_nulos = (
            listar_marcadores(id_v, ruta_db) == [(m, id_v, 5.0, None)]
            and listar_segmentos(id_v, ruta_db) == [(s[0], 1.0, 2.0, None)]
        )
        return ok_ausente and ok_nulos, f"ausente={ok_ausente} nulos={ok_nulos}"
    finally:
        temp.cleanup()


def test_07():
    """Migración aditiva e idempotente de `color` en ambas tablas."""
    temp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp.name, "vieja.db")
    try:
        conn = sqlite3.connect(ruta_db)
        conn.execute(
            """
            CREATE TABLE marcadores_video (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER,
                tiempo REAL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE segmentos_video (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER,
                inicio REAL,
                fin REAL
            )
            """
        )
        conn.commit()
        conn.close()
        conn_migracion = conectar_bd(ruta_db)
        conn_migracion.close()
        conn_migracion = conectar_bd(ruta_db)
        conn_migracion.close()
        conn = sqlite3.connect(ruta_db)
        try:
            cols_m = [fila[1] for fila in conn.execute(
                "PRAGMA table_info(marcadores_video)")]
            cols_s = [fila[1] for fila in conn.execute(
                "PRAGMA table_info(segmentos_video)")]
            tipos = dict(
                conn.execute("SELECT name, type FROM sqlite_master WHERE type='table'")
            )
        finally:
            conn.close()
        ok = (
            cols_m.count("color") == 1
            and cols_s.count("color") == 1
            and "marcadores_video" in tipos
            and "segmentos_video" in tipos
        )
        return ok, f"marcadores_cols={cols_m} segmentos_cols={cols_s}"
    finally:
        temp.cleanup()


def test_08():
    """Nombres globales personalizados: guardar, leer y texto visible."""
    fd, ruta = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        ok_default = (
            texto_color("rojo", ruta) == "Rojo"
            and texto_color("azul", ruta) == "Azul"
        )
        ok_guardar = guardar_nombre_color("rojo", "Crimson", ruta) == "Crimson"
        ok_leer = obtener_nombres_colores(ruta) == {"rojo": "Crimson"}
        ok_texto = texto_color("rojo", ruta) == "Crimson"
        ok_otros_default = texto_color("verde", ruta) == "Verde"
        ok_invalida = (
            texto_color("magenta", ruta) is None
            and guardar_nombre_color("magenta", "X", ruta) is None
            and "magenta" not in obtener_nombres_colores(ruta)
        )
        return (
            ok_default and ok_guardar and ok_leer and ok_texto
            and ok_otros_default and ok_invalida,
            f"texto={texto_color('rojo', ruta)} leido={obtener_nombres_colores(ruta)}",
        )
    finally:
        os.unlink(ruta)


def test_09():
    """Config: límite, no-texto, vacío restaura fábrica."""
    fd, ruta = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        limite = LIMITE_LONGITUD_NOMBRE_COLOR
        ok_limite = (
            guardar_nombre_color("verde", "x" * (limite + 1), ruta) is None
            and guardar_nombre_color("verde", "x" * limite, ruta) == "x" * limite
        )
        ok_no_texto = guardar_nombre_color("amarillo", 123, ruta) is None
        ok_restaura = guardar_nombre_color("rojo", "Crimson", ruta) == "Crimson"
        ok_vacio = guardar_nombre_color("rojo", "   ", ruta) == "Rojo"
        ok_lejos = "rojo" not in obtener_nombres_colores(ruta)
        ok_texto_vacio = texto_color("rojo", ruta) == "Rojo"
        ok_validos = {
            clave: NOMBRES_COLORES_POR_DEFECTO[clave]
            for clave in CLAVES_COLOR_CLASIFICACION
        }
        ok = (
            ok_limite and ok_no_texto and ok_restaura
            and ok_vacio and ok_lejos and ok_texto_vacio
            and ok_validos
        )
        return (
            ok,
            f"limite={ok_limite} no_texto={ok_no_texto} vacio={ok_vacio} "
            f"restaura={texto_color('rojo', ruta)} fabrica={ok_validos}",
        )
    finally:
        os.unlink(ruta)


def test_10():
    """Renombrar un color no altera la clave persistida en SQLite."""
    temp = tempfile.TemporaryDirectory()
    fd, ruta_config = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    ruta_db = os.path.join(temp.name, "catalogo.db")
    try:
        conn = conectar_bd(ruta_db)
        conn.close()
        guardar_videos([_registro("a.mp4")], ruta_db)
        id_v = _video_id(ruta_db, "a.mp4")
        m = guardar_marcador(id_v, 7.0, ruta_db, color="rojo")
        guardar_nombre_color("rojo", "Carmesí", ruta_config)
        filas = listar_marcadores(id_v, ruta_db)
        ok_clave = filas == [(m, id_v, 7.0, "rojo")]
        ok_texto = texto_color("rojo", ruta_config) == "Carmesí"
        ok_renombrado_no_toca = (
            ok_clave
            and guardar_nombre_color("naranja", "Ámbar", ruta_config) == "Ámbar"
            and listar_marcadores(id_v, ruta_db) == [(m, id_v, 7.0, "rojo")]
        )
        return (
            ok_clave and ok_texto and ok_renombrado_no_toca,
            f"persistido={filas[0][3]} visible={texto_color('rojo', ruta_config)}",
        )
    finally:
        temp.cleanup()


def test_11():
    """TareaAsignarColorMarcador: éxito, id inexistente y clave inválida."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    errores = []
    try:
        id_v = _video_id(ruta_db, "a.mp4")
        m = guardar_marcador(id_v, 5.0, ruta_db)
        tarea = tv.TareaAsignarColorMarcador(m, "verde", ruta_db)
        ok_propiedades = (
            tarea.marcador_id == m
            and tarea.color == "verde"
            and tarea.ruta_db == ruta_db
        )
        ok_exito = tarea._trabajo() == (m, id_v, 5.0, "verde")
        ok_persiste = listar_marcadores(id_v, ruta_db) == [(m, id_v, 5.0, "verde")]
        ok_ausente = tv.TareaAsignarColorMarcador(
            999999, "rojo", ruta_db
        )._trabajo() is None
        ok_invalida = False
        try:
            tv.TareaAsignarColorMarcador(m, "magenta", ruta_db)._trabajo()
        except ValueError:
            ok_invalida = True
        return (
            ok_propiedades and ok_exito and ok_persiste
            and ok_ausente and ok_invalida,
            f"props={ok_propiedades} exito={ok_exito} persiste={ok_persiste} "
            f"ausente={ok_ausente} invalida={ok_invalida}",
        )
    finally:
        temp.cleanup()


def test_12():
    """TareaAsignarColorSegmento: éxito, id inexistente y clave inválida."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_v = _video_id(ruta_db, "a.mp4")
        s = guardar_segmento(id_v, 10.0, 20.0, ruta_db)
        tarea = tv.TareaAsignarColorSegmento(s[0], "azul", ruta_db)
        ok_propiedades = (
            tarea.segmento_id == s[0]
            and tarea.color == "azul"
            and tarea.ruta_db == ruta_db
        )
        ok_exito = tarea._trabajo() == (s[0], 10.0, 20.0, "azul")
        ok_persiste = listar_segmentos(id_v, ruta_db) == [(s[0], 10.0, 20.0, "azul")]
        ok_ausente = tv.TareaAsignarColorSegmento(
            999999, "verde", ruta_db
        )._trabajo() is None
        ok_invalida = False
        try:
            tv.TareaAsignarColorSegmento(s[0], "cyan", ruta_db)._trabajo()
        except ValueError:
            ok_invalida = True
        return (
            ok_propiedades and ok_exito and ok_persiste
            and ok_ausente and ok_invalida,
            f"props={ok_propiedades} exito={ok_exito} persiste={ok_persiste} "
            f"ausente={ok_ausente} invalida={ok_invalida}",
        )
    finally:
        temp.cleanup()


@contextlib.contextmanager
def _franja_mostrada(ancho=400, alto=224):
    contenedor = QWidget()
    layout = QVBoxLayout(contenedor)
    layout.setContentsMargins(0, 0, 0, 0)
    franja = FranjaExploracion()
    layout.addWidget(franja)
    contenedor.resize(ancho, alto)
    contenedor.show()
    QApplication.processEvents()
    franja.set_duracion(100.0)
    franja.set_instante(None)
    try:
        yield franja
    finally:
        contenedor.close()
        franja.deleteLater()
        contenedor.deleteLater()
        for _ in range(3):
            QApplication.processEvents()


def _y_pista(franja):
    return _MARGEN + franja.fontMetrics().height() + 4


def _pixel_marca(franja, tiempo):
    imagen = franja.grab().toImage()
    dpr = franja.devicePixelRatioF() or 1.0
    x = int(tiempo_a_posicion(tiempo, franja.width(), franja.duracion()) * dpr)
    y = int(((_MARGEN - 2 + (_y_pista(franja) - 2)) / 2) * dpr)
    return imagen.pixelColor(x, y)


def _pixel_banda(franja, inicio, fin):
    imagen = franja.grab().toImage()
    dpr = franja.devicePixelRatioF() or 1.0
    y = int((_y_pista(franja) + _ALTO_PISTA // 2) * dpr)
    x1 = tiempo_a_posicion(inicio, franja.width(), franja.duracion()) * dpr
    x2 = tiempo_a_posicion(fin, franja.width(), franja.duracion()) * dpr
    return imagen.pixelColor(int((x1 + x2) / 2), y)


def test_13():
    """Render marcador: color de paleta vs NULL (gris neutro B6.5)."""
    from scrubber import _COLOR_MARCA_SIN
    from escanear_videos import COLORES_CLASIFICACION
    from PySide6.QtGui import QColor
    with _franja_mostrada() as franja:
        franja.set_marcadores([50.0], {50.0: "verde"})
        verde = _pixel_marca(franja, 50.0)
        ok_verde = verde.green() > verde.red() and verde.green() > verde.blue()
        franja.set_marcadores([60.0])
        gris_null = _pixel_marca(franja, 60.0)
        gris = _COLOR_MARCA_SIN
        ok_gris = gris_null.name() == gris.name() or (abs(gris_null.red()-gris.red())<8 and abs(gris_null.green()-gris.green())<8 and abs(gris_null.blue()-gris.blue())<8)
        ok_no_rojo = not (gris_null.red() > gris_null.green() and gris_null.red() > gris_null.blue())
        paleta = [QColor(r,g,b) for _,r,g,b in COLORES_CLASIFICACION]
        ok_no_paleta = all(gris_null.name()!=c.name() for c in paleta)
        ok = ok_verde and ok_gris and ok_no_rojo and ok_no_paleta
        return (
            ok,
            f"verde={verde.name()} gris_null={gris_null.name()} gris_esperado={gris.name()}",
        )


def test_14():
    """Render segmento: color de paleta vs NULL (gris neutro B6.5)."""
    from scrubber import _COLOR_SEGMENTO_SIN, _COLOR_SEGMENTO_SIN_BORDE
    from escanear_videos import COLORES_CLASIFICACION
    from PySide6.QtGui import QColor
    with _franja_mostrada() as franja:
        franja.set_segmentos(
            [{"id": 1, "inicio": 20.0, "fin": 80.0, "color": "verde"}]
        )
        verde = _pixel_banda(franja, 20.0, 80.0)
        ok_verde = verde.green() > verde.blue() and verde.green() > verde.red()
        franja.set_segmentos([{"id": 2, "inicio": 20.0, "fin": 80.0}])
        gris_null = _pixel_banda(franja, 20.0, 80.0)
        gris = _COLOR_SEGMENTO_SIN
        # fondo gris con alfa 120 puede mezclar con pista, tolerancia
        ok_gris = gris_null.blue() == gris_null.red() == gris_null.green() or (abs(gris_null.red()-gris.red())<30 and gris_null.red()==gris_null.green())
        ok_no_azul = not (gris_null.blue() > gris_null.red() and gris_null.blue() > gris_null.green())
        paleta = [QColor(r,g,b) for _,r,g,b in COLORES_CLASIFICACION]
        # segmento gris no debe ser ningún color de paleta saturado
        ok_no_paleta = gris_null.red()==gris_null.green()==gris_null.blue()
        ok = ok_verde and ok_gris and ok_no_azul and ok_no_paleta
        return (
            ok,
            f"verde={verde.name()} gris_null={gris_null.name()} gris_esperado={gris.name()}",
        )


def test_15():
    """Selector de color en la tarjeta: ítems, datos y color activo."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            selector = tarjeta._selector_color
            textos = [selector.itemText(i) for i in range(selector.count())]
            datos = [selector.itemData(i) for i in range(selector.count())]
            ok_items = (
                textos[0] == "Sin clasificar"
                and datos[0] is None
                and textos[1:] == [
                    "Rojo", "Naranja", "Amarillo", "Verde", "Azul", "Violeta"
                ]
                and datos[1:] == [
                    "rojo", "naranja", "amarillo", "verde", "azul", "violeta"
                ]
            )
            selector.setCurrentIndex(selector.findData("rojo"))
            ok_activo = tarjeta._color_activo == "rojo"
            selector.setCurrentIndex(0)
            ok_sin = tarjeta._color_activo is None
            return (
                ok_items and ok_activo and ok_sin,
                f"items={textos} datos={datos} color_activo={tarjeta._color_activo}",
            )
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()


def test_16():
    """Menú de marcador: submenú accionable tras gc.collect y persistencia."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            franja = tarjeta._franja
            ancho = franja.width()
            marcador = _crear_marcador_persistido(ventana, tarjeta, ancho * 0.5)
            if marcador is None:
                return False, "no se creo el marcador"
            id_m = marcador["id"]
            tarjeta._menu_marcador_actual = None
            _press_derecho(franja, ancho * 0.5)
            if not _esperar(
                lambda: tarjeta._menu_marcador_actual is not None
            ):
                return False, "no abrio el menu de marcador"
            gc.collect()
            menu = tarjeta._menu_marcador_actual
            sub = tarjeta._submenu_marcador_color_actual
            accion = _accion_de_submenu(menu, "Asignar color", "Verde")
            ok_vivo = sub is not None and accion is not None
            ops_capturadas = []
            original_encolar = ventana._encolar_marcador

            def _capturar_marcador(op):
                ops_capturadas.append(op)
                return original_encolar(op)

            ventana._encolar_marcador = _capturar_marcador
            try:
                accion.trigger()
                QApplication.processEvents()
                ok_ram = marcador.get("color") == "verde"
                ok_op = any(
                    op.get("tipo") == "color"
                    and op.get("marcador_id") == id_m
                    and op.get("color") == "verde"
                    and op.get("color_previo") is None
                    for op in ops_capturadas
                )
            finally:
                ventana._encolar_marcador = original_encolar
            ok_drena = _drenar_marcadores(ventana)
            filas = listar_marcadores(id_m, ruta_db)
            ok_persiste = filas == [(id_m, tarjeta._video_id, marcador["tiempo"], "verde")]
            return (
                ok_vivo and ok_ram and ok_op and ok_drena and ok_persiste,
                f"vivo={ok_vivo} ram={ok_ram} op={ok_op} drena={ok_drena} "
                f"persiste={ok_persiste} filas={filas}",
            )
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()


def test_17():
    """Menú de segmento: submenú accionable tras gc.collect y persistencia."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            franja = tarjeta._franja
            ancho = franja.width()
            x1 = ancho * 0.2
            x2 = ancho * 0.8
            segmento = _crear_segmento_persistido(ventana, tarjeta, x1, x2)
            if segmento is None:
                return False, "no se creo el segmento"
            id_s = segmento["id"]
            x_medio = (x1 + x2) / 2
            tarjeta._menu_segmento_actual = None
            _press_derecho(franja, x_medio)
            _esperar(lambda: tarjeta._menu_segmento_actual is not None)
            gc.collect()
            menu = tarjeta._menu_segmento_actual
            sub = tarjeta._submenu_segmento_color_actual
            accion = _accion_de_submenu(menu, "Asignar color", "Naranja")
            ok_vivo = sub is not None and accion is not None
            ops_capturadas = []
            original_encolar = ventana._encolar_segmento

            def _capturar_segmento(op):
                ops_capturadas.append(op)
                return original_encolar(op)

            ventana._encolar_segmento = _capturar_segmento
            try:
                accion.trigger()
                QApplication.processEvents()
                ok_ram = segmento.get("color") == "naranja"
                ok_op = any(
                    op.get("tipo") == "color"
                    and op.get("segmento_id") == id_s
                    and op.get("color") == "naranja"
                    for op in ops_capturadas
                )
            finally:
                ventana._encolar_segmento = original_encolar
            ok_drena = _drenar_segmentos(ventana)
            ok_persiste = listar_segmentos(id_s, ruta_db) == [
                (id_s, segmento["inicio"], segmento["fin"], "naranja")
            ]
            tarjeta._menu_segmento_actual = None
            _press_derecho(franja, x_medio)
            _esperar(lambda: tarjeta._menu_segmento_actual is not None)
            gc.collect()
            menu2 = tarjeta._menu_segmento_actual
            accion_quitar = _accion_de_submenu(
                menu2, "Asignar color", "Sin clasificar"
            )
            ok_quitar_habil = accion_quitar is not None and accion_quitar.isEnabled()
            accion_quitar.trigger()
            QApplication.processEvents()
            _drenar_segmentos(ventana)
            ok_quitar = segmento.get("color") is None
            ok_persiste_nulo = listar_segmentos(id_s, ruta_db) == [
                (id_s, segmento["inicio"], segmento["fin"], None)
            ]
            return (
                ok_vivo and ok_ram and ok_op and ok_drena and ok_persiste
                and ok_quitar_habil and ok_quitar and ok_persiste_nulo,
                f"vivo={ok_vivo} ram={ok_ram} op={ok_op} drena={ok_drena} "
                f"persiste={ok_persiste} quitar_habil={ok_quitar_habil} "
                f"quitar={ok_quitar} nulo={ok_persiste_nulo}",
            )
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()


def test_18():
    """Marcador: cambiar de color y dejarlo Sin clasificar."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            franja = tarjeta._franja
            ancho = franja.width()
            x = ancho * 0.4
            marcador = _crear_marcador_persistido(ventana, tarjeta, x)
            if marcador is None:
                return False, "no se creo el marcador"
            id_m = marcador["id"]
            video_id = tarjeta._video_id
            tiempo = marcador["tiempo"]

            tarjeta._menu_marcador_actual = None
            _press_derecho(franja, x)
            _esperar(lambda: tarjeta._menu_marcador_actual is not None)
            gc.collect()
            acc = _accion_de_submenu(
                tarjeta._menu_marcador_actual, "Asignar color", "Rojo"
            )
            acc.trigger()
            QApplication.processEvents()
            _drenar_marcadores(ventana)
            ok_rojo = marcador.get("color") == "rojo"

            tarjeta._menu_marcador_actual = None
            _press_derecho(franja, x)
            _esperar(lambda: tarjeta._menu_marcador_actual is not None)
            gc.collect()
            acc2 = _accion_de_submenu(
                tarjeta._menu_marcador_actual, "Asignar color", "Verde"
            )
            acc2.trigger()
            QApplication.processEvents()
            _drenar_marcadores(ventana)
            ok_verde = marcador.get("color") == "verde"

            tarjeta._menu_marcador_actual = None
            _press_derecho(franja, x)
            _esperar(lambda: tarjeta._menu_marcador_actual is not None)
            gc.collect()
            acc3 = _accion_de_submenu(
                tarjeta._menu_marcador_actual, "Asignar color", "Sin clasificar"
            )
            ok_habil = acc3 is not None and acc3.isEnabled()
            acc3.trigger()
            QApplication.processEvents()
            ok_sin = marcador.get("color") is None
            ok_drena = _drenar_marcadores(ventana)
            ok_persiste = listar_marcadores(id_m, ruta_db) == [
                (id_m, video_id, tiempo, None)
            ]
            return (
                ok_rojo and ok_verde and ok_habil and ok_sin
                and ok_drena and ok_persiste,
                f"rojo={ok_rojo} verde={ok_verde} habil={ok_habil} "
                f"sin={ok_sin} drena={ok_drena} persiste={ok_persiste}",
            )
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()


def test_19():
    """Restauración del color persistido al recargar (marcador y segmento)."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            ventana = _abrir_ventana(ruta_db)
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                _expandir(tarjeta)
                franja = tarjeta._franja
                ancho = franja.width()
                marcador = _crear_marcador_persistido(
                    ventana, tarjeta, ancho * 0.5
                )
                segmento = _crear_segmento_persistido(
                    ventana, tarjeta, ancho * 0.2, ancho * 0.8
                )
                if marcador is None or segmento is None:
                    return False, "no se crearon marcador/segmento"
                id_m = marcador["id"]
                id_s = segmento["id"]
                asignar_color_marcador(id_m, "violeta", ruta_db)
                asignar_color_segmento(id_s, "verde", ruta_db)
            finally:
                ventana.close()
                _limpiar(ventana)

            ventana2 = _abrir_ventana(ruta_db)
            try:
                tarjeta2 = dict(ventana2.tarjetas)["a.mp4"]
                _expandir(tarjeta2)
                _drenar_marcadores(ventana2)
                _drenar_segmentos(ventana2)
                ok_m = any(
                    m.get("color") == "violeta"
                    for m in tarjeta2._marcadores
                )
                ok_s = any(
                    seg.get("color") == "verde"
                    for seg in tarjeta2._segmentos
                )
                ok_franja_colores = any(
                    v == "violeta"
                    for _t, v in tarjeta2._franja._marcador_colores.items()
                )
                return (
                    ok_m and ok_s and ok_franja_colores,
                    f"marcador_color={ok_m} segmento_color={ok_s} "
                    f"franja_colores={tarjeta2._franja._marcador_colores}",
                )
            finally:
                ventana2.close()
                _limpiar(ventana2)
        finally:
            temp.cleanup()


def test_20():
    """Rollback visual ante error de persistencia (marcador y segmento)."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            franja = tarjeta._franja
            ancho = franja.width()
            x_m = ancho * 0.95
            x1 = ancho * 0.2
            x2 = ancho * 0.8
            marcador = _crear_marcador_persistido(ventana, tarjeta, x_m)
            segmento = _crear_segmento_persistido(ventana, tarjeta, x1, x2)
            if marcador is None or segmento is None:
                return False, "no se crearon marcador/segmento"
            id_m = marcador["id"]
            id_s = segmento["id"]

            original_m = tv.asignar_color_marcador
            original_s = tv.asignar_color_segmento

            def _falla_m(*args, **kwargs):
                raise OSError("falla simulada marcador")

            def _falla_s(*args, **kwargs):
                raise OSError("falla simulada segmento")

            tv.asignar_color_marcador = _falla_m
            try:
                tarjeta._menu_marcador_actual = None
                _press_derecho(franja, x_m)
                _esperar(lambda: tarjeta._menu_marcador_actual is not None)
                gc.collect()
                acc = _accion_de_submenu(
                    tarjeta._menu_marcador_actual, "Asignar color", "Rojo"
                )
                acc.trigger()
                QApplication.processEvents()
                ok_drena_m = _drenar_marcadores(ventana)
                ok_rollback_m = marcador.get("color") is None
                ok_msg_m = "No se pudo asignar el color del marcador" in ventana.mensaje_carpeta.text()
                ok_db_m = listar_marcadores(id_m, ruta_db) == [
                    (id_m, tarjeta._video_id, marcador["tiempo"], None)
                ]
            finally:
                tv.asignar_color_marcador = original_m

            tv.asignar_color_segmento = _falla_s
            try:
                x_medio = (x1 + x2) / 2
                tarjeta._menu_segmento_actual = None
                _press_derecho(franja, x_medio)
                _esperar(lambda: tarjeta._menu_segmento_actual is not None)
                gc.collect()
                acc2 = _accion_de_submenu(
                    tarjeta._menu_segmento_actual, "Asignar color", "Verde"
                )
                acc2.trigger()
                QApplication.processEvents()
                ok_drena_s = _drenar_segmentos(ventana)
                ok_rollback_s = segmento.get("color") is None
                ok_msg_s = "No se pudo asignar el color del segmento" in ventana.mensaje_carpeta.text()
                ok_db_s = listar_segmentos(id_s, ruta_db) == [
                    (id_s, segmento["inicio"], segmento["fin"], None)
                ]
            finally:
                tv.asignar_color_segmento = original_s

            return (
                ok_drena_m and ok_rollback_m and ok_msg_m and ok_db_m
                and ok_drena_s and ok_rollback_s and ok_msg_s and ok_db_s,
                f"marcador: rollback={ok_rollback_m} msg={ok_msg_m} db={ok_db_m} "
                f"segmento: rollback={ok_rollback_s} msg={ok_msg_s} db={ok_db_s}",
            )
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()


def test_21():
    """`QLineEdit` de colores en Preferencias limita la longitud."""
    from visor_videos import PreferenciasDialog
    from PySide6.QtWidgets import QDialogButtonBox
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        dialogo = None
        try:
            dialogo = PreferenciasDialog(parent=ventana)
            cajas = dialogo._cajas_color
            ok_cajas = (
                set(cajas) == set(CLAVES_COLOR_CLASIFICACION)
                and all(
                    isinstance(c, QLineEdit)
                    and c.maxLength() == LIMITE_LONGITUD_NOMBRE_COLOR
                    for c in cajas.values()
                )
            )
            dialogo.reject()
            return ok_cajas, f"cajas={sorted(cajas)}"
        finally:
            if dialogo is not None:
                dialogo.deleteLater()
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()


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
    print(f"TOTAL={aprobadas}/{len(pruebas)}")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())