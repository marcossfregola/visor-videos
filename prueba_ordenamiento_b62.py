import json
import os
import py_compile
import sqlite3
import sys
import tempfile
import threading
import time

from PySide6.QtCore import QThread, qInstallMessageHandler
from PySide6.QtWidgets import QApplication

import escanear_videos as escanear_mod
import tareas_videos as tv
from configuracion import (
    CLAVE_ORDEN_CRITERIO,
    CLAVE_ORDEN_DIRECCION,
    guardar_orden_catalogo,
    obtener_orden_catalogo,
)
from escanear_videos import (
    ORDEN_CRITERIO_DEFAULT,
    ORDEN_CRITERIOS,
    ORDEN_DIRECCION_DEFAULT,
    ORDEN_DIRECCIONES,
    fragmento_orden_sql,
)
from tareas_videos import TareaLecturaCatalogoPaginada
from visor_videos import TAMANIO_PAGINA_INICIAL, ESTILO_SELECCIONADA, VisorVideos

QT_MENSAJES = []


def _mensaje_qt(tipo, contexto, texto):
    QT_MENSAJES.append(str(texto))


qInstallMessageHandler(_mensaje_qt)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _fila(nombre, fecha, duracion, ancho, alto, codec, cantidad, tamano):
    return (
        nombre,
        os.path.join("C:\\", nombre),
        os.path.splitext(nombre)[1].lower(),
        fecha,
        duracion,
        ancho,
        alto,
        codec,
        cantidad,
        tamano,
    )


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
            "INSERT INTO videos (nombre, ruta, extension, fecha_importacion, "
            "duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas, "
            "tamano_bytes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            filas,
        )
        conn.commit()
    finally:
        conn.close()
    return temp, ruta_db


BASE = [
    _fila("zeta.mp4", "2026-01-10T00:00:00", 90.0, 1920, 1080, "h264", 3, 5000),
    _fila("alfa.mp4", "2026-03-20T00:00:00", 30.0, 640, 480, "h265", 2, 1200),
    _fila("beta.mkv", "2026-02-15T00:00:00", 60.0, 1280, 720, "av1", 1, 3000),
    _fila("nulo.mp4", "2026-04-01T00:00:00", None, None, None, None, 0, None),
    _fila("tie1.mp4", "2026-05-05T00:00:00", 45.0, 800, 600, "h264", 4, 2000),
    _fila("tie2.mp4", "2026-05-05T00:00:00", 45.0, 800, 600, "h264", 5, 2000),
]

# Orden esperado (nombres) por criterio y dirección para el fixture BASE.
# `nulo.mp4` tiene NULL en duracion/resolucion/codec/tamano: siempre al final.
EXPECTADOS = {
    ("nombre", "asc"): [
        "alfa.mp4", "beta.mkv", "nulo.mp4", "tie1.mp4", "tie2.mp4", "zeta.mp4",
    ],
    ("nombre", "desc"): [
        "zeta.mp4", "tie2.mp4", "tie1.mp4", "nulo.mp4", "beta.mkv", "alfa.mp4",
    ],
    ("duracion", "asc"): [
        "alfa.mp4", "tie1.mp4", "tie2.mp4", "beta.mkv", "zeta.mp4", "nulo.mp4",
    ],
    ("duracion", "desc"): [
        "zeta.mp4", "beta.mkv", "tie1.mp4", "tie2.mp4", "alfa.mp4", "nulo.mp4",
    ],
    ("resolucion", "asc"): [
        "alfa.mp4", "tie1.mp4", "tie2.mp4", "beta.mkv", "zeta.mp4", "nulo.mp4",
    ],
    ("resolucion", "desc"): [
        "zeta.mp4", "beta.mkv", "tie1.mp4", "tie2.mp4", "alfa.mp4", "nulo.mp4",
    ],
    ("codec", "asc"): [
        "beta.mkv", "zeta.mp4", "tie1.mp4", "tie2.mp4", "alfa.mp4", "nulo.mp4",
    ],
    ("codec", "desc"): [
        "alfa.mp4", "zeta.mp4", "tie1.mp4", "tie2.mp4", "beta.mkv", "nulo.mp4",
    ],
    ("tamano", "asc"): [
        "alfa.mp4", "tie1.mp4", "tie2.mp4", "beta.mkv", "zeta.mp4", "nulo.mp4",
    ],
    ("tamano", "desc"): [
        "zeta.mp4", "beta.mkv", "tie1.mp4", "tie2.mp4", "alfa.mp4", "nulo.mp4",
    ],
    ("fecha_importacion", "asc"): [
        "zeta.mp4", "beta.mkv", "alfa.mp4", "nulo.mp4", "tie1.mp4", "tie2.mp4",
    ],
    ("fecha_importacion", "desc"): [
        "tie1.mp4", "tie2.mp4", "nulo.mp4", "alfa.mp4", "beta.mkv", "zeta.mp4",
    ],
}


def _nombres(resultado):
    return [fila[0] for fila in resultado["videos"]]


def _nombres_con(tamano, prefijo="v"):
    return [f"{prefijo}{i:03d}.mp4" for i in range(1, tamano + 1)]


def _filas_serie(nombres):
    filas = []
    for i, nombre in enumerate(nombres, start=1):
        filas.append(
            _fila(
                nombre,
                "2026-06-01T00:00:00",
                float(i),
                1920,
                1080,
                "h264",
                1,
                i * 10,
            )
        )
    return filas


def _crear_bd_serie(tamano):
    nombres = _nombres_con(tamano)
    return _crear_bd(_filas_serie(nombres))


def _crear_config(temp):
    return os.path.join(temp.name, "config.json")


class _ControlLectura:
    def __init__(self, fn):
        self.fn = fn
        self.llamadas = 0
        self.empezada = threading.Event()
        self.soltar = threading.Event()
        self.ident = None
        self.kwargs_vistos = []

    def __call__(self, *args, **kwargs):
        self.llamadas += 1
        self.kwargs_vistos.append(dict(kwargs))
        self.ident = threading.get_ident()
        if self.llamadas == 1:
            self.empezada.set()
            self.soltar.wait(10)
        return self.fn(*args, **kwargs)


def _esperar(predicado, timeout_ms=8000, paso_ms=20):
    fin = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < fin:
        QApplication.processEvents()
        if predicado():
            return True
        time.sleep(paso_ms / 1000)
    QApplication.processEvents()
    return predicado()


def _idle(ventana):
    return (
        ventana.gestor.hilo is None
        and not ventana._reordenamiento_pendiente
        and not ventana._recarga_catalogo_pendiente
        and not ventana._pagina_pendiente
    )


def _limpiar(ventana):
    if ventana is None:
        return
    if ventana.gestor.hilo is not None:
        ventana.gestor.cerrar()
    ventana.close()
    ventana.deleteLater()
    for _ in range(5):
        QApplication.processEvents()


def _cambiar_orden(ventana, clave, direccion):
    indice = ventana.combo_orden_criterio.findData(clave)
    if indice >= 0:
        ventana.combo_orden_criterio.setCurrentIndex(indice)
    indice_dir = ventana.combo_orden_direccion.findData(direccion)
    if indice_dir >= 0:
        ventana.combo_orden_direccion.setCurrentIndex(indice_dir)


def _referencia(ruta_db, clave, direccion, texto=None, limite=1000, desplazamiento=0):
    return escanear_mod.listar_videos_paginado(
        limite,
        desplazamiento,
        texto,
        ruta_db,
        orden_clave=clave,
        orden_direccion=direccion,
    )


# ---------------------------------------------------------------------------
# Pruebas
# ---------------------------------------------------------------------------

def test_01():
    modulos = [
        "escanear_videos.py",
        "tareas_videos.py",
        "configuracion.py",
        "visor_videos.py",
        "prueba_ordenamiento_b62.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    temp, ruta_db = _crear_bd(BASE)
    try:
        resultado = escanear_mod.listar_videos_paginado(100, 0, None, ruta_db)
        ok = (
            _nombres(resultado) == EXPECTADOS[("nombre", "asc")]
            and resultado["total"] == 6
            and set(resultado.keys()) == {"videos", "total", "limite", "desplazamiento"}
        )
        return ok, f"nombres={_nombres(resultado)}"
    finally:
        temp.cleanup()


def test_03():
    temp, ruta_db = _crear_bd(BASE)
    try:
        casos = [
            ("clave_desconocida", fragmento_orden_sql, ("xyz", "asc"), ValueError),
            ("direccion_desconocida", fragmento_orden_sql, ("nombre", "diagonal"), ValueError),
            ("clave_no_texto", fragmento_orden_sql, (123, "asc"), TypeError),
            ("direccion_no_texto", fragmento_orden_sql, ("nombre", None), TypeError),
        ]
        resultados = []
        ok = True
        for etiqueta, fn, args, esperado in casos:
            try:
                fn(*args)
                ok = False
                resultados.append(f"{etiqueta}=sin_error")
            except esperado:
                resultados.append(f"{etiqueta}=ok")
            except Exception as exc:
                ok = False
                resultados.append(f"{etiqueta}={type(exc).__name__}")
        for etiqueta, fn, args, esperado in [
            ("listar_clave", escanear_mod.listar_videos_paginado, (100, 0, None, ruta_db, "zzz", "asc"), ValueError),
            ("listar_direccion", escanear_mod.listar_videos_paginado, (100, 0, None, ruta_db, "nombre", "up"), ValueError),
            ("listar_clave_tipo", escanear_mod.listar_videos_paginado, (100, 0, None, ruta_db, 5, "asc"), TypeError),
            ("listar_direccion_tipo", escanear_mod.listar_videos_paginado, (100, 0, None, ruta_db, "nombre", ["asc"]), TypeError),
        ]:
            try:
                fn(*args)
                ok = False
                resultados.append(f"{etiqueta}=sin_error")
            except esperado:
                resultados.append(f"{etiqueta}=ok")
            except Exception as exc:
                ok = False
                resultados.append(f"{etiqueta}={type(exc).__name__}")
        valido = escanear_mod.listar_videos_paginado(
            100, 0, None, ruta_db, orden_clave="nombre", orden_direccion="asc"
        )
        ok = ok and len(valido["videos"]) == 6
        fin = fragmento_orden_sql("nombre", "asc")
        ok = ok and fin.endswith("id ASC")
        return ok, "; ".join(resultados) + f" | valido={len(valido['videos'])} fin={fin!r}"
    finally:
        temp.cleanup()


def test_04():
    temp, ruta_db = _crear_bd(BASE)
    try:
        fallidos = []
        for (clave, direccion), esperado in EXPECTADOS.items():
            resultado = escanear_mod.listar_videos_paginado(
                100, 0, None, ruta_db, orden_clave=clave, orden_direccion=direccion
            )
            nombres = _nombres(resultado)
            if (
                nombres != esperado
                or resultado["total"] != 6
                or set(resultado.keys()) != {"videos", "total", "limite", "desplazamiento"}
            ):
                fallidos.append(f"{clave}/{direccion}={nombres}")
        return (not fallidos), "fallidos=" + ("; ".join(fallidos) if fallidos else "ninguno")
    finally:
        temp.cleanup()


def test_05():
    temp, ruta_db = _crear_bd(BASE)
    try:
        # Solo criterios donde tie1/tie2 comparten el mismo valor de orden
        # (en "nombre" los nombres difieren y el desempate no participa).
        criterios_empate = [
            "duracion", "resolucion", "codec", "tamano", "fecha_importacion",
        ]
        fallidos = []
        for clave in criterios_empate:
            for direccion in ORDEN_DIRECCIONES:
                resultado = escanear_mod.listar_videos_paginado(
                    100, 0, None, ruta_db, orden_clave=clave, orden_direccion=direccion
                )
                pos_tie1 = [fila[0] for fila in resultado["videos"]].index("tie1.mp4")
                pos_tie2 = [fila[0] for fila in resultado["videos"]].index("tie2.mp4")
                id_tie1 = resultado["videos"][pos_tie1][-1]
                id_tie2 = resultado["videos"][pos_tie2][-1]
                if not (pos_tie1 < pos_tie2 and id_tie1 < id_tie2):
                    fallidos.append(f"{clave}/{direccion}: tie1={id_tie1}@{pos_tie1} tie2={id_tie2}@{pos_tie2}")
        return (not fallidos), "; ".join(fallidos) if fallidos else "tie-break id ASC estable"
    finally:
        temp.cleanup()


def test_06():
    temp, ruta_db = _crear_bd(BASE)
    try:
        criterios_nulos = ["duracion", "resolucion", "codec", "tamano"]
        fallidos = []
        for clave in criterios_nulos:
            for direccion in ORDEN_DIRECCIONES:
                resultado = escanear_mod.listar_videos_paginado(
                    100, 0, None, ruta_db, orden_clave=clave, orden_direccion=direccion
                )
                nombres = _nombres(resultado)
                if nombres[-1] != "nulo.mp4":
                    fallidos.append(f"{clave}/{direccion}: ultimo={nombres[-1]}")
        return (not fallidos), "; ".join(fallidos) if fallidos else "NULL siempre al final"
    finally:
        temp.cleanup()


def test_07():
    filas = [
        _fila("A.mp4", "2026-07-01T00:00:00", 1.0, 1200, 400, "c", 1, 100),
        _fila("B.mp4", "2026-07-02T00:00:00", 2.0, 640, 900, "c", 1, 200),
    ]
    temp, ruta_db = _crear_bd(filas)
    try:
        asc = _nombres(escanear_mod.listar_videos_paginado(
            100, 0, None, ruta_db, orden_clave="resolucion", orden_direccion="asc"
        ))
        desc = _nombres(escanear_mod.listar_videos_paginado(
            100, 0, None, ruta_db, orden_clave="resolucion", orden_direccion="desc"
        ))
        # A: 1200*400=480000 ; B: 640*900=576000. Si se ordenara por ancho solo,
        # B (640) precederia a A (1200). El orden por producto da A antes que B.
        ok = asc == ["A.mp4", "B.mp4"] and desc == ["B.mp4", "A.mp4"]
        return ok, f"asc={asc} desc={desc}"
    finally:
        temp.cleanup()


def test_08():
    temp, ruta_db = _crear_bd(BASE)
    try:
        fallidos = []
        for clave, direccion in [
            (c, d) for c in ORDEN_CRITERIOS for d in ORDEN_DIRECCIONES
        ]:
            concatenados = []
            desplazamiento = 0
            totales = []
            while True:
                pagina = escanear_mod.listar_videos_paginado(
                    2, desplazamiento, None, ruta_db,
                    orden_clave=clave, orden_direccion=direccion,
                )
                totales.append(pagina["total"])
                if not pagina["videos"]:
                    break
                concatenados.extend(_nombres(pagina))
                desplazamiento += 2
            completo = _nombres(_referencia(ruta_db, clave, direccion))
            if (
                concatenados != completo
                or len(concatenados) != len(set(concatenados))
                or len(concatenados) != 6
                or set(totales) != {6}
            ):
                fallidos.append(f"{clave}/{direccion}: {concatenados}")
        return (not fallidos), "; ".join(fallidos) if fallidos else "sin duplicados ni saltos por criterio"
    finally:
        temp.cleanup()


def test_09():
    temp, ruta_db = _crear_bd(BASE)
    try:
        resultado = escanear_mod.listar_videos_paginado(
            100, 0, "mp4", ruta_db, orden_clave="duracion", orden_direccion="desc"
        )
        esperado = ["zeta.mp4", "tie1.mp4", "tie2.mp4", "alfa.mp4", "nulo.mp4"]
        ok = (
            _nombres(resultado) == esperado
            and resultado["total"] == 5
        )
        return ok, f"videos={_nombres(resultado)} total={resultado['total']}"
    finally:
        temp.cleanup()


def test_10():
    temp = tempfile.TemporaryDirectory()
    try:
        ruta_config = _crear_config(temp)
        guardar_orden_catalogo("duracion", "desc", ruta_config)
        persistido = obtener_orden_catalogo(ruta_config)
        sin_config = obtener_orden_catalogo(os.path.join(temp.name, "otra.json"))
        invalido = guardar_orden_catalogo("no_existe", "asc", ruta_config)
        invalido_dir = guardar_orden_catalogo("nombre", "de_lado", ruta_config)
        tras_invalidos = obtener_orden_catalogo(ruta_config)
        guardar_orden_catalogo("nombre", "asc", ruta_config)
        ok = (
            persistido == ("duracion", "desc")
            and sin_config == (ORDEN_CRITERIO_DEFAULT, ORDEN_DIRECCION_DEFAULT)
            and invalido is None
            and invalido_dir is None
            and tras_invalidos == ("duracion", "desc")
            and obtener_orden_catalogo(ruta_config) == ("nombre", "asc")
        )
        # Config existente pero con valores inválidos: fallback.
        with open(ruta_config, "w", encoding="utf-8") as f:
            json.dump(
                {CLAVE_ORDEN_CRITERIO: 7, CLAVE_ORDEN_DIRECCION: "desc"},
                f,
            )
        ok = ok and obtener_orden_catalogo(ruta_config) == ("nombre", "desc")
        with open(ruta_config, "w", encoding="utf-8") as f:
            json.dump({"otra_clave": 1}, f)
        ok = ok and obtener_orden_catalogo(ruta_config) == (
            ORDEN_CRITERIO_DEFAULT,
            ORDEN_DIRECCION_DEFAULT,
        )
        return ok, f"persistido={persistido} sin_config={sin_config} fallback_ok={ok}"
    finally:
        temp.cleanup()


def test_11():
    temp, ruta_db = _crear_bd(BASE)
    try:
        tarea = TareaLecturaCatalogoPaginada(
            3, 1, None, ruta_db, orden_clave="duracion", orden_direccion="desc"
        )
        ok = (
            tarea.limite == 3
            and tarea.desplazamiento == 1
            and tarea.texto is None
            and tarea.ruta_db == ruta_db
            and tarea.orden_clave == "duracion"
            and tarea.orden_direccion == "desc"
        )
        capturado = {}
        original = tv.listar_videos_paginado

        def _espia(*args, **kwargs):
            capturado["args"] = args
            capturado["kwargs"] = kwargs
            return {"videos": [], "total": 0, "limite": args[0], "desplazamiento": args[1]}

        tv.listar_videos_paginado = _espia
        try:
            tarea._trabajo()
        finally:
            tv.listar_videos_paginado = original
        ok = (
            ok
            and capturado["args"] == (3, 1, None, ruta_db)
            and capturado["kwargs"]
            == {"orden_clave": "duracion", "orden_direccion": "desc"}
        )
        tarea_default = TareaLecturaCatalogoPaginada(3, 1, None, ruta_db)
        tv.listar_videos_paginado = _espia
        try:
            tarea_default._trabajo()
        finally:
            tv.listar_videos_paginado = original
        ok = ok and capturado["kwargs"] == {"orden_clave": None, "orden_direccion": None}
        return ok, f"args={capturado['args']} kwargs={capturado['kwargs']}"
    finally:
        temp.cleanup()


def test_12():
    temp, ruta_db = _crear_bd_serie(150)
    try:
        ruta_config = _crear_config(temp)
        ventana = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        default_ok = (
            ventana._orden_catalogo == ("nombre", "asc")
            and ventana.combo_orden_criterio.currentData() == "nombre"
            and ventana.combo_orden_direccion.currentData() == "asc"
            and [n for n, _ in ventana.tarjetas][0] == "v001.mp4"
            and len(ventana.tarjetas) == TAMANIO_PAGINA_INICIAL
        )
        _cambiar_orden(ventana, "duracion", "desc")
        _esperar(lambda v=ventana: _idle(v))
        nombres = [n for n, _ in ventana.tarjetas]
        esperado = _nombres(_referencia(ruta_db, "duracion", "desc", limite=TAMANIO_PAGINA_INICIAL))
        with open(ruta_config, encoding="utf-8") as f:
            config = json.load(f)
        ok = (
            default_ok
            and ventana._orden_catalogo == ("duracion", "desc")
            and config.get(CLAVE_ORDEN_CRITERIO) == "duracion"
            and config.get(CLAVE_ORDEN_DIRECCION) == "desc"
            and len(nombres) == TAMANIO_PAGINA_INICIAL
            and nombres == esperado
            and nombres[0] == "v150.mp4"
        )
        _limpiar(ventana)
        return ok, f"default={default_ok} nombres[0]={nombres[0]} len={len(nombres)} esperado[0]={esperado[0]}"
    finally:
        temp.cleanup()


def test_13():
    temp, ruta_db = _crear_bd_serie(8)
    try:
        ruta_config = _crear_config(temp)
        ventana = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        ventana._al_seleccionar_tarjeta("v003.mp4", False)
        seleccion_antes = "v003.mp4" in ventana._nombres_seleccionados
        _cambiar_orden(ventana, "duracion", "desc")
        _esperar(lambda v=ventana: _idle(v))
        tarjeta = ventana._tarjeta_por_nombre("v003.mp4")
        ok = (
            seleccion_antes
            and "v003.mp4" in ventana._nombres_seleccionados
            and tarjeta is not None
            and tarjeta._seleccionada
            and ESTILO_SELECCIONADA in tarjeta.styleSheet()
        )
        _limpiar(ventana)
        return ok, f"seleccion_antes={seleccion_antes} conservada={ok}"
    finally:
        temp.cleanup()


def test_14():
    temp, ruta_db = _crear_bd_serie(150)
    try:
        ruta_config = _crear_config(temp)
        ventana = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        ventana.resize(400, 300)
        ventana.show()
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        barra = ventana.area.verticalScrollBar()
        if barra.maximum() <= 0:
            barra.setMaximum(1000)
        barra.setValue(600)
        QApplication.processEvents()
        valor_previa = barra.value()
        _cambiar_orden(ventana, "tamano", "desc")
        QApplication.processEvents()
        valor_inmediato = barra.value()
        _esperar(lambda v=ventana: _idle(v))
        valor_final = barra.value()
        ok = valor_previa > 0 and valor_inmediato == 0 and valor_final == 0
        _limpiar(ventana)
        return ok, f"previa={valor_previa} inmediato={valor_inmediato} final={valor_final}"
    finally:
        temp.cleanup()


def test_15():
    temp, ruta_db = _crear_bd_serie(150)
    try:
        ruta_config = _crear_config(temp)
        ventana = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        orig = tv.listar_videos_paginado
        control = _ControlLectura(orig)
        tv.listar_videos_paginado = control
        try:
            ventana.boton_cargar_mas.click()
            _esperar(lambda c=control: c.empezada.is_set())
            primera_kwargs = control.kwargs_vistos[0]
            _cambiar_orden(ventana, "duracion", "desc")
            control.soltar.set()
            _esperar(lambda v=ventana: _idle(v))
        finally:
            tv.listar_videos_paginado = orig
        nombres = [n for n, _ in ventana.tarjetas]
        esperado = _nombres(_referencia(ruta_db, "duracion", "desc", limite=TAMANIO_PAGINA_INICIAL))
        kwargs_recarga = control.kwargs_vistos[1] if len(control.kwargs_vistos) > 1 else {}
        ok = (
            primera_kwargs == {"orden_clave": "nombre", "orden_direccion": "asc"}
            and len(nombres) == TAMANIO_PAGINA_INICIAL
            and nombres == esperado
            and kwargs_recarga.get("orden_clave") == "duracion"
            and kwargs_recarga.get("orden_direccion") == "desc"
        )
        _limpiar(ventana)
        return (
            ok,
            f"primera={primera_kwargs} len={len(nombres)} "
            f"recarga={kwargs_recarga}",
        )
    finally:
        temp.cleanup()


def test_16():
    temp, ruta_db = _crear_bd_serie(150)
    try:
        ruta_config = _crear_config(temp)
        ventana = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        orig = tv.listar_videos_paginado
        llamadas = []
        bloqueada = threading.Event()
        soltar = threading.Event()

        def _respuesta_anterior(limite, desplazamiento):
            # Resultado falsificado del orden viejo: si se aplicara como
            # reemplazo o como anexo, las tarjetas FANTASMA lo delatarían.
            filas = [
                (f"FANTASMA_{i:03d}.mp4", None, None, None, None, None, None, None, 1000 + i)
                for i in range(1, limite + 1)
            ]
            return {
                "videos": filas,
                "total": 150,
                "limite": limite,
                "desplazamiento": desplazamiento,
            }

        def _espia(*args, **kwargs):
            llamadas.append((args, dict(kwargs)))
            if len(llamadas) == 1:
                bloqueada.set()
                soltar.wait(10)
                return _respuesta_anterior(args[0], args[1])
            return orig(*args, **kwargs)

        reemplazos = []
        original_reemplazo = ventana._reemplazar_tarjetas

        def _reemplazo_espiado(filas):
            reemplazos.append([fila[0] for fila in filas])
            return original_reemplazo(filas)

        ventana._reemplazar_tarjetas = _reemplazo_espiado
        tv.listar_videos_paginado = _espia
        try:
            ventana._recarga_catalogo_pendiente = True
            ventana._iniciar_recarga_catalogo()
            _esperar(lambda: bloqueada.is_set())
            _cambiar_orden(ventana, "tamano", "desc")
            soltar.set()
            _esperar(lambda v=ventana: _idle(v))
        finally:
            tv.listar_videos_paginado = orig
            ventana._reemplazar_tarjetas = original_reemplazo
        nombres = [n for n, _ in ventana.tarjetas]
        esperado = _nombres(_referencia(ruta_db, "tamano", "desc", limite=TAMANIO_PAGINA_INICIAL))
        primera = llamadas[0][1]
        contaminaciones = [
            r for r in reemplazos if any(n.startswith("FANTASMA") for n in r)
        ]
        ok = (
            primera.get("orden_clave") == "nombre"
            and primera.get("orden_direccion") == "asc"
            and len(llamadas) == 2
            and len(reemplazos) == 1
            and not contaminaciones
            and len(nombres) == TAMANIO_PAGINA_INICIAL
            and nombres == esperado
            and not any(n.startswith("FANTASMA") for n in nombres)
        )
        _limpiar(ventana)
        return (
            ok,
            f"anterior={primera} llamadas={len(llamadas)} reemplazos={len(reemplazos)} "
            f"contaminado={bool(contaminaciones)} len={len(nombres)} primero={nombres[0]}",
        )
    finally:
        temp.cleanup()


def test_17():
    temp, ruta_db = _crear_bd_serie(250)
    try:
        ruta_config = _crear_config(temp)
        ventana = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        _cambiar_orden(ventana, "duracion", "desc")
        _esperar(lambda v=ventana: _idle(v))
        capturado = []
        original = tv.listar_videos_paginado

        def _espia(*args, **kwargs):
            capturado.append((args, dict(kwargs)))
            return original(*args, **kwargs)

        tv.listar_videos_paginado = _espia
        try:
            ventana.boton_cargar_mas.click()
            _esperar(lambda v=ventana: _idle(v))
        finally:
            tv.listar_videos_paginado = original
        args, kwargs = capturado[0]
        nombres = [n for n, _ in ventana.tarjetas]
        esperado = _nombres(_referencia(
            ruta_db, "duracion", "desc", limite=2 * TAMANIO_PAGINA_INICIAL
        ))
        # `desplazamiento` llega como argumento posicional (args[1]); el offset
        # de "Cargar más" tras reordenar debe ser una página completa.
        ok = (
            kwargs.get("orden_clave") == "duracion"
            and kwargs.get("orden_direccion") == "desc"
            and args[0] == TAMANIO_PAGINA_INICIAL
            and args[1] == TAMANIO_PAGINA_INICIAL
            and len(nombres) == 2 * TAMANIO_PAGINA_INICIAL
            and len(set(nombres)) == len(nombres)
            and nombres == esperado
            and nombres[0].startswith("v250")
        )
        _limpiar(ventana)
        return ok, f"args[0]={args[0]} args[1]={args[1]} kwargs={kwargs} len={len(nombres)} esperado_len={len(esperado)}"
    finally:
        temp.cleanup()


def test_18():
    temp, ruta_db = _crear_bd(BASE)
    try:
        nombres = set(_nombres(escanear_mod.listar_videos_paginado(
            100, 0, None, ruta_db, orden_clave="duracion", orden_direccion="desc"
        )))
        ids = set()
        conn = sqlite3.connect(ruta_db)
        try:
            filas = conn.execute("SELECT id FROM videos").fetchall()
            ids = {fila[0] for fila in filas}
        finally:
            conn.close()
        ok = len(ids) == 6 and len(nombres) == 6
        return ok, f"videos={len(nombres)} ids={len(ids)}"
    finally:
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

    qInstallMessageHandler(None)
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
