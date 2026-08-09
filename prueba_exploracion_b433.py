"""Pruebas de B4.3.3: ajustes de interacción y densidad manual.

Cubre:
- Mejora A (z-order): durante el hover la preview dinámica queda por encima
  de las miniaturas fijas de marcadores (uno y varios); al salir de la
  superficie las fijas vuelven a verse normalmente; la eliminación por clic
  derecho sigue funcionando.
- Mejora B (densidad manual): selector Auto | 15 | 30 | 60 | 120 | 200;
  objetivo manual en videos cortos (30 s y 2 min); incrementar reutilizando
  lo existente (15→60, 60→120); disminuir sin borrar caché ni regenerar;
  volver a Auto recalculando y conservando extras; un solo FFmpeg activo;
  mouseMove solo RAM; marcadores conservan tiempo/id.
"""

import gc
import os
import py_compile
import sys
import tempfile
import threading
import time

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import QApplication

import exploracion_cache as cache
import tareas_videos
import visor_videos
import prueba_exploracion_b432 as b432
from exploracion_temporal import tiempos_objetivo
from scrubber import MiniaturaMarcador
from tareas import TareaBase
from visor_videos import Tarjeta, VisorVideos


class _Resultado:
    def __init__(self, returncode):
        self.returncode = returncode


class _TareaExploracionDensaFake(TareaBase):
    creadas = []
    resultado = {"version": "v1", "fotogramas": [0, 5000, 10000]}
    liberar = None

    resultado_parcial = Signal(object)

    def __init__(self, video_id, ruta_video, duracion=None, cantidad=None,
                 parent=None, objetivo_manual=None):
        super().__init__(parent)
        self.video_id = video_id
        self.ruta_video = ruta_video
        self.duracion = duracion
        self.cantidad = cantidad
        self.objetivo_manual = objetivo_manual
        self._cancelada = False
        _TareaExploracionDensaFake.creadas.append(self)

    def cancelar(self):
        self._cancelada = True

    def _trabajo(self):
        if _TareaExploracionDensaFake.liberar is not None:
            _TareaExploracionDensaFake.liberar.wait(3.0)
        if self._cancelada:
            return {"cancelado": True, "version": None, "fotogramas": []}
        return _TareaExploracionDensaFake.resultado


def _video_temporal(contenido=b"datos del video"):
    temp = tempfile.TemporaryDirectory()
    ruta = os.path.join(temp.name, "video.mp4")
    with open(ruta, "wb") as f:
        f.write(contenido)
    return temp, ruta


def _mock_ffmpeg(cuenta, contenido=b"\xff\xd8\xff\xe0datos"):
    def _run(comando, *args, **kwargs):
        cuenta["n"] += 1
        with open(comando[-1], "wb") as f:
            f.write(contenido)
        return _Resultado(0)

    return _run


def _generar_fake(cantidades, presentes):
    """Fake de generar_fotogramas que registra cantidades y puebla presentes."""

    def _generar(video_id, ruta_video, duracion=None, cantidad=None,
                 on_progreso=None, cancelar=None):
        cantidades.append(cantidad)
        if cantidad is None:
            cantidad = cache.objetivo_total_densidad(duracion)
        objetivos = tiempos_objetivo(duracion, cantidad)
        for indice, ms in enumerate(objetivos, start=1):
            if ms not in presentes:
                presentes.append(ms)
            if on_progreso is not None:
                on_progreso(indice, len(objetivos))
        return {
            "version": "v9",
            "fotogramas": list(objetivos),
            "cancelado": False,
        }

    return _generar


def _tarea_con_fake(duracion, manual):
    cantidades = []
    presentes = []
    original_generar = tareas_videos.generar_fotogramas
    original_listar = tareas_videos.listar_fotogramas_version
    original_ruta = tareas_videos.ruta_fotograma_version
    original_version = tareas_videos.version_actual
    ruta_png = b432._crear_png(
        os.path.join(b432._CONFIG_TEMPORAL.name, "fotograma_b433.png")
    )
    tareas_videos.ruta_fotograma_version = (
        lambda video_id, ms, version: ruta_png
    )
    tareas_videos.version_actual = lambda *args, **kwargs: "v9"
    tareas_videos.generar_fotogramas = _generar_fake(cantidades, presentes)
    tareas_videos.listar_fotogramas_version = (
        lambda video_id, version, duracion=None: list(presentes)
    )
    parciales = []
    try:
        tarea = tareas_videos.TareaExploracionDensa(
            1, "C:\\videos\\clip.mp4", duracion=duracion, cantidad=15,
            objetivo_manual=manual,
        )
        tarea.resultado_parcial.connect(lambda d: parciales.append(d))
        resultado = tarea._trabajo()
    finally:
        tareas_videos.generar_fotogramas = original_generar
        tareas_videos.listar_fotogramas_version = original_listar
        tareas_videos.ruta_fotograma_version = original_ruta
        tareas_videos.version_actual = original_version
    emitidos = [ms for p in parciales for ms, _ in p["fotogramas"]]
    return cantidades, emitidos, presentes, resultado


def test_01():
    modulos = [
        "tareas_videos.py",
        "visor_videos.py",
        "exploracion_cache.py",
        "prueba_exploracion_b433.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    casos = [(30.0, 15), (120.0, 15), (600.0, 20), (3360.0, 112), (7200.0, 200)]
    for d, esperado in casos:
        if cache.objetivo_total_densidad(d) != esperado:
            return False, f"{d}s -> {cache.objetivo_total_densidad(d)} (esperado {esperado})"
    return True, "formula Auto conservada (30s=15 2min=15 10min=20 56min=112 2h=200)"


def test_03():
    cantidades, emitidos, presentes, resultado = _tarea_con_fake(30.0, 60)
    objetivos = tiempos_objetivo(30.0, 60)
    ok_cantidades = cantidades == [15, 60]
    ok_total = len(objetivos) == 60
    ok_emitidos = (
        len(emitidos) == 60
        and len(set(emitidos)) == 60
        and emitidos[:15] == list(tiempos_objetivo(30.0, 15))
    )
    ok_resultado = resultado.get("fotogramas") == list(objetivos)
    return (
        ok_cantidades and ok_total and ok_emitidos and ok_resultado,
        f"cantidades={cantidades} emitidos={len(emitidos)}",
    )


def test_04():
    cantidades, emitidos, _presentes, resultado = _tarea_con_fake(120.0, 60)
    objetivos = tiempos_objetivo(120.0, 60)
    ok_cantidades = cantidades == [15, 60]
    ok_emitidos = len(emitidos) == 60 and len(set(emitidos)) == 60
    ok_resultado = resultado.get("fotogramas") == list(objetivos)
    return (
        ok_cantidades and ok_emitidos and ok_resultado,
        f"2min manual 60 -> cantidades={cantidades} emitidos={len(emitidos)}",
    )


def test_05():
    cantidades, emitidos, _presentes, _resultado = _tarea_con_fake(3360.0, 120)
    ok_manual = cantidades == [15, 120] and len(emitidos) == 120
    cantidades_a, emitidos_a, _presentes_a, _resultado_a = _tarea_con_fake(
        3360.0, None
    )
    ok_auto = cantidades_a == [15, 112] and len(emitidos_a) == 112
    return ok_manual and ok_auto, (
        f"manual120={cantidades} auto112={cantidades_a}"
    )


def test_06():
    temp, ruta = _video_temporal()
    base = tempfile.TemporaryDirectory()
    try:
        cuenta = {"n": 0}
        cache.generar_fotogramas(
            "v1", ruta, duracion=30.0, cantidad=15,
            subprocess_run=_mock_ffmpeg(cuenta),
            ruta_carpeta_base=base.name,
        )
        n_tras_15 = cuenta["n"]
        r = cache.generar_fotogramas(
            "v1", ruta, duracion=30.0, cantidad=60,
            subprocess_run=_mock_ffmpeg(cuenta),
            ruta_carpeta_base=base.name,
        )
        ok = (
            n_tras_15 == 15
            and r["reutilizados"] == 15
            and r["generados"] == 45
            and cuenta["n"] == 60
            and r["faltantes"] == 0
            and len(r["fotogramas"]) == 60
        )
    finally:
        base.cleanup()
        temp.cleanup()
    return ok, f"15->60 reutiliza={r['reutilizados']} genera={r['generados']} ffmpeg={cuenta['n']}"


def test_07():
    temp, ruta = _video_temporal()
    base = tempfile.TemporaryDirectory()
    try:
        cuenta = {"n": 0}
        cache.generar_fotogramas(
            "v1", ruta, duracion=30.0, cantidad=60,
            subprocess_run=_mock_ffmpeg(cuenta),
            ruta_carpeta_base=base.name,
        )
        n_tras_60 = cuenta["n"]
        r = cache.generar_fotogramas(
            "v1", ruta, duracion=30.0, cantidad=120,
            subprocess_run=_mock_ffmpeg(cuenta),
            ruta_carpeta_base=base.name,
        )
        ok = (
            n_tras_60 == 60
            and r["reutilizados"] == 60
            and r["generados"] == 60
            and cuenta["n"] == 120
            and r["faltantes"] == 0
            and len(r["fotogramas"]) == 120
        )
    finally:
        base.cleanup()
        temp.cleanup()
    return ok, f"60->120 reutiliza={r['reutilizados']} genera={r['generados']} ffmpeg={cuenta['n']}"


def test_08():
    temp, ruta = _video_temporal()
    base = tempfile.TemporaryDirectory()
    try:
        cuenta = {"n": 0}
        cache.generar_fotogramas(
            "v1", ruta, duracion=30.0, cantidad=120,
            subprocess_run=_mock_ffmpeg(cuenta),
            ruta_carpeta_base=base.name,
        )
        en_disco_antes = len(
            cache.listar_fotogramas_version(
                "v1", cache.version_actual("v1", ruta, 30.0, base.name), base.name
            )
        )
        cuenta["n"] = 0
        version = cache.version_actual("v1", ruta, 30.0, base.name)
        r = cache.generar_fotogramas(
            "v1", ruta, duracion=30.0, cantidad=30,
            subprocess_run=_mock_ffmpeg(cuenta),
            ruta_carpeta_base=base.name,
        )
        en_disco_despues = len(
            cache.listar_fotogramas_version("v1", version, base.name)
        )
        ok = (
            r["reutilizados"] == 30
            and r["generados"] == 0
            and cuenta["n"] == 0
            and r["faltantes"] == 0
            and en_disco_despues == 120
        )
    finally:
        base.cleanup()
        temp.cleanup()
    return ok, f"120->30 sin generar ffmpeg={cuenta['n']} disco={en_disco_despues}"


def test_09():
    temp, ruta = _video_temporal()
    base = tempfile.TemporaryDirectory()
    try:
        cuenta = {"n": 0}
        cache.generar_fotogramas(
            "v1", ruta, duracion=3360.0, cantidad=120,
            subprocess_run=_mock_ffmpeg(cuenta),
            ruta_carpeta_base=base.name,
        )
        en_disco = len(
            cache.listar_fotogramas_version(
                "v1", cache.version_actual("v1", ruta, 3360.0, base.name), base.name
            )
        )
        cuenta["n"] = 0
        r = cache.generar_fotogramas(
            "v1", ruta, duracion=3360.0,
            cantidad=cache.objetivo_total_densidad(3360.0),
            subprocess_run=_mock_ffmpeg(cuenta),
            ruta_carpeta_base=base.name,
        )
        en_disco_final = len(
            cache.listar_fotogramas_version(
                "v1", cache.version_actual("v1", ruta, 3360.0, base.name), base.name
            )
        )
        ok = (
            r["reutilizados"] == 112
            and r["generados"] == 0
            and cuenta["n"] == 0
            and en_disco_final == en_disco == 120
        )
    finally:
        base.cleanup()
        temp.cleanup()
    return ok, f"Auto nuevamente: reutiliza={r['reutilizados']} extras_en_disco={en_disco_final}"


def test_10():
    temp, ruta = _video_temporal()
    base = tempfile.TemporaryDirectory()
    try:
        cuenta = {"n": 0, "activos": 0, "max": 0}

        def _run(comando, *a, **k):
            cuenta["activos"] += 1
            cuenta["max"] = max(cuenta["max"], cuenta["activos"])
            time.sleep(0.003)
            with open(comando[-1], "wb") as f:
                f.write(b"\xff\xd8\xff\xe0datos")
            cuenta["activos"] -= 1
            cuenta["n"] += 1
            return _Resultado(0)

        cache.generar_fotogramas(
            "v1", ruta, duracion=30.0, cantidad=120,
            subprocess_run=_run,
            ruta_carpeta_base=base.name,
        )
        ok = cuenta["max"] == 1 and cuenta["n"] == 120
    finally:
        base.cleanup()
        temp.cleanup()
    return ok, f"manual 120 secuencial max_concurrentes={cuenta['max']} llamadas={cuenta['n']}"


def _tarjeta_con_marcadores(instantes_marcadores):
    tarjeta = Tarjeta(b432._fila_basica())
    tarjeta.expandir()
    tarjeta.agregar_fotogramas_densos(
        [
            {"instante": 0.0, "pixmap": b432._pixmap_color(QColor("red"))},
            {"instante": 50.0, "pixmap": b432._pixmap_color(QColor("green"))},
            {"instante": 100.0, "pixmap": b432._pixmap_color(QColor("blue"))},
        ]
    )
    for instante in instantes_marcadores:
        tarjeta._al_marcador_solicitado(instante)
    return tarjeta


def _etiquetas(tarjeta):
    return list(tarjeta._franja.findChildren(MiniaturaMarcador))


def test_11():
    with b432._miniaturas_temporales():
        tarjeta = _tarjeta_con_marcadores([50.0])
        preview = tarjeta._imagen_exploracion
        etiquetas = _etiquetas(tarjeta)
        if len(etiquetas) != 1:
            return False, f"marcadores={len(etiquetas)}"
        tarjeta._al_instante_exploracion(50.0)
        ok_hover = (
            tarjeta._franja.children()[-1] is preview
            and not preview.isHidden()
        )
        tarjeta.eventFilter(tarjeta._franja, QEvent(QEvent.Leave))
        ok_leave = (
            tarjeta._franja.children()[-1] is not preview
            and not preview.isHidden()
            and etiquetas[0] in tarjeta._franja.children()
        )
    return ok_hover and ok_leave, f"hover_arriba={ok_hover} leave_marcador_arriba={ok_leave}"


def test_12():
    with b432._miniaturas_temporales():
        tarjeta = _tarjeta_con_marcadores([20.0, 80.0])
        preview = tarjeta._imagen_exploracion
        etiquetas = _etiquetas(tarjeta)
        if len(etiquetas) != 2:
            return False, f"marcadores={len(etiquetas)}"
        tarjeta._al_instante_exploracion(50.0)
        ok_hover = tarjeta._franja.children()[-1] is preview
        tarjeta.eventFilter(tarjeta._franja, QEvent(QEvent.Leave))
        ok_leave = tarjeta._franja.children()[-1] is not preview
    return ok_hover and ok_leave, (
        f"varios_marcadores hover_arriba={ok_hover} leave={ok_leave}"
    )


def test_13():
    with b432._miniaturas_temporales():
        tarjeta = _tarjeta_con_marcadores([50.0])
        antes = len(tarjeta._marcadores)
        etiqueta = tarjeta._marcadores[0].get("etiqueta")
        tarjeta._al_marcador_eliminar_solicitado(50.0)
        ok_eliminado = (
            antes == 1
            and len(tarjeta._marcadores) == 0
            and etiqueta is not None
            and etiqueta.isHidden()
        )
        ok_franja = tarjeta._franja._marcadores == []
    return ok_eliminado and ok_franja, (
        f"eliminado={len(tarjeta._marcadores)==0} franja_vacia={tarjeta._franja._marcadores == []}"
    )


def test_14():
    _TareaExploracionDensaFake.creadas = []
    _TareaExploracionDensaFake.liberar = None
    original_tarea = visor_videos.TareaExploracionDensa
    visor_videos.TareaExploracionDensa = _TareaExploracionDensaFake
    ruta_png = b432._crear_png(
        os.path.join(b432._CONFIG_TEMPORAL.name, "fotograma_b433_combo.png")
    )
    original_ruta = cache.ruta_fotograma_version
    cache.ruta_fotograma_version = lambda video_id, ms, version: ruta_png
    try:
        with b432._ventana_con(["clip.mp4"], [30.0]) as (
            ventana,
            tarjetas,
            _carpeta,
        ):
            tarjeta = tarjetas["clip.mp4"]
            tarjeta.expandir()
            b432._esperar(
                lambda: ventana.gestor_exploracion.hilo is None
            )
            ok_auto = (
                tarjeta._selector_densidad.currentData() is None
                and tarjeta._densidad_manual is None
            )
            n_antes = len(_TareaExploracionDensaFake.creadas)
            tarjeta._selector_densidad.setCurrentIndex(3)  # 60
            b432._esperar(
                lambda: ventana.gestor_exploracion.hilo is None
            )
            ok_manual = tarjeta._densidad_manual == 60
            ok_tarea = (
                len(_TareaExploracionDensaFake.creadas) > n_antes
                and _TareaExploracionDensaFake.creadas[-1].objetivo_manual == 60
            )
            ok_opciones = tarjeta._selector_densidad.count() == 6
    finally:
        cache.ruta_fotograma_version = original_ruta
        visor_videos.TareaExploracionDensa = original_tarea
    return ok_auto and ok_manual and ok_tarea and ok_opciones, (
        f"auto={ok_auto} manual_60={tarjeta._densidad_manual} "
        f"tarea_objetivo={_TareaExploracionDensaFake.creadas[-1].objetivo_manual if _TareaExploracionDensaFake.creadas else None}"
    )


def test_15():
    with b432._miniaturas_temporales():
        tarjeta = _tarjeta_con_marcadores([])
        tarjeta._selector_densidad.setCurrentIndex(3)  # 60
        ok_manual = tarjeta._densidad_manual == 60
        tarjeta.colapsar()
        tarjeta.expandir()
        ok_persistio = (
            tarjeta._densidad_manual == 60
            and tarjeta._selector_densidad.currentData() == 60
        )
    return ok_manual and ok_persistio, (
        f"manual={tarjeta._densidad_manual} combo={tarjeta._selector_densidad.currentData()}"
    )


def test_16():
    with b432._miniaturas_temporales():
        tarjeta = _tarjeta_con_marcadores([])
        original_ruta = cache.ruta_fotograma_version

        def _prohibir(*a, **k):
            raise AssertionError("mouseMove no debe leer de disco")

        cache.ruta_fotograma_version = _prohibir
        try:
            pix = tarjeta._pixmap_para_instante(50.0)
            ok_no_disco = pix is not None and not pix.isNull()
            tarjeta._mostrar_preview_para_instante(60.0)
            ok_scrub = (
                tarjeta._imagen_exploracion.pixmap() is not None
                and not tarjeta._imagen_exploracion.pixmap().isNull()
            )
        finally:
            cache.ruta_fotograma_version = original_ruta
    return ok_no_disco and ok_scrub, (
        f"pix_ram={'OK' if ok_no_disco else 'FALLO'} scrub={'OK' if ok_scrub else 'FALLO'}"
    )


def test_17():
    with b432._miniaturas_temporales():
        tarjeta = _tarjeta_con_marcadores([50.0])
        marcador = tarjeta._marcadores[0]
        tiempo_antes = marcador["tiempo"]
        tarjeta.aplicar_densidad(30)
        tarjeta.aplicar_densidad(60)
        ok_tiempo = tarjeta._marcadores[0]["tiempo"] == tiempo_antes == 50.0
        ok_pixmap = tarjeta._marcadores[0].get("pixmap") is not None
    return ok_tiempo and ok_pixmap, (
        f"tiempo={tarjeta._marcadores[0]['tiempo']} pixmap={'OK' if ok_pixmap else 'FALLO'}"
    )


def _tarea_superset(duracion, disco_cantidad, manual):
    """Simula una caché con `disco_cantidad` fotogramas ya en disco (superset).

    La tarea se ejecuta con la densidad `manual` (None = Auto) y el fake de
    generar_fotogramas simula que todos los objetivos ya están reutilizados
    (FFmpeg = 0). Devuelve (cantidades, emitidos, resultado, cola_ms).
    """
    disco = set(tiempos_objetivo(duracion, disco_cantidad))
    cantidades = []
    original_generar = tareas_videos.generar_fotogramas
    original_listar = tareas_videos.listar_fotogramas_version
    original_ruta = tareas_videos.ruta_fotograma_version
    original_version = tareas_videos.version_actual
    ruta_png = b432._crear_png(
        os.path.join(b432._CONFIG_TEMPORAL.name, "fotograma_b433_sup.png")
    )

    def _generar(video_id, ruta_video, duracion=None, cantidad=None,
                 on_progreso=None, cancelar=None):
        cantidades.append(cantidad)
        if cantidad is None:
            cantidad = cache.objetivo_total_densidad(duracion)
        objetivos = tiempos_objetivo(duracion, cantidad)
        for indice, ms in enumerate(objetivos, start=1):
            if on_progreso is not None:
                on_progreso(indice, len(objetivos))
        reutilizados = sum(1 for ms in objetivos if ms in disco)
        return {
            "version": "v9",
            "fotogramas": list(objetivos),
            "reutilizados": reutilizados,
            "generados": 0,
            "cancelado": False,
        }

    tareas_videos.ruta_fotograma_version = (
        lambda video_id, ms, version: ruta_png
    )
    tareas_videos.version_actual = lambda *args, **kwargs: "v9"
    tareas_videos.generar_fotogramas = _generar
    tareas_videos.listar_fotogramas_version = (
        lambda video_id, version, duracion=None: list(disco)
    )
    parciales = []
    try:
        tarea = tareas_videos.TareaExploracionDensa(
            1, "C:\\videos\\clip.mp4", duracion=duracion, cantidad=15,
            objetivo_manual=manual,
        )
        tarea.resultado_parcial.connect(lambda d: parciales.append(d))
        resultado = tarea._trabajo()
    finally:
        tareas_videos.generar_fotogramas = original_generar
        tareas_videos.listar_fotogramas_version = original_listar
        tareas_videos.ruta_fotograma_version = original_ruta
        tareas_videos.version_actual = original_version
    emitidos = [ms for p in parciales for ms, _ in p["fotogramas"]]
    cola_ms = [ms for ms, _ in (resultado.get("imagenes") or [])]
    return cantidades, emitidos, resultado, cola_ms


def test_18():
    cantidades, emitidos, resultado, cola = _tarea_superset(30.0, 120, 30)
    objetivo30 = set(tiempos_objetivo(30.0, 30))
    ok = (
        cantidades == [15, 30]
        and len(emitidos) == 30
        and set(emitidos) == objetivo30
        and all(ms in objetivo30 for ms in cola)
        and resultado.get("generados") == 0
        and resultado.get("reutilizados") == 30
    )
    return ok, f"120->30 emitidos={len(emitidos)} generados={resultado.get('generados')}"


def test_19():
    cantidades, emitidos, resultado, cola = _tarea_superset(30.0, 120, 60)
    objetivo60 = set(tiempos_objetivo(30.0, 60))
    ok = (
        cantidades == [15, 60]
        and len(emitidos) == 60
        and set(emitidos) == objetivo60
        and all(ms in objetivo60 for ms in cola)
        and resultado.get("generados") == 0
        and resultado.get("reutilizados") == 60
    )
    return ok, f"120->60 emitidos={len(emitidos)} generados={resultado.get('generados')}"


def test_20():
    cantidades, emitidos, resultado, cola = _tarea_superset(30.0, 120, None)
    objetivo15 = set(tiempos_objetivo(30.0, 15))
    ok = (
        cantidades == [15]
        and len(emitidos) == 15
        and set(emitidos) == objetivo15
        and all(ms in objetivo15 for ms in cola)
        and resultado.get("generados") == 0
        and resultado.get("reutilizados") == 15
    )
    return ok, f"120->Auto(15) emitidos={len(emitidos)} generados={resultado.get('generados')}"


def test_21():
    cantidades, emitidos, resultado, _cola = _tarea_superset(30.0, 120, 120)
    primeros15 = set(tiempos_objetivo(30.0, 15))
    objetivo120 = set(tiempos_objetivo(30.0, 120))
    ok = (
        cantidades == [15, 120]
        and len(emitidos) == 120
        and set(emitidos) == objetivo120
        and set(emitidos[:15]) == primeros15
        and all(ms not in primeros15 for ms in emitidos[15:])
        and resultado.get("generados") == 0
        and resultado.get("reutilizados") == 120
    )
    return ok, (
        f"fase_rapida_superset emitidos={len(emitidos)} "
        f"primeros15_set_ok={set(emitidos[:15]) == primeros15}"
    )


def test_22():
    _c1, e1, r1, _cola1 = _tarea_superset(30.0, 120, 30)
    _c2, e2, r2, _cola2 = _tarea_superset(30.0, 120, 120)
    ok = (
        len(e1) == 30
        and set(e1) == set(tiempos_objetivo(30.0, 30))
        and len(e2) == 120
        and set(e2) == set(tiempos_objetivo(30.0, 120))
        and r2.get("generados") == 0
        and r2.get("reutilizados") == 120
    )
    return ok, f"30->120 reutiliza={r2.get('reutilizados')} sin_generar={r2.get('generados')}"


def main():
    app = QApplication(sys.argv)
    pruebas = [
        test_01,
        test_02,
        test_03,
        test_04,
        test_05,
        test_06,
        test_07,
        test_08,
        test_09,
        test_10,
        test_11,
        test_12,
        test_13,
        test_14,
        test_15,
        test_16,
        test_17,
        test_18,
        test_19,
        test_20,
        test_21,
        test_22,
    ]
    resultados = []
    for i, fn in enumerate(pruebas, start=1):
        try:
            ok, detalle = fn()
        except Exception as exc:
            ok, detalle = False, f"excepcion: {type(exc).__name__}: {exc}"
        resultados.append((i, ok, detalle))
        print(f"P{i:02d} {'OK' if ok else 'FALLO'} - {detalle}")

    ok_total = all(ok for _, ok, _ in resultados)
    aprobadas = sum(1 for _, ok, _ in resultados if ok)
    print(f"TOTAL={aprobadas}/{len(pruebas)}")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
