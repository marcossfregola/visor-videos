import contextlib
import json
import os
import sqlite3
import sys
import tempfile
import time

from PySide6.QtCore import QEvent
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

import escanear_videos as escanear_mod
import visor_videos
from escanear_videos import configurar_cantidad_previews
from visor_videos import Tarjeta, VisorVideos, configurar_tamano_miniaturas

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
def _espia_generar_preview():
    llamadas = []
    original = escanear_mod.generar_preview

    def _generar(ruta_video, destino, indice=None, duracion_segundos=None):
        llamadas.append(indice)
        imagen = QImage(160, 100, QImage.Format_RGB32)
        imagen.fill(QColor("green"))
        imagen.save(destino, "PNG")
        return True

    escanear_mod.generar_preview = _generar
    try:
        yield llamadas
    finally:
        escanear_mod.generar_preview = original


def _fila_bd(nombre, duracion, carpeta_videos):
    return (
        nombre, os.path.join(carpeta_videos, nombre), os.path.splitext(nombre)[1].lower(),
        "2026-08-06T00:00:00", duracion, 1920, 1080, "h264", 1, 1024,
    )


@contextlib.contextmanager
def _entorno():
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
    conn.executemany(
        "INSERT INTO videos (nombre, ruta, extension, fecha_importacion, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas, tamano_bytes) VALUES (?,?,?,?,?,?,?,?,?,?)",
        [_fila_bd("clip.mp4", 100.0, videos.name)]
        + [_fila_bd(f"extra_{i:02d}.mp4", 100.0, videos.name) for i in range(20)],
    )
    conn.commit()
    conn.close()

    original_escaneo = escanear_mod.ruta_carpeta_miniaturas
    original_visor = visor_videos.ruta_carpeta_miniaturas
    escanear_mod.ruta_carpeta_miniaturas = lambda: mini.name
    visor_videos.ruta_carpeta_miniaturas = lambda: mini.name
    _crear_previews(mini.name, "clip", 3)
    for i in range(20):
        _crear_previews(mini.name, f"extra_{i:02d}", 9)
    with open(os.path.join(videos.name, "clip.mp4"), "wb") as f:
        f.write(b"video")
    for i in range(20):
        with open(os.path.join(videos.name, f"extra_{i:02d}.mp4"), "wb") as f:
            f.write(b"video")
    try:
        yield {
            "ruta_db": ruta_db,
            "ruta_config": ruta_config,
            "carpeta_videos": videos.name,
        }
    finally:
        escanear_mod.ruta_carpeta_miniaturas = original_escaneo
        visor_videos.ruta_carpeta_miniaturas = original_visor
        temp.cleanup()
        mini.cleanup()
        videos.cleanup()


def _esperar_previews(ventana, timeout_ms=8000):
    fin = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < fin:
        QApplication.processEvents()
        if (
            not ventana.gestor_previews.activo
            and ventana.gestor_previews.hilo is None
            and not ventana._cola_previews
        ):
            return True
        time.sleep(0.02)
    QApplication.processEvents()
    return (
        not ventana.gestor_previews.activo
        and not ventana._cola_previews
    )


def main():
    app = QApplication(sys.argv)

    _CONTADOR[0] = 1
    configurar_cantidad_previews(3)
    configurar_tamano_miniaturas("mediano")

    try:
        # --- A) crecimiento dinámico de slots (tarjeta directa) ---
        with _miniaturas_temporales() as carpeta:
            _crear_previews(carpeta, "clip", 3)
            tarjeta = Tarjeta(("clip.mp4", 100.0, 1920, 1080, "h264", 1, 1024))
            tarjeta.actualizar_previews(
                [os.path.join(carpeta, f"clip_preview_{i:02d}.jpg") for i in (1, 2, 3)]
            )
            contenedor = QWidget()
            contenedor.setLayout(QVBoxLayout())
            contenedor.layout().addWidget(tarjeta)
            contenedor.show()
            QApplication.processEvents()
            try:
                verifica(
                    len(tarjeta._etiquetas_previews) == 3,
                    "tarjeta inicial con 3 slots",
                )
                configurar_cantidad_previews(5)
                tarjeta.ajustar_previews(5)
                QApplication.processEvents()
                verifica(
                    len(tarjeta._etiquetas_previews) == 5,
                    "ajustar a 5 crea 2 slots nuevos",
                )
                visibles = sum(1 for e in tarjeta._etiquetas_previews if e.isVisible())
                verifica(
                    visibles == 5,
                    "5 slots visibles tras crecer",
                )
                verifica(
                    tarjeta._etiquetas_previews[4].text() == "Generando preview…"
                    and tarjeta._etiquetas_previews[4]._pixmap_original is None,
                    "el slot nuevo es un placeholder",
                )
                configurar_cantidad_previews(9)
                tarjeta.ajustar_previews(9)
                QApplication.processEvents()
                verifica(
                    len(tarjeta._etiquetas_previews) == 9,
                    "ajustar a 9 crea hasta 9 slots",
                )
                configurar_cantidad_previews(3)
                tarjeta.ajustar_previews(3)
                QApplication.processEvents()
                verifica(
                    len(tarjeta._etiquetas_previews) == 9
                    and sum(1 for e in tarjeta._etiquetas_previews if e.isVisible()) == 3,
                    "disminuir solo oculta (no destruye slots ni genera trabajo)",
                )

                # eventFilter y vista ampliada sobre slot nuevo
                rutas = _crear_previews(carpeta, "clip", 5)
                tarjeta.actualizar_previews(rutas)
                recibidos = []
                tarjeta.vista_solicitada.connect(lambda p: recibidos.append(p))
                QApplication.sendEvent(
                    tarjeta._etiquetas_previews[4], QEvent(QEvent.Enter)
                )
                verifica(
                    len(recibidos) == 1
                    and recibidos[0] is tarjeta._etiquetas_previews[4]._pixmap_original,
                    "el slot nuevo conserva eventFilter y emite el pixmap original",
                )

                # tamaño configurado aplica a los slots nuevos
                configurar_tamano_miniaturas("grande")
                tarjeta.aplicar_tamano()
                alturas = [e.height() for e in tarjeta._etiquetas_previews]
                verifica(
                    all(h == 225 for h in alturas),
                    "aplicar_tamano reescala también los slots nuevos",
                    extra=set(alturas),
                )
            finally:
                contenedor.close()
            configurar_tamano_miniaturas("mediano")
            configurar_cantidad_previews(3)

        # --- B) integración: generación automática de solo las faltantes ---
        with _entorno() as entorno:
            with _espia_generar_preview() as llamadas:
                ventana = VisorVideos(
                    ruta_db=entorno["ruta_db"], ruta_config=entorno["ruta_config"]
                )
                ventana.resize(900, 600)
                ventana.show()

                def esperar_carga(predicado, intentos=400):
                    for _ in range(intentos):
                        QApplication.processEvents()
                        if predicado():
                            return True
                        time.sleep(0.02)
                    QApplication.processEvents()
                    return predicado()

                try:
                    esperar_carga(
                        lambda: ventana._carga_completada
                        and ventana.gestor.hilo is None
                    )
                    ventana.carpeta_seleccionada = entorno["carpeta_videos"]
                    ventana._al_seleccionar_tarjeta("clip.mp4", False)
                    scrollbar = ventana.area.verticalScrollBar()
                    scrollbar.setValue(20)
                    QApplication.processEvents()
                    tarjeta_clip = dict(ventana.tarjetas)["clip.mp4"]
                    verifica(
                        len(tarjeta_clip._etiquetas_previews) == 3,
                        "integración: tarjeta inicial con 3 slots",
                    )

                    # aumentar 3 -> 5
                    idx = ventana.combo_cantidad_previews.findText("5")
                    ventana.combo_cantidad_previews.setCurrentIndex(idx)
                    QApplication.processEvents()
                    ventana._timer_previews.timeout.emit()
                    genero = _esperar_previews(ventana)
                    verifica(
                        genero,
                        "la generación en segundo plano finaliza",
                    )
                    verifica(
                        sorted(llamadas) == [4, 5],
                        "solo se generan los índices faltantes (4 y 5)",
                        extra=sorted(llamadas),
                    )
                    verifica(
                        len(tarjeta_clip._etiquetas_previews) == 5,
                        "la tarjeta creció a 5 slots",
                    )
                    pixmaps = sum(
                        1
                        for e in tarjeta_clip._etiquetas_previews
                        if e.pixmap() is not None and not e.pixmap().isNull()
                    )
                    verifica(
                        pixmaps == 5,
                        "las 5 previews quedaron visibles tras generarse",
                        extra=pixmaps,
                    )
                    verifica(
                        all(e._tiempo is not None for e in tarjeta_clip._etiquetas_previews),
                        "overlays presentes en los slots nuevos",
                    )
                    verifica(
                        "clip.mp4" in ventana.nombres_seleccionados,
                        "selección conservada",
                    )
                    verifica(
                        scrollbar.value() == 20,
                        "scroll conservado",
                        extra=f"valor={scrollbar.value()}",
                    )
                    verifica(
                        not ventana.gestor.activo and ventana.tarea_escaneo is None,
                        "sin escaneo ni pipeline de catálogo",
                    )
                    verifica(
                        ventana.gestor_previews.activo is False,
                        "gestor de previews inactivo tras terminar",
                    )
                    with open(entorno["ruta_config"], encoding="utf-8") as f:
                        config_contenido = json.load(f)
                    verifica(
                        config_contenido.get("cantidad_previews") == 5,
                        "cantidad 5 persistida",
                    )

                    # aumentar 5 -> 7: solo índices 6 y 7
                    llamadas.clear()
                    idx = ventana.combo_cantidad_previews.findText("7")
                    ventana.combo_cantidad_previews.setCurrentIndex(idx)
                    QApplication.processEvents()
                    ventana._timer_previews.timeout.emit()
                    _esperar_previews(ventana)
                    verifica(
                        sorted(llamadas) == [6, 7],
                        "5 -> 7: solo se generan 6 y 7",
                        extra=sorted(llamadas),
                    )

                    # "completo.mp4" ya tenía 5 -> a 7 le faltan 6,7 también se generan
                    verifica(
                        len(llamadas) == 2,
                        "no se regeneran índices existentes",
                    )

                    # disminuir 7 -> 3: sin trabajo en segundo plano
                    llamadas.clear()
                    idx = ventana.combo_cantidad_previews.findText("3")
                    ventana.combo_cantidad_previews.setCurrentIndex(idx)
                    QApplication.processEvents()
                    ventana._timer_previews.timeout.emit()
                    QApplication.processEvents()
                    verifica(
                        llamadas == [] and ventana._cola_previews == [],
                        "disminuir no genera ningún trabajo en segundo plano",
                    )
                finally:
                    ventana.close()
                    ventana.gestor.cerrar()
                    ventana.gestor_previews.cerrar()

        configurar_cantidad_previews(3)

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
