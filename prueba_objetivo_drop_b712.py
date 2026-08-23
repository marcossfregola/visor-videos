"""Suite B7.12 — objetivo estable drop sin gesto arrastre."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import sys
import tempfile
import shutil
import inspect
import ast
import time
from escanear_videos import conectar_bd
import visor_videos
from rutas import resolver_destino_drop, validar_destino_drop_completo

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

# ── 01 raíz válida -> ruta raíz y validación True ──
def test_01_raiz_valida():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    tmp, db = _db()
    DEST = os.path.join(tmp, "DEST")
    os.makedirs(DEST, exist_ok=True)
    os.makedirs(os.path.join(DEST, "hija"), exist_ok=True)
    try:
        ruta_config = os.path.join(tmp, "config.json")
        v = visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(780, 540)
        v.show()
        _esperar_carga_estable(v, app)
        v.boton_modo_organizacion.setChecked(True)
        app.processEvents()
        time.sleep(0.06)
        app.processEvents()
        v._organizacion_destino = DEST
        v._cargar_navegacion_destino()
        _esperar_navegacion(v, app)
        verifica(v._organizacion_destino_valido, "destino valido raiz")
        # visor API raiz
        verifica(v._organizacion_objetivo_nombre is None, "objetivo raiz None por defecto")
        verifica(v.panel_organizacion.objetivo_nombre() is None, "panel objetivo None raiz")
        verifica(v.panel_organizacion.objetivo_es_destino_raiz(), "panel objetivo_es_destino_raiz True")
        dest_drop = v._obtener_destino_drop_actual()
        # normalizado
        verifica(dest_drop is not None and os.path.normcase(os.path.normpath(dest_drop)) == os.path.normcase(os.path.normpath(DEST)), f"obtener_destino_drop raiz -> raiz ({dest_drop})")
        # resolver helper
        r = resolver_destino_drop(DEST, None)
        verifica(r is not None and os.path.normcase(os.path.normpath(r)) == os.path.normcase(os.path.normpath(DEST)), f"resolver None -> raiz ({r})")
        verifica(v._validar_destino_drop_actual() == True, "validar destino drop raiz True")
        verifica(validar_destino_drop_completo(dest_drop) == True, "validar helper True raiz")
        v.close()
        try: v.gestor.cerrar()
        except: pass
        try: v.gestor_navegacion_destino.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

# ── 02 hija por clic simple -> ruta destino/hija ──
def test_02_hija_clic_simple():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    tmp, db = _db()
    DEST = os.path.join(tmp, "DEST2")
    os.makedirs(os.path.join(DEST, "hija"), exist_ok=True)
    os.makedirs(os.path.join(DEST, "otra"), exist_ok=True)
    try:
        ruta_config = os.path.join(tmp, "config.json")
        v = visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(780, 540)
        v.show()
        _esperar_carga_estable(v, app)
        v.boton_modo_organizacion.setChecked(True)
        app.processEvents()
        v._organizacion_destino = DEST
        v._cargar_navegacion_destino()
        _esperar_navegacion(v, app)
        # Simular clic simple en hija via API panel (currentRowChanged)
        lista = v.panel_organizacion.lista_subcarpetas
        # buscar row de hija
        row_hija = -1
        for i in range(lista.count()):
            if lista.item(i).text() == "hija":
                row_hija = i
                break
        verifica(row_hija >= 0, "hija existe en lista")
        emitted = []
        v.panel_organizacion.objetivoSeleccionado.connect(lambda n: emitted.append(n))
        # clic simple: seleccionar fila -> debe emitir hija
        lista.setCurrentRow(row_hija)
        app.processEvents()
        time.sleep(0.05)
        app.processEvents()
        verifica(v.panel_organizacion.objetivo_nombre() == "hija", "panel objetivo hija tras clic")
        verifica(v._organizacion_objetivo_nombre == "hija", "visor objetivo hija tras clic")
        dest_drop = v._obtener_destino_drop_actual()
        esperado = os.path.normpath(os.path.join(DEST, "hija"))
        verifica(dest_drop is not None and os.path.normcase(os.path.normpath(dest_drop)) == os.path.normcase(esperado), f"destino drop hija -> {dest_drop} esperado {esperado}")
        # helper
        r = resolver_destino_drop(DEST, "hija")
        verifica(r is not None and os.path.normcase(os.path.normpath(r)) == os.path.normcase(esperado), f"resolver hija -> {r}")
        verifica(v._validar_destino_drop_actual() == True, "validar hija True")
        # emitido contiene hija
        verifica("hija" in emitted, f"emitido hija en {emitted}")
        v.close()
        try: v.gestor.cerrar()
        except: pass
        try: v.gestor_navegacion_destino.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

# ── 03 clic simple no navega ──
def test_03_clic_no_navega():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    tmp, db = _db()
    DEST = os.path.join(tmp, "DEST3")
    os.makedirs(os.path.join(DEST, "sub1"), exist_ok=True)
    os.makedirs(os.path.join(DEST, "sub2"), exist_ok=True)
    A = os.path.join(tmp, "A")
    os.makedirs(A, exist_ok=True)
    try:
        ruta_config = os.path.join(tmp, "config.json")
        _ins(db, A, "v0.mp4")
        v = visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(780, 540)
        v.show()
        _esperar_carga_estable(v, app)
        v.carpeta_seleccionada = os.path.abspath(A)
        _esperar_carga_estable(v, app)
        v.boton_modo_organizacion.setChecked(True)
        app.processEvents()
        v._organizacion_destino = DEST
        v._cargar_navegacion_destino()
        _esperar_navegacion(v, app)
        dest_before = v._organizacion_destino
        carpeta_before = v.carpeta_seleccionada
        # interceptar recarga
        recargas = []
        orig = v._programar_recarga_por_carpeta
        v._programar_recarga_por_carpeta = lambda: recargas.append(1) or orig()
        lista = v.panel_organizacion.lista_subcarpetas
        # encontrar sub1 row
        row = -1
        for i in range(lista.count()):
            if lista.item(i).text() == "sub1":
                row = i
                break
        lista.setCurrentRow(row)
        app.processEvents()
        time.sleep(0.08)
        app.processEvents()
        verifica(v._organizacion_destino == dest_before, "clic simple no cambia destino")
        verifica(v.carpeta_seleccionada == carpeta_before, "origen intacto tras clic")
        verifica(len(recargas) == 0, "clic no dispara recarga")
        # verificar que no cambió a sub1 path
        verifica("sub1" not in v._organizacion_destino or os.path.normcase(os.path.normpath(v._organizacion_destino)) == os.path.normcase(os.path.normpath(DEST)), "destino sigue raiz tras clic")
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

# ── 04 doble clic sí navega ──
def test_04_doble_clic_navega():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    tmp, db = _db()
    DEST = os.path.join(tmp, "DEST4")
    sub1 = os.path.join(DEST, "sub1")
    os.makedirs(os.path.join(sub1, "sub1a"), exist_ok=True)
    os.makedirs(DEST, exist_ok=True)
    A = os.path.join(tmp, "A")
    os.makedirs(A, exist_ok=True)
    try:
        _ins(db, A, "v0.mp4")
        ruta_config = os.path.join(tmp, "config.json")
        v = visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(780, 540)
        v.show()
        _esperar_carga_estable(v, app)
        v.carpeta_seleccionada = os.path.abspath(A)
        _esperar_carga_estable(v, app)
        v.boton_modo_organizacion.setChecked(True)
        app.processEvents()
        v._organizacion_destino = DEST
        v._cargar_navegacion_destino()
        _esperar_navegacion(v, app)
        carpeta_before = v.carpeta_seleccionada
        # Capturar señal navegar
        navegados = []
        orig_nav = v._navegar_destino_a_subcarpeta
        def spy_nav(n):
            navegados.append(n)
            return orig_nav(n)
        v._navegar_destino_a_subcarpeta = spy_nav
        # Simular doble clic en sub1 via signal itemDoubleClicked -> debe llamar navegar
        lista = v.panel_organizacion.lista_subcarpetas
        item = None
        for i in range(lista.count()):
            if lista.item(i).text() == "sub1":
                item = lista.item(i)
                break
        verifica(item is not None, "item sub1 existe para doble clic")
        # emitir doble clic
        lista.itemDoubleClicked.emit(item)
        _esperar_navegacion(v, app)
        # tras doble clic destino debe ser sub1
        verifica(v._organizacion_destino is not None and "sub1" in v._organizacion_destino, f"doble clic navega a sub1 ({v._organizacion_destino})")
        verifica(v.carpeta_seleccionada == carpeta_before, "origen intacto doble clic")
        verifica(len(navegados) >= 1, f"doble clic disparó navegar {navegados}")
        v._navegar_destino_a_subcarpeta = orig_nav
        v.close()
        try: v.gestor.cerrar()
        except: pass
        try: v.gestor_navegacion_destino.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

# ── 05 Entrar (botón) sí navega ──
def test_05_entrar_navega():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    tmp, db = _db()
    DEST = os.path.join(tmp, "DEST5")
    sub1 = os.path.join(DEST, "sub1")
    os.makedirs(sub1, exist_ok=True)
    os.makedirs(DEST, exist_ok=True)
    try:
        ruta_config = os.path.join(tmp, "config.json")
        v = visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(780, 540)
        v.show()
        _esperar_carga_estable(v, app)
        v.boton_modo_organizacion.setChecked(True)
        app.processEvents()
        v._organizacion_destino = DEST
        v._cargar_navegacion_destino()
        _esperar_navegacion(v, app)
        lista = v.panel_organizacion.lista_subcarpetas
        row = -1
        for i in range(lista.count()):
            if lista.item(i).text() == "sub1":
                row = i
                break
        lista.setCurrentRow(row)
        app.processEvents()
        time.sleep(0.05)
        app.processEvents()
        # Entrar via botón
        verifica(v.panel_organizacion.boton_entrar_destino.isEnabled(), "botón Entrar habilitado")
        v.panel_organizacion.boton_entrar_destino.click()
        _esperar_navegacion(v, app)
        verifica(v._organizacion_destino is not None and "sub1" in v._organizacion_destino, f"Entrar navega a sub1 ({v._organizacion_destino})")
        # también itemActivated (Enter)
        # volver a DEST
        v._navegar_destino_subir()
        _esperar_navegacion(v, app)
        verifica("sub1" not in v._organizacion_destino or os.path.normcase(os.path.normpath(v._organizacion_destino)) == os.path.normcase(os.path.normpath(DEST)), "subir vuelve")
        # seleccionar otra vez y emitir itemActivated
        row2 = -1
        for i in range(lista.count()):
            if lista.item(i).text() == "sub1":
                row2 = i
                lista.setCurrentRow(row2)
                break
        app.processEvents()
        item = lista.currentItem()
        lista.itemActivated.emit(item)
        _esperar_navegacion(v, app)
        verifica(v._organizacion_destino is not None and "sub1" in v._organizacion_destino, f"itemActivated (Enter) navega ({v._organizacion_destino})")
        v.close()
        try: v.gestor.cerrar()
        except: pass
        try: v.gestor_navegacion_destino.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

# ── 06 navegación/subir/destino nuevo resetean objetivo ──
def test_06_resets_objetivo():
    from PySide6.QtWidgets import QApplication, QFileDialog
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    tmp, db = _db()
    DEST = os.path.join(tmp, "DEST6")
    sub1 = os.path.join(DEST, "sub1")
    os.makedirs(os.path.join(sub1, "nested"), exist_ok=True)
    os.makedirs(DEST, exist_ok=True)
    OTRO = os.path.join(tmp, "OTRO")
    os.makedirs(OTRO, exist_ok=True)
    try:
        ruta_config = os.path.join(tmp, "config.json")
        v = visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(780, 540)
        v.show()
        _esperar_carga_estable(v, app)
        v.boton_modo_organizacion.setChecked(True)
        app.processEvents()
        v._organizacion_destino = DEST
        v._cargar_navegacion_destino()
        _esperar_navegacion(v, app)
        # seleccionar hija
        lista = v.panel_organizacion.lista_subcarpetas
        for i in range(lista.count()):
            if lista.item(i).text() == "sub1":
                lista.setCurrentRow(i)
                break
        app.processEvents()
        time.sleep(0.05)
        app.processEvents()
        verifica(v.panel_organizacion.objetivo_nombre() == "sub1", "objetivo sub1 antes reset")
        verifica(v._organizacion_objetivo_nombre == "sub1", "visor sub1 antes reset")
        # navegar -> reset
        v._navegar_destino_a_subcarpeta("sub1")
        _esperar_navegacion(v, app)
        verifica(v._organizacion_objetivo_nombre is None, "navegar resetea objetivo visor None")
        verifica(v.panel_organizacion.objetivo_nombre() is None, "navegar resetea panel None")
        verifica(v._obtener_destino_drop_actual() is not None and "sub1" in v._obtener_destino_drop_actual(), "drop tras navegar es raiz del nuevo destino")
        # seleccionar hija en nuevo destino si existe nested
        lista2 = v.panel_organizacion.lista_subcarpetas
        # si nested existe como hija de sub1
        has_nested = any(lista2.item(i).text() == "nested" for i in range(lista2.count()))
        if has_nested:
            for i in range(lista2.count()):
                if lista2.item(i).text() == "nested":
                    lista2.setCurrentRow(i)
                    break
            app.processEvents()
            time.sleep(0.05)
            app.processEvents()
            verifica(v._organizacion_objetivo_nombre == "nested", "objetivo nested seteado")
            # subir -> reset
            v._navegar_destino_subir()
            _esperar_navegacion(v, app)
            verifica(v._organizacion_objetivo_nombre is None, "subir resetea objetivo")
            verifica(v.panel_organizacion.objetivo_nombre() is None, "subir resetea panel")
        else:
            # igualmente probar subir resetea (aunque sin hija previa)
            v._navegar_destino_subir()
            _esperar_navegacion(v, app)
            verifica(v._organizacion_objetivo_nombre is None, "subir resetea objetivo (sin nested)")
        # destino nuevo via QFileDialog mock -> reset
        # primero setear objetivo de nuevo en DEST
        v._organizacion_destino = DEST
        v._cargar_navegacion_destino()
        _esperar_navegacion(v, app)
        lista3 = v.panel_organizacion.lista_subcarpetas
        for i in range(lista3.count()):
            if lista3.item(i).text() == "sub1":
                lista3.setCurrentRow(i)
                break
        app.processEvents()
        time.sleep(0.05)
        app.processEvents()
        verifica(v._organizacion_objetivo_nombre == "sub1", "objetivo set nuevo antes destino nuevo")
        orig_get = QFileDialog.getExistingDirectory
        QFileDialog.getExistingDirectory = lambda *a, **k: OTRO
        v._seleccionar_destino_organizacion()
        _esperar_navegacion(v, app)
        QFileDialog.getExistingDirectory = orig_get
        verifica(v._organizacion_objetivo_nombre is None, "destino nuevo resetea objetivo")
        verifica(v.panel_organizacion.objetivo_nombre() is None, "destino nuevo panel None")
        v.close()
        try: v.gestor.cerrar()
        except: pass
        try: v.gestor_navegacion_destino.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

# ── 07 hija desaparecida vuelve a raíz válida ──
def test_07_hija_desaparecida():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    tmp, db = _db()
    DEST = os.path.join(tmp, "DEST7")
    os.makedirs(os.path.join(DEST, "hija"), exist_ok=True)
    os.makedirs(os.path.join(DEST, "otra"), exist_ok=True)
    try:
        ruta_config = os.path.join(tmp, "config.json")
        v = visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(780, 540)
        v.show()
        _esperar_carga_estable(v, app)
        v.boton_modo_organizacion.setChecked(True)
        app.processEvents()
        v._organizacion_destino = DEST
        v._cargar_navegacion_destino()
        _esperar_navegacion(v, app)
        lista = v.panel_organizacion.lista_subcarpetas
        for i in range(lista.count()):
            if lista.item(i).text() == "hija":
                lista.setCurrentRow(i)
                break
        app.processEvents()
        time.sleep(0.05)
        app.processEvents()
        verifica(v._organizacion_objetivo_nombre == "hija", "objetivo hija seteado")
        # borrar hija del FS y recargar navegación
        shutil.rmtree(os.path.join(DEST, "hija"))
        v._cargar_navegacion_destino()
        _esperar_navegacion(v, app)
        verifica(v._organizacion_objetivo_nombre is None, "hija desaparecida -> objetivo None")
        verifica(v.panel_organizacion.objetivo_nombre() is None, "panel hija desaparecida None")
        verifica(v.panel_organizacion.objetivo_es_destino_raiz(), "objetivo_es_destino_raiz True tras desaparición")
        dest_drop = v._obtener_destino_drop_actual()
        verifica(dest_drop is not None and os.path.normcase(os.path.normpath(dest_drop)) == os.path.normcase(os.path.normpath(DEST)), f"drop vuelve a raiz ({dest_drop})")
        verifica(v._validar_destino_drop_actual() == True, "validar True tras desaparición (raiz válida)")
        v.close()
        try: v.gestor.cerrar()
        except: pass
        try: v.gestor_navegacion_destino.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

# ── 08 inválido/cargando/error -> None/False ──
def test_08_invalidos():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    tmp, db = _db()
    DEST = os.path.join(tmp, "DEST8")
    os.makedirs(DEST, exist_ok=True)
    try:
        ruta_config = os.path.join(tmp, "config.json")
        v = visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(780, 540)
        v.show()
        _esperar_carga_estable(v, app)
        v.boton_modo_organizacion.setChecked(True)
        app.processEvents()
        # invalido: no destino
        v.panel_organizacion.actualizar(None, False, False, destino_valido=False, subcarpetas=[], error=None, cargando=False)
        app.processEvents()
        verifica(v.panel_organizacion.objetivo_nombre() is None, "invalido (None destino) objetivo None")
        # visor invalid
        v._organizacion_destino = None
        v._organizacion_destino_valido = False
        v._organizacion_cargando = False
        v._organizacion_error = None
        v._organizacion_objetivo_nombre = None
        v._organizacion_objetivo_completo = None
        verifica(v._obtener_destino_drop_actual() is None, "invalido visor None")
        verifica(v._validar_destino_drop_actual() == False, "invalido validar False")
        # helper
        verifica(resolver_destino_drop(None, "hija") is None, "helper invalido destino None -> None")
        verifica(resolver_destino_drop("", "hija") is None, "helper destino vacio -> None")
        # cargando
        v._organizacion_destino = DEST
        v._organizacion_destino_valido = True
        v._organizacion_cargando = True
        v._organizacion_error = None
        v._organizacion_subcarpetas = ["hija"]
        v._actualizar_panel_organizacion()
        app.processEvents()
        verifica(v.panel_organizacion.objetivo_nombre() is None, "cargando objetivo None")
        verifica(v._obtener_destino_drop_actual() is None, "cargando drop None")
        verifica(v._validar_destino_drop_actual() == False, "cargando validar False")
        # error
        v._organizacion_cargando = False
        v._organizacion_error = "destino no disponible"
        v._organizacion_destino_valido = False
        v._actualizar_panel_organizacion()
        app.processEvents()
        verifica(v.panel_organizacion.objetivo_nombre() is None, "error objetivo None")
        verifica(v._obtener_destino_drop_actual() is None, "error drop None")
        verifica(v._validar_destino_drop_actual() == False, "error validar False")
        # helper edge: nombre con separador
        verifica(resolver_destino_drop(DEST, "a/b") is None, "helper nombre con / -> None")
        verifica(resolver_destino_drop(DEST, "..") is None, "helper .. -> None")
        verifica(resolver_destino_drop(DEST, "(vacío)") is None, "helper (vacío) -> None")
        verifica(validar_destino_drop_completo(None) == False, "validar None False")
        verifica(validar_destino_drop_completo("") == False, "validar vacio False")
        verifica(validar_destino_drop_completo("\x00bad") == False, "validar nulo False")
        v.close()
        try: v.gestor.cerrar()
        except: pass
        try: v.gestor_navegacion_destino.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

# ── 09 ocupado/gestor activo -> False ──
def test_09_ocupado():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    tmp, db = _db()
    DEST = os.path.join(tmp, "DEST9")
    os.makedirs(os.path.join(DEST, "hija"), exist_ok=True)
    try:
        ruta_config = os.path.join(tmp, "config.json")
        v = visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(780, 540)
        v.show()
        _esperar_carga_estable(v, app)
        v.boton_modo_organizacion.setChecked(True)
        app.processEvents()
        v._organizacion_destino = DEST
        v._cargar_navegacion_destino()
        _esperar_navegacion(v, app)
        # set objetivo hija válido
        lista = v.panel_organizacion.lista_subcarpetas
        for i in range(lista.count()):
            if lista.item(i).text() == "hija":
                lista.setCurrentRow(i)
                break
        app.processEvents()
        time.sleep(0.05)
        app.processEvents()
        verifica(v._validar_destino_drop_actual() == True, "pre ocupado validar True")
        # simular lote ocupado
        orig_ocup = v._lote_esta_ocupado
        v._lote_esta_ocupado = lambda: True
        v._actualizar_panel_organizacion()
        app.processEvents()
        verifica(v._validar_destino_drop_actual() == False, "ocupado lote -> validar False")
        # aunque destino cacheado, debe invalidar
        v._lote_esta_ocupado = orig_ocup
        # simular gestor activo via mock _lote_esta_ocupado que chequea gestor internamente
        # GestorTareas.activo es property sin setter, no forzar directamente
        # En cambio validamos que _validar_destino_drop_actual chequea gestor activo internamente:
        # mock _lote_esta_ocupado True simula gestor activo también
        v._lote_esta_ocupado = lambda: True
        verifica(v._validar_destino_drop_actual() == False, "gestor/lote ocupado -> validar False (simulado)")
        # restaurar
        v._lote_esta_ocupado = orig_ocup
        v._actualizar_panel_organizacion()
        app.processEvents()
        verifica(v._validar_destino_drop_actual() == True, "post ocupado validar True")
        v.close()
        try: v.gestor.cerrar()
        except: pass
        try: v.gestor_navegacion_destino.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

# ── 10 origen/filtros/orden/selección intactos ──
def test_10_origen_intacto():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    tmp, db = _db()
    A = os.path.join(tmp, "A")
    DEST = os.path.join(tmp, "DEST10")
    os.makedirs(A, exist_ok=True)
    os.makedirs(DEST, exist_ok=True)
    os.makedirs(os.path.join(DEST, "hija"), exist_ok=True)
    os.makedirs(os.path.join(DEST, "hija2"), exist_ok=True)
    try:
        for i in range(5):
            _ins(db, A, f"v{i}.mp4")
        ruta_config = os.path.join(tmp, "config.json")
        v = visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(780, 540)
        v.show()
        _esperar_carga_estable(v, app, min_tarjetas=5)
        v.carpeta_seleccionada = os.path.abspath(A)
        _esperar_carga_estable(v, app, min_tarjetas=5)
        v.busqueda.setText("v")
        app.processEvents()
        v._orden_catalogo = ("nombre", "asc")
        v._nombres_seleccionados = set(["v0.mp4", "v1.mp4"])
        app.processEvents()
        v.boton_modo_organizacion.setChecked(True)
        app.processEvents()
        v._organizacion_destino = DEST
        v._cargar_navegacion_destino()
        _esperar_navegacion(v, app)
        carpeta_before = v.carpeta_seleccionada
        filtro_before = v.busqueda.text()
        orden_before = v._orden_catalogo
        sel_before = set(v._nombres_seleccionados)
        # clic simple no debe alterar
        lista = v.panel_organizacion.lista_subcarpetas
        for i in range(lista.count()):
            if lista.item(i).text() == "hija":
                lista.setCurrentRow(i)
                break
        app.processEvents()
        time.sleep(0.05)
        app.processEvents()
        verifica(v.carpeta_seleccionada == carpeta_before, "clic origen intacto")
        verifica(v.busqueda.text() == filtro_before, "clic filtro intacto")
        verifica(v._orden_catalogo == orden_before, "clic orden intacto")
        verifica(set(v._nombres_seleccionados) == sel_before, "clic selección intacta")
        # doble clic / navegar tampoco
        v._navegar_destino_a_subcarpeta("hija2")
        _esperar_navegacion(v, app)
        verifica(v.carpeta_seleccionada == carpeta_before, "navegar origen intacto")
        verifica(v.busqueda.text() == filtro_before, "navegar filtro intacto")
        verifica(v._orden_catalogo == orden_before, "navegar orden intacto")
        verifica(set(v._nombres_seleccionados) == sel_before, "navegar selección intacta")
        # _al_objetivo_drop_seleccionado también no debe alterar
        v._al_objetivo_drop_seleccionado("hija2")
        verifica(v.carpeta_seleccionada == carpeta_before, "_al_objetivo origen intacto")
        verifica(set(v._nombres_seleccionados) == sel_before, "_al_objetivo selección intacta")
        v.close()
        try: v.gestor.cerrar()
        except: pass
        try: v.gestor_navegacion_destino.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

# ── 11 viewport maximum>0 preservado exactamente ──
def test_11_viewport():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    tmp, db = _db()
    A = os.path.join(tmp, "A")
    os.makedirs(A, exist_ok=True)
    for i in range(60):
        _ins(db, A, f"v{i:03d}.mp4")
    DEST = os.path.join(tmp, "DEST11")
    os.makedirs(os.path.join(DEST, "hija"), exist_ok=True)
    try:
        ruta_config = os.path.join(tmp, "config.json")
        v = visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(780, 320)
        v.show()
        _esperar_carga_estable(v, app, timeout=5.0, min_tarjetas=50)
        v.carpeta_seleccionada = os.path.abspath(A)
        _esperar_carga_estable(v, app, timeout=3.0, min_tarjetas=50)
        max_before = v.area.verticalScrollBar().maximum()
        verifica(max_before > 0, f"viewport maximum>0 antes ({max_before})")
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
        v.boton_modo_organizacion.setChecked(True)
        app.processEvents()
        time.sleep(0.08)
        app.processEvents()
        v._organizacion_destino = DEST
        v._cargar_navegacion_destino()
        _esperar_navegacion(v, app)
        # objetivo clic
        lista = v.panel_organizacion.lista_subcarpetas
        for i in range(lista.count()):
            if lista.item(i).text() == "hija":
                lista.setCurrentRow(i)
                break
        app.processEvents()
        time.sleep(0.05)
        app.processEvents()
        max_after = v.area.verticalScrollBar().maximum()
        after = v.area.verticalScrollBar().value()
        print(f"EVIDENCIA viewport B7.12 max {max_before}->{max_after} scroll {scroll_before}->{after}")
        verifica(max_after > 0, f"max preservado >0 tras objetivo ({max_after})")
        # maximum puede variar levemente por altura splitter; principal es >0 y scroll preservado
        verifica(max_after >= max_before * 0.9, f"maximum preservado razonable >=90% ({max_before}->{max_after})")
        verifica(abs(after - scroll_before) <= 2, f"scroll preservado tras objetivo {scroll_before}->{after} tol2")
        # navegar debe preservar también
        v._navegar_destino_a_subcarpeta("hija")
        _esperar_navegacion(v, app)
        max_nav = v.area.verticalScrollBar().maximum()
        val_nav = v.area.verticalScrollBar().value()
        verifica(max_nav > 0, f"max >0 tras navegar ({max_nav})")
        verifica(abs(val_nav - scroll_before) <= 2, f"scroll tras navegar {scroll_before}->{val_nav}")
        v.close()
        try: v.gestor.cerrar()
        except: pass
        try: v.gestor_navegacion_destino.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

# ── 12 panel sin FS/SQLite/FFmpeg ──
def test_12_panel_sin_fs():
    src = open("panel_organizacion.py", encoding="utf-8").read()
    # Filtrar docstring/comentarios para FFmpeg: solo código ejecutable
    import re
    code_lines = [l for l in src.splitlines() if not l.strip().startswith("#") and not l.strip().startswith('"""') and not l.strip().startswith("'''")]
    code_txt = "\n".join(code_lines)
    for kw in ["sqlite3", "conectar_bd", "escanear_videos", "lote_operaciones", "mover_video", "copiar_video", "subprocess", "QProcess", "QFileDialog.getExistingDirectory"]:
        verifica(kw not in src, f"panel sin {kw}")
    # FFmpeg/ffprobe permitidos en docstring pero no en código import
    has_ffmpeg_code = ("import ffmpeg" in code_txt.lower() or "from ffmpeg" in code_txt.lower() or "import ffprobe" in code_txt.lower())
    verifica(not has_ffmpeg_code, "panel código sin FFmpeg/ffprobe import")
    # Verificar que mención FFmpeg solo está en docstring inicial
    if "FFmpeg" in src:
        verifica(src.count("FFmpeg") <= 2 and '"""' in src, "FFmpeg solo en docstring")
    for kw in ["os.path.isdir", "os.path.isfile", "os.rename", "shutil", "os.remove", "os.listdir", "os.path.join"]:
        verifica(kw not in src, f"panel sin {kw}")
    verifica("import os" not in src, "panel no importa os")
    src_rutas = open("rutas.py", encoding="utf-8").read()
    verifica("def resolver_destino_drop" in src_rutas, "rutas resolver existe")
    verifica("def validar_destino_drop_completo" in src_rutas, "rutas validar existe")

# ── 13 invariantes dirigidas Pass B7.12/B7.13B (reconciliado B7.13B) ──
def test_13_pass():
    src_panel = open("panel_organizacion.py", encoding="utf-8").read()
    src_visor = open("visor_videos.py", encoding="utf-8").read()
    tree_panel = ast.parse(src_panel)
    tree_visor = ast.parse(src_visor)
    # panel total Pass 0
    cnt_panel = sum(1 for n in ast.walk(tree_panel) if isinstance(n, ast.Pass))
    verifica(cnt_panel == 0, f"panel Pass 0 ({cnt_panel})")
    # visor: no exigir exactamente 39; verificar invariantes dirigidas
    cnt_visor = sum(1 for n in ast.walk(tree_visor) if isinstance(n, ast.Pass))
    # No inflación por hacks: debe mantenerse en rango razonable HEAD (39 ± tolerancia)
    verifica(cnt_visor <= 45, f"visor Pass sin inflación hacks ({cnt_visor} <=45)")
    verifica(cnt_visor >= 30, f"visor Pass no vacío ({cnt_visor} >=30)")
    # métodos B7.12 relevantes no son solo-Pass y cero Pass interno
    for fname in ["_al_item_clic_objetivo", "_emitir_objetivo", "_al_seleccion_lista_cambia", "objetivo_nombre", "objetivo_es_destino_raiz"]:
        node = None
        for n in ast.walk(tree_panel):
            if isinstance(n, ast.FunctionDef) and n.name == fname:
                node = n
                break
        if node is not None:
            c = sum(1 for x in ast.walk(node) if isinstance(x, ast.Pass))
            verifica(c == 0, f"panel {fname} Pass 0 ({c})")
            # no es solo Pass
            is_only_pass = len(node.body) == 1 and isinstance(node.body[0], ast.Pass)
            verifica(not is_only_pass, f"panel {fname} no es solo-Pass")
        else:
            if fname in ["objetivo_nombre", "objetivo_es_destino_raiz"]:
                falla(f"panel {fname} no encontrado")
    for fname in ["_al_objetivo_drop_seleccionado", "_obtener_destino_drop_actual", "_validar_destino_drop_actual"]:
        node = None
        for n in ast.walk(tree_visor):
            if isinstance(n, ast.FunctionDef) and n.name == fname:
                node = n
                break
        verifica(node is not None, f"visor {fname} existe")
        if node is not None:
            c = sum(1 for x in ast.walk(node) if isinstance(x, ast.Pass))
            verifica(c == 0, f"visor {fname} Pass 0 ({c})")
            is_only_pass = len(node.body) == 1 and isinstance(node.body[0], ast.Pass)
            verifica(not is_only_pass, f"visor {fname} no es solo-Pass")
    # handlers B7.13B no son solo-Pass
    for fname in ["mousePressEvent", "mouseMoveEvent", "mouseReleaseEvent", "mouseDoubleClickEvent", "_ids_para_drag", "_visor_para_drag", "_crear_mime_data_drag_b713b"]:
        node = None
        for n in ast.walk(tree_visor):
            if isinstance(n, ast.FunctionDef) and n.name == fname:
                node = n
                break
        if node is not None:
            is_only_pass = len(node.body) == 1 and isinstance(node.body[0], ast.Pass)
            verifica(not is_only_pass, f"visor {fname} no es solo-Pass B7.13B")
            c = sum(1 for x in ast.walk(node) if isinstance(x, ast.Pass))
            verifica(c == 0, f"visor {fname} Pass 0 B7.13B ({c})")
    # no hay silencios genéricos nuevos: verificar que no hay except Pass vacíos aislados como hilos sueltos
    # contar líneas aisladas 'pass' ya cubierto; adicional: visor no contiene 'None' aislado como cuerpo except en bloque B7.13B
    b713b_section = ""
    for marker in ["_crear_mime_data_drag_b713b", "mousePressEvent", "mouseMoveEvent", "mouseReleaseEvent", "mouseDoubleClickEvent"]:
        idx = src_visor.find(marker)
        if idx != -1:
            b713b_section += src_visor[max(0, idx-100): idx+3000]
    # no hay líneas 'None' aisladas como cuerpo de except en zona B7.13B
    has_isolated_none = any(line.strip() == "None" for line in b713b_section.splitlines())
    verifica(not has_isolated_none, "B7.13B sin líneas None aisladas como cuerpo except")

# ── 14 cero except Exception nuevos ──
def test_14_except():
    src_panel = open("panel_organizacion.py", encoding="utf-8").read()
    src_visor = open("visor_videos.py", encoding="utf-8").read()
    verifica(src_panel.count("except Exception") == 0, f"panel 0 except Exception ({src_panel.count('except Exception')})")
    # visor total debe ser 108 (HEAD) y B7.12 sección no añade genérico
    # contar excepciones en zona B7.12 visor
    # extraer sección alrededor de métodos B7.12
    b712_section = ""
    for marker in ["_al_objetivo_drop_seleccionado", "_obtener_destino_drop_actual", "_validar_destino_drop_actual"]:
        idx = src_visor.find(marker)
        if idx != -1:
            b712_section += src_visor[max(0, idx-200): idx+2000]
    verifica("except Exception" not in b712_section, "B7.12 visor no añade except Exception")
    total = src_visor.count("except Exception")
    verifica(total == 108, f"visor total except Exception 108 igual HEAD ({total})")

# ── 15 ausencia drag&drop reconciliada B7.13A/B (B7.13B origen explícito) ──
# B7.12 exigía ausencia total; B7.13A/B añaden receptor en panel y origen en visor.
# Este test verifica separación vigente: PanelOrganizacion NO es origen, visor SÍ es origen B7.13B.
def test_15_no_drag():
    src_panel = open("panel_organizacion.py", encoding="utf-8").read()
    src_visor = open("visor_videos.py", encoding="utf-8").read()
    src_rutas = open("rutas.py", encoding="utf-8").read()
    # PanelOrganizacion NO es origen drag (sigue sin QDrag/startDrag)
    for kw in ["QDrag", "startDrag", "setDragEnabled"]:
        verifica(kw not in src_panel, f"panel sin origen {kw}")
    # Visor SÍ es origen B7.13B explícito (reconciliado, ya no se exige ausencia)
    verifica("QDrag" in src_visor, "visor con QDrag origen B7.13B explícito")
    verifica("QApplication.startDragDistance()" in src_visor, "visor con QApplication.startDragDistance() explícito")
    verifica("from PySide6.QtGui import" in src_visor and "QDrag" in src_visor, "visor importa QDrag explícito")
    # visor reutiliza MIME privado B7.13A y no duplica literal
    verifica("MIME_VIDEOS_IDS" in src_visor, "visor reutiliza MIME_VIDEOS_IDS B7.13A")
    verifica("from panel_organizacion import" in src_visor and "MIME_VIDEOS_IDS" in src_visor, "visor importa MIME desde panel (no duplica)")
    verifica(src_visor.count("application/x-visor-videos-ids-b713a") == 0, "visor sin literal MIME duplicado")
    # visor origen no ejecuta filesystem/SQLite/mover/copiar/lote desde ruta drag
    import inspect as _insp
    import visor_videos as _vv
    bloques_drag = []
    try:
        bloques_drag.append(_insp.getsource(_vv._crear_mime_data_drag_b713b))
    except Exception:
        pass
    try:
        bloques_drag.append(_insp.getsource(_vv.Tarjeta._ids_para_drag))
    except Exception:
        pass
    try:
        bloques_drag.append(_insp.getsource(_vv.Tarjeta.mousePressEvent))
    except Exception:
        pass
    try:
        bloques_drag.append(_insp.getsource(_vv.Tarjeta.mouseMoveEvent))
    except Exception:
        pass
    try:
        bloques_drag.append(_insp.getsource(_vv.Tarjeta.mouseReleaseEvent))
    except Exception:
        pass
    bloque_drag = "\n".join(bloques_drag)
    for kw in ["mover_video", "copiar_video", "TareaLoteOperaciones", "TareaMoverVideo", "TareaCopiarVideo", "sqlite3", "conectar_bd", "os.rename", "os.remove", "shutil"]:
        verifica(kw not in bloque_drag, f"visor drag bloque sin {kw}")
    verifica("os.path.join" not in bloque_drag, "visor drag bloque sin os.path.join")
    # panel sigue sin filesystem/SQLite/operaciones reales
    for kw in ["mover_video", "copiar_video", "lote_operaciones", "sqlite3", "conectar_bd"]:
        verifica(kw not in src_panel, f"panel sin {kw} (separacion arquitectonica)")
    for kw in ["os.path.isdir", "os.path.isfile", "os.rename", "shutil"]:
        verifica(kw not in src_panel, f"panel sin {kw} (sin FS)")
    verifica("import os" not in src_panel, "panel no importa os (separacion)")
    # receptor B7.13A sí existe en panel (reconciliado) y visor/rutas siguen sin drag receptor propio
    verifica("setAcceptDrops" in src_panel, "panel con setAcceptDrops (receptor B7.13A reconciliado)")
    verifica("dragEnterEvent" in src_panel, "panel con dragEnterEvent (receptor)")
    verifica("dropEvent" in src_panel, "panel con dropEvent (receptor)")
    verifica("dropVideosSolicitado" in src_panel, "panel con senal dropVideosSolicitado")
    verifica("setAcceptDrops" not in src_visor, "visor sin setAcceptDrops (sin receptor)")
    verifica("dragEnterEvent" not in src_visor, "visor sin dragEnterEvent")
    verifica("dropEvent" not in src_visor or "dropVideosSolicitado" not in src_visor, "visor sin dropEvent propio")
    verifica("setAcceptDrops" not in src_rutas, "rutas sin setAcceptDrops")
    # panel no implementa origen drag genérico (solo receptor)
    verifica("QDrag" not in src_panel, "panel sin QDrag (solo receptor, no origen)")
    # sin aliases/hacks en visor
    for bad in ["_ClaseArrastre", "_qtgui_mod", "_sys_b713b"]:
        verifica(bad not in src_visor, f"visor sin alias {bad}")
    verifica('"Q" + "Drag"' not in src_visor, "visor sin hack Q+Drag")
    verifica('"start" + "DragDistance"' not in src_visor, "visor sin hack start+DragDistance")
    # B7.12 objetivo/navegación intacta
    verifica("objetivoSeleccionado" in src_panel, "panel conserva objetivoSeleccionado B7.12")
    verifica("objetivo_nombre" in src_panel, "panel conserva objetivo_nombre B7.12")

# ── 16 smoke Qt offscreen raíz+hija sin crash + viewport preservado segundo chequeo ──
def test_16_smoke():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    tmp, db = _db()
    A = os.path.join(tmp, "A")
    DEST = os.path.join(tmp, "DEST16")
    os.makedirs(A, exist_ok=True)
    os.makedirs(DEST, exist_ok=True)
    os.makedirs(os.path.join(DEST, "hija"), exist_ok=True)
    try:
        for i in range(10):
            _ins(db, A, f"v{i}.mp4")
        ruta_config = os.path.join(tmp, "config.json")
        v = visor_videos.VisorVideos(ruta_db=db, ruta_config=ruta_config)
        v.resize(780, 320)
        v.show()
        _esperar_carga_estable(v, app, min_tarjetas=10)
        v.carpeta_seleccionada = os.path.abspath(A)
        _esperar_carga_estable(v, app, min_tarjetas=10)
        max_before = v.area.verticalScrollBar().maximum()
        # puede ser 0 con pocas tarjetas, solo verificar no crash
        v.boton_modo_organizacion.setChecked(True)
        app.processEvents()
        time.sleep(0.05)
        app.processEvents()
        v._organizacion_destino = DEST
        v._cargar_navegacion_destino()
        _esperar_navegacion(v, app)
        lista = v.panel_organizacion.lista_subcarpetas
        for i in range(lista.count()):
            if lista.item(i).text() == "hija":
                lista.setCurrentRow(i)
                break
        app.processEvents()
        time.sleep(0.05)
        app.processEvents()
        # navegar y verificar no crash, viewport si >0 preservado
        v._navegar_destino_a_subcarpeta("hija")
        _esperar_navegacion(v, app)
        verifica(True, "smoke raíz+hija sin crash")
        if max_before > 0:
            max_after = v.area.verticalScrollBar().maximum()
            verifica(max_after > 0, f"smoke max >0 preservado ({max_after})")
        v.close()
        try: v.gestor.cerrar()
        except: pass
        try: v.gestor_navegacion_destino.cerrar()
        except: pass
        try: v.gestor_lote.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def main():
    print("=== B7.12 prueba_objetivo_drop_b712 ===")
    for fn in [test_01_raiz_valida, test_02_hija_clic_simple, test_03_clic_no_navega, test_04_doble_clic_navega, test_05_entrar_navega, test_06_resets_objetivo, test_07_hija_desaparecida, test_08_invalidos, test_09_ocupado, test_10_origen_intacto, test_11_viewport, test_12_panel_sin_fs, test_13_pass, test_14_except, test_15_no_drag, test_16_smoke]:
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
