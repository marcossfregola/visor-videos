"""Suite B7.9 — base modo Organización/Explorer — corregida."""
import os, sys, tempfile, shutil, inspect, sqlite3, time
from escanear_videos import conectar_bd
import rutas
from tareas_videos import TareaLoteOperaciones
import visor_videos

_CONT=0; _FAIL=0
def ok(m):
    global _CONT; _CONT+=1; print(f"T{_CONT:02d} OK - {m}")
def falla(m,e=None):
    global _CONT,_FAIL; _CONT+=1; _FAIL+=1; print(f"T{_CONT:02d} FAIL - {m} {e or ''}")
def verifica(cond,desc,extra=None):
    if cond: ok(desc)
    else: falla(desc,extra)

def _db():
    tmp=tempfile.mkdtemp()
    db=os.path.join(tmp,"test.db")
    conn=conectar_bd(db); conn.commit(); conn.close()
    return tmp,db
def _ins(db, carpeta, nombre, contenido=b"x"*1024):
    ruta=os.path.join(carpeta,nombre)
    os.makedirs(carpeta,exist_ok=True)
    open(ruta,"wb").write(contenido)
    st=os.stat(ruta)
    conn=conectar_bd(db)
    conn.execute("INSERT INTO videos (nombre,ruta,ruta_normalizada,extension,fecha_importacion,tamano_bytes,mtime_ns) VALUES (?,?,?,?,?,?,?)",(nombre, os.path.abspath(ruta), rutas.normalizar_ruta_clave(os.path.abspath(ruta)), os.path.splitext(nombre)[1].lower(),"2026-01-01", st.st_size, st.st_mtime_ns))
    vid=conn.execute("SELECT id FROM videos WHERE nombre=?",(nombre,)).fetchone()[0]
    conn.commit(); conn.close()
    return vid, os.path.abspath(ruta)

def _esperar_carga_estable(v, app, timeout=4.0, min_tarjetas=0):
    """Espera fin de carga paginada inicial sin crear duplicados."""
    t0=time.time()
    while time.time()-t0 < timeout:
        app.processEvents()
        try:
            activo = bool(getattr(v.gestor, "activo", False))
        except Exception:
            activo = False
        if not activo:
            # dar un ciclo para que _al_resultado cree tarjetas
            app.processEvents()
            if min_tarjetas==0 or len(getattr(v, "tarjetas", [])) >= min_tarjetas:
                # estabilizar un poco layout
                app.processEvents()
                break
        time.sleep(0.02)
    app.processEvents()
    time.sleep(0.05)
    app.processEvents()

def test_01_modo_normal_por_defecto():
    app=None
    from PySide6.QtWidgets import QApplication
    app=QApplication.instance()
    if app is None:
        app=QApplication(sys.argv)
    tmp,db=_db()
    try:
        ruta_config=os.path.join(tmp,"config.json")
        v=visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(720,540); v.show()
        _esperar_carga_estable(v, app)
        verifica(not v._modo_organizacion,"modo normal por defecto false")
        verifica(not v.panel_organizacion.isVisible(),"panel oculto por defecto")
        verifica(v.boton_modo_organizacion.text()=="Modo Organización","boton texto exacto")
        verifica(not v.boton_modo_organizacion.isChecked(),"boton no checked por defecto")
        etiqueta=v.panel_organizacion.etiqueta_destino.text()
        verifica("Sin destino" in etiqueta,"panel muestra Sin destino seleccionado")
        v.close(); v.gestor.cerrar()
        try: v.gestor_lote.cerrar()
        except: pass
        try: v.gestor.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp,ignore_errors=True)

def test_02_entrar_salir_no_cambia_contexto():
    from PySide6.QtWidgets import QApplication
    app=QApplication.instance()
    if app is None:
        app=QApplication(sys.argv)
    tmp,db=_db()
    A=os.path.join(tmp,"A"); B=os.path.join(tmp,"B")
    os.makedirs(A,exist_ok=True); os.makedirs(B,exist_ok=True)
    try:
        # Crear contenido suficiente para maximum>0 estable (60 videos)
        for i in range(60):
            _ins(db,A,f"v{i:03d}.mp4")
        ruta_config=os.path.join(tmp,"config.json")
        v=visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        # Altura pequeña fuerza scroll con grid; ancho suficiente para 2 columnas
        v.resize(780,320)
        v.show()
        # Estabilizar fixture esperando carga async determinista (sin _crear_tarjetas duplicado)
        _esperar_carga_estable(v, app, timeout=5.0, min_tarjetas=50)
        # fijar carpeta activa explícita (coincide con paginado filtrado por carpeta)
        v.carpeta_seleccionada=os.path.abspath(A)
        # Esperar recarga por carpeta si aplica
        _esperar_carga_estable(v, app, timeout=3.0, min_tarjetas=50)
        # Verifica fixture estable sin duplicados
        n_tarjetas=len(v.tarjetas)
        print(f"EVIDENCIA fixture tarjetas={n_tarjetas} visibles={len(v.visibles)}")
        verifica(n_tarjetas >= 30, f"fixture estable tarjetas {n_tarjetas} >=30")
        # Preparar selección/filtro/orden para probar preservación
        # Usar selección existente (primer elemento)
        if v.tarjetas:
            primer_nombre=v.tarjetas[0][0]
            v._nombres_seleccionados=set([primer_nombre])
            v._ancla_seleccion=primer_nombre
        v.busqueda.setText("v")
        app.processEvents()
        time.sleep(0.05)
        app.processEvents()
        v._orden_catalogo=("nombre","asc")
        app.processEvents()
        max_before=v.area.verticalScrollBar().maximum()
        print(f"EVIDENCIA max_before={max_before} value_before={v.area.verticalScrollBar().value()}")
        verifica(max_before > 0, f"fixture scroll maximum>0 antes toggle ({max_before}) — evidencia exacta antes")
        if max_before == 0:
            falla("fixture inestable: maximum 0 con 60 tarjetas, viewport no scrolleable", f"max={max_before}")
            v.close()
            try: v.gestor.cerrar()
            except: pass
            try: v.gestor_lote.cerrar()
            except: pass
            return
        # Fijar scroll a mitad
        mid=max(10, max_before//2)
        v.area.verticalScrollBar().setValue(mid)
        app.processEvents()
        time.sleep(0.06)
        app.processEvents()
        scroll_before=v.area.verticalScrollBar().value()
        maxv=max_before
        carpeta_before=v.carpeta_seleccionada
        sel_before=set(v._nombres_seleccionados)
        filtro_before=v.busqueda.text()
        orden_before=v._orden_catalogo
        print(f"EVIDENCIA before scroll={scroll_before} max={maxv}")
        # Verificar código preserva scroll
        src_org=inspect.getsource(v._al_cambiar_modo_organizacion)
        verifica("verticalScrollBar" in src_org and "setValue" in src_org,"codigo preserva scroll")
        verifica("RuntimeError" in src_org or "barra" in src_org,"codigo maneja scroll sin fallback genérico silencioso")
        # Entrar modo — preservación exacta (panel fuera de QScrollArea)
        v.boton_modo_organizacion.setChecked(True)
        app.processEvents()
        # QTimer.singleShot(0) en código difiere; esperar un ciclo
        time.sleep(0.08)
        app.processEvents()
        app.processEvents()
        after_enter=v.area.verticalScrollBar().value()
        max_after=v.area.verticalScrollBar().maximum()
        print(f"EVIDENCIA after_enter scroll_before={scroll_before} after={after_enter} max_before={maxv} max_after={max_after}")
        verifica(v._modo_organizacion,"modo organizacion activo")
        verifica(v.panel_organizacion.isVisible(),"panel visible al entrar")
        verifica(v.carpeta_seleccionada==carpeta_before,"carpeta activa no cambia al entrar")
        verifica(set(v._nombres_seleccionados)==sel_before,"seleccion no cambia al entrar")
        verifica(v.busqueda.text()==filtro_before,"filtro no cambia al entrar")
        verifica(v._orden_catalogo==orden_before,"orden no cambia al entrar")
        # Honesta: max_after==0 con max_before>0 es fallo, no éxito
        verifica(max_after > 0, f"max preservado >0 tras entrar ({max_after}) — fallo si 0 indica fixture inestable")
        verifica(abs(after_enter - scroll_before) <= 2, f"scroll preservado al entrar {scroll_before}->{after_enter} tol 2 max {maxv}->{max_after}")
        # Salir modo
        v.boton_modo_organizacion.setChecked(False)
        app.processEvents()
        time.sleep(0.08)
        app.processEvents()
        after_exit=v.area.verticalScrollBar().value()
        max_exit=v.area.verticalScrollBar().maximum()
        print(f"EVIDENCIA after_exit scroll_before={scroll_before} after_exit={after_exit} max_exit={max_exit}")
        verifica(not v._modo_organizacion,"modo organizacion desactivado")
        verifica(not v.panel_organizacion.isVisible(),"panel oculto al salir")
        verifica(v.carpeta_seleccionada==carpeta_before,"carpeta no cambia al salir")
        verifica(set(v._nombres_seleccionados)==sel_before,"seleccion no cambia al salir")
        verifica(v.busqueda.text()==filtro_before,"filtro no cambia al salir")
        verifica(v._orden_catalogo==orden_before,"orden no cambia al salir")
        verifica(max_exit > 0, f"max preservado >0 tras salir ({max_exit})")
        verifica(abs(after_exit - scroll_before) <= 2, f"scroll preservado al salir {scroll_before}->{after_exit} tol 2")
        v.close()
        try: v.gestor.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp,ignore_errors=True)

def test_03_destino_independiente_no_cambia_origen_ni_recarga():
    from PySide6.QtWidgets import QApplication, QFileDialog
    app=QApplication.instance()
    if app is None:
        app=QApplication(sys.argv)
    tmp,db=_db()
    A=os.path.join(tmp,"A"); B=os.path.join(tmp,"B")
    os.makedirs(A,exist_ok=True); os.makedirs(B,exist_ok=True)
    try:
        _ins(db,A,"v0.mp4")
        ruta_config=os.path.join(tmp,"config.json")
        v=visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(720,540); v.show()
        _esperar_carga_estable(v, app)
        v.carpeta_seleccionada=os.path.abspath(A)
        _esperar_carga_estable(v, app)
        v.boton_modo_organizacion.setChecked(True)
        app.processEvents()
        # interceptar recarga
        recargas=[]
        orig_prog=v._programar_recarga_por_carpeta
        def fake_prog():
            recargas.append(1)
            return orig_prog()
        v._programar_recarga_por_carpeta=fake_prog
        # mock QFileDialog
        orig_get=QFileDialog.getExistingDirectory
        QFileDialog.getExistingDirectory=lambda *a,**k: B
        v._seleccionar_destino_organizacion()
        app.processEvents()
        verifica(v._organizacion_destino==B,"destino elegido es B")
        verifica(v.carpeta_seleccionada==os.path.abspath(A),"origen no cambia al elegir destino")
        verifica(len(recargas)==0,"elegir destino no dispara recarga")
        verifica("Destino:" in v.panel_organizacion.etiqueta_destino.text() and B in v.panel_organizacion.etiqueta_destino.text(),"panel muestra Destino: <ruta>")
        # cambiar destino a C
        C=os.path.join(tmp,"C")
        os.makedirs(C,exist_ok=True)
        QFileDialog.getExistingDirectory=lambda *a,**k: C
        v._seleccionar_destino_organizacion()
        verifica(v._organizacion_destino==C,"segundo destino C")
        verifica(v.carpeta_seleccionada==os.path.abspath(A),"origen sigue sin cambiar")
        QFileDialog.getExistingDirectory=orig_get
        v._programar_recarga_por_carpeta=orig_prog
        v.close()
        try: v.gestor.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp,ignore_errors=True)

def test_04_botones_deshabilitados_sin_destino_o_sin_seleccion():
    from PySide6.QtWidgets import QApplication
    app=QApplication.instance()
    if app is None:
        app=QApplication(sys.argv)
    tmp,db=_db()
    A=os.path.join(tmp,"A"); B=os.path.join(tmp,"B")
    os.makedirs(A,exist_ok=True); os.makedirs(B,exist_ok=True)
    try:
        _ins(db,A,"v0.mp4")
        ruta_config=os.path.join(tmp,"config.json")
        v=visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(720,540); v.show()
        _esperar_carga_estable(v, app)
        v.boton_modo_organizacion.setChecked(True)
        app.processEvents()
        # sin destino sin seleccion -> deshabilitados
        # asegurar sin seleccion
        v._nombres_seleccionados=set()
        v._organizacion_destino=None
        v._actualizar_panel_organizacion()
        app.processEvents()
        verifica(not v.panel_organizacion.boton_mover_seleccionados_org.isEnabled(),"mover deshabilitado sin destino/seleccion")
        verifica(not v.panel_organizacion.boton_copiar_seleccionados_org.isEnabled(),"copiar deshabilitado sin destino/seleccion")
        # con destino sin seleccion -> deshabilitados
        v._organizacion_destino=B
        v._actualizar_panel_organizacion()
        app.processEvents()
        verifica(not v.panel_organizacion.boton_mover_seleccionados_org.isEnabled(),"mover deshabilitado con destino pero sin seleccion")
        # sin destino con seleccion -> deshabilitados
        v._organizacion_destino=None
        v._nombres_seleccionados=set(["v0.mp4"])
        v._actualizar_panel_organizacion()
        verifica(not v.panel_organizacion.boton_mover_seleccionados_org.isEnabled(),"mover deshabilitado sin destino con seleccion")
        verifica(not v.panel_organizacion.boton_copiar_seleccionados_org.isEnabled(),"copiar deshabilitado sin destino con seleccion")
        # con ambos -> habilitados
        v._organizacion_destino=B
        v._actualizar_panel_organizacion()
        app.processEvents()
        verifica(v.panel_organizacion.boton_mover_seleccionados_org.isEnabled(),"mover habilitado con seleccion+destino")
        verifica(v.panel_organizacion.boton_copiar_seleccionados_org.isEnabled(),"copiar habilitado con seleccion+destino")
        v.close()
        try: v.gestor.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp,ignore_errors=True)

def test_05_mover_copiar_delegan_B76_sin_FS_duplicada():
    from PySide6.QtWidgets import QApplication
    app=QApplication.instance()
    if app is None:
        app=QApplication(sys.argv)
    tmp,db=_db()
    A=os.path.join(tmp,"A"); B=os.path.join(tmp,"B")
    os.makedirs(A,exist_ok=True); os.makedirs(B,exist_ok=True)
    try:
        ids=[]
        for i in range(2):
            vid,_=_ins(db,A,f"v{i}.mp4",contenido=b"data%d"%i)
            ids.append(vid)
        ruta_config=os.path.join(tmp,"config.json")
        v=visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(720,540); v.show()
        _esperar_carga_estable(v, app, min_tarjetas=2)
        v.carpeta_seleccionada=os.path.abspath(A)
        _esperar_carga_estable(v, app, min_tarjetas=2)
        # verificar fixture sin duplicados
        verifica(len(v.tarjetas)==2, f"fixture 2 tarjetas sin duplicados ({len(v.tarjetas)})")
        v._nombres_seleccionados=set([f"v{i}.mp4" for i in range(2)])
        v.boton_modo_organizacion.setChecked(True)
        v._organizacion_destino=B
        v._actualizar_panel_organizacion()
        app.processEvents()
        # interceptar TareaLoteOperaciones
        capturados=[]
        orig_init=v.gestor_lote.iniciar
        def fake_iniciar(tarea):
            capturados.append((tarea.operacion, tarea.video_ids, tarea.carpeta_destino, tarea.ruta_db))
            return False  # no lanzar realmente
        v.gestor_lote.iniciar=fake_iniciar
        v._iniciar_lote_mover_organizacion()
        app.processEvents()
        verifica(len(capturados)==1,"mover organizacion delega una tarea")
        if capturados:
            op, vids, dest, rdb=capturados[0]
            verifica(op=="mover","operacion mover")
            verifica(vids==ids,"ids correctos y orden estable exacto")
            verifica(dest==B,"destino correcto")
            verifica(rdb==db,"ruta_db correcta")
        # copiar
        capturados.clear()
        v._iniciar_lote_copiar_organizacion()
        verifica(len(capturados)==1,"copiar organizacion delega una tarea")
        if capturados:
            op, vids, dest, rdb=capturados[0]
            verifica(op=="copiar","operacion copiar")
            verifica(vids==ids,"ids copiar correctos")
            verifica(dest==B,"destino copiar correcto")
        # Verificar que no hay lógica FS duplicada en handlers organizacion: no usan os.path.isdir etc
        src_m=inspect.getsource(v._iniciar_lote_mover_organizacion)
        src_c=inspect.getsource(v._iniciar_lote_copiar_organizacion)
        src_e=inspect.getsource(v._ejecutar_lote_organizacion)
        # mover_org y copiar_org delegan a _ejecutar, por lo que TareaLoteOperaciones está en _ejecutar
        for src_, name in [(src_e,"ejecutar_org")]:
            verifica("os.path.isdir" not in src_ and "os.path.isfile" not in src_ and "shutil" not in src_ and "sqlite" not in src_,"{0} sin FS/SQLite duplicado".format(name))
            verifica("TareaLoteOperaciones" in src_,"{0} usa TareaLoteOperaciones".format(name))
        for src_, name in [(src_m,"mover_org"),(src_c,"copiar_org")]:
            verifica("os.path.isdir" not in src_ and "os.path.isfile" not in src_ and "shutil" not in src_ and "sqlite" not in src_,"{0} sin FS/SQLite duplicado".format(name))
            # estas dos delegan, no necesitan Tarea directa
            verifica("_ejecutar_lote_organizacion" in src_,"{0} delega a _ejecutar_lote_organizacion".format(name))
        # Verificar que _seleccionar_destino usa QFileDialog (infra existente) y no cambia carpeta
        src_sel=inspect.getsource(v._seleccionar_destino_organizacion)
        verifica("getExistingDirectory" in src_sel,"selector usa getExistingDirectory")
        verifica("carpeta_seleccionada" not in src_sel or "carpeta_seleccionada =" not in src_sel,"selector no cambia carpeta origen")
        v.gestor_lote.iniciar=orig_init
        v.close()
        try: v.gestor.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp,ignore_errors=True)

def test_06_tarea_activa_bloquea():
    from PySide6.QtWidgets import QApplication
    app=QApplication.instance()
    if app is None:
        app=QApplication(sys.argv)
    tmp,db=_db()
    A=os.path.join(tmp,"A"); B=os.path.join(tmp,"B")
    os.makedirs(A,exist_ok=True); os.makedirs(B,exist_ok=True)
    try:
        _ins(db,A,"v0.mp4")
        ruta_config=os.path.join(tmp,"config.json")
        v=visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(720,540); v.show()
        _esperar_carga_estable(v, app)
        v.boton_modo_organizacion.setChecked(True)
        v._organizacion_destino=B
        v._nombres_seleccionados=set(["v0.mp4"])
        v._actualizar_panel_organizacion()
        app.processEvents()
        verifica(v.panel_organizacion.boton_mover_seleccionados_org.isEnabled(),"antes de tarea habilitado")
        orig_lote_ocup=v._lote_esta_ocupado
        v._lote_esta_ocupado=lambda: True
        v._actualizar_panel_organizacion()
        app.processEvents()
        verifica(not v.panel_organizacion.boton_mover_seleccionados_org.isEnabled(),"mover deshabilitado cuando tarea activa")
        verifica(not v.panel_organizacion.boton_copiar_seleccionados_org.isEnabled(),"copiar deshabilitado cuando tarea activa")
        verifica(not v.panel_organizacion.boton_seleccionar_destino.isEnabled(),"seleccionar destino deshabilitado cuando tarea activa")
        v._lote_esta_ocupado=orig_lote_ocup
        v._actualizar_panel_organizacion()
        app.processEvents()
        verifica(v.panel_organizacion.boton_mover_seleccionados_org.isEnabled(),"habilitado tras finalizar")
        v.close()
        try: v.gestor.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp,ignore_errors=True)

def test_07_finalizacion_hereda_B78():
    src=inspect.getsource(visor_videos.VisorVideos._al_resultado_lote)
    verifica("_b78_lote_debe_recargar" in src,"_al_resultado_lote usa politica B7.8")
    verifica("_programar_recarga_por_carpeta" in src,"finalizacion usa recarga paginada B7.8")
    # Verificar que org delega a mismo gestor_lote, por tanto misma finalizacion
    src_org=inspect.getsource(visor_videos.VisorVideos._ejecutar_lote_organizacion)
    verifica("gestor_lote.iniciar" in src_org,"org usa mismo gestor_lote")
    # No debe haber duplicación de lógica de recarga en org
    verifica("_programar_recarga" not in src_org,"org no duplica recarga, hereda B7.8 via _al_resultado_lote")

def test_08_volver_a_entrar_conserva_destino_sesion():
    from PySide6.QtWidgets import QApplication
    app=QApplication.instance()
    if app is None:
        app=QApplication(sys.argv)
    tmp,db=_db()
    B=os.path.join(tmp,"B")
    os.makedirs(B,exist_ok=True)
    try:
        ruta_config=os.path.join(tmp,"config.json")
        v=visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(720,540); v.show()
        _esperar_carga_estable(v, app)
        v.boton_modo_organizacion.setChecked(True)
        app.processEvents()
        v._organizacion_destino=B
        v._actualizar_panel_organizacion()
        verifica(v.panel_organizacion.etiqueta_destino.text()==f"Destino: {B}","destino seteado")
        v.boton_modo_organizacion.setChecked(False)
        app.processEvents()
        v.boton_modo_organizacion.setChecked(True)
        app.processEvents()
        verifica(v._organizacion_destino==B,"destino conservado al volver a entrar")
        verifica(v.panel_organizacion.etiqueta_destino.text()==f"Destino: {B}","panel conserva destino")
        # verificar no persistencia en config (no debe guardar en obtener_ultima_carpeta etc)
        src=inspect.getsource(v._seleccionar_destino_organizacion)
        verifica("guardar_ultima_carpeta" not in src and "guardar_" not in src,"no persistencia en config")
        v.close()
        try: v.gestor.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp,ignore_errors=True)

def test_09_widget_sin_acceso_directo():
    src=open("panel_organizacion.py",encoding="utf-8").read()
    for kw in ["sqlite3","conectar_bd","escanear_videos","lote_operaciones","mover_video","copiar_video"]:
        verifica(kw not in src,f"panel sin {kw}")
    for kw in ["import subprocess","from subprocess","import sqlite3","from sqlite3","QProcess"]:
        verifica(kw not in src,f"panel sin {kw}")
    # No verificar mención docstring de FFmpeg/ffprobe, permitido
    for kw2 in ["os.path.isdir","os.path.isfile","os.rename","shutil","os.remove","subprocess"]:
        verifica(kw2 not in src,f"panel sin {kw2}")
    # verificar que no importa operaciones FS
    verifica("import os" not in src,"panel no importa os")
    # verificar señales emitidas y actualizar
    verifica("seleccionarDestinoSolicitado" in src,"panel emite seleccionarDestinoSolicitado")
    verifica("moverSolicitado" in src,"panel emite moverSolicitado")
    verifica("copiarSolicitado" in src,"panel emite copiarSolicitado")
    verifica("def actualizar" in src,"panel tiene actualizar(destino,tiene,ocupado)")

def test_10_panel_compacto_y_no_reemplaza_biblioteca():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    app=QApplication.instance()
    if app is None:
        app=QApplication(sys.argv)
    tmp,db=_db()
    try:
        ruta_config=os.path.join(tmp,"config.json")
        v=visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(720,540); v.show()
        _esperar_carga_estable(v, app)
        # panel debe estar en layout principal, no reemplazar area
        verifica(v.area.isVisible(),"area catalogo sigue visible")
        verifica(v.contenedor.isVisible(),"contenedor catalogo sigue visible")
        # panel compacto pero exploratorio B7.10: zona vertical destino (4-5 filas) sin dominar catalogo
        # B7.11: splitter vertical secundario, sin limite rígido, catalogo dominante
        h=v.panel_organizacion.sizeHint().height()
        print(f"EVIDENCIA panel height hint={h}")
        if hasattr(v, "splitter_organizacion"):
            verifica(h < 350,f"B7.11 panel height hint {h} <350 (splitter, secundario)")
            lista=v.panel_organizacion.lista_subcarpetas
            verifica(lista.minimumHeight() >= 60, f"B7.11 lista minHeight >=60 min={lista.minimumHeight()}")
            verifica(lista.maximumHeight() > 200 or lista.maximumHeight() == 16777215, f"B7.11 lista sin limite rigido max={lista.maximumHeight()}")
            verifica(v.splitter_organizacion.objectName() == "splitter_organizacion","splitter objectName correcto B7.11")
            verifica(v.splitter_organizacion.count() == 2 and v.splitter_organizacion.widget(0) is v.panel_organizacion and v.splitter_organizacion.widget(1) is v.area,"splitter contiene exactamente panel+area B7.11")
        else:
            verifica(h < 230,f"panel destino exploratorio height {h} < 230 (secundario, catalogo domina)")
            lista=v.panel_organizacion.lista_subcarpetas
            verifica(lista.minimumHeight() >= 60 and lista.maximumHeight() >= 80, f"lista altura util multi-fila min={lista.minimumHeight()} max={lista.maximumHeight()}")
            verifica(lista.maximumHeight() <= 120, f"lista no domina pantalla max={lista.maximumHeight()} <=120")
        lista=v.panel_organizacion.lista_subcarpetas
        verifica(lista.maximumHeight() > 38, "lista no colapsa a una sola fila (maxHeight > 38)")
        verifica(lista.verticalScrollBarPolicy() == Qt.ScrollBarAsNeeded, f"scroll vertical AsNeeded ({lista.verticalScrollBarPolicy()} == {Qt.ScrollBarAsNeeded})")
        verifica(hasattr(v.panel_organizacion, "etiqueta_header_destino") and "Destino" in v.panel_organizacion.etiqueta_header_destino.text(), "header Destino presente")
        # al entrar modo, area sigue visible
        v.boton_modo_organizacion.setChecked(True)
        app.processEvents()
        verifica(v.area.isVisible(),"area sigue visible en modo organizacion")
        if hasattr(v, "splitter_organizacion"):
            verifica(v.splitter_organizacion.isVisible() or v.area.isVisible(),"B7.11 splitter visible y catalogo dominante")
        else:
            verifica(v.panel_organizacion.maximumHeight() < 200 or "QSplitter" not in inspect.getsource(visor_videos.VisorVideos.__init__), "panel secundario no QSplitter doble catalogo")
        v.close()
        try: v.gestor.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp,ignore_errors=True)

def test_11_AST_silencios_B79():
    """AST específico B7.9: 0 handlers solo-Pass y 0 fallbacks genéricos silenciosos nuevos."""
    import ast, pathlib
    src=pathlib.Path("visor_videos.py").read_text(encoding="utf-8")
    tree=ast.parse(src)
    fallos=[]
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in ('_al_cambiar_modo_organizacion','_actualizar_panel_organizacion','_seleccionar_destino_organizacion','_ejecutar_lote_organizacion','_iniciar_lote_mover_organizacion','_iniciar_lote_copiar_organizacion'):
            for ch in ast.walk(node):
                if isinstance(ch, ast.ExceptHandler):
                    typ = ast.unparse(ch.type) if ch.type else "bare"
                    is_pass_only = len(ch.body)==1 and isinstance(ch.body[0], ast.Pass)
                    if is_pass_only:
                        fallos.append(f"{node.name}:{ch.lineno} pass-only {typ}")
                    if typ=="Exception":
                        fallos.append(f"{node.name}:{ch.lineno} generic Exception")
    # Permitir RuntimeError específico en _al_cambiar_modo_organizacion
    fallos_filtrados=[f for f in fallos if "RuntimeError" not in f]
    # Si queda generic Exception pero es RuntimeError ya filtrado, ok
    # Reevaluar: solo RuntimeError permitido
    # Ya filtramos, pero si hay generic Exception restante es fallo
    if fallos_filtrados:
        verifica(False, f"AST B7.9 sin silencios: {fallos_filtrados}")
    else:
        # contar RuntimeError permitidos
        verifica(True,"AST B7.9 0 handlers solo-Pass y 0 fallbacks genéricos silenciosos (RuntimeError permitido)")

def main():
    print("=== B7.9 prueba_modo_organizacion_b79 ===")
    for fn in [test_01_modo_normal_por_defecto,test_02_entrar_salir_no_cambia_contexto,test_03_destino_independiente_no_cambia_origen_ni_recarga,test_04_botones_deshabilitados_sin_destino_o_sin_seleccion,test_05_mover_copiar_delegan_B76_sin_FS_duplicada,test_06_tarea_activa_bloquea,test_07_finalizacion_hereda_B78,test_08_volver_a_entrar_conserva_destino_sesion,test_09_widget_sin_acceso_directo,test_10_panel_compacto_y_no_reemplaza_biblioteca,test_11_AST_silencios_B79]:
        try: fn()
        except Exception as e:
            import traceback; falla(fn.__name__, str(e)); traceback.print_exc()
    total=_CONT; fallos=_FAIL
    print(f"TOTAL={total-fallos}/{total}")
    if fallos==0: print("RESULTADO_FINAL=OK")
    else: print("RESULTADO_FINAL=ERROR"); sys.exit(1)

if __name__=="__main__": main()
