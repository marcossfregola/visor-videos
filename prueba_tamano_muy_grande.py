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


def _crear_png(ruta):
    imagen = QImage(160, 100, QImage.Format_RGB32)
    imagen.fill(QColor("red"))
    return imagen.save(ruta, "PNG")


def _crear_previews(carpeta, prefijo, cantidad, con_miniatura=False):
    for indice in range(1, cantidad + 1):
        _crear_png(os.path.join(carpeta, f"{prefijo}_preview_{indice:02d}.jpg"))
    if con_miniatura:
        _crear_png(os.path.join(carpeta, f"{prefijo}_01.jpg"))


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

    class _C(original):
        def __init__(self, *args, **kwargs):
            contador[0] += 1
            super().__init__(*args, **kwargs)

    visor_videos.QPixmap = _C
    try:
        yield contador
    finally:
        visor_videos.QPixmap = original


def _fila(nombre, duracion):
    return (nombre, duracion, 1920, 1080, "h264", 1, 1024)


def _fila_bd(nombre, duracion):
    n, d, ancho, alto, codec, miniaturas, tamano = _fila(nombre, duracion)
    return (
        n, f"C:\\{n}", os.path.splitext(n)[1].lower(), "2026-08-06T00:00:00",
        d, ancho, alto, codec, miniaturas, tamano,
    )


def main():
    app = QApplication(sys.argv)

    _CONTADOR[0] = 1
    configurar_tamano_miniaturas("mediano")

    try:
        # --- 1) presets: los tres existentes intactos + Muy grande ---
        esperados = {
            "pequeno": (260, 146),
            "mediano": (320, 180),
            "grande": (400, 225),
            "muy_grande": (512, 288),
        }
        for clave, dim in esperados.items():
            configurar_tamano_miniaturas(clave)
            verifica(
                dimensiones_miniatura() == dim,
                f"preset {clave}: {dim}",
            )
        configurar_tamano_miniaturas("mediano")
        verifica(
            dimensiones_miniatura() == (320, 180),
            "default: mediano (320x180)",
        )

        # --- 2) mapeo texto <-> clave ---
        verifica(
            texto_tamano_miniaturas("muy_grande") == "Muy grande"
            and clave_tamano_miniaturas("Muy grande") == "muy_grande",
            "mapeo texto<->clave para Muy grande",
        )
        verifica(
            texto_tamano_miniaturas("otro") == "Mediano"
            and clave_tamano_miniaturas("Otro") == "mediano",
            "valores desconocidos vuelven a Mediano",
        )

        # --- 3) persistencia y compatibilidad ---
        temp_config = tempfile.TemporaryDirectory()
        ruta_config = os.path.join(temp_config.name, "config.json")
        try:
            guardar_tamano_miniaturas("muy_grande", ruta_config)
            with open(ruta_config, encoding="utf-8") as f:
                contenido = json.load(f)
            verifica(
                contenido.get(CLAVE_TAMANIO_MINIATURAS) == "muy_grande"
                and obtener_tamano_miniaturas(ruta_config) == "muy_grande",
                "persistencia round-trip de 'muy_grande'",
            )
            for clave in ("pequeno", "mediano", "grande"):
                guardar_tamano_miniaturas(clave, ruta_config)
                verifica(
                    obtener_tamano_miniaturas(ruta_config) == clave,
                    f"configuración anterior sigue válida: {clave}",
                )
            ruta_no = os.path.join(temp_config.name, "inexistente.json")
            verifica(
                obtener_tamano_miniaturas(ruta_no) == "mediano",
                "obtener sin archivo devuelve mediano",
            )
            con_invalido = os.path.join(temp_config.name, "invalido.json")
            with open(con_invalido, "w", encoding="utf-8") as f:
                json.dump({CLAVE_TAMANIO_MINIATURAS: "enorme"}, f)
            verifica(
                obtener_tamano_miniaturas(con_invalido) == "mediano",
                "valor almacenado inválido vuelve a mediano",
            )
        finally:
            temp_config.cleanup()

        # --- 4) cambio a Muy grande en memoria, sin releer disco ---
        configurar_tamano_miniaturas("mediano")
        with _miniaturas_temporales() as carpeta:
            _crear_previews(carpeta, "clip", 3, con_miniatura=True)
            with _contar_qpixmap() as contador:
                tarjeta = Tarjeta(_fila("clip.mp4", 100.0))
                tarjeta.actualizar_previews(
                    [os.path.join(carpeta, f"clip_preview_{i:02d}.jpg") for i in (1, 2, 3)]
                )
                base = contador[0]
                alturas = [e.height() for e in tarjeta._etiquetas_previews]
                verifica(
                    alturas == [180, 180, 180],
                    "tarjeta inicial en mediano",
                )
                configurar_tamano_miniaturas("muy_grande")
                tarjeta.aplicar_tamano()
                alturas = [e.height() for e in tarjeta._etiquetas_previews]
                verifica(
                    alturas == [288, 288, 288],
                    "cambio a Muy grande sin reconstruir (altura 288)",
                    extra=alturas,
                )
                verifica(
                    contador[0] == base,
                    "el cambio a Muy grande no crea QPixmap nuevos (sin releer disco)",
                    extra=f"construcciones={contador[0] - base}",
                )
                verifica(
                    all(e._tiempo is not None for e in tarjeta._etiquetas_previews),
                    "overlay de tiempo conservado en Muy grande",
                )
                verifica(
                    tarjeta._imagen_miniatura is not None
                    and tarjeta._imagen_miniatura.height() == 288,
                    "miniatura principal reescalada a Muy grande",
                )
                configurar_tamano_miniaturas("mediano")

        # --- 5) vista ampliada sobre Muy grande ---
        configurar_tamano_miniaturas("muy_grande")
        with _miniaturas_temporales() as carpeta:
            _crear_previews(carpeta, "clip", 3, con_miniatura=True)
            ventana = VisorVideos(ruta_config=os.path.join(carpeta, "cfg.json"))
            ventana.show()
            QApplication.processEvents()
            try:
                configurar_tamano_miniaturas("muy_grande")
                tarjeta = Tarjeta(_fila("clip.mp4", 100.0))
                tarjeta.actualizar_previews(
                    [os.path.join(carpeta, f"clip_preview_{i:02d}.jpg") for i in (1, 2, 3)]
                )
                etiqueta = tarjeta._etiquetas_previews[0]
                ventana._vista.preparar(etiqueta._pixmap_original)
                verifica(
                    ventana._vista._tam_amp == (int(512 * 1.6), int(288 * 1.6)),
                    "vista ampliada sobre Muy grande: 1.6x (819x461)",
                    extra=ventana._vista._tam_amp,
                )
            finally:
                ventana.close()
                ventana.gestor.cerrar()
                ventana.gestor_previews.cerrar()
        configurar_tamano_miniaturas("mediano")

        # --- 6) integración con VisorVideos: cambio inmediato, selección,
        #       scroll, persistencia y restauración ---
        with _miniaturas_temporales() as carpeta:
            _crear_previews(carpeta, "a", 3, con_miniatura=True)
            _crear_previews(carpeta, "b", 3)
            temp = tempfile.TemporaryDirectory()
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
            filas_bd = [_fila_bd("a.mp4", 100.0), _fila_bd("b.mp4", 200.0)]
            for i in range(30):
                filas_bd.append(_fila_bd(f"extra_{i:02d}.mp4", 100.0))
            conn.executemany(
                "INSERT INTO videos (nombre, ruta, extension, fecha_importacion, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas, tamano_bytes) VALUES (?,?,?,?,?,?,?,?,?,?)",
                filas_bd,
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
                esperar(lambda: ventana._carga_completada and ventana.gestor.hilo is None)
                verifica(
                    len(ventana.tarjetas) == 32,
                    "integración: 32 tarjetas cargadas",
                )
                ventana._al_seleccionar_tarjeta("a.mp4", False)
                scrollbar = ventana.area.verticalScrollBar()
                scrollbar.setValue(120)
                QApplication.processEvents()
                idx = ventana.combo_tamano_miniaturas.findText("Muy grande")
                ventana.combo_tamano_miniaturas.setCurrentIndex(idx)
                QApplication.processEvents()
                alturas = {
                    nombre: [e.height() for e in t._etiquetas_previews]
                    for nombre, t in ventana.tarjetas
                }
                verifica(
                    all(h == [288, 288, 288] for h in alturas.values()),
                    "cambio a Muy grande: todas las tarjetas actualizadas al instante",
                    extra=sorted(set(tuple(h) for h in alturas.values())),
                )
                verifica(
                    "a.mp4" in ventana.nombres_seleccionados,
                    "selección conservada",
                )
                verifica(
                    scrollbar.value() == 120,
                    "scroll conservado",
                    extra=f"valor={scrollbar.value()}",
                )
                verifica(
                    not ventana.gestor.activo,
                    "sin escaneo ni reconstrucción",
                )
                with open(ruta_config, encoding="utf-8") as f:
                    config_contenido = json.load(f)
                verifica(
                    config_contenido.get(CLAVE_TAMANIO_MINIATURAS) == "muy_grande",
                    "preferencia Muy grande persistida",
                )
                overlays = all(
                    all(e._tiempo is not None for e in dict(ventana.tarjetas)[nombre]._etiquetas_previews)
                    for nombre in ("a.mp4", "b.mp4")
                )
                verifica(overlays, "overlays conservados en Muy grande")
            finally:
                ventana.close()
                ventana.gestor.cerrar()
                ventana.gestor_previews.cerrar()

            v2 = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
            v2.show()
            try:
                esperar(lambda: v2._carga_completada and v2.gestor.hilo is None)
                alturas = {
                    nombre: [e.height() for e in t._etiquetas_previews]
                    for nombre, t in v2.tarjetas
                }
                verifica(
                    all(h == [288, 288, 288] for h in alturas.values()),
                    "restauración tras reiniciar: tarjetas en Muy grande",
                    extra=sorted(set(tuple(h) for h in alturas.values())),
                )
            finally:
                v2.close()
                v2.gestor.cerrar()
                v2.gestor_previews.cerrar()
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
