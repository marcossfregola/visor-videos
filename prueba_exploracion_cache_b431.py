"""Pruebas de B4.3.1: motor de caché densa de exploración temporal.

Cubre: densidad, orden progresivo, nearest-frame por bisect, estructura
versionada (`<video_id>/<version>/`), fingerprint sin hash, invalidación
no destructiva, reanudación de generaciones parciales, fallos parciales,
aislamiento A/B/C, atomicidad, nearest solo sobre la versión actual y
aislamiento de las reglas de la etapa (sin UI, sin SQLite, sin tocar la
caché real).

No requiere PySide.
"""

import contextlib
import json
import os
import py_compile
import shutil
import sys
import tempfile
import time

import exploracion_cache as cache
import rutas
from exploracion_temporal import (
    cantidad_fotogramas,
    duracion_valida,
    fotograma_mas_cercano,
    tiempos_objetivo,
)

_VIDEO_REAL = os.path.join("videos_prueba", "video_real.mp4")


def _video_temporal(contenido=b"datos del video"):
    temp = tempfile.TemporaryDirectory()
    ruta = os.path.join(temp.name, "video.mp4")
    with open(ruta, "wb") as f:
        f.write(contenido)
    return temp, ruta


class _Resultado:
    def __init__(self, returncode):
        self.returncode = returncode


def _mock_ffmpeg(cuenta, contenido=b"\xff\xd8\xff\xe0datos"):
    def _run(comando, *args, **kwargs):
        cuenta["n"] += 1
        with open(comando[-1], "wb") as f:
            f.write(contenido)
        return _Resultado(0)

    return _run


def _mock_ffmpeg_falla(cuenta):
    def _run(comando, *args, **kwargs):
        cuenta["n"] += 1
        return _Resultado(1)

    return _run


def _mock_ffmpeg_parcial(cuenta, tope, contenido):
    def _run(comando, *args, **kwargs):
        cuenta["n"] += 1
        if cuenta["n"] <= tope:
            with open(comando[-1], "wb") as f:
                f.write(contenido)
            return _Resultado(0)
        return _Resultado(1)

    return _run


def _modificar_video(ruta, delta=10):
    with open(ruta, "ab") as f:
        f.write(b"modificacion")
    os.utime(ruta, (os.path.getmtime(ruta) + delta, os.path.getmtime(ruta) + delta))


def _version(base, video_id, ruta, duracion):
    return cache.version_actual(video_id, ruta, duracion, base)


def _contenido_fotograma(base, video_id, version, ms):
    with open(cache.ruta_fotograma_version(video_id, ms, version, base), "rb") as f:
        return f.read()


def _magic_jpeg(base, video_id, version, ms):
    ruta = cache.ruta_fotograma_version(video_id, ms, version, base)
    with open(ruta, "rb") as f:
        cabecera = f.read(2)
    return cabecera == b"\xff\xd8"


def _versiones_disco(base, video_id):
    carpeta = cache.ruta_carpeta_video_exploracion(video_id, base)
    if not os.path.isdir(carpeta):
        return []
    return sorted(n for n in os.listdir(carpeta) if os.path.isdir(os.path.join(carpeta, n)))


def test_01():
    modulos = [
        "exploracion_temporal.py",
        "rutas.py",
        "exploracion_cache.py",
        "prueba_exploracion_cache_b431.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    casos = [
        (30.0, 40),
        (80.0, 40),
        (100.0, 50),
        (400.0, 200),
        (500.0, 200),
        (700.0, 200),
        (10.0, 40),
        (1.0, 40),
        (0.0, 0),
        (None, 0),
        (-5.0, 0),
        (True, 0),
        ("100", 0),
    ]
    for duracion, esperado in casos:
        valor = cantidad_fotogramas(duracion)
        if valor != esperado:
            return False, f"dur={duracion!r}: {valor} != {esperado}"
    return True, "clamp(round(dur/2), 40, 200) y duraciones invalidas OK"


def test_03():
    esperado = [50000, 25000, 75000, 12500, 37500, 62500, 87500]
    resultado = tiempos_objetivo(100.0, 7)
    if resultado != esperado:
        return False, f"orden={resultado}"
    if tiempos_objetivo(100.0, 7) != esperado:
        return False, "no determinista"
    grande = tiempos_objetivo(100.0, 50)
    if len(grande) != 50 or len(set(grande)) != 50:
        return False, f"grande={len(grande)} unicos={len(set(grande))}"
    corto = tiempos_objetivo(0.3, 40)
    if len(corto) != 40 or len(set(corto)) != 40:
        return False, f"corto={len(corto)} unicos={len(set(corto))}"
    inicio = tiempos_objetivo(100.0, 1)
    if inicio != [50000]:
        return False, f"inicio={inicio}"
    invalidos = [
        tiempos_objetivo(0.0, 5),
        tiempos_objetivo(None, 5),
        tiempos_objetivo(-3.0, 5),
        tiempos_objetivo(100.0, 0),
        tiempos_objetivo(100.0, -1),
        tiempos_objetivo(100.0, True),
        tiempos_objetivo("100", 5),
    ]
    if any(v != [] for v in invalidos):
        return False, f"invalidos={invalidos}"
    return True, "orden 50/25/75/... determinista y sin duplicados OK"


def test_04():
    casos = [
        (([20000, 30000], 27.0), 30000),
        (([20000, 30000], 25.0), 20000),
        (([20000, 30000], 20.0), 20000),
        (([20000, 30000], 30.0), 30000),
        (([20000, 30000], 0.0), 20000),
        (([20000, 30000], 100.0), 30000),
        (([30000, 20000], 25.0), 20000),
        (([20000], 27.0), 20000),
        (([], 10.0), None),
        (([20000, 30000], None), None),
        (([20000, 30000], "x"), None),
        (("20000", 10.0), None),
    ]
    for (lista, instante), esperado in casos:
        valor = fotograma_mas_cercano(lista, instante)
        if valor != esperado:
            return False, f"lista={lista} instante={instante!r}: {valor} != {esperado}"
    return True, "nearest: 27s->30s, empate 25s->20s, bordes y ausencia OK"


def test_05():
    base = tempfile.TemporaryDirectory().name
    if not rutas.ruta_carpeta_exploracion().endswith(
        os.path.join("miniaturas", "exploracion")
    ):
        return False, "ruta_carpeta_exploracion incorrecta"
    carpeta = cache.ruta_carpeta_video_exploracion("v1", base)
    if carpeta != os.path.join(base, "v1"):
        return False, f"carpeta={carpeta}"
    version = cache.version_id_de_fingerprint({
        "ruta": r"c:\x\clip.mp4", "tamano_bytes": 100,
        "mtime_ns": 123, "duracion_segundos": 10.0,
    })
    if not (isinstance(version, str) and len(version) == 16):
        return False, f"version={version!r}"
    ruta = cache.ruta_fotograma_version("v1", 1234567, version, base)
    nombre = os.path.basename(ruta)
    if nombre != "f0001234567.jpg":
        return False, f"nombre={nombre}"
    if "v1" in nombre:
        return False, "video_id no debe repetirse en el nombre del JPG"
    if os.path.dirname(ruta) != os.path.join(base, "v1", version):
        return False, f"carpeta de version incorrecta: {os.path.dirname(ruta)}"
    if os.path.basename(cache.ruta_meta_version("v1", version, base)) != "meta.json":
        return False, "nombre de meta incorrecto"
    return True, "estructura <video_id>/<version>/f{ms:010d}.jpg y meta.json OK"


def test_06():
    if cache.video_id_desde_ruta(r"c:\x\Mi Video_2.mp4") != "Mi_Video_2":
        return False, "id derivado incorrecto"
    a = cache.video_id_desde_ruta(r"C:\carpeta\clips.mp4")
    b = cache.video_id_desde_ruta(r"D:\otra\clips.mp4")
    if a != b:
        return False, "debe derivarse solo del nombre base (sin hash)"
    try:
        cache.video_id_desde_ruta("")
        return False, "ruta vacia debe fallar"
    except ValueError:
        pass
    return True, "video_id_desde_ruta: nombre saneado y determinista"


def test_07():
    temp = tempfile.TemporaryDirectory()
    try:
        carpeta = cache.ruta_carpeta_version("v1", "abc", temp.name)
        os.makedirs(carpeta)
        for nombre in ("f000020000.jpg", "f000010000.jpg"):
            with open(os.path.join(carpeta, nombre), "wb") as f:
                f.write(b"x")
        with open(os.path.join(carpeta, "nota.txt"), "w") as f:
            f.write("x")
        with open(os.path.join(carpeta, "fabc.jpg"), "w") as f:
            f.write("x")
        with open(os.path.join(carpeta, "g000010000.jpg"), "w") as f:
            f.write("x")
        with open(os.path.join(carpeta, "fotograma_x.jpg"), "wb") as f:
            f.write(b"x")
        with open(os.path.join(carpeta, "f000030000.jpg.tmp"), "wb") as f:
            f.write(b"x")
        if cache.listar_fotogramas_version("v1", "abc", temp.name) != [10000, 20000]:
            return False, f"listado={cache.listar_fotogramas_version('v1', 'abc', temp.name)}"
        if cache.listar_fotogramas_version("v1", "xyz", temp.name) != []:
            return False, "version ausente debe devolver []"
        if cache.listar_fotogramas_version("v2", "abc", temp.name) != []:
            return False, "video ausente debe devolver []"
        if cache.listar_fotogramas_version("v1", "abc", temp.name, duracion=100.0) != []:
            return False, "fotogramas fuera del conjunto objetivo no deben listarse con duracion"
        with open(os.path.join(carpeta, "f000050000.jpg"), "wb") as f:
            f.write(b"x")
        if cache.listar_fotogramas_version("v1", "abc", temp.name, duracion=100.0) != [50000]:
            return False, "filtro por conjunto objetivo incorrecto"
    finally:
        temp.cleanup()
    return True, "listar_fotogramas_version: parseo, filtro objetivo, orden y ausencia OK"


def test_08():
    temp, ruta = _video_temporal()
    try:
        base = tempfile.TemporaryDirectory().name
        version = cache.version_actual("v1", ruta, 10.0, base)
        if not (isinstance(version, str) and len(version) == 16):
            return False, f"version={version!r}"
        carpeta = cache.ruta_carpeta_version("v1", version, base)
        os.makedirs(carpeta)
        cache._escribir_meta(carpeta, "v1", ruta, 10.0)
        if not cache.cache_vigente("v1", ruta, 10.0, base):
            return False, "fingerprint identico debe ser vigente"
        version_antes = version
        _modificar_video(ruta)
        if cache.cache_vigente("v1", ruta, 10.0, base):
            return False, "contenido cambiado debe invalidar"
        if cache.cache_vigente("v1", ruta, 20.0, base):
            return False, "duracion distinta debe invalidar"
        if cache.cache_vigente("v2", ruta, 10.0, base):
            return False, "sin meta debe ser invalido"
        version_despues = cache.version_actual("v1", ruta, 10.0, base)
        if version_despues == version_antes:
            return False, "el cambio de fingerprint debe cambiar la version"
        ruta_meta = cache.ruta_meta_version("v3", "xyz", base)
        os.makedirs(os.path.dirname(ruta_meta))
        with open(ruta_meta, "w", encoding="utf-8") as f:
            f.write("[1, 2]")
        if cache.cache_vigente("v3", ruta, 10.0, base):
            return False, "meta no-diccionario debe ser invalido"
    finally:
        temp.cleanup()
    return True, "fingerprint ruta+tamano+mtime+duracion y version derivada OK"


def test_09():
    temp, ruta = _video_temporal()
    base = tempfile.TemporaryDirectory()
    try:
        cuenta = {"n": 0}
        progresos = []
        resultado = cache.generar_fotogramas(
            "v1", ruta, duracion=100.0, cantidad=50,
            on_progreso=lambda p, t: progresos.append((p, t)),
            subprocess_run=_mock_ffmpeg(cuenta),
            ruta_carpeta_base=base.name,
        )
        fotogramas = cache.listar_fotogramas(
            "v1", ruta, 100.0, base.name, cantidad=50
        )
        version = resultado["version"]
        carpeta = cache.ruta_carpeta_version("v1", version, base.name)
        ok = (
            resultado["generados"] == 50
            and resultado["errores"] == 0
            and resultado["reutilizados"] == 0
            and resultado["faltantes"] == 0
            and not resultado["cancelado"]
            and resultado["cantidad_objetivo"] == 50
            and len(fotogramas) == 50
            and cuenta["n"] == 50
            and progresos and progresos[-1] == (50, 50) and len(progresos) == 50
            and cache.cache_vigente("v1", ruta, 100.0, base.name)
        )
        if not ok:
            return False, f"resultado={resultado} cuenta={cuenta['n']}"
        meta = cache.leer_meta_version("v1", version, base.name)
        if meta is None or meta.get("video_id") != "v1":
            return False, "meta.json faltante o sin video_id"
        for clave in ("ruta", "tamano_bytes", "mtime_ns", "duracion_segundos"):
            if clave not in meta:
                return False, f"meta sin clave {clave}"
        sobras = [
            n for n in os.listdir(carpeta)
            if n.endswith(".tmp") or n.startswith("fotograma_")
        ]
        if sobras:
            return False, f"quedaron temporales: {sobras}"
    finally:
        base.cleanup()
        temp.cleanup()
    return True, f"generacion con FFmpeg simulado: 50/50, meta y sin temporales (ffmpeg={cuenta['n']})"


def test_10():
    temp, ruta = _video_temporal()
    base = tempfile.TemporaryDirectory()
    try:
        cuenta = {"n": 0}
        cache.generar_fotogramas(
            "v1", ruta, duracion=100.0, cantidad=10,
            subprocess_run=_mock_ffmpeg(cuenta),
            ruta_carpeta_base=base.name,
        )
        cuenta["n"] = 0
        resultado = cache.generar_fotogramas(
            "v1", ruta, duracion=100.0, cantidad=10,
            subprocess_run=_mock_ffmpeg(cuenta),
            ruta_carpeta_base=base.name,
        )
        ok = (
            resultado["reutilizados"] == 10
            and resultado["generados"] == 0
            and cuenta["n"] == 0
            and cache.cache_vigente("v1", ruta, 100.0, base.name)
        )
    finally:
        base.cleanup()
        temp.cleanup()
    return ok, f"segunda corrida vigente reutiliza sin FFmpeg (ffmpeg={cuenta['n']})"


def test_11():
    temp, ruta = _video_temporal()
    base = tempfile.TemporaryDirectory()
    try:
        cuenta = {"n": 0}
        cache.generar_fotogramas(
            "v1", ruta, duracion=100.0, cantidad=10,
            subprocess_run=_mock_ffmpeg(cuenta),
            ruta_carpeta_base=base.name,
        )
        version_a = _version(base.name, "v1", ruta, 100.0)
        carpeta_a = cache.ruta_carpeta_version("v1", version_a, base.name)
        huesped = os.path.join(carpeta_a, "f000000005.jpg")
        with open(huesped, "wb") as f:
            f.write(b"\xff\xd8sobra")
        _modificar_video(ruta)
        version_b = _version(base.name, "v1", ruta, 100.0)
        if version_b == version_a:
            return False, "el fingerprint nuevo debe derivar una version distinta"
        if cache.cache_vigente("v1", ruta, 100.0, base.name):
            return False, "debe invalidarse tras modificar el video"
        cuenta["n"] = 0
        resultado = cache.generar_fotogramas(
            "v1", ruta, duracion=100.0, cantidad=10,
            subprocess_run=_mock_ffmpeg(cuenta),
            ruta_carpeta_base=base.name,
        )
        carpeta_b = cache.ruta_carpeta_version("v1", version_b, base.name)
        ok = (
            resultado["version"] == version_b
            and resultado["generados"] == 10
            and resultado["reutilizados"] == 0
            and cuenta["n"] == 10
            and os.path.isfile(os.path.join(carpeta_a, "f000000005.jpg"))
            and os.path.isdir(carpeta_a)
            and os.path.isfile(cache.ruta_meta_version("v1", version_a, base.name))
            and os.path.isdir(carpeta_b)
            and cache.cache_vigente("v1", ruta, 100.0, base.name)
        )
    finally:
        base.cleanup()
        temp.cleanup()
    return ok, f"invalidacion no destructiva: nueva version B, conserva version A (ffmpeg={cuenta['n']})"


def test_12():
    temp, ruta = _video_temporal()
    base = tempfile.TemporaryDirectory()
    try:
        cuenta = {"n": 0}
        resultado = cache.generar_fotogramas(
            "v1", ruta, duracion=100.0, cantidad=10,
            cancelar=lambda: cuenta["n"] >= 1,
            subprocess_run=_mock_ffmpeg(cuenta),
            ruta_carpeta_base=base.name,
        )
        version = resultado["version"]
        carpeta = cache.ruta_carpeta_version("v1", version, base.name)
        ok = (
            resultado["cancelado"]
            and resultado["generados"] == 1
            and cuenta["n"] == 1
            and len(cache.listar_fotogramas_version("v1", version, base.name)) == 1
            and not os.path.isfile(cache.ruta_meta_version("v1", version, base.name))
            and not cache.cache_vigente("v1", ruta, 100.0, base.name)
            and os.path.isdir(carpeta)
        )
    finally:
        base.cleanup()
        temp.cleanup()
    return ok, f"cancelacion cooperativa tras 1 fotograma, sin meta en la version (ffmpeg={cuenta['n']})"


def test_13():
    temp, ruta = _video_temporal()
    base = tempfile.TemporaryDirectory()
    try:
        cuenta = {"n": 0}
        resultado = cache.generar_fotogramas(
            "v1", ruta, duracion=100.0, cantidad=10,
            subprocess_run=_mock_ffmpeg_falla(cuenta),
            ruta_carpeta_base=base.name,
        )
        version = resultado["version"]
        carpeta = cache.ruta_carpeta_version("v1", version, base.name)
        ok = (
            resultado["errores"] == 10
            and resultado["generados"] == 0
            and resultado["faltantes"] == 10
            and cache.listar_fotogramas_version("v1", version, base.name) == []
            and not os.path.isfile(cache.ruta_meta_version("v1", version, base.name))
            and os.path.isdir(carpeta)
        )
    finally:
        base.cleanup()
        temp.cleanup()
    return ok, f"fallo FFmpeg: 10 errores, sin archivos ni meta (ffmpeg={cuenta['n']})"


def test_14():
    base = tempfile.TemporaryDirectory()
    try:
        destino = os.path.join(base.name, "salida.bin")
        cache._escribir_bytes_atomicamente(destino, b"hola")
        with open(destino, "rb") as f:
            contenido = f.read()
        sobras_ok = not [
            n for n in os.listdir(base.name) if n.endswith(".tmp")
        ]
        original = cache.os.replace

        def _falla(*a, **k):
            raise OSError("simulado")

        cache.os.replace = _falla
        try:
            try:
                cache._escribir_bytes_atomicamente(
                    os.path.join(base.name, "falla.bin"), b"x"
                )
                ok_excepcion = False
            except OSError:
                ok_excepcion = True
        finally:
            cache.os.replace = original
        ok = (
            contenido == b"hola"
            and sobras_ok
            and ok_excepcion
            and not os.path.isfile(os.path.join(base.name, "falla.bin"))
            and not [
                n for n in os.listdir(base.name) if n.endswith(".tmp")
            ]
        )
    finally:
        base.cleanup()
    return ok, "escritura atomica: exito y fallo sin dejar temporales"


def test_15():
    temp, ruta = _video_temporal()
    try:
        version = cache.version_actual("v1", ruta, 100.0, temp.name)
        carpeta = cache.ruta_carpeta_version("v1", version, temp.name)
        os.makedirs(carpeta)
        for ms in (25000, 75000):
            with open(cache.ruta_fotograma_version("v1", ms, version, temp.name), "wb") as f:
                f.write(b"\xff\xd8x")
        casos = [
            (27.0, 25000),
            (25.0, 25000),
            (20.0, 25000),
            (100.0, 75000),
            (0.0, 25000),
            (5.0, 25000),
        ]
        for instante, esperado in casos:
            valor = cache.fotograma_mas_cercano_en_cache(
                "v1", instante, ruta, 100.0, temp.name
            )
            if valor != esperado:
                return False, f"instante={instante}: {valor} != {esperado}"
        if cache.fotograma_mas_cercano_en_cache("v2", 10.0, ruta, 100.0, temp.name) is not None:
            return False, "sin cache debe devolver None"
    finally:
        temp.cleanup()
    return True, "nearest sobre la version actual en disco OK"


def test_16():
    if not os.path.isfile(_VIDEO_REAL):
        return False, f"falta video real: {_VIDEO_REAL}"
    if not cache.ffmpeg_disponible():
        return False, "ffmpeg no disponible"
    duracion = cache.duracion_video(_VIDEO_REAL)
    if not duracion_valida(duracion):
        return False, f"duracion invalida: {duracion}"
    cantidad = min(cache.cantidad_fotogramas(duracion), 20)
    if cantidad < 10:
        return False, f"benchmark demasiado corto: {cantidad}"
    base = tempfile.TemporaryDirectory()
    antes = {
        "existe": os.path.isdir(rutas.ruta_carpeta_exploracion()),
        "contenido": sorted(os.listdir(rutas.ruta_carpeta_exploracion()))
        if os.path.isdir(rutas.ruta_carpeta_exploracion())
        else [],
    }
    inicio = time.monotonic()
    resultado = cache.generar_fotogramas(
        "bench_real", os.path.abspath(_VIDEO_REAL),
        duracion=duracion, cantidad=cantidad,
        ruta_carpeta_base=base.name,
    )
    transcurrido = time.monotonic() - inicio
    version = resultado["version"]
    fotogramas = cache.listar_fotogramas_version(
        "bench_real", version, base.name, duracion
    )
    ok = (
        resultado["generados"] == cantidad
        and resultado["errores"] == 0
        and not resultado["cancelado"]
        and len(fotogramas) == cantidad
        and all(
            _magic_jpeg(base.name, "bench_real", version, ms)
            for ms in fotogramas
        )
        and cache.cache_vigente(
            "bench_real", os.path.abspath(_VIDEO_REAL), duracion, base.name
        )
    )
    despues = {
        "existe": os.path.isdir(rutas.ruta_carpeta_exploracion()),
        "contenido": sorted(os.listdir(rutas.ruta_carpeta_exploracion()))
        if os.path.isdir(rutas.ruta_carpeta_exploracion())
        else [],
    }
    ok = ok and antes == despues
    base.cleanup()
    if not ok:
        return False, f"benchmark: generados={resultado['generados']} errores={resultado['errores']} fotogramas={len(fotogramas)} tiempo={transcurrido:.2f}s"
    return True, f"FFmpeg real: {cantidad} JPEG validos en {transcurrido:.2f}s sin tocar la caché real"


def test_17():
    with open("exploracion_cache.py", encoding="utf-8") as f:
        fuente_cache = f.read()
    with open("exploracion_temporal.py", encoding="utf-8") as f:
        fuente_temporal = f.read()
    for texto, nombre in (
        (fuente_cache, "exploracion_cache.py"),
        (fuente_temporal, "exploracion_temporal.py"),
    ):
        for prohibido in (
            "PySide",
            "sqlite",
            "import escanear_videos",
            "from escanear_videos",
            "import Q",
        ):
            if prohibido in texto:
                return False, f"{nombre} no debe referenciar {prohibido!r}"
    if not hasattr(rutas, "ruta_carpeta_miniaturas"):
        return False, "ruta_carpeta_miniaturas debe seguir existiendo"
    if rutas.ruta_carpeta_miniaturas() != os.path.join(rutas.ruta_raiz(), "miniaturas"):
        return False, "ruta_carpeta_miniaturas alterada"
    return True, "aislamiento: sin Qt/SQLite/escanear_videos y rutas intactas"


def test_18():
    temp, ruta = _video_temporal(b"contenido A" * 100)
    base = tempfile.TemporaryDirectory()
    try:
        cache.generar_fotogramas(
            "v", ruta, duracion=100.0, cantidad=10,
            subprocess_run=_mock_ffmpeg({"n": 0}, b"AAAA"),
            ruta_carpeta_base=base.name,
        )
        version_a = _version(base.name, "v", ruta, 100.0)
        if not cache.cache_vigente("v", ruta, 100.0, base.name):
            return False, "caché A no quedó vigente"
        _modificar_video(ruta)
        version_b = _version(base.name, "v", ruta, 100.0)
        if version_b == version_a:
            return False, "debe existir una version B distinta"
        cuenta = {"n": 0}
        res = cache.generar_fotogramas(
            "v", ruta, duracion=100.0, cantidad=10,
            subprocess_run=_mock_ffmpeg_parcial(cuenta, 6, b"BBBB"),
            ruta_carpeta_base=base.name,
        )
        ok = (
            res["version"] == version_b
            and res["generados"] == 6
            and res["errores"] == 4
            and res["reutilizados"] == 0
            and res["faltantes"] == 4
            and not res["cancelado"]
            and not cache.cache_vigente("v", ruta, 100.0, base.name)
        )
        if not ok:
            return False, f"fallo parcial: {res}"
        fotos_a = cache.listar_fotogramas_version("v", version_a, base.name)
        fotos_b = cache.listar_fotogramas_version("v", version_b, base.name)
        if len(fotos_b) != 6 or any(
            _contenido_fotograma(base.name, "v", version_b, ms) != b"BBBB"
            for ms in fotos_b
        ):
            return False, "la version B debe tener 6 JPEGs BBBB"
        if any(
            _contenido_fotograma(base.name, "v", version_a, ms) != b"AAAA"
            for ms in fotos_a
        ) or len(fotos_a) != 10:
            return False, "la version A debe permanecer intacta"
        if not os.path.isfile(cache.ruta_meta_version("v", version_a, base.name)):
            return False, "el meta de A debe seguir existiendo"
        if os.path.isfile(cache.ruta_meta_version("v", version_b, base.name)):
            return False, "el meta de B no debe escribirse con la version incompleta"
        cuenta["n"] = 0
        res_final = cache.generar_fotogramas(
            "v", ruta, duracion=100.0, cantidad=10,
            subprocess_run=_mock_ffmpeg(cuenta, b"BBBB"),
            ruta_carpeta_base=base.name,
        )
        fotos_b_final = cache.listar_fotogramas_version("v", version_b, base.name)
        ok_final = (
            res_final["reutilizados"] == 6
            and res_final["generados"] == 4
            and cache.cache_vigente("v", ruta, 100.0, base.name)
            and len(fotos_b_final) == 10
            and all(
                _contenido_fotograma(base.name, "v", version_b, ms) == b"BBBB"
                for ms in fotos_b_final
            )
        )
    finally:
        base.cleanup()
        temp.cleanup()
    return (
        ok_final,
        "fallo parcial deja B sin meta y A intacta; al reanudar reutiliza 6 y completa 4",
    )


def test_19():
    temp, ruta = _video_temporal(b"contenido A" * 100)
    base = tempfile.TemporaryDirectory()
    try:
        cache.generar_fotogramas(
            "v", ruta, duracion=100.0, cantidad=10,
            subprocess_run=_mock_ffmpeg({"n": 0}, b"AAAA"),
            ruta_carpeta_base=base.name,
        )
        version_a = _version(base.name, "v", ruta, 100.0)
        _modificar_video(ruta)
        version_b = _version(base.name, "v", ruta, 100.0)
        cuenta = {"n": 0}
        res = cache.generar_fotogramas(
            "v", ruta, duracion=100.0, cantidad=10,
            cancelar=lambda: cuenta["n"] >= 2,
            subprocess_run=_mock_ffmpeg(cuenta, b"BBBB"),
            ruta_carpeta_base=base.name,
        )
        ok = (
            res["cancelado"]
            and res["generados"] == 2
            and res["version"] == version_b
            and not cache.cache_vigente("v", ruta, 100.0, base.name)
            and not os.path.isfile(cache.ruta_meta_version("v", version_b, base.name))
            and os.path.isdir(cache.ruta_carpeta_version("v", version_a, base.name))
        )
        cuenta["n"] = 0
        res_completa = cache.generar_fotogramas(
            "v", ruta, duracion=100.0, cantidad=10,
            subprocess_run=_mock_ffmpeg(cuenta, b"BBBB"),
            ruta_carpeta_base=base.name,
        )
        ok_final = (
            ok
            and res_completa["reutilizados"] == 2
            and res_completa["generados"] == 8
            and cache.cache_vigente("v", ruta, 100.0, base.name)
        )
    finally:
        base.cleanup()
        temp.cleanup()
    return ok_final, "cancelacion durante regeneracion: B parcial sin meta, A intacta, reanuda 2+8"


def test_20():
    temp, ruta = _video_temporal(b"contenido" * 100)
    base = tempfile.TemporaryDirectory()
    try:
        cache.generar_fotogramas(
            "v", ruta, duracion=100.0,
            subprocess_run=_mock_ffmpeg({"n": 0}, b"AAAA"),
            ruta_carpeta_base=base.name,
        )
        version_a = _version(base.name, "v", ruta, 100.0)
        cache.generar_fotogramas(
            "v", ruta, duracion=30.0,
            subprocess_run=_mock_ffmpeg({"n": 0}, b"BBBB"),
            ruta_carpeta_base=base.name,
        )
        version_b = _version(base.name, "v", ruta, 30.0)
        objetivo_b = sorted(tiempos_objetivo(30.0, cantidad_fotogramas(30.0)))
        if version_a == version_b:
            return False, "duraciones distintas deben derivar versiones distintas"
        if not cache.cache_vigente("v", ruta, 30.0, base.name):
            return False, "caché B (duración 30) no vigente"
        indice_b = cache.listar_fotogramas("v", ruta, 30.0, base.name)
        if indice_b != objetivo_b:
            return False, "la versión actual debe listar solo el conjunto B"
        fotos_a = cache.listar_fotogramas_version("v", version_a, base.name)
        if len(fotos_a) != len(tiempos_objetivo(100.0, cantidad_fotogramas(100.0))):
            return False, "la versión A debe permanecer completa en disco"
        cercano = cache.fotograma_mas_cercano_en_cache(
            "v", 50.0, ruta, 30.0, base.name
        )
        ok = (
            cercano is not None
            and cercano in set(objetivo_b)
            and os.path.isdir(cache.ruta_carpeta_version("v", version_a, base.name))
        )
    finally:
        base.cleanup()
        temp.cleanup()
    return ok, f"versiones por duración coexisten; la actual (30s) lista/nearest solo B"


def test_21():
    temp, ruta = _video_temporal(b"contenido B" * 100)
    base = tempfile.TemporaryDirectory()
    try:
        cuenta = {"n": 0}
        primera = cache.generar_fotogramas(
            "v", ruta, duracion=100.0, cantidad=20,
            cancelar=lambda: cuenta["n"] >= 8,
            subprocess_run=_mock_ffmpeg(cuenta, b"BBBB"),
            ruta_carpeta_base=base.name,
        )
        ok1 = (
            primera["cancelado"]
            and primera["generados"] == 8
            and primera["faltantes"] == 12
            and not cache.cache_vigente("v", ruta, 100.0, base.name)
        )
        version = primera["version"]
        cuenta["n"] = 0
        segunda = cache.generar_fotogramas(
            "v", ruta, duracion=100.0, cantidad=20,
            subprocess_run=_mock_ffmpeg(cuenta, b"BBBB"),
            ruta_carpeta_base=base.name,
        )
        ok2 = (
            segunda["reutilizados"] == 8
            and segunda["generados"] == 12
            and cuenta["n"] == 12
            and segunda["faltantes"] == 0
            and segunda["version"] == version
            and cache.cache_vigente("v", ruta, 100.0, base.name)
            and len(cache.listar_fotogramas_version("v", version, base.name)) == 20
        )
    finally:
        base.cleanup()
        temp.cleanup()
    return (
        ok1 and ok2,
        f"reanudacion: 8/20 reutilizados, FFmpeg solo para los 12 restantes (ffmpeg={cuenta['n']})",
    )


def test_22():
    temp, ruta = _video_temporal(b"contenido B" * 100)
    base = tempfile.TemporaryDirectory()
    try:
        cuenta = {"n": 0}
        primera = cache.generar_fotogramas(
            "v", ruta, duracion=100.0, cantidad=10,
            subprocess_run=_mock_ffmpeg_parcial(cuenta, 6, b"BBBB"),
            ruta_carpeta_base=base.name,
        )
        ok1 = (
            primera["generados"] == 6
            and primera["errores"] == 4
            and primera["faltantes"] == 4
            and not cache.cache_vigente("v", ruta, 100.0, base.name)
        )
        version = primera["version"]
        cuenta["n"] = 0
        segunda = cache.generar_fotogramas(
            "v", ruta, duracion=100.0, cantidad=10,
            subprocess_run=_mock_ffmpeg(cuenta, b"BBBB"),
            ruta_carpeta_base=base.name,
        )
        carpeta = cache.ruta_carpeta_version("v", version, base.name)
        temporales = [n for n in os.listdir(carpeta) if n.endswith(".tmp")]
        ok2 = (
            segunda["reutilizados"] == 6
            and segunda["generados"] == 4
            and segunda["errores"] == 0
            and segunda["faltantes"] == 0
            and cuenta["n"] == 4
            and not temporales
            and cache.cache_vigente("v", ruta, 100.0, base.name)
        )
    finally:
        base.cleanup()
        temp.cleanup()
    return (
        ok1 and ok2,
        f"fallos parciales: reutiliza 6 exitosos, reintenta solo 4 faltantes, sin .tmp (ffmpeg={cuenta['n']})",
    )


def test_23():
    temp, ruta = _video_temporal(b"contenido A" * 100)
    base = tempfile.TemporaryDirectory()
    try:
        cache.generar_fotogramas(
            "v", ruta, duracion=100.0, cantidad=10,
            subprocess_run=_mock_ffmpeg({"n": 0}, b"AAAA"),
            ruta_carpeta_base=base.name,
        )
        version_a = _version(base.name, "v", ruta, 100.0)
        _modificar_video(ruta)
        version_b = _version(base.name, "v", ruta, 100.0)
        cuenta_b = {"n": 0}
        cache.generar_fotogramas(
            "v", ruta, duracion=100.0, cantidad=10,
            cancelar=lambda: cuenta_b["n"] >= 1,
            subprocess_run=_mock_ffmpeg(cuenta_b, b"BBBB"),
            ruta_carpeta_base=base.name,
        )
        fotos_b = cache.listar_fotogramas_version("v", version_b, base.name)
        if not fotos_b:
            return False, "la version B debería tener al menos un fotograma"
        if any(
            _contenido_fotograma(base.name, "v", version_b, ms) == b"AAAA"
            for ms in fotos_b
        ):
            return False, "B jamás debe contener JPEGs de A"
        lista_actual = cache.listar_fotogramas("v", ruta, 100.0, base.name)
        if not all(ms in set(fotos_b) for ms in lista_actual):
            return False, "listar la versión actual debe usar solo fotogramas de B"
        cercano = cache.fotograma_mas_cercano_en_cache(
            "v", lista_actual[0] / 1000.0, ruta, 100.0, base.name
        )
        if cercano not in set(fotos_b):
            return False, "nearest de la versión actual debe provenir de B"
        if not os.path.isdir(cache.ruta_carpeta_version("v", version_a, base.name)):
            return False, "A debe permanecer en disco"
    finally:
        base.cleanup()
        temp.cleanup()
    return True, "A->B: B nunca lista ni usa JPEGs de A; A permanece"


def test_24():
    temp, ruta = _video_temporal(b"contenido A" * 100)
    base = tempfile.TemporaryDirectory()
    try:
        cache.generar_fotogramas(
            "v", ruta, duracion=100.0, cantidad=10,
            subprocess_run=_mock_ffmpeg({"n": 0}, b"AAAA"),
            ruta_carpeta_base=base.name,
        )
        version_a = _version(base.name, "v", ruta, 100.0)
        _modificar_video(ruta)
        version_b = _version(base.name, "v", ruta, 100.0)
        cache.generar_fotogramas(
            "v", ruta, duracion=100.0, cantidad=10,
            cancelar=lambda: True,
            subprocess_run=_mock_ffmpeg({"n": 0}, b"BBBB"),
            ruta_carpeta_base=base.name,
        )
        parciales_b = cache.listar_fotogramas_version("v", version_b, base.name)
        _modificar_video(ruta)
        version_c = _version(base.name, "v", ruta, 100.0)
        if len({version_a, version_b, version_c}) != 3:
            return False, "A/B/C deben ser tres versiones distintas"
        cuenta = {"n": 0}
        res = cache.generar_fotogramas(
            "v", ruta, duracion=100.0, cantidad=10,
            subprocess_run=_mock_ffmpeg(cuenta, b"CCCC"),
            ruta_carpeta_base=base.name,
        )
        ok = (
            res["version"] == version_c
            and res["generados"] == 10
            and res["reutilizados"] == 0
            and cuenta["n"] == 10
            and cache.cache_vigente("v", ruta, 100.0, base.name)
            and all(
                _contenido_fotograma(base.name, "v", version_c, ms) == b"CCCC"
                for ms in cache.listar_fotogramas_version("v", version_c, base.name)
            )
            and len(cache.listar_fotogramas_version("v", version_b, base.name)) == len(parciales_b)
            and os.path.isdir(cache.ruta_carpeta_version("v", version_a, base.name))
        )
    finally:
        base.cleanup()
        temp.cleanup()
    return ok, "B->C: C no reutiliza B; A y B permanecen en disco"


def test_25():
    temp, ruta = _video_temporal(b"contenido B" * 100)
    base = tempfile.TemporaryDirectory()
    try:
        cuenta = {"n": 0}
        parcial = cache.generar_fotogramas(
            "v", ruta, duracion=100.0, cantidad=20,
            cancelar=lambda: cuenta["n"] >= 6,
            subprocess_run=_mock_ffmpeg(cuenta, b"BBBB"),
            ruta_carpeta_base=base.name,
        )
        version = parcial["version"]
        faltantes_parcial = cache.faltantes("v", ruta, 100.0, base.name, cantidad=20)
        if not (parcial["faltantes"] == 14 and len(faltantes_parcial) == 14):
            return False, f"versión parcial debe reportar faltantes: {faltantes_parcial}"
        if len(cache.listar_fotogramas_version("v", version, base.name)) != 6:
            return False, "versión parcial debe reconocerse con sus 6 JPEGs"
        cuenta["n"] = 0
        cache.generar_fotogramas(
            "v", ruta, duracion=100.0, cantidad=20,
            subprocess_run=_mock_ffmpeg(cuenta, b"BBBB"),
            ruta_carpeta_base=base.name,
        )
        faltantes_final = cache.faltantes("v", ruta, 100.0, base.name, cantidad=20)
        ok = (
            faltantes_final == []
            and cache.cache_vigente("v", ruta, 100.0, base.name)
            and len(cache.listar_fotogramas_version("v", version, base.name)) == 20
        )
    finally:
        base.cleanup()
        temp.cleanup()
    return ok, "completitud: parcial reporta 14 faltantes; completa reporta 0"


def test_26():
    temp, ruta = _video_temporal(b"contenido B" * 100)
    base = tempfile.TemporaryDirectory()
    try:
        version = cache.version_actual("v", ruta, 100.0, base.name)
        carpeta = cache.ruta_carpeta_version("v", version, base.name)
        os.makedirs(carpeta)
        plantados = [
            os.path.join(carpeta, "f000050000.jpg.tmp"),
            os.path.join(carpeta, "fotograma_xxxx.jpg"),
        ]
        with open(plantados[0], "wb") as f:
            f.write(b"\xff\xd8parcial")
        with open(plantados[1], "wb") as f:
            f.write(b"\xff\xd8preparado")
        if cache.listar_fotogramas_version("v", version, base.name) != []:
            return False, "temporales/preparados no deben listarse como fotogramas"
        cuenta = {"n": 0}
        res = cache.generar_fotogramas(
            "v", ruta, duracion=100.0, cantidad=10,
            subprocess_run=_mock_ffmpeg_parcial(cuenta, 5, b"BBBB"),
            ruta_carpeta_base=base.name,
        )
        presentes = cache.listar_fotogramas_version("v", version, base.name)
        if len(presentes) != 5:
            return False, "FFmpeg fallido no debe producir fotograma reutilizable"
        resumen = cache.faltantes("v", ruta, 100.0, base.name, cantidad=10)
        if len(resumen) != 5:
            return False, "los faltantes deben ser exactamente los 5 no generados"
        cuenta["n"] = 0
        res2 = cache.generar_fotogramas(
            "v", ruta, duracion=100.0, cantidad=10,
            subprocess_run=_mock_ffmpeg(cuenta, b"BBBB"),
            ruta_carpeta_base=base.name,
        )
        if not (
            res2["reutilizados"] == 5
            and res2["generados"] == 5
            and cuenta["n"] == 5
        ):
            return False, "la reanudación debe reutilizar 5 y regenerar 5"
        for ruta_plantada in plantados:
            with contextlib.suppress(OSError):
                os.remove(ruta_plantada)
        ok = not [
            n for n in os.listdir(carpeta)
            if n.endswith(".tmp") or n.startswith("fotograma_")
        ]
    finally:
        base.cleanup()
        temp.cleanup()
    return ok, "atomicidad: .tmp/preparados ignorados; fallidos no se reutilizan"


def test_27():
    temp, ruta = _video_temporal(b"contenido A" * 100)
    base = tempfile.TemporaryDirectory()
    try:
        cache.generar_fotogramas(
            "v", ruta, duracion=100.0, cantidad=10,
            subprocess_run=_mock_ffmpeg({"n": 0}, b"AAAA"),
            ruta_carpeta_base=base.name,
        )
        version_a = _version(base.name, "v", ruta, 100.0)
        _modificar_video(ruta)
        version_b = _version(base.name, "v", ruta, 100.0)
        if len(cache.listar_fotogramas_version("v", version_a, base.name)) != 10:
            return False, "A debe estar completa en disco"
        if cache.fotograma_mas_cercano_en_cache(
            "v", 10.0, ruta, 100.0, base.name
        ) is not None:
            return False, "con la versión B vacía, nearest debe ser None (nunca usar A)"
        cache.generar_fotogramas(
            "v", ruta, duracion=100.0, cantidad=10,
            subprocess_run=_mock_ffmpeg({"n": 0}, b"BBBB"),
            ruta_carpeta_base=base.name,
        )
        fotos_b = set(cache.listar_fotogramas_version("v", version_b, base.name))
        cercano = cache.fotograma_mas_cercano_en_cache(
            "v", 33.0, ruta, 100.0, base.name
        )
        ok = cercano in fotos_b
    finally:
        base.cleanup()
        temp.cleanup()
    return ok, "nearest solo consulta la versión actual; nunca la A en disco"


def test_28():
    temp, ruta = _video_temporal(b"contenido A" * 100)
    base = tempfile.TemporaryDirectory()
    try:
        cache.generar_fotogramas(
            "v", ruta, duracion=100.0, cantidad=10,
            subprocess_run=_mock_ffmpeg({"n": 0}, b"AAAA"),
            ruta_carpeta_base=base.name,
        )
        version_a = _version(base.name, "v", ruta, 100.0)
        _modificar_video(ruta)
        cache.generar_fotogramas(
            "v", ruta, duracion=100.0, cantidad=10,
            subprocess_run=_mock_ffmpeg({"n": 0}, b"BBBB"),
            ruta_carpeta_base=base.name,
        )
        version_b = _version(base.name, "v", ruta, 100.0)
        _modificar_video(ruta)
        cache.generar_fotogramas(
            "v", ruta, duracion=100.0, cantidad=10,
            subprocess_run=_mock_ffmpeg({"n": 0}, b"CCCC"),
            ruta_carpeta_base=base.name,
        )
        version_c = _version(base.name, "v", ruta, 100.0)
        versiones = _versiones_disco(base.name, "v")
        if versiones != sorted([version_a, version_b, version_c]):
            return False, f"deben coexistir A/B/C: {versiones}"
        if not cache.cache_vigente("v", ruta, 100.0, base.name):
            return False, "C debe ser la vigente"
        ok = all(
            len(cache.listar_fotogramas_version("v", ver, base.name)) == 10
            for ver in (version_a, version_b, version_c)
        )
    finally:
        base.cleanup()
        temp.cleanup()
    return ok, "A/B/C coexisten completas en disco; ninguna se borra automáticamente"


def test_29():
    temp, ruta = _video_temporal(b"contenido B" * 100)
    base = tempfile.TemporaryDirectory()
    try:
        cuenta = {"n": 0}
        cache.generar_fotogramas(
            "v", ruta, duracion=100.0, cantidad=20,
            cancelar=lambda: cuenta["n"] >= 8,
            subprocess_run=_mock_ffmpeg(cuenta, b"BBBB"),
            ruta_carpeta_base=base.name,
        )
        total_ffmpeg_parcial = cuenta["n"]
        cuenta["n"] = 0
        res = cache.generar_fotogramas(
            "v", ruta, duracion=100.0, cantidad=20,
            subprocess_run=_mock_ffmpeg(cuenta, b"BBBB"),
            ruta_carpeta_base=base.name,
        )
        ok = (
            total_ffmpeg_parcial == 8
            and res["reutilizados"] == 8
            and cuenta["n"] == 12
            and (total_ffmpeg_parcial + cuenta["n"]) == 20
        )
    finally:
        base.cleanup()
        temp.cleanup()
    return (
        ok,
        f"costo de reanudación: 8 llamadas evitadas (8+12=20 fotogramas totales)",
    )


def main():
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
        test_23,
        test_24,
        test_25,
        test_26,
        test_27,
        test_28,
        test_29,
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
