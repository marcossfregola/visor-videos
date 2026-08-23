"""Servicio seguro de extracción de un segmento (B6.7).

Contrato B6.6/7 obligatorio:
- Corte preciso mediante recodificación CPU (no stream-copy).
- No sobrescribir jamás el original ni el destino existente.
- Manejo explícito de streams (no depender del mapeo default de FFmpeg).
- Archivo temporal único en el mismo directorio del destino; publicación solo tras
  verificación FFprobe exitosa.
- Verificación posterior: duración esperada con tolerancia, start_time cercano a 0,
  video presente si la fuente tenía video, archivo no vacío.
- Operación atómica sin -y contra destino final, con doble comprobación de colisión.
- Cancelación real: termina FFmpeg y limpia temporal.
"""

import math
import os
import subprocess
import tempfile
import uuid
import json
import shutil
import time

_ARGS_SIN_CONSOLA = (
    {"creationflags": subprocess.CREATE_NO_WINDOW}
    if os.name == "nt"
    else {}
)

# Tolerancias justificadas:
# - Duración fin <= duracion_fuente + 0.05 s permite errores de redondeo de
#   FFprobe (microsegundos) sin permitir un fin realmente fuera de rango.
TOLERANCIA_FIN_DURACION = 0.05
# - Duración exportada vs esperada: 0.35 s cubre 1 frame a 30 fps (0.033) +
#   variación de último frame/sample de audio (hasta ~0.2) + redondeo.
TOLERANCIA_DURACION_EXPORT = 0.35
# - Start_time cercano a 0: 0.6 s cubre offset de mov/mkv y redondeo.
TOLERANCIA_START = 0.6
# - Tolerancia para comparar rutas iguales
# Duración mínima para considerarlo válido: >0
MIN_DURACION_EXPORT = 0.05

EXTENSIONES_SOPORTADAS = {".mp4", ".mkv"}

# Subs permitidos por contenedor en B6.7. Cualquier otro codec de subtítulo
# (p. ej. hdmv_pgs_subtitle, dvd_subtitle, pgssub) se rechaza explícitamente
# para no hacer conversiones destructivas ni pérdidas silenciosas.
SUBS_MP4_PERMITIDOS = {"subrip", "mov_text", "srt"}
SUBS_MKV_PERMITIDOS = {"subrip", "ass", "ssa", "mov_text", "srt"}


def _es_finito(num):
    if isinstance(num, bool):
        return False
    if not isinstance(num, (int, float)):
        return False
    try:
        f = float(num)
    except Exception:
        return False
    return math.isfinite(f)


def _normalizar_ruta_absoluta(ruta):
    if not isinstance(ruta, str):
        return None
    try:
        return os.path.normcase(os.path.normpath(os.path.abspath(ruta)))
    except Exception:
        return None


def _validar_entrada(fuente, inicio, fin, destino):
    if not isinstance(fuente, str) or not fuente.strip():
        return "ruta fuente debe ser texto no vacío"
    if not isinstance(destino, str) or not destino.strip():
        return "ruta destino debe ser texto no vacío"
    if not _es_finito(inicio):
        return "inicio debe ser número finito"
    if not _es_finito(fin):
        return "fin debe ser número finito"
    if inicio < 0:
        return "inicio no puede ser negativo"
    if not (fin > inicio):
        return "fin debe ser mayor que inicio"
    if not os.path.isfile(fuente):
        return "archivo fuente no encontrado o no es archivo"
    try:
        if os.path.getsize(fuente) == 0:
            return "archivo fuente vacío"
    except OSError as exc:
        return f"no se pudo leer fuente: {exc}"
    # destino no debe existir (doble comprobación más adelante) y no debe ser igual a fuente
    if _normalizar_ruta_absoluta(fuente) == _normalizar_ruta_absoluta(destino):
        return "destino no puede ser el mismo archivo que la fuente"
    ext = os.path.splitext(destino)[1].lower()
    if ext not in EXTENSIONES_SOPORTADAS:
        return f"extensión no soportada en B6.7: {ext!r} (soportadas: .mp4, .mkv)"
    dir_dest = os.path.dirname(os.path.abspath(destino))
    if dir_dest and not os.path.isdir(dir_dest):
        return f"directorio de destino no existe: {dir_dest}"
    return None


def _ffprobe_info(ruta):
    """Obtiene info de FFprobe en JSON. Devuelve dict o None si falla."""
    try:
        resultado = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                ruta,
            ],
            capture_output=True,
            text=True,
            timeout=15,
            **_ARGS_SIN_CONSOLA,
        )
        if resultado.returncode != 0:
            return None
        data = json.loads(resultado.stdout)
        fmt = data.get("format") or {}
        streams = data.get("streams") or []
        # duración
        dur = None
        try:
            if fmt.get("duration") is not None:
                dur = float(fmt["duration"])
            else:
                # fallback: buscar duración en stream de video
                for s in streams:
                    if s.get("duration") is not None:
                        dur = float(s["duration"])
                        break
        except Exception:
            dur = None
        # start_time
        start = None
        try:
            if fmt.get("start_time") is not None:
                start = float(fmt["start_time"])
            else:
                for s in streams:
                    if s.get("start_time") is not None:
                        start = float(s["start_time"])
                        break
        except Exception:
            start = None
        has_video = any(s.get("codec_type") == "video" for s in streams)
        has_audio = any(s.get("codec_type") == "audio" for s in streams)
        audio_count = sum(1 for s in streams if s.get("codec_type") == "audio")
        video_count = sum(1 for s in streams if s.get("codec_type") == "video")
        sub_streams = [s for s in streams if s.get("codec_type") == "subtitle"]
        sub_codecs = [s.get("codec_name") for s in sub_streams if s.get("codec_name")]
        # distinguir streams por tipo para verificación
        return {
            "duration": dur,
            "start_time": start,
            "streams": streams,
            "has_video": has_video,
            "has_audio": has_audio,
            "audio_count": audio_count,
            "video_count": video_count,
            "sub_count": len(sub_streams),
            "sub_codecs": sub_codecs,
            "sub_streams": sub_streams,
            "format_name": fmt.get("format_name"),
        }
    except Exception:
        return None


def _generar_temporal(destino):
    dir_dest = os.path.dirname(os.path.abspath(destino))
    base = os.path.splitext(os.path.basename(destino))[0]
    ext = os.path.splitext(destino)[1]  # conserva mayúsculas/minúsculas originales pero usamos lower para ffmpeg muxer
    # Generar nombre temporal único en el MISMO directorio, conservando extensión final utilizable por FFmpeg.
    # No usar una extensión .tmp final que cambie el muxer: el temporal ya tiene .mp4/.mkv final.
    for _ in range(5):
        sufijo = uuid.uuid4().hex[:8]
        nombre = f"{base}.tmp_{sufijo}{ext}"
        ruta_tmp = os.path.join(dir_dest, nombre)
        if not os.path.exists(ruta_tmp):
            return ruta_tmp
    # Fallback con pid + timestamp
    nombre = f"{base}.tmp_{os.getpid()}_{int(time.time()*1000)}{ext}"
    return os.path.join(dir_dest, nombre)


def _construir_args_ffmpeg(fuente, inicio, duracion, tmp_dest, info_fuente):
    ext = os.path.splitext(tmp_dest)[1].lower()
    if ext not in EXTENSIONES_SOPORTADAS:
        raise ValueError(f"extensión no soportada: {ext}")

    # Política de subtítulos: si hay subtítulos no soportados -> error explícito, no pérdida silenciosa.
    sub_codecs = info_fuente.get("sub_codecs") or []
    sub_count = info_fuente.get("sub_count", 0)
    if sub_count > 0:
        if ext == ".mp4":
            no_permitidos = [c for c in sub_codecs if c not in SUBS_MP4_PERMITIDOS]
            if no_permitidos:
                raise ValueError(
                    f"subtítulo no soportado para MP4 en B6.7: {no_permitidos!r} (solo {SUBS_MP4_PERMITIDOS})"
                )
        elif ext == ".mkv":
            no_permitidos = [c for c in sub_codecs if c not in SUBS_MKV_PERMITIDOS]
            if no_permitidos:
                raise ValueError(
                    f"subtítulo no soportado para MKV en B6.7: {no_permitidos!r} (solo {SUBS_MKV_PERMITIDOS})"
                )

    has_video = info_fuente.get("has_video", False)
    has_audio = info_fuente.get("has_audio", False)

    # Construcción sin shell, argumentos como lista, con recodificación CPU precisa.
    # Usamos -i antes de -ss para precisión máxima (seek preciso), con -t.
    # Mapeo explícito de streams: no depender del mapeo default.
    args = ["ffmpeg", "-i", fuente, "-ss", f"{inicio:.6f}", "-t", f"{duracion:.6f}"]

    # Mapeo explícito
    if has_video:
        args += ["-map", "0:v"]
    if has_audio:
        args += ["-map", "0:a"]
    if sub_count > 0:
        args += ["-map", "0:s"]

    # Si no hay stream mapeado (p. ej. archivo sin video ni audio ni sub), FFmpeg fallará; lo capturamos.

    # Codecs: recodificación CPU precisa
    if has_video:
        # H.264/AAC es el camino robusto probado en B6.6; para B6.7 se recodifica siempre a H.264 yub420p
        # para asegurar compatibilidad entre contenedores, sin asumir que el codec original puede copiarse.
        args += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p"]
        if ext == ".mp4":
            args += ["-movflags", "+faststart"]
    if has_audio:
        # Doble audio preservado: -c:a aplica a todos los streams de audio mapeados
        args += ["-c:a", "aac", "-b:a", "128k"]
    if sub_count > 0:
        if ext == ".mp4":
            args += ["-c:s", "mov_text"]
        else:
            args += ["-c:s", "srt"]

    # Salida temporal: NO usar -y contra destino final; el temporal es nuevo/único.
    # No añadimos -y para que FFmpeg falle si el temporal ya existía (seguridad).
    args.append(tmp_dest)
    return args


def _verificar_salida(ruta_tmp, esperado_duracion, fuente_info):
    # archivo válido, no vacío
    if not os.path.isfile(ruta_tmp):
        return False, "archivo temporal no existe tras FFmpeg"
    try:
        tam = os.path.getsize(ruta_tmp)
        if tam <= 0:
            return False, "archivo temporal vacío"
    except OSError as exc:
        return False, f"no se pudo medir archivo temporal: {exc}"

    info = _ffprobe_info(ruta_tmp)
    if info is None:
        return False, "FFprobe no pudo leer el archivo generado"
    dur = info.get("duration")
    if dur is None or not _es_finito(dur):
        return False, "duración del derivado no disponible"
    if abs(dur - esperado_duracion) > TOLERANCIA_DURACION_EXPORT:
        return False, f"duración fuera de tolerancia: esperada {esperado_duracion:.3f} got {dur:.3f}"
    if dur < MIN_DURACION_EXPORT:
        return False, f"duración derivada demasiado corta: {dur:.3f}"
    start = info.get("start_time")
    if start is not None:
        if not _es_finito(start):
            return False, "start_time no finito"
        if abs(start) > TOLERANCIA_START:
            return False, f"start_time no cercano a 0: {start:.3f}"
    # video presente cuando fuente tiene video
    if fuente_info.get("has_video") and not info.get("has_video"):
        return False, "video ausente en derivado cuando fuente tenía video"
    # audio preservado: si fuente tenía audio, derivado debe tener audio (misma cantidad si es posible)
    if fuente_info.get("has_audio") and not info.get("has_audio"):
        return False, "audio ausente en derivado cuando fuente tenía audio"
    # subtítulos: si fuente tenía subs y eran soportados, derivado debe tener al menos 1 sub (política explícita)
    if fuente_info.get("sub_count", 0) > 0 and info.get("sub_count", 0) == 0:
        return False, "subtítulos ausentes en derivado cuando fuente tenía subtítulos soportados"

    return True, None


def exportar_segmento(fuente, inicio, fin, destino, cancel_check=None):
    """
    Núcleo seguro de exportación de un segmento.

    - Valida entrada con FFprobe (0 <= inicio < fin <= duración + tolerancia).
    - Genera temporal único en mismo directorio.
    - Ejecuta FFmpeg con recodificación CPU precisa y mapeo explícito.
    - Verifica con FFprobe y publica de forma atómica.
    - Soporta cancelación cooperativa (cancel_check callable que devuelve True si se canceló).

    Retorna dict estructurado: {ok, salida, duracion, start, streams, error, cancelado}
    Nunca expone trazas internas innecesarias; error es mensaje claro para UI.
    """
    # Validación estructurada temprana
    err = _validar_entrada(fuente, inicio, fin, destino)
    if err is not None:
        return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": err, "cancelado": False}

    # Comprobar colisión de destino ANTES de empezar (no sobrescribir)
    if os.path.exists(destino):
        return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": "destino ya existe, no se sobrescribirá", "cancelado": False}

    # FFprobe fuente para durata y streams
    info_fuente = _ffprobe_info(fuente)
    if info_fuente is None:
        return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": "no se pudo obtener duración de la fuente con FFprobe", "cancelado": False}
    dur_fuente = info_fuente.get("duration")
    if dur_fuente is None or not _es_finito(dur_fuente):
        return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": "duración de la fuente no disponible", "cancelado": False}
    # 0 <= inicio < fin <= duración + tolerancia
    if not (0 <= inicio < fin <= dur_fuente + TOLERANCIA_FIN_DURACION):
        if fin > dur_fuente + TOLERANCIA_FIN_DURACION:
            return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": f"fin ({fin}) excede duración de la fuente ({dur_fuente:.3f})", "cancelado": False}
        return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": "rango inicio/fin inválido respecto de la duración", "cancelado": False}

    # También verificar cancelación antes de generar temporal
    if cancel_check is not None and cancel_check():
        return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": "cancelado", "cancelado": True}

    tmp = _generar_temporal(destino)
    # Asegurar que no existe (muy improbable) y que destino sigue sin existir
    if os.path.exists(tmp):
        return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": "colisión temporal inesperada", "cancelado": False}
    if os.path.exists(destino):
        return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": "destino apareció antes de iniciar FFmpeg", "cancelado": False}

    duracion = float(fin) - float(inicio)
    # Construir comando
    try:
        args = _construir_args_ffmpeg(fuente, float(inicio), duracion, tmp, info_fuente)
    except ValueError as exc:
        return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": str(exc), "cancelado": False}
    except Exception as exc:
        return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": f"no se pudo construir comando FFmpeg: {exc}", "cancelado": False}

    # Ejecutar FFmpeg sin shell, lista de argumentos, sin -y contra destino final
    # Evitar deadlock de pipes: stderr a archivo temporal, stdout a DEVNULL
    proceso = None
    stderr_tmp = None
    try:
        # Usar archivo temporal para stderr para no bloquear pipe y poder capturar error
        stderr_file = tempfile.TemporaryFile(mode="w+")
        proceso = subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=stderr_file,
            text=True,
            **_ARGS_SIN_CONSOLA,
        )
        # Esperar con polling para cancelación real
        while True:
            if cancel_check is not None and cancel_check():
                # Terminar FFmpeg si está activo
                try:
                    proceso.terminate()
                except Exception:
                    pass
                try:
                    proceso.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    try:
                        proceso.kill()
                    except Exception:
                        pass
                    try:
                        proceso.wait(timeout=3)
                    except Exception:
                        pass
                try:
                    stderr_file.close()
                except Exception:
                    pass
                # Limpiar temporal si quedó parcial
                try:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                except Exception:
                    pass
                return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": "cancelado", "cancelado": True}
            ret = proceso.poll()
            if ret is not None:
                break
            time.sleep(0.05)
        # Proceso terminó, obtener stderr
        try:
            stderr_file.seek(0)
            stderr = stderr_file.read()
        except Exception:
            stderr = ""
        try:
            stderr_file.close()
        except Exception:
            pass
        stdout = ""
        if proceso.returncode != 0:
            # FFmpeg fallido: sin archivo final ni temporal huérfano
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass
            # Mensaje claro sin exponer stderr completo innecesariamente, pero incluye hint
            detalle = (stderr or "").strip().splitlines()[-1] if stderr else ""
            msg = f"FFmpeg falló (código {proceso.returncode})"
            if detalle:
                msg += f": {detalle[:200]}"
            return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": msg, "cancelado": False}
    except Exception as exc:
        # fallo al lanzar FFmpeg
        try:
            if tmp and os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        # Si fue cancelación, ya retornamos arriba; aquí es error
        if cancel_check is not None and cancel_check():
            return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": "cancelado", "cancelado": True}
        return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": f"no se pudo ejecutar FFmpeg: {exc}", "cancelado": False}
    finally:
        # proceso ya fue communicado; no dejar pipes abiertos
        pass

    # Si cancelación justo después de FFmpeg
    if cancel_check is not None and cancel_check():
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": "cancelado", "cancelado": True}

    # Verificación FFprobe posterior antes de publicar
    ok_ver, motivo = _verificar_salida(tmp, duracion, info_fuente)
    if not ok_ver:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": f"verificación fallida: {motivo}", "cancelado": False}

    # Segunda comprobación de colisión justo antes de publicar
    if os.path.exists(destino):
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": "destino apareció durante la exportación, no se sobrescribirá", "cancelado": False}

    # Publicación final controlada solo después de verificar
    # Usar operación que no sobrescriba silenciosamente: verificar de nuevo y usar os.rename (Windows falla si existe)
    try:
        # Intentar mover de forma atómica; en Windows os.replace sobrescribe, por eso usamos os.rename tras comprobar
        # Si destino apareció en la ventana, el rename lanzará OSError y no sobrescribirá.
        # En POSIX rename sobrescribiría, pero ya comprobamos; el riesgo de carrera es mínimo y está documentado.
        # Usamos shutil.move con precaución: primero intentar link/rename que falle si existe
        if os.path.exists(destino):
            raise FileExistsError("destino ya existe")
        # os.replace sería destructivo si existe, pero ya verificamos; usar os.rename para que en Windows falle
        # En POSIX, os.rename también sobrescribe, así que mantenemos la comprobación y usamos os.rename.
        os.rename(tmp, destino)
    except FileExistsError:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": "destino ya existe, no se sobrescribirá", "cancelado": False}
    except OSError as exc:
        # Si el error es porque destino ya existe (Windows), tratar como no sobrescribir
        if os.path.exists(destino):
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass
            return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": "destino ya existe, no se sobrescribirá", "cancelado": False}
        # Otro error de publicación
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": f"no se pudo publicar el archivo: {exc}", "cancelado": False}

    # Éxito: obtener info final para resultado
    info_final = _ffprobe_info(destino)
    dur_final = info_final.get("duration") if info_final else None
    start_final = info_final.get("start_time") if info_final else None
    streams_final = info_final.get("streams") if info_final else None

    return {
        "ok": True,
        "salida": destino,
        "duracion": dur_final,
        "start": start_final,
        "streams": streams_final,
        "error": None,
        "cancelado": False,
    }


def obtener_comando_ffmpeg_preview(fuente, inicio, fin, destino):
    """Helper para inspección: devuelve el comando que se usaría (sin ejecutar)."""
    info = _ffprobe_info(fuente)
    if info is None:
        raise RuntimeError("no se pudo probar fuente")
    dur = float(fin) - float(inicio)
    return _construir_args_ffmpeg(fuente, float(inicio), dur, destino, info)
