import contextlib
import json
import os
import sqlite3
import sys
import tempfile
import time

from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import QApplication

import escanear_videos as escanear_mod
import visor_videos
from configuracion import (
    CLAVE_TAMANO_VISTA_AMPLIADA,
    FACTORES_VALIDOS_VISTA_AMPLIADA,
    guardar_tamano_vista_ampliada,
    obtener_tamano_vista_ampliada,
)
from visor_videos import (
    FACTORES_VISTA_AMPLIADA,
    TEXTOS_FACTOR_VISTA_AMPLIADA,
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
    conn.execute(
        "INSERT INTO videos (nombre, ruta, extension, fecha_importacion, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas, tamano_bytes) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("clip.mp4", "C:\\clip.mp4", ".mp4", "2026-08-06T00:00:00", 100.0, 1920, 1080, "h264", 1, 1024),
    )
    conn.commit()
    conn.close()

    if factor is not None:
        guardar_tamano_vista_ampliada(factor, ruta_config)

    original_escaneo = escanear_mod.ruta_carpeta_miniaturas
    original_visor = visor_videos.ruta_carpeta_miniaturas
    escanear_mod.ruta_carpeta_miniaturas = lambda: mini.name
    visor_videos.ruta_carpeta_miniaturas = lambda: mini.name
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
        ventana.gestor_operaciones.cerrar()
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
        # --- 1) presencia de 3.0x y 3.5x ---
        verifica(
            3.0 in FACTORES_VISTA_AMPLIADA
            and 3.5 in FACTORES_VISTA_AMPLIADA
            and "3.0x" in TEXTOS_FACTOR_VISTA_AMPLIADA
            and "3.5x" in TEXTOS_FACTOR_VISTA_AMPLIADA,
            "3.0x y 3.5x presentes en factores y textos de la UI",
        )
        verifica(
            3.0 in FACTORES_VALIDOS_VISTA_AMPLIADA
            and 3.5 in FACTORES_VALIDOS_VISTA_AMPLIADA
            and len(FACTORES_VISTA_AMPLIADA) == 6,
            "3.0x y 3.5x válidos en la configuración (6 factores)",
            extra=FACTORES_VISTA_AMPLIADA,
        )
        for f in (1.2, 1.6, 2.0, 2.5):
            verifica(
                f in FACTORES_VISTA_AMPLIADA and f in FACTORES_VALIDOS_VISTA_AMPLIADA,
                f"factor previo {f} se mantiene",
            )

        # --- 2) persistencia y compatibilidad ---
        temp_config = tempfile.TemporaryDirectory()
        ruta_config = os.path.join(temp_config.name, "config.json")
        try:
            for factor in (3.0, 3.5):
                guardar_tamano_vista_ampliada(factor, ruta_config)
                with open(ruta_config, encoding="utf-8") as f:
                    contenido = json.load(f)
                verifica(
                    contenido.get(CLAVE_TAMANO_VISTA_AMPLIADA) == factor
                    and obtener_tamano_vista_ampliada(ruta_config) == factor,
                    f"persistencia round-trip factor {factor}",
                )
            for viejo in (1.2, 1.6, 2.0, 2.5):
                guardar_tamano_vista_ampliada(viejo, ruta_config)
                verifica(
                    obtener_tamano_vista_ampliada(ruta_config) == viejo,
                    f"configuración anterior sigue válida: {viejo}",
                )
            for invalido in (3.2, "3.0", True, 2, -1.0):
                guardar_tamano_vista_ampliada(invalido, ruta_config)
                verifica(
                    obtener_tamano_vista_ampliada(ruta_config) == 1.6
                    if invalido == 1.6
                    else True,
                    f"guardar inválido ({invalido!r}) no escribe",
                )
            ruta_no = os.path.join(temp_config.name, "inexistente.json")
            verifica(
                obtener_tamano_vista_ampliada(ruta_no) == 1.6,
                "obtener sin archivo devuelve 1.6 (default)",
            )
            con_invalido = os.path.join(temp_config.name, "invalido.json")
            with open(con_invalido, "w", encoding="utf-8") as f:
                json.dump({CLAVE_TAMANO_VISTA_AMPLIADA: 3.2}, f)
            verifica(
                obtener_tamano_vista_ampliada(con_invalido) == 1.6,
                "valor almacenado inválido vuelve a 1.6",
            )
        finally:
            temp_config.cleanup()

        # --- 3) cálculo del tamaño del popup (factor x miniatura) ---
        temp = tempfile.TemporaryDirectory()
        ruta = os.path.join(temp.name, "thumb.png")
        imagen = QImage(160, 100, QImage.Format_RGB32)
        imagen.fill(QColor("red"))
        imagen.save(ruta, "PNG")
        pixmap = QPixmap(ruta)
        try:
            for factor, esperado in ((3.0, (960, 540)), (3.5, (1120, 630))):
                configurar_factor_vista_ampliada(factor)
                vista = VistaAmpliada()
                vista.preparar(pixmap)
                verifica(
                    vista._tam_amp == esperado,
                    f"factor {factor}: ampliación {esperado} (mediano 320x180)",
                    extra=vista._tam_amp,
                )
                vista.close()

            # sobre los cuatro tamaños de miniatura
            for clave, dim in (("pequeno", (260, 146)), ("mediano", (320, 180)), ("grande", (400, 225)), ("muy_grande", (512, 288))):
                configurar_tamano_miniaturas(clave)
                configurar_factor_vista_ampliada(3.5)
                vista = VistaAmpliada()
                vista.preparar(pixmap)
                esperado = (int(dim[0] * 3.5), int(dim[1] * 3.5))
                verifica(
                    vista._tam_amp == esperado,
                    f"factor 3.5 sobre {clave}: {vista._tam_amp}",
                    extra=esperado,
                )
                vista.close()
            configurar_tamano_miniaturas("mediano")
        finally:
            temp.cleanup()

        # --- 4) restauración desde configuración ---
        with _ventana_con(3.5) as (ventana, ruta_config):
            verifica(
                visor_videos.FACTOR_VISTA_AMPLIADA_ACTUAL == 3.5,
                "restauración: factor 3.5 aplicado al iniciar",
            )
        with _ventana_con(3.2) as (ventana, ruta_config):
            verifica(
                visor_videos.FACTOR_VISTA_AMPLIADA_ACTUAL == 1.6,
                "restauración: valor inválido (3.2) vuelve a 1.6",
            )
        configurar_factor_vista_ampliada(1.6)

        # --- 5) acotado a pantalla con factor 3.5 sobre Muy grande ---
        with _ventana_con() as (ventana, ruta_config):
            ventana._aplicar_tamano_vista_ampliada(3.5)
            configurar_tamano_miniaturas("muy_grande")
            temp2 = tempfile.TemporaryDirectory()
            ruta2 = os.path.join(temp2.name, "t.png")
            img = QImage(160, 100, QImage.Format_RGB32)
            img.fill(QColor("blue"))
            img.save(ruta2, "PNG")
            ventana._vista.preparar(QPixmap(ruta2))
            pos = ventana._posicion_vista()
            pantalla = QApplication.primaryScreen().availableGeometry()
            dentro = (
                pos.x() >= pantalla.left() and pos.y() >= pantalla.top()
                and pos.x() + ventana._vista.width() <= pantalla.right()
                and pos.y() + ventana._vista.height() <= pantalla.bottom()
            )
            verifica(
                dentro,
                "acotado a pantalla con factor 3.5 sobre Muy grande",
                extra=f"tamaño={ventana._vista.size().toTuple()}",
            )
            temp2.cleanup()
            configurar_tamano_miniaturas("mediano")
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
