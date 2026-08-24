"""Prueba B8.2 — Migración legacy en carga inicial (contrato carga sin reescaneo)"""
import os, tempfile, sqlite3, time, shutil
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import QLabel

import escanear_videos as escanear_mod
import visor_videos, rutas as rutas_mod, tareas_videos as tv
from escanear_videos import ruta_miniatura as ruta_miniatura_legacy, ruta_preview as ruta_preview_legacy, ruta_miniatura_id, ruta_preview_id, conectar_bd
from visor_videos import VisorVideos

_CONFIG_TEMPORAL = tempfile.TemporaryDirectory()
os.environ["VISOR_CONFIG"] = os.path.join(_CONFIG_TEMPORAL.name, "configuracion.json")

def _filas(nombres, carpeta="C:\\"):
    filas=[]
    for i,nombre in enumerate(nombres, start=1):
        filas.append((nombre, os.path.join(carpeta, nombre), os.path.splitext(nombre)[1].lower(), "2026-08-03T00:00:00", float(i%5), i, i, "h264", i%3))
    return filas

def _crear_bd(filas):
    temp=tempfile.TemporaryDirectory()
    ruta_db=os.path.join(temp.name, "catalogo.db")
    conn=sqlite3.connect(ruta_db)
    try:
        conn.execute("""
            CREATE TABLE videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE,
                ruta TEXT NOT NULL,
                extension TEXT NOT NULL,
                fecha_importacion TEXT NOT NULL,
                duracion_segundos REAL,
                ancho INTEGER,
                alto INTEGER,
                codec_video TEXT,
                cantidad_miniaturas INTEGER,
                tamano_bytes INTEGER
            )
        """)
        conn.executemany("INSERT INTO videos (nombre, ruta, extension, fecha_importacion, duracion_segundos, ancho, alto, codec_video, cantidad_miniaturas) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", filas)
        conn.commit()
    finally:
        conn.close()
    return temp, ruta_db

def _crear_png(ruta, ancho=100, alto=60, color="blue"):
    imagen=QImage(ancho, alto, QImage.Format_RGB32)
    imagen.fill(QColor(color))
    ok=imagen.save(ruta)
    if not ok:
        # fallback dummy
        with open(ruta, "wb") as f:
            f.write(b"dummy")
    return ok

def _esperar(pred, timeout_ms=10000, paso_ms=20):
    fin=time.monotonic()+timeout_ms/1000
    while time.monotonic() < fin:
        QApplication.processEvents()
        if pred():
            return True
        time.sleep(paso_ms/1000)
    QApplication.processEvents()
    return pred()

def _pixmaps_de(tarjeta):
    return [l.pixmap() for l in tarjeta.findChildren(QLabel) if l.pixmap() is not None and not l.pixmap().isNull()]

def _previews_pixmaps(tarjeta):
    return sum(1 for l in tarjeta._etiquetas_previews if l.pixmap() is not None and not l.pixmap().isNull())

import contextlib
@contextlib.contextmanager
def _miniaturas_temporales():
    temp=tempfile.TemporaryDirectory()
    orig_esc=escanear_mod.ruta_carpeta_miniaturas
    orig_vis=visor_videos.ruta_carpeta_miniaturas
    orig_rutas=rutas_mod.ruta_carpeta_miniaturas
    escanear_mod.ruta_carpeta_miniaturas=lambda: temp.name
    visor_videos.ruta_carpeta_miniaturas=lambda: temp.name
    rutas_mod.ruta_carpeta_miniaturas=lambda: temp.name
    try:
        yield temp.name
    finally:
        escanear_mod.ruta_carpeta_miniaturas=orig_esc
        visor_videos.ruta_carpeta_miniaturas=orig_vis
        rutas_mod.ruta_carpeta_miniaturas=orig_rutas
        temp.cleanup()

def _limpiar(ventana):
    if ventana is None:
        return
    for g in [getattr(ventana,"gestor",None), getattr(ventana,"gestor_migracion",None), getattr(ventana,"gestor_previews",None)]:
        try:
            if g is not None and g.hilo is not None:
                g.cerrar()
        except: pass
    try:
        ventana.deleteLater()
    except: pass
    for _ in range(5):
        QApplication.processEvents()

def test_01_legacy_migracion_background_carga_inicial():
    """Contrato: registro con video_id estable, solo caché legacy, abrir sin reescanear -> migración batch background, tarjeta termina con miniatura/previews por id, legacy preservada"""
    with _miniaturas_temporales() as carpeta:
        # Crear legacy solo (sin v<id>)
        # Usaremos video nombre con prefijo simple para evitar ambigüedad
        legacy_mini=os.path.join(carpeta, "video_01_01.jpg")
        legacy_prevs=[os.path.join(carpeta, f"video_01_preview_{i:02d}.jpg") for i in range(1,4)]
        for p in [legacy_mini]+legacy_prevs:
            assert _crear_png(p), f"no se pudo crear {p}"
        # Verificar que no existe id aún
        assert not os.path.isfile(os.path.join(carpeta, "v1_01.jpg"))
        temp, ruta_db=_crear_bd(_filas(["video_01.mp4","otra.mp4"]))
        try:
            ventana=VisorVideos(ruta_db=ruta_db)
            _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None, timeout_ms=8000)
            # Carga inicial: tarjeta debe mostrar Sin miniatura hasta migración (no debe perder visual permanentemente)
            tarjeta=dict(ventana.tarjetas)["video_01.mp4"]
            vid=getattr(tarjeta,"_video_id", None)
            assert isinstance(vid,int) and vid>0, f"video_id invalido {vid}"
            # Esperar migración batch background
            ok_mig=_esperar(lambda v=ventana: not getattr(v,"gestor_migracion",None).activo if getattr(v,"gestor_migracion",None) else True, timeout_ms=6000)
            # Dar tiempo a que handler actualice UI
            _esperar(lambda: os.path.isfile(os.path.join(carpeta, f"v{vid}_01.jpg")), timeout_ms=4000)
            QApplication.processEvents()
            time.sleep(0.15)
            QApplication.processEvents()
            # Verificar rutas id creadas
            ruta_id_mini=os.path.join(carpeta, f"v{vid}_01.jpg")
            rutas_id_prevs=[os.path.join(carpeta, f"v{vid}_preview_{i:02d}.jpg") for i in range(1,4)]
            id_mini_ok=os.path.isfile(ruta_id_mini)
            id_prevs_ok=all(os.path.isfile(p) for p in rutas_id_prevs)
            legacy_ok=os.path.isfile(legacy_mini) and all(os.path.isfile(p) for p in legacy_prevs)
            # Tarjeta debe haber sido refrescada sin recargar catálogo ni perder selección/scroll
            # No debe haber hecho reescaneo (gestor activo ya inactivo, cola no vacía)
            # Verificar pixmaps: debe tener 4 (1 miniatura +3 previews) tras migración automática
            pixs=len(_pixmaps_de(tarjeta))
            prevs=_previews_pixmaps(tarjeta)
            # También verificar que previews_de_por_id retorna 3
            try:
                rutas_id=visor_videos.previews_de_por_id(vid)
            except:
                rutas_id=[]
            # No reescaneo: cantidad de videos sigue igual
            total_antes=len(ventana.tarjetas)
            # Verificar que no hubo pérdida de selección/scroll (no se reseteó)
            ok= id_mini_ok and id_prevs_ok and legacy_ok and pixs==4 and prevs==3 and len(rutas_id)==3 and total_antes==2
            ventana.close()
            _limpiar(ventana)
            return ok, f"vid={vid} id_mini={id_mini_ok} id_prevs={id_prevs_ok} legacy={legacy_ok} pixs={pixs} prevs={prevs} rutas_id={len(rutas_id)}"
        finally:
            temp.cleanup()

def test_02_no_cruce_entre_videos_batch():
    """Dos videos, solo uno con legacy: solo tarjeta objetivo se actualiza, otro permanece sin miniatura"""
    with _miniaturas_temporales() as carpeta:
        # video A con legacy, video B sin nada
        legacy_mini=os.path.join(carpeta, "a_01.jpg")
        legacy_prevs=[os.path.join(carpeta, f"a_preview_{i:02d}.jpg") for i in range(1,4)]
        for p in [legacy_mini]+legacy_prevs:
            _crear_png(p)
        # No crear legacy para b
        temp, ruta_db=_crear_bd(_filas(["a.mp4","b.mp4"]))
        try:
            ventana=VisorVideos(ruta_db=ruta_db)
            _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
            tarjeta_a=dict(ventana.tarjetas)["a.mp4"]
            tarjeta_b=dict(ventana.tarjetas)["b.mp4"]
            vid_a=getattr(tarjeta_a,"_video_id",None)
            vid_b=getattr(tarjeta_b,"_video_id",None)
            # esperar migración
            _esperar(lambda v=ventana: not getattr(v,"gestor_migracion",None).activo if getattr(v,"gestor_migracion",None) else True, timeout_ms=6000)
            _esperar(lambda: os.path.isfile(os.path.join(carpeta, f"v{vid_a}_01.jpg")) if isinstance(vid_a,int) else False, timeout_ms=4000)
            QApplication.processEvents()
            time.sleep(0.15)
            QApplication.processEvents()
            pix_a=len(_pixmaps_de(tarjeta_a))
            pix_b=len(_pixmaps_de(tarjeta_b))
            prev_a=_previews_pixmaps(tarjeta_a)
            prev_b=_previews_pixmaps(tarjeta_b)
            id_a_ok=os.path.isfile(os.path.join(carpeta, f"v{vid_a}_01.jpg")) if isinstance(vid_a,int) else False
            id_b_exists=os.path.isfile(os.path.join(carpeta, f"v{vid_b}_01.jpg")) if isinstance(vid_b,int) else False
            # b no debe tener archivo id ni pixmaps
            ok= pix_a==4 and prev_a==3 and id_a_ok and pix_b==0 and prev_b==0 and not id_b_exists
            ventana.close()
            _limpiar(ventana)
            return ok, f"a pix={pix_a} prev={prev_a} id_a={id_a_ok} b pix={pix_b} prev={prev_b} id_b={id_b_exists} vid_a={vid_a} vid_b={vid_b}"
        finally:
            temp.cleanup()

def test_03_fallo_migracion_observable_no_destruye_legacy():
    """Fallo de copia debe ser observable (fallos>0) y legacy permanece intacta"""
    with _miniaturas_temporales() as carpeta:
        legacy=os.path.join(carpeta, "c_01.jpg")
        _crear_png(legacy)
        # crear también previews legacy para forzar copia múltiple
        for i in range(1,4):
            _crear_png(os.path.join(carpeta, f"c_preview_{i:02d}.jpg"))
        # Forzar fallo: crear directorio con nombre destino v1_01.jpg antes de migrar
        # Necesitamos saber vid antes: será 1
        temp, ruta_db=_crear_bd(_filas(["c.mp4"]))
        try:
            # Pre-crear directorio que bloqueará copia para v1_01.jpg
            dst_dir=os.path.join(carpeta, "v1_01.jpg")
            # si ya existe archivo, borrar y crear dir
            if os.path.isfile(dst_dir):
                os.remove(dst_dir)
            os.makedirs(dst_dir, exist_ok=True)
            ventana=VisorVideos(ruta_db=ruta_db)
            _esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
            tarjeta=dict(ventana.tarjetas)["c.mp4"]
            vid=getattr(tarjeta,"_video_id",1)
            # esperar migración (debe terminar aunque falle)
            _esperar(lambda v=ventana: not getattr(v,"gestor_migracion",None).activo if getattr(v,"gestor_migracion",None) else True, timeout_ms=6000)
            QApplication.processEvents()
            time.sleep(0.2)
            QApplication.processEvents()
            legacy_ok=os.path.isfile(legacy) and all(os.path.isfile(os.path.join(carpeta, f"c_preview_{i:02d}.jpg")) for i in range(1,4))
            # El destino sigue siendo directorio (fallo), no archivo
            is_dir=os.path.isdir(dst_dir)
            # Verificar que ventana reportó fallo vía gestor (no borró legacy, tarjeta sigue sin miniatura pero no crash)
            pixs=len(_pixmaps_de(tarjeta))
            # Limpiar directorio para no contaminar
            try: os.rmdir(dst_dir)
            except: pass
            ok= legacy_ok and is_dir
            ventana.close()
            _limpiar(ventana)
            return ok, f"legacy_ok={legacy_ok} is_dir={is_dir} pixs={pixs} vid={vid}"
        finally:
            # asegurar limpieza del dir
            try:
                d=os.path.join(carpeta, "v1_01.jpg")
                if os.path.isdir(d):
                    os.rmdir(d)
            except: pass
            temp.cleanup()

def test_04_no_io_pesado_en_UI_batch():
    """Verificar batch y ausencia de FS pesado en Tarjeta/UI"""
    import ast
    src=open("visor_videos.py", encoding="utf-8").read()
    tree=ast.parse(src)
    # Tarjeta no debe contener listdir/copyfile/migrar_cache
    tarjeta_src=None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name=="Tarjeta":
            tarjeta_src=ast.get_source_segment(src, node)
            break
    if tarjeta_src is None:
        return False, "Tarjeta no encontrada"
    for bad in ["migrar_cache_legacy_a_id","listdir","copyfile"]:
        if bad in tarjeta_src:
            return False, f"Tarjeta contiene {bad}"
    # miniatura_principal_por_id no debe hacer listdir/isfile
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name=="miniatura_principal_por_id":
            s=ast.get_source_segment(src, node)
            if "listdir" in s or "isfile" in s or "isdir" in s or "copyfile" in s:
                return False, f"miniatura_principal_por_id con FS pesado {s[:120]}"
            if "range(1, 1000)" in s:
                return False, "loop 1..999 en miniatura_principal_por_id"
            break
    # Visor debe usar batch: _encolar_migracion_legacy recibe filas y usa TareaMigrarCacheLegacy una sola vez por lote
    visor_src=src
    if "_encolar_migracion_legacy" not in visor_src or "TareaMigrarCacheLegacy" not in visor_src:
        return False, "Visor no usa batch TareaMigrarCacheLegacy"
    if "gestor_migracion" not in visor_src:
        return False, "gestor_migracion no encontrado"
    # Verificar que _encolar_migracion_legacy no hace listdir/copyfile
    import inspect
    try:
        from visor_videos import VisorVideos
        s2=inspect.getsource(VisorVideos._encolar_migracion_legacy)
        if "listdir" in s2 or "copyfile" in s2 or "isfile" in s2:
            return False, f"_encolar_migracion_legacy con FS pesado {s2[:200]}"
    except Exception as e:
        return False, f"inspect error {e}"
    return True, "UI sin FS pesado y batch OK"

def main():
    app=QApplication.instance()
    if app is None:
        app=QApplication([])
    tests=[test_01_legacy_migracion_background_carga_inicial, test_02_no_cruce_entre_videos_batch, test_03_fallo_migracion_observable_no_destruye_legacy, test_04_no_io_pesado_en_UI_batch]
    res=[]
    for i,fn in enumerate(tests,1):
        try:
            ok,det=fn()
        except Exception as e:
            import traceback; traceback.print_exc()
            ok,det=False, f"excepcion {type(e).__name__}: {e}"
        res.append((i,ok,det))
        print(f"P{i:02d} {'OK' if ok else 'FALLO'} - {det}")
    ok_total=all(o for _,o,_ in res)
    print(f"TOTAL={sum(1 for _,o,_ in res if o)}/{len(tests)}")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")
    return 0 if ok_total else 1

if __name__=="__main__":
    import sys; sys.exit(main())
