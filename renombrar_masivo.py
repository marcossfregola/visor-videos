"""Servicio B7.7 — renombrado masivo seguro con plantilla cerrada, preview exacta y ciclos.

Contrato:
- Entrada: videos seleccionados en orden visible estable (lista de dicts con video_id, nombre, ruta).
- Plantilla: reutiliza exclusivamente motores cerrados de nombres.py (sin eval).
- Preview es exactamente el plan que se ejecutará (misma generación, incluye sanitización y sufijos).
- Resuelve colisiones intra-lote, FS existentes y UNIQUE(nombre) case-insensitive antes de ejecutar. Nunca sobrescribe.
- Detecta intercambios/ciclos (A->B y B->A, cadenas de 3) y ejecuta con temporales únicos, manteniendo compensación por item.
- Preserva extensión original de cada video; no cambia extensiones.
- Sanitización via nombres.py ocurre al construir preview y el nombre mostrado es final exacto.
- Preserva video_id, marcadores, segmentos, derivados; reasocia miniaturas/previews sin procesamiento multimedia.
- Lote con progreso y cancelación cooperativa; atomicidad por item/ciclo; informe parcial.
- Sin reescaneo global; sin procesamiento multimedia externo. UI no SQLite/FS directo (delega aquí).
"""

import os
import sqlite3
import uuid
import datetime

import nombres as nombres_mod
from rutas import ruta_biblioteca


class RenombradoMasivoError(Exception):
    pass

class ValidacionError(RenombradoMasivoError):
    pass

class PlantillaError(RenombradoMasivoError):
    pass

class ColisionError(RenombradoMasivoError):
    pass


def _validar_video_infos(video_infos):
    if isinstance(video_infos, (str, bytes, bytearray)):
        raise TypeError("video_infos debe ser colección, no texto")
    try:
        lista = list(video_infos)
    except TypeError:
        raise TypeError("video_infos debe ser colección iterable") from None
    if not lista:
        raise ValidacionError("selección vacía")
    out = []
    for idx, info in enumerate(lista):
        if not isinstance(info, dict):
            raise TypeError(f"video_infos[{idx}] debe ser dict")
        vid = info.get("video_id")
        nombre = info.get("nombre")
        ruta = info.get("ruta")
        if isinstance(vid, bool) or not isinstance(vid, int) or vid <= 0:
            raise ValidacionError(f"video_id inválido en índice {idx}: {vid!r}")
        if not isinstance(nombre, str) or not nombre.strip():
            raise ValidacionError(f"nombre inválido en índice {idx}")
        if not isinstance(ruta, str) or not ruta.strip():
            raise ValidacionError(f"ruta inválida en índice {idx}")
        # preservar extensión original
        ext = os.path.splitext(nombre)[1]
        if not ext:
            raise ValidacionError(f"nombre sin extensión en índice {idx}: {nombre!r}")
        # validar que ruta basename coincide con nombre (case-insensitive Windows)
        base = os.path.basename(ruta)
        if os.path.normcase(base) != os.path.normcase(nombre):
            # permitir diferencia de caso? validar que lower coincide; si no, advertir pero no bloquear plan (ruta puede ser histórica)
            # solo validar que nombres coincidan lower; si no, usar nombre como verdad
            pass
        out.append({
            "video_id": int(vid),
            "nombre": nombre,
            "ruta": ruta,
            "extension": ext,
            "directorio": os.path.dirname(os.path.abspath(ruta)) if os.path.isabs(ruta) else os.path.dirname(ruta) or ".",
            "indice": idx,
        })
    # verificar ids duplicados
    ids = [x["video_id"] for x in out]
    if len(ids) != len(set(ids)):
        raise ValidacionError("video_ids duplicados en selección")
    return out


def _cargar_nombres_db(ruta_db):
    if ruta_db is None:
        ruta_db = ruta_biblioteca()
    if not os.path.isfile(ruta_db):
        raise FileNotFoundError(f"Base de datos no encontrada: {ruta_db}")
    conn = sqlite3.connect(ruta_db)
    try:
        filas = conn.execute("SELECT nombre FROM videos").fetchall()
        return [r[0] for r in filas if isinstance(r[0], str)]
    finally:
        try:
            conn.close()
        except Exception as _b77_exc:
            import warnings as _b77_warnings
            _b77_warnings.warn(f"_cargar_nombres_db cerrar conexión falló: {_b77_exc}", RuntimeWarning)


def _cargar_rutas_db_por_id(video_ids, ruta_db):
    if ruta_db is None:
        ruta_db = ruta_biblioteca()
    if not os.path.isfile(ruta_db):
        raise FileNotFoundError(f"Base de datos no encontrada: {ruta_db}")
    conn = sqlite3.connect(ruta_db)
    try:
        placeholders = ",".join("?" * len(video_ids))
        filas = conn.execute(f"SELECT id, nombre, ruta FROM videos WHERE id IN ({placeholders})", video_ids).fetchall()
        mapa = {r[0]: {"id": r[0], "nombre": r[1], "ruta": r[2]} for r in filas}
        return mapa
    finally:
        try:
            conn.close()
        except Exception as _b77_exc:
            import warnings as _b77_warnings
            _b77_warnings.warn(f"_cargar_rutas_db_por_id cerrar conexión falló: {_b77_exc}", RuntimeWarning)


def construir_plan(video_infos, plantilla, texto=None, fecha_hoy=None, ruta_db=None):
    """Construye preview/plan exacto para renombrado masivo.

    video_infos: lista ordenada estable de dicts {video_id, nombre, ruta}
    plantilla: texto con tokens cerrados nombres.py
    texto: valor para {texto} si plantilla lo usa (puede ser None si no usa)
    fecha_hoy: date para determinismo (None => today)
    ruta_db: ruta a biblioteca.db (None => default)

    Retorna dict:
      {
        ok: bool,
        plan: [ {video_id, nombre_actual, nombre_final, ruta_actual, ruta_final, directorio, extension, stem, error, indice} ],
        errores: [mensajes globales],
        plantilla: str,
        texto: str|None,
      }
    Si plantilla inválida o error global, ok=False y plan vacío o con errores por item.
    La preview debe mostrar exactamente nombre_final (con extensión preservada y sufijos).
    """
    # Validar plantilla tipo
    if not isinstance(plantilla, str):
        return {"ok": False, "plan": [], "errores": ["plantilla debe ser texto"], "plantilla": plantilla}
    if not plantilla.strip():
        return {"ok": False, "plan": [], "errores": ["plantilla vacía"], "plantilla": plantilla}
    # validar tokens via nombres
    try:
        nombres_mod._validar_plantilla(plantilla)
    except (nombres_mod.PlantillaInvalidaError, nombres_mod.TokenDesconocidoError, nombres_mod.FormatoInvalidoError) as exc:
        return {"ok": False, "plan": [], "errores": [f"plantilla inválida: {exc}"], "plantilla": plantilla}
    except nombres_mod.NombresError as exc:
        return {"ok": False, "plan": [], "errores": [f"plantilla error: {exc}"], "plantilla": plantilla}

    # validar video_infos
    try:
        infos = _validar_video_infos(video_infos)
    except Exception as exc:
        return {"ok": False, "plan": [], "errores": [str(exc)], "plantilla": plantilla}

    # fecha determinística
    if fecha_hoy is not None and not isinstance(fecha_hoy, (datetime.date, datetime.datetime, str)):
        return {"ok": False, "plan": [], "errores": ["fecha_hoy debe ser date/datetime/str o None"], "plantilla": plantilla}
    # si fecha_hoy es datetime, convertir a date
    fecha_ref = fecha_hoy
    if isinstance(fecha_ref, datetime.datetime):
        fecha_ref = fecha_ref.date()

    # Cargar DB nombres existentes
    try:
        db_nombres = _cargar_nombres_db(ruta_db)
    except Exception as exc:
        return {"ok": False, "plan": [], "errores": [f"no se pudo leer DB: {exc}"], "plantilla": plantilla}

    # Mapa de nombres actuales del lote (lower) para excluir de colisión externa
    lote_actual_lower = {info["nombre"].lower(): info["video_id"] for info in infos}
    # DB restantes = todos menos los del lote (lower set)
    db_lower_all = {n.lower() for n in db_nombres}
    db_restante_lower = db_lower_all - set(lote_actual_lower.keys())
    # También necesitamos mapa nombre->id para mensajes, pero no esencial

    # FS por directorio: listado
    # Agrupar por directorio normalizado
    dirs = {}
    for info in infos:
        d = info["directorio"]
        # normalizar para FS check case-insensitive
        norm = os.path.normcase(os.path.normpath(os.path.abspath(d))) if os.path.isabs(d) or os.path.isdir(d) else os.path.normcase(os.path.normpath(d))
        dirs.setdefault(norm, []).append(info)
    # Construir FS sets por directorio (lower nombres existentes excluyendo batch fuentes en ese dir)
    fs_sets = {}
    for norm_dir, lista in dirs.items():
        # obtener directorio real (primer info)
        dir_real = lista[0]["directorio"]
        # os.path.abspath puede fallar si dir_relativo; usar dir_real tal cual
        try:
            if os.path.isdir(dir_real):
                archivos = os.listdir(dir_real)
            else:
                # intentar abspath version
                abs_dir = os.path.abspath(dir_real)
                if os.path.isdir(abs_dir):
                    archivos = os.listdir(abs_dir)
                    dir_real = abs_dir
                else:
                    archivos = []
        except OSError:
            archivos = []
        # lower set de archivos en ese directorio
        lower_fs_all = {f.lower() for f in archivos if isinstance(f, str)}
        # excluir fuentes del lote en ese directorio
        fuentes_en_dir_lower = {info["nombre"].lower() for info in lista}
        fs_sets[norm_dir] = lower_fs_all - fuentes_en_dir_lower
        # guardar también dir_real para referencia
        # actualizar dirs mapping to keep real
    # Mapa de directorio norm -> set restantes

    # Generación secuencial con resolución de colisiones
    lote_final_lower = set()
    plan = []
    errores_globales = []
    tiene_error_item = False

    # Para resolver colisión por item, necesitamos función existe_fn que cierre sobre db_restante, fs_sets y lote_final
    for info in infos:
        vid = info["video_id"]
        nombre_actual = info["nombre"]
        ruta_actual = info["ruta"]
        ext_original = info["extension"]
        directorio = info["directorio"]
        norm_dir = os.path.normcase(os.path.normpath(os.path.abspath(directorio))) if os.path.isabs(directorio) or os.path.isdir(directorio) else os.path.normcase(os.path.normpath(directorio))
        # contexto para plantilla
        contexto = {
            "original": nombre_actual,
            "numero": info["indice"] + 1,  # 1-index
        }
        # fecha: si plantilla contiene {fecha}, proveer fecha_ref
        if "{fecha" in plantilla:
            # proveer fecha explicita para determinismo
            if fecha_ref is not None:
                contexto["fecha"] = fecha_ref
            else:
                contexto["fecha"] = datetime.date.today()
        # texto: si plantilla contiene {texto}
        if "{texto" in plantilla:
            # texto debe ser proporcionado
            if texto is None:
                # error: texto faltante
                plan.append({
                    "video_id": vid,
                    "nombre_actual": nombre_actual,
                    "nombre_final": None,
                    "ruta_actual": ruta_actual,
                    "ruta_final": None,
                    "directorio": directorio,
                    "extension": ext_original,
                    "stem": None,
                    "error": "plantilla requiere {texto} pero no se proporcionó texto",
                    "indice": info["indice"],
                })
                tiene_error_item = True
                continue
            contexto["texto"] = texto
        # Si plantilla contiene {inicio} o {fin} sin contexto, fallará en render (ContextoFaltante)
        # No proveemos inicio/fin para rename masivo (no tiene sentido); dejar que falle visiblemente

        # Intentar renderizar plantilla a stem
        try:
            stem = nombres_mod.renderizar_plantilla(plantilla, contexto, fecha_hoy=fecha_ref if isinstance(fecha_ref, datetime.date) else None)
        except nombres_mod.NombresError as exc:
            plan.append({
                "video_id": vid,
                "nombre_actual": nombre_actual,
                "nombre_final": None,
                "ruta_actual": ruta_actual,
                "ruta_final": None,
                "directorio": directorio,
                "extension": ext_original,
                "stem": None,
                "error": f"{type(exc).__name__}: {exc}",
                "indice": info["indice"],
            })
            tiene_error_item = True
            continue
        except Exception as exc:
            plan.append({
                "video_id": vid,
                "nombre_actual": nombre_actual,
                "nombre_final": None,
                "ruta_actual": ruta_actual,
                "ruta_final": None,
                "directorio": directorio,
                "extension": ext_original,
                "stem": None,
                "error": f"error inesperado render: {type(exc).__name__}: {exc}",
                "indice": info["indice"],
            })
            tiene_error_item = True
            continue

        # Construir nombre completo preservando extensión original
        # stem ya sanitizado; ext_original incluye punto; debe preservarse tal cual (no normalizar a lower? mantener original)
        # Pero para validación de longitud, usar ext tal cual
        # Validar que ext no cambie: ya lo preservamos
        nombre_base = stem + ext_original
        # Validar longitud total (MAX_COMPONENTE)
        try:
            nombres_mod.validar_longitud_final(nombre_base)
        except nombres_mod.NombreVacioError as exc:
            plan.append({
                "video_id": vid,
                "nombre_actual": nombre_actual,
                "nombre_final": None,
                "ruta_actual": ruta_actual,
                "ruta_final": None,
                "directorio": directorio,
                "extension": ext_original,
                "stem": stem,
                "error": f"longitud inválida: {exc}",
                "indice": info["indice"],
            })
            tiene_error_item = True
            continue

        # Resolver colisión determinística con sufijo
        # existe_fn debe verificar db_restante, fs_sets[norm_dir], y lote_final_lower (case-insensitive)
        def existe_fn(candidato):
            cand_lower = candidato.lower()
            if cand_lower in lote_final_lower:
                return True
            if cand_lower in db_restante_lower:
                return True
            # FS check per directorio
            fs_set = fs_sets.get(norm_dir, set())
            if cand_lower in fs_set:
                return True
            return False

        try:
            nombre_final = nombres_mod.resolver_colision(stem, ext_original, existe_fn=existe_fn, nombres_en_lote=lote_final_lower)
        except nombres_mod.NombreVacioError as exc:
            plan.append({
                "video_id": vid,
                "nombre_actual": nombre_actual,
                "nombre_final": None,
                "ruta_actual": ruta_actual,
                "ruta_final": None,
                "directorio": directorio,
                "extension": ext_original,
                "stem": stem,
                "error": f"colisión/longitud: {exc}",
                "indice": info["indice"],
            })
            tiene_error_item = True
            continue
        except nombres_mod.ColisionNoResolubleError as exc:
            plan.append({
                "video_id": vid,
                "nombre_actual": nombre_actual,
                "nombre_final": None,
                "ruta_actual": ruta_actual,
                "ruta_final": None,
                "directorio": directorio,
                "extension": ext_original,
                "stem": stem,
                "error": f"colisión no resoluble: {exc}",
                "indice": info["indice"],
            })
            tiene_error_item = True
            continue
        except Exception as exc:
            plan.append({
                "video_id": vid,
                "nombre_actual": nombre_actual,
                "nombre_final": None,
                "ruta_actual": ruta_actual,
                "ruta_final": None,
                "directorio": directorio,
                "extension": ext_original,
                "stem": stem,
                "error": f"error colisión: {type(exc).__name__}: {exc}",
                "indice": info["indice"],
            })
            tiene_error_item = True
            continue

        # Validar que nombre_final case-insensitive no sea idéntico al actual? Si es idéntico (mismo lower), es no-op.
        # Tratamos como no-op pero no error: si lower igual, no necesita rename; lo marcamos como final igual a actual (sin sufijo)
        # Sin embargo si el usuario eligió plantilla que genera mismo nombre, preview mostrará mismo y ejecución será no-op (omitido)
        # No lo consideramos error, pero lo registramos.
        # Si nombre_final lower == nombre_actual lower, lo dejamos como está (sin cambio) - no añadirá suffix diferente, pero resolver_colision ya habría devuelto base si no colisionaba con otros.
        # Si es idéntico, no hay necesidad de renombrar; lo dejamos.

        # Añadir a lote set
        lote_final_lower.add(nombre_final.lower())
        ruta_final = os.path.join(directorio, nombre_final)
        # Si ruta_actual es absoluta, hacer ruta_final absoluta para ejecución
        if os.path.isabs(ruta_actual):
            ruta_final = os.path.abspath(ruta_final)

        plan.append({
            "video_id": vid,
            "nombre_actual": nombre_actual,
            "nombre_final": nombre_final,
            "ruta_actual": ruta_actual,
            "ruta_final": ruta_final,
            "directorio": directorio,
            "extension": ext_original,
            "stem": stem,
            "error": None,
            "indice": info["indice"],
        })

    ok = not tiene_error_item and not errores_globales
    return {
        "ok": ok,
        "plan": plan,
        "errores": errores_globales,
        "plantilla": plantilla,
        "texto": texto,
    }


def _nombre_seguro_cache(nombre):
    return nombre.replace(os.sep, "_").replace("/", "_")


def _calcular_renombres_cache(nombre_actual, nombre_nuevo, carpeta_mini=None):
    """Reutiliza lógica B7.1 para reasociar miniaturas/previews."""
    try:
        import rutas as rutas_mod
        if carpeta_mini is None:
            try:
                carpeta_mini = rutas_mod.ruta_carpeta_miniaturas()
            except Exception:
                return []
        if not isinstance(carpeta_mini, str) or not carpeta_mini:
            return []
        if not os.path.isdir(carpeta_mini):
            return []
        prefijo_old = _nombre_seguro_cache(os.path.splitext(nombre_actual)[0])
        prefijo_new = _nombre_seguro_cache(os.path.splitext(nombre_nuevo)[0])
        if prefijo_old == prefijo_new:
            return []
        try:
            archivos = os.listdir(carpeta_mini)
        except OSError:
            return []
        renombres = []
        for fname in archivos:
            if not fname.lower().endswith(".jpg"):
                continue
            base, ext = os.path.splitext(fname)
            if base.startswith(prefijo_old + "_preview_"):
                suffix = base[len(prefijo_old):]
                rest = suffix[len("_preview_"):]
                if rest.isdigit():
                    new_name = prefijo_new + suffix + ext
                    src = os.path.join(carpeta_mini, fname)
                    dst = os.path.join(carpeta_mini, new_name)
                    if src != dst:
                        renombres.append((src, dst))
                continue
            if base.startswith(prefijo_old + "_"):
                suffix = base[len(prefijo_old):]
                rest = suffix[1:]
                if rest.isdigit():
                    new_name = prefijo_new + suffix + ext
                    src = os.path.join(carpeta_mini, fname)
                    dst = os.path.join(carpeta_mini, new_name)
                    if src != dst:
                        renombres.append((src, dst))
        return renombres
    except Exception:
        return []


def _renombrar_un_video_atomico(video_id, nombre_actual, nombre_final, ruta_actual, ruta_final, ruta_db):
    """Renombra un único video de forma segura (reutiliza lógica B7.1 mínima).

    Realiza FS rename + cache + DB UPDATE con compensación.
    Lanza excepciones tipadas en fallo. Retorna dict ok en éxito.
    No valida plantilla; asume plan ya validado.
    """
    import renombrar_video as svc_ren  # reutilizar validaciones mínimas pero no su validar_nuevo_nombre estricto (ya sanitizado)
    # Prevalidar que nombres no sean idénticos case-insensitive -> no-op
    if nombre_actual.lower() == nombre_final.lower():
        # No-op skip
        return {"ok": True, "video_id": video_id, "nombre": nombre_final, "ruta": ruta_actual, "nombre_anterior": nombre_actual, "ruta_anterior": ruta_actual, "omitido": True}

    # Determinar rutas absolutas para FS
    if os.path.isabs(ruta_actual):
        ruta_actual_abs = os.path.abspath(ruta_actual)
    else:
        ruta_actual_abs = ruta_actual
    if os.path.isabs(ruta_final):
        ruta_final_abs = os.path.abspath(ruta_final)
    else:
        ruta_final_abs = ruta_final

    # Verificar origen existe
    if not os.path.isfile(ruta_actual_abs):
        if not os.path.isfile(ruta_actual):
            raise svc_ren.RenombradoError(f"archivo origen no encontrado: {ruta_actual!r}")
        ruta_actual_abs = ruta_actual  # usar relativa si es la que existe

    # Verificar destino no existe (case-insensitive Windows semantics via normcase)
    if os.path.exists(ruta_final_abs):
        # en Windows normcase
        if os.path.normcase(os.path.normpath(ruta_final_abs)) != os.path.normcase(os.path.normpath(ruta_actual_abs)):
            raise svc_ren.ColisionError(f"ya existe archivo en destino: {ruta_final_abs!r}")
        else:
            raise svc_ren.ValidacionError("destino idéntico al origen")

    # DB UNIQUE pre-check (excluir self)
    conn_chk = sqlite3.connect(ruta_db if ruta_db else ruta_biblioteca())
    try:
        fila_dup = conn_chk.execute("SELECT id FROM videos WHERE nombre = ? COLLATE NOCASE AND id != ?", (nombre_final, video_id)).fetchone()
        if fila_dup is not None:
            raise svc_ren.ColisionError(f"ya existe otro video con nombre {nombre_final!r} (id {fila_dup[0]})")
    finally:
        try:
            conn_chk.close()
        except Exception as _b77_exc:
            import warnings as _b77_warnings
            _b77_warnings.warn(f"_renombrar_un_video_atomico conn_chk cerrar falló: {_b77_exc}", RuntimeWarning)

    # Cache colisión
    renombres_cache = _calcular_renombres_cache(nombre_actual, nombre_final)
    for _src, _dst in renombres_cache:
        if os.path.exists(_dst):
            if os.path.normcase(os.path.normpath(_dst)) != os.path.normcase(os.path.normpath(_src)):
                raise svc_ren.ColisionError(f"colisión en cache destino ya existe: {_dst!r}")

    # FS rename video
    try:
        os.rename(ruta_actual_abs if os.path.isfile(ruta_actual_abs) else ruta_actual, ruta_final_abs)
    except OSError as exc:
        raise svc_ren.RenombradoError(f"fallo al renombrar en filesystem: {exc}") from exc

    cache_renombrados = []
    try:
        for src, dst in renombres_cache:
            if not os.path.isfile(src):
                continue
            if os.path.exists(dst):
                continue
            os.rename(src, dst)
            cache_renombrados.append((src, dst))
    except OSError as exc:
        _b77_cache_comp_errs = []
        for s, d in reversed(cache_renombrados):
            try:
                if os.path.isfile(d) and not os.path.exists(s):
                    os.rename(d, s)
            except OSError as _b77_exc:
                _b77_cache_comp_errs.append(f"{d!r}->{s!r}: {_b77_exc}")
        _b77_cache_detalle = f" | compensación cache falló: {'; '.join(_b77_cache_comp_errs)}" if _b77_cache_comp_errs else ""
        try:
            os.rename(ruta_final_abs, ruta_actual_abs if os.path.isabs(ruta_actual_abs) else ruta_actual)
        except OSError as exc_comp:
            raise svc_ren.CompensacionFalloError(
                f"fallo al renombrar cache tras rename video y compensación video también falló: {exc}{_b77_cache_detalle} | compensación video: {exc_comp}",
                ruta_original=ruta_actual_abs, ruta_nueva=ruta_final_abs, error_db=str(exc)+_b77_cache_detalle, error_compensacion=str(exc_comp),
            ) from exc_comp
        if _b77_cache_comp_errs:
            raise svc_ren.RenombradoError(f"fallo al renombrar cache de miniaturas: {exc}{_b77_cache_detalle}") from exc
        raise svc_ren.RenombradoError(f"fallo al renombrar cache de miniaturas: {exc}") from exc

    # DB update
    conn = sqlite3.connect(ruta_db if ruta_db else ruta_biblioteca())
    try:
        conn.execute("BEGIN")
        fila_dup2 = conn.execute("SELECT id FROM videos WHERE nombre = ? COLLATE NOCASE AND id != ?", (nombre_final, video_id)).fetchone()
        if fila_dup2 is not None:
            conn.rollback()
            _b77_cache_comp_errs = []
            for s, d in reversed(cache_renombrados):
                try:
                    if os.path.isfile(d) and not os.path.exists(s):
                        os.rename(d, s)
                except OSError as _b77_exc:
                    _b77_cache_comp_errs.append(f"{d!r}->{s!r}: {_b77_exc}")
            _b77_cache_detalle = f" | compensación cache falló: {'; '.join(_b77_cache_comp_errs)}" if _b77_cache_comp_errs else ""
            try:
                os.rename(ruta_final_abs, ruta_actual_abs if os.path.isabs(ruta_actual_abs) else ruta_actual)
            except OSError as exc_comp:
                raise svc_ren.CompensacionFalloError(
                    f"fallo SQLite (colisión) y compensación también falló: {exc_comp}{_b77_cache_detalle}",
                    ruta_original=ruta_actual_abs, ruta_nueva=ruta_final_abs, error_db=f"colisión UNIQUE {nombre_final!r}{_b77_cache_detalle}", error_compensacion=str(exc_comp),
                ) from exc_comp
            if _b77_cache_comp_errs:
                raise svc_ren.CompensacionFalloError(
                    f"compensación cache falló tras colisión: {'; '.join(_b77_cache_comp_errs)}",
                    ruta_original=ruta_actual_abs, ruta_nueva=ruta_final_abs, error_db=f"colisión UNIQUE {nombre_final!r}", error_compensacion='; '.join(_b77_cache_comp_errs),
                )
            raise svc_ren.ColisionError(f"ya existe otro video con nombre {nombre_final!r} (carrera)")
        cur = conn.execute("UPDATE videos SET nombre = ?, ruta = ? WHERE id = ?", (nombre_final, ruta_final_abs, video_id))
        if cur.rowcount == 0:
            conn.rollback()
            _b77_cache_comp_errs2 = []
            for s, d in reversed(cache_renombrados):
                try:
                    if os.path.isfile(d) and not os.path.exists(s):
                        os.rename(d, s)
                except OSError as _b77_exc:
                    _b77_cache_comp_errs2.append(f"{d!r}->{s!r}: {_b77_exc}")
            _b77_cache_detalle2 = f" | compensación cache falló: {'; '.join(_b77_cache_comp_errs2)}" if _b77_cache_comp_errs2 else ""
            try:
                os.rename(ruta_final_abs, ruta_actual_abs if os.path.isabs(ruta_actual_abs) else ruta_actual)
            except OSError as exc_comp:
                raise svc_ren.CompensacionFalloError(
                    f"video_id {video_id} no encontrado tras rename y compensación falló{_b77_cache_detalle2}",
                    ruta_original=ruta_actual_abs, ruta_nueva=ruta_final_abs, error_db="UPDATE rowcount 0"+_b77_cache_detalle2, error_compensacion=str(exc_comp),
                ) from exc_comp
            if _b77_cache_comp_errs2:
                raise svc_ren.CompensacionFalloError(
                    f"compensación cache falló tras rowcount 0: {'; '.join(_b77_cache_comp_errs2)}",
                    ruta_original=ruta_actual_abs, ruta_nueva=ruta_final_abs, error_db="UPDATE rowcount 0", error_compensacion='; '.join(_b77_cache_comp_errs2),
                )
            raise svc_ren.RenombradoError(f"video_id {video_id} no encontrado para actualizar")
        conn.commit()
    except (sqlite3.IntegrityError, sqlite3.OperationalError) as exc:
        _b77_rollback_err = None
        try:
            conn.rollback()
        except Exception as _b77_exc:
            _b77_rollback_err = f"rollback falló: {_b77_exc}"
        _b77_cache_comp_errs = []
        for s, d in reversed(cache_renombrados):
            try:
                if os.path.isfile(d) and not os.path.exists(s):
                    os.rename(d, s)
            except OSError as _b77_exc:
                _b77_cache_comp_errs.append(f"{d!r}->{s!r}: {_b77_exc}")
        _b77_extra = ""
        if _b77_rollback_err:
            _b77_extra += f" | {_b77_rollback_err}"
        if _b77_cache_comp_errs:
            _b77_extra += f" | compensación cache falló: {'; '.join(_b77_cache_comp_errs)}"
        try:
            os.rename(ruta_final_abs, ruta_actual_abs if os.path.isabs(ruta_actual_abs) else ruta_actual)
        except OSError as exc_comp:
            raise svc_ren.CompensacionFalloError(
                f"fallo SQLite tras rename FS y compensación también falló: {exc}{_b77_extra} | compensación video: {exc_comp}",
                ruta_original=ruta_actual_abs, ruta_nueva=ruta_final_abs, error_db=str(exc)+_b77_extra, error_compensacion=str(exc_comp),
            ) from exc_comp
        if _b77_extra:
            raise svc_ren.RenombradoError(f"fallo al persistir renombrado en DB (FS restaurado): {exc}{_b77_extra}") from exc
        raise svc_ren.RenombradoError(f"fallo al persistir renombrado en DB (FS restaurado): {exc}") from exc
    except svc_ren.RenombradoError:
        raise
    except svc_ren.CompensacionFalloError:
        raise
    except Exception as exc:
        _b77_rollback_err = None
        try:
            conn.rollback()
        except Exception as _b77_exc:
            _b77_rollback_err = f"rollback falló: {_b77_exc}"
        _b77_cache_comp_errs = []
        for s, d in reversed(cache_renombrados):
            try:
                if os.path.isfile(d) and not os.path.exists(s):
                    os.rename(d, s)
            except OSError as _b77_exc:
                _b77_cache_comp_errs.append(f"{d!r}->{s!r}: {_b77_exc}")
        _b77_extra = ""
        if _b77_rollback_err:
            _b77_extra += f" | {_b77_rollback_err}"
        if _b77_cache_comp_errs:
            _b77_extra += f" | compensación cache falló: {'; '.join(_b77_cache_comp_errs)}"
        try:
            os.rename(ruta_final_abs, ruta_actual_abs if os.path.isabs(ruta_actual_abs) else ruta_actual)
        except OSError as exc_comp:
            raise svc_ren.CompensacionFalloError(
                f"fallo inesperado tras rename FS y compensación falló: {exc}{_b77_extra} | compensación video: {exc_comp}",
                ruta_original=ruta_actual_abs, ruta_nueva=ruta_final_abs, error_db=str(exc)+_b77_extra, error_compensacion=str(exc_comp),
            ) from exc_comp
        if _b77_extra:
            raise svc_ren.RenombradoError(f"fallo inesperado al renombrar: {exc}{_b77_extra}") from exc
        raise svc_ren.RenombradoError(f"fallo inesperado al renombrar: {exc}") from exc
    finally:
        try:
            conn.close()
        except Exception as _b77_exc:
            import warnings as _b77_warnings
            _b77_warnings.warn(f"_renombrar_un_video_atomico cerrar conexión final falló: {_b77_exc}", RuntimeWarning)

    return {
        "ok": True,
        "video_id": video_id,
        "nombre": nombre_final,
        "ruta": ruta_final_abs,
        "nombre_anterior": nombre_actual,
        "ruta_anterior": ruta_actual_abs if os.path.isabs(ruta_actual_abs) else ruta_actual,
        "error": None,
    }


def ejecutar_plan(plan, ruta_db=None, cancel_check=None, progreso_callback=None):
    """Ejecuta plan previamente construido (preview exacta).

    plan: lista de dicts como retorna construir_plan (con nombre_final, ruta_final)
    ruta_db: ruta DB
    cancel_check: callable -> True si debe cancelar antes del próximo ítem
    progreso_callback: callable(actual, total)

    Retorna dict lote:
      {total, procesados, exitosos, fallidos, cancelados, detalles, plan}
    No sobrescribe, maneja ciclos con temporales únicos, preserva extensión, reasocia miniaturas.
    """
    if ruta_db is None:
        try:
            ruta_db = ruta_biblioteca()
        except Exception as _b77_exc:
            raise RenombradoMasivoError(f"no se pudo resolver ruta_db vía ruta_biblioteca(): {_b77_exc}") from _b77_exc
    if not isinstance(plan, list):
        raise TypeError("plan debe ser lista")
    total = len(plan)
    # Validar plan sin errores previos
    for item in plan:
        if not isinstance(item, dict):
            raise TypeError("item plan debe ser dict")
        if item.get("error"):
            raise ValidacionError(f"plan contiene error en video_id {item.get('video_id')}: {item.get('error')}")

    # Detectar ciclos/intercambios: mapear source lower -> item, target lower -> items
    source_lower_to_item = {}
    for item in plan:
        source_lower_to_item[item["nombre_actual"].lower()] = item
    # items cuya target lower está en source_lower (potencial ciclo/cadena)
    necesita_temp = set()
    for item in plan:
        tgt = item["nombre_final"]
        if tgt is None:
            continue
        if tgt.lower() in source_lower_to_item:
            # solo si mismo directorio? Para FS, check directorio; para DB global, cualquier dir cuenta
            # Si directorios distintos, FS no colisiona pero DB sí, igual necesita temp para DB
            necesita_temp.add(item["video_id"])
            # también marcar el item fuente que es target de este?
            # El source item que tiene ese nombre también debería ir a temp para liberar
            # Pero eso se detectará cuando ese source item sea evaluado como necesita_temp si su target también está en source set
            # Para swap A->B, B->A ambos tienen target en source set, ambos marcados
            # Para cadena A->B, B->C, A target B está en source, B target C no está en source si C no es fuente, entonces solo A marcado
            # A necesita temp, B no necesariamente, pero si ejecutamos A->temp luego B->C luego temp->B funciona
            pass

    # Para swap, ambos necesitan temp. Para cadena, solo el que apunta a fuente necesita temp.
    # Construir conjunto de video_ids que participan en cualquier ciclo (SCC)
    # Simple: encontrar componentes donde cada nodo apunta a otro nodo en lote
    # Haremos detección de ciclos via DFS para marcar todos los nodos en ciclos reales
    # Para cadenas, no es ciclo, solo marca el primero
    # Por ahora marcar como necesita_temp todos los que su target esté en source set (suficiente para manejar swaps y cadenas con temporaries para el primero)

    # Construir lista ordenada de ejecución:
    # Para evitar colisión intra-lote no cíclica, el orden ya está dado y ya resolvimos suffixes, no hay colisión.
    # Para ciclos, usaremos fase temp.

    # Generar temporales únicos para los que necesitan
    temp_map = {}  # video_id -> {temp_nombre, temp_ruta}
    for vid in necesita_temp:
        # buscar item
        item = next((x for x in plan if x["video_id"] == vid), None)
        if item is None:
            continue
        ext = item["extension"]
        directorio = item["directorio"]
        # generar temp único que no colisione con ningún nombre existente (DB, FS, lote finales, temporales)
        for _ in range(5):
            tmp_name = f"__tmp_mass_{vid}_{uuid.uuid4().hex[:8]}{ext}"
            tmp_lower = tmp_name.lower()
            # verificar no colisione con lote finales ni fuentes ni db restantes ni fs
            # simple: si tmp_lower no está en source_lower ni en lote finales ni db ni fs, aceptable
            # comprobar contra fuentes y finales
            if tmp_lower in source_lower_to_item:
                continue
            # finales lower set
            finales_lower = {p["nombre_final"].lower() for p in plan if p.get("nombre_final")}
            if tmp_lower in finales_lower:
                continue
            # db restantes (reconsultar) - fallo de verificación impide asumir temporal seguro
            try:
                db_nombres = _cargar_nombres_db(ruta_db)
                if tmp_lower in {n.lower() for n in db_nombres}:
                    continue
            except Exception as _b77_exc:
                raise ColisionError(f"no se pudo verificar colisión DB para temporal {tmp_name!r}: {_b77_exc}") from _b77_exc
            # fs check per dir: verificar no existe archivo con ese nombre en dir
            dir_real = directorio
            try:
                if os.path.isdir(dir_real):
                    existing = {f.lower() for f in os.listdir(dir_real)}
                    if tmp_lower in existing:
                        continue
                else:
                    abs_dir = os.path.abspath(dir_real)
                    if os.path.isdir(abs_dir):
                        existing = {f.lower() for f in os.listdir(abs_dir)}
                        if tmp_lower in existing:
                            continue
            except Exception as _b77_exc:
                raise ColisionError(f"no se pudo verificar FS para temporal {tmp_name!r} en {dir_real!r}: {_b77_exc}") from _b77_exc
            # ok
            temp_ruta = os.path.join(directorio, tmp_name)
            if os.path.isabs(item["ruta_actual"]):
                temp_ruta = os.path.abspath(temp_ruta)
            temp_map[vid] = {"temp_nombre": tmp_name, "temp_ruta": temp_ruta, "item": item}
            break
        if vid not in temp_map:
            raise ColisionError(f"no se pudo generar temporal único para video_id {vid}")

    # --- Detección de ciclos/SCC para rollback determinista ---
    def _encontrar_ciclos(plan_local, source_map):
        lower_to_vid = {it["nombre_actual"].lower(): it["video_id"] for it in plan_local}
        vid_to_target = {}
        for it in plan_local:
            tgt = it.get("nombre_final")
            lower = tgt.lower() if isinstance(tgt, str) else None
            vid_to_target[it["video_id"]] = lower_to_vid.get(lower) if lower else None
        visited_global = set()
        ciclos = []
        for start in list(vid_to_target.keys()):
            if start in visited_global:
                continue
            path = []
            pos = {}
            cur = start
            seen = set()
            while cur is not None and cur not in visited_global:
                if cur in pos:
                    ciclo = set(path[pos[cur]:])
                    if len(ciclo) > 1 or (len(ciclo) == 1 and vid_to_target.get(cur) == cur):
                        ciclos.append(ciclo)
                    break
                if cur in seen:
                    break
                pos[cur] = len(path)
                path.append(cur)
                seen.add(cur)
                cur = vid_to_target.get(cur)
            for n in path:
                visited_global.add(n)
        return ciclos

    ciclos = _encontrar_ciclos(plan, source_lower_to_item)
    # Mapear vid -> ciclo idx
    vid_a_ciclo = {}
    grupos_temp = []  # lista de sets (ciclos)
    for c in ciclos:
        grupos_temp.append(set(c))
        for v in c:
            vid_a_ciclo[v] = len(grupos_temp) - 1
    # Singletons que necesitan temp pero no están en ciclo -> grupo unitario
    for vid in list(necesita_temp):
        if vid not in vid_a_ciclo:
            grupos_temp.append({vid})
            vid_a_ciclo[vid] = len(grupos_temp) - 1
    # Orden de grupos según aparición en plan
    def _grupo_orden(g):
        return min(next((p["indice"] for p in plan if p["video_id"] == v), 9999) for v in g)
    grupos_temp.sort(key=_grupo_orden)

    exitosos = []
    fallidos = []
    cancelados = []
    detalles = []
    temp_exitos = {}  # vid -> temp result

    # Helper rollback para un grupo
    def _rollback_temps(grupo, motivo_error=None):
        errores = []
        # revertir cada temp exitoso del grupo a origen
        for vid in list(grupo):
            if vid not in temp_exitos:
                continue
            item = next((x for x in plan if x["video_id"] == vid), None)
            if item is None:
                continue
            rec = temp_exitos.get(vid)
            if rec is None:
                continue
            try:
                _renombrar_un_video_atomico(vid, rec["nombre"], item["nombre_actual"], rec["ruta"], item["ruta_actual"], ruta_db)
                del temp_exitos[vid]
                # limpiar temp_map entry si existe
                temp_map.pop(vid, None)
            except Exception as exc2:
                errores.append(f"rollback temp->original vid {vid} falló: {type(exc2).__name__}: {exc2}")
        return errores

    def _rollback_finales_y_temps(grupo, finales_ok_set):
        errores = []
        # 1) finales -> temp
        for vid in list(finales_ok_set):
            item = next((x for x in plan if x["video_id"] == vid), None)
            rec = temp_exitos.get(vid)
            if item is None or rec is None:
                continue
            try:
                _renombrar_un_video_atomico(vid, item["nombre_final"], rec["nombre"], item["ruta_final"], rec["ruta"], ruta_db)
                finales_ok_set.discard(vid)
            except Exception as exc2:
                errores.append(f"compensación final->temp vid {vid} falló: {type(exc2).__name__}: {exc2}")
        # 2) temps -> original
        for vid in list(grupo):
            if vid not in temp_exitos:
                continue
            item = next((x for x in plan if x["video_id"] == vid), None)
            rec = temp_exitos.get(vid)
            if item is None or rec is None:
                continue
            try:
                _renombrar_un_video_atomico(vid, rec["nombre"], item["nombre_actual"], rec["ruta"], item["ruta_actual"], ruta_db)
                del temp_exitos[vid]
                temp_map.pop(vid, None)
            except Exception as exc2:
                errores.append(f"compensación temp->original vid {vid} falló: {type(exc2).__name__}: {exc2}")
        return errores

    # Fase 1: temps por grupo con rollback si falla algún miembro del grupo
    cancelado_global = False
    for grupo in grupos_temp:
        if cancelado_global:
            break
        # cancel check antes de grupo
        if callable(cancel_check):
            try:
                if bool(cancel_check()):
                    # cancelar todos los pendientes (toda la cola)
                    pendientes = [p for p in plan if p["video_id"] not in {e["video_id"] for e in exitosos} and p["video_id"] not in {f["video_id"] for f in fallidos} and p["video_id"] not in {c["video_id"] for c in cancelados}]
                    for rp in pendientes:
                        cancelados.append({"video_id": rp["video_id"], "indice": rp["indice"], "motivo": "cancelado"})
                        detalles.append({"video_id": rp["video_id"], "ok": False, "cancelado": True, "error": "cancelado", "tipo": "Cancelado", "indice": rp["indice"]})
                        if callable(progreso_callback):
                            try:
                                progreso_callback(rp["indice"]+1, total)
                            except Exception as _b77_exc:
                                detalles.append({"video_id": rp["video_id"], "ok": False, "error": f"progreso_callback falló: {_b77_exc}", "tipo": type(_b77_exc).__name__, "indice": rp["indice"], "fase": "progreso_callback", "advertencia": True})
                    cancelado_global = True
                    break
            except Exception as exc:
                for vid in grupo:
                    idx = next((p["indice"] for p in plan if p["video_id"] == vid), -1)
                    fallidos.append({"video_id": vid, "error": f"cancel_check falló: {exc}", "tipo": type(exc).__name__, "indice": idx})
                    detalles.append({"video_id": vid, "ok": False, "error": f"cancel_check falló: {exc}", "tipo": type(exc).__name__, "indice": idx})
                continue
        grupo_exitos_temp = set()
        grupo_fallo = None
        for vid in sorted(grupo, key=lambda v: next((p["indice"] for p in plan if p["video_id"] == v), 9999)):
            if callable(cancel_check):
                try:
                    if bool(cancel_check()):
                        cancelado_global = True
                        break
                except Exception as exc:
                    fallidos.append({"video_id": vid, "error": f"cancel_check falló: {exc}", "tipo": type(exc).__name__, "indice": next((p["indice"] for p in plan if p["video_id"]==vid), -1)})
                    detalles.append({"video_id": vid, "ok": False, "error": f"cancel_check falló: {exc}", "tipo": type(exc).__name__, "indice": next((p["indice"] for p in plan if p["video_id"]==vid), -1)})
                    grupo_fallo = exc
                    break
            info_temp = temp_map.get(vid)
            if info_temp is None:
                continue
            item = info_temp["item"]
            try:
                res = _renombrar_un_video_atomico(item["video_id"], item["nombre_actual"], info_temp["temp_nombre"], item["ruta_actual"], info_temp["temp_ruta"], ruta_db)
                temp_exitos[vid] = res
                grupo_exitos_temp.add(vid)
            except Exception as exc:
                idx = item["indice"]
                fallidos.append({"video_id": vid, "error": str(exc), "tipo": type(exc).__name__, "excepcion": exc, "indice": idx})
                detalles.append({"video_id": vid, "ok": False, "error": str(exc), "tipo": type(exc).__name__, "excepcion": exc, "indice": idx, "fase": "temp"})
                grupo_fallo = exc
                # rollback otros temps exitosos del mismo grupo
                if grupo_exitos_temp:
                    errs = _rollback_temps(grupo_exitos_temp, motivo_error=str(exc))
                    if errs:
                        # compensación falló -> error crítico con evidencia, preservar temps restantes
                        msg = f"ERROR CRÍTICO rollback temp tras fallo en grupo {sorted(grupo)}: {'; '.join(errs)} — evidencia preservada (posible __tmp_mass_* residual requiere intervención manual)"
                        for v in grupo_exitos_temp:
                            if v in temp_exitos:
                                # marcar como fallido crítico
                                idx2 = next((p["indice"] for p in plan if p["video_id"] == v), -1)
                                fallidos.append({"video_id": v, "error": msg, "tipo": "CompensacionFalloError", "indice": idx2})
                                detalles.append({"video_id": v, "ok": False, "error": msg, "tipo": "CompensacionFalloError", "indice": idx2, "fase": "compensacion_temp"})
                    else:
                        # marcar los revertidos como fallidos del grupo (no exitosos)
                        for v in list(grupo_exitos_temp):
                            idx2 = next((p["indice"] for p in plan if p["video_id"] == v), -1)
                            # si no ya en fallidos
                            if not any(f.get("video_id") == v for f in fallidos):
                                fallidos.append({"video_id": v, "error": f"revertido por fallo en ciclo/grupo: {exc}", "tipo": type(exc).__name__, "indice": idx2})
                                detalles.append({"video_id": v, "ok": False, "error": f"revertido por fallo en ciclo/grupo: {exc}", "tipo": type(exc).__name__, "indice": idx2, "fase": "rollback_temp"})
                # limpiar entradas del grupo que fallaron
                temp_map.pop(vid, None)
                # marcar restantes del grupo que aún no se intentaron como fallidos revertidos
                for v_rest in grupo:
                    if v_rest == vid or v_rest in grupo_exitos_temp:
                        continue
                    # si no se intentó, marcar como no intentado por fallo de grupo
                    if v_rest in temp_map:
                        temp_map.pop(v_rest, None)
                    idx2 = next((p["indice"] for p in plan if p["video_id"] == v_rest), -1)
                    if not any(f.get("video_id") == v_rest for f in fallidos):
                        fallidos.append({"video_id": v_rest, "error": f"no ejecutado por fallo en grupo {sorted(grupo)}: {exc}", "tipo": type(exc).__name__, "indice": idx2})
                        detalles.append({"video_id": v_rest, "ok": False, "error": f"no ejecutado por fallo en grupo: {exc}", "tipo": type(exc).__name__, "indice": idx2, "fase": "temp_grupo"})
                break
        if cancelado_global:
            # si cancel durante grupo, revertir temps exitosos del grupo
            if grupo_exitos_temp:
                _rollback_temps(grupo_exitos_temp)
                for v in grupo_exitos_temp:
                    idx2 = next((p["indice"] for p in plan if p["video_id"] == v), -1)
                    # remover de fallidos? marcar cancelado
                    # ya están en temp_exitos revertidos, ahora cancelados
                    pass
            # marcar restantes del grupo como cancelados
            for v in grupo:
                if not any(c.get("video_id")==v for c in cancelados) and not any(f.get("video_id")==v for f in fallidos):
                    idx2 = next((p["indice"] for p in plan if p["video_id"] == v), -1)
                    cancelados.append({"video_id": v, "indice": idx2, "motivo": "cancelado"})
                    detalles.append({"video_id": v, "ok": False, "cancelado": True, "error": "cancelado", "tipo": "Cancelado", "indice": idx2})
            # cancelar todos los grupos restantes también
            for g_rest in grupos_temp:
                if g_rest == grupo:
                    continue
                for v in g_rest:
                    if any(c.get("video_id")==v for c in cancelados) or any(f.get("video_id")==v for f in fallidos):
                        continue
                    idx2 = next((p["indice"] for p in plan if p["video_id"] == v), -1)
                    cancelados.append({"video_id": v, "indice": idx2, "motivo": "cancelado"})
                    detalles.append({"video_id": v, "ok": False, "cancelado": True, "error": "cancelado", "tipo": "Cancelado", "indice": idx2})
            break
        # progreso no se reporta aún para temps (intermedio)

    if cancelado_global:
        # también cancelar simples no-temp pendientes
        simples_pend = [p for p in plan if p["video_id"] not in necesita_temp and p["video_id"] not in {e["video_id"] for e in exitosos} and p["video_id"] not in {f["video_id"] for f in fallidos} and p["video_id"] not in {c["video_id"] for c in cancelados}]
        for rp in simples_pend:
            cancelados.append({"video_id": rp["video_id"], "indice": rp["indice"], "motivo": "cancelado"})
            detalles.append({"video_id": rp["video_id"], "ok": False, "cancelado": True, "error": "cancelado", "tipo": "Cancelado", "indice": rp["indice"]})
            if callable(progreso_callback):
                try:
                    progreso_callback(rp["indice"]+1, total)
                except Exception as _b77_exc:
                    detalles.append({"video_id": rp["video_id"], "ok": False, "error": f"progreso_callback falló: {_b77_exc}", "tipo": type(_b77_exc).__name__, "indice": rp["indice"], "fase": "progreso_callback", "advertencia": True})
        # ordenar y retornar - si falla, registrar y retornar sin ordenar
        try:
            detalles = sorted(detalles, key=lambda d: d.get("indice", 0))
        except Exception as _b77_exc:
            detalles.append({"video_id": None, "ok": False, "error": f"no se pudo ordenar detalles: {_b77_exc}", "tipo": type(_b77_exc).__name__, "indice": -1, "fase": "ordenamiento", "advertencia": True})
        procesados = len(exitosos) + len(fallidos)
        return {
            "total": total,
            "procesados": procesados,
            "exitosos": exitosos,
            "fallidos": fallidos,
            "cancelados": cancelados,
            "detalles": detalles,
            "exitosos_count": len(exitosos),
            "fallidos_count": len(fallidos),
            "cancelados_count": len(cancelados),
            "plan": plan,
        }

    # Fase 2: ejecutar simples (no-temp) primero, luego grupos temp->final
    # Simples en orden plan
    simples = [p for p in plan if p["video_id"] not in necesita_temp]
    # También singletons temp que tuvieron éxito están en temp_exitos, los fallidos ya descartados
    # Para simples, manejo per-item sin rollback de grupo
    for item in sorted(simples, key=lambda x: x["indice"]):
        vid = item["video_id"]
        idx = item["indice"]
        if any(c.get("video_id")==vid for c in cancelados):
            continue
        if any(f.get("video_id")==vid for f in fallidos):
            continue
        if callable(cancel_check):
            try:
                if bool(cancel_check()):
                    remaining = [p for p in plan if p["indice"] >= idx and p["video_id"] not in {e["video_id"] for e in exitosos} and p["video_id"] not in {f["video_id"] for f in fallidos} and p["video_id"] not in {c["video_id"] for c in cancelados}]
                    for rp in remaining:
                        cancelados.append({"video_id": rp["video_id"], "indice": rp["indice"], "motivo": "cancelado"})
                        detalles.append({"video_id": rp["video_id"], "ok": False, "cancelado": True, "error": "cancelado", "tipo": "Cancelado", "indice": rp["indice"]})
                        if callable(progreso_callback):
                            try:
                                progreso_callback(rp["indice"]+1, total)
                            except Exception as _b77_exc:
                                detalles.append({"video_id": rp["video_id"], "ok": False, "error": f"progreso_callback falló: {_b77_exc}", "tipo": type(_b77_exc).__name__, "indice": rp["indice"], "fase": "progreso_callback", "advertencia": True})
                    cancelado_global = True
                    break
            except Exception as exc:
                fallidos.append({"video_id": vid, "error": f"cancel_check falló: {exc}", "tipo": type(exc).__name__, "indice": idx})
                detalles.append({"video_id": vid, "ok": False, "error": f"cancel_check falló: {exc}", "tipo": type(exc).__name__, "indice": idx})
                if callable(progreso_callback):
                    try:
                        progreso_callback(len(exitosos)+len(fallidos)+len(cancelados), total)
                    except Exception as _b77_exc:
                        detalles.append({"video_id": vid, "ok": False, "error": f"progreso_callback falló: {_b77_exc}", "tipo": type(_b77_exc).__name__, "indice": idx, "fase": "progreso_callback", "advertencia": True})
                continue
        if item["nombre_actual"].lower() == item["nombre_final"].lower():
            exitosos.append({"video_id": vid, "resultado": {"ok": True, "omitido": True, "video_id": vid, "nombre": item["nombre_final"], "ruta": item["ruta_actual"]}, "indice": idx})
            detalles.append({"video_id": vid, "ok": True, "resultado": {"omitido": True}, "indice": idx})
            if callable(progreso_callback):
                try:
                    progreso_callback(idx+1, total)
                except Exception as _b77_exc:
                    detalles.append({"video_id": vid, "ok": False, "error": f"progreso_callback falló: {_b77_exc}", "tipo": type(_b77_exc).__name__, "indice": idx, "fase": "progreso_callback", "advertencia": True})
            continue
        try:
            res = _renombrar_un_video_atomico(vid, item["nombre_actual"], item["nombre_final"], item["ruta_actual"], item["ruta_final"], ruta_db)
            exitosos.append({"video_id": vid, "resultado": res, "indice": idx})
            detalles.append({"video_id": vid, "ok": True, "resultado": res, "indice": idx})
        except Exception as exc:
            fallidos.append({"video_id": vid, "error": str(exc), "tipo": type(exc).__name__, "excepcion": exc, "indice": idx})
            detalles.append({"video_id": vid, "ok": False, "error": str(exc), "tipo": type(exc).__name__, "excepcion": exc, "indice": idx})
        finally:
            if callable(progreso_callback):
                try:
                    progreso_callback(idx+1, total)
                except Exception as _b77_exc:
                    detalles.append({"video_id": vid, "ok": False, "error": f"progreso_callback falló: {_b77_exc}", "tipo": type(_b77_exc).__name__, "indice": idx, "fase": "progreso_callback", "advertencia": True})
    if cancelado_global:
        # cancelar grupos restantes
        for grupo in grupos_temp:
            for vid in grupo:
                if vid not in temp_exitos:
                    # ya fallido o no iniciado
                    if any(f.get("video_id")==vid for f in fallidos) or any(c.get("video_id")==vid for c in cancelados):
                        continue
                    idx2 = next((p["indice"] for p in plan if p["video_id"]==vid), -1)
                    cancelados.append({"video_id": vid, "indice": idx2, "motivo": "cancelado"})
                    detalles.append({"video_id": vid, "ok": False, "cancelado": True, "error": "cancelado", "tipo": "Cancelado", "indice": idx2})
                else:
                    # tiene temp exitoso pero aún no finalizado -> revertir temp
                    _rollback_temps({vid})
                    idx2 = next((p["indice"] for p in plan if p["video_id"]==vid), -1)
                    cancelados.append({"video_id": vid, "indice": idx2, "motivo": "cancelado"})
                    detalles.append({"video_id": vid, "ok": False, "cancelado": True, "error": "cancelado", "tipo": "Cancelado", "indice": idx2})
        try:
            detalles = sorted(detalles, key=lambda d: d.get("indice", 0))
        except Exception as _b77_exc:
            detalles.append({"video_id": None, "ok": False, "error": f"no se pudo ordenar detalles: {_b77_exc}", "tipo": type(_b77_exc).__name__, "indice": -1, "fase": "ordenamiento", "advertencia": True})
        procesados = len(exitosos) + len(fallidos)
        return {
            "total": total,
            "procesados": procesados,
            "exitosos": exitosos,
            "fallidos": fallidos,
            "cancelados": cancelados,
            "detalles": detalles,
            "exitosos_count": len(exitosos),
            "fallidos_count": len(fallidos),
            "cancelados_count": len(cancelados),
            "plan": plan,
        }

    # Fase 2b: grupos temp -> final con rollback atómico por grupo
    for grupo in grupos_temp:
        # si grupo ya tiene fallidos (temp falló), skip finales
        if any(any(f.get("video_id")==v for f in fallidos) for v in grupo):
            # ya fallido, asegurar temp limpios y reportar progreso
            for v in sorted(grupo, key=lambda v: next((p["indice"] for p in plan if p["video_id"]==v), 9999)):
                if callable(progreso_callback):
                    try:
                        # reportar progreso para cada miembro como fallido ya
                        idx2 = next((p["indice"] for p in plan if p["video_id"]==v), -1)
                        progreso_callback(idx2+1, total)
                    except Exception as _b77_exc:
                        idx2 = next((p["indice"] for p in plan if p["video_id"]==v), -1)
                        detalles.append({"video_id": v, "ok": False, "error": f"progreso_callback falló: {_b77_exc}", "tipo": type(_b77_exc).__name__, "indice": idx2, "fase": "progreso_callback", "advertencia": True})
            continue
        # verificar cancel antes de grupo
        if callable(cancel_check):
            try:
                if bool(cancel_check()):
                    # cancelar restantes grupos
                    pendientes = []
                    idx_grupo = grupos_temp.index(grupo)
                    for g in grupos_temp[idx_grupo:]:
                        for v in g:
                            if v in temp_exitos:
                                # revertir temps del grupo pendiente
                                _rollback_temps({v})
                            if not any(c.get("video_id")==v for c in cancelados) and not any(f.get("video_id")==v for f in fallidos):
                                idx2 = next((p["indice"] for p in plan if p["video_id"]==v), -1)
                                cancelados.append({"video_id": v, "indice": idx2, "motivo": "cancelado"})
                                detalles.append({"video_id": v, "ok": False, "cancelado": True, "error": "cancelado", "tipo": "Cancelado", "indice": idx2})
                                if callable(progreso_callback):
                                    try:
                                        progreso_callback(idx2+1, total)
                                    except Exception as _b77_exc:
                                        detalles.append({"video_id": v, "ok": False, "error": f"progreso_callback falló: {_b77_exc}", "tipo": type(_b77_exc).__name__, "indice": idx2, "fase": "progreso_callback", "advertencia": True})
                    # también simples ya hechos, solo falta marcar cancel
                    cancelado_global = True
                    break
            except Exception as exc:
                for v in grupo:
                    idx2 = next((p["indice"] for p in plan if p["video_id"]==v), -1)
                    fallidos.append({"video_id": v, "error": f"cancel_check falló: {exc}", "tipo": type(exc).__name__, "indice": idx2})
                    detalles.append({"video_id": v, "ok": False, "error": f"cancel_check falló: {exc}", "tipo": type(exc).__name__, "indice": idx2})
                continue
        if cancelado_global:
            break
        finales_ok = set()
        fallo_en_grupo = None
        # ordenar miembros por indice plan
        for vid in sorted(grupo, key=lambda v: next((p["indice"] for p in plan if p["video_id"]==v), 9999)):
            if callable(cancel_check):
                try:
                    if bool(cancel_check()):
                        fallo_en_grupo = Exception("cancelado")
                        break
                except Exception as exc:
                    fallidos.append({"video_id": vid, "error": f"cancel_check falló: {exc}", "tipo": type(exc).__name__, "indice": next((p["indice"] for p in plan if p["video_id"]==vid), -1)})
                    detalles.append({"video_id": vid, "ok": False, "error": f"cancel_check falló: {exc}", "tipo": type(exc).__name__, "indice": next((p["indice"] for p in plan if p["video_id"]==vid), -1)})
                    fallo_en_grupo = exc
                    break
            item = next((x for x in plan if x["video_id"]==vid), None)
            if item is None or vid not in temp_exitos:
                continue
            origen_nombre = temp_exitos[vid]["nombre"]
            origen_ruta = temp_exitos[vid]["ruta"]
            dest_nombre = item["nombre_final"]
            dest_ruta = item["ruta_final"]
            try:
                res = _renombrar_un_video_atomico(vid, origen_nombre, dest_nombre, origen_ruta, dest_ruta, ruta_db)
                exitosos.append({"video_id": vid, "resultado": res, "indice": item["indice"]})
                detalles.append({"video_id": vid, "ok": True, "resultado": res, "indice": item["indice"]})
                finales_ok.add(vid)
            except Exception as exc:
                idx = item["indice"]
                fallidos.append({"video_id": vid, "error": str(exc), "tipo": type(exc).__name__, "excepcion": exc, "indice": idx})
                detalles.append({"video_id": vid, "ok": False, "error": str(exc), "tipo": type(exc).__name__, "excepcion": exc, "indice": idx})
                fallo_en_grupo = exc
                break
            finally:
                if callable(progreso_callback):
                    try:
                        progreso_callback(item["indice"]+1, total)
                    except Exception as _b77_exc:
                        detalles.append({"video_id": item["video_id"] if item else vid, "ok": False, "error": f"progreso_callback falló: {_b77_exc}", "tipo": type(_b77_exc).__name__, "indice": item["indice"] if item else -1, "fase": "progreso_callback", "advertencia": True})
        if fallo_en_grupo is not None:
            # rollback atómico del grupo: revertir finales_ok y temps restantes
            # primero remover de exitosos los que se habían marcado como éxito en este grupo
            for v in list(finales_ok):
                # quitar de exitosos
                exitosos[:] = [e for e in exitosos if e.get("video_id") != v]
                detalles[:] = [d for d in detalles if not (d.get("video_id")==v and d.get("ok")==True)]
            errs = _rollback_finales_y_temps(grupo, finales_ok)
            if errs:
                msg = f"ERROR CRÍTICO rollback grupo {sorted(grupo)} tras fallo '{fallo_en_grupo}': {'; '.join(errs)} — evidencia preservada (posible __tmp_mass_* residual requiere intervención manual)"
                # marcar todos los vids del grupo como fallidos críticos si no ya fallidos
                for v in grupo:
                    idx2 = next((p["indice"] for p in plan if p["video_id"]==v), -1)
                    if not any(f.get("video_id")==v for f in fallidos):
                        fallidos.append({"video_id": v, "error": msg, "tipo": "CompensacionFalloError", "indice": idx2})
                        detalles.append({"video_id": v, "ok": False, "error": msg, "tipo": "CompensacionFalloError", "indice": idx2, "fase": "compensacion"})
                    else:
                        # anexar detalle de compensación a fallido existente
                        for f in fallidos:
                            if f.get("video_id")==v:
                                f["error"] = f.get("error","") + f" | {msg}"
            else:
                # rollback exitoso: asegurar que todos los miembros del grupo queden como fallidos (revertidos)
                for v in grupo:
                    idx2 = next((p["indice"] for p in plan if p["video_id"]==v), -1)
                    if not any(f.get("video_id")==v for f in fallidos):
                        # si tenía éxito final que fue revertido, ya quitado; ahora marcar como fallido revertido
                        fallidos.append({"video_id": v, "error": f"revertido por fallo atómico en ciclo/grupo: {fallo_en_grupo}", "tipo": type(fallo_en_grupo).__name__, "indice": idx2})
                        detalles.append({"video_id": v, "ok": False, "error": f"revertido por fallo atómico en ciclo/grupo: {fallo_en_grupo}", "tipo": type(fallo_en_grupo).__name__, "indice": idx2, "fase": "rollback_grupo"})
                    # si ya tenía fallido por el que disparó rollback, ya está
                # también necesitamos asegurar que no quede temp residual visible: verificación
            # progreso ya reportado por iteración
            continue
        # si grupo completó sin fallo, nada más
    # Verificación final: no debe quedar ningún __tmp_mass_* en FS de directorios involucrados
    # Si queda, intentar limpieza y reportar inconsistencia pero no ocultar
    try:
        dirs_verif = {p["directorio"] for p in plan}
        for d in dirs_verif:
            real_d = d
            if not os.path.isdir(real_d):
                try:
                    real_d = os.path.abspath(d)
                except Exception:
                    continue
                if not os.path.isdir(real_d):
                    continue
            try:
                lst = os.listdir(real_d)
            except OSError:
                continue
            try:
                for fname in lst:
                    if fname.startswith("__tmp_mass_"):
                        if any(rec.get("nombre") == fname for rec in temp_exitos.values()):
                            msg = f"temporal residual detectado {os.path.join(real_d,fname)} tras ejecución — inconsistencia crítica"
                            detalles.append({"video_id": None, "ok": False, "error": msg, "tipo": "TemporalResidual", "indice": -1})
                        else:
                            try:
                                os.remove(os.path.join(real_d, fname))
                            except OSError:
                                detalles.append({"video_id": None, "ok": False, "error": f"no se pudo limpiar temporal huérfano {fname}", "tipo": "LimpiezaTemporalFallo", "indice": -1})
            except Exception as _b77_exc:
                detalles.append({"video_id": None, "ok": False, "error": f"no se pudo verificar temporales en {real_d!r}: {_b77_exc}", "tipo": type(_b77_exc).__name__, "indice": -1, "fase": "verificacion_temporal", "advertencia": True})
    except Exception as _b77_exc:
        detalles.append({"video_id": None, "ok": False, "error": f"fallo verificación final de temporales: {_b77_exc}", "tipo": type(_b77_exc).__name__, "indice": -1, "fase": "verificacion_temporal", "advertencia": True})

    # Ordenar detalles por indice - si falla, registrar advertencia y retornar sin ordenar
    try:
        detalles = sorted(detalles, key=lambda d: d.get("indice", 0))
    except Exception as _b77_exc:
        detalles.append({"video_id": None, "ok": False, "error": f"no se pudo ordenar detalles finales: {_b77_exc}", "tipo": type(_b77_exc).__name__, "indice": -1, "fase": "ordenamiento", "advertencia": True})
    procesados = len(exitosos) + len(fallidos)
    return {
        "total": total,
        "procesados": procesados,
        "exitosos": exitosos,
        "fallidos": fallidos,
        "cancelados": cancelados,
        "detalles": detalles,
        "exitosos_count": len(exitosos),
        "fallidos_count": len(fallidos),
        "cancelados_count": len(cancelados),
        "plan": plan,
    }

