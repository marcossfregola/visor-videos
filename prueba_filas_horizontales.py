import ast
import contextlib
import os
import py_compile
import sqlite3
import sys
import tempfile
import time

from PySide6.QtCore import QEventLoop, QThread, QTimer, qInstallMessageHandler
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QLabel

import visor_videos
from rutas import ruta_biblioteca, ruta_carpeta_miniaturas, ruta_carpeta_videos
from tareas import Estado, _GESTORES_ACTIVOS
from visor_videos import (
    ALTO_TARJETA,
    ANCHO_TARJETA,
    TAMANIO_PAGINA_INICIAL,
    Tarjeta,
    VisorVideos,
)

QT_MENSAJES = []

_CONFIG_TEMPORAL = tempfile.TemporaryDirectory()
os.environ["VISOR_CONFIG"] = os.path.join(_CONFIG_TEMPORAL.name, "configuracion.json")


def _mensaje_qt(tipo, contexto, texto):
    QT_MENSAJES.append(str(texto))


qInstallMessageHandler(_mensaje_qt)


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


def _filas_resultado(nombres):
    return [
        (
            nombre,
            float(i % 5),
            i,
            i,
            "h264",
            i % 3,
            None,
        )
        for i, nombre in enumerate(nombres, start=1)
    ]


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


def _mostrar(ventana):
    ventana.resize(900, 600)
    ventana.show()
    QApplication.processEvents()
    _procesar(80)
    QApplication.processEvents()


def _limpiar(ventana):
    if ventana is None:
        return
    if ventana.gestor.hilo is not None:
        ventana.gestor.cerrar()
    ventana.deleteLater()
    for _ in range(5):
        QApplication.processEvents()


def _campos_de(tarjeta):
    campos = {}
    for etiqueta in tarjeta.findChildren(QLabel):
        texto = etiqueta.text()
        if not texto.startswith("<b>"):
            continue
        partes = texto.split("</b>")
        clave = partes[0][len("<b>"):]
        campos[clave] = partes[1].strip()
    return campos


def _nombre_de(tarjeta):
    return _campos_de(tarjeta).get("Nombre:")


@contextlib.contextmanager
def _sin_miniaturas():
    original = visor_videos.miniatura_principal
    visor_videos.miniatura_principal = lambda nombre: None
    try:
        yield
    finally:
        visor_videos.miniatura_principal = original


@contextlib.contextmanager
def _miniatura_falsa(ruta):
    original = visor_videos.miniatura_principal
    visor_videos.miniatura_principal = lambda nombre: ruta
    try:
        yield
    finally:
        visor_videos.miniatura_principal = original


def _instantanea(ruta):
    if not os.path.isdir(ruta):
        return None
    resultado = {}
    for raiz, _, archivos in os.walk(ruta):
        for archivo in sorted(archivos):
            r = os.path.join(raiz, archivo)
            st = os.stat(r)
            resultado[os.path.relpath(r, ruta)] = (st.st_size, st.st_mtime_ns)
    return resultado


def _instantanea_archivo(ruta):
    if not os.path.isfile(ruta):
        return None
    st = os.stat(ruta)
    return (st.st_size, st.st_mtime_ns)


def test_01():
    modulos = [
        "visor_videos.py",
        "tareas.py",
        "tareas_videos.py",
        "escanear_videos.py",
        "rutas.py",
        "prueba_filas_horizontales.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    nombres = ["a.mp4", "b.mkv", "c.avi", "d.mov", "e.webm"]
    temp, ruta_db = _crear_bd(_filas(nombres))
    try:
        with _sin_miniaturas():
            ventana = VisorVideos(ruta_db=ruta_db)
            _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
            _mostrar(ventana)
            tarjetas = [nombre for nombre, _ in ventana.tarjetas]
            hijas = ventana.contenedor.findChildren(Tarjeta)
            coinciden = True
            for i in range(len(nombres)):
                item = ventana.cuadricula.itemAtPosition(i, 0)
                coincide = item is not None and item.widget() is ventana.tarjetas[i][1]
                coinciden = coinciden and coincide
            ventana.close()
            _limpiar(ventana)
        ok = (
            tarjetas == nombres
            and len(hijas) == len(nombres)
            and ventana.cuadricula.count() == len(nombres)
            and coinciden
        )
        return (
            ok,
            f"una_fila_por_video tarjetas={len(tarjetas)} hijas={len(hijas)} "
            f"items={ventana.cuadricula.count()} coinciden={coinciden}",
        )
    finally:
        temp.cleanup()


def test_03():
    nombres = [f"v{i:03d}.mp4" for i in range(1, 9)]
    temp, ruta_db = _crear_bd(_filas(nombres))
    try:
        with _sin_miniaturas():
            ventana = VisorVideos(ruta_db=ruta_db)
            _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
            _mostrar(ventana)
            ventana.contenedor.adjustSize()
            ventana.contenedor.layout().activate()
            for _ in range(5):
                QApplication.processEvents()
            ventana.contenedor.layout().activate()
            QApplication.processEvents()
            ys = []
            xs = []
            altos = []
            for i in range(len(nombres)):
                geom = ventana.tarjetas[i][1].geometry()
                ys.append(geom.y())
                xs.append(geom.x())
                altos.append(geom.height())
            crecientes = all(ys[i] < ys[i + 1] for i in range(len(ys) - 1))
            misma_columna = all(x == xs[0] for x in xs)
            positivos = all(a > 0 for a in altos)
            ventana.close()
            _limpiar(ventana)
        ok = crecientes and misma_columna and positivos
        return (
            ok,
            f"ys={ys} xs={set(xs)} altos={altos} "
            f"crecientes={crecientes} misma_columna={misma_columna}",
        )
    finally:
        temp.cleanup()


def test_04():
    nombres = ["uno.mp4", "dos.mp4", "tres.mp4", "cuatro.mp4", "cinco.mp4", "seis.mp4"]
    temp, ruta_db = _crear_bd(_filas(nombres))
    try:
        with _sin_miniaturas():
            ventana = VisorVideos(ruta_db=ruta_db)
            _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
            _mostrar(ventana)
            columnas = ventana.cuadricula.columnCount()
            sin_segunda = all(
                ventana.cuadricula.itemAtPosition(i, 1) is None
                for i in range(len(nombres))
            )
            tarjeta = ventana.tarjetas[0][1]
            ancho_fila = tarjeta.width()
            ancho_contenedor = ventana.contenedor.width()
            ocupa_ancho = ancho_fila >= 0.8 * ancho_contenedor
            ventana.close()
            _limpiar(ventana)
        ok = columnas == 1 and sin_segunda and ocupa_ancho
        return (
            ok,
            f"columnas={columnas} sin_segunda={sin_segunda} "
            f"ancho_fila={ancho_fila} ancho_contenedor={ancho_contenedor}",
        )
    finally:
        temp.cleanup()


def test_05():
    nombres = ["con_miniatura.mp4", "sin_miniatura.mp4"]
    temp, ruta_db = _crear_bd(_filas(nombres))
    mini = tempfile.TemporaryDirectory()
    try:
        with _sin_miniaturas():
            ventana = VisorVideos(ruta_db=ruta_db)
            _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
            reemplazo = True
            for nombre, tarjeta in ventana.tarjetas:
                recuadros = [
                    l.text() for l in tarjeta.findChildren(QLabel) if l.text() == "Sin miniatura"
                ]
                reemplazo = reemplazo and len(recuadros) == 1
            ventana.close()
            _limpiar(ventana)

        ruta_png = os.path.join(mini.name, "thumb_1.png")
        imagen = QImage(ANCHO_TARJETA, ALTO_TARJETA, QImage.Format_RGB32)
        imagen.fill(QColor("red"))
        guardado = imagen.save(ruta_png)
        with _miniatura_falsa(ruta_png):
            ventana2 = VisorVideos(ruta_db=ruta_db)
            _esperar(lambda v=ventana2: v._carga_completada and v.gestor.hilo is None)
            con_pixmap = True
            for nombre, tarjeta in ventana2.tarjetas:
                pixmaps = [
                    l.pixmap() for l in tarjeta.findChildren(QLabel) if l.pixmap() is not None
                ]
                con_pixmap = con_pixmap and any(p is not None and not p.isNull() for p in pixmaps)
            ventana2.close()
            _limpiar(ventana2)
        ok = guardado and reemplazo and con_pixmap
        return (
            ok,
            f"guardado_png={guardado} reemplazo_sin_miniatura={reemplazo} "
            f"pixmap_presente={con_pixmap}",
        )
    finally:
        mini.cleanup()
        temp.cleanup()


def test_06():
    nombres = ["pera.mp4", "durazno.mkv", "kiwi.avi"]
    temp, ruta_db = _crear_bd(_filas(nombres))
    try:
        with _sin_miniaturas():
            ventana = VisorVideos(ruta_db=ruta_db)
            _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
            _mostrar(ventana)
            visibles = True
            nombres_vistos = []
            for nombre, tarjeta in ventana.tarjetas:
                campos = _campos_de(tarjeta)
                nombres_vistos.append(campos.get("Nombre:"))
                visibles = visibles and campos.get("Nombre:") == nombre
                for etiqueta in tarjeta.findChildren(QLabel):
                    if etiqueta.text().startswith("<b>Nombre:</b>"):
                        visibles = visibles and etiqueta.isVisible()
            ventana.close()
            _limpiar(ventana)
        ok = visibles and nombres_vistos == sorted(nombres)
        return (
            ok,
            f"nombres_vistos={nombres_vistos} visibles={visibles}",
        )
    finally:
        temp.cleanup()


def test_07():
    filas = [
        (
            "peli.mp4",
            os.path.join("C:\\", "peli.mp4"),
            ".mp4",
            "2026-08-03T00:00:00",
            5.0,
            640,
            360,
            "h264",
            1,
        )
    ]
    temp, ruta_db = _crear_bd(filas)
    try:
        with _sin_miniaturas():
            ventana = VisorVideos(ruta_db=ruta_db)
            _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
            campos = _campos_de(ventana.tarjetas[0][1])
            ventana.close()
            _limpiar(ventana)
        ok = (
            campos.get("Duración:") == "0:05"
            and campos.get("Resolución:") == "640x360"
            and campos.get("Codec:") == "h264"
            and campos.get("Miniaturas:") == "1"
        )
        return (
            ok,
            f"campos={campos}",
        )
    finally:
        temp.cleanup()


def test_08():
    nombres = ["manzana.mp4", "mango.mkv", "pera.avi"]
    temp, ruta_db = _crear_bd(_filas(nombres))
    try:
        with _sin_miniaturas():
            ventana = VisorVideos(ruta_db=ruta_db)
            _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
            _mostrar(ventana)
            ventana.busqueda.setText("manz")
            QApplication.processEvents()
            visibles_filtro = ventana.tarjetas_visibles()
            estados = {}
            for nombre, tarjeta in ventana.tarjetas:
                estados[nombre] = tarjeta.isVisible()
            ventana.busqueda.setText("")
            QApplication.processEvents()
            visibles_limpiar = ventana.tarjetas_visibles()
            ventana.close()
            _limpiar(ventana)
        ok = (
            visibles_filtro == ["manzana.mp4"]
            and estados == {
                "manzana.mp4": True,
                "mango.mkv": False,
                "pera.avi": False,
            }
            and visibles_limpiar == sorted(nombres)
        )
        return (
            ok,
            f"visibles_filtro={visibles_filtro} estados={estados} "
            f"visibles_limpiar={visibles_limpiar}",
        )
    finally:
        temp.cleanup()


def test_09():
    nombres = ["uno.mp4", "dos.mp4", "tres.mp4", "cuatro.mp4", "cinco.mp4"]
    temp, ruta_db = _crear_bd(_filas(nombres))
    try:
        with _sin_miniaturas():
            ventana = VisorVideos(ruta_db=ruta_db)
            _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
            inicial = ventana.contador.text()
            ventana.busqueda.setText("uno")
            QApplication.processEvents()
            filtrado = ventana.contador.text()
            ventana.busqueda.setText("")
            QApplication.processEvents()
            restaurado = ventana.contador.text()
            ventana.close()
            _limpiar(ventana)
        ok = inicial == "5 videos" and filtrado == "1 video" and restaurado == "5 videos"
        return (
            ok,
            f"inicial={inicial!r} filtrado={filtrado!r} restaurado={restaurado!r}",
        )
    finally:
        temp.cleanup()


def test_10():
    nombres = ["a.mp4", "b.mkv", "c.avi"]
    temp, ruta_db = _crear_bd(_filas(nombres))
    try:
        with _sin_miniaturas():
            ventana = VisorVideos(ruta_db=ruta_db)
            _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
            antes = [
                ventana.cuadricula.itemAtPosition(i, 0).widget() for i in range(3)
            ]
            ventana._agregar_tarjetas(_filas_resultado(["d.mp4", "e.mp4"]))
            _procesar(30)
            despues = [
                ventana.cuadricula.itemAtPosition(i, 0).widget() for i in range(5)
            ]
            nombres_finales = [
                ventana.tarjetas[i][0] for i in range(5)
            ]
            conservadas = despues[:3] == antes
            agregadas = despues[3:] not in [antes] and len(despues) == 5
            vivas = all(a in ventana.contenedor.findChildren(Tarjeta) for a in antes)
            abajo = (
                _nombre_de(despues[3]) == "d.mp4" and _nombre_de(despues[4]) == "e.mp4"
            )
            ventana.close()
            _limpiar(ventana)
        ok = conservadas and agregadas and vivas and abajo and nombres_finales == [
            "a.mp4",
            "b.mkv",
            "c.avi",
            "d.mp4",
            "e.mp4",
        ]
        return (
            ok,
            f"conservadas={conservadas} agregadas={agregadas} vivas={vivas} "
            f"abajo={abajo} nombres={nombres_finales}",
        )
    finally:
        temp.cleanup()


def test_11():
    nombres = ["a.mp4", "b.mkv", "c.avi"]
    temp, ruta_db = _crear_bd(_filas(nombres))
    try:
        with _sin_miniaturas():
            ventana = VisorVideos(ruta_db=ruta_db)
            _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
            antes = ventana.contenedor.findChildren(Tarjeta)
            ventana._reemplazar_tarjetas(_filas_resultado(["x.mp4", "y.mp4"]))
            _procesar(60)
            despues = ventana.contenedor.findChildren(Tarjeta)
            nombres_finales = [nombre for nombre, _ in ventana.tarjetas]
            liberadas = all(a not in despues for a in antes)
            en_grilla = (
                _nombre_de(ventana.cuadricula.itemAtPosition(0, 0).widget()) == "x.mp4"
                and _nombre_de(ventana.cuadricula.itemAtPosition(1, 0).widget()) == "y.mp4"
                and ventana.cuadricula.itemAtPosition(2, 0) is None
            )
            ventana.close()
            _limpiar(ventana)
        ok = (
            nombres_finales == ["x.mp4", "y.mp4"]
            and len(despues) == 2
            and liberadas
            and en_grilla
        )
        return (
            ok,
            f"nombres={nombres_finales} hijas={len(despues)} liberadas={liberadas} "
            f"en_grilla={en_grilla}",
        )
    finally:
        temp.cleanup()


def test_12():
    nombres = [f"v{i:03d}.mp4" for i in range(1, 151)]
    temp, ruta_db = _crear_bd(_filas(nombres))
    try:
        with _sin_miniaturas():
            ventana = VisorVideos(ruta_db=ruta_db)
            _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
            primera_pagina = [nombre for nombre, _ in ventana.tarjetas]
            habilitado = ventana.boton_cargar_mas.isEnabled()
            ventana.boton_cargar_mas.click()
            _esperar(
                lambda v=ventana: not v._pagina_pendiente and v.gestor.hilo is None
            )
            total = [nombre for nombre, _ in ventana.tarjetas]
            coinciden = True
            orden = sorted(nombres)
            for i in range(len(orden)):
                item = ventana.cuadricula.itemAtPosition(i, 0)
                coincide = item is not None and _nombre_de(item.widget()) == orden[i]
                coinciden = coinciden and coincide
            contador = ventana.contador.text()
            ventana.close()
            _limpiar(ventana)
        ok = (
            len(primera_pagina) == TAMANIO_PAGINA_INICIAL
            and habilitado
            and len(total) == 150
            and len(set(total)) == 150
            and total[:100] == primera_pagina
            and coinciden
            and contador == "150 videos"
        )
        return (
            ok,
            f"primera_pagina={len(primera_pagina)} habilitado={habilitado} "
            f"total={len(total)} duplicados={len(total) - len(set(total))} "
            f"posiciones={coinciden} contador={contador!r}",
        )
    finally:
        temp.cleanup()


def test_13():
    nombres = [f"w{i:02d}.mp4" for i in range(1, 11)]
    temp, ruta_db = _crear_bd(_filas(nombres))
    try:
        with _sin_miniaturas():
            ventana = VisorVideos(ruta_db=ruta_db)
            _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
            _mostrar(ventana)
            visible = ventana.isVisible()
            ventana.resize(900, 600)
            QApplication.processEvents()
            redimension = ventana.width() == 900 and ventana.height() == 600
            barra = ventana.area.verticalScrollBar()
            barra.setValue(200)
            QApplication.processEvents()
            scrolleo = barra.value() > 0
            tarjetas_antes = len(ventana.tarjetas)
            estado_idle = ventana.gestor.estado
            ventana.close()
            _limpiar(ventana)
        ok = (
            visible
            and redimension
            and scrolleo
            and tarjetas_antes == 10
            and estado_idle == Estado.INACTIVO
            and ventana.gestor.hilo is None
            and len(_GESTORES_ACTIVOS) == 0
        )
        return (
            ok,
            f"visible={visible} redimension={redimension} scrolleo={scrolleo} "
            f"tarjetas={tarjetas_antes} estado_idle={estado_idle} "
            f"gestores={len(_GESTORES_ACTIVOS)}",
        )
    finally:
        temp.cleanup()


def test_14():
    with open("visor_videos.py", "r", encoding="utf-8") as f:
        fuente = f.read()
    inicio = fuente.index("class Tarjeta")
    fin = fuente.index("def main()")
    clase = fuente[inicio:fin]
    sin_sqlite = "sqlite3" not in clase
    sin_conectar = "conectar_bd(" not in clase
    sin_execute = ".execute(" not in clase
    sin_guardar = "guardar_videos(" not in clase
    sin_import_sqlite3 = "import sqlite3" not in fuente
    ok = sin_sqlite and sin_conectar and sin_execute and sin_guardar and sin_import_sqlite3
    return (
        ok,
        f"clases={inicio}-{fin} sqlite3={sin_sqlite} conectar_bd={sin_conectar} "
        f"execute={sin_execute} guardar_videos={sin_guardar} "
        f"import_sqlite3={sin_import_sqlite3}",
    )


def test_15():
    with open("visor_videos.py", "r", encoding="utf-8") as f:
        arbol = ast.parse(f.read())

    def _literales_en_llamadas(arbol):
        encontrados = []
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Call):
                argumentos = list(nodo.args) + [
                    kw.value for kw in nodo.keywords
                ]
                for arg in argumentos:
                    if isinstance(arg, ast.Constant) and isinstance(
                        arg.value, str
                    ):
                        encontrados.append(arg.value)
        return encontrados

    # La regla protege el uso real (p. ej. comandos pasados a una llamada que
    # lanzaria un binario), no los docstrings ni comentarios documentales.
    binarios = [
        lit
        for lit in _literales_en_llamadas(arbol)
        if "ffprobe" in lit.lower() or "ffmpeg" in lit.lower()
    ]
    nombres = [nodo.id for nodo in ast.walk(arbol) if isinstance(nodo, ast.Name)]
    importa_subprocess = any(
        isinstance(nodo, (ast.Import, ast.ImportFrom))
        and any(getattr(alias, "name", "") == "subprocess" for alias in nodo.names)
        for nodo in ast.walk(arbol)
    )
    sin_subprocess = not importa_subprocess and "subprocess" not in nombres
    sin_popen = "Popen" not in nombres
    sin_qprocess = "QProcess" not in nombres
    sin_os_system = not any(
        isinstance(nodo, ast.Call)
        and isinstance(nodo.func, ast.Attribute)
        and nodo.func.attr == "system"
        and isinstance(nodo.func.value, ast.Name)
        and nodo.func.value.id == "os"
        for nodo in ast.walk(arbol)
    )
    ok = (
        not binarios
        and sin_subprocess
        and sin_popen
        and sin_qprocess
        and sin_os_system
    )
    return (
        ok,
        f"literales_binarios={binarios} subprocess={sin_subprocess} "
        f"Popen={sin_popen} QProcess={sin_qprocess} os_system={sin_os_system}",
    )


def test_16():
    ruta_db_real = ruta_biblioteca()
    ruta_min = ruta_carpeta_miniaturas()
    ruta_videos = ruta_carpeta_videos()
    if not os.path.isfile(ruta_db_real):
        return False, f"falta biblioteca.db en {ruta_db_real}"
    antes_db = _instantanea_archivo(ruta_db_real)
    antes_min = _instantanea(ruta_min)
    antes_videos = _instantanea(ruta_videos)
    if antes_min is None or antes_videos is None:
        return False, f"faltan carpetas: miniaturas={antes_min} videos={antes_videos}"
    temp, ruta_db = _crear_bd(_filas(["real_uno.mp4", "real_dos.mkv"]))
    try:
        with _sin_miniaturas():
            ventana = VisorVideos(ruta_db=ruta_db)
            _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
            _mostrar(ventana)
            ventana.close()
            _limpiar(ventana)
    finally:
        temp.cleanup()
    despues_db = _instantanea_archivo(ruta_db_real)
    despues_min = _instantanea(ruta_min)
    despues_videos = _instantanea(ruta_videos)
    ok = (
        antes_db == despues_db
        and antes_min == despues_min
        and antes_videos == despues_videos
    )
    return (
        ok,
        f"biblioteca_ok={antes_db == despues_db} miniaturas_ok={antes_min == despues_min} "
        f"videos_prueba_ok={antes_videos == despues_videos}",
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
        print(f"T{i:02d} {'OK' if ok else 'FALLO'} - {detalle}")

    ok_total = all(ok for _, ok, _ in resultados)
    aprobadas = sum(1 for _, ok, _ in resultados if ok)
    print(f"TOTAL={aprobadas}/16")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")

    qInstallMessageHandler(None)
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
