import contextlib
import os
import sqlite3
import sys
import tempfile
import time

from PySide6.QtCore import QEvent
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QLabel

import escanear_videos as escanear_mod
import visor_videos
from visor_videos import (
    RETARDO_VISTA_AMPLIADA_MS,
    Tarjeta,
    VistaAmpliada,
    VisorVideos,
)

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


def _crear_png(ruta, color="red"):
    imagen = QImage(160, 100, QImage.Format_RGB32)
    imagen.fill(QColor(color))
    return imagen.save(ruta, "PNG")


def _crear_previews(carpeta, prefijo, cantidad, con_miniatura=False):
    rutas = []
    for indice in range(1, cantidad + 1):
        ruta = os.path.join(carpeta, f"{prefijo}_preview_{indice:02d}.jpg")
        _crear_png(ruta)
        rutas.append(ruta)
    if con_miniatura:
        _crear_png(os.path.join(carpeta, f"{prefijo}_01.jpg"))
    return rutas


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


@contextlib.contextmanager
def _contar_qpixmap():
    contador = [0]
    original = visor_videos.QPixmap

    class _QPixmapContador(original):
        def __init__(self, *args, **kwargs):
            contador[0] += 1
            super().__init__(*args, **kwargs)

    visor_videos.QPixmap = _QPixmapContador
    try:
        yield contador
    finally:
        visor_videos.QPixmap = original


def _fila(nombre, duracion):
    return (nombre, duracion, 1920, 1080, "h264", 1, 1024)


def _fila_bd(nombre, duracion):
    n, d, ancho, alto, codec, miniaturas, tamano = _fila(nombre, duracion)
    return (
        n,
        f"C:\\{n}",
        os.path.splitext(n)[1].lower(),
        "2026-08-06T00:00:00",
        d,
        ancho,
        alto,
        codec,
        miniaturas,
        tamano,
    )


def _crear_bd(filas):
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
    conn.executemany(
        "INSERT INTO videos (nombre, ruta, extension, fecha_importacion, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas, tamano_bytes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        filas,
    )
    conn.commit()
    conn.close()
    return temp, ruta_db


def _evento(widget, tipo):
    if widget is None:
        return False
    QApplication.sendEvent(widget, QEvent(tipo))
    return True


def _esperar(predicado, intentos=300):
    for _ in range(intentos):
        QApplication.processEvents()
        if predicado():
            return True
        time.sleep(0.02)
    QApplication.processEvents()
    return predicado()


def _esperar_preview(ventana, nombre, indice=0):
    """Espera de forma determinista a que la preview este aplicada.

    Desde B4.6 las previews se cargan de forma progresiva/diferida, por lo
    que una tarjeta puede no tener todavia el pixmap original justo despues
    de cargar el catalogo.
    """

    def _aplicada():
        tarjeta = dict(ventana.tarjetas).get(nombre)
        if tarjeta is None:
            return False
        etiquetas = tarjeta._etiquetas_previews
        if indice >= len(etiquetas):
            return False
        return etiquetas[indice]._pixmap_original is not None

    return _esperar(_aplicada)


def main():
    app = QApplication(sys.argv)

    _CONTADOR[0] = 1

    # --- 1) instancia única, aislada de la tarjeta y sin lecturas nuevas ---
    with _miniaturas_temporales() as carpeta:
        _crear_previews(carpeta, "clip", 3, con_miniatura=True)
        with _contar_qpixmap() as contador:
            tarjeta = Tarjeta(_fila("clip.mp4", 100.0))
            tarjeta.actualizar_previews(_crear_previews(carpeta, "clip", 3))
            base = contador[0]
            verifica(
                isinstance(tarjeta, Tarjeta),
                "tarjeta construida (pixmaps de disco cargados)",
            )
            ventana = VisorVideos(
                ruta_config=os.path.join(carpeta, "cfg.json")
            )
            ventana.show()
            QApplication.processEvents()
            try:
                verifica(
                    isinstance(ventana._vista, VistaAmpliada),
                    "existe una única instancia de VistaAmpliada",
                )
                verifica(
                    ventana._vista not in tarjeta.findChildren(VistaAmpliada)
                    and ventana._vista._etiqueta
                    not in tarjeta.findChildren(QLabel),
                    "el popup no es hijo de la tarjeta (no rompe helpers de test)",
                )
            finally:
                ventana.close()
                ventana.gestor.cerrar()
                ventana.gestor_previews.cerrar()
            ventana._vista.preparar(
                tarjeta._etiquetas_previews[0]._pixmap_original
            )
            verifica(
                contador[0] == base,
                "preparar la vista ampliada no lee disco (0 QPixmap nuevos)",
                extra=f"construcciones={contador[0] - base}",
            )

    # --- 2) retardo: aparece después del retardo y desaparece al salir ---
    with _miniaturas_temporales() as carpeta:
        _crear_previews(carpeta, "clip", 3, con_miniatura=True)
        temp, ruta_db = _crear_bd([_fila_bd("clip.mp4", 100.0)])
        ruta_config = os.path.join(temp.name, "config.json")
        try:
            ventana = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
            ventana.show()
            _esperar(
                lambda: ventana._carga_completada
                and ventana.gestor.hilo is None
            )
            _esperar_preview(ventana, "clip.mp4")
            tarjeta = dict(ventana.tarjetas)["clip.mp4"]
            etiqueta = tarjeta._etiquetas_previews[0]
            verifica(
                etiqueta._pixmap_original is not None,
                "el preview tiene el pixmap original cargado",
            )
            _evento(etiqueta, QEvent.Enter)
            verifica(
                not ventana._vista.isVisible()
                and ventana._vista_pendiente is not None,
                "tras entrar: pendiente pero aún no visible (retardo)",
            )
            ventana._timer_vista_mostrar.timeout.emit()
            verifica(
                ventana._vista.isVisible(),
                "tras el retardo: la vista ampliada se muestra",
            )
            _evento(etiqueta, QEvent.Leave)
            verifica(
                ventana._vista_pendiente is None
                and ventana._timer_vista_ocultar.isActive(),
                "al salir: se cancela el pendiente y se programa el ocultado",
            )
            ventana._timer_vista_ocultar.timeout.emit()
            verifica(
                not ventana._vista.isVisible(),
                "tras el ocultado programado: la vista desaparece",
            )
        finally:
            ventana.close()
            ventana.gestor.cerrar()
            ventana.gestor_previews.cerrar()
            temp.cleanup()

    # --- 3) miniatura principal y previews: mismo comportamiento, original ---
    with _miniaturas_temporales() as carpeta:
        _crear_previews(carpeta, "clip", 3, con_miniatura=True)
        tarjeta = Tarjeta(_fila("clip.mp4", 100.0))
        tarjeta.actualizar_previews(_crear_previews(carpeta, "clip", 3))
        recibidos = []
        tarjeta.vista_solicitada.connect(lambda p: recibidos.append(p))
        verifica(
            tarjeta._imagen_miniatura is not None,
            "la tarjeta tiene miniatura principal",
        )
        _evento(tarjeta._imagen_miniatura, QEvent.Enter)
        verifica(
            len(recibidos) == 1 and recibidos[0] is tarjeta._miniatura_original,
            "enter sobre miniatura principal emite el pixmap original",
        )
        recibidos.clear()
        _evento(tarjeta._etiquetas_previews[0], QEvent.Enter)
        verifica(
            len(recibidos) == 1
            and recibidos[0] is tarjeta._etiquetas_previews[0]._pixmap_original,
            "enter sobre preview emite el pixmap original (mismo comportamiento)",
        )
        salidas = []
        tarjeta.vista_abandonada.connect(lambda: salidas.append(True))
        _evento(tarjeta._etiquetas_previews[0], QEvent.Leave)
        verifica(
            len(salidas) == 1,
            "leave emite la señal de abandono",
        )

    # --- 4) ocultar por scroll y por reconstrucción del catálogo ---
    with _miniaturas_temporales() as carpeta:
        _crear_previews(carpeta, "clip", 3, con_miniatura=True)
        temp, ruta_db = _crear_bd([_fila_bd("clip.mp4", 100.0)])
        ruta_config = os.path.join(temp.name, "config.json")
        try:
            ventana = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
            ventana.show()
            _esperar(
                lambda: ventana._carga_completada
                and ventana.gestor.hilo is None
            )
            _esperar_preview(ventana, "clip.mp4")
            etiqueta = dict(ventana.tarjetas)["clip.mp4"]._etiquetas_previews[0]
            _evento(etiqueta, QEvent.Enter)
            ventana._timer_vista_mostrar.timeout.emit()
            verifica(
                ventana._vista.isVisible(),
                "vista visible antes del scroll",
            )
            ventana.area.verticalScrollBar().valueChanged.emit(10)
            verifica(
                not ventana._vista.isVisible(),
                "el scroll oculta la vista ampliada",
            )

            _evento(etiqueta, QEvent.Enter)
            ventana._timer_vista_mostrar.timeout.emit()
            verifica(
                ventana._vista.isVisible(),
                "vista visible antes de la recarga",
            )
            ventana._reemplazar_tarjetas([_fila("clip.mp4", 100.0)])
            verifica(
                not ventana._vista.isVisible(),
                "la reconstrucción del catálogo oculta la vista",
            )
        finally:
            ventana.close()
            ventana.gestor.cerrar()
            ventana.gestor_previews.cerrar()
            temp.cleanup()

    # --- 5) posicionamiento dentro de la pantalla y tamaño ~1.6x ---
    with _miniaturas_temporales() as carpeta:
        _crear_previews(carpeta, "clip", 3, con_miniatura=True)
        temp, ruta_db = _crear_bd([_fila_bd("clip.mp4", 100.0)])
        ruta_config = os.path.join(temp.name, "config.json")
        try:
            ventana = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
            ventana.show()
            _esperar(
                lambda: ventana._carga_completada
                and ventana.gestor.hilo is None
            )
            _esperar_preview(ventana, "clip.mp4")
            etiqueta = dict(ventana.tarjetas)["clip.mp4"]._etiquetas_previews[0]
            _evento(etiqueta, QEvent.Enter)
            ventana._timer_vista_mostrar.timeout.emit()
            pos = ventana._posicion_vista()
            pantalla = QApplication.primaryScreen().availableGeometry()
            dentro = (
                pos.x() >= pantalla.left()
                and pos.y() >= pantalla.top()
                and pos.x() + ventana._vista.width() <= pantalla.right()
                and pos.y() + ventana._vista.height() <= pantalla.bottom()
            )
            verifica(
                dentro,
                "la vista ampliada queda completamente dentro de la pantalla",
                extra=f"pos=({pos.x()},{pos.y()}) tamaño={ventana._vista.size().toTuple()}",
            )
            verifica(
                ventana._vista._tam_amp == (int(320 * 1.6), int(180 * 1.6)),
                "tamaño de ampliación ~1.6x del tamaño configurado",
                extra=ventana._vista._tam_amp,
            )
        finally:
            ventana.close()
            ventana.gestor.cerrar()
            ventana.gestor_previews.cerrar()
            temp.cleanup()

    # --- 6) integración completa con catálogo ---
    with _miniaturas_temporales() as carpeta:
        _crear_previews(carpeta, "a", 3, con_miniatura=True)
        _crear_previews(carpeta, "b", 3)
        temp, ruta_db = _crear_bd(
            [_fila_bd("a.mp4", 100.0), _fila_bd("b.mp4", 200.0)]
        )
        ruta_config = os.path.join(temp.name, "config.json")
        try:
            ventana = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
            ventana.resize(1000, 700)
            ventana.show()
            _esperar(
                lambda: ventana._carga_completada
                and ventana.gestor.hilo is None
            )
            verifica(
                len(ventana.tarjetas) == 2,
                "integración: 2 tarjetas cargadas",
            )
            _esperar_preview(ventana, "a.mp4")
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            etiqueta = tarjeta._etiquetas_previews[0]
            _evento(etiqueta, QEvent.Enter)
            ventana._timer_vista_mostrar.timeout.emit()
            verifica(
                ventana._vista.isVisible()
                and ventana._vista._pixmap is etiqueta._pixmap_original,
                "integración: popup visible reutilizando el pixmap original",
            )
            _evento(tarjeta._imagen_miniatura, QEvent.Enter)
            ventana._timer_vista_mostrar.timeout.emit()
            verifica(
                ventana._vista._pixmap is tarjeta._miniatura_original,
                "integración: miniatura principal también amplía",
            )
            ventana._ocultar_vista()
            verifica(
                not ventana._vista.isVisible(),
                "integración: ocultado explícito correcto",
            )
        finally:
            ventana.close()
            ventana.gestor.cerrar()
            ventana.gestor_previews.cerrar()
            temp.cleanup()

    verifica(RETARDO_VISTA_AMPLIADA_MS > 0, "retardo configurable definido")

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
