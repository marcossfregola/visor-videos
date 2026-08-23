"""Servicio de unión de varios segmentos del mismo original (B6.10).

Contrato:
- N>=2 segmentos del MISMO archivo origen -> un único derivado.
- Vía principal sin subtítulos: FFmpeg trim/atrim/setpts+concat con recodificación CPU
  (libx264 velmi fast crf 18 yuv420p + aac 128k), preservando 0/1/2 audios.
- Subtítulos compatibles: fallback por extracción precisa de cada segmento + concat/mapeo explícito.
- MKV/SubRip no validado: rechazo claro (no pérdida silenciosa).
- FFprobe antes de publicar, no overwrite (doble comprobación), temporales únicos en mismo directorio,
  limpieza y cancelación real.

No implementa B6.11 (incorporación al catálogo).
"""

import math
import os
import subprocess
import tempfile
import uuid
import json
import time

import exportar_segmento as exp

_ARGS_SIN_CONSOLA = (
    {"creationflags": subprocess.CREATE_NO_WINDOW}
    if os.name == "nt"
    else {}
)

TOLERANCIA_FIN_DURACION = exp.TOLERANCIA_FIN_DURACION
TOLERANCIA_DURACION_EXPORT = exp.TOLERANCIA_DURACION_EXPORT
TOLERANCIA_START = exp.TOLERANCIA_START
MIN_DURACION_EXPORT = exp.MIN_DURACION_EXPORT
EXTENSIONES_SOPORTADAS = exp.EXTENSIONES_SOPORTADAS
SUBS_MP4_PERMITIDOS = exp.SUBS_MP4_PERMITIDOS
SUBS_MKV_PERMITIDOS = exp.SUBS_MKV_PERMITIDOS


def _es_finito(num):
    return exp._es_finito(num)


def _normalizar_ruta_absoluta(ruta):
    return exp._normalizar_ruta_absoluta(ruta)


def _validar_segmentos(segmentos):
    if not isinstance(segmentos, (list, tuple)):
        return "segmentos debe ser lista de (inicio, fin)"
    if len(segmentos) < 2:
        return "se requieren al menos 2 segmentos para secuencia"
    for idx, seg in enumerate(segmentos):
        if not isinstance(seg, (list, tuple)) or len(seg) != 2:
            return f"segmento {idx} debe ser (inicio, fin)"
        ini, fin = seg[0], seg[1]
        if not _es_finito(ini):
            return f"segmento {idx} inicio no finito"
        if not _es_finito(fin):
            return f"segmento {idx} fin no finito"
        if ini < 0:
            return f"segmento {idx} inicio negativo"
        if not (fin > ini):
            return f"segmento {idx} fin debe ser mayor que inicio"
        if (fin - ini) < MIN_DURACION_EXPORT:
            return f"segmento {idx} duración demasiado corta"
    return None


def _validar_entrada(fuente, segmentos, destino):
    if not isinstance(fuente, str) or not fuente.strip():
        return "ruta fuente debe ser texto no vacío"
    if not isinstance(destino, str) or not destino.strip():
        return "ruta destino debe ser texto no vacío"
    err = _validar_segmentos(segmentos)
    if err:
        return err
    if not os.path.isfile(fuente):
        return "archivo fuente no encontrado o no es archivo"
    try:
        if os.path.getsize(fuente) == 0:
            return "archivo fuente vacío"
    except OSError as exc:
        return f"no se pudo leer fuente: {exc}"
    if _normalizar_ruta_absoluta(fuente) == _normalizar_ruta_absoluta(destino):
        return "destino no puede ser el mismo archivo que la fuente"
    ext = os.path.splitext(destino)[1].lower()
    if ext not in EXTENSIONES_SOPORTADAS:
        return f"extensión no soportada en B6.10: {ext!r} (soportadas: .mp4, .mkv)"
    dir_dest = os.path.dirname(os.path.abspath(destino))
    if dir_dest and not os.path.isdir(dir_dest):
        return f"directorio de destino no existe: {dir_dest}"
    return None


def _ffprobe_info(ruta):
    return exp._ffprobe_info(ruta)


def _generar_temporal(destino):
    return exp._generar_temporal(destino)


def _generar_temporal_parte(destino, idx):
    dir_dest = os.path.dirname(os.path.abspath(destino))
    base = os.path.splitext(os.path.basename(destino))[0]
    ext = os.path.splitext(destino)[1]
    for _ in range(5):
        sufijo = uuid.uuid4().hex[:8]
        nombre = f"{base}.tmp_seq_{sufijo}_part{idx}{ext}"
        ruta_tmp = os.path.join(dir_dest, nombre)
        if not os.path.exists(ruta_tmp):
            return ruta_tmp
    nombre = f"{base}.tmp_seq_{os.getpid()}_{int(time.time()*1000)}_part{idx}{ext}"
    return os.path.join(dir_dest, nombre)


def _construir_args_concat_sin_subs(fuente, segmentos, tmp_dest, info_fuente):
    # Validar política MKV/SubRip antes de construir
    ext = os.path.splitext(tmp_dest)[1].lower()
    has_video = info_fuente.get("has_video", False)
    has_audio = info_fuente.get("has_audio", False)
    audio_count = info_fuente.get("audio_count", 0)
    sub_count = info_fuente.get("sub_count", 0)
    sub_codecs = info_fuente.get("sub_codecs") or []
    # Rechazo MKV/SubRip no validado: si hay subrip/srt y contenedor MKV
    # (fuente o destino mkv) -> rechazo claro
    if sub_count > 0:
        # Política B6.10: MKV con SubRip no validado se rechaza siempre
        # para evitar pérdida silenciosa
        ext_fuente = os.path.splitext(fuente)[1].lower()
        if ext == ".mkv" or ext_fuente == ".mkv":
            if any(c in ("subrip", "srt") for c in sub_codecs):
                raise ValueError("MKV/SubRip no validado en B6.10: rechazo claro (no se garantiza conversión)")
        # Otros codecs no permitidos también rechazo
        if ext == ".mp4":
            no_perm = [c for c in sub_codecs if c not in SUBS_MP4_PERMITIDOS]
            if no_perm:
                raise ValueError(f"subtítulo no soportado para MP4 en B6.10: {no_perm!r}")
        else:
            no_perm = [c for c in sub_codecs if c not in SUBS_MKV_PERMITIDOS]
            if no_perm:
                raise ValueError(f"subtítulo no soportado para MKV en B6.10: {no_perm!r}")
        # Si hay subtítulos compatibles pero estamos en vía principal sin subs,
        # el caller debe usar fallback, no esta función
        raise ValueError("vía principal sin subtítulos no soporta fuente con subtítulos, use fallback")

    if not has_video:
        raise ValueError("fuente sin video no soportada para secuencia B6.10")

    n = len(segmentos)
    # Limitar audio a 2 máximo para preservar según investigación
    if audio_count > 2:
        audio_count = 2

    filter_parts = []
    concat_inputs = []
    for i, (ini, fin) in enumerate(segmentos):
        # trim precisa con recodificación, start/end en segundos
        filter_parts.append(f"[0:v]trim=start={float(ini):.6f}:end={float(fin):.6f},setpts=PTS-STARTPTS[v{i}]")
        concat_inputs.append(f"[v{i}]")
        if has_audio:
            if audio_count == 1:
                filter_parts.append(f"[0:a]atrim=start={float(ini):.6f}:end={float(fin):.6f},asetpts=PTS-STARTPTS[a{i}]")
                concat_inputs.append(f"[a{i}]")
            elif audio_count == 2:
                filter_parts.append(f"[0:a:0]atrim=start={float(ini):.6f}:end={float(fin):.6f},asetpts=PTS-STARTPTS[a{i}_0]")
                filter_parts.append(f"[0:a:1]atrim=start={float(ini):.6f}:end={float(fin):.6f},asetpts=PTS-STARTPTS[a{i}_1]")
                concat_inputs.append(f"[a{i}_0]")
                concat_inputs.append(f"[a{i}_1]")

    if has_video and has_audio:
        if audio_count == 1:
            concat_filter = f"{''.join(concat_inputs)}concat=n={n}:v=1:a=1[vcat][acat]"
            filter_complex = ";".join(filter_parts) + ";" + concat_filter
            args = ["ffmpeg", "-i", fuente, "-filter_complex", filter_complex,
                    "-map", "[vcat]", "-map", "[acat]"]
        else:  # 2
            concat_filter = f"{''.join(concat_inputs)}concat=n={n}:v=1:a=2[vcat][acat0][acat1]"
            filter_complex = ";".join(filter_parts) + ";" + concat_filter
            args = ["ffmpeg", "-i", fuente, "-filter_complex", filter_complex,
                    "-map", "[vcat]", "-map", "[acat0]", "-map", "[acat1]"]
    elif has_video:
        concat_filter = f"{''.join(concat_inputs)}concat=n={n}:v=1:a=0[vcat]"
        filter_complex = ";".join(filter_parts) + ";" + concat_filter
        args = ["ffmpeg", "-i", fuente, "-filter_complex", filter_complex,
                "-map", "[vcat]"]
    else:
        # Solo audio (raro)
        if audio_count == 1:
            concat_filter = f"{''.join(concat_inputs)}concat=n={n}:v=0:a=1[acat]"
            filter_complex = ";".join(filter_parts) + ";" + concat_filter
            args = ["ffmpeg", "-i", fuente, "-filter_complex", filter_complex,
                    "-map", "[acat]"]
        else:
            concat_filter = f"{''.join(concat_inputs)}concat=n={n}:v=0:a=2[acat0][acat1]"
            filter_complex = ";".join(filter_parts) + ";" + concat_filter
            args = ["ffmpeg", "-i", fuente, "-filter_complex", filter_complex,
                    "-map", "[acat0]", "-map", "[acat1]"]

    # Codecs recodificación CPU precisa
    if has_video:
        args += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p"]
        if ext == ".mp4":
            args += ["-movflags", "+faststart"]
    if has_audio:
        args += ["-c:a", "aac", "-b:a", "128k"]
    args.append(tmp_dest)
    return args


def _verificar_salida(ruta_tmp, esperado_duracion, fuente_info):
    # Reutiliza lógica de exportar_segmento pero con duración suma
    return exp._verificar_salida(ruta_tmp, esperado_duracion, fuente_info)


def _ejecutar_ffmpeg(args, tmp_dest, cancelar_check=None):
    proceso = None
    stderr_tmp = None
    try:
        stderr_file = tempfile.TemporaryFile(mode="w+")
        proceso = subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=stderr_file,
            text=True,
            **_ARGS_SIN_CONSOLA,
        )
        while True:
            if cancelar_check is not None and cancelar_check():
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
                try:
                    if os.path.exists(tmp_dest):
                        os.remove(tmp_dest)
                except Exception:
                    pass
                return False, "cancelado", True
            ret = proceso.poll()
            if ret is not None:
                break
            time.sleep(0.05)
        try:
            stderr_file.seek(0)
            stderr = stderr_file.read()
        except Exception:
            stderr = ""
        try:
            stderr_file.close()
        except Exception:
            pass
        if proceso.returncode != 0:
            try:
                if os.path.exists(tmp_dest):
                    os.remove(tmp_dest)
            except Exception:
                pass
            detalle = (stderr or "").strip().splitlines()[-1] if stderr else ""
            msg = f"FFmpeg falló (código {proceso.returncode})"
            if detalle:
                msg += f": {detalle[:200]}"
            return False, msg, False
        return True, None, False
    except Exception as exc:
        try:
            if tmp_dest and os.path.exists(tmp_dest):
                os.remove(tmp_dest)
        except Exception:
            pass
        if cancelar_check is not None and cancelar_check():
            return False, "cancelado", True
        return False, f"no se pudo ejecutar FFmpeg: {exc}", False


def exportar_secuencia(fuente, segmentos, destino, cancel_check=None):
    """
    Une N>=2 segmentos del MISMO origen en un único derivado.
    segmentos: lista de (inicio, fin) en el orden explícito deseado.
    Retorna dict {ok, salida, duracion, start, streams, error, cancelado}
    """
    err = _validar_entrada(fuente, segmentos, destino)
    if err is not None:
        return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": err, "cancelado": False}
    if os.path.exists(destino):
        return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": "destino ya existe, no se sobrescribirá", "cancelado": False}

    info_fuente = _ffprobe_info(fuente)
    if info_fuente is None:
        return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": "no se pudo obtener duración de la fuente con FFprobe", "cancelado": False}
    dur_fuente = info_fuente.get("duration")
    if dur_fuente is None or not _es_finito(dur_fuente):
        return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": "duración de la fuente no disponible", "cancelado": False}
    # Validar cada fin <= duración + tolerancia
    for idx, (ini, fin) in enumerate(segmentos):
        if not (0 <= ini < fin <= dur_fuente + TOLERANCIA_FIN_DURACION):
            if fin > dur_fuente + TOLERANCIA_FIN_DURACION:
                return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": f"segmento {idx} fin ({fin}) excede duración de la fuente ({dur_fuente:.3f})", "cancelado": False}
            return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": f"segmento {idx} rango inicio/fin inválido respecto de la duración", "cancelado": False}

    if cancel_check is not None and cancel_check():
        return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": "cancelado", "cancelado": True}

    tmp = _generar_temporal(destino)
    if os.path.exists(tmp):
        return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": "colisión temporal inesperada", "cancelado": False}
    if os.path.exists(destino):
        return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": "destino apareció antes de iniciar FFmpeg", "cancelado": False}

    duracion_total = sum(float(fin) - float(ini) for ini, fin in segmentos)

    sub_count = info_fuente.get("sub_count", 0)
    sub_codecs = info_fuente.get("sub_codecs") or []
    ext_dest = os.path.splitext(tmp)[1].lower()
    ext_fuente = os.path.splitext(fuente)[1].lower()

    # Rechazo MKV/SubRip no validado antes de cualquier FFmpeg
    if sub_count > 0:
        # MKV con subrip/srt -> rechazo claro
        if ext_dest == ".mkv" or ext_fuente == ".mkv":
            if any(c in ("subrip", "srt") for c in sub_codecs):
                return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": "MKV/SubRip no validado en B6.10: rechazo claro", "cancelado": False}
        # Codecs no soportados también rechazo
        if ext_dest == ".mp4":
            no_perm = [c for c in sub_codecs if c not in SUBS_MP4_PERMITIDOS]
            if no_perm:
                return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": f"subtítulo no soportado para MP4 en B6.10: {no_perm!r}", "cancelado": False}
        else:
            no_perm = [c for c in sub_codecs if c not in SUBS_MKV_PERMITIDOS]
            if no_perm:
                return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": f"subtítulo no soportado para MKV en B6.10: {no_perm!r}", "cancelado": False}

    # Decidir vía
    fallback_subs = sub_count > 0

    if not fallback_subs:
        # Vía principal sin subtítulos: trim/atrim + concat con recodificación
        try:
            args = _construir_args_concat_sin_subs(fuente, segmentos, tmp, info_fuente)
        except ValueError as exc:
            return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": str(exc), "cancelado": False}
        except Exception as exc:
            return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": f"no se pudo construir comando FFmpeg: {exc}", "cancelado": False}

        ok_exec, msg, fue_cancel = _ejecutar_ffmpeg(args, tmp, cancel_check)
        if fue_cancel:
            return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": "cancelado", "cancelado": True}
        if not ok_exec:
            return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": msg, "cancelado": False}

        if cancel_check is not None and cancel_check():
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass
            return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": "cancelado", "cancelado": True}

        ok_ver, motivo = _verificar_salida(tmp, duracion_total, info_fuente)
        if not ok_ver:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass
            return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": f"verificación fallida: {motivo}", "cancelado": False}

        if os.path.exists(destino):
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass
            return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": "destino apareció durante la exportación, no se sobrescribirá", "cancelado": False}
        try:
            if os.path.exists(destino):
                raise FileExistsError("destino ya existe")
            os.rename(tmp, destino)
        except FileExistsError:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass
            return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": "destino ya existe, no se sobrescribirá", "cancelado": False}
        except OSError as exc:
            if os.path.exists(destino):
                try:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                except Exception:
                    pass
                return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": "destino ya existe, no se sobrescribirá", "cancelado": False}
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass
            return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": f"no se pudo publicar el archivo: {exc}", "cancelado": False}

        info_final = _ffprobe_info(destino)
        dur_final = info_final.get("duration") if info_final else None
        start_final = info_final.get("start_time") if info_final else None
        streams_final = info_final.get("streams") if info_final else None
        return {"ok": True, "salida": destino, "duracion": dur_final, "start": start_final, "streams": streams_final, "error": None, "cancelado": False}

    else:
        # Fallback con subtítulos compatibles: extracción precisa + concat/mapeo explícito
        # Paso 1: extraer cada segmento a temporal con recodificación precisa (incluyendo subs)
        partes = []
        try:
            for idx, (ini, fin) in enumerate(segmentos):
                if cancel_check is not None and cancel_check():
                    # limpiar partes ya creadas
                    for p in partes:
                        try:
                            if os.path.exists(p):
                                os.remove(p)
                        except Exception:
                            pass
                    try:
                        if os.path.exists(tmp):
                            os.remove(tmp)
                    except Exception:
                        pass
                    return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": "cancelado", "cancelado": True}
                part_tmp = _generar_temporal_parte(destino, idx)
                partes.append(part_tmp)
                dur = float(fin) - float(ini)
                try:
                    args_part = exp._construir_args_ffmpeg(fuente, float(ini), dur, part_tmp, info_fuente)
                except ValueError as exc:
                    # limpiar
                    for p in partes:
                        try:
                            if os.path.exists(p):
                                os.remove(p)
                        except Exception:
                            pass
                    return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": str(exc), "cancelado": False}
                ok_exec, msg, fue_cancel = _ejecutar_ffmpeg(args_part, part_tmp, cancel_check)
                if fue_cancel:
                    for p in partes:
                        try:
                            if os.path.exists(p):
                                os.remove(p)
                        except Exception:
                            pass
                    return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": "cancelado", "cancelado": True}
                if not ok_exec:
                    for p in partes:
                        try:
                            if os.path.exists(p):
                                os.remove(p)
                        except Exception:
                            pass
                    return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": msg, "cancelado": False}
                # Verificar cada parte
                ok_ver, motivo = exp._verificar_salida(part_tmp, dur, info_fuente)
                if not ok_ver:
                    for p in partes:
                        try:
                            if os.path.exists(p):
                                os.remove(p)
                        except Exception:
                            pass
                    return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": f"verificación de parte {idx} fallida: {motivo}", "cancelado": False}

            # Paso 2: concat de partes con mapeo explícito y recodificación
            if cancel_check is not None and cancel_check():
                for p in partes:
                    try:
                        if os.path.exists(p):
                            os.remove(p)
                    except Exception:
                        pass
                try:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                except Exception:
                    pass
                return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": "cancelado", "cancelado": True}

            # Usar concat demuxer con lista temporal
            lista_path = os.path.join(os.path.dirname(os.path.abspath(tmp)), f".tmp_concat_list_{uuid.uuid4().hex[:6]}.txt")
            try:
                with open(lista_path, "w", encoding="utf-8") as lf:
                    for p in partes:
                        # Escapar comillas simples: ffmpeg concat requiere 'file' con ruta
                        # Usar comillas simples y escapar ' -> '\''
                        ruta_esc = p.replace("'", "'\\''")
                        lf.write(f"file '{ruta_esc}'\n")
            except Exception as exc:
                for p in partes:
                    try:
                        if os.path.exists(p):
                            os.remove(p)
                    except Exception:
                        pass
                return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": f"no se pudo crear lista concat: {exc}", "cancelado": False}

            # Construir args concat demuxer con recodificación y mapeo explícito
            # Necesitamos preservar 0/1/2 audio y subs
            has_video = info_fuente.get("has_video", False)
            has_audio = info_fuente.get("has_audio", False)
            # Construir comando: ffmpeg -f concat -safe 0 -i lista -c:v ... -c:a ... -c:s ... tmp
            args_concat = ["ffmpeg", "-f", "concat", "-safe", "0", "-i", lista_path]
            # Mapeo explícito: maps dependen de streams presentes en las partes
            # Las partes tienen ya los mismos streams que fuente (video/audio/subs) recodificados
            # Usamos mapeo explícito 0:v, 0:a, 0:s si existen
            if has_video:
                args_concat += ["-map", "0:v"]
            if has_audio:
                args_concat += ["-map", "0:a"]
            if sub_count > 0:
                args_concat += ["-map", "0:s"]
            if has_video:
                args_concat += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p"]
                if ext_dest == ".mp4":
                    args_concat += ["-movflags", "+faststart"]
            if has_audio:
                args_concat += ["-c:a", "aac", "-b:a", "128k"]
            if sub_count > 0:
                if ext_dest == ".mp4":
                    args_concat += ["-c:s", "mov_text"]
                else:
                    args_concat += ["-c:s", "srt"]
            args_concat.append(tmp)

            ok_exec, msg, fue_cancel = _ejecutar_ffmpeg(args_concat, tmp, cancel_check)
            # limpiar lista y partes siempre
            try:
                if os.path.exists(lista_path):
                    os.remove(lista_path)
            except Exception:
                pass
            # partes se limpian tras éxito o antes de verificar; si cancel, ya limpiadas
            for p in partes:
                try:
                    if os.path.exists(p):
                        os.remove(p)
                except Exception:
                    pass

            if fue_cancel:
                try:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                except Exception:
                    pass
                return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": "cancelado", "cancelado": True}
            if not ok_exec:
                return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": msg, "cancelado": False}

            if cancel_check is not None and cancel_check():
                try:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                except Exception:
                    pass
                return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": "cancelado", "cancelado": True}

            ok_ver, motivo = _verificar_salida(tmp, duracion_total, info_fuente)
            if not ok_ver:
                try:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                except Exception:
                    pass
                return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": f"verificación fallida: {motivo}", "cancelado": False}

            if os.path.exists(destino):
                try:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                except Exception:
                    pass
                return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": "destino apareció durante la exportación, no se sobrescribirá", "cancelado": False}
            try:
                if os.path.exists(destino):
                    raise FileExistsError("destino ya existe")
                os.rename(tmp, destino)
            except FileExistsError:
                try:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                except Exception:
                    pass
                return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": "destino ya existe, no se sobrescribirá", "cancelado": False}
            except OSError as exc:
                if os.path.exists(destino):
                    try:
                        if os.path.exists(tmp):
                            os.remove(tmp)
                    except Exception:
                        pass
                    return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": "destino ya existe, no se sobrescribirá", "cancelado": False}
                try:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                except Exception:
                    pass
                return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": f"no se pudo publicar el archivo: {exc}", "cancelado": False}

            info_final = _ffprobe_info(destino)
            dur_final = info_final.get("duration") if info_final else None
            start_final = info_final.get("start_time") if info_final else None
            streams_final = info_final.get("streams") if info_final else None
            return {"ok": True, "salida": destino, "duracion": dur_final, "start": start_final, "streams": streams_final, "error": None, "cancelado": False}

        except Exception as exc:
            # limpieza agresiva ante excepción inesperada
            for p in partes:
                try:
                    if os.path.exists(p):
                        os.remove(p)
                except Exception:
                    pass
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass
            if cancel_check is not None and cancel_check():
                return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": "cancelado", "cancelado": True}
            return {"ok": False, "salida": None, "duracion": None, "start": None, "streams": None, "error": f"error inesperado en fallback: {exc}", "cancelado": False}


def obtener_comando_preview(fuente, segmentos, destino):
    info = _ffprobe_info(fuente)
    if info is None:
        raise RuntimeError("no se pudo probar fuente")
    if info.get("sub_count", 0) > 0:
        # fallback preview: mostrar comandos de partes + concat? Simplificar
        return ["ffmpeg", "-f", "concat", "fallback"]
    return _construir_args_concat_sin_subs(fuente, segmentos, destino, info)
