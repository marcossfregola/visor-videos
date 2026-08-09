import math
import os
import py_compile
import sys
import tempfile
import time

import escanear_videos as escanear_mod
from escanear_videos import (
    _duracion_utilizable,
    asegurar_miniaturas,
    calcular_tiempo_miniatura,
    calcular_tiempo_preview,
    configurar_cantidad_previews,
    generar_miniatura,
    generar_preview,
    generar_previews_faltantes,
    ruta_preview,
)
from tareas_videos import TareaMiniaturas, TareaPreviewsProgresivas

_CANTIDAD_ORIGINAL = escanear_mod.CANTIDAD_PREVIEWS


class _ResultadoFake:
    def __init__(self, stdout="", returncode=0):
        self.stdout = stdout
        self.returncode = returncode


class _ControladorProcesos:
    """Cuenta ffprobe/ffmpeg y simula su ejecución."""

    def __init__(self):
        self.ffprobe = 0
        self.ffmpeg = 0
        self.argvs = []
        self._original = escanear_mod.subprocess.run

    def _run(self, args, **kwargs):
        base = os.path.basename(args[0]).lower() if args else ""
        self.argvs.append(list(args))
        if base == "ffprobe":
            self.ffprobe += 1
            return _ResultadoFake(
                stdout=(
                    "width=640\n"
                    "height=360\n"
                    "codec_name=h264\n"
                    "duration=40.0\n"
                )
            )
        if base == "ffmpeg":
            self.ffmpeg += 1
            if args:
                destino = args[-1]
                with open(destino, "wb") as f:
                    f.write(b"\xff\xd8")
            return _ResultadoFake()
        return self._original(args, **kwargs)

    def activar(self):
        escanear_mod.subprocess.run = self._run

    def desactivar(self):
        escanear_mod.subprocess.run = self._original

    def ss_de_ffmpeg(self):
        for argv in self.argvs:
            if argv and os.path.basename(argv[0]).lower() == "ffmpeg":
                return argv[3]
        return None


def _crear_video(ruta):
    with open(ruta, "wb") as f:
        f.write(b"datos" * 10)
    return ruta


def _crear_carpeta_videos(nombres):
    temp = tempfile.TemporaryDirectory()
    for nombre in nombres:
        _crear_video(os.path.join(temp.name, nombre))
    return temp


def test_01_py_compile():
    ok = True
    detalles = []
    for archivo in [
        "escanear_videos.py",
        "tareas_videos.py",
        "visor_videos.py",
        "prueba_optimizacion_ffprobe_b452.py",
    ]:
        try:
            py_compile.compile(archivo, doraise=True)
        except py_compile.PyCompileError as exc:
            ok = False
            detalles.append(f"{archivo}: {exc}")
    return ok, "; ".join(detalles) or "py_compile OK"


def test_02_duracion_utilizable():
    casos = [
        (None, False),
        (0, False),
        (-5, False),
        ("abc", False),
        (True, False),
        (float("nan"), False),
        (float("inf"), False),
        (5, True),
        (5.5, True),
        (12.437, True),
    ]
    ok = all(_duracion_utilizable(v) == esperado for v, esperado in casos)
    return ok, str([(v, _duracion_utilizable(v)) for v, _ in casos])


def test_03_miniatura_con_duracion_conocida():
    video = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    video.close()
    _crear_video(video.name)
    ruta_min = os.path.join(
        tempfile.gettempdir(), f"min_{time.monotonic_ns()}.jpg"
    )
    control = _ControladorProcesos()
    control.activar()
    try:
        ok_genero = generar_miniatura(video.name, ruta_min, duracion_segundos=40.0)
    finally:
        control.desactivar()
    ok = ok_genero and control.ffprobe == 0 and control.ffmpeg == 1
    os.remove(video.name)
    if os.path.exists(ruta_min):
        os.remove(ruta_min)
    return ok, f"ffprobe={control.ffprobe} ffmpeg={control.ffmpeg} ok={ok_genero}"


def test_04_preview_con_duracion_conocida():
    video = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    video.close()
    _crear_video(video.name)
    destino = os.path.join(
        tempfile.gettempdir(), f"prev_{time.monotonic_ns()}.jpg"
    )
    control = _ControladorProcesos()
    control.activar()
    try:
        ok_genero = generar_preview(
            video.name, destino, indice=2, duracion_segundos=40.0
        )
    finally:
        control.desactivar()
    ok = ok_genero and control.ffprobe == 0 and control.ffmpeg == 1
    os.remove(video.name)
    if os.path.exists(destino):
        os.remove(destino)
    return ok, f"ffprobe={control.ffprobe} ffmpeg={control.ffmpeg} ok={ok_genero}"


def test_05_fallback_miniatura_sin_duracion():
    video = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    video.close()
    _crear_video(video.name)
    ruta_min = os.path.join(
        tempfile.gettempdir(), f"min_{time.monotonic_ns()}.jpg"
    )
    control = _ControladorProcesos()
    control.activar()
    try:
        ok_genero = generar_miniatura(video.name, ruta_min)
    finally:
        control.desactivar()
    ok = ok_genero and control.ffprobe == 1 and control.ffmpeg == 1
    os.remove(video.name)
    if os.path.exists(ruta_min):
        os.remove(ruta_min)
    return ok, f"ffprobe={control.ffprobe} ffmpeg={control.ffmpeg} ok={ok_genero}"


def test_06_fallback_preview_sin_duracion():
    video = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    video.close()
    _crear_video(video.name)
    destino = os.path.join(
        tempfile.gettempdir(), f"prev_{time.monotonic_ns()}.jpg"
    )
    control = _ControladorProcesos()
    control.activar()
    try:
        ok_genero = generar_preview(video.name, destino, indice=1)
    finally:
        control.desactivar()
    ok = ok_genero and control.ffprobe == 1 and control.ffmpeg == 1
    os.remove(video.name)
    if os.path.exists(destino):
        os.remove(destino)
    return ok, f"ffprobe={control.ffprobe} ffmpeg={control.ffmpeg} ok={ok_genero}"


def test_07_fallback_duracion_invalida():
    casos = [None, 0, -3, "abc", True, float("nan"), float("inf")]
    video = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    video.close()
    _crear_video(video.name)
    resultados = []
    try:
        for caso in casos:
            destino = os.path.join(
                tempfile.gettempdir(), f"prev_{time.monotonic_ns()}.jpg"
            )
            control = _ControladorProcesos()
            control.activar()
            try:
                ok_genero = generar_preview(
                    video.name, destino, indice=1, duracion_segundos=caso
                )
            finally:
                control.desactivar()
            resultados.append(
                (repr(caso), control.ffprobe == 1, ok_genero)
            )
            if os.path.exists(destino):
                os.remove(destino)
    finally:
        os.remove(video.name)
    ok = all(p == 1 for _, p, _ in resultados) and all(
        g for _, _, g in resultados
    )
    return ok, f"fallbacks={resultados}"


def test_08_tiempos_equivalentes():
    video = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    video.close()
    _crear_video(video.name)
    ruta_min_a = os.path.join(
        tempfile.gettempdir(), f"min_{time.monotonic_ns()}.jpg"
    )
    ruta_min_b = os.path.join(
        tempfile.gettempdir(), f"min_{time.monotonic_ns()}.jpg"
    )
    ss_conocida = None
    ss_fallback = None
    try:
        control = _ControladorProcesos()
        control.activar()
        try:
            generar_miniatura(video.name, ruta_min_a, duracion_segundos=40.0)
        finally:
            control.desactivar()
        ss_conocida = control.ss_de_ffmpeg()

        control2 = _ControladorProcesos()
        control2.activar()
        try:
            generar_miniatura(video.name, ruta_min_b)
        finally:
            control2.desactivar()
        ss_fallback = control2.ss_de_ffmpeg()
    finally:
        os.remove(video.name)
        for r in (ruta_min_a, ruta_min_b):
            if os.path.exists(r):
                os.remove(r)
    esperado = str(calcular_tiempo_miniatura(40.0))
    ok = (
        ss_conocida == esperado
        and ss_fallback == esperado
        and ss_conocida == ss_fallback
    )
    return ok, f"ss_conocida={ss_conocida} ss_fallback={ss_fallback} esperado={esperado}"


def test_09_pipeline_miniaturas_con_duraciones():
    temp = _crear_carpeta_videos(["a.mp4", "b.mp4", "c.mp4"])
    carpeta_mini = tempfile.TemporaryDirectory()
    original_mini = escanear_mod.ruta_carpeta_miniaturas
    original_disponible = escanear_mod.ffmpeg_disponible
    escanear_mod.ruta_carpeta_miniaturas = lambda: carpeta_mini.name
    escanear_mod.ffmpeg_disponible = lambda: True
    nombres = sorted(os.listdir(temp.name))
    rutas = {os.path.join(temp.name, n): 40.0 for n in nombres}
    control = _ControladorProcesos()
    control.activar()
    try:
        resultado = asegurar_miniaturas(nombres, temp.name, duraciones=rutas)
    finally:
        control.desactivar()
        escanear_mod.ruta_carpeta_miniaturas = original_mini
        escanear_mod.ffmpeg_disponible = original_disponible
    ok = (
        control.ffprobe == 0
        and control.ffmpeg == 3
        and resultado["con_miniatura"] == 3
    )
    temp.cleanup()
    carpeta_mini.cleanup()
    return ok, (
        f"ffprobe={control.ffprobe} ffmpeg={control.ffmpeg} "
        f"con_miniatura={resultado['con_miniatura']}"
    )


def test_10_pipeline_previews_con_duraciones():
    temp = _crear_carpeta_videos(["a.mp4", "b.mp4", "c.mp4"])
    carpeta_mini = tempfile.TemporaryDirectory()
    original_mini = escanear_mod.ruta_carpeta_miniaturas
    original_disponible = escanear_mod.ffmpeg_disponible
    escanear_mod.ruta_carpeta_miniaturas = lambda: carpeta_mini.name
    escanear_mod.ffmpeg_disponible = lambda: True
    nombres = sorted(os.listdir(temp.name))
    rutas = {os.path.join(temp.name, n): 40.0 for n in nombres}
    control = _ControladorProcesos()
    control.activar()
    try:
        resultado = generar_previews_faltantes(nombres, temp.name, rutas)
    finally:
        control.desactivar()
        escanear_mod.ruta_carpeta_miniaturas = original_mini
        escanear_mod.ffmpeg_disponible = original_disponible
    ok = (
        control.ffprobe == 0
        and control.ffmpeg == 9
        and resultado["generados"] == 9
        and resultado["completos"] == 3
    )
    temp.cleanup()
    carpeta_mini.cleanup()
    return ok, (
        f"ffprobe={control.ffprobe} ffmpeg={control.ffmpeg} "
        f"generados={resultado['generados']}"
    )


def test_11_cache_existente_no_genera():
    temp = _crear_carpeta_videos(["a.mp4", "b.mp4"])
    carpeta_mini = tempfile.TemporaryDirectory()
    original_mini = escanear_mod.ruta_carpeta_miniaturas
    original_disponible = escanear_mod.ffmpeg_disponible
    escanear_mod.ruta_carpeta_miniaturas = lambda: carpeta_mini.name
    escanear_mod.ffmpeg_disponible = lambda: True
    nombres = sorted(os.listdir(temp.name))
    rutas = {os.path.join(temp.name, n): 40.0 for n in nombres}
    try:
        primer_pase = _ControladorProcesos()
        primer_pase.activar()
        try:
            asegurar_miniaturas(nombres, temp.name, duraciones=rutas)
            generar_previews_faltantes(nombres, temp.name, rutas)
        finally:
            primer_pase.desactivar()
        segundo_pase = _ControladorProcesos()
        segundo_pase.activar()
        try:
            r1 = asegurar_miniaturas(nombres, temp.name, duraciones=rutas)
            r2 = generar_previews_faltantes(nombres, temp.name, rutas)
        finally:
            segundo_pase.desactivar()
    finally:
        escanear_mod.ruta_carpeta_miniaturas = original_mini
        escanear_mod.ffmpeg_disponible = original_disponible
    ok = (
        segundo_pase.ffprobe == 0
        and segundo_pase.ffmpeg == 0
        and r1["con_miniatura"] == 2
        and r2["generados"] == 0
    )
    temp.cleanup()
    carpeta_mini.cleanup()
    return ok, (
        f"ffprobe={segundo_pase.ffprobe} ffmpeg={segundo_pase.ffmpeg} "
        f"mini={r1['con_miniatura']} prev={r2['generados']}"
    )


def test_12_callers_antiguos_sin_duracion():
    temp = _crear_carpeta_videos(["a.mp4", "b.mp4"])
    carpeta_mini = tempfile.TemporaryDirectory()
    original_mini = escanear_mod.ruta_carpeta_miniaturas
    original_disponible = escanear_mod.ffmpeg_disponible
    escanear_mod.ruta_carpeta_miniaturas = lambda: carpeta_mini.name
    escanear_mod.ffmpeg_disponible = lambda: True
    nombres = sorted(os.listdir(temp.name))
    control = _ControladorProcesos()
    control.activar()
    try:
        r1 = asegurar_miniaturas(nombres, temp.name)
        r2 = generar_previews_faltantes(nombres, temp.name)
    finally:
        control.desactivar()
        escanear_mod.ruta_carpeta_miniaturas = original_mini
        escanear_mod.ffmpeg_disponible = original_disponible
    # 2 miniaturas (1 ffprobe+1 ffmpeg c/u) + 6 previews (1 ffprobe+1 ffmpeg c/u)
    ok = (
        control.ffprobe == 8
        and control.ffmpeg == 8
        and r1["con_miniatura"] == 2
        and r2["generados"] == 6
    )
    temp.cleanup()
    carpeta_mini.cleanup()
    return ok, (
        f"ffprobe={control.ffprobe} ffmpeg={control.ffmpeg} "
        f"mini={r1['con_miniatura']} prev={r2['generados']}"
    )


def test_13_tarea_miniaturas_con_duraciones():
    temp = _crear_carpeta_videos(["a.mp4", "b.mp4", "c.mp4"])
    carpeta_mini = tempfile.TemporaryDirectory()
    original_mini = escanear_mod.ruta_carpeta_miniaturas
    original_disponible = escanear_mod.ffmpeg_disponible
    escanear_mod.ruta_carpeta_miniaturas = lambda: carpeta_mini.name
    escanear_mod.ffmpeg_disponible = lambda: True
    nombres = sorted(os.listdir(temp.name))
    rutas = {os.path.join(temp.name, n): 40.0 for n in nombres}
    tarea = TareaMiniaturas(nombres, temp.name, duraciones=rutas)
    control = _ControladorProcesos()
    control.activar()
    try:
        resultado = tarea._trabajo()
    finally:
        control.desactivar()
        escanear_mod.ruta_carpeta_miniaturas = original_mini
        escanear_mod.ffmpeg_disponible = original_disponible
    ok = control.ffprobe == 0 and control.ffmpeg == 3
    temp.cleanup()
    carpeta_mini.cleanup()
    return ok, f"ffprobe={control.ffprobe} ffmpeg={control.ffmpeg}"


def test_14_tarea_previews_con_duraciones():
    temp = _crear_carpeta_videos(["a.mp4", "b.mp4"])
    carpeta_mini = tempfile.TemporaryDirectory()
    original_mini = escanear_mod.ruta_carpeta_miniaturas
    original_disponible = escanear_mod.ffmpeg_disponible
    escanear_mod.ruta_carpeta_miniaturas = lambda: carpeta_mini.name
    escanear_mod.ffmpeg_disponible = lambda: True
    nombres = sorted(os.listdir(temp.name))
    rutas = {os.path.join(temp.name, n): 40.0 for n in nombres}
    tarea = TareaPreviewsProgresivas(nombres, temp.name, duraciones=rutas)
    control = _ControladorProcesos()
    control.activar()
    try:
        resultado = tarea._trabajo()
    finally:
        control.desactivar()
        escanear_mod.ruta_carpeta_miniaturas = original_mini
        escanear_mod.ffmpeg_disponible = original_disponible
    ok = control.ffprobe == 0 and control.ffmpeg == 6
    temp.cleanup()
    carpeta_mini.cleanup()
    return ok, f"ffprobe={control.ffprobe} ffmpeg={control.ffmpeg}"


def main():
    configurar_cantidad_previews(3)
    try:
        pruebas = [
            test_01_py_compile,
            test_02_duracion_utilizable,
            test_03_miniatura_con_duracion_conocida,
            test_04_preview_con_duracion_conocida,
            test_05_fallback_miniatura_sin_duracion,
            test_06_fallback_preview_sin_duracion,
            test_07_fallback_duracion_invalida,
            test_08_tiempos_equivalentes,
            test_09_pipeline_miniaturas_con_duraciones,
            test_10_pipeline_previews_con_duraciones,
            test_11_cache_existente_no_genera,
            test_12_callers_antiguos_sin_duracion,
            test_13_tarea_miniaturas_con_duraciones,
            test_14_tarea_previews_con_duraciones,
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
