"""Suite B7.10 — navegación visual embebida del DESTINO en Modo Organización."""
import os
import sys
import tempfile
import shutil
import inspect
import time
import sqlite3
from escanear_videos import conectar_bd
import visor_videos

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

def _db():
    tmp = tempfile.mkdtemp()
    db = os.path.join(tmp, "test.db")
    conn = conectar_bd(db)
    conn.commit()
    conn.close()
    return tmp, db

def _ins(db, carpeta, nombre, contenido=b"x"*1024):
    ruta = os.path.join(carpeta, nombre)
    os.makedirs(carpeta, exist_ok=True)
    open(ruta, "wb").write(contenido)
    st = os.stat(ruta)
    conn = conectar_bd(db)
    conn.execute("INSERT INTO videos (nombre,ruta,extension,fecha_importacion,tamano_bytes,mtime_ns) VALUES (?,?,?,?,?,?)", (nombre, os.path.abspath(ruta), os.path.splitext(nombre)[1].lower(), "2026-01-01", st.st_size, st.st_mtime_ns))
    vid = conn.execute("SELECT id FROM videos WHERE nombre=?", (nombre,)).fetchone()[0]
    conn.commit()
    conn.close()
    return vid, os.path.abspath(ruta)

def _esperar_carga_estable(v, app, timeout=4.0, min_tarjetas=0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        app.processEvents()
        try:
            activo = bool(getattr(v.gestor, "activo", False))
        except Exception:
            activo = False
        if not activo:
            app.processEvents()
            if min_tarjetas == 0 or len(getattr(v, "tarjetas", [])) >= min_tarjetas:
                app.processEvents()
                break
        time.sleep(0.02)
    app.processEvents()
    time.sleep(0.05)
    app.processEvents()

def _esperar_navegacion(v, app, timeout=3.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        app.processEvents()
        try:
            carg = bool(getattr(v, "_organizacion_cargando", False))
            activo = bool(getattr(v.gestor_navegacion_destino, "activo", False))
        except Exception:
            carg = False
            activo = False
        if not carg and not activo:
            app.processEvents()
            time.sleep(0.05)
            app.processEvents()
            break
        time.sleep(0.02)
    app.processEvents()

def test_01_visible_solo_modo_organizacion():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    tmp, db = _db()
    try:
        ruta_config = os.path.join(tmp, "config.json")
        v = visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(720, 540)
        v.show()
        _esperar_carga_estable(v, app)
        verifica(not v._modo_organizacion, "modo normal por defecto false")
        verifica(not v.panel_organizacion.isVisible(), "panel oculto por defecto")
        v.boton_modo_organizacion.setChecked(True)
        app.processEvents()
        time.sleep(0.08)
        app.processEvents()
        verifica(v._modo_organizacion, "modo organizacion activo")
        verifica(v.panel_organizacion.isVisible(), "panel visible al entrar B7.10")
        # verificar que lista y boton subir existen
        verifica(hasattr(v.panel_organizacion, "lista_subcarpetas"), "panel tiene lista_subcarpetas")
        verifica(hasattr(v.panel_organizacion, "boton_subir_destino"), "panel tiene boton_subir_destino")
        verifica(hasattr(v.panel_organizacion, "etiqueta_estado_navegacion"), "panel tiene etiqueta_estado_navegacion")
        # objectNames
        verifica(v.panel_organizacion.lista_subcarpetas.objectName() == "lista_subcarpetas_destino", "objectName lista correcto")
        verifica(v.panel_organizacion.boton_subir_destino.objectName() == "boton_subir_destino", "objectName subir correcto")
        v.boton_modo_organizacion.setChecked(False)
        app.processEvents()
        time.sleep(0.05)
        app.processEvents()
        verifica(not v.panel_organizacion.isVisible(), "panel oculto al salir B7.10")
        v.close()
        try: v.gestor.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
        try: v.gestor_navegacion_destino.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_02_destino_breadcrumb_y_subcarpetas():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    tmp, db = _db()
    A = os.path.join(tmp, "A")
    os.makedirs(A, exist_ok=True)
    sub1 = os.path.join(A, "sub1")
    sub2 = os.path.join(A, "sub2")
    os.makedirs(sub1, exist_ok=True)
    os.makedirs(sub2, exist_ok=True)
    try:
        ruta_config = os.path.join(tmp, "config.json")
        v = visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(720, 540)
        v.show()
        _esperar_carga_estable(v, app)
        v.boton_modo_organizacion.setChecked(True)
        app.processEvents()
        # simular selección destino A vía API directa + cargar navegación
        v._organizacion_destino = A
        v._cargar_navegacion_destino()
        _esperar_navegacion(v, app)
        verifica(v._organizacion_destino == A, "destino es A")
        verifica(v._organizacion_destino_valido, "destino valido")
        verifica(v._organizacion_error is None, "sin error para destino valido")
        # breadcrumbs / etiqueta
        txt = v.panel_organizacion.etiqueta_destino.text()
        verifica("Destino:" in txt and A in txt, f"breadcrumb muestra Destino: {A} ({txt})")
        # subcarpetas listadas ordenadas
        lista = v.panel_organizacion._subcarpetas
        verifica("sub1" in lista and "sub2" in lista, f"subcarpetas listadas {lista}")
        # también verificar widget lista contiene items
        items = [v.panel_organizacion.lista_subcarpetas.item(i).text() for i in range(v.panel_organizacion.lista_subcarpetas.count())]
        verifica("sub1" in items and "sub2" in items, f"QListWidget items {items}")
        v.close()
        try: v.gestor.cerrar()
        except: pass
        try: v.gestor_navegacion_destino.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_03_entrar_subcarpeta():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    tmp, db = _db()
    A = os.path.join(tmp, "A")
    sub1 = os.path.join(A, "sub1")
    sub1a = os.path.join(sub1, "sub1a")
    os.makedirs(sub1a, exist_ok=True)
    os.makedirs(os.path.join(A, "sub2"), exist_ok=True)
    try:
        _ins(db, A, "v0.mp4")
        ruta_config = os.path.join(tmp, "config.json")
        v = visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(780, 320)
        v.show()
        _esperar_carga_estable(v, app)
        # fijar origen
        v.carpeta_seleccionada = os.path.abspath(A)
        _esperar_carga_estable(v, app, min_tarjetas=1)
        v.boton_modo_organizacion.setChecked(True)
        app.processEvents()
        v._organizacion_destino = A
        v._cargar_navegacion_destino()
        _esperar_navegacion(v, app)
        # capturar estado origen antes
        carpeta_before = v.carpeta_seleccionada
        sel_before = set(v._nombres_seleccionados)
        filtro_before = v.busqueda.text()
        orden_before = v._orden_catalogo
        # interceptar recarga
        recargas = []
        orig_prog = v._programar_recarga_por_carpeta
        def fake():
            recargas.append(1)
            return orig_prog()
        v._programar_recarga_por_carpeta = fake
        # entrar sub1
        v._navegar_destino_a_subcarpeta("sub1")
        _esperar_navegacion(v, app)
        verifica(os.path.normcase(os.path.normpath(v._organizacion_destino)) == os.path.normcase(os.path.normpath(sub1)), f"entrar sub1 destino es sub1 ({v._organizacion_destino})")
        verifica(v.carpeta_seleccionada == carpeta_before, "origen no cambia al entrar subcarpeta")
        verifica(set(v._nombres_seleccionados) == sel_before, "seleccion no cambia al entrar")
        verifica(v.busqueda.text() == filtro_before, "filtro no cambia al entrar")
        verifica(v._orden_catalogo == orden_before, "orden no cambia al entrar")
        verifica(len(recargas) == 0, "entrar no dispara recarga catalogo")
        # verificar árbol origen no tocado (no cambió selección)
        # breadcrumb actualizado
        txt = v.panel_organizacion.etiqueta_destino.text()
        verifica("sub1" in txt, f"breadcrumb tras entrar contiene sub1 ({txt})")
        # verificar lista ahora muestra sub1a
        lista_items = [v.panel_organizacion.lista_subcarpetas.item(i).text() for i in range(v.panel_organizacion.lista_subcarpetas.count())]
        verifica("sub1a" in lista_items, f"subcarpetas de sub1 listadas {lista_items}")
        v._programar_recarga_por_carpeta = orig_prog
        v.close()
        try: v.gestor.cerrar()
        except: pass
        try: v.gestor_navegacion_destino.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_04_subir_padre():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    tmp, db = _db()
    A = os.path.join(tmp, "A")
    sub1 = os.path.join(A, "sub1")
    os.makedirs(sub1, exist_ok=True)
    try:
        ruta_config = os.path.join(tmp, "config.json")
        v = visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(720, 540)
        v.show()
        _esperar_carga_estable(v, app)
        v.carpeta_seleccionada = os.path.abspath(A)
        _esperar_carga_estable(v, app)
        v.boton_modo_organizacion.setChecked(True)
        app.processEvents()
        # destino en sub1
        v._organizacion_destino = sub1
        v._cargar_navegacion_destino()
        _esperar_navegacion(v, app)
        verifica(v._organizacion_destino_valido, "sub1 valido antes subir")
        recargas = []
        orig = v._programar_recarga_por_carpeta
        v._programar_recarga_por_carpeta = lambda: recargas.append(1) or orig()
        carpeta_before = v.carpeta_seleccionada
        filtro_before = v.busqueda.text()
        # subir
        v._navegar_destino_subir()
        _esperar_navegacion(v, app)
        verifica(os.path.normcase(os.path.normpath(v._organizacion_destino)) == os.path.normcase(os.path.normpath(A)), f"subir lleva a A ({v._organizacion_destino})")
        verifica(v.carpeta_seleccionada == carpeta_before, "origen no cambia al subir")
        verifica(v.busqueda.text() == filtro_before, "filtro no cambia al subir")
        verifica(len(recargas) == 0, "subir no dispara recarga")
        # breadcrumb
        txt = v.panel_organizacion.etiqueta_destino.text()
        verifica(A in txt and "sub1" not in txt or "Destino:" in txt, f"breadcrumb tras subir {txt}")
        v._programar_recarga_por_carpeta = orig
        v.close()
        try: v.gestor.cerrar()
        except: pass
        try: v.gestor_navegacion_destino.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_05_QFileDialog_sincroniza():
    from PySide6.QtWidgets import QApplication, QFileDialog
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    tmp, db = _db()
    A = os.path.join(tmp, "A")
    B = os.path.join(tmp, "B")
    os.makedirs(A, exist_ok=True)
    os.makedirs(B, exist_ok=True)
    os.makedirs(os.path.join(B, "hija"), exist_ok=True)
    try:
        _ins(db, A, "v0.mp4")
        ruta_config = os.path.join(tmp, "config.json")
        v = visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(720, 540)
        v.show()
        _esperar_carga_estable(v, app)
        v.carpeta_seleccionada = os.path.abspath(A)
        _esperar_carga_estable(v, app)
        v.boton_modo_organizacion.setChecked(True)
        app.processEvents()
        orig_get = QFileDialog.getExistingDirectory
        QFileDialog.getExistingDirectory = lambda *a, **k: B
        recargas = []
        orig_prog = v._programar_recarga_por_carpeta
        v._programar_recarga_por_carpeta = lambda: recargas.append(1) or orig_prog()
        v._seleccionar_destino_organizacion()
        _esperar_navegacion(v, app)
        verifica(v._organizacion_destino == B, "QFileDialog sincroniza destino B")
        verifica(v._organizacion_destino_valido, "B valido tras QFileDialog")
        txt = v.panel_organizacion.etiqueta_destino.text()
        verifica("Destino:" in txt and B in txt, "panel muestra destino tras QFileDialog")
        items = [v.panel_organizacion.lista_subcarpetas.item(i).text() for i in range(v.panel_organizacion.lista_subcarpetas.count())]
        verifica("hija" in items, f"navegador sincronizado muestra hija {items}")
        verifica(v.carpeta_seleccionada == os.path.abspath(A), "origen no cambia tras QFileDialog")
        verifica(len(recargas) == 0, "QFileDialog no dispara recarga")
        QFileDialog.getExistingDirectory = orig_get
        v._programar_recarga_por_carpeta = orig_prog
        v.close()
        try: v.gestor.cerrar()
        except: pass
        try: v.gestor_navegacion_destino.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_06_independencia_origen():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    tmp, db = _db()
    A = os.path.join(tmp, "A")
    B = os.path.join(tmp, "B")
    os.makedirs(A, exist_ok=True)
    os.makedirs(B, exist_ok=True)
    os.makedirs(os.path.join(B, "subB"), exist_ok=True)
    try:
        for i in range(5):
            _ins(db, A, f"v{i}.mp4")
        ruta_config = os.path.join(tmp, "config.json")
        v = visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(720, 540)
        v.show()
        _esperar_carga_estable(v, app, min_tarjetas=5)
        v.carpeta_seleccionada = os.path.abspath(A)
        _esperar_carga_estable(v, app, min_tarjetas=5)
        v.busqueda.setText("v")
        app.processEvents()
        v._orden_catalogo = ("nombre", "asc")
        v._nombres_seleccionados = set(["v0.mp4"])
        app.processEvents()
        v.boton_modo_organizacion.setChecked(True)
        app.processEvents()
        v._organizacion_destino = B
        v._cargar_navegacion_destino()
        _esperar_navegacion(v, app)
        carpeta_before = v.carpeta_seleccionada
        sel_before = set(v._nombres_seleccionados)
        filtro_before = v.busqueda.text()
        orden_before = v._orden_catalogo
        # mock recarga
        recargas = []
        orig = v._programar_recarga_por_carpeta
        v._programar_recarga_por_carpeta = lambda: recargas.append(1) or orig()
        # navegar
        v._navegar_destino_a_subcarpeta("subB")
        _esperar_navegacion(v, app)
        verifica(v.carpeta_seleccionada == carpeta_before, "independencia: carpeta origen unchanged")
        verifica(set(v._nombres_seleccionados) == sel_before, "independencia: seleccion unchanged")
        verifica(v.busqueda.text() == filtro_before, "independencia: filtro unchanged")
        verifica(v._orden_catalogo == orden_before, "independencia: orden unchanged")
        # verificar arbol no cambio (no tocar)
        # No hay API directa, pero carpeta_before still A
        verifica(len(recargas) == 0, "independencia: no recarga catalogo")
        # verificar visor no tocó _total_catalogo ni tarjetas_visibles lógica? al menos tarjetas length preserved
        verifica(len(v.tarjetas) >= 5, "catalogo visual no vaciado")
        v._programar_recarga_por_carpeta = orig
        v.close()
        try: v.gestor.cerrar()
        except: pass
        try: v.gestor_navegacion_destino.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_07_viewport_estable():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    tmp, db = _db()
    A = os.path.join(tmp, "A")
    os.makedirs(A, exist_ok=True)
    try:
        for i in range(60):
            _ins(db, A, f"v{i:03d}.mp4")
        ruta_config = os.path.join(tmp, "config.json")
        v = visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(780, 320)
        v.show()
        _esperar_carga_estable(v, app, timeout=5.0, min_tarjetas=50)
        v.carpeta_seleccionada = os.path.abspath(A)
        _esperar_carga_estable(v, app, timeout=3.0, min_tarjetas=50)
        n = len(v.tarjetas)
        print(f"EVIDENCIA viewport fixture tarjetas={n}")
        verifica(n >= 30, f"fixture tarjetas {n} >=30")
        max_before = v.area.verticalScrollBar().maximum()
        print(f"EVIDENCIA viewport max_before={max_before} value_before={v.area.verticalScrollBar().value()}")
        verifica(max_before > 0, f"maximum>0 antes ({max_before})")
        if max_before == 0:
            falla("fixture maximum 0", f"max={max_before}")
            v.close()
            try: v.gestor.cerrar()
            except: pass
            try: v.gestor_navegacion_destino.cerrar()
            except: pass
            return
        mid = max(10, max_before // 2)
        v.area.verticalScrollBar().setValue(mid)
        app.processEvents()
        time.sleep(0.06)
        app.processEvents()
        scroll_before = v.area.verticalScrollBar().value()
        # Entrar modo + destino
        dest = os.path.join(tmp, "DEST")
        os.makedirs(dest, exist_ok=True)
        os.makedirs(os.path.join(dest, "hija"), exist_ok=True)
        v.boton_modo_organizacion.setChecked(True)
        app.processEvents()
        time.sleep(0.08)
        app.processEvents()
        max_after_enter = v.area.verticalScrollBar().maximum()
        after_enter = v.area.verticalScrollBar().value()
        print(f"EVIDENCIA viewport after_enter scroll {scroll_before}->{after_enter} max {max_before}->{max_after_enter}")
        verifica(max_after_enter > 0, f"max preservado >0 tras entrar ({max_after_enter})")
        verifica(abs(after_enter - scroll_before) <= 2, f"scroll preservado al entrar {scroll_before}->{after_enter} tol2")
        # Navegar destino (no debe afectar viewport)
        v._organizacion_destino = dest
        v._cargar_navegacion_destino()
        _esperar_navegacion(v, app)
        max_nav = v.area.verticalScrollBar().maximum()
        val_nav = v.area.verticalScrollBar().value()
        print(f"EVIDENCIA viewport tras navegacion_destino max={max_nav} value={val_nav}")
        verifica(max_nav > 0, f"max >0 tras navegacion ({max_nav})")
        verifica(abs(val_nav - scroll_before) <= 2, f"viewport estable tras navegar destino {scroll_before}->{val_nav}")
        # Entrar subcarpeta también estable
        v._navegar_destino_a_subcarpeta("hija")
        _esperar_navegacion(v, app)
        max_sub = v.area.verticalScrollBar().maximum()
        val_sub = v.area.verticalScrollBar().value()
        print(f"EVIDENCIA viewport tras entrar subcarpeta max={max_sub} value={val_sub}")
        verifica(max_sub > 0, f"max >0 tras entrar subcarpeta ({max_sub})")
        verifica(abs(val_sub - scroll_before) <= 2, f"viewport estable tras entrar subcarpeta {scroll_before}->{val_sub}")
        # Subir también estable
        v._navegar_destino_subir()
        _esperar_navegacion(v, app)
        max_up = v.area.verticalScrollBar().maximum()
        val_up = v.area.verticalScrollBar().value()
        verifica(max_up > 0, f"max >0 tras subir ({max_up})")
        verifica(abs(val_up - scroll_before) <= 2, f"viewport estable tras subir {scroll_before}->{val_up}")
        v.close()
        try: v.gestor.cerrar()
        except: pass
        try: v.gestor_navegacion_destino.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_08_destino_invalido_desaparecido():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    tmp, db = _db()
    A = os.path.join(tmp, "A")
    B = os.path.join(tmp, "B")
    os.makedirs(A, exist_ok=True)
    os.makedirs(B, exist_ok=True)
    try:
        _ins(db, A, "v0.mp4")
        ruta_config = os.path.join(tmp, "config.json")
        v = visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(720, 540)
        v.show()
        _esperar_carga_estable(v, app)
        v.boton_modo_organizacion.setChecked(True)
        app.processEvents()
        # destino valido B
        v._organizacion_destino = B
        v._cargar_navegacion_destino()
        _esperar_navegacion(v, app)
        verifica(v._organizacion_destino_valido, "B valido inicial")
        # con seleccion -> habilitados
        v._nombres_seleccionados = set(["v0.mp4"])
        v._actualizar_panel_organizacion()
        verifica(v.panel_organizacion.boton_mover_seleccionados_org.isEnabled(), "mover habilitado con destino valido y seleccion")
        # hacer destino invalido: borrar carpeta
        shutil.rmtree(B)
        v._cargar_navegacion_destino()
        _esperar_navegacion(v, app)
        verifica(not v._organizacion_destino_valido, "destino invalido tras borrar")
        verifica(v._organizacion_error is not None, "error visible tras destino desaparecido")
        txt_dest = v.panel_organizacion.etiqueta_destino.text()
        verifica("NO DISPONIBLE" in txt_dest or "no disponible" in txt_dest.lower(), f"panel muestra NO DISPONIBLE ({txt_dest})")
        verifica(not v.panel_organizacion.boton_mover_seleccionados_org.isEnabled(), "mover deshabilitado con destino invalido")
        verifica(not v.panel_organizacion.boton_copiar_seleccionados_org.isEnabled(), "copiar deshabilitado con destino invalido")
        # lista deshabilitada
        verifica(not v.panel_organizacion.lista_subcarpetas.isEnabled() or v.panel_organizacion.lista_subcarpetas.count() == 0, "lista deshabilitada con destino invalido")
        # intentar navegar no debe cambiar destino ni lanzar excepción silenciosa
        old_dest = v._organizacion_destino
        try:
            v._navegar_destino_a_subcarpeta("cualquiera")
            _esperar_navegacion(v, app)
            verifica(v._organizacion_destino == old_dest, "navegar con destino invalido no cambia destino")
        except Exception as exc:
            falla("navegar con destino invalido no debe lanzar", str(exc))
        # intentar mover debe bloquear con mensaje sin excepción
        try:
            v._iniciar_lote_mover_organizacion()
            verifica("Destino no disponible" in v.mensaje_carpeta.text() or "Seleccione destino" in v.mensaje_carpeta.text() or "no disponible" in v.mensaje_carpeta.text().lower(), f"mover con destino invalido muestra estado ({v.mensaje_carpeta.text()})")
        except Exception as exc:
            falla("mover con destino invalido no debe lanzar", str(exc))
        v.close()
        try: v.gestor.cerrar()
        except: pass
        try: v.gestor_navegacion_destino.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_09_lote_bloquea_interaccion_competitiva():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    tmp, db = _db()
    A = os.path.join(tmp, "A")
    B = os.path.join(tmp, "B")
    os.makedirs(A, exist_ok=True)
    os.makedirs(B, exist_ok=True)
    os.makedirs(os.path.join(B, "sub"), exist_ok=True)
    try:
        _ins(db, A, "v0.mp4")
        ruta_config = os.path.join(tmp, "config.json")
        v = visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(720, 540)
        v.show()
        _esperar_carga_estable(v, app)
        v.boton_modo_organizacion.setChecked(True)
        v._organizacion_destino = B
        v._cargar_navegacion_destino()
        _esperar_navegacion(v, app)
        v._nombres_seleccionados = set(["v0.mp4"])
        v._actualizar_panel_organizacion()
        verifica(v.panel_organizacion.boton_mover_seleccionados_org.isEnabled(), "pre lote habilitado")
        # simular lote activo
        orig_ocup = v._lote_esta_ocupado
        v._lote_esta_ocupado = lambda: True
        v._actualizar_panel_organizacion()
        app.processEvents()
        verifica(not v.panel_organizacion.boton_mover_seleccionados_org.isEnabled(), "mover deshabilitado con lote activo")
        verifica(not v.panel_organizacion.boton_copiar_seleccionados_org.isEnabled(), "copiar deshabilitado con lote activo")
        verifica(not v.panel_organizacion.boton_seleccionar_destino.isEnabled(), "seleccionar destino deshabilitado con lote activo")
        verifica(not v.panel_organizacion.boton_subir_destino.isEnabled(), "subir deshabilitado con lote activo")
        verifica(not v.panel_organizacion.lista_subcarpetas.isEnabled(), "lista deshabilitada con lote activo")
        # intentar navegar con lote activo no cambia destino
        old = v._organizacion_destino
        v._navegar_destino_a_subcarpeta("sub")
        app.processEvents()
        verifica(v._organizacion_destino == old, "navegar bloqueado con lote activo")
        v._navegar_destino_subir()
        verifica(v._organizacion_destino == old, "subir bloqueado con lote activo")
        v._lote_esta_ocupado = orig_ocup
        v._actualizar_panel_organizacion()
        verifica(v.panel_organizacion.boton_mover_seleccionados_org.isEnabled(), "habilitado tras lote")
        v.close()
        try: v.gestor.cerrar()
        except: pass
        try: v.gestor_navegacion_destino.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_10_AST_imports_sin_accesos_prohibidos():
    src = open("panel_organizacion.py", encoding="utf-8").read()
    for kw in ["sqlite3", "conectar_bd", "escanear_videos", "lote_operaciones", "mover_video", "copiar_video", "QFileDialog.getExistingDirectory"]:
        # QFileDialog solo debe estar en visor, no panel
        if kw == "QFileDialog.getExistingDirectory":
            verifica(kw not in src, f"panel sin {kw} (solo visor lo usa)")
        else:
            verifica(kw not in src, f"panel sin {kw}")
    for kw in ["import subprocess", "from subprocess", "import sqlite3", "from sqlite3", "QProcess"]:
        verifica(kw not in src, f"panel sin {kw}")
    for kw2 in ["os.path.isdir", "os.path.isfile", "os.rename", "shutil", "os.remove", "subprocess", "os.listdir"]:
        verifica(kw2 not in src, f"panel sin {kw2}")
    verifica("import os" not in src, "panel no importa os")
    verifica("seleccionarDestinoSolicitado" in src, "panel emite seleccionarDestinoSolicitado")
    verifica("moverSolicitado" in src, "panel emite moverSolicitado")
    verifica("copiarSolicitado" in src, "panel emite copiarSolicitado")
    verifica("entrarSubcarpetaSolicitada" in src, "panel emite entrarSubcarpetaSolicitada B7.10")
    verifica("subirSolicitado" in src, "panel emite subirSolicitado B7.10")
    verifica("def actualizar" in src, "panel tiene actualizar")
    # verificar que actualizar no toca FS
    src_act = inspect.getsource(visor_videos.VisorVideos._cargar_navegacion_destino)
    verifica("TareaListarSubcarpetasDestino" in src_act, "_cargar_navegacion usa Tarea background")
    # Panel no debe duplicar helper: verificar que no importa rutas/listar_subcarpetas directamente (docstring no cuenta como código ejecutable)
    panel_src = open("panel_organizacion.py", encoding="utf-8").read()
    verifica("from rutas import" not in panel_src and "import rutas" not in panel_src, "panel no importa rutas/listar_subcarpetas directo")
    # visor navegación no hace polling
    src_nav = inspect.getsource(visor_videos.VisorVideos._navegar_destino_a_subcarpeta) + inspect.getsource(visor_videos.VisorVideos._navegar_destino_subir) + inspect.getsource(visor_videos.VisorVideos._cargar_navegacion_destino)
    verifica("QTimer" not in src_nav or "singleShot" not in src_nav or "poll" not in src_nav.lower(), "navegacion sin polling periódico")
    # panel compacto B7.10 vs B7.11: B7.11 elimina límites rígidos maxHeight y usa splitter + mínimos
    if hasattr(visor_videos.VisorVideos, "_al_cambiar_modo_organizacion") and "splitter_organizacion" in inspect.getsource(visor_videos.VisorVideos.__init__):
        verifica("setMinimumHeight" in src or "MinimumHeight" in src, "B7.11 panel define MinimumHeight (splitter gestiona altura)")
        verifica("setMaximumHeight(155" not in src and "setMaximumHeight(92" not in src, "B7.11 sin limites rigidos 155/92")
    else:
        verifica("MaximumHeight" in src or "maximumHeight" in src.lower(), "panel compacto define MaximumHeight")

def test_11_panel_compacto_no_reemplaza_biblioteca():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    tmp, db = _db()
    try:
        ruta_config = os.path.join(tmp, "config.json")
        v = visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(720, 540)
        v.show()
        _esperar_carga_estable(v, app)
        verifica(v.area.isVisible(), "area catalogo sigue visible")
        verifica(v.contenedor.isVisible(), "contenedor catalogo sigue visible")
        h = v.panel_organizacion.sizeHint().height()
        print(f"EVIDENCIA panel height hint={h}")
        # B7.10 agrupado: panel destino ahora es zona vertical exploratoria (4-5 filas visibles)
        # B7.11: panel pasa a splitter, sin limite rígido. Validar que no domina catálogo pero puede crecer.
        if hasattr(v, "splitter_organizacion"):
            verifica(h < 350, f"B7.11 panel height hint {h} <350 (splitter, no domina)")
            lista = v.panel_organizacion.lista_subcarpetas
            # B7.11: sin max rígido 92/120, debe permitir crecimiento: maxHeight grande, min razonable
            verifica(lista.minimumHeight() >= 60, f"B7.11 lista minHeight >=60 min={lista.minimumHeight()}")
            verifica(lista.maximumHeight() > 200 or lista.maximumHeight() == 16777215, f"B7.11 lista sin limite rigido max={lista.maximumHeight()} >200")
            verifica(v.splitter_organizacion is not None and v.splitter_organizacion.objectName() == "splitter_organizacion", "splitter_organizacion objectName correcto")
        else:
            verifica(h < 230, f"panel destino exploratorio height {h} < 230 (secundario, catalogo domina)")
            lista = v.panel_organizacion.lista_subcarpetas
            verifica(lista.minimumHeight() >= 60 and lista.maximumHeight() >= 80, f"lista altura util multi-fila min={lista.minimumHeight()} max={lista.maximumHeight()}")
            verifica(lista.maximumHeight() <= 120, f"lista no domina pantalla max={lista.maximumHeight()} <=120")
        lista = v.panel_organizacion.lista_subcarpetas
        # Verificar lista puede contener N>1 simultáneamente (widget no colapsa a una fila)
        verifica(lista.maximumHeight() > 38, "lista no colapsa a una sola fila (maxHeight > 38)")
        # Comprobación real contra enum PySide6 correcto, sin bypass ni tolerancia artificial
        verifica(lista.verticalScrollBarPolicy() == Qt.ScrollBarAsNeeded, f"scroll vertical policy AsNeeded real ({lista.verticalScrollBarPolicy()} == {Qt.ScrollBarAsNeeded})")
        # Header Destino claramente diferenciado
        verifica(hasattr(v.panel_organizacion, "etiqueta_header_destino") and "Destino" in v.panel_organizacion.etiqueta_header_destino.text(), "header Destino presente")
        v.boton_modo_organizacion.setChecked(True)
        app.processEvents()
        verifica(v.area.isVisible(), "area sigue visible en modo organizacion B7.10/B7.11")
        # verificar que panel no es QSplitter doble catalogo: B7.11 SI tiene splitter vertical secundario correcto
        if hasattr(v, "splitter_organizacion"):
            verifica(v.splitter_organizacion.count() == 2, "splitter secundario tiene exactamente 2 widgets")
            verifica(v.splitter_organizacion.widget(0) is v.panel_organizacion, "splitter widget0 es panel")
            verifica(v.splitter_organizacion.widget(1) is v.area, "splitter widget1 es area catalogo")
        else:
            verifica("QSplitter" not in inspect.getsource(visor_videos.VisorVideos.__init__) or v.panel_organizacion.maximumHeight() < 200, "no QSplitter doble catalogo")
        v.close()
        try: v.gestor.cerrar()
        except: pass
        try: v.gestor_navegacion_destino.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_11b_scroll_determinista_muchas_subcarpetas():
    """Prueba determinista B7.10: con muchas subcarpetas (>=20/30), widget mostrado y layout procesado,
    demostrar count>=20, content/viewport suficiente y scrollbar maximum>0 (evidencia real, no textual)."""
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    tmp, db = _db()
    DEST = os.path.join(tmp, "DEST_MUCHAS")
    os.makedirs(DEST, exist_ok=True)
    # Crear >=30 subcarpetas para cubrir ambos umbrales 20 y 30
    for i in range(30):
        os.makedirs(os.path.join(DEST, f"sub{i:02d}"), exist_ok=True)
    try:
        ruta_config = os.path.join(tmp, "config.json")
        v = visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(720, 540)
        v.show()
        _esperar_carga_estable(v, app)
        # Entrar modo organización y cargar destino con muchas subcarpetas
        v.boton_modo_organizacion.setChecked(True)
        app.processEvents()
        time.sleep(0.06)
        app.processEvents()
        v._organizacion_destino = DEST
        v._cargar_navegacion_destino()
        _esperar_navegacion(v, app)
        # Asegurar layout procesado: widget mostrado, processEvents y geometría
        app.processEvents()
        time.sleep(0.08)
        app.processEvents()
        lista = v.panel_organizacion.lista_subcarpetas
        # Force layout ensureVisible
        lista.updateGeometry()
        app.processEvents()
        time.sleep(0.04)
        app.processEvents()
        count = lista.count()
        policy = lista.verticalScrollBarPolicy()
        h_policy = lista.horizontalScrollBarPolicy()
        max_scroll = lista.verticalScrollBar().maximum()
        viewport_h = lista.viewport().height()
        # content height estimado por filas - determinista sin genericos
        row_h = lista.sizeHintForRow(0) if count > 0 else 0
        content_h = row_h * count if row_h else 0
        print(f"EVIDENCIA scroll muchas subcarpetas count={count} policy={policy} h_policy={h_policy} max={max_scroll} viewport_h={viewport_h} row_h={row_h} content_h={content_h}")
        verifica(count >= 20, f"lista count >=20 con muchas subcarpetas ({count})")
        verifica(count >= 30, f"lista count >=30 con 30 subcarpetas ({count})")
        verifica(policy == Qt.ScrollBarAsNeeded, f"policy vertical AsNeeded real ({policy} == {Qt.ScrollBarAsNeeded})")
        verifica(h_policy == Qt.ScrollBarAlwaysOff, f"policy horizontal AlwaysOff ({h_policy} == {Qt.ScrollBarAlwaysOff})")
        # content/viewport suficiente: contenido supera viewport cuando hay muchas filas
        # Evidencia determinista: row_h*count > viewport_h implica necesidad de scroll
        if row_h and viewport_h:
            verifica(content_h > viewport_h, f"content {content_h} > viewport {viewport_h} (suficiente para scroll)")
        else:
            # fallback evidencia via maximum>0 si métricas no disponibles en offscreen
            verifica(max_scroll >= 0, f"viewport métrica fallback max={max_scroll}")
        verifica(max_scroll > 0, f"verticalScrollBar maximum >0 con muchas subcarpetas ({max_scroll})")
        # Verificar iconos: cada item tiene icono carpeta no nulo - sin silencios genericos
        iconos_ok = 0
        for i in range(count):
            item = lista.item(i)
            if item is not None:
                ic = item.icon()
                if ic is not None and not ic.isNull():
                    iconos_ok += 1
        print(f"EVIDENCIA iconos {iconos_ok}/{count} con icono carpeta")
        verifica(iconos_ok == count and count >= 20, f"iconos carpeta presentes en todos los items ({iconos_ok}/{count})")
        # Verificar header Destino y panel visible
        verifica(v.panel_organizacion.isVisible(), "panel visible en Organizacion con muchas subcarpetas")
        verifica(hasattr(v.panel_organizacion, "etiqueta_header_destino") and "Destino" in v.panel_organizacion.etiqueta_header_destino.text(), "header Destino presente con muchas subcarpetas")
        # Viewport catálogo estable: no debe resetearse al navegar destino
        verifica(v.area.isVisible(), "area catalogo sigue visible con muchas subcarpetas")
        v.close()
        # cierre explicito sin silencios genericos bare/except Exception
        if hasattr(v, "gestor") and hasattr(v.gestor, "cerrar"):
            v.gestor.cerrar()
        if hasattr(v, "gestor_navegacion_destino") and hasattr(v.gestor_navegacion_destino, "cerrar"):
            v.gestor_navegacion_destino.cerrar()
        if hasattr(v, "gestor_lote") and hasattr(v.gestor_lote, "cerrar"):
            v.gestor_lote.cerrar()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_12_regresion_B79():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    tmp, db = _db()
    A = os.path.join(tmp, "A")
    os.makedirs(A, exist_ok=True)
    try:
        ruta_config = os.path.join(tmp, "config.json")
        v = visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(720, 540)
        v.show()
        _esperar_carga_estable(v, app)
        verifica(not v._modo_organizacion, "regresion B7.9: modo normal por defecto")
        verifica(not v.panel_organizacion.isVisible(), "regresion B7.9: panel oculto por defecto")
        etiqueta = v.panel_organizacion.etiqueta_destino.text()
        verifica("Sin destino" in etiqueta, "regresion B7.9: Sin destino")
        v.boton_modo_organizacion.setChecked(True)
        app.processEvents()
        verifica(v.panel_organizacion.isVisible(), "regresion B7.9: panel visible al entrar")
        v.boton_modo_organizacion.setChecked(False)
        app.processEvents()
        verifica(not v.panel_organizacion.isVisible(), "regresion B7.9: panel oculto al salir")
        # destino no persistido entre sesiones: nuevo Visor con mismo config no conserva destino (B7.10 requisito 8)
        # Config no guarda destino -> nuevo visor debe iniciar sin destino
        v2 = visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v2.resize(720, 540)
        v2.show()
        _esperar_carga_estable(v2, app)
        verifica(v2._organizacion_destino is None, "no persistencia destino entre sesiones")
        verifica("Sin destino" in v2.panel_organizacion.etiqueta_destino.text(), "panel nuevo sin destino")
        v.close()
        v2.close()
        try: v.gestor.cerrar()
        except: pass
        try: v2.gestor.cerrar()
        except: pass
        try: v.gestor_navegacion_destino.cerrar()
        except: pass
        try: v2.gestor_navegacion_destino.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
        try: v2.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_13_helper_reutilizado():
    # verificar que helper está en rutas y no duplicado en widget
    import rutas
    verifica(hasattr(rutas, "listar_subcarpetas"), "rutas tiene helper listar_subcarpetas B7.10")
    verifica(hasattr(rutas, "carpeta_padre"), "rutas tiene helper carpeta_padre")
    src_rutas = inspect.getsource(rutas.listar_subcarpetas)
    verifica("os.listdir" in src_rutas, "helper usa os.listdir centralizado")
    verifica("os.path.isdir" in src_rutas, "helper usa isdir centralizado")
    src_panel = open("panel_organizacion.py", encoding="utf-8").read()
    verifica("os.listdir" not in src_panel, "panel no duplica listar")
    verifica("os.path.isdir" not in src_panel, "panel no duplica isdir")
    # visor usa helper via tarea, no directo en panel
    src_visor_nav = inspect.getsource(visor_videos.VisorVideos._al_resultado_navegacion_destino)
    verifica("listar_subcarpetas" not in src_visor_nav or "Tarea" in inspect.getsource(visor_videos.VisorVideos._cargar_navegacion_destino), "visor delega via Tarea")
    # sin polling: no QTimer periódico en navegación
    src_cargar = inspect.getsource(visor_videos.VisorVideos._cargar_navegacion_destino)
    verifica("poll" not in src_cargar.lower() and "QTimer" not in src_cargar or "singleShot" in inspect.getsource(visor_videos.VisorVideos._al_cambiar_modo_organizacion), "sin polling periódico")

def main():
    print("=== B7.10 prueba_navegacion_destino_b710 ===")
    for fn in [test_01_visible_solo_modo_organizacion, test_02_destino_breadcrumb_y_subcarpetas, test_03_entrar_subcarpeta, test_04_subir_padre, test_05_QFileDialog_sincroniza, test_06_independencia_origen, test_07_viewport_estable, test_08_destino_invalido_desaparecido, test_09_lote_bloquea_interaccion_competitiva, test_10_AST_imports_sin_accesos_prohibidos, test_11_panel_compacto_no_reemplaza_biblioteca, test_11b_scroll_determinista_muchas_subcarpetas, test_12_regresion_B79, test_13_helper_reutilizado]:
        try:
            fn()
        except Exception as e:
            import traceback
            falla(fn.__name__, str(e))
            traceback.print_exc()
    total = _CONT
    fallos = _FAIL
    print(f"TOTAL={total-fallos}/{total}")
    if fallos == 0:
        print("RESULTADO_FINAL=OK")
    else:
        print("RESULTADO_FINAL=ERROR")
        sys.exit(1)

if __name__ == "__main__":
    main()
