"""Prueba B7.13C corregida — prevalidación atómica antes de mover (VisorVideos -> TareaPrevalidarDrop -> TareaLoteOperaciones)."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import sys
import tempfile
import shutil
import time
import inspect

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QDragEnterEvent

from escanear_videos import conectar_bd
import visor_videos as vv
import panel_organizacion as po
from tareas_videos import TareaLoteOperaciones, TareaPrevalidarDrop

app = QApplication.instance() or QApplication(sys.argv)

_CONT = 0
_FAIL = 0

def ok(m):
    global _CONT
    _CONT += 1
    print(f"T{_CONT:02d} OK - {m}")

def falla(m, e=None):
    global _CONT, _FAIL
    _CONT += 1
    _FAIL += 1
    print(f"T{_CONT:02d} FAIL - {m} {e or ''}")

def verifica(cond, desc, extra=None):
    if cond:
        ok(desc)
    else:
        falla(desc, extra)

def _fila(nombre, vid, ruta):
    return (nombre, 10.0, 640, 480, "h264", 1, 1024, ruta, vid)

def _esperar_carga(v, timeout=3.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        app.processEvents()
        try:
            activo = bool(getattr(v.gestor, "activo", False))
        except Exception:
            activo = False
        if not activo:
            app.processEvents()
            break
        time.sleep(0.02)
    app.processEvents()
    time.sleep(0.05)
    app.processEvents()

def _esperar_prevalidacion_y_lote(visor, timeout=8.0):
    """Espera a que prevalidación y eventual lote terminen; procesa eventos."""
    t0 = time.time()
    # primero esperar prevalidacion
    while time.time() - t0 < timeout:
        app.processEvents()
        try:
            pre_act = bool(getattr(visor.gestor_prevalidacion_drop, "activo", False))
            pre_flag = bool(getattr(visor, "_prevalidacion_drop_en_curso", False))
            lote_act = bool(getattr(visor.gestor_lote, "activo", False))
            lote_flag = bool(getattr(visor, "_lote_en_curso", False))
        except Exception:
            pre_act = pre_flag = lote_act = lote_flag = False
        if not pre_act and not pre_flag and not lote_act and not lote_flag:
            # si nunca se inició nada, salir pronto después de un breve lapso para fallo
            # pero necesitamos distinguir rechazos sin lote: pre también inactivo rápidamente
            # Esperar al menos 0.4s para que background haya ejecutado
            if time.time() - t0 > 0.6:
                break
        if not pre_act and not pre_flag:
            # prevalidación terminó; si lote inició, esperar lote
            if lote_act or lote_flag:
                # seguir esperando lote
                pass
            else:
                if time.time() - t0 > 0.7:
                    break
        time.sleep(0.03)
        app.processEvents()
    time.sleep(0.15)
    app.processEvents()

def _crear_visor_con_videos():
    tmp = tempfile.mkdtemp()
    db = os.path.join(tmp, "test.db")
    conn = conectar_bd(db)
    conn.commit()
    conn.close()
    carpeta_videos = os.path.join(tmp, "origen")
    os.makedirs(carpeta_videos, exist_ok=True)
    dest_root = os.path.join(tmp, "dest_root")
    os.makedirs(dest_root, exist_ok=True)
    sub = os.path.join(dest_root, "subcarpeta")
    os.makedirs(sub, exist_ok=True)
    otra = os.path.join(dest_root, "otra")
    os.makedirs(otra, exist_ok=True)
    vids = []
    for name in ["video_a.mp4", "video_b.mp4", "video_c.mp4"]:
        ruta = os.path.join(carpeta_videos, name)
        open(ruta, "wb").write(b"x" * 2048)
        st = os.stat(ruta)
        c = conectar_bd(db)
        c.execute("INSERT INTO videos (nombre,ruta,extension,fecha_importacion,tamano_bytes,mtime_ns) VALUES (?,?,?,?,?,?)",
                  (name, os.path.abspath(ruta), ".mp4", "2026-01-01", st.st_size, st.st_mtime_ns))
        row = c.execute("SELECT id FROM videos WHERE nombre=?", (name,)).fetchone()
        vid = row[0]
        vids.append((name, vid, os.path.abspath(ruta)))
        c.commit()
        c.close()
    ruta_config = os.path.join(tmp, "config.json")
    visor = vv.VisorVideos(ruta_db=db, ruta_config=ruta_config)
    visor.resize(900, 600)
    visor.show()
    _esperar_carga(visor, timeout=3.0)
    filas = [_fila(n, vid, ruta) for n, vid, ruta in vids]
    visor._reemplazar_tarjetas(filas)
    app.processEvents()
    time.sleep(0.05)
    app.processEvents()
    visor.boton_modo_organizacion.setChecked(True)
    app.processEvents()
    time.sleep(0.08)
    app.processEvents()
    visor._organizacion_destino = dest_root
    visor._organizacion_destino_valido = True
    visor._organizacion_subcarpetas = ["subcarpeta", "otra"]
    visor._organizacion_error = None
    visor._organizacion_cargando = False
    visor._organizacion_objetivo_nombre = None
    visor._organizacion_objetivo_completo = None
    visor._actualizar_panel_organizacion()
    app.processEvents()
    return visor, tmp, db, carpeta_videos, dest_root, sub, vids

print("=== B7.13C corregida prueba_drag_movimiento_b713c ===")

# --- Setup base para tests rápidos de validación sin mover archivos (usa real prevalidación) ---
# Tests 1-9 usan visor real con gestors reales, pero operaciones son rápidas
# Para evitar mover archivos innecesariamente, los tests de rechazo verifican que NO se movió

# Helper para contar lotes iniciados: interceptar _iniciar_lote_drop_real sin romper prevalidación
# En su lugar verificamos estado final: si lote se inició, _lote_en_curso/gestor_lote.activo y archivos movidos

# T01: [99999] inexistente -> cero lote, cero archivos movidos
print("--- T01 [99999] inexistente -> cero lote ---")
visor, tmp_base, db_base, origen_base, dest_root_base, sub_base, vids_base = _crear_visor_con_videos()
vids_ids = [vid for name, vid, ruta in vids_base]
orig_rutas = {vid: ruta for name, vid, ruta in vids_base}
# guardar tamaños antes
for name, vid, ruta in vids_base:
    assert os.path.isfile(ruta)
visor._al_drop_videos_solicitado([99999], None)
_esperar_prevalidacion_y_lote(visor, timeout=5.0)
# verificar que ningún lote se inició (gestor_lote no activo ni en curso, y mensaje de rechazo)
verifica(not getattr(visor, "_lote_en_curso", False) and not getattr(visor.gestor_lote, "activo", False), "T01 cero lote en_curso/activo")
verifica("rechazado" in visor.mensaje_carpeta.text().lower() or "inexistente" in visor.mensaje_carpeta.text().lower(), f"T01 mensaje rechazo {visor.mensaje_carpeta.text()!r}")
# archivos deben permanecer
for name, vid, ruta in vids_base:
    verifica(os.path.isfile(ruta), f"T01 archivo permanece {name}")
    # DB sin cambios
    c = conectar_bd(db_base)
    row = c.execute("SELECT ruta FROM videos WHERE id=?", (vid,)).fetchone()
    c.close()
    verifica(row is not None and os.path.normcase(row[0]) == os.path.normcase(ruta), f"T01 DB sin cambio {name}")
visor.close()
for g in ["gestor","gestor_previews","gestor_navegacion_destino","gestor_lote","gestor_prevalidacion_drop","gestor_renombrar_masivo","gestor_mover","gestor_copiar","gestor_eliminar"]:
    try:
        getattr(visor, g).cerrar()
    except Exception:
        pass
shutil.rmtree(tmp_base, ignore_errors=True)

# T02: [ID válido, 99999] -> cero lote, archivo válido permanece
print("--- T02 [válido, 99999] -> cero lote ---")
visor, tmp_base, db_base, origen_base, dest_root_base, sub_base, vids_base = _crear_visor_con_videos()
vids_ids = [vid for name, vid, ruta in vids_base]
valid = vids_ids[0]
visor._al_drop_videos_solicitado([valid, 99999], None)
_esperar_prevalidacion_y_lote(visor, timeout=5.0)
verifica(not getattr(visor, "_lote_en_curso", False) and not getattr(visor.gestor_lote, "activo", False), "T02 cero lote")
for name, vid, ruta in vids_base:
    verifica(os.path.isfile(ruta), f"T02 archivo permanece {name}")
    # destino no debe tener el válido
    verifica(not os.path.isfile(os.path.join(dest_root_base, name)) or name not in [v[0] for v in vids_base if v[1]==valid], f"T02 destino no creado {name}")
visor.close()
for g in ["gestor","gestor_previews","gestor_navegacion_destino","gestor_lote","gestor_prevalidacion_drop"]:
    try: getattr(visor,g).cerrar()
    except: pass
shutil.rmtree(tmp_base, ignore_errors=True)

# T03: [99999, ID válido] -> cero lote
print("--- T03 [99999, válido] -> cero lote ---")
visor, tmp_base, db_base, origen_base, dest_root_base, sub_base, vids_base = _crear_visor_con_videos()
vids_ids = [vid for name, vid, ruta in vids_base]
valid = vids_ids[1]
visor._al_drop_videos_solicitado([99999, valid], None)
_esperar_prevalidacion_y_lote(visor, timeout=5.0)
verifica(not getattr(visor, "_lote_en_curso", False), "T03 cero lote")
for name, vid, ruta in vids_base:
    verifica(os.path.isfile(ruta), f"T03 permanece {name}")
visor.close()
for g in ["gestor","gestor_previews","gestor_navegacion_destino","gestor_lote","gestor_prevalidacion_drop"]:
    try: getattr(visor,g).cerrar()
    except: pass
shutil.rmtree(tmp_base, ignore_errors=True)

# T04: todos válidos -> exactamente un lote
print("--- T04 todos válidos -> un lote ---")
visor, tmp_base, db_base, origen_base, dest_root_base, sub_base, vids_base = _crear_visor_con_videos()
vids_ids = [vid for name, vid, ruta in vids_base]
ids_move = [vids_ids[0], vids_ids[1]]
visor._al_drop_videos_solicitado(ids_move, None)
_esperar_prevalidacion_y_lote(visor, timeout=8.0)
# debe haber iniciado lote y terminado: verificar archivos movidos y DB
# esperar un poco más por recarga catalogo? pero archivo debe estar movido ya
time.sleep(0.3)
app.processEvents()
# verificar que lote se ejecutó (mensaje Moviendo o completado)
msg = visor.mensaje_carpeta.text()
verifica("moviendo" in msg.lower() or "completado" in msg.lower() or "ok" in msg.lower(), f"T04 mensaje lote {msg!r}")
for name, vid, ruta in vids_base:
    ruta_dest = os.path.join(dest_root_base, name)
    if vid in ids_move:
        verifica(os.path.isfile(ruta_dest), f"T04 movido {name} a dest")
        verifica(not os.path.isfile(ruta), f"T04 origen eliminado {name}")
        c = conectar_bd(db_base)
        row = c.execute("SELECT ruta FROM videos WHERE id=?", (vid,)).fetchone()
        c.close()
        verifica(row and os.path.normcase(row[0]) == os.path.normcase(ruta_dest), f"T04 DB actualizada {name}")
    else:
        verifica(os.path.isfile(ruta), f"T04 no movido permanece {name}")
visor.close()
for g in ["gestor","gestor_previews","gestor_navegacion_destino","gestor_lote","gestor_prevalidacion_drop"]:
    try: getattr(visor,g).cerrar()
    except: pass
shutil.rmtree(tmp_base, ignore_errors=True)

# T05: destino inexistente antes de comenzar -> cero lote
print("--- T05 destino inexistente -> cero lote ---")
visor, tmp_base, db_base, origen_base, dest_root_base, sub_base, vids_base = _crear_visor_con_videos()
vids_ids = [vid for name, vid, ruta in vids_base]
# eliminar destino root físicamente antes de drop
shutil.rmtree(dest_root_base, ignore_errors=True)
# mantener flag valido True para simular que UI no se enteró aún, pero worker detectará
visor._organizacion_destino = dest_root_base
visor._organizacion_destino_valido = True  # engañar para que pase sintáctica y llegue a prevalidación
visor._organizacion_error = None
visor._organizacion_cargando = False
visor._actualizar_panel_organizacion()
app.processEvents()
visor._al_drop_videos_solicitado([vids_ids[0]], None)
_esperar_prevalidacion_y_lote(visor, timeout=5.0)
verifica(not getattr(visor, "_lote_en_curso", False) and not getattr(visor.gestor_lote, "activo", False), "T05 cero lote destino inexistente")
verifica("rechazado" in visor.mensaje_carpeta.text().lower() or "no disponible" in visor.mensaje_carpeta.text().lower() or "no disponible" in visor.mensaje_carpeta.text(), f"T05 mensaje rechazo {visor.mensaje_carpeta.text()!r}")
for name, vid, ruta in vids_base:
    verifica(os.path.isfile(ruta), f"T05 archivo permanece {name}")
visor.close()
for g in ["gestor","gestor_previews","gestor_navegacion_destino","gestor_lote","gestor_prevalidacion_drop"]:
    try: getattr(visor,g).cerrar()
    except: pass
shutil.rmtree(tmp_base, ignore_errors=True)

# T06: subcarpeta objetivo desaparecida -> cero lote
print("--- T06 subcarpeta desaparecida -> cero lote ---")
visor, tmp_base, db_base, origen_base, dest_root_base, sub_base, vids_base = _crear_visor_con_videos()
vids_ids = [vid for name, vid, ruta in vids_base]
# eliminar subcarpeta físicamente
shutil.rmtree(sub_base, ignore_errors=True)
visor._organizacion_destino = dest_root_base
visor._organizacion_subcarpetas = ["subcarpeta", "otra"]  # UI aún cree que existe
visor._organizacion_destino_valido = True
visor._organizacion_objetivo_nombre = "subcarpeta"
visor.panel_organizacion._objetivo_nombre = "subcarpeta"
visor._actualizar_panel_organizacion()
app.processEvents()
# destino resuelto será dest_root/subcarpeta que ya no existe
visor._al_drop_videos_solicitado([vids_ids[0]], "subcarpeta")
_esperar_prevalidacion_y_lote(visor, timeout=5.0)
verifica(not getattr(visor, "_lote_en_curso", False), "T06 cero lote subcarpeta desaparecida")
for name, vid, ruta in vids_base:
    verifica(os.path.isfile(ruta), f"T06 permanece {name}")
visor.close()
for g in ["gestor","gestor_previews","gestor_navegacion_destino","gestor_lote","gestor_prevalidacion_drop"]:
    try: getattr(visor,g).cerrar()
    except: pass
shutil.rmtree(tmp_base, ignore_errors=True)

# T07: validación ocurre fuera de UI/SQLite directo
print("--- T07 validación fuera de UI ---")
# inspeccionar handler no hace sqlite/os path directo; delega a tareas
src_handler = inspect.getsource(vv.VisorVideos._al_drop_videos_solicitado)
verifica("TareaPrevalidarDrop" in src_handler, "T07 handler usa TareaPrevalidarDrop")
verifica("gestor_prevalidacion_drop.iniciar" in src_handler, "T07 handler usa gestor_prevalidacion_drop")
for kw in ["sqlite3", "conectar_bd", "os.path.isdir", "os.path.isfile", "os.path.exists", "shutil"]:
    verifica(kw not in src_handler, f"T07 handler sin {kw}")
# inspeccionar tarea sí usa helpers centralizados
src_tarea = inspect.getsource(TareaPrevalidarDrop)
verifica("listar_videos_por_ids" in src_tarea, "T07 tarea usa listar_videos_por_ids")
verifica("listar_subcarpetas" in src_tarea, "T07 tarea usa listar_subcarpetas")
verifica("validar_destino_drop_completo" in src_tarea, "T07 tarea usa validar_destino_drop_completo")
# handler no importa sqlite
verifica("import sqlite3" not in src_handler, "T07 handler sin import sqlite3")

# T08: no copy/delete
print("--- T08 no copy/delete ---")
verifica('"copiar"' not in src_handler and "'copiar'" not in src_handler, "T08 sin copiar")
verifica('"eliminar"' not in src_handler and "'eliminar'" not in src_handler, "T08 sin eliminar")
# también verificar que _iniciar_lote_drop_real solo usa mover
src_real = inspect.getsource(vv.VisorVideos._iniciar_lote_drop_real)
verifica('"mover"' in src_real and '"copiar"' not in src_real, "T08 _iniciar_lote_drop_real solo mover")

# T09: señal duplicada no crea doble lote mientras prevalidación/lote ocupado
print("--- T09 duplicada no doble lote ---")
visor, tmp_base, db_base, origen_base, dest_root_base, sub_base, vids_base = _crear_visor_con_videos()
vids_ids = [vid for name, vid, ruta in vids_base]
# emitir dos drops rápidos
visor._al_drop_videos_solicitado([vids_ids[0]], None)
# inmediatamente segunda señal antes de que prevalidación termine (debe rechazar por ocupado)
visor._al_drop_videos_solicitado([vids_ids[1]], None)
_esperar_prevalidacion_y_lote(visor, timeout=8.0)
# solo un lote debe haber movido (el primero) o rechazo del segundo; no dos lotes
# contar archivos movidos: solo uno debe estar en destino si segundo fue rechazado atomicamente
movidos = 0
for name, vid, ruta in vids_base:
    if os.path.isfile(os.path.join(dest_root_base, name)):
        movidos += 1
verifica(movidos == 1, f"T09 solo un lote movió 1 archivo (movidos={movidos})")
# además probar que duplicada mientras lote activo también rechaza
# Reiniciar visor limpio para segunda parte: mover 1 válido y durante lote intentar otro
visor.close()
for g in ["gestor","gestor_previews","gestor_navegacion_destino","gestor_lote","gestor_prevalidacion_drop"]:
    try: getattr(visor,g).cerrar()
    except: pass
shutil.rmtree(tmp_base, ignore_errors=True)

# Segunda parte: integración lote mixto vs lote válido completo ya probada en T02 vs T04, pero repetir mixto explícito con verificación cero movimiento
print("--- T10 integración lote mixto cero movimiento (explícito) ---")
visor, tmp_base, db_base, origen_base, dest_root_base, sub_base, vids_base = _crear_visor_con_videos()
vids_ids = [vid for name, vid, ruta in vids_base]
valid = vids_ids[0]
invalid = 99999
# guardar rutas antes
ruta_valid_antes = [r for n, vid, r in vids_base if vid == valid][0]
visor._al_drop_videos_solicitado([valid, invalid], None)
_esperar_prevalidacion_y_lote(visor, timeout=5.0)
verifica(os.path.isfile(ruta_valid_antes), "T10 mixto válido permanece en origen")
verifica(not os.path.isfile(os.path.join(dest_root_base, os.path.basename(ruta_valid_antes))), "T10 mixto destino no creado")
verifica(not getattr(visor, "_lote_en_curso", False), "T10 mixto cero lote")
visor.close()
for g in ["gestor","gestor_previews","gestor_navegacion_destino","gestor_lote","gestor_prevalidacion_drop"]:
    try: getattr(visor,g).cerrar()
    except: pass
shutil.rmtree(tmp_base, ignore_errors=True)

print("--- T11 integración lote válido completo mueve todo ---")
visor, tmp_base, db_base, origen_base, dest_root_base, sub_base, vids_base = _crear_visor_con_videos()
vids_ids = [vid for name, vid, ruta in vids_base]
ids_validos = vids_ids[:2]
visor._al_drop_videos_solicitado(ids_validos, None)
_esperar_prevalidacion_y_lote(visor, timeout=8.0)
time.sleep(0.2)
app.processEvents()
for name, vid, ruta in vids_base:
    dest_path = os.path.join(dest_root_base, name)
    if vid in ids_validos:
        verifica(os.path.isfile(dest_path), f"T11 movido {name}")
        verifica(not os.path.isfile(ruta), f"T11 origen eliminado {name}")
    else:
        verifica(os.path.isfile(ruta), f"T11 no movido {name}")
visor.close()
for g in ["gestor","gestor_previews","gestor_navegacion_destino","gestor_lote","gestor_prevalidacion_drop"]:
    try: getattr(visor,g).cerrar()
    except: pass
shutil.rmtree(tmp_base, ignore_errors=True)

# T12: destino raíz y subcarpeta válidos ya cubiertos, pero verificar regresión B7.13A/B básica
print("--- T12 regresión panel/visor ---")
visor, tmp_base, db_base, origen_base, dest_root_base, sub_base, vids_base = _crear_visor_con_videos()
verifica(hasattr(po, "MIME_VIDEOS_IDS"), "T12 MIME existe")
verifica(hasattr(visor.panel_organizacion, "dropVideosSolicitado"), "T12 señal existe")
# dragEnter válido sigue aceptando
from PySide6.QtCore import QMimeData, QByteArray
panel = visor.panel_organizacion
panel.resize(320,220)
panel.show()
app.processEvents()
m = QMimeData()
payload = po._serializar_ids_videos_para_mime([1,2])
m.setData(po.MIME_VIDEOS_IDS, QByteArray(payload))
ev = QDragEnterEvent(panel.rect().center(), Qt.CopyAction, m, Qt.LeftButton, Qt.NoModifier)
QApplication.sendEvent(panel, ev)
app.processEvents()
verifica(ev.isAccepted(), "T12 dragEnter acepta")
visor.close()
for g in ["gestor","gestor_previews","gestor_navegacion_destino","gestor_lote","gestor_prevalidacion_drop"]:
    try: getattr(visor,g).cerrar()
    except: pass
shutil.rmtree(tmp_base, ignore_errors=True)

# --- Nuevos casos fuente faltante (corrección final B7.13C) ---
# T13: un ID válido en DB cuyo archivo fuente fue eliminado -> cero lote
print("--- T13 archivo fuente faltante (1) -> cero lote ---")
visor, tmp_base, db_base, origen_base, dest_root_base, sub_base, vids_base = _crear_visor_con_videos()
vids_ids = [vid for name, vid, ruta in vids_base]
# eliminar físicamente el archivo del primer video
ruta_faltante = vids_base[0][2]
os.remove(ruta_faltante)
verifica(not os.path.isfile(ruta_faltante), "T13 precondición archivo eliminado")
visor._al_drop_videos_solicitado([vids_ids[0]], None)
_esperar_prevalidacion_y_lote(visor, timeout=5.0)
verifica(not getattr(visor, "_lote_en_curso", False) and not getattr(visor.gestor_lote, "activo", False), "T13 cero lote archivo faltante")
verifica("faltante" in visor.mensaje_carpeta.text().lower() or "fuente" in visor.mensaje_carpeta.text().lower() or "rechazado" in visor.mensaje_carpeta.text().lower(), f"T13 mensaje rechazo {visor.mensaje_carpeta.text()!r}")
# los otros archivos deben permanecer
for name, vid, ruta in vids_base[1:]:
    verifica(os.path.isfile(ruta), f"T13 otros permanecen {name}")
# destino no debe tener nada
verifica(not os.path.isfile(os.path.join(dest_root_base, vids_base[0][0])), "T13 destino no creado")
visor.close()
for g in ["gestor","gestor_previews","gestor_navegacion_destino","gestor_lote","gestor_prevalidacion_drop"]:
    try: getattr(visor,g).cerrar()
    except: pass
shutil.rmtree(tmp_base, ignore_errors=True)

# T14: mezcla [existente, faltante] -> cero lote, existente permanece
print("--- T14 mezcla [existente, faltante] -> cero lote ---")
visor, tmp_base, db_base, origen_base, dest_root_base, sub_base, vids_base = _crear_visor_con_videos()
vids_ids = [vid for name, vid, ruta in vids_base]
ruta_falt = vids_base[1][2]
os.remove(ruta_falt)
visor._al_drop_videos_solicitado([vids_ids[0], vids_ids[1]], None)
_esperar_prevalidacion_y_lote(visor, timeout=5.0)
verifica(not getattr(visor, "_lote_en_curso", False), "T14 cero lote mezcla existente+faltante")
ruta_exist = vids_base[0][2]
verifica(os.path.isfile(ruta_exist), "T14 existente permanece en origen")
verifica(not os.path.isfile(os.path.join(dest_root_base, vids_base[0][0])), "T14 destino no creado para existente")
visor.close()
for g in ["gestor","gestor_previews","gestor_navegacion_destino","gestor_lote","gestor_prevalidacion_drop"]:
    try: getattr(visor,g).cerrar()
    except: pass
shutil.rmtree(tmp_base, ignore_errors=True)

# T15: mezcla [faltante, existente] -> cero lote
print("--- T15 mezcla [faltante, existente] -> cero lote ---")
visor, tmp_base, db_base, origen_base, dest_root_base, sub_base, vids_base = _crear_visor_con_videos()
vids_ids = [vid for name, vid, ruta in vids_base]
os.remove(vids_base[0][2])
visor._al_drop_videos_solicitado([vids_ids[0], vids_ids[2]], None)
_esperar_prevalidacion_y_lote(visor, timeout=5.0)
verifica(not getattr(visor, "_lote_en_curso", False), "T15 cero lote faltante+existente")
verifica(os.path.isfile(vids_base[2][2]), "T15 existente permanece")
visor.close()
for g in ["gestor","gestor_previews","gestor_navegacion_destino","gestor_lote","gestor_prevalidacion_drop"]:
    try: getattr(visor,g).cerrar()
    except: pass
shutil.rmtree(tmp_base, ignore_errors=True)

# T16: tres IDs con el del medio faltante -> cero lote
print("--- T16 3 IDs medio faltante -> cero lote ---")
visor, tmp_base, db_base, origen_base, dest_root_base, sub_base, vids_base = _crear_visor_con_videos()
vids_ids = [vid for name, vid, ruta in vids_base]
os.remove(vids_base[1][2])
visor._al_drop_videos_solicitado(vids_ids, None)
_esperar_prevalidacion_y_lote(visor, timeout=5.0)
verifica(not getattr(visor, "_lote_en_curso", False), "T16 cero lote 3 con medio faltante")
for name, vid, ruta in vids_base:
    if vid == vids_ids[1]:
        verifica(not os.path.isfile(ruta), "T16 faltante sigue ausente")
    else:
        verifica(os.path.isfile(ruta), f"T16 otros permanecen {name}")
        verifica(not os.path.isfile(os.path.join(dest_root_base, name)), f"T16 destino no creado {name}")
visor.close()
for g in ["gestor","gestor_previews","gestor_navegacion_destino","gestor_lote","gestor_prevalidacion_drop"]:
    try: getattr(visor,g).cerrar()
    except: pass
shutil.rmtree(tmp_base, ignore_errors=True)

# T17: todos presentes -> exactamente un lote (control positivo fuente)
print("--- T17 todos presentes fuente -> un lote ---")
visor, tmp_base, db_base, origen_base, dest_root_base, sub_base, vids_base = _crear_visor_con_videos()
vids_ids = [vid for name, vid, ruta in vids_base]
visor._al_drop_videos_solicitado(vids_ids[:2], None)
_esperar_prevalidacion_y_lote(visor, timeout=8.0)
time.sleep(0.3)
app.processEvents()
for name, vid, ruta in vids_base:
    dest_path = os.path.join(dest_root_base, name)
    if vid in vids_ids[:2]:
        verifica(os.path.isfile(dest_path), f"T17 movido {name}")
        verifica(not os.path.isfile(ruta), f"T17 origen eliminado {name}")
    else:
        verifica(os.path.isfile(ruta), f"T17 no movido {name}")
visor.close()
for g in ["gestor","gestor_previews","gestor_navegacion_destino","gestor_lote","gestor_prevalidacion_drop"]:
    try: getattr(visor,g).cerrar()
    except: pass
shutil.rmtree(tmp_base, ignore_errors=True)

# T18: validación archivo fuente ocurre fuera de UI (tarea, no handler)
print("--- T18 validación fuente fuera de UI ---")
src_handler2 = inspect.getsource(vv.VisorVideos._al_drop_videos_solicitado)
# handler no debe usar isfile directamente
verifica("os.path.isfile" not in src_handler2, "T18 handler sin isfile")
verifica("os.path.exists" not in src_handler2, "T18 handler sin exists")
src_tarea2 = inspect.getsource(TareaPrevalidarDrop)
verifica("isfile" in src_tarea2, "T18 tarea sí usa isfile para fuente")
verifica("listar_videos_por_ids" in src_tarea2, "T18 tarea usa listar_videos_por_ids")

print(f"TOTAL={_CONT-_FAIL}/{_CONT}")
if _FAIL == 0:
    print("RESULTADO_FINAL=OK")
else:
    print("RESULTADO_FINAL=ERROR")
    sys.exit(1)
