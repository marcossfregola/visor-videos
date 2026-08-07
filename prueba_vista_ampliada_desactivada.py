import contextlib
import json
import os
import sqlite3
import sys
import tempfile
import time

from PySide6.QtCore import QEvent
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

import escanear_videos as escanear_mod
import visor_videos
from configuracion import (
    CLAVE_RETARDO_VISTA_AMPLIADA,
    guardar_retardo_vista_ampliada,
    obtener_retardo_vista_ampliada,
)
from visor_videos import VisorVideos

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


def _crear_png(ruta):
    imagen = QImage(160, 100, QImage.Format_RGB32)
    imagen.fill(QColor("red"))
    return imagen.save(ruta, "PNG")


@contextlib.contextmanager
def _ventana_con(ms):
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
        ("clip.mp4", "C:\\clip.mp4", ".mp4", "2026-08-06T00:00:00", 100.0, 1920, 1080, "h264", 1, 1024),
    )
    conn.commit()
    conn.close()

    guardar_retardo_vista_ampliada(ms, ruta_config)

    original_escaneo = escanear_mod.ruta_carpeta_miniaturas
    original_visor = visor_videos.ruta_carpeta_miniaturas
    escanear_mod.ruta_carpeta_miniaturas = lambda: mini.name
    visor_videos.ruta_carpeta_miniaturas = lambda: mini.name
    _crear_png(os.path.join(mini.name, "clip_preview_01.jpg"))
    _crear_png(os.path.join(mini.name, "clip_preview_02.jpg"))
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
        ventana.carpeta_seleccionada = videos.name
        yield ventana, ruta_config
    finally:
        ventana.close()
        ventana.gestor.cerrar()
        ventana.gestor_previews.cerrar()
        ventana.gestor_operaciones.cerrar()
        escanear_mod.ruta_carpeta_miniaturas = original_escaneo
        visor_videos.ruta_carpeta_miniaturas = original_visor
        temp.cleanup()
        mini.cleanup()
        videos.cleanup()


def main():
    app = QApplication(sys.argv)

    _CONTADOR[0] = 1

    # --- A) persistencia y compatibilidad del valor -1 ---
    temp_config = tempfile.TemporaryDirectory()
    ruta_config = os.path.join(temp_config.name, "config.json")
    try:
        guardar_retardo_vista_ampliada(-1, ruta_config)
        with open(ruta_config, encoding="utf-8") as f:
            contenido = json.load(f)
        verifica(
            contenido.get(CLAVE_RETARDO_VISTA_AMPLIADA) == -1
            and obtener_retardo_vista_ampliada(ruta_config) == -1,
            "persistencia del valor -1 (Desactivado)",
        )
        for invalido in (True, 100, "400", -5, 3.5):
            guardar_retardo_vista_ampliada(invalido, ruta_config)
            verifica(
                obtener_retardo_vista_ampliada(ruta_config) == -1,
                f"guardar inválido ({invalido!r}) conserva el último válido (-1)",
            )
        ruta_no = os.path.join(temp_config.name, "inexistente.json")
        verifica(
            obtener_retardo_vista_ampliada(ruta_no) == 400,
            "obtener sin archivo sigue devolviendo 400 (default)",
        )
        con_invalido = os.path.join(temp_config.name, "invalido.json")
        with open(con_invalido, "w", encoding="utf-8") as f:
            json.dump({CLAVE_RETARDO_VISTA_AMPLIADA: 100}, f)
        verifica(
            obtener_retardo_vista_ampliada(con_invalido) == 400,
            "valor almacenado inválido sigue volviendo a 400",
        )
    finally:
        temp_config.cleanup()

    # --- B) restauración: retardo -1 en la configuración ---
    with _ventana_con(-1) as (ventana, ruta_config):
        verifica(
            ventana._retardo_vista_ampliada == -1,
            "restauración: retardo -1 aplicado al iniciar",
        )
        tarjeta = dict(ventana.tarjetas)["clip.mp4"]
        etiqueta = tarjeta._etiquetas_previews[0]
        verifica(
            etiqueta._pixmap_original is not None,
            "la preview tiene el pixmap original cargado",
        )
        QApplication.sendEvent(etiqueta, QEvent(QEvent.Enter))
        QApplication.processEvents()
        verifica(
            not ventana._timer_vista_mostrar.isActive()
            and ventana._vista_pendiente is None
            and not ventana._vista.isVisible(),
            "con 'Desactivado': no se inicia el timer ni aparece el popup",
        )
        # mover el mouse sobre varias previews: ninguna acción
        for e in tarjeta._etiquetas_previews:
            QApplication.sendEvent(e, QEvent(QEvent.Enter))
            QApplication.sendEvent(e, QEvent(QEvent.Leave))
        QApplication.processEvents()
        verifica(
            not ventana._vista.isVisible() and ventana._vista_pendiente is None,
            "recorrer previews con 'Desactivado' no produce ninguna acción",
        )
        ventana._timer_vista_mostrar.timeout.emit()
        QApplication.processEvents()
        verifica(
            not ventana._vista.isVisible(),
            "incluso disparando el timeout, el popup nunca aparece",
        )

    # --- C) persistencia al aplicar -1 y reactivación ---
    with _ventana_con(400) as (ventana, ruta_config):
        tarjeta = dict(ventana.tarjetas)["clip.mp4"]
        etiqueta = tarjeta._etiquetas_previews[0]

        ventana._aplicar_retardo_vista_ampliada(-1)
        verifica(
            ventana._retardo_vista_ampliada == -1
            and obtener_retardo_vista_ampliada(ruta_config) == -1,
            "aplicar -1 persiste y actualiza el estado",
        )
        QApplication.sendEvent(etiqueta, QEvent(QEvent.Enter))
        ventana._timer_vista_mostrar.timeout.emit()
        QApplication.processEvents()
        verifica(
            not ventana._vista.isVisible(),
            "tras aplicar 'Desactivado' el popup no aparece",
        )
        ventana._timer_vista_ocultar.stop()

        # reactivar a 400
        ventana._aplicar_retardo_vista_ampliada(400)
        verifica(
            ventana._retardo_vista_ampliada == 400
            and obtener_retardo_vista_ampliada(ruta_config) == 400
            and ventana._timer_vista_mostrar.interval() == 400,
            "reactivar a 400 ms actualiza estado, persistencia e intervalo",
        )
        QApplication.sendEvent(etiqueta, QEvent(QEvent.Enter))
        verifica(
            ventana._vista_pendiente is not None
            and ventana._timer_vista_mostrar.isActive(),
            "reactivado: el timer se inicia de nuevo",
        )
        ventana._timer_vista_mostrar.timeout.emit()
        QApplication.processEvents()
        verifica(
            ventana._vista.isVisible(),
            "reactivado: el popup vuelve a aparecer",
        )
        ventana._ocultar_vista()

        # ocultar el popup si se desactiva estando visible
        ventana._aplicar_retardo_vista_ampliada(400)
        QApplication.sendEvent(etiqueta, QEvent(QEvent.Enter))
        ventana._timer_vista_mostrar.timeout.emit()
        QApplication.processEvents()
        verifica(ventana._vista.isVisible(), "popup visible antes de desactivar")
        ventana._aplicar_retardo_vista_ampliada(-1)
        QApplication.processEvents()
        verifica(
            not ventana._vista.isVisible(),
            "aplicar 'Desactivado' oculta el popup si estaba visible",
        )

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
