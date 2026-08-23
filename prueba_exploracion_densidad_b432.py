"""Pruebas de B4.3.2 Etapa 2: densidad secundaria adaptativa.

Cubre: fórmula de densidad (1 cada 30 s, mín 15, máx 200), fase rápida
siempre primero, los 15 iniciales no se regeneran, reutilización 45/100,
generación secuencial (máximo un FFmpeg a la vez), incorporación
progresiva de secundarios, cancelación A->B sin fugas, colapso que libera
RAM, reexpansión que reutiliza, mouseMove solo en RAM y marcadores que
conservan tiempo/id y pueden mejorar su imagen.

Requiere PySide (reutiliza helpers de la suite B4.3.2 ya estable).
"""

import gc
import os
import py_compile
import sys
import tempfile
import threading
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import QApplication

import exploracion_cache as cache
import tareas_videos
import visor_videos
import prueba_exploracion_b432 as b432
from exploracion_temporal import preview_mas_cercana, tiempos_objetivo
from visor_videos import Tarjeta, VisorVideos


class _Resultado:
    def __init__(self, returncode):
        self.returncode = returncode


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


def _generar_fase_fake(cantidades, presentes, duracion):
    """Fake de generar_fotogramas que puebla `presentes` de a un fotograma."""

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


def test_01():
    modulos = [
        "tareas_videos.py",
        "visor_videos.py",
        "exploracion_cache.py",
        "prueba_exploracion_densidad_b432.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    casos = [
        (120, 15),    # 2 min
        (600, 20),    # 10 min
        (1800, 60),   # 30 min
        (3000, 100),  # 50 min
        (3360, 112),  # 56 min
        (7200, 200),  # 2 h
    ]
    for d, esperado in casos:
        obtenido = cache.objetivo_total_densidad(d)
        if obtenido != esperado:
            return False, f"{d}s -> {obtenido} (esperado {esperado})"
    invalidos = [(0, 0), (-5, 0), (True, 0), (None, 0), ("x", 0), (False, 0)]
    for d, esperado in invalidos:
        if cache.objetivo_total_densidad(d) != esperado:
            return False, f"invalido {d!r} -> {cache.objetivo_total_densidad(d)}"
    limites = [(1, 15), (30, 15), (450, 15), (451, 16), (6000, 200), (6001, 200)]
    for d, esperado in limites:
        if cache.objetivo_total_densidad(d) != esperado:
            return False, f"limite {d}s -> {cache.objetivo_total_densidad(d)} (esperado {esperado})"
    return True, "densidad 2m=15 10m=20 30m=60 50m=100 56m=112 2h=200 e invalidos OK"


def test_03():
    cantidades = []
    presentes = []
    original_generar = tareas_videos.generar_fotogramas
    original_listar = tareas_videos.listar_fotogramas_version
    original_ruta = tareas_videos.ruta_fotograma_version
    original_version = tareas_videos.version_actual
    ruta_png = b432._crear_png(
        os.path.join(b432._CONFIG_TEMPORAL.name, "fotograma_dens_fases.png")
    )
    tareas_videos.ruta_fotograma_version = (
        lambda video_id, ms, version: ruta_png
    )
    tareas_videos.version_actual = lambda *args, **kwargs: "v9"
    tareas_videos.generar_fotogramas = _generar_fase_fake(
        cantidades, presentes, 3000.0
    )
    tareas_videos.listar_fotogramas_version = (
        lambda video_id, version, duracion=None: list(presentes)
    )
    parciales = []
    try:
        tarea = tareas_videos.TareaExploracionDensa(
            1, "C:\\videos\\clip.mp4", duracion=3000.0, cantidad=15
        )
        tarea.resultado_parcial.connect(lambda d: parciales.append(d))
        resultado = tarea._trabajo()
        primeros_15 = tiempos_objetivo(3000.0, 15)
        objetivos_100 = tiempos_objetivo(3000.0, 100)
        secundarios = objetivos_100[15:]
        emitidos = [ms for p in parciales for ms, _ in p["fotogramas"]]
        ok_cantidades = cantidades == [15, 100]
        ok_15_primero = (
            len(emitidos) == 100
            and emitidos[:15] == list(primeros_15)
            and all(ms in set(secundarios) for ms in emitidos[15:])
        )
        ok_no_duplicados = len(set(emitidos)) == 100
        ok_presentes = presentes == list(objetivos_100)
        ok_resultado = resultado.get("fotogramas") == list(objetivos_100)
        ok_version = all(p["version"] == "v9" for p in parciales)
    finally:
        tareas_videos.generar_fotogramas = original_generar
        tareas_videos.listar_fotogramas_version = original_listar
        tareas_videos.ruta_fotograma_version = original_ruta
        tareas_videos.version_actual = original_version
    return (
        ok_cantidades
        and ok_15_primero
        and ok_no_duplicados
        and ok_presentes
        and ok_resultado
        and ok_version,
        f"cantidades={cantidades} emitidos={len(emitidos)} 15_primero={emitidos[:3]}...",
    )


def test_04():
    temp, ruta = _video_temporal()
    base = tempfile.TemporaryDirectory()
    try:
        cuenta = {"n": 0}
        r1 = cache.generar_fotogramas(
            "v1", ruta, duracion=3000.0, cantidad=15,
            subprocess_run=_mock_ffmpeg(cuenta),
            ruta_carpeta_base=base.name,
        )
        n_tras_rapida = cuenta["n"]
        r2 = cache.generar_fotogramas(
            "v1", ruta, duracion=3000.0, cantidad=100,
            subprocess_run=_mock_ffmpeg(cuenta),
            ruta_carpeta_base=base.name,
        )
        ok = (
            n_tras_rapida == 15
            and r1["generados"] == 15
            and r2["reutilizados"] == 15
            and r2["generados"] == 85
            and r2["faltantes"] == 0
            and cuenta["n"] == 100
            and len(
                cache.listar_fotogramas(
                    "v1", ruta, 3000.0, base.name, cantidad=100
                )
            ) == 100
        )
    finally:
        base.cleanup()
        temp.cleanup()
    return ok, (
        f"rapida={n_tras_rapida} ffmpeg_total={cuenta['n']} "
        f"reutiliza={r2['reutilizados']} genera={r2['generados']}"
    )


def test_05():
    temp, ruta = _video_temporal()
    base = tempfile.TemporaryDirectory()
    try:
        version = cache.version_actual("v1", ruta, 3000.0, base.name)
        objetivos = tiempos_objetivo(3000.0, 100)
        for ms in objetivos[:45]:
            ruta_f = cache.ruta_fotograma_version(
                "v1", ms, version, base.name
            )
            os.makedirs(os.path.dirname(ruta_f), exist_ok=True)
            with open(ruta_f, "wb") as f:
                f.write(b"\xff\xd8\xff\xe0datos")
        cuenta = {"n": 0}
        r = cache.generar_fotogramas(
            "v1", ruta, duracion=3000.0, cantidad=100,
            subprocess_run=_mock_ffmpeg(cuenta),
            ruta_carpeta_base=base.name,
        )
        ok = (
            r["reutilizados"] == 45
            and r["generados"] == 55
            and cuenta["n"] == 55
            and r["faltantes"] == 0
            and len(r["fotogramas"]) == 100
        )
    finally:
        base.cleanup()
        temp.cleanup()
    return ok, (
        f"reutilizados={r['reutilizados']} generados={r['generados']} "
        f"ffmpeg={cuenta['n']}"
    )


def test_06():
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
            "v1", ruta, duracion=3000.0, cantidad=100,
            subprocess_run=_run,
            ruta_carpeta_base=base.name,
        )
        ok = cuenta["max"] == 1 and cuenta["n"] == 100
    finally:
        base.cleanup()
        temp.cleanup()
    return ok, f"max_concurrentes={cuenta['max']} llamadas={cuenta['n']}"


def test_07():
    cantidades = []
    presentes = []
    original_generar = tareas_videos.generar_fotogramas
    original_listar = tareas_videos.listar_fotogramas_version
    original_ruta = tareas_videos.ruta_fotograma_version
    original_version = tareas_videos.version_actual
    ruta_png = b432._crear_png(
        os.path.join(b432._CONFIG_TEMPORAL.name, "fotograma_dens_prog.png")
    )
    tareas_videos.ruta_fotograma_version = (
        lambda video_id, ms, version: ruta_png
    )
    tareas_videos.version_actual = lambda *args, **kwargs: "v9"

    def _generar_prog(video_id, ruta_video, duracion=None, cantidad=None,
                      on_progreso=None, cancelar=None):
        cantidades.append(cantidad)
        if cantidad is None:
            cantidad = cache.objetivo_total_densidad(duracion)
        objetivos = tiempos_objetivo(duracion, cantidad)
        for indice, ms in enumerate(objetivos, start=1):
            if ms not in presentes:
                presentes.append(ms)
            if on_progreso is not None and indice % 10 == 0:
                on_progreso(indice, len(objetivos))
        return {
            "version": "v9",
            "fotogramas": list(objetivos),
            "cancelado": False,
        }

    tareas_videos.generar_fotogramas = _generar_prog
    tareas_videos.listar_fotogramas_version = (
        lambda video_id, version, duracion=None: list(presentes)
    )
    parciales = []
    try:
        tarea = tareas_videos.TareaExploracionDensa(
            1, "C:\\videos\\clip.mp4", duracion=3000.0, cantidad=15
        )
        tarea.resultado_parcial.connect(lambda d: parciales.append(d))
        tarea._trabajo()
        emitidos = [ms for p in parciales for ms, _ in p["fotogramas"]]
        acumulados = []
        for p in parciales:
            acumulados.append(len(p["fotogramas"]))
        ok_multiples = len(parciales) >= 5
        ok_total = len(emitidos) == 100
        ok_no_duplicados = len(set(emitidos)) == 100
        ok_progresivo = all(x > 0 for x in acumulados)
        primeros_15 = tiempos_objetivo(3000.0, 15)
        ok_15_primero = emitidos[:15] == list(primeros_15)
    finally:
        tareas_videos.generar_fotogramas = original_generar
        tareas_videos.listar_fotogramas_version = original_listar
        tareas_videos.ruta_fotograma_version = original_ruta
        tareas_videos.version_actual = original_version
    return (
        ok_multiples
        and ok_total
        and ok_no_duplicados
        and ok_progresivo
        and ok_15_primero,
        f"parciales={len(parciales)} emitidos={len(emitidos)} tamanos={acumulados[:6]}...",
    )


def test_08():
    b432._TareaExploracionDensaFake.creadas = []
    b432._TareaExploracionDensaFake.liberar = threading.Event()
    b432._TareaExploracionDensaFake.parciales = []
    b432._TareaExploracionDensaFake.resultado = {
        "version": "v1",
        "fotogramas": [0, 5000, 10000],
    }
    original_tarea = visor_videos.TareaExploracionDensa
    visor_videos.TareaExploracionDensa = b432._TareaExploracionDensaFake
    ruta_png = b432._crear_png(
        os.path.join(b432._CONFIG_TEMPORAL.name, "fotograma_dens_ab.png")
    )
    original_ruta = cache.ruta_fotograma_version
    cache.ruta_fotograma_version = lambda video_id, ms, version: ruta_png
    try:
        with b432._ventana_con(["clip1.mp4", "clip2.mp4"], [3000.0, 50.0]) as (
            ventana,
            tarjetas,
            _carpeta,
        ):
            tarjeta1 = tarjetas["clip1.mp4"]
            tarjeta2 = tarjetas["clip2.mp4"]
            tarjeta1.expandir()
            ok_a_activa = _esperar_(
                lambda: ventana.tarea_exploracion is not None
                and ventana.gestor_exploracion.hilo is not None
            )
            tarea_a = ventana.tarea_exploracion
            tarjeta2.expandir()
            ok_cancelada_a = tarea_a._cancelada is True
            ok_colapsada_a = not tarjeta1._expandida
            ok_objetivo_b = ventana._exploracion_objetivo == "clip2.mp4"
            b432._TareaExploracionDensaFake.liberar.set()
            _esperar_(lambda: ventana.gestor_exploracion.hilo is None)
            _esperar_(lambda: len(tarjeta2._previews_densos) == 3)
            ok_b_densos = len(tarjeta2._previews_densos) == 3
            antes = len(tarjeta2._previews_densos)
            ventana._al_resultado_parcial_exploracion(
                {
                    "video_id": 1,
                    "version": "v1",
                    "fotogramas": [(5000, b432._crear_qimage(5000))],
                }
            )
            ok_tardio_ignorado = (
                len(tarjeta2._previews_densos) == antes
                and len(tarjeta1._previews_densos) == 0
            )
    finally:
        b432._TareaExploracionDensaFake.liberar.set()
        b432._TareaExploracionDensaFake.parciales = []
        cache.ruta_fotograma_version = original_ruta
        visor_videos.TareaExploracionDensa = original_tarea
    return (
        ok_a_activa
        and ok_cancelada_a
        and ok_colapsada_a
        and ok_objetivo_b
        and ok_b_densos
        and ok_tardio_ignorado,
        f"cancelada_a={tarea_a._cancelada} densos_b={len(tarjeta2._previews_densos)}",
    )


def test_09():
    b432._TareaExploracionDensaFake.creadas = []
    b432._TareaExploracionDensaFake.liberar = threading.Event()
    b432._TareaExploracionDensaFake.parciales = []
    b432._TareaExploracionDensaFake.resultado = {
        "version": "v1",
        "fotogramas": [0, 5000, 10000],
    }
    original_tarea = visor_videos.TareaExploracionDensa
    visor_videos.TareaExploracionDensa = b432._TareaExploracionDensaFake
    ruta_png = b432._crear_png(
        os.path.join(b432._CONFIG_TEMPORAL.name, "fotograma_dens_colapso.png")
    )
    original_ruta = cache.ruta_fotograma_version
    cache.ruta_fotograma_version = lambda video_id, ms, version: ruta_png
    try:
        with b432._ventana_con(["clip1.mp4"], [3000.0]) as (
            ventana,
            tarjetas,
            _carpeta,
        ):
            tarjeta1 = tarjetas["clip1.mp4"]
            tarjeta1.expandir()
            _esperar_(
                lambda: ventana.tarea_exploracion is not None
                and ventana.gestor_exploracion.hilo is not None
            )
            tarea = ventana.tarea_exploracion
            tarjeta1.colapsar()
            ok_cancelada = tarea._cancelada is True
            ok_ram_liberada = (
                tarjeta1._previews_densos == []
                and tarjeta1._previews_exploracion == []
            )
            ok_objetivo_limpio = (
                ventana._exploracion_objetivo is None
                and ventana._cola_exploracion == []
            )
            b432._TareaExploracionDensaFake.liberar.set()
            _esperar_(lambda: ventana.gestor_exploracion.hilo is None)
    finally:
        b432._TareaExploracionDensaFake.liberar.set()
        b432._TareaExploracionDensaFake.parciales = []
        cache.ruta_fotograma_version = original_ruta
        visor_videos.TareaExploracionDensa = original_tarea
    return ok_cancelada and ok_ram_liberada and ok_objetivo_limpio, (
        f"cancelada={tarea._cancelada} densos={len(tarjeta1._previews_densos)}"
    )


def test_10():
    b432._TareaExploracionDensaFake.creadas = []
    b432._TareaExploracionDensaFake.liberar = None
    b432._TareaExploracionDensaFake.resultado = {
        "version": "v1",
        "fotogramas": [0, 5000, 10000],
    }
    original_tarea = visor_videos.TareaExploracionDensa
    visor_videos.TareaExploracionDensa = b432._TareaExploracionDensaFake
    ruta_png = b432._crear_png(
        os.path.join(b432._CONFIG_TEMPORAL.name, "fotograma_dens_reexp.png")
    )
    original_ruta = cache.ruta_fotograma_version
    cache.ruta_fotograma_version = lambda video_id, ms, version: ruta_png
    try:
        with b432._ventana_con(["clip1.mp4"], [3000.0]) as (
            ventana,
            tarjetas,
            _carpeta,
        ):
            tarjeta1 = tarjetas["clip1.mp4"]
            tarjeta1.expandir()
            _esperar_(lambda: ventana.gestor_exploracion.hilo is None)
            ok_primera = len(tarjeta1._previews_densos) == 3
            tarjeta1.colapsar()
            tarjeta1.expandir()
            _esperar_(lambda: ventana.gestor_exploracion.hilo is None)
            ok_segunda = len(tarjeta1._previews_densos) == 3
            ok_dos_tareas = len(b432._TareaExploracionDensaFake.creadas) == 2
    finally:
        b432._TareaExploracionDensaFake.parciales = []
        cache.ruta_fotograma_version = original_ruta
        visor_videos.TareaExploracionDensa = original_tarea
    return ok_primera and ok_segunda and ok_dos_tareas, (
        f"tareas={len(b432._TareaExploracionDensaFake.creadas)} "
        f"densos_1ra={len(tarjeta1._previews_densos)}"
    )


def test_11():
    with b432._miniaturas_temporales():
        tarjeta = Tarjeta(b432._fila_basica())
        tarjeta.expandir()
        tarjeta.agregar_fotogramas_densos(
            [
                {"instante": 0.0, "pixmap": b432._pixmap_color(QColor("red"))},
                {"instante": 50.0, "pixmap": b432._pixmap_color(QColor("green"))},
                {"instante": 100.0, "pixmap": b432._pixmap_color(QColor("blue"))},
            ]
        )
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
        f"pix_para_instante={'OK' if ok_no_disco else 'FALLO'} "
        f"scrub={'OK' if ok_scrub else 'FALLO'}"
    )


def test_12():
    with b432._miniaturas_temporales():
        tarjeta = Tarjeta(b432._fila_basica())
        tarjeta.expandir()
        tarjeta.agregar_fotogramas_densos(
            [
                {"instante": 0.0, "pixmap": b432._pixmap_color(QColor("red"))},
                {"instante": 90.0, "pixmap": b432._pixmap_color(QColor("blue"))},
            ]
        )
        marcador = {"tiempo": 50.0, "id": "m1"}
        instantes = lambda: [d["instante"] for d in tarjeta._previews_densos]
        idx1 = preview_mas_cercana(instantes(), marcador["tiempo"])
        dist1 = abs(instantes()[idx1] - marcador["tiempo"])
        tarjeta.agregar_fotogramas_densos(
            [
                {"instante": 30.0, "pixmap": b432._pixmap_color(QColor("green"))},
                {"instante": 60.0, "pixmap": b432._pixmap_color(QColor("yellow"))},
            ]
        )
        idx2 = preview_mas_cercana(instantes(), marcador["tiempo"])
        dist2 = abs(instantes()[idx2] - marcador["tiempo"])
        ok_mejora = dist2 < dist1
        ok_marcador_intacto = (
            marcador["tiempo"] == 50.0 and marcador["id"] == "m1"
        )
        pix = tarjeta._pixmap_para_instante(50.0)
        ok_pix = pix is not None and not pix.isNull()
    return ok_mejora and ok_marcador_intacto and ok_pix, (
        f"dist_antes={dist1} dist_despues={dist2}"
    )


def _esperar_(predicado, timeout_ms=8000, paso_ms=20):
    import time as _t

    fin = _t.monotonic() + timeout_ms / 1000
    while _t.monotonic() < fin:
        QApplication.processEvents()
        if predicado():
            return True
        _t.sleep(paso_ms / 1000)
    QApplication.processEvents()
    return predicado()


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
