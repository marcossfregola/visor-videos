import contextlib
import os
import sqlite3
import sys
import tempfile
import time

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

import escanear_videos as escanear_mod
import visor_videos
from escanear_videos import calcular_tiempo_preview, configurar_cantidad_previews
from visor_videos import Tarjeta, VisorVideos, formatear_tiempo

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
    imagen = QImage(60, 40, QImage.Format_RGB32)
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


def main():
    app = QApplication(sys.argv)

    _CONTADOR[0] = 1
    original_cantidad = escanear_mod.CANTIDAD_PREVIEWS

    try:
        # --- 1) formatear_tiempo: casos de borde ---
        verifica(formatear_tiempo(None) is None, "formatear_tiempo(None) es None")
        verifica(formatear_tiempo(True) is None, "formatear_tiempo(bool) es None")
        verifica(formatear_tiempo(-3) is None, "formatear_tiempo(negativo) es None")
        verifica(formatear_tiempo("5") is None, "formatear_tiempo(texto) es None")
        verifica(formatear_tiempo(0) == "0:00", "formatear_tiempo(0) = 0:00")
        verifica(
            formatear_tiempo(41.070833) == "0:41",
            "formatear_tiempo(41.07) = 0:41",
        )
        verifica(
            formatear_tiempo(65.4) == "1:05",
            "formatear_tiempo(65.4) = 1:05",
        )
        verifica(
            formatear_tiempo(3600) == "1:00:00",
            "formatear_tiempo(3600) = 1:00:00",
        )
        verifica(
            formatear_tiempo(3723) == "1:02:03",
            "formatear_tiempo(3723) = 1:02:03",
        )

        # --- 2) derivación desde duración (sin ffprobe): N=3/5/7/9 ---
        configurar_cantidad_previews(3)
        verifica(
            [calcular_tiempo_preview(100, i) for i in (1, 2, 3)]
            == [25.0, 50.0, 75.0],
            "N=3: previews al 25/50/75 %",
        )
        configurar_cantidad_previews(5)
        verifica(
            all(
                abs(calcular_tiempo_preview(100, i) - 100 * i / 6) < 1e-9
                for i in range(1, 6)
            ),
            "N=5: tiempos proporcionales i/6",
        )
        configurar_cantidad_previews(7)
        verifica(
            all(
                abs(calcular_tiempo_preview(100, i) - 100 * i / 8) < 1e-9
                for i in range(1, 8)
            ),
            "N=7: tiempos proporcionales i/8",
        )
        configurar_cantidad_previews(9)
        verifica(
            all(
                abs(calcular_tiempo_preview(100, i) - 100 * i / 10) < 1e-9
                for i in range(1, 10)
            ),
            "N=9: tiempos proporcionales i/10",
        )
        configurar_cantidad_previews(original_cantidad)

        # --- 3) Tarjeta con duración válida: overlay por preview ---
        configurar_cantidad_previews(3)
        with _miniaturas_temporales() as carpeta:
            rutas = _crear_previews(carpeta, "clip", 3)
            tarjeta = Tarjeta(("clip.mp4", 100.0, 1920, 1080, "h264", 1, 1024))
            tarjeta.actualizar_previews(rutas)
            etiquetas = tarjeta._etiquetas_previews
            esperados = [
                formatear_tiempo(calcular_tiempo_preview(100.0, i))
                for i in (1, 2, 3)
            ]
            verifica(
                [e._tiempo for e in etiquetas] == esperados,
                "duración válida: overlay con el instante de cada preview",
                extra=[e._tiempo for e in etiquetas],
            )
            verifica(
                esperados == ["0:25", "0:50", "1:15"],
                "duración 100 s: textos 0:25/0:50/1:15",
            )
            verifica(
                sum(
                    1
                    for e in etiquetas
                    if e.pixmap() is not None and not e.pixmap().isNull()
                )
                == 3,
                "los 3 previews tienen pixmap",
            )
            for e in etiquetas:
                verifica(
                    not e.grab().isNull(),
                    "paintEvent dibuja el overlay sin errores",
                )

        # --- 4) duración None/inválida: sin overlay ---
        configurar_cantidad_previews(3)
        with _miniaturas_temporales() as carpeta:
            rutas = _crear_previews(carpeta, "clip", 3)
            for duracion in (None, 0, -5, "abc", True):
                tarjeta = Tarjeta(
                    ("clip.mp4", duracion, 1920, 1080, "h264", 1, 1024)
                )
                tarjeta.actualizar_previews(rutas)
                tiempos = [e._tiempo for e in tarjeta._etiquetas_previews]
                verifica(
                    tiempos == [None, None, None],
                    f"duración {duracion!r}: sin overlay en ningún preview",
                    extra=tiempos,
                )

        # --- 5) ruta inválida: sin overlay y placeholder intacto ---
        with _miniaturas_temporales():
            tarjeta = Tarjeta(("clip.mp4", 100.0, 1920, 1080, "h264", 1, 1024))
            resultado = tarjeta.actualizar_previews(
                [os.path.join("C:\\", "no_existe.jpg")]
            )
            verifica(
                resultado is False,
                "ruta inexistente: actualizar_previews devuelve False",
            )
            verifica(
                tarjeta._etiquetas_previews[0].text() == "Generando preview…",
                "ruta inexistente: placeholder conservado",
            )
            verifica(
                tarjeta._etiquetas_previews[0]._tiempo is None,
                "ruta inexistente: sin tiempo",
            )

        # --- 6) regresión ajustar_previews 3/5/7/9 ---
        configurar_cantidad_previews(9)
        with _miniaturas_temporales() as carpeta:
            rutas = _crear_previews(carpeta, "clip", 9)
            tarjeta = Tarjeta(("clip.mp4", 100.0, 1920, 1080, "h264", 1, 1024))
            tarjeta.actualizar_previews(rutas)
            contenedor = QWidget()
            contenedor.setLayout(QVBoxLayout())
            contenedor.layout().addWidget(tarjeta)
            contenedor.show()
            QApplication.processEvents()
            try:
                for cantidad, esperado in ((3, 3), (5, 5), (7, 7), (9, 9)):
                    tarjeta.ajustar_previews(cantidad)
                    QApplication.processEvents()
                    visibles = sum(
                        1 for e in tarjeta._etiquetas_previews if e.isVisible()
                    )
                    verifica(
                        visibles == esperado,
                        f"ajustar_previews({cantidad}) deja {esperado} visibles",
                    )
                verifica(
                    tarjeta._etiquetas_previews[0]._tiempo
                    == formatear_tiempo(calcular_tiempo_preview(100.0, 1)),
                    "tras ajustar, el preview 1 conserva su overlay",
                )
            finally:
                contenedor.close()
        configurar_cantidad_previews(original_cantidad)

        # --- 7) integración con VisorVideos (duración desde catálogo) ---
        configurar_cantidad_previews(3)
        with _miniaturas_temporales() as carpeta:
            _crear_previews(carpeta, "con", 3)
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
                        ("con.mp4", "C:\\con.mp4", ".mp4", "2026-08-06T00:00:00", 100.0, 1920, 1080, "h264", 1, 1024),
                        ("sin.mp4", "C:\\sin.mp4", ".mp4", "2026-08-06T00:00:00", None, 1920, 1080, "h264", 0, 1024),
                    ],
                )
                conn.commit()
                conn.close()

                ventana = VisorVideos(
                    ruta_db=ruta_db, ruta_config=ruta_config
                )
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

                try:
                    esperar(
                        lambda: ventana._carga_completada
                        and ventana.gestor.hilo is None
                    )
                    verifica(
                        len(ventana.tarjetas) == 2,
                        "integración: 2 tarjetas cargadas",
                    )
                    con_tarjeta = dict(ventana.tarjetas)["con.mp4"]
                    sin_tarjeta = dict(ventana.tarjetas)["sin.mp4"]
                    tiempos_con = [
                        e._tiempo for e in con_tarjeta._etiquetas_previews
                    ]
                    tiempos_sin = [
                        e._tiempo for e in sin_tarjeta._etiquetas_previews
                    ]
                    verifica(
                        tiempos_con == ["0:25", "0:50", "1:15"],
                        "integración: overlay presente desde duración del catálogo",
                        extra=tiempos_con,
                    )
                    verifica(
                        tiempos_sin == [None, None, None],
                        "integración: duración NULL no muestra overlay",
                        extra=tiempos_sin,
                    )
                finally:
                    ventana.close()
                    ventana.gestor.cerrar()
                    ventana.gestor_previews.cerrar()
            finally:
                temp.cleanup()
        configurar_cantidad_previews(original_cantidad)

    finally:
        configurar_cantidad_previews(original_cantidad)

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
