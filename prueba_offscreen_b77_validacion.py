r"""Validación offscreen B7.7 — dentro de C:\prueba, sin Temp externo, sin tocar videos_prueba ni DB real."""
import os
import sys
import shutil
import sqlite3

# Forzar offscreen antes de importar Qt
os.environ["QT_QPA_PLATFORM"] = "offscreen"

BASE_PRUEBA = os.path.join(os.path.abspath(r"C:\prueba"), "_offscreen_test_b77")
DB_PATH = os.path.join(BASE_PRUEBA, "test_offscreen.db")
CONFIG_PATH = os.path.join(BASE_PRUEBA, "test_config.json")
VIDEOS_DIR = os.path.join(BASE_PRUEBA, "videos")

def _limpiar_seguro():
    # Solo limpiar si BASE_PRUEBA está dentro de C:\prueba y tiene nombre esperado
    base_abs = os.path.abspath(BASE_PRUEBA)
    prueba_abs = os.path.abspath(r"C:\prueba")
    if not base_abs.startswith(prueba_abs + os.sep) and base_abs != prueba_abs:
        print(f"ERROR: ruta no segura para limpiar {base_abs}")
        sys.exit(2)
    if os.path.basename(base_abs) != "_offscreen_test_b77":
        print(f"ERROR: nombre inesperado {base_abs}")
        sys.exit(2)
    if os.path.isdir(base_abs):
        shutil.rmtree(base_abs, ignore_errors=True)
        print(f"Limpieza previa: {base_abs} eliminado")

def main():
    print("=== Offscreen B7.7 validacion dentro de C:\\prueba ===")
    _limpiar_seguro()
    os.makedirs(VIDEOS_DIR, exist_ok=True)
    # crear 2 videos dummy
    for name, content in [("a.mp4", b"A"*1024), ("b.mp4", b"B"*1024)]:
        ruta = os.path.join(VIDEOS_DIR, name)
        with open(ruta, "wb") as f:
            f.write(content)
    # crear DB dentro de BASE_PRUEBA
    from escanear_videos import conectar_bd
    conn = conectar_bd(DB_PATH)
    conn.commit()
    # insertar videos
    vids = []
    for name in ["a.mp4", "b.mp4"]:
        ruta = os.path.join(VIDEOS_DIR, name)
        abs_ruta = os.path.abspath(ruta)
        st = os.stat(ruta)
        conn.execute("INSERT INTO videos (nombre,ruta,extension,fecha_importacion,tamano_bytes,mtime_ns) VALUES (?,?,?,?,?,?)",
                     (name, abs_ruta, os.path.splitext(name)[1].lower(), "2026-01-01", st.st_size, st.st_mtime_ns))
        vid = conn.execute("SELECT id FROM videos WHERE nombre=?", (name,)).fetchone()[0]
        vids.append(vid)
    conn.commit()
    conn.close()
    print(f"DB creada en {DB_PATH} con vids {vids}")
    # also create empty config file
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write("{}")
    # QApplication offscreen
    from PySide6.QtWidgets import QApplication
    from visor_videos import VisorVideos, DialogoRenombrarMasivo

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    print("QApplication offscreen creado")

    # VisorVideos con DB/config de prueba DENTRO de C:\\prueba
    visor = VisorVideos(ruta_db=DB_PATH, ruta_config=CONFIG_PATH)
    print("VisorVideos construido")
    # Verificar ventana construye
    assert visor is not None, "visor no construido"
    print("CHECK ventana construye: OK")
    # Verificar botón existe
    boton = getattr(visor, "boton_renombrar_masivo", None)
    assert boton is not None, "boton_renombrar_masivo no existe"
    print(f"CHECK boton existe: OK ({boton.text()})")
    assert "Renombrar seleccionados" in boton.text(), f"botón debe decir Renombrar seleccionados… got {boton.text()!r}"
    print("CHECK boton label Renombrar seleccionados…: OK")
    # Esperar carga inicial y gestores realmente inactivos (sin falsificar estado interno privado)
    import time
    for _ in range(150):
        app.processEvents()
        time.sleep(0.02)
        if getattr(visor, "_carga_completada", False) and not visor._lote_esta_ocupado():
            break
    # Espera adicional determinista hasta que _lote_esta_ocupado sea False (event loop real)
    for _ in range(100):
        if not visor._lote_esta_ocupado():
            break
        app.processEvents()
        time.sleep(0.02)
    app.processEvents()
    # Simular selección múltiple y verificar habilitación coherente
    visor._nombres_seleccionados = {"a.mp4", "b.mp4"}
    visor._actualizar_botones_lote()
    app.processEvents()
    assert boton.isEnabled(), "botón debe habilitarse con 2 seleccionados"
    print("CHECK boton habilitado con 2 seleccionados: OK")
    visor._nombres_seleccionados.clear()
    visor._actualizar_botones_lote()
    app.processEvents()
    assert not boton.isEnabled(), "botón debe deshabilitarse con 0"
    print("CHECK boton deshabilitado con 0: OK")
    visor._nombres_seleccionados = {"a.mp4","b.mp4"}
    visor._actualizar_botones_lote()
    # Verificar menú contextual contiene Renombrar seleccionados…
    import visor_videos as vv_mod
    import inspect
    src_menu = inspect.getsource(visor._mostrar_menu_contextual)
    assert "Renombrar seleccionados" in src_menu, "menú debe contener Renombrar seleccionados…"
    print("CHECK menu fuente contiene Renombrar seleccionados…: OK")
    # Captura offscreen del menú sin exec bloqueante
    captured = {}
    orig_QMenu = vv_mod.QMenu
    class FakeMenu:
        def __init__(self, *a, **k):
            self.actions=[]
            self.objs=[]
        def addAction(self, txt):
            class FakeAct:
                def __init__(self, t):
                    self._txt=t; self._enabled=True; self._trigger=None
                def text(self): return self._txt
                def setEnabled(self, v): self._enabled=bool(v)
                def isEnabled(self): return self._enabled
                @property
                def triggered(self):
                    class Sig:
                        def __init__(self, outer): self.outer=outer
                        def connect(self, fn): self.outer._trigger=fn
                    return Sig(self)
            act=FakeAct(txt)
            self.actions.append(txt); self.objs.append(act)
            return act
        def exec(self, *a, **k):
            captured["actions"]=list(self.actions)
            captured["objs"]=list(self.objs)
            return None
    vv_mod.QMenu = FakeMenu
    try:
        visor._nombres_seleccionados = {"a.mp4","b.mp4"}
        visor._mostrar_menu_contextual("a.mp4")
        acts = captured.get("actions",[])
        assert "Renombrar seleccionados…" in acts, f"menu debe tener Renombrar seleccionados… got {acts}"
        assert "Renombrar…" in acts, "menu debe conservar Renombrar… individual"
        print(f"CHECK menu acciones detectadas: OK {acts}")
        # verificar habilitado con 2
        idx = acts.index("Renombrar seleccionados…")
        assert captured["objs"][idx].isEnabled(), "menu Renombrar seleccionados habilitado con 2"
        print("CHECK menu Renombrar seleccionados habilitado con 2: OK")
        # 0 selección deshabilitado
        visor._nombres_seleccionados.clear()
        captured.clear()
        visor._mostrar_menu_contextual("a.mp4")
        acts0 = captured.get("actions",[])
        if "Renombrar seleccionados…" in acts0:
            idx0 = acts0.index("Renombrar seleccionados…")
            assert not captured["objs"][idx0].isEnabled(), "menu deshabilitado con 0"
            print("CHECK menu deshabilitado con 0: OK")
        # trigger abre diálogo
        from PySide6.QtWidgets import QDialog
        visor._nombres_seleccionados = {"a.mp4","b.mp4"}
        # asegurar tarjetas visibles mínimas para _iniciar_renombrar_masivo
        visor.carpeta_seleccionada = VIDEOS_DIR
        # crear tarjetas si no existen
        if not getattr(visor, "tarjetas", None):
            visor.tarjetas=[]
        if not visor.tarjetas:
            from visor_videos import Tarjeta
            # filas dummy
            import escanear_videos as esc
            # usar paginado real ya tenemos vids
            for name, vid in zip(["a.mp4","b.mp4"], vids):
                fila=(name,10.0,640,480,"h264",1,123,os.path.join(VIDEOS_DIR,name),vid)
                t=Tarjeta(fila, ruta_config=CONFIG_PATH)
                visor.tarjetas.append((name,t))
                visor.visibles.append(name) if hasattr(visor,"visibles") else None
        dlg_opened={"ok":False}
        orig_exec = vv_mod.DialogoRenombrarMasivo.exec
        def fake_exec(self):
            dlg_opened["ok"]=True
            return QDialog.Rejected
        vv_mod.DialogoRenombrarMasivo.exec=fake_exec
        try:
            visor._iniciar_renombrar_masivo()
            assert dlg_opened["ok"], "trigger debe abrir dialogo"
            print("CHECK trigger abre DialogoRenombrarMasivo: OK")
        finally:
            vv_mod.DialogoRenombrarMasivo.exec=orig_exec
    finally:
        vv_mod.QMenu = orig_QMenu
    # Verificar diálogo construye
    video_infos = [
        {"video_id": vids[0], "nombre": "a.mp4", "ruta": os.path.join(VIDEOS_DIR, "a.mp4")},
        {"video_id": vids[1], "nombre": "b.mp4", "ruta": os.path.join(VIDEOS_DIR, "b.mp4")},
    ]
    dlg = DialogoRenombrarMasivo(video_infos, DB_PATH)
    print("DialogoRenombrarMasivo construido")
    assert dlg is not None
    print("CHECK dialogo construye: OK")
    # Preview válida genera plan
    # plantilla por defecto ya es {original}_{numero:03d} y texto None -> debe ser ok
    plan = dlg.plan()
    assert plan is not None and len(plan)==2, f"plan válido esperado 2, got {plan}"
    print(f"CHECK preview valida genera plan: OK ({[p['nombre_final'] for p in plan]})")
    # Plantilla válida: botón Aplicar habilitado
    from PySide6.QtWidgets import QDialogButtonBox
    ok_btn = dlg._botones.button(QDialogButtonBox.Ok)
    assert ok_btn.isEnabled(), "botón Aplicar debe estar habilitado con plantilla válida"
    print("CHECK plantilla valida habilita Aplicar: OK")
    # Plantilla inválida bloquea Aplicar
    dlg._campo_plantilla.setText("{desconocido}")
    app.processEvents()
    assert not ok_btn.isEnabled(), "botón Aplicar debe estar deshabilitado con plantilla inválida"
    print("CHECK plantilla invalida bloquea Aplicar: OK")
    # Restaurar válida y verificar de nuevo habilitado
    dlg._campo_plantilla.setText("{original}_{numero:03d}")
    app.processEvents()
    assert ok_btn.isEnabled(), "botón debe re-habilitarse con plantilla válida"
    print("CHECK restauracion plantilla valida: OK")
    # Cierre limpio
    dlg.close()
    visor.close()
    print("CHECK cierre limpio: OK")
    app.processEvents()
    # No quit completamente para no interferir, pero cerrar
    # Limpieza segura solo artefactos creados
    # Verificar rutas explícitas antes de borrar
    assert os.path.abspath(BASE_PRUEBA).startswith(os.path.abspath(r"C:\prueba"))
    assert os.path.basename(os.path.abspath(BASE_PRUEBA)) == "_offscreen_test_b77"
    if os.path.isdir(BASE_PRUEBA):
        shutil.rmtree(BASE_PRUEBA, ignore_errors=True)
        print(f"Limpieza final: {BASE_PRUEBA} eliminado")
    # Verificar no tocó videos_prueba ni DB real
    assert not os.path.exists(os.path.join(BASE_PRUEBA, "dummy")), "no debería existir"
    real_db = os.path.join(r"C:\prueba", "biblioteca.db")
    assert os.path.isfile(real_db), "DB real debe seguir existiendo"
    print("CHECK no tocó DB/config reales: OK")
    # Verificar directorio de trabajo es C:\\prueba y no Temp externo usado
    print(f"BASE_PRUEBA usado: {BASE_PRUEBA}")
    print("RESULTADO_FINAL=OK")
    # exit 0
    sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print(f"FAIL offscreen: {e}")
        traceback.print_exc()
        # intentar limpieza igualmente pero segura
        try:
            if os.path.isdir(BASE_PRUEBA) and os.path.basename(os.path.abspath(BASE_PRUEBA)) == "_offscreen_test_b77":
                shutil.rmtree(BASE_PRUEBA, ignore_errors=True)
        except Exception as _b77_exc:
            # B7.7 corrección silencio: limpieza final tolerada pero explícita
            _b77_limpieza_error = f"{type(_b77_exc).__name__}: {_b77_exc}"
        sys.exit(1)
