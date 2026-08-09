"""Motor de caché densa de exploración temporal en disco (etapa B4.3.1).

Guarda en `miniaturas/exploracion/<video_id>/<version>/` un conjunto de
JPEGs pequeños (`f{ms:010d}.jpg`) que representan instantes del video a
lo largo de toda su duración, para poder mostrar el fotograma más
cercano al hacer scrubbing sin depender de las previews de B4.1.

Diseño aprobado (versionado físico por fingerprint):

- `video_id` identifica la carpeta contenedora y no se repite en el
  nombre del JPG.
- Cada versión vive en su propia carpeta:
  `miniaturas/exploracion/<video_id>/<version>/meta.json` + `f*.jpg`.
- La versión es un digest corto y estable de los metadatos baratos
  (ruta normalizada + tamaño + `mtime_ns` + duración). NO es un hash del
  contenido del video. Limitación aceptada: dos archivos con la misma
  ruta, tamaño, mtime y duración no son distinguibles sin hash de
  contenido (no se intenta resolver en B4.3.1).
- Identidad y completitud están separadas: la carpeta de versión
  identifica a qué fingerprint pertenecen sus JPEGs, y la completitud se
  deriva de `objetivos - existentes`. Una versión parcial sigue siendo
  reconocible como tal y se puede **reanudar** sin repetir FFmpeg para
  los JPEGs ya terminados (cada JPEG se escribe atómicamente: temporal
  -> `os.replace`, así que un `f*.jpg` presente está completo).
- Una versión nunca utiliza ni lista JPEGs de otra; no se borra nada
  automáticamente (las versiones antiguas quedan para una limpieza
  futura, fuera de alcance). El `meta.json` solo se escribe cuando la
  generación de esa versión termina sin cancelarse y **completa**
  (`faltantes == 0`).
- FFmpeg: una invocación por fotograma (patrón `-ss` + `-frames:v 1`),
  reducción de resolución durante la extracción y escritura atómica.

Sin Qt, sin SQLite y sin acoplamiento con `escanear_videos`.
"""

import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import tempfile

from exploracion_temporal import (
    cantidad_fotogramas,
    duracion_valida,
    fotograma_mas_cercano,
    tiempos_objetivo,
)
from rutas import ruta_carpeta_exploracion

_ARGS_SIN_CONSOLA = (
    {"creationflags": subprocess.CREATE_NO_WINDOW}
    if os.name == "nt"
    else {}
)

NOMBRE_META = "meta.json"
EXTENSION_FOTOGRAMA = ".jpg"
PREFIJO_FOTOGRAMA = "f"
ALTURA_FOTOGRAMA = 120
TIEMPO_FPROBE_SEGUNDOS = 30
TIEMPO_FFMPEG_SEGUNDOS = 30
LONGITUD_VERSION = 16


def _validar_video_id(video_id):
    if isinstance(video_id, bool) or not isinstance(video_id, (str, int)):
        raise TypeError("video_id debe ser texto o entero")
    if str(video_id) == "":
        raise ValueError("video_id no puede estar vacío")


def video_id_desde_ruta(ruta):
    """Identificador de carpeta derivado de una ruta (sin hash).

    Conveniencia para uso independiente de la base de datos. Se construye
    a partir del nombre base saneado. Limitación documentada: dos rutas
    con el mismo nombre base colisionan; la integración real (B4.3.2)
    deberá pasar el `video_id` de la base de datos.
    """
    if not isinstance(ruta, str) or not ruta:
        raise ValueError("ruta debe ser texto no vacío")
    base = os.path.basename(os.path.abspath(ruta))
    nombre = os.path.splitext(base)[0]
    limpio = "".join(c if (c.isalnum() or c in "._-") else "_" for c in nombre)
    return limpio or "video"


def fingerprint_actual(ruta_video, duracion):
    """Metadatos baratos que identifican la versión (sin hash de contenido).

    Devuelve None si el archivo no se puede inspeccionar.
    """
    try:
        tamano = os.path.getsize(ruta_video)
        mtime_ns = os.stat(ruta_video).st_mtime_ns
    except OSError:
        return None
    return {
        "ruta": os.path.normcase(
            os.path.normpath(os.path.abspath(ruta_video))
        ),
        "tamano_bytes": tamano,
        "mtime_ns": mtime_ns,
        "duracion_segundos": (
            float(duracion) if duracion_valida(duracion) else None
        ),
    }


def version_id_de_fingerprint(fingerprint):
    """Nombre de carpeta de una versión: digest corto de sus metadatos.

    Costo: concatenar cuatro valores y un SHA-256 sobre ~100 bytes.
    No es un hash del contenido del video.
    """
    if not isinstance(fingerprint, dict):
        raise TypeError("fingerprint debe ser un dict")
    material = "|".join(
        str(fingerprint.get(clave))
        for clave in ("ruta", "tamano_bytes", "mtime_ns", "duracion_segundos")
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:LONGITUD_VERSION]


def version_actual(video_id, ruta_video, duracion, base=None):
    """Versión (nombre de carpeta) del fingerprint vigente del video.

    Solo consulta el sistema de archivos para `os.stat` (barato); no lee
    la caché. Devuelve None si el video no se puede inspeccionar.
    """
    fp = fingerprint_actual(ruta_video, duracion)
    if fp is None:
        return None
    return version_id_de_fingerprint(fp)


def ruta_carpeta_video_exploracion(video_id, base=None):
    _validar_video_id(video_id)
    if base is None:
        base = ruta_carpeta_exploracion()
    return os.path.join(base, str(video_id))


def ruta_carpeta_version(video_id, version, base=None):
    _validar_video_id(video_id)
    if not isinstance(version, str) or not version:
        raise ValueError("version debe ser texto no vacío")
    return os.path.join(
        ruta_carpeta_video_exploracion(video_id, base), version
    )


def ruta_carpeta_actual(video_id, ruta_video, duracion, base=None):
    """Carpeta de la versión actual (puede no existir todavía)."""
    version = version_actual(video_id, ruta_video, duracion, base)
    if version is None:
        raise ValueError(
            "no se pudo determinar la versión actual del video"
        )
    return ruta_carpeta_version(video_id, version, base)


def ruta_fotograma_version(video_id, ms, version, base=None):
    _validar_video_id(video_id)
    if isinstance(ms, bool) or not isinstance(ms, int):
        raise TypeError("ms debe ser un entero")
    if ms < 0:
        raise ValueError("ms no puede ser negativo")
    return os.path.join(
        ruta_carpeta_version(video_id, version, base),
        f"{PREFIJO_FOTOGRAMA}{ms:010d}{EXTENSION_FOTOGRAMA}",
    )


def ruta_meta_version(video_id, version, base=None):
    return os.path.join(
        ruta_carpeta_version(video_id, version, base), NOMBRE_META
    )


def leer_meta_version(video_id, version, base=None):
    ruta = ruta_meta_version(video_id, version, base)
    if not os.path.isfile(ruta):
        return None
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            datos = json.load(f)
    except (OSError, ValueError):
        return None
    return datos if isinstance(datos, dict) else None


def listar_fotogramas_version(video_id, version, base=None, duracion=None):
    """Milisegundos de los fotogramas existentes en una versión, ordenados.

    Si se pasa la `duracion`, solo se devuelven los que pertenecen al
    conjunto objetivo de esa duración (los sobrantes de otra densidad
    quedan en disco pero no se listan).
    """
    carpeta = ruta_carpeta_version(video_id, version, base)
    if not os.path.isdir(carpeta):
        return []
    resultado = []
    for nombre in os.listdir(carpeta):
        if (
            not nombre.startswith(PREFIJO_FOTOGRAMA)
            or not nombre.endswith(EXTENSION_FOTOGRAMA)
        ):
            continue
        cuerpo = nombre[len(PREFIJO_FOTOGRAMA):-len(EXTENSION_FOTOGRAMA)]
        if cuerpo.isdigit():
            resultado.append(int(cuerpo))
    if duracion is not None and duracion_valida(duracion):
        objetivo = set(
            tiempos_objetivo(duracion, cantidad_fotogramas(duracion))
        )
        resultado = [ms for ms in resultado if ms in objetivo]
    return sorted(resultado)


def _objetivos_vigentes(duracion, cantidad=None):
    if not duracion_valida(duracion):
        return []
    if cantidad is None:
        cantidad = cantidad_fotogramas(duracion)
    if isinstance(cantidad, bool) or not isinstance(cantidad, int) or cantidad <= 0:
        return []
    return tiempos_objetivo(duracion, cantidad)


def listar_fotogramas(video_id, ruta_video, duracion, base=None,
                      cantidad=None):
    """Fotogramas de la versión actual, restringidos al conjunto objetivo.

    El consumidor no gestiona versiones: esta función resuelve
    internamente la versión del fingerprint vigente.
    """
    version = version_actual(video_id, ruta_video, duracion, base)
    if version is None:
        return []
    objetivos = _objetivos_vigentes(duracion, cantidad)
    presentes = set(listar_fotogramas_version(video_id, version, base))
    return sorted(ms for ms in objetivos if ms in presentes)


def faltantes(video_id, ruta_video, duracion, base=None, cantidad=None):
    """Fotogramas objetivo aún no presentes en la versión actual."""
    version = version_actual(video_id, ruta_video, duracion, base)
    if version is None:
        return []
    objetivos = _objetivos_vigentes(duracion, cantidad)
    presentes = set(listar_fotogramas_version(video_id, version, base))
    return [ms for ms in objetivos if ms not in presentes]


def _escribir_bytes_atomicamente(ruta_destino, contenido):
    carpeta = os.path.dirname(ruta_destino)
    os.makedirs(carpeta, exist_ok=True)
    descriptor, ruta_temporal = tempfile.mkstemp(
        dir=carpeta, suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "wb") as f:
            f.write(contenido)
        os.replace(ruta_temporal, ruta_destino)
    except Exception:
        with contextlib.suppress(OSError):
            os.remove(ruta_temporal)
        raise


def _meta_coincide(meta, ruta_video, duracion):
    actual = fingerprint_actual(ruta_video, duracion)
    if actual is None or not isinstance(meta, dict):
        return False
    for clave, valor in actual.items():
        meta_valor = meta.get(clave)
        if clave == "ruta":
            if not isinstance(meta_valor, str):
                return False
            if os.path.normcase(os.path.normpath(meta_valor)) != valor:
                return False
        elif meta_valor != valor:
            return False
    return True


def cache_vigente(video_id, ruta_video, duracion, base=None):
    """True si la versión actual está completa (meta que coincide)."""
    version = version_actual(video_id, ruta_video, duracion, base)
    if version is None:
        return False
    return _meta_coincide(
        leer_meta_version(video_id, version, base), ruta_video, duracion
    )


def _escribir_meta(carpeta, video_id, ruta_video, duracion):
    fingerprint = fingerprint_actual(ruta_video, duracion)
    if fingerprint is None:
        return
    meta = {
        "video_id": str(video_id),
        "ruta": os.path.abspath(ruta_video),
        "tamano_bytes": fingerprint["tamano_bytes"],
        "mtime_ns": fingerprint["mtime_ns"],
        "duracion_segundos": fingerprint["duracion_segundos"],
    }
    contenido = json.dumps(meta, ensure_ascii=False, indent=2).encode("utf-8")
    _escribir_bytes_atomicamente(
        os.path.join(carpeta, NOMBRE_META), contenido
    )


def duracion_video(ruta_video, subprocess_run=None):
    """Duración en segundos vía ffprobe; None si no se puede obtener."""
    if subprocess_run is None:
        subprocess_run = subprocess.run
    try:
        resultado = subprocess_run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                ruta_video,
            ],
            capture_output=True,
            text=True,
            timeout=TIEMPO_FPROBE_SEGUNDOS,
            **_ARGS_SIN_CONSOLA,
        )
        if resultado.returncode != 0:
            return None
        valor = resultado.stdout.strip()
        if not valor:
            return None
        return float(valor)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def _extraer_fotograma(ruta_video, ms, ruta_destino, subprocess_run=None,
                       timeout=TIEMPO_FFMPEG_SEGUNDOS):
    """Una invocación de FFmpeg para extraer un fotograma.

    Patrón idéntico a `generar_preview` (`-ss` antes de `-i`,
    `-frames:v 1`, JPEG, sin ventana de consola, timeout) más la
    reducción de resolución durante la extracción. Devuelve True solo si
    el proceso termina con código 0 y el archivo destino existe.
    """
    if subprocess_run is None:
        subprocess_run = subprocess.run
    try:
        resultado = subprocess_run(
            [
                "ffmpeg", "-y", "-ss", f"{ms / 1000:.3f}",
                "-i", ruta_video,
                "-frames:v", "1", "-q:v", "3",
                "-vf", f"scale=-2:{ALTURA_FOTOGRAMA}",
                ruta_destino,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            **_ARGS_SIN_CONSOLA,
        )
        return resultado.returncode == 0 and os.path.isfile(ruta_destino)
    except (OSError, subprocess.SubprocessError):
        return False


def generar_fotogramas(video_id, ruta_video, duracion=None, cantidad=None,
                       on_progreso=None, cancelar=None, subprocess_run=None,
                       ruta_carpeta_base=None,
                       timeout=TIEMPO_FFMPEG_SEGUNDOS):
    """Genera o completa la caché densa de exploración de un video.

    - `duracion` (segundos): si no se pasa o es inválida, se consulta
      con ffprobe.
    - `cantidad`: si no se pasa, usa `cantidad_fotogramas(duracion)`.
    - Trabaja siempre sobre la carpeta de la **versión actual** (derivada
      del fingerprint barato). Los JPEGs ya presentes en esa versión se
      reutilizan aunque la versión esté incompleta: así una generación
      parcial se puede **reanudar** sin repetir FFmpeg (un `f*.jpg`
      presente está completo porque la escritura es atómica).
    - `cancelar`: callable sin argumentos que corta la generación de
      forma cooperativa entre fotogramas.
    - La escritura es atómica (temporal -> os.replace) tanto para los
      JPEGs como para `meta.json`.
    - `meta.json` de la versión solo se escribe si la generación termina
      sin cancelarse y **completa** (faltantes == 0); la completitud se
      deriva siempre de `objetivos - existentes`. No se borra ninguna
      versión.
    """
    _validar_video_id(video_id)
    if not isinstance(ruta_video, str) or not ruta_video:
        raise ValueError("ruta_video debe ser texto no vacío")
    if not os.path.isfile(ruta_video):
        raise FileNotFoundError(f"Video no encontrado: {ruta_video}")
    if on_progreso is not None and not callable(on_progreso):
        raise TypeError("on_progreso debe ser callable o None")
    if cancelar is None:
        cancelar = lambda: False
    if not callable(cancelar):
        raise TypeError("cancelar debe ser callable o None")

    if not duracion_valida(duracion):
        duracion = duracion_video(ruta_video, subprocess_run)
    if not duracion_valida(duracion):
        return {
            "video_id": str(video_id),
            "ruta_video": ruta_video,
            "duracion_segundos": None,
            "cantidad_objetivo": 0,
            "generados": 0,
            "reutilizados": 0,
            "errores": 0,
            "cancelado": False,
            "faltantes": 0,
            "version": None,
            "fotogramas": [],
        }
    if cantidad is None:
        cantidad = cantidad_fotogramas(duracion)
    if isinstance(cantidad, bool) or not isinstance(cantidad, int) or cantidad <= 0:
        cantidad = 0
    objetivos = _objetivos_vigentes(duracion, cantidad)
    version = version_actual(video_id, ruta_video, duracion, ruta_carpeta_base)
    if version is None:
        return {
            "video_id": str(video_id),
            "ruta_video": ruta_video,
            "duracion_segundos": duracion,
            "cantidad_objetivo": cantidad,
            "generados": 0,
            "reutilizados": 0,
            "errores": 0,
            "cancelado": False,
            "faltantes": 0,
            "version": None,
            "fotogramas": [],
        }
    carpeta = ruta_carpeta_version(video_id, version, ruta_carpeta_base)
    os.makedirs(carpeta, exist_ok=True)

    presentes = set(
        listar_fotogramas_version(video_id, version, ruta_carpeta_base)
    )
    total = len(objetivos)
    generados = 0
    reutilizados = 0
    errores = 0
    cancelado = False
    for indice, ms in enumerate(objetivos):
        if cancelar():
            cancelado = True
            break
        if ms in presentes:
            reutilizados += 1
            if on_progreso is not None:
                on_progreso(indice + 1, total)
            continue
        destino = ruta_fotograma_version(video_id, ms, version, ruta_carpeta_base)
        descriptor, ruta_temporal = tempfile.mkstemp(
            dir=carpeta, prefix="fotograma_", suffix=EXTENSION_FOTOGRAMA
        )
        os.close(descriptor)
        with contextlib.suppress(OSError):
            os.remove(ruta_temporal)
        if _extraer_fotograma(
            ruta_video, ms, ruta_temporal,
            subprocess_run=subprocess_run, timeout=timeout,
        ):
            try:
                os.replace(ruta_temporal, destino)
                generados += 1
            except OSError:
                errores += 1
                with contextlib.suppress(OSError):
                    os.remove(ruta_temporal)
        else:
            errores += 1
            with contextlib.suppress(OSError):
                os.remove(ruta_temporal)
        if on_progreso is not None:
            on_progreso(indice + 1, total)

    faltantes_restantes = total - generados - reutilizados
    if not cancelado and total > 0 and faltantes_restantes == 0:
        _escribir_meta(carpeta, video_id, ruta_video, duracion)

    presentes_finales = set(
        listar_fotogramas_version(video_id, version, ruta_carpeta_base)
    )
    fotogramas = sorted(ms for ms in objetivos if ms in presentes_finales)

    return {
        "video_id": str(video_id),
        "ruta_video": ruta_video,
        "duracion_segundos": duracion,
        "cantidad_objetivo": cantidad,
        "generados": generados,
        "reutilizados": reutilizados,
        "errores": errores,
        "cancelado": cancelado,
        "faltantes": faltantes_restantes,
        "version": version,
        "fotogramas": fotogramas,
    }


def fotograma_mas_cercano_en_cache(video_id, instante, ruta_video, duracion,
                                   base=None):
    """Milisegundo del fotograma de la versión actual más cercano a `instante`.

    Solo consulta la versión vigente; nunca fotogramas de otras versiones
    (ni sobrantes que no pertenezcan al conjunto objetivo).
    """
    version = version_actual(video_id, ruta_video, duracion, base)
    if version is None:
        return None
    return fotograma_mas_cercano(
        listar_fotogramas_version(video_id, version, base, duracion),
        instante,
    )


def ffmpeg_disponible():
    return shutil.which("ffmpeg") is not None
