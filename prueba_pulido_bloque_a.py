import contextlib
import os
import sqlite3
import sys
import tempfile
import time

from PySide6.QtCore import QEvent
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import QApplication

import escanear_videos as escanear_mod
import visor_videos
from visor_videos import (
    LIMITE_ORIGINAL_MINIATURA,
    Tarjeta,
    VisorVideos,
    _duracion_valida,
    _pixmap_acotado,
    configurar_cantidad_previews,
    configurar_tamano_miniaturas,
    formatear_tiempo,
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


def _guardar_png(ruta, ancho, alto, color="red"):
    imagen = QImage(ancho, alto, QImage.Format_RGB32)
    imagen.fill(QColor(color))
    return imagen.save(ruta, "PNG")


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


def _fila_bd(nombre, duracion):
    return (
        nombre, f"C:\\{nombre}", os.path.splitext(nombre)[1].lower(),
        "2026-08-06T00:00:00", duracion, 1920, 1080, "h264", 1, 1024,
    )


@contextlib.contextmanager
def _ventana_con():
    temp = tempfile.TemporaryDirectory()
    mini = tempfile.TemporaryDirectory()
    videos = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp.name, "catalogo.db")
    ruta_config = os.path.join(temp.name, "config.json")
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
        "INSERT INTO videos (nombre, ruta, extension, fecha_importacion, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas, tamano_bytes) VALUES (?,?,?,?,?,?,?,?,?,?)",
        _fila_bd("clip.mp4", 100.0),
    )
    conn.commit()
    conn.close()
    with open(ruta_config, "w", encoding="utf-8") as f:
        f.write("{}")

    original_escaneo = escanear_mod.ruta_carpeta_miniaturas
    original_visor = visor_videos.ruta_carpeta_miniaturas
    escanear_mod.ruta_carpeta_miniaturas = lambda: mini.name
    visor_videos.ruta_carpeta_miniaturas = lambda: mini.name
    _guardar_png(os.path.join(mini.name, "clip_preview_01.jpg"), 1920, 1080, "red")
    _guardar_png(os.path.join(mini.name, "clip_preview_02.jpg"), 1920, 1080, "blue")
    _guardar_png(os.path.join(mini.name, "clip_01.jpg"), 1920, 1080, "green")
    with open(os.path.join(videos.name, "clip.mp4"), "wb") as f:
        f.write(b"x")
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

        def _previews_aplicadas():
            return any(
                tarjeta._etiquetas_previews
                and tarjeta._etiquetas_previews[0]._pixmap_original is not None
                for _, tarjeta in ventana.tarjetas
            )

        # Desde B4.6 las previews se aplican de forma progresiva/diferida.
        esperar(_previews_aplicadas)
        ventana.carpeta_seleccionada = videos.name
        yield ventana
    finally:
        ventana.close()
        ventana.gestor.cerrar()
        ventana.gestor_previews.cerrar()
        escanear_mod.ruta_carpeta_miniaturas = original_escaneo
        visor_videos.ruta_carpeta_miniaturas = original_visor
        temp.cleanup()
        mini.cleanup()
        videos.cleanup()


def main():
    app = QApplication(sys.argv)

    _CONTADOR[0] = 1
    configurar_cantidad_previews(3)
    configurar_tamano_miniaturas("mediano")

    try:
        # --- 1) _pixmap_acotado: límite de memoria y preservación ---
        pequeno = QPixmap(160, 100)
        pequeno.fill(QColor("red"))
        verifica(
            _pixmap_acotado(pequeno) is pequeno
            and _pixmap_acotado(pequeno).size() == pequeno.size(),
            "imágenes pequeñas se conservan tal cual (mismo objeto)",
        )
        vacio = QPixmap()
        verifica(
            _pixmap_acotado(vacio) is vacio,
            "pixmap vacío se conserva",
        )
        grande = QPixmap(1920, 1080)
        grande.fill(QColor("red"))
        acotado = _pixmap_acotado(grande)
        verifica(
            acotado.size().toTuple() == (1280, 720),
            "1920x1080 se acota a 1280x720 (lado mayor 1280)",
            extra=acotado.size().toTuple(),
        )
        antes = 1920 * 1080 * 4
        despues = 1280 * 720 * 4
        verifica(
            despues < antes,
            "reducción de memoria del original almacenado",
            extra=f"{antes} -> {despues} bytes ({(1 - despues / antes) * 100:.0f}% menos)",
        )
        verifica(
            LIMITE_ORIGINAL_MINIATURA >= int(512 * 2.5),
            "el límite cubre la mayor salida (Muy grande 512 x 2.5 = 1280)",
            extra=f"limite={LIMITE_ORIGINAL_MINIATURA} max_salida={int(512 * 2.5)}",
        )

        # --- 2) el acotado se aplica al cargar previews y miniatura ---
        with _miniaturas_temporales() as carpeta:
            _guardar_png(os.path.join(carpeta, "clip_preview_01.jpg"), 1920, 1080)
            _guardar_png(os.path.join(carpeta, "clip_01.jpg"), 1920, 1080)
            tarjeta = Tarjeta(("clip.mp4", 100.0, 1920, 1080, "h264", 1, 1024))
            tarjeta.actualizar_previews(
                [os.path.join(carpeta, "clip_preview_01.jpg")]
            )
            verifica(
                tarjeta._etiquetas_previews[0]._pixmap_original.size().toTuple() == (1280, 720),
                "preview cargada se almacena acotada (1280x720)",
                extra=tarjeta._etiquetas_previews[0]._pixmap_original.size().toTuple(),
            )
            verifica(
                tarjeta._miniatura_original.size().toTuple() == (1280, 720),
                "miniatura principal se almacena acotada (1280x720)",
                extra=tarjeta._miniatura_original.size().toTuple(),
            )
            verifica(
                tarjeta._etiquetas_previews[0].pixmap() is not None
                and not tarjeta._etiquetas_previews[0].pixmap().isNull(),
                "la preview sigue mostrándose correctamente",
            )

        # --- 3) _duracion_valida y comportamiento sin cambios ---
        for valor in (5, 5.5, 100.0, 0.1):
            verifica(_duracion_valida(valor), f"_duracion_valida({valor!r}) True")
        for valor in (None, 0, -5, True, "5", 0.0):
            verifica(not _duracion_valida(valor), f"_duracion_valida({valor!r}) False")
        with _miniaturas_temporales() as carpeta:
            _guardar_png(os.path.join(carpeta, "clip_preview_01.jpg"), 160, 100)
            tarjeta = Tarjeta(("clip.mp4", 100.0, 1920, 1080, "h264", 1, 1024))
            tarjeta.actualizar_previews([os.path.join(carpeta, "clip_preview_01.jpg")])
            verifica(
                tarjeta._etiquetas_previews[0]._tiempo
                == formatear_tiempo(__import__("escanear_videos").calcular_tiempo_preview(100.0, 1)),
                "overlay intacto con duración válida (tras refactor del helper)",
            )
            sin = Tarjeta(("clip.mp4", None, 1920, 1080, "h264", 1, 1024))
            sin.actualizar_previews([os.path.join(carpeta, "clip_preview_01.jpg")])
            verifica(
                sin._etiquetas_previews[0]._tiempo is None,
                "sin overlay con duración inválida (tras refactor del helper)",
            )

        # --- 4) popup: transición limpia al cambiar de miniatura ---
        with _ventana_con() as ventana:
            tarjeta = dict(ventana.tarjetas)["clip.mp4"]
            etiqueta0 = tarjeta._etiquetas_previews[0]
            etiqueta1 = tarjeta._etiquetas_previews[1]
            orig0 = etiqueta0._pixmap_original
            orig1 = etiqueta1._pixmap_original
            verifica(
                orig0 is not None and orig1 is not None and orig0 is not orig1,
                "dos previews con originals distintos",
            )

            ventana._al_vista_solicitada(orig0)
            ventana._timer_vista_mostrar.timeout.emit()
            verifica(
                ventana._vista.isVisible() and ventana._vista._pixmap is orig0,
                "popup visible mostrando la primera imagen",
            )

            # misma imagen de nuevo: no se oculta
            ventana._al_vista_solicitada(orig0)
            ventana._timer_vista_mostrar.timeout.emit()
            verifica(
                ventana._vista.isVisible() and ventana._vista._pixmap is orig0,
                "re-entrada sobre la misma imagen no oculta",
            )

            # otra imagen: se oculta de inmediato y se muestra la nueva tras el retardo
            ventana._al_vista_solicitada(orig1)
            verifica(
                not ventana._vista.isVisible()
                and ventana._vista_pendiente is orig1,
                "al pasar a otra imagen el popup se oculta de inmediato",
            )
            ventana._timer_vista_mostrar.timeout.emit()
            verifica(
                ventana._vista.isVisible() and ventana._vista._pixmap is orig1,
                "tras el retardo se muestra la nueva imagen",
            )

        # --- 5) constantes realmente muertas eliminadas ---
        verifica(
            not hasattr(visor_videos, "ANCHO_PREVIEW")
            and not hasattr(visor_videos, "ALTO_PREVIEW"),
            "ANCHO_PREVIEW / ALTO_PREVIEW eliminadas (constantes muertas)",
        )

        # --- 6) memoria en el flujo real + vista ampliada sobre original acotado ---
        with _ventana_con() as ventana:
            tarjeta = dict(ventana.tarjetas)["clip.mp4"]
            orig = tarjeta._etiquetas_previews[0]._pixmap_original
            verifica(
                orig.size().toTuple() == (1280, 720),
                "flujo real: preview almacenada acotada (1280x720)",
                extra=orig.size().toTuple(),
            )
            ventana._vista.preparar(orig)
            verifica(
                ventana._vista._tam_amp == (int(320 * 1.6), int(180 * 1.6)),
                "vista ampliada funciona sobre el original acotado",
                extra=ventana._vista._tam_amp,
            )
            ventana._vista.preparar(tarjeta._miniatura_original)
            verifica(
                not ventana._vista._etiqueta.pixmap().isNull(),
                "ampliación de la miniatura principal acotada ok",
            )

        configurar_cantidad_previews(3)
        configurar_tamano_miniaturas("mediano")

    finally:
        configurar_cantidad_previews(3)
        configurar_tamano_miniaturas("mediano")

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
