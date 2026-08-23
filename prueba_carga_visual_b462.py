import os
import py_compile
import shutil
import sys
import tempfile
import time

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

import escanear_videos as escanear_mod
import visor_videos
from escanear_videos import (
    CANTIDAD_PREVIEWS,
    configurar_cantidad_previews,
    conectar_bd,
    guardar_videos,
    listar_videos_paginado,
    ruta_preview,
)
from visor_videos import Tarjeta, VisorVideos

_CANTIDAD_ORIGINAL = escanear_mod.CANTIDAD_PREVIEWS
_CONFIG = tempfile.TemporaryDirectory()
os.environ["VISOR_CONFIG"] = os.path.join(_CONFIG.name, "config.json")


def _esperar(predicado, timeout_ms=15000, paso_ms=20):
    fin = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < fin:
        QApplication.processEvents()
        if predicado():
            return True
        time.sleep(paso_ms / 1000)
    QApplication.processEvents()
    return predicado()


def _limpiar(ventana):
    if ventana is None:
        return
    if ventana.gestor.hilo is not None:
        ventana.gestor.cerrar()
    if ventana.gestor_previews is not None:
        ventana.gestor_previews.cerrar()
    if ventana.gestor_marcadores is not None:
        ventana.gestor_marcadores.cerrar()
    if ventana.gestor_reproduccion is not None:
        ventana.gestor_reproduccion.cerrar()
    ventana.deleteLater()
    for _ in range(5):
        QApplication.processEvents()


def _registro(nombre, ruta, duracion=30.0):
    return {
        "nombre": nombre,
        "ruta": ruta,
        "extension": os.path.splitext(nombre)[1].lower(),
        "fecha_importacion": "f",
        "duracion_segundos": duracion,
        "ancho": 640,
        "alto": 360,
        "codec_video": "h264",
        "cantidad_miniaturas": 1,
        "tamano_bytes": 100,
        "mtime_ns": 1,
    }


def _crear_archivo_video(ruta):
    with open(ruta, "wb") as f:
        f.write(b"x" * 50)


def _crear_jpg(ruta, color=QColor(100, 150, 200)):
    img = QImage(64, 36, QImage.Format_RGB32)
    img.fill(color)
    img.save(ruta, "JPEG")


def _escenario(nombres, con_previews=True):
    carpeta_videos = tempfile.TemporaryDirectory()
    carpeta_mini = tempfile.TemporaryDirectory()
    temp_bd = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp_bd.name, "c.db")
    for nombre in nombres:
        _crear_archivo_video(os.path.join(carpeta_videos.name, nombre))
    conn = conectar_bd(ruta_db)
    conn.close()
    guardar_videos(
        [
            _registro(n, os.path.join(carpeta_videos.name, n))
            for n in nombres
        ],
        ruta_db,
    )
    original_mini = escanear_mod.ruta_carpeta_miniaturas
    escanear_mod.ruta_carpeta_miniaturas = lambda: carpeta_mini.name
    visor_videos.ruta_carpeta_miniaturas = lambda: carpeta_mini.name
    if con_previews:
        for nombre in nombres:
            for indice in range(1, CANTIDAD_PREVIEWS + 1):
                _crear_jpg(ruta_preview(nombre, indice))
    base_jpg = os.path.join(carpeta_mini.name, "base_generada.jpg")
    _crear_jpg(base_jpg, QColor(200, 100, 100))
    return {
        "carpeta_videos": carpeta_videos,
        "carpeta_mini": carpeta_mini,
        "temp_bd": temp_bd,
        "ruta_db": ruta_db,
        "original_mini": original_mini,
        "base_jpg": base_jpg,
    }


def _cerrar_escenario(esc):
    escanear_mod.ruta_carpeta_miniaturas = esc["original_mini"]
    visor_videos.ruta_carpeta_miniaturas = esc["original_mini"]
    esc["carpeta_videos"].cleanup()
    esc["carpeta_mini"].cleanup()
    esc["temp_bd"].cleanup()


def _crear_ventana(esc):
    ventana = VisorVideos(ruta_db=esc["ruta_db"])
    ventana.resize(1000, 700)
    ventana.show()
    ok = _esperar(
        lambda: ventana._carga_completada and ventana.gestor.hilo is None
    )
    ventana._timer_previews.stop()
    return ventana, ok


def _procesar_cola(ventana):
    nombres = [nombre for nombre, _ in ventana.tarjetas]
    ventana._encolar_previews(nombres)
    ventana._al_previews_finalizada()
    return _esperar(
        lambda: not ventana.gestor_previews.activo
        and not ventana._cola_previews
    )


def _completas(ventana):
    return {
        nombre: getattr(tarjeta, "_previews_completas", False)
        for nombre, tarjeta in ventana.tarjetas
    }


class _ControladorGenerar:
    def __init__(self, base_jpg):
        self.n = 0
        self._base = base_jpg
        self._original = escanear_mod.generar_preview

    def _generar(self, ruta_video, destino, indice=None, duracion_segundos=None):
        self.n += 1
        shutil.copyfile(self._base, destino)
        return True

    def activar(self):
        escanear_mod.generar_preview = self._generar

    def desactivar(self):
        escanear_mod.generar_preview = self._original


def test_01_py_compile():
    ok = True
    detalles = []
    for archivo in [
        "visor_videos.py",
        "tareas_videos.py",
        "prueba_carga_visual_b462.py",
    ]:
        try:
            py_compile.compile(archivo, doraise=True)
        except py_compile.PyCompileError as exc:
            ok = False
            detalles.append(f"{archivo}: {exc}")
    return ok, "; ".join(detalles) or "py_compile OK"


def test_02_crear_tarjetas_no_aplica_previews():
    nombres = ["a.mp4", "b.mp4", "c.mp4"]
    esc = _escenario(nombres, con_previews=True)
    ventana = None
    try:
        ventana, ok_carga = _crear_ventana(esc)
        completas = _completas(ventana)
        placeholders = {
            nombre: all(
                etiqueta.pixmap().isNull()
                for etiqueta in tarjeta._etiquetas_previews
            )
            for nombre, tarjeta in ventana.tarjetas
        }
        ok = (
            ok_carga
            and not any(completas.values())
            and all(placeholders.values())
            and len(ventana.tarjetas) == 3
        )
        return ok, f"completas={completas} placeholders={placeholders}"
    finally:
        if ventana is not None:
            ventana.close()
            _limpiar(ventana)
        _cerrar_escenario(esc)


def test_03_previews_cacheadas_progresivo_cero_ffmpeg():
    nombres = ["a.mp4", "b.mp4", "c.mp4", "d.mp4", "e.mp4", "f.mp4"]
    esc = _escenario(nombres, con_previews=True)
    ventana = None
    control = _ControladorGenerar(esc["base_jpg"])
    try:
        ventana, ok_carga = _crear_ventana(esc)
        control.activar()
        ok_cola = _procesar_cola(ventana)
        control.desactivar()
        completas = _completas(ventana)
        ok = (
            ok_carga
            and ok_cola
            and control.n == 0
            and all(completas.values())
        )
        return ok, f"ffmpeg={control.n} cola={ok_cola} completas={completas}"
    finally:
        control.desactivar()
        if ventana is not None:
            ventana.close()
            _limpiar(ventana)
        _cerrar_escenario(esc)


def test_04_preview_faltante_genera():
    nombres = ["a.mp4", "b.mp4", "c.mp4"]
    esc = _escenario(nombres, con_previews=False)
    ventana = None
    control = _ControladorGenerar(esc["base_jpg"])
    try:
        ventana, ok_carga = _crear_ventana(esc)
        control.activar()
        ok_cola = _procesar_cola(ventana)
        control.desactivar()
        completas = _completas(ventana)
        ok = (
            ok_carga
            and ok_cola
            and control.n == len(nombres) * CANTIDAD_PREVIEWS
            and all(completas.values())
        )
        return ok, f"ffmpeg={control.n} esperado={len(nombres)*CANTIDAD_PREVIEWS}"
    finally:
        control.desactivar()
        if ventana is not None:
            ventana.close()
            _limpiar(ventana)
        _cerrar_escenario(esc)


def test_05_lotes_conservados():
    nombres = [f"v{i:02d}.mp4" for i in range(8)]
    esc = _escenario(nombres, con_previews=True)
    ventana = None
    lotes = []
    original_siguiente = VisorVideos._siguiente_lote_previews

    def _spy(self):
        lotes.append(len(self._cola_previews))
        return original_siguiente(self)

    VisorVideos._siguiente_lote_previews = _spy
    try:
        ventana, ok_carga = _crear_ventana(esc)
        ok_cola = _procesar_cola(ventana)
        ok = ok_carga and ok_cola and len(lotes) > 1
        return ok, f"lotes={len(lotes)} cola={ok_cola}"
    finally:
        VisorVideos._siguiente_lote_previews = original_siguiente
        if ventana is not None:
            ventana.close()
            _limpiar(ventana)
        _cerrar_escenario(esc)


def test_06_cambio_carpeta_ignora_resultados_tardios():
    nombres = ["a.mp4"]
    esc_a = _escenario(nombres, con_previews=True)
    esc_b = _escenario(nombres, con_previews=True)
    ventana = None
    try:
        ventana, ok_carga = _crear_ventana(esc_b)
        tarjeta = ventana._tarjeta_por_nombre("a.mp4")
        ruta_video_b = os.path.join(esc_b["carpeta_videos"].name, "a.mp4")
        ruta_preview_b = ruta_preview("a.mp4", 1)
        ruta_preview_a = ruta_preview("a.mp4", 1)
        resultado_tardio = {
            "resultados": [
                {
                    "nombre": "a.mp4",
                    "ruta": os.path.join(
                        esc_a["carpeta_videos"].name, "a.mp4"
                    ),
                    "previews": [ruta_preview_a],
                }
            ]
        }
        ventana._aplicar_previews(resultado_tardio)
        tras_tardio = tarjeta._previews_completas
        resultado_correcto = {
            "resultados": [
                {
                    "nombre": "a.mp4",
                    "ruta": ruta_video_b,
                    "previews": [
                        ruta_preview("a.mp4", i) for i in range(1, CANTIDAD_PREVIEWS + 1)
                    ],
                }
            ]
        }
        ventana._aplicar_previews(resultado_correcto)
        tras_correcto = tarjeta._previews_completas
        ok = ok_carga and (not tras_tardio) and tras_correcto
        return ok, f"tras_tardio={tras_tardio} tras_correcto={tras_correcto}"
    finally:
        if ventana is not None:
            ventana.close()
            _limpiar(ventana)
        _cerrar_escenario(esc_a)
        _cerrar_escenario(esc_b)


def test_07_reemplazo_no_carga_de_golpe():
    nombres = ["a.mp4", "b.mp4", "c.mp4"]
    esc = _escenario(nombres, con_previews=True)
    ventana = None
    original_actualizar = Tarjeta.actualizar_previews
    llamadas = {"n": 0}

    def _spy(self, rutas):
        llamadas["n"] += 1
        return original_actualizar(self, rutas)

    Tarjeta.actualizar_previews = _spy
    try:
        ventana, ok_carga = _crear_ventana(esc)
        durante_creacion = llamadas["n"]
        filas = listar_videos_paginado(100, 0, ruta_db=esc["ruta_db"])["videos"]
        ventana._reemplazar_tarjetas(filas)
        durante_reemplazo = llamadas["n"] - durante_creacion
        placeholders = all(
            getattr(t, "_previews_completas", False) is False
            for _, t in ventana.tarjetas
        )
        ok = ok_carga and durante_creacion == 0 and durante_reemplazo == 0 and placeholders
        return ok, (
            f"durante_creacion={durante_creacion} "
            f"durante_reemplazo={durante_reemplazo} placeholders={placeholders}"
        )
    finally:
        Tarjeta.actualizar_previews = original_actualizar
        if ventana is not None:
            ventana.close()
            _limpiar(ventana)
        _cerrar_escenario(esc)


def test_08_cargar_mas_correspondencia():
    nombres = ["a.mp4", "b.mp4", "c.mp4"]
    esc = _escenario(nombres, con_previews=True)
    ventana = None
    try:
        ventana, ok_carga = _crear_ventana(esc)
        _procesar_cola(ventana)
        extra = "z.mp4"
        _crear_archivo_video(os.path.join(esc["carpeta_videos"].name, extra))
        guardar_videos(
            [
                _registro(
                    extra, os.path.join(esc["carpeta_videos"].name, extra)
                )
            ],
            esc["ruta_db"],
        )
        fila_extra = [
            f
            for f in listar_videos_paginado(100, 0, ruta_db=esc["ruta_db"])[
                "videos"
            ]
            if f[0] == extra
        ]
        for indice in range(1, CANTIDAD_PREVIEWS + 1):
            _crear_jpg(ruta_preview(extra, indice))
        ventana._agregar_tarjetas(fila_extra)
        _procesar_cola(ventana)
        tarjeta_z = ventana._tarjeta_por_nombre(extra)
        ok = (
            ok_carga
            and tarjeta_z is not None
            and getattr(tarjeta_z, "_previews_completas", False)
            and len(ventana.tarjetas) == 4
        )
        return ok, (
            f"z_completa={getattr(tarjeta_z, '_previews_completas', None) if tarjeta_z else None}"
        )
    finally:
        if ventana is not None:
            ventana.close()
            _limpiar(ventana)
        _cerrar_escenario(esc)


def test_09_filtro_no_rompe_aplicacion():
    nombres = ["aa.mp4", "ab.mp4", "bx.mp4"]
    esc = _escenario(nombres, con_previews=True)
    ventana = None
    try:
        ventana, ok_carga = _crear_ventana(esc)
        ventana.filtrar("a")
        visibles = set(ventana.visibles)
        _procesar_cola(ventana)
        completas = _completas(ventana)
        ok = (
            ok_carga
            and visibles == {"aa.mp4", "ab.mp4"}
            and all(completas.values())
        )
        return ok, f"visibles={visibles} completas={completas}"
    finally:
        if ventana is not None:
            ventana.close()
            _limpiar(ventana)
        _cerrar_escenario(esc)


def main():
    app = QApplication(sys.argv)
    configurar_cantidad_previews(3)
    try:
        pruebas = [
            test_01_py_compile,
            test_02_crear_tarjetas_no_aplica_previews,
            test_03_previews_cacheadas_progresivo_cero_ffmpeg,
            test_04_preview_faltante_genera,
            test_05_lotes_conservados,
            test_06_cambio_carpeta_ignora_resultados_tardios,
            test_07_reemplazo_no_carga_de_golpe,
            test_08_cargar_mas_correspondencia,
            test_09_filtro_no_rompe_aplicacion,
        ]
        resultados = []
        for indice, fn in enumerate(pruebas, start=1):
            try:
                ok, detalle = fn()
            except Exception as exc:
                ok, detalle = False, f"excepcion: {type(exc).__name__}: {exc}"
            resultados.append((indice, ok, detalle))
            print(f"P{indice:02d} {'OK' if ok else 'FALLO'} - {detalle}")
        ok_total = all(ok for _, ok, _ in resultados)
        aprobadas = sum(1 for _, ok, _ in resultados if ok)
        print(f"TOTAL={aprobadas}/{len(pruebas)}")
        print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")
        return 0 if ok_total else 1
    finally:
        configurar_cantidad_previews(_CANTIDAD_ORIGINAL)


if __name__ == "__main__":
    sys.exit(main())
