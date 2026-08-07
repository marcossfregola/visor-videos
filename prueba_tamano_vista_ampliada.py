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
    CLAVE_TAMANO_VISTA_AMPLIADA,
    guardar_tamano_vista_ampliada,
    obtener_tamano_vista_ampliada,
)
from visor_videos import (
    FACTORES_VISTA_AMPLIADA,
    PreferenciasDialog,
    VistaAmpliada,
    VisorVideos,
    configurar_factor_vista_ampliada,
    configurar_tamano_miniaturas,
    dimensiones_miniatura,
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


def _crear_png(ruta):
    imagen = QImage(160, 100, QImage.Format_RGB32)
    imagen.fill(QColor("red"))
    return imagen.save(ruta, "PNG")


def _crear_previews(carpeta, prefijo, cantidad):
    for indice in range(1, cantidad + 1):
        _crear_png(os.path.join(carpeta, f"{prefijo}_preview_{indice:02d}.jpg"))


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
def _ventana_con(factor=None):
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
    filas = [_fila_bd("clip.mp4", 100.0)]
    for i in range(20):
        filas.append(_fila_bd(f"extra_{i:02d}.mp4", 100.0))
    conn.executemany(
        "INSERT INTO videos (nombre, ruta, extension, fecha_importacion, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas, tamano_bytes) VALUES (?,?,?,?,?,?,?,?,?,?)",
        filas,
    )
    conn.commit()
    conn.close()

    if factor is not None:
        guardar_tamano_vista_ampliada(factor, ruta_config)

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
    configurar_factor_vista_ampliada(1.6)
    configurar_tamano_miniaturas("mediano")

    try:
        # --- 1) persistencia del factor ---
        temp_config = tempfile.TemporaryDirectory()
        ruta_config = os.path.join(temp_config.name, "config.json")
        try:
            for factor in (1.2, 1.6, 2.0, 2.5):
                guardar_tamano_vista_ampliada(factor, ruta_config)
                with open(ruta_config, encoding="utf-8") as f:
                    contenido = json.load(f)
                verifica(
                    contenido.get(CLAVE_TAMANO_VISTA_AMPLIADA) == factor
                    and obtener_tamano_vista_ampliada(ruta_config) == factor,
                    f"persistencia round-trip factor {factor}",
                )
            for invalido in (True, 1.5, "1.6", 2, 3.0, -1.0):
                guardar_tamano_vista_ampliada(invalido, ruta_config)
                verifica(
                    obtener_tamano_vista_ampliada(ruta_config) == 2.5,
                    f"guardar inválido ({invalido!r}) no modifica y conserva el último válido",
                )
            ruta_no = os.path.join(temp_config.name, "inexistente.json")
            verifica(
                obtener_tamano_vista_ampliada(ruta_no) == 1.6,
                "obtener sin archivo devuelve 1.6 (default)",
            )
            con_invalido = os.path.join(temp_config.name, "invalido.json")
            with open(con_invalido, "w", encoding="utf-8") as f:
                json.dump({CLAVE_TAMANO_VISTA_AMPLIADA: 1.5}, f)
            verifica(
                obtener_tamano_vista_ampliada(con_invalido) == 1.6,
                "valor almacenado inválido vuelve a 1.6",
            )
        finally:
            temp_config.cleanup()

        # --- 2) configurar_factor_vista_ampliada ---
        for factor in FACTORES_VISTA_AMPLIADA:
            configurar_factor_vista_ampliada(factor)
            verifica(
                visor_videos.FACTOR_VISTA_AMPLIADA_ACTUAL == factor,
                f"configurar_factor_vista_ampliada({factor})",
            )
        configurar_factor_vista_ampliada(1.9)
        verifica(
            visor_videos.FACTOR_VISTA_AMPLIADA_ACTUAL == 2.5,
            "factor inválido se ignora",
        )
        configurar_factor_vista_ampliada(1.6)

        # --- 3) preparar escala con el factor configurado ---
        with _miniaturas_temporales() as carpeta:
            ruta = os.path.join(carpeta, "thumb.png")
            _crear_png(ruta)
            from PySide6.QtGui import QPixmap
            pixmap = QPixmap(ruta)
            for factor, esperado in ((1.2, (384, 216)), (1.6, (512, 288)), (2.0, (640, 360)), (2.5, (800, 450))):
                configurar_factor_vista_ampliada(factor)
                vista = VistaAmpliada()
                vista.preparar(pixmap)
                verifica(
                    vista._tam_amp == esperado,
                    f"factor {factor}: ampliación {esperado} (mediano 320x180)",
                    extra=vista._tam_amp,
                )
                vista.close()
            configurar_factor_vista_ampliada(1.6)

        # --- 4) diálogo: default y mapeo ---
        temp_config = tempfile.TemporaryDirectory()
        ruta_config = os.path.join(temp_config.name, "config.json")
        try:
            dialogo = PreferenciasDialog(ruta_config)
            verifica(
                dialogo.factor_vista_seleccionado() == 1.6,
                "diálogo: default 1.6",
                extra=dialogo.combo_factor_vista.currentText(),
            )
            for texto, factor in (("1.2x", 1.2), ("2.0x", 2.0), ("2.5x", 2.5)):
                dialogo.combo_factor_vista.setCurrentIndex(
                    dialogo.combo_factor_vista.findText(texto)
                )
                verifica(
                    dialogo.factor_vista_seleccionado() == factor,
                    f"diálogo: {texto} -> {factor}",
                )
        finally:
            temp_config.cleanup()

        # --- 5) flujo del diálogo: aceptar aplica, cancelar no ---
        with _ventana_con() as (ventana, ruta_config):
            original_exec = visor_videos.PreferenciasDialog.exec

            def _aceptar_20(self):
                self.combo_factor_vista.setCurrentIndex(
                    self.combo_factor_vista.findText("2.0x")
                )
                return QDialog.Accepted

            visor_videos.PreferenciasDialog.exec = _aceptar_20
            ventana.boton_preferencias.click()
            QApplication.processEvents()
            visor_videos.PreferenciasDialog.exec = original_exec
            verifica(
                visor_videos.FACTOR_VISTA_AMPLIADA_ACTUAL == 2.0
                and obtener_tamano_vista_ampliada(ruta_config) == 2.0,
                "aceptar el diálogo aplica y persiste el factor 2.0",
            )

        with _ventana_con() as (ventana, ruta_config):
            configurar_factor_vista_ampliada(1.2)
            visor_videos.PreferenciasDialog.exec = lambda self: QDialog.Rejected
            ventana.boton_preferencias.click()
            QApplication.processEvents()
            visor_videos.PreferenciasDialog.exec = original_exec
            verifica(
                visor_videos.FACTOR_VISTA_AMPLIADA_ACTUAL == 1.2,
                "cancelar el diálogo conserva el factor vigente",
            )
        configurar_factor_vista_ampliada(1.6)

        # --- 6) restauración al iniciar ---
        with _ventana_con(factor=2.5) as (ventana, ruta_config):
            verifica(
                visor_videos.FACTOR_VISTA_AMPLIADA_ACTUAL == 2.5,
                "restauración: configuración con 2.5 aplicada al iniciar",
            )
        with _ventana_con(factor=1.9) as (ventana, ruta_config):
            verifica(
                visor_videos.FACTOR_VISTA_AMPLIADA_ACTUAL == 1.6,
                "restauración: valor inválido (1.9) vuelve a 1.6",
            )
        configurar_factor_vista_ampliada(1.6)

        # --- 7) integración: cambio del factor, selección y scroll ---
        with _ventana_con() as (ventana, ruta_config):
            ventana._al_seleccionar_tarjeta("clip.mp4", False)
            scrollbar = ventana.area.verticalScrollBar()
            scrollbar.setValue(60)
            QApplication.processEvents()
            ventana._aplicar_tamano_vista_ampliada(2.0)
            verifica(
                visor_videos.FACTOR_VISTA_AMPLIADA_ACTUAL == 2.0,
                "aplicar factor 2.0 de inmediato",
            )
            verifica(
                "clip.mp4" in ventana.nombres_seleccionados,
                "selección conservada al aplicar el factor",
            )
            verifica(
                scrollbar.value() == 60,
                "scroll conservado al aplicar el factor",
                extra=f"valor={scrollbar.value()}",
            )
            verifica(
                not ventana.gestor.activo,
                "sin escaneo ni reconstrucción",
            )
            tarjeta = dict(ventana.tarjetas)["clip.mp4"]
            etiqueta = tarjeta._etiquetas_previews[0]
            ventana._vista.preparar(etiqueta._pixmap_original)
            verifica(
                ventana._vista._tam_amp == (int(320 * 2.0), int(180 * 2.0)),
                "popup ampliado a 2.0x sobre mediano",
                extra=ventana._vista._tam_amp,
            )

        # --- 8) acotado a pantalla ---
        with _ventana_con() as (ventana, ruta_config):
            ventana._aplicar_tamano_vista_ampliada(2.5)
            tarjeta = dict(ventana.tarjetas)["clip.mp4"]
            etiqueta = tarjeta._etiquetas_previews[0]
            ventana._vista.preparar(etiqueta._pixmap_original)
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
                "acotado a pantalla con factor 2.5",
                extra=f"tamaño={ventana._vista.size().toTuple()}",
            )
        configurar_factor_vista_ampliada(1.6)

    finally:
        configurar_factor_vista_ampliada(1.6)
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
