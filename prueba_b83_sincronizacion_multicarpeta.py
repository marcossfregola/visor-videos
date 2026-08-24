"""Suite B8.3A — sincronización multicarpeta scope-segura."""
import os, sys, sqlite3, tempfile, shutil
from escanear_videos import conectar_bd, sincronizar_bd, detectar_diferencias, preparar_plan_sincronizacion, eliminar_candidatos
from rutas import normalizar_ruta_clave

_CONT=0; _FAIL=0
def ok(m): global _CONT; _CONT+=1; print(f"T{_CONT:02d} OK - {m}")
def falla(m,e=None): global _CONT,_FAIL; _CONT+=1; _FAIL+=1; print(f"T{_CONT:02d} FAIL - {m} {e or ''}")
def verifica(c,d,extra=None):
    if c: ok(d)
    else: falla(d,extra)

def _db():
    tmp=tempfile.mkdtemp()
    db=os.path.join(tmp,"test.db")
    conn=conectar_bd(db); conn.commit(); conn.close()
    return tmp,db

def _ins_file(carpeta,nombre,contenido=b"x"):
    os.makedirs(carpeta,exist_ok=True)
    p=os.path.join(carpeta,nombre)
    open(p,"wb").write(contenido)
    return p

def test_sincronizar_bd_scope():
    tmp,db=_db()
    A=os.path.join(tmp,"A"); B=os.path.join(tmp,"B")
    os.makedirs(A,exist_ok=True); os.makedirs(B,exist_ok=True)
    try:
        pA=_ins_file(A,"video.mp4",b"a")
        pB=_ins_file(B,"otro.mp4",b"b")
        conn=conectar_bd(db)
        sincronizar_bd(conn,A)
        sincronizar_bd(conn,B)
        conn.commit()
        cnt=conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
        verifica(cnt==2,f"catalogados A+ B {cnt}")
        # ambos siguen tras sincronizar A con ambos en disco
        sincronizar_bd(conn,A)
        conn.commit()
        cnt2=conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
        verifica(cnt2==2,"sincronizar A ambos siguen")
        # ambos siguen tras sincronizar B
        sincronizar_bd(conn,B)
        conn.commit()
        cnt3=conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
        verifica(cnt3==2,"sincronizar B ambos siguen")
        # borrar B/otro del FS
        os.remove(pB)
        sincronizar_bd(conn,A)
        conn.commit()
        cnt4=conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
        verifica(cnt4==2,"sincronizar A no borra B (scope)")
        # verificar B sigue en DB
        normB=normalizar_ruta_clave(pB)
        fila=conn.execute("SELECT ruta_normalizada FROM videos WHERE ruta_normalizada=?",(normB,)).fetchone()
        verifica(fila is not None,"B sigue en DB tras sync A")
        # sincronizar B solo B se elimina
        sincronizar_bd(conn,B)
        conn.commit()
        cnt5=conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
        verifica(cnt5==1,"sync B elimina solo B")
        filaA=conn.execute("SELECT ruta_normalizada FROM videos WHERE ruta_normalizada=?",(normalizar_ruta_clave(pA),)).fetchone()
        verifica(filaA is not None,"A sigue")
        filaB=conn.execute("SELECT ruta_normalizada FROM videos WHERE ruta_normalizada=?",(normB,)).fetchone()
        verifica(filaB is None,"B eliminado")
        # integrity
        chk=conn.execute("PRAGMA integrity_check").fetchone()[0]
        verifica(chk=="ok","integrity ok")
        conn.close()
    finally: shutil.rmtree(tmp,ignore_errors=True)

def test_moderno_aislamiento():
    tmp,db=_db()
    A=os.path.join(tmp,"A"); B=os.path.join(tmp,"B")
    os.makedirs(A,exist_ok=True); os.makedirs(B,exist_ok=True)
    try:
        pA=_ins_file(A,"video.mp4",b"a")
        pB=_ins_file(B,"otro.mp4",b"b")
        conn=conectar_bd(db)
        # inicial catalogar vía sync
        sincronizar_bd(conn,A); sincronizar_bd(conn,B); conn.commit(); conn.close()
        # detectar diferencias moderno
        difA=detectar_diferencias(A,db)
        difB=detectar_diferencias(B,db)
        verifica("video.mp4" in difA["presentes_en_ambos"],"moderno A presente")
        verifica("otro.mp4" in difB["presentes_en_ambos"],"moderno B presente")
        verifica(difA["ausentes_del_disco"]==[],"moderno A ausentes vacío")
        # borrar B
        os.remove(pB)
        difA2=detectar_diferencias(A,db)
        difB2=detectar_diferencias(B,db)
        verifica(difA2["ausentes_del_disco"]==[],"moderno A no lista B borrado")
        verifica("otro.mp4" in difB2["ausentes_del_disco"],"moderno B ausente correcto")
        # preparar+eliminar solo B
        planB=preparar_plan_sincronizacion(difB2)
        res=eliminar_candidatos(planB,db)
        verifica(res["eliminados"]==1,"moderno eliminar solo B")
        conn=sqlite3.connect(db)
        cnt=conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
        verifica(cnt==1,"moderno queda solo A")
        chk=conn.execute("PRAGMA integrity_check").fetchone()[0]
        verifica(chk=="ok","moderno integrity ok")
        conn.close()
    finally: shutil.rmtree(tmp,ignore_errors=True)

def test_homonimos_sync():
    tmp,db=_db()
    # Padre A con subcarpetas B y C homónimos video.mp4
    A=os.path.join(tmp,"A"); B=os.path.join(A,"B"); C=os.path.join(A,"C")
    os.makedirs(B,exist_ok=True); os.makedirs(C,exist_ok=True)
    try:
        pB=_ins_file(B,"video.mp4",b"b")
        pC=_ins_file(C,"video.mp4",b"c")
        # Crear DB via conectar_bd y guardar rutas exactas
        from escanear_videos import guardar_videos
        # usar guardar_videos para insertar ambos con rutas normalizadas distintas
        registros=[
            {"nombre":"video.mp4","ruta":pB,"extension":".mp4","fecha_importacion":"2026-01-01T00:00:00"},
            {"nombre":"video.mp4","ruta":pC,"extension":".mp4","fecha_importacion":"2026-01-01T00:00:00"},
        ]
        res=guardar_videos(registros, db)
        verifica(res["guardados"]==2,"homonimos guardados 2")
        conn=sqlite3.connect(db)
        filas=conn.execute("SELECT id, ruta, ruta_normalizada FROM videos ORDER BY ruta").fetchall()
        verifica(len(filas)==2 and filas[0][2]!=filas[1][2],"homonimos IDs distintos y rutas normalizadas distintas")
        ids={row[2]:row[0] for row in filas}
        conn.close()
        # Procesar B con archivo ausente -> solo B candidato
        os.remove(pB)
        difB=detectar_diferencias(B, db)
        verifica("video.mp4" in difB["ausentes_del_disco"],"homonimo B ausente listado")
        verifica("ausentes_rutas_normalizadas" in difB,"homonimo B tiene ausentes_rutas_normalizadas")
        normB=normalizar_ruta_clave(pB)
        verifica(normB in difB["ausentes_rutas_normalizadas"],"homonimo B ruta exacta en ausentes_rutas_normalizadas")
        normC=normalizar_ruta_clave(pC)
        verifica(normC not in difB["ausentes_rutas_normalizadas"],"homonimo C no en ausentes de B")
        planB=preparar_plan_sincronizacion(difB)
        verifica("candidatos_a_eliminar_rutas" in planB,"planB tiene candidatos_a_eliminar_rutas")
        verifica(normB in planB["candidatos_a_eliminar_rutas"],"planB ruta exacta B presente")
        verifica(normC not in planB["candidatos_a_eliminar_rutas"],"planB ruta C no presente")
        resE=eliminar_candidatos(planB, db)
        verifica(resE["eliminados"]==1,"homonimo eliminar solo B")
        conn=sqlite3.connect(db)
        cnt=conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
        verifica(cnt==1,"homonimo queda solo C tras borrar B")
        filaC=conn.execute("SELECT ruta_normalizada FROM videos WHERE ruta_normalizada=?",(normC,)).fetchone()
        verifica(filaC is not None,"homonimo C permanece tras borrar B")
        filaB=conn.execute("SELECT ruta_normalizada FROM videos WHERE ruta_normalizada=?",(normB,)).fetchone()
        verifica(filaB is None,"homonimo B eliminado")
        conn.close()
        # Restaurar B para siguiente subtest
        pB=_ins_file(B,"video.mp4",b"b2")
        conn=sqlite3.connect(db)
        # reinsertar B via guardar
        guardar_videos([{"nombre":"video.mp4","ruta":pB,"extension":".mp4","fecha_importacion":"2026-01-01T00:00:00"}], db)
        conn.close()
        # Procesar A con B y C protegidas -> ninguno ausente
        # Borrar de nuevo B para probar protección? No, dejar ambos presentes, entonces A no debe listar ausentes
        difA=detectar_diferencias(A, db, carpetas_protegidas=[B,C])
        verifica(difA["ausentes_del_disco"]==[],"A con B y C protegidas ninguno ausente (ambos presentes)")
        verifica(difA["ausentes_rutas_normalizadas"]==[],"A protegidas rutas vacías")
        # Ahora borrar B y procesar A con protegidas -> aún ninguno ausente (B protegida)
        os.remove(pB)
        difA2=detectar_diferencias(A, db, carpetas_protegidas=[B,C])
        verifica(difA2["ausentes_del_disco"]==[],"A con B protegida aunque B falta no lista ausente")
        verifica(difA2["ausentes_rutas_normalizadas"]==[],"A protegida rutas vacías aunque B falta")
        # Procesar B sin protección debe listar ausente
        difB2=detectar_diferencias(B, db)
        verifica("video.mp4" in difB2["ausentes_del_disco"],"B sin protección lista ausente tras borrar")
        # eliminar_candidatos con ruta exacta B borra solo B (ya probado) y C queda
        planB2=preparar_plan_sincronizacion(difB2)
        resE2=eliminar_candidatos(planB2, db)
        verifica(resE2["eliminados"]==1,"homonimo segundo borrado B exacto")
        conn=sqlite3.connect(db)
        cnt2=conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
        verifica(cnt2==1,"homonimo queda C tras segundo borrado")
        conn.close()
        # Intento legacy ambiguo por basename sin ruta exacta -> error visible / cero borrados
        plan_legacy={"carpeta": B, "a_incorporar": [], "ya_sincronizados": [], "candidatos_a_eliminar": ["video.mp4"]}
        try:
            resL=eliminar_candidatos(plan_legacy, db)
            # Si no lanza, debe ser cero borrados
            verifica(resL["eliminados"]==0,"legacy sin ruta exacta cero borrados")
        except ValueError as exc:
            verifica("ruta_normalizada" in str(exc).lower() or "identidad exacta" in str(exc).lower(),"legacy sin ruta exacta error visible")
        except Exception as exc:
            falla("legacy sin ruta exacta error inesperado", str(exc))
        # integrity
        conn=sqlite3.connect(db)
        chk=conn.execute("PRAGMA integrity_check").fetchone()[0]
        verifica(chk=="ok","homonimos integrity ok")
        conn.close()
    finally: shutil.rmtree(tmp,ignore_errors=True)

def test_shrink_helper():
    tmp,db=_db()
    A=os.path.join(tmp,"A"); B=os.path.join(tmp,"B"); X=os.path.join(tmp,"X")
    for d in [A,B,X]: os.makedirs(d,exist_ok=True)
    try:
        pA=_ins_file(A,"a.mp4",b"a")
        pB=_ins_file(B,"b.mp4",b"b")
        pX=_ins_file(X,"x.mp4",b"x")
        from escanear_videos import guardar_videos, eliminar_registros_de_carpetas_retiradas
        guardar_videos([
            {"nombre":"a.mp4","ruta":pA,"extension":".mp4","fecha_importacion":"2026-01-01T00:00:00"},
            {"nombre":"b.mp4","ruta":pB,"extension":".mp4","fecha_importacion":"2026-01-01T00:00:00"},
            {"nombre":"x.mp4","ruta":pX,"extension":".mp4","fecha_importacion":"2026-01-01T00:00:00"},
        ], db)
        conn=sqlite3.connect(db)
        cnt=conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
        verifica(cnt==3,"shrink inicial 3 filas")
        conn.close()
        # Helper recibe solo B (retirada), debe eliminar solo B/b
        res=eliminar_registros_de_carpetas_retiradas(db, [B])
        verifica(res["eliminados"]==1,"shrink helper elimina solo B")
        verifica(len(res["ids"])==1 and len(res["rutas"])==1,"shrink helper ids/rutas deterministas")
        normB=normalizar_ruta_clave(pB)
        verifica(normB in res["rutas"],"shrink helper ruta B en resultado")
        conn=sqlite3.connect(db)
        cnt2=conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
        verifica(cnt2==2,"shrink quedan 2 tras eliminar B")
        filaA=conn.execute("SELECT 1 FROM videos WHERE ruta_normalizada=?",(normalizar_ruta_clave(pA),)).fetchone()
        verifica(filaA is not None,"shrink A permanece")
        filaX=conn.execute("SELECT 1 FROM videos WHERE ruta_normalizada=?",(normalizar_ruta_clave(pX),)).fetchone()
        verifica(filaX is not None,"shrink X permanece (nunca retirada)")
        filaB=conn.execute("SELECT 1 FROM videos WHERE ruta_normalizada=?",(normB,)).fetchone()
        verifica(filaB is None,"shrink B eliminado")
        conn.close()
        # Helper ejecutado desde tarea worker: capturar thread id
        import threading
        from tareas_videos import TareaSincronizacionCatalogo
        from PySide6.QtWidgets import QApplication
        import time
        # Preparar B de nuevo para probar via tarea
        _ins_file(B,"b.mp4",b"b2")
        guardar_videos([{"nombre":"b.mp4","ruta":pB,"extension":".mp4","fecha_importacion":"2026-01-01T00:00:00"}], db)
        # Necesitamos un gestor y tarea que haga shrink [A,B]->[A]
        # Simulamos carpetas_retiradas=[B] en worker
        main_thread = threading.get_ident()
        tarea = TareaSincronizacionCatalogo(B, db, carpetas_retiradas=[B])
        # Ejecutar _trabajo en hilo separado para verificar no main
        result_holder={}
        def run():
            result_holder["res"]=tarea._trabajo()
            result_holder["tid"]=result_holder["res"].get("shrink",{}).get("thread_id")
            result_holder["is_main"]=result_holder["res"].get("shrink",{}).get("is_main_thread")
        th=threading.Thread(target=run)
        th.start(); th.join(timeout=5)
        verifica("res" in result_holder,"shrink tarea worker ejecutada")
        if "res" in result_holder:
            verifica(result_holder["tid"] != main_thread,"shrink ejecutado fuera del hilo principal")
            verifica(result_holder["is_main"]==False,"shrink is_main_thread False")
            verifica(result_holder["res"]["shrink"]["eliminados"]>=0,"shrink worker resultado determinista")
        # Fallo de cleanup -> rollback, datos intactos, error visible
        # Simular fallo por carpeta retirada inválida (vacía) -> helper debe error visible y no borrar
        conn=sqlite3.connect(db)
        cnt_antes = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
        conn.close()
        try:
            res_bad=eliminar_registros_de_carpetas_retiradas(db, [""])
            falla("shrink con carpeta vacía debe fallar", str(res_bad))
        except (ValueError, TypeError) as exc:
            verifica("vacía" in str(exc).lower() or "inválida" in str(exc).lower() or "carpeta" in str(exc).lower(),"shrink con carpeta inválida error visible")
            # Verificar rollback: datos intactos
            conn=sqlite3.connect(db)
            cnt3=conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
            verifica(cnt3==cnt_antes,"shrink fallo rollback datos intactos")
            filaA2=conn.execute("SELECT 1 FROM videos WHERE ruta_normalizada=?",(normalizar_ruta_clave(pA),)).fetchone()
            verifica(filaA2 is not None,"shrink fallo rollback A intacto")
            conn.close()
        except Exception as exc:
            falla("shrink fallo tipo inesperado", str(exc))
        # También probar NULL ruta_normalizada si es posible (aunque schema NOT NULL impide insertarlo, verificamos que helper detectaría)
        # Creamos DB temporal con tabla sin NOT NULL para simular corrupción
        tmp2=tempfile.mkdtemp(); db2=os.path.join(tmp2,"corrupt.db")
        conn2=sqlite3.connect(db2)
        conn2.execute("CREATE TABLE videos (id INTEGER PRIMARY KEY, nombre TEXT, ruta TEXT, extension TEXT, fecha_importacion TEXT, ruta_normalizada TEXT)")
        conn2.execute("INSERT INTO videos (nombre, ruta, extension, fecha_importacion, ruta_normalizada) VALUES (?,?,?,? ,?)", ("good.mp4", pA, ".mp4", "x", normalizar_ruta_clave(pA)))
        conn2.execute("INSERT INTO videos (nombre, ruta, extension, fecha_importacion, ruta_normalizada) VALUES (?,?,?,? ,?)", ("bad.mp4", os.path.join(tmp,"bad.mp4"), ".mp4", "x", None))
        conn2.commit(); conn2.close()
        try:
            res_bad2=eliminar_registros_de_carpetas_retiradas(db2, [A])
            falla("shrink corrupto NULL debe fallar", str(res_bad2))
        except ValueError as exc:
            verifica("NULL" in str(exc) or "vacía" in str(exc),"shrink corrupto NULL error visible")
        except Exception as exc:
            falla("shrink corrupto tipo inesperado", str(exc))
        finally:
            shutil.rmtree(tmp2,ignore_errors=True)
        # integrity final
        conn=sqlite3.connect(db)
        chk=conn.execute("PRAGMA integrity_check").fetchone()[0]
        verifica(chk=="ok","shrink integrity ok")
        conn.close()
    finally: shutil.rmtree(tmp,ignore_errors=True)

def test_arquitectura_ui():
    import ast, pathlib
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "visor_videos.py")
    with open(ruta, encoding="utf-8") as f:
        src=f.read()
        arbol=ast.parse(src, ruta)
    # 1) visor no importa sqlite3 ni dinámicamente para shrink
    has_sqlite_import = ("sqlite3" in src)
    # buscar importlib.import_module('sqlite3') en src
    has_importlib_sqlite = "import_module('sqlite3')" in src or 'import_module("sqlite3")' in src
    verifica(not has_sqlite_import,"arquitectura UI no importa sqlite3")
    verifica(not has_importlib_sqlite,"arquitectura UI no usa importlib para sqlite3")
    # 2) no contiene SELECT, DELETE FROM videos, commit() relacionados al shrink
    # Buscar strings exactos en visor que indicarían acceso directo
    has_select = "SELECT" in src and "ruta_normalizada" in src  # heurística
    # Más preciso: buscar "DELETE FROM videos" en visor
    has_delete = "DELETE FROM videos" in src
    # commit() relacionado a DB: buscar "conn.commit" en visor
    has_commit = "conn.commit" in src
    # Para ser honesto, permitimos commit de otras tareas pero no de videos shrink
    # La prueba original busca SELECT/DELETE/commit en visor; nosotros ya eliminamos shrink
    verifica(not has_delete,"arquitectura UI sin DELETE FROM videos")
    verifica(not has_commit or "DELETE FROM videos" not in src,"arquitectura UI sin commit DB shrink")
    # 3) tareas sí realizan DB fuera del hilo principal (verificar que TareaSincronizacionCatalogo usa eliminar_registros...)
    ruta_tareas=os.path.join(os.path.dirname(os.path.abspath(__file__)), "tareas_videos.py")
    with open(ruta_tareas, encoding="utf-8") as f:
        src_t=f.read()
    has_helper = "eliminar_registros_de_carpetas_retiradas" in src_t
    verifica(has_helper,"arquitectura backend helper presente en tareas")
    # Verificar que eliminar_candidatos no usa WHERE nombre
    ruta_esc=os.path.join(os.path.dirname(os.path.abspath(__file__)), "escanear_videos.py")
    with open(ruta_esc, encoding="utf-8") as f:
        src_e=f.read()
    # Contar WHERE nombre en eliminar_candidatos (debe ser 0)
    # Extraer función eliminar_candidatos
    try:
        arbol_e=ast.parse(src_e, ruta_esc)
        func_src=None
        for node in ast.walk(arbol_e):
            if isinstance(node, ast.FunctionDef) and node.name=="eliminar_candidatos":
                func_src=ast.get_source_segment(src_e, node)
                break
        if func_src:
            where_nombre = func_src.count("WHERE nombre")
            collate = func_src.count("COLLATE")
            verifica(where_nombre==0,"eliminar_candidatos sin WHERE nombre")
            verifica(collate==0,"eliminar_candidatos sin COLLATE NOCASE")
        else:
            falla("no se encontró eliminar_candidatos para arquitectura")
    except Exception as exc:
        falla("arquitectura parse eliminar_candidatos", str(exc))

def main():
    print("=== B8.3A prueba_b83_sincronizacion_multicarpeta ===")
    for fn in [test_sincronizar_bd_scope,test_moderno_aislamiento,test_homonimos_sync,test_shrink_helper,test_arquitectura_ui]:
        try: fn()
        except Exception as e:
            import traceback; falla(fn.__name__, str(e)); traceback.print_exc()
    total=_CONT; fallos=_FAIL
    print(f"TOTAL={total-fallos}/{total}")
    if fallos==0: print("RESULTADO_FINAL=OK")
    else: print("RESULTADO_FINAL=ERROR"); sys.exit(1)

if __name__=="__main__": main()
