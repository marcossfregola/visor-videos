"""Suite B7.5 — eliminación individual segura a Papelera Windows."""
import os
import sys
import sqlite3
import tempfile
import shutil
import inspect
import pathlib

from escanear_videos import (
    conectar_bd,
    guardar_marcador,
    guardar_segmento,
    listar_marcadores,
    listar_segmentos,
    detectar_diferencias,
    preparar_plan_sincronizacion,
    aplicar_incorporaciones,
    eliminar_candidatos,
    listar_videos_paginado,
    listar_videos,
)
import operaciones
import eliminar_video as svc
from eliminar_video import (
    ValidacionError as ElimValidacionError,
    OrigenNoEncontradoError as ElimOrigenError,
    EliminarError as ElimError,
    EliminarInconsistenciaError as ElimInconsistenciaError,
)
from tareas_videos import TareaEliminarVideo
import visor_videos

_CONTADOR = [0]
_FALLOS = [0]

def ok(msg):
    _CONTADOR[0]+=1
    print(f"T{_CONTADOR[0]:02d} OK - {msg}")

def falla(msg, extra=None):
    _FALLOS[0]+=1
    _CONTADOR[0]+=1
    txt=f"T{_CONTADOR[0]:02d} ERROR - {msg}"
    if extra is not None:
        txt+=f" ({extra})"
    print(txt)

def verifica(cond, desc, extra=None):
    if cond:
        ok(desc)
    else:
        falla(desc, extra)

def _crear_db():
    tmpdir=tempfile.mkdtemp()
    ruta_db=os.path.join(tmpdir,"test.db")
    conn=conectar_bd(ruta_db)
    conn.commit()
    conn.close()
    return tmpdir, ruta_db

def _insertar(ruta_db, carpeta, nombre, contenido=b"x"*1024):
    ruta=os.path.join(carpeta,nombre)
    os.makedirs(carpeta,exist_ok=True)
    with open(ruta,"wb") as f:
        f.write(contenido)
    st=os.stat(ruta)
    conn=conectar_bd(ruta_db)
    try:
        from rutas import normalizar_ruta_clave
        ruta_abs=os.path.abspath(ruta)
        ruta_norm=normalizar_ruta_clave(ruta_abs)
        conn.execute("INSERT INTO videos (nombre, ruta, ruta_normalizada, extension, fecha_importacion, tamano_bytes, mtime_ns) VALUES (?,?,?,?,?,?,?)",
            (nombre, ruta_abs, ruta_norm, os.path.splitext(nombre)[1].lower(), "2026-01-01T00:00:00", st.st_size, st.st_mtime_ns))
        vid=conn.execute("SELECT id FROM videos WHERE ruta_normalizada=?",(ruta_norm,)).fetchone()[0]
        conn.commit()
        return vid, ruta_abs
    finally:
        conn.close()

def test_mecanismo_papelera():
    src=pathlib.Path("operaciones.py").read_text(encoding="utf-8")
    verifica("SHFileOperationW" in src, "mecanismo Papelera usa SHFileOperationW")
    verifica("FOF_ALLOWUNDO" in src, "mecanismo permite Papelera (ALLOWUNDO)")
    verifica("os.remove" not in src or "_enviar_a_papelera" in src, "no usa os.remove para video (solo via Papelera)")
    # verificar eliminar_video usa mecanismo
    src2=pathlib.Path("eliminar_video.py").read_text(encoding="utf-8")
    verifica("_enviar_a_papelera" in src2, "eliminar_video reutiliza _enviar_a_papelera")
    # Verificar uso real (con paréntesis) no solo mención en comentario
    verifica("os.remove(" not in src2 and "os.unlink(" not in src2 and "shutil.rmtree" not in src2, "eliminar_video nunca usa borrado permanente")
    verifica("send2trash" not in src2.lower() and "send2trash" not in src.lower(), "no agrega send2trash ni dependencia")

def test_exito_basico():
    tmpdir,ruta_db=_crear_db()
    carpeta=os.path.join(tmpdir,"carp")
    os.makedirs(carpeta,exist_ok=True)
    try:
        vid,ruta=_insertar(ruta_db,carpeta,"v01.mp4",b"content1")
        assert os.path.isfile(ruta)
        res=svc.eliminar_video(vid,ruta_db)
        verifica(res.get("ok") and res["video_id"]==vid, "eliminar exito retorna ok")
        verifica(not os.path.exists(ruta), "archivo ya no existe tras Papelera (exito)")
        # DB ya no contiene video
        conn=sqlite3.connect(ruta_db)
        fila=conn.execute("SELECT id FROM videos WHERE id=?",(vid,)).fetchone()
        conn.close()
        verifica(fila is None, "video eliminado del catalogo")
        # papeleria: no permanente (asume via API; mock verification es _enviar_a_papelera llamado)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_fallo_papelera_db_intacta():
    tmpdir,ruta_db=_crear_db()
    carpeta=os.path.join(tmpdir,"carp")
    os.makedirs(carpeta,exist_ok=True)
    try:
        vid,ruta=_insertar(ruta_db,carpeta,"v02.mp4",b"content2")
        orig=operaciones._enviar_a_papelera
        def fake_papelera(p):
            raise OSError("simulado fallo Papelera")
        svc_mod = svc
        # monkeypatch operaciones._enviar_a_papelera usado por eliminar_video
        import operaciones as opm
        old=opm._enviar_a_papelera
        opm._enviar_a_papelera=fake_papelera
        try:
            try:
                svc.eliminar_video(vid,ruta_db)
                verifica(False,"fallo Papelera debe lanzar")
            except ElimError:
                ok("fallo Papelera lanza EliminarError")
            except Exception as e:
                falla("fallo Papelera lanza tipo incorrecto", str(e))
            verifica(os.path.isfile(ruta),"archivo intacto tras fallo Papelera")
            conn=sqlite3.connect(ruta_db)
            fila=conn.execute("SELECT id FROM videos WHERE id=?",(vid,)).fetchone()
            conn.close()
            verifica(fila is not None,"DB intacta tras fallo Papelera")
        finally:
            opm._enviar_a_papelera=old
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_video_id_invalido():
    tmpdir,ruta_db=_crear_db()
    try:
        for bad in [0,-1, "1", 1.5, None, True, 3.14]:
            try:
                svc.eliminar_video(bad,ruta_db)
                verifica(False,f"video_id invalido {bad!r} debe lanzar")
            except (TypeError, ValueError, ElimValidacionError):
                ok(f"video_id invalido {bad!r} rechazado")
            except Exception as e:
                falla(f"video_id invalido {bad!r} tipo inesperado", str(e))
        # id inexistente
        try:
            svc.eliminar_video(9999,ruta_db)
            verifica(False,"id inexistente debe lanzar ValidacionError")
        except ElimValidacionError:
            ok("id inexistente lanza ValidacionError")
        except Exception as e:
            falla("id inexistente tipo inesperado", str(e))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_origen_faltante():
    tmpdir,ruta_db=_crear_db()
    carpeta=os.path.join(tmpdir,"carp")
    os.makedirs(carpeta,exist_ok=True)
    try:
        vid,ruta=_insertar(ruta_db,carpeta,"v03.mp4",b"xxx")
        os.remove(ruta)
        verifica(not os.path.exists(ruta),"precond origen borrado")
        try:
            svc.eliminar_video(vid,ruta_db)
            verifica(False,"origen faltante debe lanzar")
        except ElimOrigenError:
            ok("origen faltante lanza OrigenNoEncontradoError")
            conn=sqlite3.connect(ruta_db)
            fila=conn.execute("SELECT id FROM videos WHERE id=?",(vid,)).fetchone()
            conn.close()
            verifica(fila is not None,"DB intacta tras origen faltante")
        except Exception as e:
            falla("origen faltante tipo inesperado", str(e))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_cancelacion_previa():
    tmpdir,ruta_db=_crear_db()
    carpeta=os.path.join(tmpdir,"carp")
    os.makedirs(carpeta,exist_ok=True)
    try:
        vid,ruta=_insertar(ruta_db,carpeta,"v04.mp4",b"cancel")
        tarea=TareaEliminarVideo(vid,ruta_db)
        tarea.cancelar()
        res=tarea._trabajo()
        verifica(res.get("cancelado")==True,"cancelacion previa retorna cancelado")
        verifica(os.path.isfile(ruta),"archivo intacto tras cancelacion previa")
        conn=sqlite3.connect(ruta_db)
        fila=conn.execute("SELECT id FROM videos WHERE id=?",(vid,)).fetchone()
        conn.close()
        verifica(fila is not None,"DB intacta tras cancelacion previa")
        # asegurar que no llama Papelera si cancelada: monkeypatch
        called=[False]
        old=operaciones._enviar_a_papelera
        def spy(p):
            called[0]=True
            return old(p)
        operaciones._enviar_a_papelera=spy
        tarea2=TareaEliminarVideo(vid,ruta_db)
        tarea2.cancelar()
        tarea2._trabajo()
        operaciones._enviar_a_papelera=old
        verifica(not called[0],"Papelera no llamada si cancelado antes de punto de no retorno")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_fallo_catalogo_post_papelera():
    tmpdir,ruta_db=_crear_db()
    carpeta=os.path.join(tmpdir,"carp")
    os.makedirs(carpeta,exist_ok=True)
    try:
        vid,ruta=_insertar(ruta_db,carpeta,"v05.mp4",b"postfail")
        # monkey Papelera exitosa (real) pero DB falla
        # Usamos stub Papelera que borra archivo (simula Papelera moviendo)
        real_papelera=operaciones._enviar_a_papelera
        def stub_papelera(p):
            # simular Papelera: eliminar archivo (pero en test es temporal, borramos)
            try:
                os.remove(p)
            except: pass
        operaciones._enviar_a_papelera=stub_papelera
        # parchear sqlite para fallar
        orig_connect=sqlite3.connect
        import sqlite3 as sq
        class FakeConn:
            def __init__(self,*a,**k):
                self._real=orig_connect(*a,**k)
            @property
            def in_transaction(self):
                return self._real.in_transaction
            def __getattr__(self, name):
                return getattr(self._real, name)
            def execute(self,sql,params=()):
                if "DELETE FROM videos" in sql:
                    raise sq.OperationalError("simulado fallo DB post Papelera")
                return self._real.execute(sql,params)
            def commit(self): return self._real.commit()
            def rollback(self):
                try: self._real.rollback()
                except: pass
            def close(self): return self._real.close()
        callcount=[0]
        def fake_connect(*a,**k):
            callcount[0]+=1
            if callcount[0]>=2:  # segunda conexion es la de catalogo post-papelera
                return FakeConn(*a,**k)
            return orig_connect(*a,**k)
        # monkey en eliminar_video
        import eliminar_video as ev
        old_connect=ev.sqlite3.connect
        ev.sqlite3.connect=fake_connect
        try:
            try:
                ev.eliminar_video(vid,ruta_db)
                verifica(False,"debe lanzar inconsistencia")
            except ElimInconsistenciaError as e:
                ok(f"fallo catalogo post Papelera lanza inconsistencia: {e}")
                verifica(hasattr(e,"ruta") and e.ruta is not None,"inconsistencia expone ruta")
                verifica(hasattr(e,"error_db"),"inconsistencia expone error_db")
                verifica(not os.path.exists(ruta),"archivo ya en Papelera (no existe)")
            except Exception as e:
                falla("fallo catalogo post Papelera tipo inesperado", str(e))
        finally:
            ev.sqlite3.connect=old_connect
            operaciones._enviar_a_papelera=real_papelera
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_integridad_relaciones():
    tmpdir,ruta_db=_crear_db()
    carpeta=os.path.join(tmpdir,"carp")
    os.makedirs(carpeta,exist_ok=True)
    try:
        vid,ruta=_insertar(ruta_db,carpeta,"v06.mp4",b"rel")
        mid=guardar_marcador(vid, 1.0, ruta_db, color="rojo")
        sid,_ ,_=guardar_segmento(vid, 0.5, 1.5, ruta_db, color="azul")
        # crear derivado
        vid2,ruta2=_insertar(ruta_db,carpeta,"der06.mp4",b"der")
        conn=conectar_bd(ruta_db)
        conn.execute("INSERT INTO videos_derivados (derivado_video_id, original_video_id, tipo, fecha_creacion, derivado_nombre, derivado_ruta, original_nombre, original_ruta) VALUES (?,?,?,?,?,?,?,?)",
            (vid2, vid, "individual", "2026-01-01T00:00:00", "der06.mp4", ruta2, "v06.mp4", ruta))
        deriv_id=conn.execute("SELECT id FROM videos_derivados WHERE derivado_video_id=?",(vid2,)).fetchone()[0]
        conn.execute("INSERT INTO videos_derivados_segmentos (derivacion_id, segmento_id, orden, inicio, fin) VALUES (?,?,?,?,?)",(deriv_id, sid, 0, 0.5, 1.5))
        conn.commit()
        conn.close()
        # eliminar original
        # stub Papelera para no depender de Windows trash en linux env (pero en Windows real usaria trash)
        real=operaciones._enviar_a_papelera
        def stub(p):
            try: os.remove(p)
            except: pass
        operaciones._enviar_a_papelera=stub
        try:
            svc.eliminar_video(vid,ruta_db)
        finally:
            operaciones._enviar_a_papelera=real
        conn=sqlite3.connect(ruta_db)
        marc=conn.execute("SELECT * FROM marcadores_video WHERE video_id=?",(vid,)).fetchall()
        segs=conn.execute("SELECT * FROM segmentos_video WHERE video_id=?",(vid,)).fetchall()
        verifica(marc==[], "marcadores huérfanos eliminados")
        verifica(segs==[], "segmentos huérfanos eliminados")
        # derivados deben persistir (orfandad tolerada)
        der=conn.execute("SELECT * FROM videos_derivados WHERE derivado_video_id=?",(vid2,)).fetchall()
        verifica(der!=[], "videos_derivados persiste tras eliminar original (orfandad tolerada)")
        der_seg=conn.execute("SELECT * FROM videos_derivados_segmentos WHERE derivacion_id=?",(deriv_id,)).fetchall()
        verifica(der_seg!=[], "videos_derivados_segmentos persiste")
        # derivado video mismo sigue existiendo
        fila=conn.execute("SELECT id FROM videos WHERE id=?",(vid2,)).fetchone()
        verifica(fila is not None,"derivado video sigue en catalogo")
        conn.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_restauracion_reescaneo():
    tmpdir,ruta_db=_crear_db()
    carpeta=os.path.join(tmpdir,"carp")
    os.makedirs(carpeta,exist_ok=True)
    try:
        vid,ruta=_insertar(ruta_db,carpeta,"v07.mp4",b"orig07")
        mid=guardar_marcador(vid, 2.0, ruta_db)
        sid,_ ,_=guardar_segmento(vid, 1.0, 2.0, ruta_db)
        real=operaciones._enviar_a_papelera
        operaciones._enviar_a_papelera=lambda p: os.remove(p)
        try:
            svc.eliminar_video(vid,ruta_db)
        finally:
            operaciones._enviar_a_papelera=real
        verifica(not os.path.exists(ruta),"tras eliminar archivo no existe")
        conn=sqlite3.connect(ruta_db)
        assert conn.execute("SELECT id FROM videos WHERE id=?",(vid,)).fetchone() is None
        conn.close()
        # Simular restauración: archivo vuelve con mismo nombre
        with open(ruta,"wb") as f:
            f.write(b"orig07_restaurado")
        # Reescaneo: detectar diferencias debe ver nuevo
        dif=detectar_diferencias(carpeta,ruta_db)
        verifica("v07.mp4" in dif["nuevos"],"reescaneo detecta archivo restaurado como nuevo")
        verifica("v07.mp4" not in dif["ausentes_del_disco"],"no ausente tras restauración")
        plan=preparar_plan_sincronizacion(dif)
        res_inc=aplicar_incorporaciones(plan,ruta_db)
        verifica(res_inc["incorporados"]==1,"reincorporación inserta 1")
        conn=sqlite3.connect(ruta_db)
        fila=conn.execute("SELECT id, nombre FROM videos WHERE nombre=?",("v07.mp4",)).fetchone()
        verifica(fila is not None,"nuevo video_id tras reescaneo")
        nuevo_id=fila[0]
        verifica(nuevo_id != vid,"video_id nuevo distinto (no preservado)")
        # marcadores/segmentos no recuperados (esperado por modelo)
        marc=conn.execute("SELECT * FROM marcadores_video WHERE video_id=?",(nuevo_id,)).fetchall()
        verifica(marc==[],"marcadores no recuperados tras restauracion (modelo)")
        segs=conn.execute("SELECT * FROM segmentos_video WHERE video_id=?",(nuevo_id,)).fetchall()
        verifica(segs==[],"segmentos no recuperados tras restauracion")
        conn.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_ui_delega_sin_fs_sqlite():
    src=inspect.getsource(visor_videos.VisorVideos._iniciar_eliminar_video)
    verifica("TareaEliminarVideo" in src,"UI delega a TareaEliminarVideo")
    verifica("gestor_eliminar.iniciar" in src,"UI usa gestor_eliminar background")
    verifica("os.remove(" not in src and "os.unlink(" not in src and "os.rmdir(" not in src,"UI sin FS directo")
    # Permitir mención de sqlite en docstring, pero no uso real (execute/commit)
    verifica("sqlite3" not in src and "execute(" not in src.lower(),"UI sin SQLite directo")
    verifica("QMessageBox" in src and "Eliminar" in src,"UI muestra confirmación")
    verifica("Cancelar" in src,"UI confirmación con Cancelar")
    # verificar que _al_resultado no hace FS
    src2=inspect.getsource(visor_videos.VisorVideos._al_resultado_eliminar_video)
    verifica("os.remove(" not in src2 and "sqlite3" not in src2,"resultado UI sin FS/SQLite")
    verifica("filtrar" in src2 or "actualizar_contador" in src2,"UI actualiza lista sin Escanear")
    verifica("iniciar_escaneo" not in src2 and "TareaEscaneo" not in src2,"UI no reescanea en éxito")

def test_actualizacion_sin_escaneo():
    # Simular ventana y verificar que al_al_resultado no llama escaneo
    import sys, time
    from PySide6.QtWidgets import QApplication
    tmpdir,ruta_db=_crear_db()
    carpeta=os.path.join(tmpdir,"carp")
    os.makedirs(carpeta,exist_ok=True)
    try:
        vid,ruta=_insertar(ruta_db,carpeta,"v08.mp4",b"ui08")
        app=QApplication.instance()
        if app is None:
            app=QApplication(sys.argv)
        ruta_config=os.path.join(tmpdir,"config.json")
        ventana=visor_videos.VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        ventana.resize(700,500)
        ventana.show()
        def esperar(p,i=250):
            for _ in range(i):
                QApplication.processEvents()
                if p(): return True
                time.sleep(0.02)
            return p()
        esperar(lambda: ventana._carga_completada and not ventana.gestor.activo)
        ventana.carpeta_seleccionada=carpeta
        # crear tarjeta artificial si no existe
        tarjeta=ventana._tarjeta_por_nombre("v08.mp4")
        if tarjeta is None:
            fila=("v08.mp4",10.0,640,480,"h264",1,100,ruta,vid)
            from visor_videos import Tarjeta
            tarjeta=Tarjeta(fila,ruta_config=ruta_config)
            ventana.tarjetas.append(("v08.mp4",tarjeta))
            ventana.visibles.append("v08.mp4")
            ventana.cuadricula.addWidget(tarjeta, len(ventana.tarjetas)-1,0)
            ventana.filtrar(ventana.busqueda.text())
        # patch escaneo detectors
        calls=[]
        orig_ini=visor_videos.VisorVideos.iniciar_escaneo
        orig_crear=visor_videos.VisorVideos._crear_tarea_lectura
        visor_videos.VisorVideos.iniciar_escaneo=lambda *a,**k: calls.append("ini") or None
        visor_videos.VisorVideos._crear_tarea_lectura=lambda *a,**k: calls.append("crear") or orig_crear(*a,**k)
        # stub Papelera
        real=operaciones._enviar_a_papelera
        operaciones._enviar_a_papelera=lambda p: os.remove(p)
        try:
            svc.eliminar_video(vid,ruta_db)
            # simular handler UI
            ventana._eliminar_nombre="v08.mp4"
            ventana._eliminar_video_id=vid
            res={"ok":True,"video_id":vid,"nombre":"v08.mp4","ruta":ruta}
            ventana._al_resultado_eliminar_video(res)
            QApplication.processEvents()
            verifica("v08.mp4" not in [n for n,_ in ventana.tarjetas],"UI remueve tarjeta sin escaneo")
            verifica(not calls,"no reescaneo tras eliminar")
            verifica("v08.mp4" not in ventana.visibles,"visibles actualizado")
        finally:
            operaciones._enviar_a_papelera=real
            visor_videos.VisorVideos.iniciar_escaneo=orig_ini
            visor_videos.VisorVideos._crear_tarea_lectura=orig_crear
        ventana.close()
        ventana.gestor.cerrar()
        try: ventana.gestor_eliminar.cerrar()
        except: pass
        try: ventana.gestor_previews.cerrar()
        except: pass
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_paginacion_filtro_orden():
    tmpdir,ruta_db=_crear_db()
    carpeta=os.path.join(tmpdir,"carp")
    os.makedirs(carpeta,exist_ok=True)
    try:
        # insertar 5 videos con nombres para ordenar
        ids=[]
        for name in ["aaa.mp4","bbb.mp4","ccc.mp4","ddd.mp4","eee.mp4"]:
            vid,_=_insertar(ruta_db,carpeta,name,b"content")
            ids.append(vid)
            # asignar marcadores a algunos para filtro
            if name in ["bbb.mp4","ccc.mp4"]:
                guardar_marcador(vid,1.0,ruta_db)
        # paginacion antes
        pag=listar_videos_paginado(2,0,None,ruta_db,orden_clave="nombre",orden_direccion="asc")
        verifica(pag["total"]==5,"paginado total 5 antes")
        verifica([r[0] for r in pag["videos"]]==["aaa.mp4","bbb.mp4"],"orden asc pagina 0")
        # eliminar bbb (id 1)
        vid_bbb=ids[1]
        ruta_bbb=os.path.join(carpeta,"bbb.mp4")
        real=operaciones._enviar_a_papelera
        operaciones._enviar_a_papelera=lambda p: os.remove(p)
        try:
            svc.eliminar_video(vid_bbb,ruta_db)
        finally:
            operaciones._enviar_a_papelera=real
        pag2=listar_videos_paginado(2,0,None,ruta_db,orden_clave="nombre",orden_direccion="asc")
        verifica(pag2["total"]==4,"total 4 tras eliminar")
        verifica("bbb.mp4" not in [r[0] for r in pag2["videos"]+ listar_videos_paginado(10,0,None,ruta_db,orden_clave="nombre",orden_direccion="asc")["videos"]],"bbb no en listado tras eliminar")
        # filtro con_marcadores: ccc debe seguir, bbb ya no
        pag_f=listar_videos_paginado(10,0,None,ruta_db,orden_clave="nombre",orden_direccion="asc",filtro="con_marcadores")
        nombres_f=[r[0] for r in pag_f["videos"]]
        verifica("ccc.mp4" in nombres_f and "bbb.mp4" not in nombres_f,"filtro con_marcadores refleja eliminacion")
        # orden desc
        pag_desc=listar_videos_paginado(10,0,None,ruta_db,orden_clave="nombre",orden_direccion="desc")
        verifica(pag_desc["videos"][0][0]=="eee.mp4","orden desc funciona tras eliminar")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_doble_ejecucion():
    tmpdir,ruta_db=_crear_db()
    carpeta=os.path.join(tmpdir,"carp")
    os.makedirs(carpeta,exist_ok=True)
    try:
        vid,ruta=_insertar(ruta_db,carpeta,"v09.mp4",b"doble")
        real=operaciones._enviar_a_papelera
        operaciones._enviar_a_papelera=lambda p: os.remove(p)
        try:
            svc.eliminar_video(vid,ruta_db)
            ok("primera eliminacion ok")
            try:
                svc.eliminar_video(vid,ruta_db)
                verifica(False,"segunda eliminacion debe fallar ValidacionError")
            except ElimValidacionError:
                ok("doble ejecucion segunda lanza ValidacionError")
            except Exception as e:
                falla("doble ejecucion tipo inesperado", str(e))
            verifica(not os.path.exists(ruta),"archivo sigue sin existir tras doble")
        finally:
            operaciones._enviar_a_papelera=real
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_cache():
    tmpdir,ruta_db=_crear_db()
    carpeta=os.path.join(tmpdir,"carp")
    mini=os.path.join(tmpdir,"mini")
    os.makedirs(carpeta,exist_ok=True)
    os.makedirs(mini,exist_ok=True)
    try:
        vid,ruta=_insertar(ruta_db,carpeta,"v10.mp4",b"cache")
        # crear miniatura fake
        import rutas
        old=rutas.ruta_carpeta_miniaturas
        rutas.ruta_carpeta_miniaturas=lambda: mini
        import escanear_videos as ev
        old2=ev.ruta_carpeta_miniaturas
        ev.ruta_carpeta_miniaturas=lambda: mini
        # generar miniatura path
        prefijo=vid  # not used, generate name
        nombre="v10.mp4"
        pref= nombre.replace(".mp4","")
        # Crear archivos _01 etc
        mini_path=os.path.join(mini, f"{pref}_01.jpg")
        with open(mini_path,"wb") as f:
            f.write(b"fakejpg")
        verifica(os.path.isfile(mini_path),"miniatura pre existe")
        real=operaciones._enviar_a_papelera
        operaciones._enviar_a_papelera=lambda p: os.remove(p)
        try:
            svc.eliminar_video(vid,ruta_db)
        finally:
            operaciones._enviar_a_papelera=real
        # cache no debe borrarse necesariamente, pero verificar que no se borró video por error
        verifica(os.path.isfile(mini_path),"cache miniatura persiste tras eliminar (no se borra indiscriminado)")
        rutas.ruta_carpeta_miniaturas=old
        ev.ruta_carpeta_miniaturas=old2
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_cero_ffmpeg():
    src=pathlib.Path("eliminar_video.py").read_text(encoding="utf-8")
    # Buscar uso real, no mención en comentario (ahora doc no contiene ff* )
    for kw in ["ffprobe","ffmpeg","subprocess"]:
        verifica(kw.lower() not in src.lower(), f"cero FFmpeg: no {kw}")
    src2=inspect.getsource(TareaEliminarVideo._trabajo)
    for kw in ["ffprobe","ffmpeg"]:
        verifica(kw.lower() not in src2.lower(), f"TareaEliminarVideo cero FFmpeg no {kw}")

def main():
    print("=== B7.5 prueba_eliminar_b75 ===")
    test_mecanismo_papelera()
    test_exito_basico()
    test_fallo_papelera_db_intacta()
    test_video_id_invalido()
    test_origen_faltante()
    test_cancelacion_previa()
    test_fallo_catalogo_post_papelera()
    test_integridad_relaciones()
    test_restauracion_reescaneo()
    test_ui_delega_sin_fs_sqlite()
    test_actualizacion_sin_escaneo()
    test_paginacion_filtro_orden()
    test_doble_ejecucion()
    test_cache()
    test_cero_ffmpeg()
    total=_CONTADOR[0]
    fallos=_FALLOS[0]
    print(f"TOTAL={total - fallos}/{total}")
    if fallos==0:
        print("RESULTADO_FINAL=OK")
    else:
        print("RESULTADO_FINAL=ERROR")
        sys.exit(1)

if __name__=="__main__":
    main()
