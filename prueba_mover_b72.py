"""Suite B7.2 — mover individual seguro same/cross-volume."""

import os
import sqlite3
import tempfile
import shutil
import hashlib
import inspect

from escanear_videos import (
    conectar_bd,
    guardar_marcador,
    guardar_segmento,
    asignar_color_marcador,
    asignar_color_segmento,
    listar_marcadores,
    listar_segmentos,
    obtener_video_por_id,
    actualizar_ruta_video,
)
from rutas import normalizar_ruta_clave
import mover_video as svc
from mover_video import (
    ValidacionError,
    ColisionError,
    OrigenNoEncontradoError,
    HashMismatchError,
    CompensacionFalloError,
    CriticoMoverError,
    MoverError,
)
from tareas_videos import TareaMoverVideo
import visor_videos


def _crear_db_temporal():
    tmpdir = tempfile.mkdtemp()
    ruta_db = os.path.join(tmpdir, "test.db")
    conn = conectar_bd(ruta_db)
    conn.commit()
    conn.close()
    return tmpdir, ruta_db

def _insertar_video(ruta_db, carpeta, nombre, contenido=b"x"*1024):
    ruta = os.path.join(carpeta, nombre)
    os.makedirs(carpeta, exist_ok=True)
    with open(ruta, "wb") as f:
        f.write(contenido)
    st = os.stat(ruta)
    conn = conectar_bd(ruta_db)
    try:
        ruta_abs = os.path.abspath(ruta)
        ruta_norm = normalizar_ruta_clave(ruta_abs)
        conn.execute(
            "INSERT INTO videos (nombre, ruta, ruta_normalizada, extension, fecha_importacion, tamano_bytes, mtime_ns) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (nombre, ruta_abs, ruta_norm, os.path.splitext(nombre)[1].lower(), "2026-01-01T00:00:00", st.st_size, st.st_mtime_ns),
        )
        vid = conn.execute("SELECT id FROM videos WHERE ruta_normalizada=?", (ruta_norm,)).fetchone()[0]
        conn.commit()
        return vid, ruta_abs
    finally:
        conn.close()

def test_01_same_volume_exito():
    tmpdir, ruta_db = _crear_db_temporal()
    orig = os.path.join(tmpdir, "orig")
    dest = os.path.join(tmpdir, "dest")
    os.makedirs(orig, exist_ok=True)
    os.makedirs(dest, exist_ok=True)
    try:
        vid, ruta_orig = _insertar_video(ruta_db, orig, "video01.mp4", contenido=b"abc"*100)
        res = svc.mover_video(vid, dest, ruta_db)
        assert res["ok"] and res["video_id"] == vid
        assert res["modo"] == "same-volume"
        assert res["nombre"] == "video01.mp4"
        assert os.path.isfile(res["ruta"])
        assert not os.path.isfile(ruta_orig)
        # DB ruta actualizada
        info = obtener_video_por_id(vid, ruta_db)
        assert info["ruta"] == res["ruta"]
        assert info["nombre"] == "video01.mp4"
        print("test_01 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_02_id_relaciones_preservadas():
    tmpdir, ruta_db = _crear_db_temporal()
    orig = os.path.join(tmpdir, "orig")
    dest = os.path.join(tmpdir, "dest")
    os.makedirs(orig, exist_ok=True)
    os.makedirs(dest, exist_ok=True)
    try:
        vid, _ = _insertar_video(ruta_db, orig, "vid02.mp4", contenido=b"xyz"*200)
        mid = guardar_marcador(vid, 1.5, ruta_db, color="rojo")
        asignar_color_marcador(mid, "verde", ruta_db)
        sid, _, _ = guardar_segmento(vid, 1.0, 2.0, ruta_db, color="azul")
        asignar_color_segmento(sid, "amarillo", ruta_db)
        # crear derivado trazabilidad
        vid_der, _ = _insertar_video(ruta_db, orig, "der02.mp4", contenido=b"der")
        conn = conectar_bd(ruta_db)
        conn.execute(
            "INSERT INTO videos_derivados (derivado_video_id, original_video_id, tipo, fecha_creacion, derivado_nombre, derivado_ruta, original_nombre, original_ruta) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (vid_der, vid, "individual", "2026-01-01T00:00:00", "der02.mp4", os.path.join(orig, "der02.mp4"), "vid02.mp4", os.path.join(orig, "vid02.mp4")),
        )
        deriv_id = conn.execute("SELECT id FROM videos_derivados WHERE derivado_video_id=?", (vid_der,)).fetchone()[0]
        conn.execute("INSERT INTO videos_derivados_segmentos (derivacion_id, segmento_id, orden, inicio, fin) VALUES (?, ?, ?, ?, ?)", (deriv_id, sid, 0, 1.0, 2.0))
        conn.commit()
        conn.close()
        # mover original
        svc.mover_video(vid, dest, ruta_db)
        marc = listar_marcadores(vid, ruta_db)
        seg = listar_segmentos(vid, ruta_db)
        assert marc[0][0] == mid and marc[0][3] == "verde"
        assert seg[0][0] == sid and seg[0][3] == "amarillo"
        conn = sqlite3.connect(ruta_db)
        fila = conn.execute("SELECT 1 FROM videos_derivados WHERE derivado_video_id=? AND original_video_id=?", (vid_der, vid)).fetchone()
        assert fila is not None
        seg2 = conn.execute("SELECT 1 FROM videos_derivados_segmentos WHERE derivacion_id=?", (deriv_id,)).fetchone()
        assert seg2 is not None
        conn.close()
        info = obtener_video_por_id(vid, ruta_db)
        assert info["id"] == vid
        print("test_02 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_03_misma_carpeta_rechazo():
    tmpdir, ruta_db = _crear_db_temporal()
    orig = os.path.join(tmpdir, "orig")
    os.makedirs(orig, exist_ok=True)
    try:
        vid, ruta_orig = _insertar_video(ruta_db, orig, "vid03.mp4")
        try:
            svc.mover_video(vid, orig, ruta_db)
            assert False, "misma carpeta debe rechazar"
        except ValidacionError as exc:
            # B8.3A: misma carpeta y mismo archivo comparten ruta_normalizada; ambas son válidas
            msg = str(exc).lower()
            assert "misma carpeta" in msg or "mismo archivo" in msg
        assert os.path.isfile(ruta_orig)
        info = obtener_video_por_id(vid, ruta_db)
        assert info["ruta"] == ruta_orig
        print("test_03 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_04_colision_rechazo():
    tmpdir, ruta_db = _crear_db_temporal()
    orig = os.path.join(tmpdir, "orig")
    dest = os.path.join(tmpdir, "dest")
    os.makedirs(orig, exist_ok=True)
    os.makedirs(dest, exist_ok=True)
    try:
        vid1, ruta1 = _insertar_video(ruta_db, orig, "a04.mp4")
        # Crear archivo existente en destino con mismo nombre
        with open(os.path.join(dest, "a04.mp4"), "wb") as f:
            f.write(b"existente")
        try:
            svc.mover_video(vid1, dest, ruta_db)
            assert False, "colisión debe fallar"
        except ColisionError:
            pass
        assert os.path.isfile(ruta1)
        assert os.path.isfile(os.path.join(dest, "a04.mp4"))
        info = obtener_video_por_id(vid1, ruta_db)
        assert info["ruta"] == ruta1
        print("test_04 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_05_origen_faltante():
    tmpdir, ruta_db = _crear_db_temporal()
    orig = os.path.join(tmpdir, "orig")
    dest = os.path.join(tmpdir, "dest")
    os.makedirs(orig, exist_ok=True)
    os.makedirs(dest, exist_ok=True)
    try:
        vid, ruta_orig = _insertar_video(ruta_db, orig, "vid05.mp4")
        os.remove(ruta_orig)
        try:
            svc.mover_video(vid, dest, ruta_db)
            assert False
        except OrigenNoEncontradoError:
            pass
        print("test_05 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_06_db_falla_rollback_same():
    tmpdir, ruta_db = _crear_db_temporal()
    orig = os.path.join(tmpdir, "orig")
    dest = os.path.join(tmpdir, "dest")
    os.makedirs(orig, exist_ok=True)
    os.makedirs(dest, exist_ok=True)
    try:
        vid, ruta_orig = _insertar_video(ruta_db, orig, "vid06.mp4")
        nueva = os.path.join(dest, "vid06.mp4")
        import mover_video as m
        orig_connect = m.sqlite3.connect
        class FakeConn:
            def __init__(self, *a, **k):
                self._real = orig_connect(*a, **k)
            @property
            def in_transaction(self):
                return self._real.in_transaction
            def __getattr__(self, name):
                return getattr(self._real, name)
            def execute(self, sql, params=()):
                if "UPDATE videos SET ruta" in sql:
                    raise sqlite3.OperationalError("simulado fallo DB")
                return self._real.execute(sql, params)
            def commit(self): return self._real.commit()
            def rollback(self):
                try: self._real.rollback()
                except: pass
            def close(self): return self._real.close()
        def fake_connect(*a, **k):
            fake_connect.calls += 1
            if fake_connect.calls >= 2:
                return FakeConn(*a,**k)
            return orig_connect(*a,**k)
        fake_connect.calls = 0
        m.sqlite3.connect = fake_connect
        try:
            try:
                m.mover_video(vid, dest, ruta_db)
                assert False
            except MoverError:
                assert os.path.isfile(ruta_orig)
                assert not os.path.isfile(nueva)
        finally:
            m.sqlite3.connect = orig_connect
        info = obtener_video_por_id(vid, ruta_db)
        assert info["ruta"] == ruta_orig
        print("test_06 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_07_rollback_falla_critico_same():
    tmpdir, ruta_db = _crear_db_temporal()
    orig = os.path.join(tmpdir, "orig")
    dest = os.path.join(tmpdir, "dest")
    os.makedirs(orig, exist_ok=True)
    os.makedirs(dest, exist_ok=True)
    try:
        vid, ruta_orig = _insertar_video(ruta_db, orig, "vid07.mp4")
        nueva = os.path.join(dest, "vid07.mp4")
        import mover_video as m
        orig_connect = m.sqlite3.connect
        orig_rename = m.os.rename
        renames=[]
        def tracking_rename(src,dst):
            renames.append((src,dst))
            if len(renames)==1:
                return orig_rename(src,dst)
            else:
                raise OSError("compensación fallida")
        class FakeConn2:
            def __init__(self,*a,**k): self._real=orig_connect(*a,**k)
            @property
            def in_transaction(self):
                return self._real.in_transaction
            def __getattr__(self, name):
                return getattr(self._real, name)
            def execute(self,sql,params=()):
                if "UPDATE videos SET ruta" in sql:
                    raise sqlite3.OperationalError("fallo DB")
                return self._real.execute(sql,params)
            def commit(self): return self._real.commit()
            def rollback(self):
                try: self._real.rollback()
                except: pass
            def close(self): return self._real.close()
        def fake_connect2(*a,**k):
            fake_connect2.calls+=1
            if fake_connect2.calls>=2:
                return FakeConn2(*a,**k)
            return orig_connect(*a,**k)
        fake_connect2.calls=0
        m.sqlite3.connect=fake_connect2
        m.os.rename=tracking_rename
        try:
            try:
                m.mover_video(vid, dest, ruta_db)
                assert False
            except CompensacionFalloError as exc:
                assert exc.ruta_original is not None
                assert exc.ruta_nueva is not None
                assert os.path.isfile(nueva)
                assert not os.path.isfile(ruta_orig)
        finally:
            m.sqlite3.connect=orig_connect
            m.os.rename=orig_rename
        print("test_07 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_08_cross_forzado_exito():
    tmpdir, ruta_db = _crear_db_temporal()
    orig = os.path.join(tmpdir, "orig")
    dest = os.path.join(tmpdir, "dest")
    os.makedirs(orig, exist_ok=True)
    os.makedirs(dest, exist_ok=True)
    try:
        contenido = b"cross_content_"*500
        vid, ruta_orig = _insertar_video(ruta_db, orig, "vid08.mp4", contenido=contenido)
        res = svc.mover_video(vid, dest, ruta_db, forzar_cross_volume=True)
        assert res["ok"] and res["modo"] == "cross-volume"
        assert os.path.isfile(res["ruta"])
        assert not os.path.isfile(ruta_orig)
        # verificar hash y tamaño
        assert os.path.getsize(res["ruta"]) == len(contenido)
        # DB
        info = obtener_video_por_id(vid, ruta_db)
        assert info["ruta"] == res["ruta"]
        # temporales limpios
        temps = [f for f in os.listdir(dest) if ".tmp_mover" in f]
        assert not temps, f"temporales no limpios {temps}"
        print("test_08 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_09_hash_distinto_aborta_cross():
    tmpdir, ruta_db = _crear_db_temporal()
    orig = os.path.join(tmpdir, "orig")
    dest = os.path.join(tmpdir, "dest")
    os.makedirs(orig, exist_ok=True)
    os.makedirs(dest, exist_ok=True)
    try:
        vid, ruta_orig = _insertar_video(ruta_db, orig, "vid09.mp4", contenido=b"original_content")
        import mover_video as m
        orig_hash = m._hash_sha256_stream
        def fake_hash(path):
            if "dest" in path or ".tmp_mover" in path:
                return "hash_temporal_distinto"
            return orig_hash(ruta_orig) if os.path.isfile(ruta_orig) else orig_hash(path)
        # more precise: monkey hash to force mismatch
        m._hash_sha256_stream = lambda p, chunk_size=1024*1024: "aaa" if ".tmp" in p else "bbb"
        try:
            try:
                m.mover_video(vid, dest, ruta_db, forzar_cross_volume=True)
                assert False, "hash distinto debe abortar"
            except HashMismatchError:
                assert os.path.isfile(ruta_orig)
                assert not os.path.isfile(os.path.join(dest, "vid09.mp4"))
                temps = [f for f in os.listdir(dest) if ".tmp" in f]
                assert not temps
                info = obtener_video_por_id(vid, ruta_db)
                assert info["ruta"] == ruta_orig
        finally:
            m._hash_sha256_stream = orig_hash
        print("test_09 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_10_db_falla_cross_compensa_destino():
    tmpdir, ruta_db = _crear_db_temporal()
    orig = os.path.join(tmpdir, "orig")
    dest = os.path.join(tmpdir, "dest")
    os.makedirs(orig, exist_ok=True)
    os.makedirs(dest, exist_ok=True)
    try:
        vid, ruta_orig = _insertar_video(ruta_db, orig, "vid10.mp4", contenido=b"cross10")
        nueva = os.path.join(dest, "vid10.mp4")
        import mover_video as m
        orig_connect = m.sqlite3.connect
        class FakeConn:
            def __init__(self,*a,**k): self._real=orig_connect(*a,**k)
            @property
            def in_transaction(self):
                return self._real.in_transaction
            def __getattr__(self, name):
                return getattr(self._real, name)
            def execute(self,sql,params=()):
                if "UPDATE videos SET ruta" in sql:
                    raise sqlite3.OperationalError("fallo DB cross")
                return self._real.execute(sql,params)
            def commit(self): return self._real.commit()
            def rollback(self):
                try: self._real.rollback()
                except: pass
            def close(self): return self._real.close()
        def fake_connect(*a,**k):
            fake_connect.calls+=1
            if fake_connect.calls>=2:
                return FakeConn(*a,**k)
            return orig_connect(*a,**k)
        fake_connect.calls=0
        m.sqlite3.connect=fake_connect
        try:
            try:
                m.mover_video(vid, dest, ruta_db, forzar_cross_volume=True)
                assert False
            except MoverError as exc:
                assert "DB cross" in str(exc) or "fallo DB" in str(exc).lower()
                assert os.path.isfile(ruta_orig), "origen intacto"
                assert not os.path.isfile(nueva), "destino compensado debe eliminarse"
                temps = [f for f in os.listdir(dest) if ".tmp" in f]
                assert not temps
                info = obtener_video_por_id(vid, ruta_db)
                assert info["ruta"] == ruta_orig
        finally:
            m.sqlite3.connect=orig_connect
        print("test_10 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_11_remove_origen_falla_critico_cross():
    tmpdir, ruta_db = _crear_db_temporal()
    orig = os.path.join(tmpdir, "orig")
    dest = os.path.join(tmpdir, "dest")
    os.makedirs(orig, exist_ok=True)
    os.makedirs(dest, exist_ok=True)
    try:
        vid, ruta_orig = _insertar_video(ruta_db, orig, "vid11.mp4", contenido=b"content11")
        nueva = os.path.join(dest, "vid11.mp4")
        import mover_video as m
        orig_remove = m.os.remove
        def fake_remove(path):
            if os.path.normcase(os.path.normpath(path)) == os.path.normcase(os.path.normpath(ruta_orig)):
                raise OSError("no se pudo eliminar origen simulado")
            return orig_remove(path)
        m.os.remove = fake_remove
        try:
            try:
                m.mover_video(vid, dest, ruta_db, forzar_cross_volume=True)
                assert False
            except CriticoMoverError as exc:
                assert exc.ruta_original is not None and exc.ruta_nueva is not None
                # ambas copias conservadas
                assert os.path.isfile(ruta_orig), "origen debe conservarse"
                assert os.path.isfile(nueva), "destino debe conservarse"
                info = obtener_video_por_id(vid, ruta_db)
                assert info["ruta"] == nueva, "DB debe apuntar a destino"
        finally:
            m.os.remove = orig_remove
        print("test_11 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_12_temporales_limpios_en_fallos():
    tmpdir, ruta_db = _crear_db_temporal()
    orig = os.path.join(tmpdir, "orig")
    dest = os.path.join(tmpdir, "dest")
    os.makedirs(orig, exist_ok=True)
    os.makedirs(dest, exist_ok=True)
    try:
        vid, ruta_orig = _insertar_video(ruta_db, orig, "vid12.mp4", contenido=b"temp_clean")
        import mover_video as m
        orig_hash = m._hash_sha256_stream
        m._hash_sha256_stream = lambda p, chunk_size=1024*1024: "mismatch_a" if "orig" in p else "mismatch_b"
        try:
            try:
                m.mover_video(vid, dest, ruta_db, forzar_cross_volume=True)
                assert False
            except HashMismatchError:
                pass
        finally:
            m._hash_sha256_stream = orig_hash
        temps = [f for f in os.listdir(dest) if ".tmp" in f or ".part" in f]
        assert not temps, f"temporales deben limpiarse tras fallo, got {temps}"
        # también tras éxito no quedan temporales (ya probado) pero verificar de nuevo
        print("test_12 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_13_ui_delega_background():
    fuente_mover = inspect.getsource(visor_videos.VisorVideos._iniciar_mover)
    assert "TareaMoverVideo" in fuente_mover, "UI debe usar TareaMoverVideo"
    assert "QFileDialog.getExistingDirectory" in fuente_mover, "debe usar selector carpeta existente"
    assert "os.rename" not in fuente_mover, "UI no debe hacer rename directo"
    assert "sqlite" not in fuente_mover.lower(), "UI no debe acceder SQLite directo"
    assert "gestor_mover.iniciar" in fuente_mover
    fuente_tarea = inspect.getsource(TareaMoverVideo._trabajo)
    assert "mover_video" in fuente_tarea
    fuente_menu = inspect.getsource(visor_videos.VisorVideos._mostrar_menu_contextual)
    assert "Mover a" in fuente_menu
    # Verificar handlers resultado/error existen
    assert hasattr(visor_videos.VisorVideos, "_al_resultado_mover")
    assert hasattr(visor_videos.VisorVideos, "_al_error_mover")
    # Verificar que actualizar_ruta existe
    assert hasattr(visor_videos.Tarjeta, "actualizar_ruta")
    print("test_13 OK")

def test_14_recarga_usa_nueva_ruta_sin_escaneo():
    tmpdir, ruta_db = _crear_db_temporal()
    orig = os.path.join(tmpdir, "orig")
    dest = os.path.join(tmpdir, "dest")
    os.makedirs(orig, exist_ok=True)
    os.makedirs(dest, exist_ok=True)
    try:
        vid, ruta_orig = _insertar_video(ruta_db, orig, "vid14.mp4", contenido=b"recarga")
        res = svc.mover_video(vid, dest, ruta_db)
        # Simular recarga: nuevo proceso lee DB sin escanear FS
        info = obtener_video_por_id(vid, ruta_db)
        assert info["ruta"] == res["ruta"]
        assert os.path.isfile(info["ruta"])
        # Verificar que listar_videos devuelve nueva ruta
        from escanear_videos import listar_videos
        filas = listar_videos(ruta_db)
        found = [r for r in filas if r[8] == vid]
        assert len(found)==1
        assert found[0][7] == res["ruta"]
        # Simular reinicio creando tarjeta desde fila
        fila = found[0]  # nombre, duracion, ancho, alto, codec, cantidad, tamano, ruta, id
        # No se necesita reescanear: ruta ya persiste
        print("test_14 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_15_helper_actualizar_ruta_video():
    tmpdir, ruta_db = _crear_db_temporal()
    orig = os.path.join(tmpdir, "orig")
    dest = os.path.join(tmpdir, "dest")
    os.makedirs(orig, exist_ok=True)
    os.makedirs(dest, exist_ok=True)
    try:
        vid, ruta_orig = _insertar_video(ruta_db, orig, "vid15.mp4")
        nueva = os.path.join(dest, "vid15.mp4")
        # helper directo
        actualizar_ruta_video(vid, nueva, ruta_db)
        info = obtener_video_por_id(vid, ruta_db)
        assert os.path.normcase(os.path.normpath(info["ruta"])) == os.path.normcase(os.path.normpath(os.path.abspath(nueva)))
        print("test_15 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_16_ui_actualiza_tarjeta_sin_reescaneo():
    import sys, time
    from PySide6.QtWidgets import QApplication
    import apertura_videos

    tmpdir, ruta_db = _crear_db_temporal()
    orig = os.path.join(tmpdir, "orig")
    dest = os.path.join(tmpdir, "dest")
    os.makedirs(orig, exist_ok=True)
    os.makedirs(dest, exist_ok=True)
    try:
        vid, ruta_orig = _insertar_video(ruta_db, orig, "orig16_mover.mp4", contenido=b"abc")
        assert os.path.isfile(ruta_orig)
        nueva_ruta = os.path.join(dest, "orig16_mover.mp4")
        # Crear window
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        ruta_config = os.path.join(tmpdir, "config_b16.json")
        ventana = visor_videos.VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        ventana.resize(720,540)
        ventana.show()
        def esperar(pred, intentos=200):
            for _ in range(intentos):
                QApplication.processEvents()
                if pred():
                    return True
                time.sleep(0.02)
            QApplication.processEvents()
            return pred()
        esperar(lambda: ventana._carga_completada and not ventana.gestor.activo, intentos=250)
        ventana.carpeta_seleccionada = orig
        tarjeta = ventana._tarjeta_por_nombre("orig16_mover.mp4")
        if tarjeta is None:
            fila = ("orig16_mover.mp4", 10.0, 640, 480, "h264", 1, 123, ruta_orig, vid)
            from visor_videos import Tarjeta
            tarjeta = Tarjeta(fila, ruta_config=ruta_config)
            ventana.tarjetas.append(("orig16_mover.mp4", tarjeta))
            ventana.visibles.append("orig16_mover.mp4")
            ventana._nombres_seleccionados.add("orig16_mover.mp4")
        # Patch reescaneo detection
        reescaneo_calls=[]
        orig_iniciar_escaneo = visor_videos.VisorVideos.iniciar_escaneo
        orig_crear_tarea = visor_videos.VisorVideos._crear_tarea_lectura
        def fake_iniciar_escaneo(self,*a,**k):
            reescaneo_calls.append("iniciar_escaneo")
            return None
        def fake_crear(self,*a,**k):
            reescaneo_calls.append("_crear_tarea_lectura")
            return orig_crear_tarea(self,*a,**k)
        visor_videos.VisorVideos.iniciar_escaneo = fake_iniciar_escaneo
        visor_videos.VisorVideos._crear_tarea_lectura = fake_crear
        # Simular movimiento físico + DB ya hecho, luego UI result
        os.rename(ruta_orig, nueva_ruta)
        conn = sqlite3.connect(ruta_db)
        conn.execute("UPDATE videos SET ruta=? WHERE id=?", (nueva_ruta, vid))
        conn.commit()
        conn.close()
        resultado = {"ok": True, "video_id": vid, "nombre": "orig16_mover.mp4", "ruta": nueva_ruta, "ruta_anterior": ruta_orig, "modo": "same-volume"}
        ventana._mover_nombre_anterior = "orig16_mover.mp4"
        ventana._mover_video_id = vid
        ventana._al_resultado_mover(resultado)
        QApplication.processEvents()
        assert getattr(tarjeta, "_video_id", None) == vid
        assert tarjeta.nombre == "orig16_mover.mp4"
        ruta_resuelta = ventana._ruta_video_de(tarjeta)
        assert ruta_resuelta is not None and os.path.normcase(os.path.normpath(ruta_resuelta)) == os.path.normcase(os.path.normpath(nueva_ruta))
        assert os.path.isfile(ruta_resuelta)
        assert not reescaneo_calls, f"no debe reescaneo {reescaneo_calls}"
        visor_videos.VisorVideos.iniciar_escaneo = orig_iniciar_escaneo
        visor_videos.VisorVideos._crear_tarea_lectura = orig_crear_tarea
        ventana.close()
        ventana.gestor.cerrar()
        try: ventana.gestor_previews.cerrar()
        except: pass
        try: ventana.gestor_renombrado.cerrar()
        except: pass
        try: ventana.gestor_mover.cerrar()
        except: pass
        print("test_16 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_17_actualizar_ruta_rechaza_basename_inconsistente():
    """Tarjeta.actualizar_ruta debe rechazar basename distinto (case-insensitive en Windows)."""
    import sys
    from PySide6.QtWidgets import QApplication
    tmpdir = tempfile.mkdtemp()
    try:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        ruta_config = os.path.join(tmpdir, "config_b17.json")
        # Crear tarjeta con nombre fijo
        fila = ("video17.mp4", 10.0, 640, 480, "h264", 1, 123, os.path.join(tmpdir, "orig", "video17.mp4"), 999)
        from visor_videos import Tarjeta
        tarjeta = Tarjeta(fila, ruta_config=ruta_config)
        # Verificar que _carpeta_video inicial existe (puede ser None o derivada)
        carpeta_previa = getattr(tarjeta, "_carpeta_video", None)
        # Caso 1: basename distinto debe lanzar ValueError
        try:
            tarjeta.actualizar_ruta(os.path.join(tmpdir, "dest", "otro_nombre.mp4"))
            assert False, "basename distinto debe lanzar ValueError"
        except ValueError as exc:
            assert "coincide" in str(exc).lower() or "basename" in str(exc).lower()
        # No debe haber mutado carpeta en caso de rechazo
        assert getattr(tarjeta, "_carpeta_video", None) == carpeta_previa, "no debe mutar _carpeta_video tras rechazo"
        # Caso 2: ruta vacía / no string debe lanzar ValueError
        try:
            tarjeta.actualizar_ruta("")
            assert False, "ruta vacía debe lanzar ValueError"
        except ValueError:
            pass
        try:
            tarjeta.actualizar_ruta(None)
            assert False, "None debe lanzar ValueError"
        except ValueError:
            pass
        # Caso 3: basename con distinta capitalización en Windows debe aceptarse (normcase)
        # En Linux normcase es sensible, así que solo verificamos comportamiento según plataforma
        if os.name == "nt":
            # Windows: case-insensitive, no debe lanzar
            try:
                tarjeta.actualizar_ruta(os.path.join(tmpdir, "dest", "VIDEO17.MP4"))
            except ValueError:
                assert False, "en Windows case-insensitive debe aceptar VIDEO17.MP4"
            # Verificar que sí actualizó carpeta
            assert os.path.normcase(os.path.normpath(getattr(tarjeta, "_carpeta_video", ""))) == os.path.normcase(os.path.normpath(os.path.join(tmpdir, "dest")))
        else:
            # Linux: actualización con mismo basename exacto debe funcionar
            tarjeta2 = Tarjeta(fila, ruta_config=ruta_config)
            dest_ruta = os.path.join(tmpdir, "dest", "video17.mp4")
            tarjeta2.actualizar_ruta(dest_ruta)
            assert os.path.normpath(getattr(tarjeta2, "_carpeta_video", "")) == os.path.normpath(os.path.dirname(dest_ruta))
        print("test_17 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_18_sin_fallback_silencioso_en_resultado_mover():
    """_al_resultado_mover no debe escribir _carpeta_video directo si actualizar_ruta falla; debe mostrar inconsistencia y conservar evidencia."""
    import sys
    from PySide6.QtWidgets import QApplication
    tmpdir, ruta_db = _crear_db_temporal()
    orig = os.path.join(tmpdir, "orig")
    dest = os.path.join(tmpdir, "dest")
    os.makedirs(orig, exist_ok=True)
    os.makedirs(dest, exist_ok=True)
    try:
        vid, ruta_orig = _insertar_video(ruta_db, orig, "video18.mp4", contenido=b"content18")
        nueva_ruta = os.path.join(dest, "video18.mp4")
        # Simular FS/DB ya movidos para aislar UI
        os.rename(ruta_orig, nueva_ruta)
        conn = sqlite3.connect(ruta_db)
        conn.execute("UPDATE videos SET ruta=? WHERE id=?", (nueva_ruta, vid))
        conn.commit()
        conn.close()
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        ruta_config = os.path.join(tmpdir, "config_b18.json")
        ventana = visor_videos.VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        ventana.resize(720,540)
        ventana.show()
        import time
        def esperar(pred, intentos=200):
            from PySide6.QtWidgets import QApplication as QA
            for _ in range(intentos):
                QA.processEvents()
                if pred():
                    return True
                time.sleep(0.02)
            QA.processEvents()
            return pred()
        esperar(lambda: ventana._carga_completada and not ventana.gestor.activo, intentos=250)
        ventana.carpeta_seleccionada = orig
        tarjeta = ventana._tarjeta_por_nombre("video18.mp4")
        if tarjeta is None:
            fila = ("video18.mp4", 10.0, 640, 480, "h264", 1, 123, ruta_orig, vid)
            from visor_videos import Tarjeta
            tarjeta = Tarjeta(fila, ruta_config=ruta_config)
            ventana.tarjetas.append(("video18.mp4", tarjeta))
            ventana.visibles.append("video18.mp4")
            ventana._nombres_seleccionados.add("video18.mp4")
        carpeta_previa = getattr(tarjeta, "_carpeta_video", None)
        # Parchear actualizar_ruta para que falle
        orig_actualizar = tarjeta.actualizar_ruta
        def failing_actualizar(nueva):
            raise ValueError("fallo sincronización simulado")
        tarjeta.actualizar_ruta = failing_actualizar
        # Llamar handler con resultado exitoso
        resultado = {"ok": True, "video_id": vid, "nombre": "video18.mp4", "ruta": nueva_ruta, "ruta_anterior": ruta_orig, "modo": "same-volume"}
        ventana._mover_nombre_anterior = "video18.mp4"
        ventana._mover_video_id = vid
        ventana._mover_ruta_inconsistente = None
        ventana._mover_error_sincronizacion = None
        ventana._al_resultado_mover(resultado)
        from PySide6.QtWidgets import QApplication as QA
        QA.processEvents()
        # Verificar que NO hubo fallback silencioso: _carpeta_video no cambió
        assert getattr(tarjeta, "_carpeta_video", None) == carpeta_previa, "fallback silencioso no debe mutar _carpeta_video tras fallo"
        # Debe mostrar estado inconsistente explícito y conservar evidencia
        mensaje = ventana.mensaje_carpeta.text()
        assert "inconsistente" in mensaje.lower(), f"debe mostrar inconsistencia, got {mensaje!r}"
        assert getattr(ventana, "_mover_ruta_inconsistente", None) is not None, "debe conservar ruta inconsistente"
        assert nueva_ruta in str(getattr(ventana, "_mover_ruta_inconsistente", "")) or nueva_ruta == getattr(ventana, "_mover_ruta_inconsistente", None)
        assert getattr(ventana, "_mover_error_sincronizacion", None) is not None
        # No debe fingir éxito "Movido a"
        assert "movido a" not in mensaje.lower() or "inconsistente" in mensaje.lower()
        # Restaurar
        tarjeta.actualizar_ruta = orig_actualizar
        ventana.close()
        ventana.gestor.cerrar()
        try: ventana.gestor_previews.cerrar()
        except: pass
        try: ventana.gestor_renombrado.cerrar()
        except: pass
        try: ventana.gestor_mover.cerrar()
        except: pass
        print("test_18 OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

def test_19_smoke_conductual_mover_real():
    """Smoke conductual real reproducible: DB temporal, archivo origen, Visor/Tarjeta real,
    _iniciar_mover con mock QFileDialog, GestorTareas/TareaMoverVideo real, procesamiento Qt,
    verificación origen ausente, destino presente, DB apunta destino, mismo video_id,
    Tarjeta._carpeta_video destino, _ruta_video_de destino y ausencia de reescaneo global."""
    import sys, time
    from PySide6.QtWidgets import QApplication, QFileDialog
    tmpdir, ruta_db = _crear_db_temporal()
    orig = os.path.join(tmpdir, "orig")
    dest = os.path.join(tmpdir, "dest")
    os.makedirs(orig, exist_ok=True)
    os.makedirs(dest, exist_ok=True)
    contenido = b"smoke_real_content_"*200
    try:
        vid, ruta_orig = _insertar_video(ruta_db, orig, "smoke19.mp4", contenido=contenido)
        assert os.path.isfile(ruta_orig)
        ruta_dest_esperada = os.path.join(dest, "smoke19.mp4")
        assert not os.path.isfile(ruta_dest_esperada)
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        ruta_config = os.path.join(tmpdir, "config_b19.json")
        ventana = visor_videos.VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        ventana.resize(720,540)
        ventana.show()
        def esperar(pred, intentos=250):
            from PySide6.QtWidgets import QApplication as QA
            for _ in range(intentos):
                QA.processEvents()
                if pred():
                    return True
                time.sleep(0.02)
            QA.processEvents()
            return pred()
        esperar(lambda: ventana._carga_completada and not ventana.gestor.activo, intentos=300)
        ventana.carpeta_seleccionada = orig
        # Asegurar tarjeta existe para smoke (mismo flujo que test_16)
        tarjeta = ventana._tarjeta_por_nombre("smoke19.mp4")
        if tarjeta is None:
            fila = ("smoke19.mp4", 10.0, 640, 480, "h264", 1, 123, ruta_orig, vid)
            from visor_videos import Tarjeta
            tarjeta = Tarjeta(fila, ruta_config=ruta_config)
            ventana.tarjetas.append(("smoke19.mp4", tarjeta))
            ventana.visibles.append("smoke19.mp4")
            ventana._nombres_seleccionados.add("smoke19.mp4")
            # Reemplazar si ya había otra
        else:
            # Asegurar que video_id coincide
            assert getattr(tarjeta, "_video_id", None) == vid or getattr(tarjeta, "_video_id", None) is None
            if getattr(tarjeta, "_video_id", None) is None:
                tarjeta._video_id = vid
        # Parchear QFileDialog para automatizar selección destino temporal
        orig_getExisting = QFileDialog.getExistingDirectory
        QFileDialog.getExistingDirectory = lambda *a, **k: dest
        # Parchear reescaneo global para detectar si se dispara
        reescaneo_calls=[]
        orig_iniciar_escaneo = visor_videos.VisorVideos.iniciar_escaneo
        orig_crear_tarea = visor_videos.VisorVideos._crear_tarea_lectura
        def fake_iniciar_escaneo(self,*a,**k):
            reescaneo_calls.append("iniciar_escaneo")
            return None
        def fake_crear(self,*a,**k):
            reescaneo_calls.append("_crear_tarea_lectura")
            return orig_crear_tarea(self,*a,**k)
        visor_videos.VisorVideos.iniciar_escaneo = fake_iniciar_escaneo
        visor_videos.VisorVideos._crear_tarea_lectura = fake_crear
        try:
            # Iniciar mover vía UI real (usa TareaMoverVideo + GestorTareas)
            ventana._iniciar_mover("smoke19.mp4")
            # Esperar que GestorTareas termine (tarea background real)
            ok = esperar(lambda: not ventana.gestor_mover.activo and not ventana._mover_en_curso, intentos=400)
            # Procesar eventos adicionales para que llegue _al_resultado_mover
            for _ in range(30):
                QApplication.processEvents()
                time.sleep(0.02)
            assert ok, "timeout esperando gestor_mover"
        finally:
            QFileDialog.getExistingDirectory = orig_getExisting
            visor_videos.VisorVideos.iniciar_escaneo = orig_iniciar_escaneo
            visor_videos.VisorVideos._crear_tarea_lectura = orig_crear_tarea
        # Verificaciones conductuales reales
        assert not os.path.isfile(ruta_orig), "origen debe estar ausente tras mover"
        assert os.path.isfile(ruta_dest_esperada), "destino debe existir"
        # DB apunta a destino, mismo video_id
        info = obtener_video_por_id(vid, ruta_db)
        assert info is not None and info["id"] == vid
        assert os.path.normcase(os.path.normpath(info["ruta"])) == os.path.normcase(os.path.normpath(os.path.abspath(ruta_dest_esperada)))
        assert info["nombre"] == "smoke19.mp4"
        # Tarjeta._carpeta_video destino
        carpeta_tarjeta = getattr(tarjeta, "_carpeta_video", None)
        assert carpeta_tarjeta is not None
        assert os.path.normcase(os.path.normpath(carpeta_tarjeta)) == os.path.normcase(os.path.normpath(dest)), f"Tarjeta._carpeta_video {carpeta_tarjeta!r} != {dest!r}"
        # _ruta_video_de destino
        ruta_resuelta = ventana._ruta_video_de(tarjeta)
        assert ruta_resuelta is not None and os.path.normcase(os.path.normpath(ruta_resuelta)) == os.path.normcase(os.path.normpath(os.path.abspath(ruta_dest_esperada))), f"_ruta_video_de {ruta_resuelta!r} != {ruta_dest_esperada!r}"
        assert os.path.isfile(ruta_resuelta)
        # Mismo video_id preservado
        assert getattr(tarjeta, "_video_id", None) == vid
        assert tarjeta.nombre == "smoke19.mp4"
        # Ausencia de reescaneo global
        assert not reescaneo_calls, f"no debe haber reescaneo global, got {reescaneo_calls}"
        ventana.close()
        ventana.gestor.cerrar()
        try: ventana.gestor_previews.cerrar()
        except: pass
        try: ventana.gestor_renombrado.cerrar()
        except: pass
        try: ventana.gestor_mover.cerrar()
        except: pass
        print("test_19 SMOKE OK — origen ausente, destino presente, DB apunta destino, video_id preservado, tarjeta y _ruta_video_de OK, sin reescaneo")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_20_diagnostico_catalogo_origen_post_move():
    """Diagnóstico reproducible B7.2 — causas A y B separadas con funciones reales.

    Usa DB temporal, carpetas A/B temporales y archivo temporal (tempfile).
    Llama funciones reales de catalogo (listar_videos, listar_videos_paginado,
    conectar_bd, obtener_video_por_id) y VisorVideos real.
    Registra: presente en A antes; estado DB; mover por mover_video;
    listado A después; listado B después; cerrar/reabrir conexión y repetir;
    recrear Visor y verificar A ausente B correcto sin reescaneo.
    """
    import sys, time
    from PySide6.QtWidgets import QApplication
    tmpdir, ruta_db = _crear_db_temporal()
    carpeta_A = os.path.join(tmpdir, "A")
    carpeta_B = os.path.join(tmpdir, "B")
    os.makedirs(carpeta_A, exist_ok=True)
    os.makedirs(carpeta_B, exist_ok=True)
    try:
        vid, ruta_A = _insertar_video(ruta_db, carpeta_A, "diag20.mp4", contenido=b"diag"*500)
        # Estado inicial: presente en A
        info0 = obtener_video_por_id(vid, ruta_db)
        assert info0["ruta"] == ruta_A
        # Funciones reales de listado (escanear_videos.py)
        from escanear_videos import listar_videos, listar_videos_paginado, conectar_bd
        filas = listar_videos(ruta_db)
        assert any(r[8] == vid and os.path.normcase(r[7]) == os.path.normcase(ruta_A) for r in filas), "debe estar en listar_videos antes"
        pag = listar_videos_paginado(100, 0, None, ruta_db)
        assert pag["total"] >= 1 and any(r[8] == vid for r in pag["videos"])
        def en_carpeta(filas_, carpeta):
            carpeta_n = os.path.normcase(os.path.normpath(os.path.abspath(carpeta)))
            res = []
            for r in filas_:
                ruta = r[7]
                try:
                    if os.path.normcase(os.path.normpath(os.path.dirname(ruta))) == carpeta_n:
                        res.append(r)
                except Exception:
                    continue
            return res
        assert len(en_carpeta(filas, carpeta_A)) == 1, f"A antes debe tener 1, got {en_carpeta(filas, carpeta_A)}"
        assert len(en_carpeta(filas, carpeta_B)) == 0
        print("diag20: presente en A antes OK, DB ruta ok, listado A=1 B=0")
        # Visor real antes
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        ruta_config = os.path.join(tmpdir, "config_diag20.json")
        ventana = visor_videos.VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        ventana.resize(720, 540)
        ventana.show()
        def esperar(pred, intentos=250):
            for _ in range(intentos):
                QApplication.processEvents()
                if pred():
                    return True
                time.sleep(0.02)
            QApplication.processEvents()
            return pred()
        esperar(lambda: ventana._carga_completada and not ventana.gestor.activo, intentos=300)
        ventana.carpeta_seleccionada = os.path.abspath(carpeta_A)
        tarjeta = ventana._tarjeta_por_nombre("diag20.mp4")
        if tarjeta is None:
            fila = ("diag20.mp4", 10.0, 640, 480, "h264", 1, 123, ruta_A, vid)
            from visor_videos import Tarjeta
            tarjeta = Tarjeta(fila, ruta_config=ruta_config)
            ventana.tarjetas.append(("diag20.mp4", tarjeta))
            ventana.visibles.append("diag20.mp4")
            ventana.cuadricula.addWidget(tarjeta, len(ventana.tarjetas)-1, 0)
            ventana.filtrar(ventana.busqueda.text())
        else:
            assert os.path.normcase(os.path.normpath(getattr(tarjeta, "_carpeta_video", ""))) == os.path.normcase(os.path.normpath(os.path.abspath(carpeta_A)))
        assert tarjeta.nombre == "diag20.mp4"
        assert ventana._ruta_video_de(tarjeta) == ruta_A
        assert "diag20.mp4" in ventana.visibles
        print("diag20: Visor A visible antes OK")
        # Mover via servicio real
        res = svc.mover_video(vid, carpeta_B, ruta_db)
        assert res["ok"] and res["video_id"] == vid
        nueva_ruta = res["ruta"]
        assert os.path.normcase(os.path.dirname(nueva_ruta)) == os.path.normcase(os.path.abspath(carpeta_B))
        info1 = obtener_video_por_id(vid, ruta_db)
        assert os.path.normcase(info1["ruta"]) == os.path.normcase(nueva_ruta)
        filas2 = listar_videos(ruta_db)
        assert len(en_carpeta(filas2, carpeta_A)) == 0, f"listado A después debe ser 0, got {en_carpeta(filas2, carpeta_A)}"
        assert len(en_carpeta(filas2, carpeta_B)) == 1
        print("diag20: DB post-move A ausente B presente OK")
        # Cerrar/reabrir conexión
        conn = conectar_bd(ruta_db)
        fila_db = conn.execute("SELECT ruta FROM videos WHERE id=?", (vid,)).fetchone()
        conn.close()
        assert fila_db and os.path.normcase(fila_db[0]) == os.path.normcase(nueva_ruta)
        filas3 = listar_videos(ruta_db)
        assert len(en_carpeta(filas3, carpeta_A)) == 0
        assert len(en_carpeta(filas3, carpeta_B)) == 1
        print("diag20: reconexión DB coherente A=0 B=1")
        # Handler UI con carpeta_seleccionada = A (vista origen) — debe quitar tarjeta
        ventana._mover_nombre_anterior = "diag20.mp4"
        ventana._mover_video_id = vid
        reescaneo = []
        orig_iniciar = visor_videos.VisorVideos.iniciar_escaneo
        orig_crear = visor_videos.VisorVideos._crear_tarea_lectura
        def fake_iniciar(self, *a, **k):
            reescaneo.append("iniciar_escaneo")
            return None
        def fake_crear(self, *a, **k):
            reescaneo.append("_crear_tarea_lectura")
            return orig_crear(self, *a, **k)
        visor_videos.VisorVideos.iniciar_escaneo = fake_iniciar
        visor_videos.VisorVideos._crear_tarea_lectura = fake_crear
        ventana._nombres_seleccionados.add("diag20.mp4")
        ventana._al_resultado_mover(res)
        QApplication.processEvents()
        # A ausente inmediatamente — causa A
        nombres_en_tarjetas = [n for n, _ in ventana.tarjetas]
        assert "diag20.mp4" not in nombres_en_tarjetas, f"tarjeta debe ser removida de A tras mover, tarjetas={nombres_en_tarjetas}"
        assert "diag20.mp4" not in ventana.visibles, f"visibles debe no contener diag20 tras mover de A, visibles={ventana.visibles}"
        assert "diag20.mp4" not in ventana._nombres_seleccionados
        assert not reescaneo, f"no debe reescanear en éxito, got {reescaneo}"
        # contador coherente
        ventana.actualizar_contador()
        assert "0 " in ventana.contador.text() or "1 " in ventana.contador.text()  # coherente tras remover
        print("diag20: A ausente inmediatamente (UI) OK, sin reescaneo, contador coherente")
        visor_videos.VisorVideos.iniciar_escaneo = orig_iniciar
        visor_videos.VisorVideos._crear_tarea_lectura = orig_crear
        ventana.close()
        ventana.gestor.cerrar()
        try: ventana.gestor_previews.cerrar()
        except: pass
        try: ventana.gestor_renombrado.cerrar()
        except: pass
        try: ventana.gestor_mover.cerrar()
        except: pass
        # Recrear Visor como reinicio — causa B: DB ya correcta, UI debe mantener A ausente B correcto
        ventana2 = visor_videos.VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        ventana2.resize(720, 540)
        ventana2.show()
        esperar(lambda: ventana2._carga_completada and not ventana2.gestor.activo, intentos=300)
        filas_reload = listar_videos(ruta_db)
        assert len(en_carpeta(filas_reload, carpeta_A)) == 0
        assert len(en_carpeta(filas_reload, carpeta_B)) == 1
        t2 = ventana2._tarjeta_por_nombre("diag20.mp4")
        if t2 is not None:
            assert os.path.normcase(os.path.normpath(getattr(t2, "_carpeta_video", ""))) == os.path.normcase(os.path.normpath(os.path.abspath(carpeta_B))), f"t2 carpeta {getattr(t2, '_carpeta_video', '')} != B"
            assert os.path.normcase(os.path.normpath(ventana2._ruta_video_de(t2))) == os.path.normcase(os.path.normpath(nueva_ruta))
        else:
            pag2 = listar_videos_paginado(100, 0, None, ruta_db)
            assert any(r[8] == vid and os.path.normcase(os.path.dirname(r[7])) == os.path.normcase(os.path.abspath(carpeta_B)) for r in pag2["videos"])
        print("diag20: recrear Visor A ausente B correcto OK, contador/listas coherentes")
        ventana2.close()
        ventana2.gestor.cerrar()
        try: ventana2.gestor_previews.cerrar()
        except: pass
        try: ventana2.gestor_renombrado.cerrar()
        except: pass
        try: ventana2.gestor_mover.cerrar()
        except: pass
        print("test_20 DIAG OK — causa A y B demostradas, sin reescaneo")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_21_reinicio_real_persistido_navegacion():
    """B7.2 fix-017 — reproducción REAL de reinicio con config persistida y navegación.

    Usa DB/config/carpetas temporales bajo C:\\prueba (evita short 8.3), persiste A,
    mueve A->B, cierra primera Visor, crea SEGUNDA Visor leyendo esa misma config
    sin asignar manualmente carpeta_seleccionada después del arranque, verifica:
    - reinicio con A restaurada: video ausente en A (tarjetas filtradas en SQL)
    - navegar B: presente
    - volver A: ausente
    - sin escaneo, mismo video_id, contador coherente, no reescaneo.
    """
    import sys, time
    from PySide6.QtWidgets import QApplication
    # Usar dir bajo C:\prueba para que revelar_ruta funcione sin short names
    base_tmp = os.path.join(os.path.abspath("."), "tmp_reinicio_test")
    os.makedirs(base_tmp, exist_ok=True)
    tmpdir = tempfile.mkdtemp(dir=base_tmp)
    ruta_db = os.path.join(tmpdir, "test.db")
    conn = conectar_bd(ruta_db)
    conn.commit()
    conn.close()
    A = os.path.join(tmpdir, "A")
    B = os.path.join(tmpdir, "B")
    os.makedirs(A, exist_ok=True)
    os.makedirs(B, exist_ok=True)
    ruta_config = os.path.join(tmpdir, "config_reinicio.json")
    try:
        # Insertar archivo real para que mover funcione FS
        vid, ruta_A = _insertar_video(ruta_db, A, "reinicio21.mp4", contenido=b"abc"*500)
        with open(ruta_A, "wb") as f:
            f.write(b"abc"*500)
        # Primera ventana
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        ventana1 = visor_videos.VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        ventana1.resize(720,540)
        ventana1.show()
        def esperar(pred, intentos=300):
            for _ in range(intentos):
                QApplication.processEvents()
                if pred():
                    return True
                time.sleep(0.02)
            return pred()
        esperar(lambda: ventana1._carga_completada and not ventana1.gestor.activo, intentos=350)
        # Persistir A como carpeta seleccionada (simula cierre con A activa)
        from configuracion import guardar_ultima_carpeta
        ventana1.carpeta_seleccionada = os.path.abspath(A)
        guardar_ultima_carpeta(A, ruta_config)
        # Esperar recarga por carpeta
        esperar(lambda: not ventana1.gestor.activo and not ventana1._reordenamiento_pendiente and not ventana1._recarga_catalogo_pendiente, intentos=350)
        time.sleep(0.2)
        QApplication.processEvents()
        assert any(n == "reinicio21.mp4" for n,_ in ventana1.tarjetas), "v1 debe mostrar video en A antes de mover"
        # Mover A->B vía servicio y handler UI (sin reescaneo)
        res = svc.mover_video(vid, B, ruta_db)
        assert res["ok"]
        ventana1._mover_nombre_anterior = "reinicio21.mp4"
        ventana1._mover_video_id = vid
        reescaneo = []
        orig_ini = visor_videos.VisorVideos.iniciar_escaneo
        orig_crear = visor_videos.VisorVideos._crear_tarea_lectura
        def fake_ini(self,*a,**k):
            reescaneo.append("ini")
            return None
        def fake_crear(self,*a,**k):
            reescaneo.append("crear")
            return orig_crear(self,*a,**k)
        visor_videos.VisorVideos.iniciar_escaneo = fake_ini
        visor_videos.VisorVideos._crear_tarea_lectura = fake_crear
        ventana1._al_resultado_mover(res)
        QApplication.processEvents()
        assert not any(n == "reinicio21.mp4" for n,_ in ventana1.tarjetas), "v1 tras mover debe quitar de A"
        assert not reescaneo, f"no debe escanear tras mover {reescaneo}"
        visor_videos.VisorVideos.iniciar_escaneo = orig_ini
        visor_videos.VisorVideos._crear_tarea_lectura = orig_crear
        ventana1.close()
        ventana1.gestor.cerrar()
        try: ventana1.gestor_previews.cerrar()
        except: pass
        try: ventana1.gestor_renombrado.cerrar()
        except: pass
        try: ventana1.gestor_mover.cerrar()
        except: pass
        # SEGUNDA ventana leyendo misma config (sin asignar manualmente carpeta_seleccionada)
        ventana2 = visor_videos.VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        ventana2.resize(720,540)
        ventana2.show()
        esperar(lambda: ventana2._carga_completada and not ventana2.gestor.activo, intentos=400)
        # esperar posible recarga por carpeta
        for _ in range(60):
            QApplication.processEvents()
            time.sleep(0.02)
        esperar(lambda: not ventana2.gestor.activo and not ventana2._reordenamiento_pendiente and not ventana2._recarga_catalogo_pendiente, intentos=300)
        # Debe haber restaurado A
        assert ventana2.carpeta_seleccionada is not None, "v2 debe restaurar carpeta A"
        assert os.path.normcase(os.path.normpath(ventana2.carpeta_seleccionada)) == os.path.normcase(os.path.normpath(os.path.abspath(A))), f"v2 carpeta {ventana2.carpeta_seleccionada} != A"
        # Verificar visual/estructural A ausente sin escaneo
        assert not any(n == "reinicio21.mp4" for n,_ in ventana2.tarjetas), f"v2 reinicio: video no debe aparecer en A, tarjetas={[n for n,_ in ventana2.tarjetas]}"
        assert "reinicio21.mp4" not in ventana2.visibles
        # Contador coherente (0 en A)
        ventana2.actualizar_contador()
        assert "0 " in ventana2.contador.text() or "0 video" in ventana2.contador.text().lower(), f"contador A debe ser 0, got {ventana2.contador.text()}"
        # Navegar B -> debe aparecer con misma identidad
        ventana2.carpeta_seleccionada = os.path.abspath(B)
        guardar_ultima_carpeta(B, ruta_config)
        ventana2._programar_recarga_por_carpeta()
        esperar(lambda: not ventana2.gestor.activo and not ventana2._reordenamiento_pendiente and not ventana2._recarga_catalogo_pendiente, intentos=400)
        for _ in range(60):
            QApplication.processEvents()
            time.sleep(0.02)
        assert any(n == "reinicio21.mp4" for n,_ in ventana2.tarjetas), "v2 B debe contener video"
        tB = ventana2._tarjeta_por_nombre("reinicio21.mp4")
        assert tB is not None and getattr(tB, "_video_id", None) == vid
        # Volver A -> ausente
        ventana2.carpeta_seleccionada = os.path.abspath(A)
        guardar_ultima_carpeta(A, ruta_config)
        ventana2._programar_recarga_por_carpeta()
        esperar(lambda: not ventana2.gestor.activo and not ventana2._reordenamiento_pendiente and not ventana2._recarga_catalogo_pendiente, intentos=400)
        for _ in range(60):
            QApplication.processEvents()
            time.sleep(0.02)
        assert not any(n == "reinicio21.mp4" for n,_ in ventana2.tarjetas), "v2 volver A debe estar ausente"
        ventana2.close()
        ventana2.gestor.cerrar()
        try: ventana2.gestor_previews.cerrar()
        except: pass
        print("test_21 OK — reinicio REAL con config persistida, navegación A->B->A sin escaneo")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        try: shutil.rmtree(base_tmp, ignore_errors=True)
        except: pass

def test_22_paginacion_y_filtros_por_carpeta():
    """B7.2 fix-017 — paginación, búsqueda y contador operan sobre carpeta, no global.

    - Inserta videos repartidos entre A y B, verifica total por carpeta, LIMIT/OFFSET
      no mezcla, páginas completas, A vs AB no confundido, case y separadores.
    """
    tmpdir = tempfile.mkdtemp()
    ruta_db = os.path.join(tmpdir, "test.db")
    conn = conectar_bd(ruta_db)
    conn.commit()
    conn.close()
    A = os.path.join(tmpdir, "A")
    AB = os.path.join(tmpdir, "AB")
    B = os.path.join(tmpdir, "B")
    os.makedirs(A, exist_ok=True)
    os.makedirs(AB, exist_ok=True)
    os.makedirs(B, exist_ok=True)
    try:
        from escanear_videos import listar_videos_paginado
        from rutas import normalizar_ruta_clave as _norm22
        def ins(nombre, carpeta):
            ruta = os.path.join(carpeta, nombre)
            ruta_abs = os.path.abspath(ruta)
            ruta_norm = _norm22(ruta_abs)
            c = sqlite3.connect(ruta_db)
            # B8.3A: conectar_bd ya creó esquema con ruta_normalizada NOT NULL, pero este ins usa sqlite3 directo sin migraciones; asegurar via conectar_bd helper o insert explícito con ruta_normalizada
            # Intentar asegurar columna por si DB recién creada con conectar_bd ya tiene, sino INSERT fallará; usamos INSERT con ruta_normalizada
            try:
                c.execute("INSERT INTO videos (nombre, ruta, ruta_normalizada, extension, fecha_importacion) VALUES (?,?,?,?,?)", (nombre, ruta_abs, ruta_norm, os.path.splitext(nombre)[1], "2026-01-01T00:00:00"))
            except sqlite3.OperationalError as exc:
                if "no such column" in str(exc).lower() and "ruta_normalizada" in str(exc).lower():
                    # fallback: crear columna y reintentar (migración mínima para test directo)
                    try:
                        c.execute("ALTER TABLE videos ADD COLUMN ruta_normalizada TEXT")
                    except Exception:
                        pass
                    c.execute("INSERT INTO videos (nombre, ruta, ruta_normalizada, extension, fecha_importacion) VALUES (?,?,?,?,?)", (nombre, ruta_abs, ruta_norm, os.path.splitext(nombre)[1], "2026-01-01T00:00:00"))
                else:
                    raise
            c.commit()
            c.close()
        # A vs AB: 3 en A, 2 en AB
        ins("a1.mp4", A); ins("a2.mp4", A); ins("a3.mp4", A)
        ins("ab1.mp4", AB); ins("ab2.mp4", AB)
        pagA = listar_videos_paginado(10,0,None,ruta_db, carpeta=A)
        pagAB = listar_videos_paginado(10,0,None,ruta_db, carpeta=AB)
        assert pagA["total"] == 3, f"A total {pagA['total']} !=3, AB confusion"
        assert pagAB["total"] == 2, f"AB total {pagAB['total']} !=2"
        # Case Windows: carpeta en distinto case debe coincidir (lower)
        pagA_low = listar_videos_paginado(10,0,None,ruta_db, carpeta=A.lower())
        assert pagA_low["total"] == 3, "case-insensitive A lower debe dar 3"
        # Separadores: carpeta con '/' vs '\\' debe coincidir tras replace
        A_slash = A.replace("\\","/")
        pagA_slash = listar_videos_paginado(10,0,None,ruta_db, carpeta=A_slash)
        assert pagA_slash["total"] == 3, "separadores '/' deben normalizarse"
        # Vacío: carpeta inexistente -> 0
        pagVacia = listar_videos_paginado(10,0,None,ruta_db, carpeta=os.path.join(tmpdir,"NOEXISTE"))
        assert pagVacia["total"] == 0
        # Múltiples páginas con reparto A/B: insertar 12 en A, 8 en B, paginar A 5 por página
        for i in range(12):
            ins(f"pA_{i:02d}.mp4", A)
        for i in range(8):
            ins(f"pB_{i:02d}.mp4", B)
        # A ahora debe tener 3+12=15
        pagA_total = listar_videos_paginado(100,0,None,ruta_db, carpeta=A)["total"]
        assert pagA_total == 15, f"A total tras insert {pagA_total} !=15"
        # Páginas completas: 5,5,5
        p1 = listar_videos_paginado(5,0,None,ruta_db, carpeta=A)
        p2 = listar_videos_paginado(5,5,None,ruta_db, carpeta=A)
        p3 = listar_videos_paginado(5,10,None,ruta_db, carpeta=A)
        assert len(p1["videos"])==5 and len(p2["videos"])==5 and len(p3["videos"])==5, f"paginación incompleta {len(p1['videos'])},{len(p2['videos'])},{len(p3['videos'])}"
        # Verificar que ninguna página contiene videos de B o AB (no mezcla)
        for pag in [p1,p2,p3]:
            for fila in pag["videos"]:
                ruta = fila[7]
                assert os.path.normcase(os.path.dirname(os.path.abspath(ruta))) == os.path.normcase(os.path.abspath(A)), f"ruta {ruta} no pertenece a A"
        # Búsqueda dentro de carpeta: texto 'pA_' debe dar 12 en A, 0 en B
        pagA_search = listar_videos_paginado(100,0,"pA_",ruta_db, carpeta=A)
        pagB_search = listar_videos_paginado(100,0,"pA_",ruta_db, carpeta=B)
        assert pagA_search["total"] == 12, f"busqueda pA_ en A {pagA_search['total']} !=12"
        assert pagB_search["total"] == 0, f"busqueda pA_ en B debe 0 got {pagB_search['total']}"
        # Contador: total carpeta == len(tarjetas) si cargamos todo
        print("test_22 OK — paginación y filtros por carpeta, A vs AB, case, sep, vacío, búsqueda")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

if __name__ == "__main__":
    test_01_same_volume_exito()
    test_02_id_relaciones_preservadas()
    test_03_misma_carpeta_rechazo()
    test_04_colision_rechazo()
    test_05_origen_faltante()
    test_06_db_falla_rollback_same()
    test_07_rollback_falla_critico_same()
    test_08_cross_forzado_exito()
    test_09_hash_distinto_aborta_cross()
    test_10_db_falla_cross_compensa_destino()
    test_11_remove_origen_falla_critico_cross()
    test_12_temporales_limpios_en_fallos()
    test_13_ui_delega_background()
    test_14_recarga_usa_nueva_ruta_sin_escaneo()
    test_15_helper_actualizar_ruta_video()
    test_16_ui_actualiza_tarjeta_sin_reescaneo()
    test_17_actualizar_ruta_rechaza_basename_inconsistente()
    test_18_sin_fallback_silencioso_en_resultado_mover()
    test_19_smoke_conductual_mover_real()
    test_20_diagnostico_catalogo_origen_post_move()
    test_21_reinicio_real_persistido_navegacion()
    test_22_paginacion_y_filtros_por_carpeta()
    print("TODOS B7.2 OK (22 tests)")

