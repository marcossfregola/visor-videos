import contextlib
import json
import os
import sqlite3
import sys
import tempfile
import time

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QDialog

import escanear_videos as escanear_mod
import visor_videos
from configuracion import (
    CLAVE_RETARDO_VISTA_AMPLIADA,
    guardar_retardo_vista_ampliada,
    obtener_retardo_vista_ampliada,
)
from visor_videos import PreferenciasDialog, VisorVideos

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


def _crear_previews(carpeta, prefijo, cantidad):
    for indice in range(1, cantidad + 1):
        _crear_png(
            os.path.join(carpeta, f"{prefijo}_preview_{indice:02d}.jpg")
        )


@contextlib.contextmanager
def _ventana_con(ms=None, sin_carpeta_config=False):
    temp = tempfile.TemporaryDirectory()
    mini = tempfile.TemporaryDirectory()
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
    filas = [("clip.mp4", "C:\\clip.mp4", ".mp4", "2026-08-06T00:00:00", 100.0, 1920, 1080, "h264", 1, 1024)]
    for i in range(30):
        nombre = f"clip_{i:02d}.mp4"
        filas.append((nombre, f"C:\\{nombre}", ".mp4", "2026-08-06T00:00:00", 100.0, 1920, 1080, "h264", 1, 1024))
    conn.executemany(
        "INSERT INTO videos (nombre, ruta, extension, fecha_importacion, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas, tamano_bytes) VALUES (?,?,?,?,?,?,?,?,?,?)",
        filas,
    )
    conn.commit()
    conn.close()

    if ms is not None and not sin_carpeta_config:
        guardar_retardo_vista_ampliada(ms, ruta_config)

    original_escaneo = escanear_mod.ruta_carpeta_miniaturas
    original_visor = visor_videos.ruta_carpeta_miniaturas
    escanear_mod.ruta_carpeta_miniaturas = lambda: mini.name
    visor_videos.ruta_carpeta_miniaturas = lambda: mini.name
    _crear_previews(mini.name, "clip", 3)
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
        yield ventana, ruta_config
    finally:
        ventana.close()
        ventana.gestor.cerrar()
        ventana.gestor_previews.cerrar()
        escanear_mod.ruta_carpeta_miniaturas = original_escaneo
        visor_videos.ruta_carpeta_miniaturas = original_visor
        temp.cleanup()
        mini.cleanup()


def main():
    app = QApplication(sys.argv)

    _CONTADOR[0] = 1

    # --- 1) persistencia del retardo ---
    temp_config = tempfile.TemporaryDirectory()
    ruta_config = os.path.join(temp_config.name, "config.json")
    try:
        for ms in (0, 250, 400, 600):
            guardar_retardo_vista_ampliada(ms, ruta_config)
            with open(ruta_config, encoding="utf-8") as f:
                contenido = json.load(f)
            verifica(
                contenido.get(CLAVE_RETARDO_VISTA_AMPLIADA) == ms
                and obtener_retardo_vista_ampliada(ruta_config) == ms,
                f"persistencia round-trip retardo {ms}",
            )
        for invalido in (True, 100, "400", -5, 3.5):
            guardar_retardo_vista_ampliada(invalido, ruta_config)
            verifica(
                obtener_retardo_vista_ampliada(ruta_config) == 600,
                f"guardar inválido ({invalido!r}) no modifica y conserva el último válido",
            )
        ruta_no = os.path.join(temp_config.name, "inexistente.json")
        verifica(
            obtener_retardo_vista_ampliada(ruta_no) == 400,
            "obtener sin archivo devuelve 400 (default)",
        )
        con_invalido = os.path.join(temp_config.name, "invalido.json")
        with open(con_invalido, "w", encoding="utf-8") as f:
            json.dump({CLAVE_RETARDO_VISTA_AMPLIADA: 100}, f)
        verifica(
            obtener_retardo_vista_ampliada(con_invalido) == 400,
            "valor almacenado inválido vuelve a 400 (default)",
        )
    finally:
        temp_config.cleanup()

    # --- 2) diálogo: valores discretos y default ---
    temp_config = tempfile.TemporaryDirectory()
    ruta_config = os.path.join(temp_config.name, "config.json")
    try:
        dialogo = PreferenciasDialog(ruta_config)
        verifica(
            dialogo.retardo_seleccionado() == 400,
            "diálogo: default 400 ms",
            extra=dialogo.combo_retardo.currentText(),
        )
        for texto, ms in (("Inmediato", 0), ("250 ms", 250), ("600 ms", 600)):
            dialogo.combo_retardo.setCurrentIndex(
                dialogo.combo_retardo.findText(texto)
            )
            verifica(
                dialogo.retardo_seleccionado() == ms,
                f"diálogo: {texto} -> {ms} ms",
            )
    finally:
        temp_config.cleanup()

    # --- 3) ventana: combos existentes preservados + botón Preferencias ---
    with _ventana_con() as (ventana, ruta_config):
        verifica(
            hasattr(ventana, "combo_cantidad_previews")
            and hasattr(ventana, "combo_tamano_miniaturas"),
            "los controles Previews y Tamaño permanecen en la barra (acceso directo)",
        )
        verifica(
            hasattr(ventana, "boton_preferencias"),
            "existe el botón Preferencias…",
        )
        verifica(
            ventana._timer_vista_mostrar.interval() == 400,
            "intervalo inicial del retardo = 400 (default)",
        )

    # --- 4) aplicación inmediata y persistencia ---
    with _ventana_con() as (ventana, ruta_config):
        ventana._aplicar_retardo_vista_ampliada(600)
        verifica(
            ventana._timer_vista_mostrar.interval() == 600,
            "aplicar 600 ms actualiza el intervalo inmediatamente",
        )
        verifica(
            obtener_retardo_vista_ampliada(ruta_config) == 600,
            "aplicar 600 ms persiste en la configuración",
        )
        verifica(
            not ventana.gestor.activo and len(ventana.tarjetas) == 31,
            "aplicar el retardo no reconstruye ni escanea (tarjetas intactas)",
        )
        ventana._aplicar_retardo_vista_ampliada(0)
        verifica(
            ventana._timer_vista_mostrar.interval() == 0,
            "aplicar 'Inmediato' (0 ms) actualiza el intervalo",
        )

    # --- 5) flujo del diálogo: aceptar aplica, cancelar no ---
    with _ventana_con() as (ventana, ruta_config):
        original_exec = visor_videos.PreferenciasDialog.exec

        def _aceptar_600(self):
            self.combo_retardo.setCurrentIndex(
                self.combo_retardo.findText("600 ms")
            )
            return QDialog.Accepted

        visor_videos.PreferenciasDialog.exec = _aceptar_600
        ventana.boton_preferencias.click()
        QApplication.processEvents()
        visor_videos.PreferenciasDialog.exec = original_exec
        verifica(
            ventana._timer_vista_mostrar.interval() == 600
            and obtener_retardo_vista_ampliada(ruta_config) == 600,
            "aceptar el diálogo aplica y persiste el retardo",
        )

    with _ventana_con() as (ventana, ruta_config):
        visor_videos.PreferenciasDialog.exec = lambda self: QDialog.Rejected
        ventana._aplicar_retardo_vista_ampliada(250)
        ventana.boton_preferencias.click()
        QApplication.processEvents()
        visor_videos.PreferenciasDialog.exec = original_exec
        verifica(
            ventana._timer_vista_mostrar.interval() == 250
            and obtener_retardo_vista_ampliada(ruta_config) == 250,
            "cancelar el diálogo no cambia el retardo vigente",
        )

    # --- 6) restauración al iniciar (config existente y config inválida) ---
    with _ventana_con(ms=600) as (ventana, ruta_config):
        verifica(
            ventana._timer_vista_mostrar.interval() == 600,
            "restauración: configuración con 600 ms aplicada al iniciar",
        )
    with _ventana_con(ms=100) as (ventana, ruta_config):
        verifica(
            ventana._timer_vista_mostrar.interval() == 400,
            "restauración: valor inválido (100) vuelve a 400",
        )

    # --- 7) vista ampliada usa el retardo configurado ---
    with _ventana_con() as (ventana, ruta_config):
        ventana._aplicar_retardo_vista_ampliada(600)
        tarjeta = dict(ventana.tarjetas)["clip.mp4"]
        etiqueta = tarjeta._etiquetas_previews[0]
        from PySide6.QtCore import QEvent
        QApplication.sendEvent(etiqueta, QEvent(QEvent.Enter))
        verifica(
            not ventana._vista.isVisible() and ventana._vista_pendiente is not None,
            "con retardo 600: pendiente, aún no visible",
        )
        ventana._timer_vista_mostrar.timeout.emit()
        verifica(
            ventana._vista.isVisible(),
            "con retardo 600: visible al vencer el timer",
        )
        ventana._ocultar_vista()
        ventana._aplicar_retardo_vista_ampliada(0)
        QApplication.sendEvent(etiqueta, QEvent(QEvent.Enter))
        verifica(
            ventana._timer_vista_mostrar.interval() == 0,
            "retardo 'Inmediato' usa intervalo 0",
        )

    # --- 8) selección y scroll se conservan al aplicar el retardo ---
    with _ventana_con() as (ventana, ruta_config):
        ventana._al_seleccionar_tarjeta("clip.mp4", False)
        scrollbar = ventana.area.verticalScrollBar()
        scrollbar.setValue(20)
        QApplication.processEvents()
        ventana._aplicar_retardo_vista_ampliada(600)
        verifica(
            "clip.mp4" in ventana.nombres_seleccionados,
            "la selección se conserva al aplicar el retardo",
        )
        verifica(
            scrollbar.value() == 20,
            "la posición del scroll se conserva al aplicar el retardo",
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
