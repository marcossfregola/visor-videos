import contextlib
import json
import os
import sqlite3
import sys
import tempfile
import time

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

import escanear_videos as escanear_mod
import visor_videos
from configuracion import (
    CLAVE_TAMANIO_MINIATURAS,
    guardar_tamano_miniaturas,
    obtener_tamano_miniaturas,
)
from visor_videos import (
    Tarjeta,
    VisorVideos,
    clave_tamano_miniaturas,
    configurar_tamano_miniaturas,
    dimensiones_miniatura,
    texto_tamano_miniaturas,
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
    imagen = QImage(120, 80, QImage.Format_RGB32)
    imagen.fill(QColor(color))
    return imagen.save(ruta, "PNG")


def _crear_previews(carpeta, prefijo, cantidad):
    rutas = []
    for indice in range(1, cantidad + 1):
        ruta = os.path.join(carpeta, f"{prefijo}_preview_{indice:02d}.jpg")
        _crear_png(ruta)
        rutas.append(ruta)
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


def main():
    app = QApplication(sys.argv)

    _CONTADOR[0] = 1
    configurar_tamano_miniaturas("mediano")

    try:
        # --- 1) presets y resolvedor ---
        verifica(
            dimensiones_miniatura() == (320, 180),
            "default: mediano (320x180)",
        )
        configurar_tamano_miniaturas("pequeno")
        verifica(
            dimensiones_miniatura() == (260, 146),
            "pequeno: 260x146",
        )
        configurar_tamano_miniaturas("grande")
        verifica(
            dimensiones_miniatura() == (400, 225),
            "grande: 400x225",
        )
        configurar_tamano_miniaturas("invalido")
        verifica(
            dimensiones_miniatura() == (400, 225),
            "clave inválida: se ignora",
        )
        configurar_tamano_miniaturas("mediano")

        # --- 2) mapeo texto <-> clave ---
        verifica(
            texto_tamano_miniaturas("pequeno") == "Pequeño"
            and texto_tamano_miniaturas("mediano") == "Mediano"
            and texto_tamano_miniaturas("grande") == "Grande"
            and texto_tamano_miniaturas("otro") == "Mediano",
            "texto_tamano_miniaturas mapea correctamente",
        )
        verifica(
            clave_tamano_miniaturas("Pequeño") == "pequeno"
            and clave_tamano_miniaturas("Mediano") == "mediano"
            and clave_tamano_miniaturas("Grande") == "grande"
            and clave_tamano_miniaturas("Otro") == "mediano",
            "clave_tamano_miniaturas mapea correctamente",
        )

        # --- 3) persistencia ---
        temp_config = tempfile.TemporaryDirectory()
        ruta_config = os.path.join(temp_config.name, "config.json")
        try:
            for nombre in ("pequeno", "mediano", "grande"):
                guardar_tamano_miniaturas(nombre, ruta_config)
                with open(ruta_config, encoding="utf-8") as f:
                    contenido = json.load(f)
                verifica(
                    contenido.get(CLAVE_TAMANIO_MINIATURAS) == nombre
                    and obtener_tamano_miniaturas(ruta_config) == nombre,
                    f"persistencia round-trip: {nombre}",
                )
            verifica(
                guardar_tamano_miniaturas("enorme", ruta_config) is None,
                "guardar inválido devuelve None sin escribir",
            )
            verifica(
                obtener_tamano_miniaturas(ruta_config) == "grande",
                "tras guardar inválido conserva el último válido",
            )
            ruta_no = os.path.join(temp_config.name, "inexistente.json")
            verifica(
                obtener_tamano_miniaturas(ruta_no) == "mediano",
                "obtener sin archivo devuelve mediano",
            )
            con_invalido = os.path.join(temp_config.name, "invalido.json")
            with open(con_invalido, "w", encoding="utf-8") as f:
                json.dump({CLAVE_TAMANIO_MINIATURAS: "huge"}, f)
            verifica(
                obtener_tamano_miniaturas(con_invalido) == "mediano",
                "valor almacenado inválido vuelve a mediano",
            )
        finally:
            temp_config.cleanup()

        # --- 4) cambio en memoria, sin releer disco ni regenerar ---
        configurar_tamano_miniaturas("mediano")
        with _miniaturas_temporales() as carpeta:
            _crear_previews(carpeta, "clip", 3)
            with _contar_qpixmap() as contador:
                tarjeta = Tarjeta(("clip.mp4", 100.0, 1920, 1080, "h264", 1, 1024))
                tarjeta.actualizar_previews(_crear_previews(carpeta, "clip", 3))
                alturas = [e.height() for e in tarjeta._etiquetas_previews]
                verifica(
                    alturas == [180, 180, 180],
                    "tarjeta inicial en mediano (altura 180)",
                    extra=alturas,
                )
                base = contador[0]

                configurar_tamano_miniaturas("grande")
                tarjeta.aplicar_tamano()
                alturas = [e.height() for e in tarjeta._etiquetas_previews]
                verifica(
                    alturas == [225, 225, 225],
                    "cambio a grande sin reconstruir (altura 225)",
                    extra=alturas,
                )
                verifica(
                    contador[0] == base,
                    "el cambio de tamaño no crea QPixmap nuevos (sin releer disco)",
                    extra=f"construcciones={contador[0] - base}",
                )
                tiempos = [e._tiempo for e in tarjeta._etiquetas_previews]
                verifica(
                    all(t is not None for t in tiempos),
                    "el overlay de B3.1 se conserva tras redimensionar",
                )
                for e in tarjeta._etiquetas_previews:
                    verifica(
                        not e.grab().isNull(),
                        "overlay renderiza en tamaño grande sin errores",
                    )

                configurar_tamano_miniaturas("pequeno")
                tarjeta.aplicar_tamano()
                alturas = [e.height() for e in tarjeta._etiquetas_previews]
                verifica(
                    alturas == [146, 146, 146],
                    "cambio a pequeno (altura 146)",
                    extra=alturas,
                )
                verifica(
                    contador[0] == base,
                    "cambio a pequeno tampoco crea QPixmap nuevos",
                    extra=f"construcciones={contador[0] - base}",
                )
                configurar_tamano_miniaturas("mediano")

        # --- 5) integración VisorVideos: inmediato, sin rescan, sin perder
        #       selección ni scroll, persistido ---
        with _miniaturas_temporales() as carpeta:
            _crear_previews(carpeta, "a", 3)
            _crear_previews(carpeta, "b", 3)
            temp = tempfile.TemporaryDirectory()
            ruta_db = os.path.join(temp.name, "catalogo.db")
            ruta_config = os.path.join(temp.name, "config.json")
            try:
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
                    [
                        ("a.mp4", "C:\\a.mp4", ".mp4", "2026-08-06T00:00:00", 100.0, 1920, 1080, "h264", 1, 1024),
                        ("b.mp4", "C:\\b.mp4", ".mp4", "2026-08-06T00:00:00", 200.0, 1920, 1080, "h264", 1, 1024),
                    ],
                )
                conn.commit()
                conn.close()

                ventana = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
                ventana.resize(1000, 700)
                ventana.show()

                def esperar(predicado, intentos=300):
                    for _ in range(intentos):
                        QApplication.processEvents()
                        if predicado():
                            return True
                        time.sleep(0.02)
                    QApplication.processEvents()
                    return predicado()

                try:
                    esperar(
                        lambda: ventana._carga_completada
                        and ventana.gestor.hilo is None
                    )
                    verifica(
                        len(ventana.tarjetas) == 2,
                        "integración: 2 tarjetas cargadas",
                    )

                    ventana._al_seleccionar_tarjeta("a.mp4", False)
                    QApplication.processEvents()
                    scrollbar = ventana.area.verticalScrollBar()
                    scrollbar.setValue(50)
                    QApplication.processEvents()
                    valor_scroll = scrollbar.value()

                    idx_grande = ventana.combo_tamano_miniaturas.findText("Grande")
                    ventana.combo_tamano_miniaturas.setCurrentIndex(idx_grande)
                    QApplication.processEvents()

                    alturas = {
                        nombre: [e.height() for e in t._etiquetas_previews]
                        for nombre, t in ventana.tarjetas
                    }
                    verifica(
                        all(h == [225, 225, 225] for h in alturas.values()),
                        "cambio a Grande: todas las tarjetas actualizadas al instante",
                        extra=alturas,
                    )
                    verifica(
                        "a.mp4" in ventana.nombres_seleccionados,
                        "la selección se conserva al cambiar el tamaño",
                    )
                    verifica(
                        scrollbar.value() == valor_scroll,
                        "la posición del scroll se conserva",
                        extra=f"antes={valor_scroll} despues={scrollbar.value()}",
                    )
                    verifica(
                        not ventana.gestor.activo,
                        "sin escaneo ni reconstrucción del catálogo",
                    )
                    with open(ruta_config, encoding="utf-8") as f:
                        config_contenido = json.load(f)
                    verifica(
                        config_contenido.get(CLAVE_TAMANIO_MINIATURAS) == "grande",
                        "el cambio queda persistido en la configuración",
                    )
                    for nombre, t in ventana.tarjetas:
                        verifica(
                            all(e._tiempo is not None for e in t._etiquetas_previews),
                            f"overlay conservado en {nombre} en tamaño Grande",
                        )

                    idx_pequeno = ventana.combo_tamano_miniaturas.findText("Pequeño")
                    ventana.combo_tamano_miniaturas.setCurrentIndex(idx_pequeno)
                    QApplication.processEvents()
                    alturas = {
                        nombre: [e.height() for e in t._etiquetas_previews]
                        for nombre, t in ventana.tarjetas
                    }
                    verifica(
                        all(h == [146, 146, 146] for h in alturas.values()),
                        "cambio a Pequeño: tarjetas actualizadas al instante",
                        extra=alturas,
                    )
                    verifica(
                        "a.mp4" in ventana.nombres_seleccionados,
                        "la selección se conserva en Pequeño",
                    )
                finally:
                    ventana.close()
                    ventana.gestor.cerrar()
                    ventana.gestor_previews.cerrar()
            finally:
                temp.cleanup()
        configurar_tamano_miniaturas("mediano")

    finally:
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
