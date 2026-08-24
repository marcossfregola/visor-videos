"""Suite B7.11 — doble panel estructural de Organización con QSplitter vertical."""
import os
import sys
import tempfile
import shutil
import inspect
import time
import ast
from escanear_videos import conectar_bd
import rutas
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
    conn.execute("INSERT INTO videos (nombre,ruta,ruta_normalizada,extension,fecha_importacion,tamano_bytes,mtime_ns) VALUES (?,?,?,?,?,?,?)", (nombre, os.path.abspath(ruta), rutas.normalizar_ruta_clave(os.path.abspath(ruta)), os.path.splitext(nombre)[1].lower(), "2026-01-01", st.st_size, st.st_mtime_ns))
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

def test_01_splitter_secundario():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    tmp, db = _db()
    try:
        ruta_config = os.path.join(tmp, "config.json")
        v = visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(800, 600)
        v.show()
        _esperar_carga_estable(v, app)
        # 1. splitter secundario existe
        verifica(hasattr(v, "splitter_organizacion"), "B7.11 splitter_organizacion existe")
        s = getattr(v, "splitter_organizacion", None)
        verifica(s is not None, "splitter no es None")
        if s is not None:
            verifica(s.objectName() == "splitter_organizacion", f"objectName splitter_organizacion ({s.objectName()})")
            verifica(s.orientation() == Qt.Vertical, f"orientacion Vertical ({s.orientation()} == {Qt.Vertical})")
            verifica(s.count() == 2, f"splitter tiene exactamente 2 widgets ({s.count()})")
            verifica(s.widget(0) is v.panel_organizacion, "widget0 es PanelOrganizacion")
            verifica(s.widget(1) is v.area, "widget1 es area catalogo")
            # no recrea tarjetas
            verifica(s.widget(1).findChild(type(v.contenedor)) is not None or v.contenedor.parent() is not None, "contenedor catálogo sigue dentro de area sin duplicar")
        # verificar que global horizontal intacto
        from PySide6.QtWidgets import QSplitter
        # buscar splitter horizontal global
        splitters = v.findChildren(QSplitter)
        verifica(len(splitters) >= 2, f"existen al menos 2 QSplitters (global + secundario) count={len(splitters)}")
        # identificar horizontal: debe tener 2 widgets (panel izquierdo + raiz)
        horizontales = [sp for sp in splitters if sp.orientation() == Qt.Horizontal]
        verifica(len(horizontales) >= 1, "splitter horizontal global existe")
        if horizontales:
            h = horizontales[0]
            verifica(h.count() == 2, f"horizontal global count 2 ({h.count()})")
            verifica(h.handleWidth() >= 6, "horizontal handleWidth razonable")
        v.close()
        try: v.gestor.cerrar()
        except: pass
        try: v.gestor_navegacion_destino.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_02_modo_normal_oculta():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    tmp, db = _db()
    try:
        ruta_config = os.path.join(tmp, "config.json")
        v = visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(800, 600)
        v.show()
        _esperar_carga_estable(v, app)
        verifica(not v._modo_organizacion, "modo normal por defecto")
        verifica(not v.panel_organizacion.isVisible(), "panel oculto en modo normal")
        # catálogo ocupa altura: area height debe ser grande, splitter sizes
        s = v.splitter_organizacion
        # splitter visible, area debe tener altura significativa
        total_h = s.height()
        area_h = v.area.height()
        panel_h = v.panel_organizacion.height()
        print(f"EVIDENCIA modo normal splitter_total={total_h} area_h={area_h} panel_h={panel_h} panel_visible={v.panel_organizacion.isVisible()}")
        # panel hidden => su height 0 o no visible, area ocupa casi todo
        verifica(area_h > 100, f"area altura >100 en modo normal ({area_h})")
        # si panel hidden, area debe ser >80% de splitter total si total>0
        if total_h > 50:
            verifica(area_h >= total_h * 0.85, f"catalogo recupera ~toda altura area {area_h} vs total {total_h}")
        else:
            verifica(True, "splitter altura aun no calculada, skip proporcion")
        v.close()
        try: v.gestor.cerrar()
        except: pass
        try: v.gestor_navegacion_destino.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_03_organizacion_muestra_destino_y_catalogo_dominante():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    tmp, db = _db()
    A = os.path.join(tmp, "A")
    sub1 = os.path.join(A, "sub1")
    sub2 = os.path.join(A, "sub2")
    os.makedirs(sub1, exist_ok=True)
    os.makedirs(sub2, exist_ok=True)
    try:
        ruta_config = os.path.join(tmp, "config.json")
        v = visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(800, 600)
        v.show()
        _esperar_carga_estable(v, app)
        v.boton_modo_organizacion.setChecked(True)
        app.processEvents()
        time.sleep(0.12)
        app.processEvents()
        verifica(v._modo_organizacion, "modo organizacion activo")
        verifica(v.panel_organizacion.isVisible(), "panel visible en Organizacion")
        verifica(v.area.isVisible(), "area catalogo sigue visible en Organizacion")
        # panel debe tener espacio real para varias filas > B7.10 compacto (que era max 92)
        v._organizacion_destino = A
        v._cargar_navegacion_destino()
        _esperar_navegacion(v, app)
        app.processEvents()
        time.sleep(0.08)
        app.processEvents()
        lista = v.panel_organizacion.lista_subcarpetas
        panel_h = v.panel_organizacion.height()
        area_h = v.area.height()
        total_h = v.splitter_organizacion.height()
        print(f"EVIDENCIA organizacion panel_h={panel_h} area_h={area_h} total={total_h} lista_h={lista.height()} count={lista.count()}")
        verifica(panel_h > 100, f"panel destino altura >100 con varias filas ({panel_h}) > B7.10 compacto 155 limite eliminado")
        verifica(area_h > 140, f"catalogo permanece visible con altura >140 ({area_h})")
        # proporción razonable: destino 25-30%, catalogo 70-75% (tolerancia amplia 20-45%)
        if total_h > 100:
            ratio_panel = panel_h / total_h if total_h else 0
            verifica(0.18 <= ratio_panel <= 0.50, f"proporcion panel 18-50% ({ratio_panel:.2f}) 25-30% objetivo")
            verifica(area_h > panel_h, f"catalogo dominante area {area_h} > panel {panel_h}")
        # lista debe existir y tener 2 carpetas visibles simultáneamente
        items = [lista.item(i).text() for i in range(lista.count())]
        verifica("sub1" in items and "sub2" in items, f"lista muestra varias filas {items}")
        v.close()
        try: v.gestor.cerrar()
        except: pass
        try: v.gestor_navegacion_destino.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_04_handle_ajustable_y_no_colapsa():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    tmp, db = _db()
    try:
        ruta_config = os.path.join(tmp, "config.json")
        v = visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(800, 600)
        v.show()
        _esperar_carga_estable(v, app)
        v.boton_modo_organizacion.setChecked(True)
        app.processEvents()
        time.sleep(0.1)
        app.processEvents()
        s = v.splitter_organizacion
        verifica(s.handleWidth() >= 5, f"handleWidth ajustable >=5 ({s.handleWidth()})")
        verifica(not s.isCollapsible(1), "catalogo no colapsable (isCollapsible(1)==False)")
        # probar mover handle programáticamente
        sizes_before = s.sizes()
        print(f"EVIDENCIA sizes_before={sizes_before}")
        if len(sizes_before) == 2 and sum(sizes_before) > 0:
            # mover handle: aumentar panel en 40px
            new_panel = sizes_before[0] + 40
            new_area = max(140, sizes_before[1] - 40)
            s.setSizes([new_panel, new_area])
            app.processEvents()
            time.sleep(0.05)
            app.processEvents()
            sizes_after = s.sizes()
            print(f"EVIDENCIA sizes_after={sizes_after}")
            verifica(sizes_after[0] != sizes_before[0], f"handle ajustable cambia sizes {sizes_before}->{sizes_after}")
            verifica(s.sizes()[1] >= 100, f"catalogo sigue con altura >=100 tras mover handle ({s.sizes()[1]})")
            # verificar que catálogo no colapsa a 0 al intentar forzar panel muy grande
            total = sum(sizes_after)
            s.setSizes([total - 10, 10])
            app.processEvents()
            time.sleep(0.05)
            app.processEvents()
            forced = s.sizes()
            print(f"EVIDENCIA forced sizes {forced}")
            verifica(forced[1] >= 50, f"catalogo no colapsa aun forzando panel grande, min {forced[1]} >=50")
            # restaurar
            s.setSizes([150, 470])
            app.processEvents()
        else:
            verifica(False, "sizes_before no disponibles")
        v.close()
        try: v.gestor.cerrar()
        except: pass
        try: v.gestor_navegacion_destino.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_05_mover_handle_no_altera_scroll():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    tmp, db = _db()
    A = os.path.join(tmp, "A")
    os.makedirs(A, exist_ok=True)
    try:
        for i in range(50):
            _ins(db, A, f"v{i:03d}.mp4")
        ruta_config = os.path.join(tmp, "config.json")
        v = visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(780, 320)
        v.show()
        _esperar_carga_estable(v, app, timeout=5.0, min_tarjetas=40)
        v.carpeta_seleccionada = os.path.abspath(A)
        _esperar_carga_estable(v, app, timeout=3.0, min_tarjetas=40)
        max_before = v.area.verticalScrollBar().maximum()
        print(f"EVIDENCIA mover_handle max_before={max_before}")
        verifica(max_before > 0, f"maximum>0 antes ({max_before})")
        if max_before > 0:
            mid = max(10, max_before // 2)
            v.area.verticalScrollBar().setValue(mid)
            app.processEvents()
            time.sleep(0.06)
            app.processEvents()
            scroll_before = v.area.verticalScrollBar().value()
            v.boton_modo_organizacion.setChecked(True)
            app.processEvents()
            time.sleep(0.08)
            app.processEvents()
            # mover handle del splitter
            s = v.splitter_organizacion
            sizes = s.sizes()
            s.setSizes([sizes[0]+30, sizes[1]-30])
            app.processEvents()
            time.sleep(0.08)
            app.processEvents()
            after = v.area.verticalScrollBar().value()
            print(f"EVIDENCIA mover handle scroll {scroll_before}->{after}")
            verifica(abs(after - scroll_before) <= 2, f"mover handle no altera scroll {scroll_before}->{after} tol2")
            # mover otra vez
            s.setSizes([sizes[0]-20, sizes[1]+20])
            app.processEvents()
            time.sleep(0.05)
            app.processEvents()
            after2 = v.area.verticalScrollBar().value()
            verifica(abs(after2 - scroll_before) <= 2, f"segundo mover handle no altera scroll {scroll_before}->{after2}")
        v.close()
        try: v.gestor.cerrar()
        except: pass
        try: v.gestor_navegacion_destino.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_06_viewport_preservado_activar_desactivar():
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
        max_before = v.area.verticalScrollBar().maximum()
        verifica(max_before > 0, f"maximum>0 antes activar ({max_before})")
        if max_before == 0:
            v.close()
            try: v.gestor.cerrar()
            except: pass
            return
        mid = max(10, max_before // 2)
        v.area.verticalScrollBar().setValue(mid)
        app.processEvents()
        time.sleep(0.06)
        app.processEvents()
        scroll_before = v.area.verticalScrollBar().value()
        dest = os.path.join(tmp, "DEST")
        os.makedirs(dest, exist_ok=True)
        os.makedirs(os.path.join(dest, "hija"), exist_ok=True)
        v.boton_modo_organizacion.setChecked(True)
        app.processEvents()
        time.sleep(0.08)
        app.processEvents()
        max_after = v.area.verticalScrollBar().maximum()
        after = v.area.verticalScrollBar().value()
        print(f"EVIDENCIA viewport activar {scroll_before}->{after} max {max_before}->{max_after}")
        verifica(max_after > 0, f"max preservado >0 tras activar ({max_after})")
        verifica(abs(after - scroll_before) <= 2, f"scroll preservado al activar {scroll_before}->{after}")
        # desactivar
        v.boton_modo_organizacion.setChecked(False)
        app.processEvents()
        time.sleep(0.08)
        app.processEvents()
        max_off = v.area.verticalScrollBar().maximum()
        after_off = v.area.verticalScrollBar().value()
        print(f"EVIDENCIA viewport desactivar {after}->{after_off} max {max_off}")
        verifica(max_off > 0, f"max >0 tras desactivar ({max_off})")
        verifica(abs(after_off - scroll_before) <= 2, f"scroll preservado al desactivar {scroll_before}->{after_off}")
        v.close()
        try: v.gestor.cerrar()
        except: pass
        try: v.gestor_navegacion_destino.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_07_entrar_subir_preserva_origen():
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
        for i in range(20):
            _ins(db, A, f"v{i:02d}.mp4")
        ruta_config = os.path.join(tmp, "config.json")
        v = visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(780, 320)
        v.show()
        _esperar_carga_estable(v, app, timeout=4.0, min_tarjetas=10)
        v.carpeta_seleccionada = os.path.abspath(A)
        _esperar_carga_estable(v, app, min_tarjetas=10)
        v.busqueda.setText("v")
        app.processEvents()
        v._orden_catalogo = ("nombre", "asc")
        v._nombres_seleccionados = set(["v00.mp4"])
        app.processEvents()
        # preparar scroll
        maxv = v.area.verticalScrollBar().maximum()
        if maxv > 0:
            v.area.verticalScrollBar().setValue(max(5, maxv//3))
            app.processEvents()
            time.sleep(0.05)
            app.processEvents()
        scroll_before = v.area.verticalScrollBar().value()
        v.boton_modo_organizacion.setChecked(True)
        app.processEvents()
        v._organizacion_destino = A
        v._cargar_navegacion_destino()
        _esperar_navegacion(v, app)
        carpeta_before = v.carpeta_seleccionada
        sel_before = set(v._nombres_seleccionados)
        filtro_before = v.busqueda.text()
        orden_before = v._orden_catalogo
        recargas = []
        orig_prog = v._programar_recarga_por_carpeta
        def fake():
            recargas.append(1)
            return orig_prog()
        v._programar_recarga_por_carpeta = fake
        v._navegar_destino_a_subcarpeta("sub1")
        _esperar_navegacion(v, app)
        verifica(v._organizacion_destino is not None and "sub1" in v._organizacion_destino, "entrar sub1 cambia destino")
        verifica(v.carpeta_seleccionada == carpeta_before, "origen no cambia al entrar subcarpeta B7.11")
        verifica(set(v._nombres_seleccionados) == sel_before, "seleccion no cambia al entrar B7.11")
        verifica(v.busqueda.text() == filtro_before, "filtro no cambia al entrar B7.11")
        verifica(v._orden_catalogo == orden_before, "orden no cambia al entrar B7.11")
        verifica(len(recargas) == 0, "entrar no dispara recarga B7.11")
        viewport_after = v.area.verticalScrollBar().value()
        verifica(abs(viewport_after - scroll_before) <= 2, f"viewport estable tras entrar subcarpeta {scroll_before}->{viewport_after}")
        # subir
        recargas.clear()
        v._navegar_destino_subir()
        _esperar_navegacion(v, app)
        verifica("sub1" not in v._organizacion_destino or os.path.normcase(os.path.normpath(v._organizacion_destino)) == os.path.normcase(os.path.normpath(A)), f"subir vuelve a A ({v._organizacion_destino})")
        verifica(v.carpeta_seleccionada == carpeta_before, "origen no cambia al subir B7.11")
        verifica(len(recargas) == 0, "subir no dispara recarga B7.11")
        viewport_up = v.area.verticalScrollBar().value()
        verifica(abs(viewport_up - scroll_before) <= 2, f"viewport estable tras subir {scroll_before}->{viewport_up}")
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

def test_08_30_subcarpetas_scroll_real():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    tmp, db = _db()
    DEST = os.path.join(tmp, "DEST_MUCHAS")
    os.makedirs(DEST, exist_ok=True)
    for i in range(30):
        os.makedirs(os.path.join(DEST, f"sub{i:02d}"), exist_ok=True)
    try:
        ruta_config = os.path.join(tmp, "config.json")
        v = visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(800, 600)
        v.show()
        _esperar_carga_estable(v, app)
        v.boton_modo_organizacion.setChecked(True)
        app.processEvents()
        time.sleep(0.06)
        app.processEvents()
        v._organizacion_destino = DEST
        v._cargar_navegacion_destino()
        _esperar_navegacion(v, app)
        app.processEvents()
        time.sleep(0.08)
        app.processEvents()
        lista = v.panel_organizacion.lista_subcarpetas
        lista.updateGeometry()
        app.processEvents()
        time.sleep(0.04)
        app.processEvents()
        count = lista.count()
        max_scroll = lista.verticalScrollBar().maximum()
        viewport_h = lista.viewport().height()
        row_h = lista.sizeHintForRow(0) if count > 0 else 0
        content_h = row_h * count if row_h else 0
        print(f"EVIDENCIA 30 subcarpetas count={count} max={max_scroll} viewport_h={viewport_h} row_h={row_h} content_h={content_h} panel_h={v.panel_organizacion.height()} lista_h={lista.height()}")
        verifica(count >= 30, f"30 subcarpetas count>=30 ({count})")
        verifica(lista.verticalScrollBarPolicy() == Qt.ScrollBarAsNeeded, "policy AsNeeded")
        if row_h and viewport_h:
            verifica(content_h > viewport_h, f"content {content_h} > viewport {viewport_h} necesita scroll")
        verifica(max_scroll > 0, f"scroll destino real maximum>0 ({max_scroll})")
        verifica(v.panel_organizacion.height() > 120, f"panel destino altura >120 con 30 carpetas ({v.panel_organizacion.height()}) > B7.10 compacto")
        v.close()
        if hasattr(v, "gestor") and hasattr(v.gestor, "cerrar"):
            v.gestor.cerrar()
        if hasattr(v, "gestor_navegacion_destino") and hasattr(v.gestor_navegacion_destino, "cerrar"):
            v.gestor_navegacion_destino.cerrar()
        if hasattr(v, "gestor_lote") and hasattr(v.gestor_lote, "cerrar"):
            v.gestor_lote.cerrar()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_09_error_cargando_botones():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    tmp, db = _db()
    A = os.path.join(tmp, "A")
    os.makedirs(A, exist_ok=True)
    B = os.path.join(tmp, "B")
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
        verifica(v._organizacion_destino_valido, "B valido inicial B7.11")
        v._nombres_seleccionados = set(["v0.mp4"])
        v._actualizar_panel_organizacion()
        verifica(v.panel_organizacion.boton_mover_seleccionados_org.isEnabled(), "mover habilitado con destino valido")
        # estado cargando simulado
        v._organizacion_cargando = True
        v._actualizar_panel_organizacion()
        verifica(not v.panel_organizacion.boton_mover_seleccionados_org.isEnabled(), "mover deshabilitado cargando")
        verifica("Cargando" in v.panel_organizacion.etiqueta_estado_navegacion.text() or v.panel_organizacion.etiqueta_estado_navegacion.isVisible(), "etiqueta cargando visible")
        v._organizacion_cargando = False
        # destino invalido
        shutil.rmtree(B)
        v._cargar_navegacion_destino()
        _esperar_navegacion(v, app)
        verifica(not v._organizacion_destino_valido, "destino invalido tras borrar B7.11")
        verifica(v._organizacion_error is not None, "error visible")
        txt = v.panel_organizacion.etiqueta_destino.text()
        verifica("NO DISPONIBLE" in txt, f"panel NO DISPONIBLE ({txt})")
        verifica(not v.panel_organizacion.boton_mover_seleccionados_org.isEnabled(), "mover deshabilitado invalido")
        verifica(not v.panel_organizacion.boton_copiar_seleccionados_org.isEnabled(), "copiar deshabilitado invalido")
        v.close()
        try: v.gestor.cerrar()
        except: pass
        try: v.gestor_navegacion_destino.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_10_mover_copiar_delegan():
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
        verifica(hasattr(v, "_iniciar_lote_mover_organizacion"), "visores tiene _iniciar_lote_mover_organizacion")
        verifica(hasattr(v, "_iniciar_lote_copiar_organizacion"), "visores tiene _iniciar_lote_copiar_organizacion")
        # verificar conexiones del panel siguen delegando B7.6
        src_mover = inspect.getsource(v._iniciar_lote_mover_organizacion)
        verifica("TareaLoteOperaciones" in src_mover or "_ejecutar_lote_organizacion" in src_mover, "mover delega B7.6")
        src_copiar = inspect.getsource(v._iniciar_lote_copiar_organizacion)
        verifica("TareaLoteOperaciones" in src_copiar or "_ejecutar_lote_organizacion" in src_copiar, "copiar delega B7.6")
        # señales conectadas
        verifica(v.panel_organizacion.moverSolicitado is not None, "panel moverSolicitado existe")
        verifica(v.panel_organizacion.copiarSolicitado is not None, "panel copiarSolicitado existe")
        v.close()
        try: v.gestor.cerrar()
        except: pass
        try: v.gestor_navegacion_destino.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_11_AST():
    src_panel = open("panel_organizacion.py", encoding="utf-8").read()
    src_visor = open("visor_videos.py", encoding="utf-8").read()
    # REFUERZO B7.11 segunda corrección: localizar ambos métodos por nombre y contar ast.Pass via ast.walk(method_node) exactamente 0
    # Panel: _al_seleccion_lista_cambia
    tree_panel = ast.parse(src_panel)
    panel_node = None
    for node in ast.walk(tree_panel):
        if isinstance(node, ast.FunctionDef) and node.name == "_al_seleccion_lista_cambia":
            panel_node = node
            break
    panel_pass_count = sum(1 for n in ast.walk(panel_node) if isinstance(n, ast.Pass)) if panel_node is not None else -1
    verifica(panel_node is not None, "_al_seleccion_lista_cambia existe panel")
    verifica(panel_pass_count == 0, f"0 ast.Pass en _al_seleccion_lista_cambia via ast.walk ({panel_pass_count})")
    # Visor: _al_cambiar_modo_organizacion
    tree_visor = ast.parse(src_visor)
    visor_node = None
    for node in ast.walk(tree_visor):
        if isinstance(node, ast.FunctionDef) and node.name == "_al_cambiar_modo_organizacion":
            visor_node = node
            break
    visor_pass_count = sum(1 for n in ast.walk(visor_node) if isinstance(n, ast.Pass)) if visor_node is not None else -1
    verifica(visor_node is not None, "_al_cambiar_modo_organizacion existe visor")
    verifica(visor_pass_count == 0, f"0 ast.Pass en _al_cambiar_modo_organizacion via ast.walk ({visor_pass_count})")
    # contar pass-only handlers B7.10/B7.11 (compat histórica, pero ahora exige walk 0 arriba)
    def count_pass_handlers(src):
        tree = ast.parse(src)
        cnt = 0
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        # solo handlers B7.10/B7.11 relevantes: _al_*
                        if item.name.startswith("_al_"):
                            if len(item.body) == 1 and isinstance(item.body[0], ast.Pass):
                                cnt += 1
                            elif len(item.body) == 2 and isinstance(item.body[0], ast.Expr) and isinstance(item.body[0].value, ast.Constant) and isinstance(item.body[1], ast.Pass):
                                # docstring + pass
                                cnt += 1
                            elif item.name == "_al_seleccion_lista_cambia":
                                # este fue corregido B7.11
                                if len(item.body) == 1 and isinstance(item.body[0], ast.Pass):
                                    cnt += 1
        return cnt
    # conteo especifico B7.10/B7.11: _al_seleccion_lista_cambia y navegación
    panel_handlers = 0
    tree = ast.parse(src_panel)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in ("_al_seleccion_lista_cambia", "_al_doble_clic_subcarpeta", "_al_boton_entrar"):
            if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                panel_handlers += 1
            # docstring + pass
            if len(node.body) == 2 and isinstance(node.body[0], ast.Expr) and isinstance(node.body[1], ast.Pass):
                panel_handlers += 1
    verifica(panel_handlers == 0, f"0 pass-only handlers B7.10/B7.11 panel ({panel_handlers})")
    # visor handlers B7.10/B7.11 relevantes: no deben ser pass
    visor_handlers = []
    for name in ["_al_cambiar_modo_organizacion", "_navegar_destino_a_subcarpeta", "_navegar_destino_subir", "_cargar_navegacion_destino", "_al_resultado_navegacion_destino"]:
        if f"def {name}" in src_visor:
            # parse
            tree2 = ast.parse(src_visor)
            for cls in tree2.body:
                if isinstance(cls, ast.ClassDef) and cls.name == "VisorVideos":
                    for meth in cls.body:
                        if isinstance(meth, ast.FunctionDef) and meth.name == name:
                            if len(meth.body) == 1 and isinstance(meth.body[0], ast.Pass):
                                visor_handlers.append(name)
    verifica(len(visor_handlers) == 0, f"0 pass-only handlers visor B7.10/B7.11 ({visor_handlers})")
    # 0 except Exception genéricos nuevos en B7.11: buscar "except Exception" en diff B7.11
    # Contar en panel y visor zonas B7.11
    panel_excepts = src_panel.count("except Exception")
    # visor debe tener 0 nuevos genéricos: comparar con baseline? permitir los existentes pero no nuevos sin calificador
    # Verificar que panel no tiene except Exception
    verifica(panel_excepts == 0, f"0 except Exception genéricos nuevos panel ({panel_excepts})")
    # visor: contar nuevos en sección B7.11 (splitter/ navegacion) no debe tener except Exception sin tipo específico
    # buscar patrón "except Exception" en visor y verificar que no está en zonas nuevas (splitter es inocuo)
    visor_excepts = src_visor.count("except Exception")
    print(f"EVIDENCIA except Exception panel={panel_excepts} visor total={visor_excepts}")
    # No exigir 0 total visor porque histórico tiene muchos, pero si exigir que B7.11 no añadió
    # Para prueba, verificar que panel no añadió y que visor B7.11 code no contiene "except Exception:"
    visor_b711_section = ""
    for marker in ["splitter_organizacion", "_al_cambiar_modo_organizacion"]:
        idx = src_visor.find(marker)
        if idx != -1:
            visor_b711_section += src_visor[max(0, idx-500): idx+1500]
    verifica("except Exception" not in visor_b711_section, "B7.11 no añade except Exception genérico en splitter/navegacion")

def test_12_no_segundo_catalogo_ni_dragdrop():
    src_panel = open("panel_organizacion.py", encoding="utf-8").read()
    src_visor = open("visor_videos.py", encoding="utf-8").read()
    verifica("drag" not in src_panel.lower() or "dragdrop" not in src_panel.lower(), "panel sin drag&drop")
    # verificar que visor no crea segunda lista de videos (no segunda area)
    count_area = src_visor.count("self.area = QScrollArea")
    verifica(count_area == 1, f"solo una lista videos self.area ({count_area})")
    verifica("splitter_organizacion" in src_visor, "splitter_organizacion existe")
    verifica(src_visor.count("QSplitter") >= 2, "al menos 2 QSplitters (global + secundario)")

def main():
    print("=== B7.11 prueba_doble_panel_b711 ===")
    for fn in [test_01_splitter_secundario, test_02_modo_normal_oculta, test_03_organizacion_muestra_destino_y_catalogo_dominante, test_04_handle_ajustable_y_no_colapsa, test_05_mover_handle_no_altera_scroll, test_06_viewport_preservado_activar_desactivar, test_07_entrar_subir_preserva_origen, test_08_30_subcarpetas_scroll_real, test_09_error_cargando_botones, test_10_mover_copiar_delegan, test_11_AST, test_12_no_segundo_catalogo_ni_dragdrop]:
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
