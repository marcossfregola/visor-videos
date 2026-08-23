"""Pruebas estructurales del pulido de ancho (B5 — layout horizontal).

Verifica que la zona de miniaturas/previews de la tarjeta esté contenida en
un `QScrollArea` LOCAL y que ese scroll local NO imponga su ancho total al
contenedor/catálogo general:

- `_area_imagenes` existe, es `QScrollArea`, y contiene las etiquetas de
  imágenes como descendientes;
- usa scrollbar horizontal `ScrollBarAsNeeded` y vertical `AlwaysOff`;
- con una tarjeta de muchas miniaturas anchas, el scroll local tiene
  `maximum() > 0` (contenido excede su viewport);
- la tarjeta NO hereda el ancho total de las miniaturas (minimumSizeHint
  acotado) y el contenedor global se ajusta al viewport (sin scrollbar
  horizontal GLOBAL);
- los controles temporales (Segmento, Densidad, franja) quedan FUERA de la
  superficie horizontal desplazable;
- al desplazar el scrollbar local solo se mueven las miniaturas, no los
  controles ni el catálogo.

Las verificaciones son estructurales/relativas (no coordenadas exactas).
"""

import json
import os
import sqlite3
import sys
import tempfile
import time

from PySide6.QtCore import QEventLoop, QPoint, Qt, QTimer, qInstallMessageHandler
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QScrollArea

import escanear_videos as escanear_mod
import visor_videos
from visor_videos import Tarjeta, VisorVideos

QT_MENSAJES = []


def _mensaje_qt(_tipo, _contexto, texto):
    QT_MENSAJES.append(str(texto))


qInstallMessageHandler(_mensaje_qt)

_CONFIG = tempfile.TemporaryDirectory()
os.environ["VISOR_CONFIG"] = os.path.join(_CONFIG.name, "configuracion.json")

_DIR = tempfile.TemporaryDirectory()

_PREVIEWS_ANCHO = 9
_PREVIEWS_NORMALES = 3


def _paso():
    return


def _crear_bd(nombres):
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
        filas = []
        for nombre in nombres:
            filas.append(
                (
                    nombre,
                    os.path.join("C:\\", nombre),
                    os.path.splitext(nombre)[1].lower(),
                    "2026-08-03T00:00:00",
                    500.0,
                    640,
                    360,
                    "h264",
                    3,
                    1000,
                )
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


def _imagen(ancho, alto, color):
    imagen = QImage(ancho, alto, QImage.Format_RGB32)
    imagen.fill(QColor(color))
    return imagen


def _pngs(archivos, ancho, alto, color):
    rutas = []
    for nombre in archivos:
        ruta = os.path.join(_DIR.name, nombre)
        _imagen(ancho, alto, color).save(ruta)
        rutas.append(ruta)
    return rutas


def _configurar_miniaturas(nombre_ancho):
    def _miniatura(nombre):
        if nombre == nombre_ancho:
            return os.path.join(_DIR.name, "ancha_min.png")
        return os.path.join(_DIR.name, "vertical_min.png")

    def _previews(nombre):
        if nombre == nombre_ancho:
            return _pngs(
                [f"ancha_pre_{i}.png" for i in range(1, _PREVIEWS_ANCHO + 1)],
                320, 180, "#b03030",
            )
        return _pngs(
            [f"vertical_pre_{i}.png" for i in range(1, _PREVIEWS_NORMALES + 1)],
            90, 180, "#3070b0",
        )

    visor_videos.miniatura_principal = _miniatura
    visor_videos.previews_de = _previews


def _procesar(ms):
    bucle = QEventLoop()
    QTimer.singleShot(ms, bucle.quit)
    bucle.exec()


def _esperar(predicado, timeout_ms=10000, paso_ms=20):
    fin = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < fin:
        QApplication.processEvents()
        if predicado():
            return True
        time.sleep(paso_ms / 1000)
    QApplication.processEvents()
    return predicado()


def _abrir_ventana(ruta_db):
    ventana = VisorVideos(ruta_db=ruta_db)
    _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
    ventana.resize(1200, 700)
    ventana.show()
    _procesar(80)
    QApplication.processEvents()
    return ventana


def _limpiar(ventana):
    for gestor in (
        getattr(ventana, "gestor", None),
        getattr(ventana, "gestor_marcadores", None),
        getattr(ventana, "gestor_segmentos", None),
        getattr(ventana, "gestor_previews", None),
        getattr(ventana, "gestor_reproduccion", None),
        getattr(ventana, "gestor_exploracion", None),
    ):
        if gestor is not None:
            gestor.cerrar()
    ventana.deleteLater()
    for _ in range(5):
        QApplication.processEvents()


def _tarjeta_por_nombre(ventana, nombre):
    for n, tarjeta in ventana.tarjetas:
        if n == nombre:
            return tarjeta
    return None


def _escenario():
    """Ventana real con una tarjeta ancha (9 miniaturas) y tarjetas estrechas."""
    _imagen(320, 180, "#b03030").save(os.path.join(_DIR.name, "ancha_min.png"))
    _imagen(90, 180, "#3070b0").save(os.path.join(_DIR.name, "vertical_min.png"))
    with open(os.environ["VISOR_CONFIG"], "w", encoding="utf-8") as f:
        json.dump({"cantidad_previews": _PREVIEWS_ANCHO}, f)
    nombres = ["ancha.mp4", "estrecha1.mp4", "estrecha2.mp4"]
    temp, ruta_db = _crear_bd(nombres)
    escanear_mod.configurar_cantidad_previews(_PREVIEWS_ANCHO)
    try:
        _configurar_miniaturas("ancha.mp4")
        ventana = _abrir_ventana(ruta_db)
        for nombre, tarjeta in ventana.tarjetas:
            if nombre == "ancha.mp4":
                tarjeta.ajustar_previews(_PREVIEWS_ANCHO)
            else:
                tarjeta.ajustar_previews(_PREVIEWS_NORMALES)
            tarjeta.actualizar_previews(visor_videos.previews_de(nombre))
        _procesar(60)
        QApplication.processEvents()
        return ventana, temp, ruta_db
    except Exception:
        temp.cleanup()
        raise


def _descendiente(raiz, widget):
    while widget is not None:
        if widget is raiz:
            return True
        widget = widget.parentWidget()
    return False


def test_01():
    """La zona de imágenes vive dentro de un QScrollArea local de la tarjeta."""
    ventana, temp, ruta_db = _escenario()
    try:
        tarjeta = _tarjeta_por_nombre(ventana, "ancha.mp4")
        area = getattr(tarjeta, "_area_imagenes", None)
        ok_area = isinstance(area, QScrollArea)
        ok_hijos = all(
            _descendiente(area, etiqueta)
            for etiqueta in (
                [tarjeta._imagen_miniatura] + tarjeta._etiquetas_previews
            )
            if etiqueta is not None
        )
        ok_politicas = (
            area.horizontalScrollBarPolicy() == Qt.ScrollBarAsNeeded
            and area.verticalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
        )
        ok_anidado = _descendiente(tarjeta, area)
    finally:
        ventana.close()
        _limpiar(ventana)
        temp.cleanup()
    ok = ok_area and ok_hijos and ok_politicas and ok_anidado
    return (
        ok,
        f"area={ok_area} hijos={ok_hijos} politicas={ok_politicas} "
        f"anidado={ok_anidado}",
    )


def test_02():
    """El scroll local aparece solo si el contenido excede su viewport."""
    ventana, temp, ruta_db = _escenario()
    try:
        tarjeta = _tarjeta_por_nombre(ventana, "ancha.mp4")
        estrecha = _tarjeta_por_nombre(ventana, "estrecha1.mp4")
        area_ancha = tarjeta._area_imagenes
        area_estrecha = estrecha._area_imagenes
        max_ancha = area_ancha.horizontalScrollBar().maximum()
        max_estrecha = area_estrecha.horizontalScrollBar().maximum()
        contenido = tarjeta._contenedor_imagenes.sizeHint().width()
        viewport_ancha = area_ancha.viewport().width()
        ok = (
            max_ancha > 0
            and contenido > viewport_ancha
            and max_estrecha == 0
        )
    finally:
        ventana.close()
        _limpiar(ventana)
        temp.cleanup()
    return (
        ok,
        f"max_ancha={max_ancha} max_estrecha={max_estrecha} "
        f"contenido={contenido} viewport_ancha={viewport_ancha}",
    )


def test_03():
    """Ni la tarjeta ni el contenedor heredan el ancho total de las miniaturas."""
    ventana, temp, ruta_db = _escenario()
    try:
        tarjeta = _tarjeta_por_nombre(ventana, "ancha.mp4")
        contenido = tarjeta._contenedor_imagenes.sizeHint().width()
        min_tarjeta = tarjeta.minimumSizeHint().width()
        min_contenedor = ventana.contenedor.minimumSizeHint().width()
        hbar_global = ventana.area.horizontalScrollBar()
        ok_tarjeta = min_tarjeta < contenido * 0.6
        ok_contenedor = min_contenedor < contenido * 0.6
        ok_sin_scroll_global = hbar_global.maximum() == 0
        viewport = ventana.area.viewport().width()
        ok_ajuste = ventana.contenedor.width() <= viewport
        ok_tarjetas = all(
            t.width() <= viewport for _, t in ventana.tarjetas
        )
    finally:
        ventana.close()
        _limpiar(ventana)
        temp.cleanup()
    ok = (
        ok_tarjeta
        and ok_contenedor
        and ok_sin_scroll_global
        and ok_ajuste
        and ok_tarjetas
    )
    return (
        ok,
        f"contenido={contenido} min_tarjeta={min_tarjeta} "
        f"min_contenedor={min_contenedor} "
        f"hbar_global_max={hbar_global.maximum()} "
        f"contenedor_w={ventana.contenedor.width()} viewport={viewport}",
    )


def test_04():
    """Segmento, Densidad y la franja quedan FUERA de la zona desplazable."""
    ventana, temp, ruta_db = _escenario()
    try:
        tarjeta = _tarjeta_por_nombre(ventana, "ancha.mp4")
        tarjeta.expandir()
        _procesar(120)
        QApplication.processEvents()
        area = tarjeta._area_imagenes
        fuera_segmento = not _descendiente(area, tarjeta._boton_segmento)
        fuera_densidad = not _descendiente(area, tarjeta._selector_densidad)
        fuera_franja = not _descendiente(area, tarjeta._franja)
        fuera_colapsar = not _descendiente(area, tarjeta._boton_expandir)
    finally:
        ventana.close()
        _limpiar(ventana)
        temp.cleanup()
    ok = fuera_segmento and fuera_densidad and fuera_franja and fuera_colapsar
    return (
        ok,
        f"segmento={fuera_segmento} densidad={fuera_densidad} "
        f"franja={fuera_franja} colapsar={fuera_colapsar}",
    )


def test_05():
    """Al desplazar el scroll local se mueven las miniaturas, no los controles."""
    ventana, temp, ruta_db = _escenario()
    try:
        tarjeta = _tarjeta_por_nombre(ventana, "ancha.mp4")
        tarjeta.expandir()
        _procesar(120)
        QApplication.processEvents()
        area = tarjeta._area_imagenes
        viewport = ventana.area.viewport()
        barra = area.horizontalScrollBar()
        if barra.maximum() <= 0:
            return False, "no hay scroll local para desplazar"
        miniatura = tarjeta._imagen_miniatura
        x_mini_antes = miniatura.mapTo(viewport, QPoint(0, 0)).x()
        x_seg_antes = tarjeta._boton_segmento.mapTo(viewport, QPoint(0, 0)).x()
        barra.setValue(barra.maximum())
        QApplication.processEvents()
        x_mini_despues = miniatura.mapTo(viewport, QPoint(0, 0)).x()
        x_seg_despues = tarjeta._boton_segmento.mapTo(viewport, QPoint(0, 0)).x()
        se_mueve_miniatura = x_mini_despues != x_mini_antes
        quieto_segmento = x_seg_despues == x_seg_antes
    finally:
        ventana.close()
        _limpiar(ventana)
        temp.cleanup()
    ok = se_mueve_miniatura and quieto_segmento
    return (
        ok,
        f"mini_x={x_mini_antes}->{x_mini_despues} "
        f"seg_x={x_seg_antes}->{x_seg_despues}",
    )


def test_06():
    """Redimensionado: sin mínimo global heredado y scroll local según corresponda."""
    ventana, temp, ruta_db = _escenario()
    try:
        tarjeta = _tarjeta_por_nombre(ventana, "ancha.mp4")
        tarjeta.expandir()
        resultados = {}
        for ancho in (760, 1200, 1900):
            ventana.resize(ancho, 700)
            _procesar(120)
            QApplication.processEvents()
            resultados[ancho] = (
                ventana.area.horizontalScrollBar().maximum(),
                tarjeta._area_imagenes.horizontalScrollBar().maximum(),
                ventana.contenedor.width(),
                ventana.area.viewport().width(),
                tarjeta._boton_segmento.mapTo(
                    ventana.area.viewport(), QPoint(0, 0)
                ).x(),
            )
    finally:
        ventana.close()
        _limpiar(ventana)
        temp.cleanup()
    sin_global = all(
        resultados[a][0] == 0
        and resultados[a][2] <= resultados[a][3]
        for a in resultados
    )
    controles_dentro = all(
        0 <= resultados[a][4] <= resultados[a][3] for a in resultados
    )
    scroll_ancha = all(resultados[a][1] > 0 for a in resultados)
    ok = sin_global and controles_dentro and scroll_ancha
    return (
        ok,
        f"resumen={resultados} sin_global={sin_global} "
        f"controles_dentro={controles_dentro} scroll_ancha={scroll_ancha}",
    )


def test_07():
    """Expandir/colapsar siguen funcionando sobre la tarjeta con scroll local."""
    ventana, temp, ruta_db = _escenario()
    try:
        tarjeta = _tarjeta_por_nombre(ventana, "ancha.mp4")
        tarjeta.expandir()
        _procesar(120)
        QApplication.processEvents()
        expandida = tarjeta._expandida and tarjeta._contenedor_exploracion.isVisible()
        franja_ok = tarjeta._franja.width() > 0
        tarjeta.colapsar()
        _procesar(60)
        QApplication.processEvents()
        colapsada = (not tarjeta._expandida) and (
            not tarjeta._contenedor_exploracion.isVisible()
        )
    finally:
        ventana.close()
        _limpiar(ventana)
        temp.cleanup()
    ok = expandida and franja_ok and colapsada
    return (
        ok,
        f"expandida={expandida} franja_ok={franja_ok} colapsada={colapsada}",
    )


def test_08():
    """AST: `_area_imagenes` es un QScrollArea local, sin hacks de ancho fijo."""
    with open("visor_videos.py", "r", encoding="utf-8") as f:
        fuente = f.read()
    inicio = fuente.index("class Tarjeta")
    fin = fuente.index("class PanelPrincipal")
    clase = fuente[inicio:fin]
    ok = (
        "QScrollArea()" in clase
        and "ScrollBarAsNeeded" in clase
        and "ScrollBarAlwaysOff" in clase
        and "setFixedWidth" not in clase
    )
    return (
        ok,
        f"scroll_local={'QScrollArea()' in clase} "
        f"asneeded={'ScrollBarAsNeeded' in clase} "
        f"alwaysoff={'ScrollBarAlwaysOff' in clase} "
        f"sin_setFixedWidth={'setFixedWidth' not in clase}",
    )


def test_09():
    """El scroll local responde a la rueda horizontal y no rompe la tarjeta."""
    ventana, temp, ruta_db = _escenario()
    try:
        tarjeta = _tarjeta_por_nombre(ventana, "ancha.mp4")
        area = tarjeta._area_imagenes
        barra = area.horizontalScrollBar()
        if barra.maximum() <= 0:
            return False, "no hay scroll local para operar"
        barra.setValue(0)
        QApplication.processEvents()
        from PySide6.QtGui import QWheelEvent

        evento = QWheelEvent(
            QPoint(10, 10),
            area.viewport().mapToGlobal(QPoint(10, 10)),
            QPoint(0, 0),
            QPoint(-240, 0),
            Qt.NoButton,
            Qt.NoModifier,
            Qt.NoScrollPhase,
            False,
        )
        QApplication.sendEvent(area.viewport(), evento)
        QApplication.processEvents()
        se_movio = barra.value() > 0
        altura_ok = tarjeta.height() < 400
    finally:
        ventana.close()
        _limpiar(ventana)
        temp.cleanup()
    ok = se_movio and altura_ok
    return (
        ok,
        f"barra 0->{barra.value()} (max={barra.maximum()}) "
        f"altura_tarjeta={tarjeta.height()}",
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
    print(f"TOTAL={aprobadas}/9")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")

    qInstallMessageHandler(None)
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
