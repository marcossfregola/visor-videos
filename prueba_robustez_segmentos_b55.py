"""Pruebas de robustez y ciclo de vida de segmentos (B5.5).

Endurecimiento sobre B5.4 (sin funciones nuevas): supervivencia ante
reescaneo, cambio de metadatos, video movido conservando nombre, orfandad
por eliminación, fallos de carga/creación/eliminación (estado consistente y
reintento), ráfagas, cambio rápido A→B→A, reconstrucción de tarjetas con
operaciones pendientes, cierre de la aplicación con tareas/timer pendientes
y ausencia de crash nativo reproducible atribuible a B5.4/B5.5.
"""

import contextlib
import inspect
import os
import py_compile
import shutil
import sys
import tempfile
import time

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QPointingDevice
from PySide6.QtWidgets import QApplication

import escanear_videos as escanear_mod
import tareas_videos as tv
import visor_videos
from escanear_videos import (
    conectar_bd,
    detectar_diferencias,
    eliminar_candidatos,
    eliminar_marcador,
    guardar_marcador,
    guardar_segmento,
    guardar_videos,
    listar_marcadores,
    listar_segmentos,
    listar_videos,
    preparar_plan_sincronizacion,
)
from visor_videos import Tarjeta, VisorVideos

_CONFIG_TEMPORAL = tempfile.TemporaryDirectory()
os.environ["VISOR_CONFIG"] = os.path.join(
    _CONFIG_TEMPORAL.name, "configuracion.json"
)


def _esperar(predicado, timeout_ms=10000, paso_ms=20):
    fin = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < fin:
        QApplication.processEvents()
        if predicado():
            return True
        time.sleep(paso_ms / 1000)
    QApplication.processEvents()
    return predicado()


def _limpiar(ventana):
    if ventana is None:
        return
    for gestor in (
        getattr(ventana, "gestor", None),
        getattr(ventana, "gestor_marcadores", None),
        getattr(ventana, "gestor_segmentos", None),
        getattr(ventana, "gestor_previews", None),
        getattr(ventana, "gestor_reproduccion", None),
        getattr(ventana, "gestor_exploracion", None),
    ):
        if gestor is not None:
            gestor.cerrar()
    ventana.deleteLater()
    for _ in range(5):
        QApplication.processEvents()


@contextlib.contextmanager
def _miniaturas_temporales():
    temp = tempfile.TemporaryDirectory()
    original_escaneo = escanear_mod.ruta_carpeta_miniaturas
    original_visor = visor_videos.ruta_carpeta_miniaturas
    escanear_mod.ruta_carpeta_miniaturas = lambda: temp.name
    visor_videos.ruta_carpeta_miniaturas = lambda: temp.name
    try:
        yield temp.name
    finally:
        escanear_mod.ruta_carpeta_miniaturas = original_escaneo
        visor_videos.ruta_carpeta_miniaturas = original_visor
        temp.cleanup()


def _registro(nombre, duracion=100.0):
    return {
        "nombre": nombre,
        "ruta": f"C:\\v\\{nombre}",
        "extension": os.path.splitext(nombre)[1].lower(),
        "fecha_importacion": "f",
        "duracion_segundos": duracion,
        "ancho": 640,
        "alto": 360,
        "codec_video": "h264",
        "cantidad_miniaturas": 3,
        "tamano_bytes": 1000,
    }


def _registro_ruta(nombre, ruta, duracion=100.0):
    tamano = os.path.getsize(ruta) if os.path.isfile(ruta) else 100
    return {
        "nombre": nombre,
        "ruta": ruta,
        "extension": os.path.splitext(nombre)[1].lower(),
        "fecha_importacion": "f",
        "duracion_segundos": duracion,
        "ancho": 640,
        "alto": 360,
        "codec_video": "h264",
        "cantidad_miniaturas": 0,
        "tamano_bytes": tamano,
        "mtime_ns": (
            int(os.path.getmtime(ruta) * 1e9) if os.path.isfile(ruta) else None
        ),
    }


def _crear_archivo(carpeta, nombre, tamano=64):
    ruta = os.path.join(carpeta, nombre)
    with open(ruta, "wb") as archivo:
        archivo.write(b"\x00" * tamano)
    return ruta


def _crear_db():
    temp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp.name, "catalogo.db")
    conn = conectar_bd(ruta_db)
    conn.close()
    return temp, ruta_db


def _crear_bd_con_videos(nombres):
    temp, ruta_db = _crear_db()
    guardar_videos([_registro(n) for n in nombres], ruta_db)
    return temp, ruta_db


def _video_id(ruta_db, nombre):
    for fila in listar_videos(ruta_db):
        if fila[0] == nombre:
            return fila[8]
    return None


def _abrir_ventana(ruta_db):
    ventana = VisorVideos(ruta_db=ruta_db)
    ventana.resize(900, 620)
    ventana.show()
    _esperar(
        lambda v=ventana: v._carga_completada and v.gestor.hilo is None
    )
    return ventana


def _enviar(widget, tipo, x, boton):
    evento = QMouseEvent(
        tipo,
        QPointF(float(x), 6.0),
        boton,
        boton,
        Qt.NoModifier,
        QPointingDevice.primaryPointingDevice(),
    )
    QApplication.sendEvent(widget, evento)


def _press(widget, x):
    _enviar(widget, QEvent.MouseButtonPress, x, Qt.LeftButton)


def _expandir(tarjeta):
    tarjeta.expandir()
    _esperar(lambda: tarjeta._franja.width() > 0)


def _drenar_segmentos(ventana, timeout_ms=15000):
    return _esperar(
        lambda: not ventana.gestor_segmentos.activo
        and not ventana._cola_segmentos,
        timeout_ms=timeout_ms,
    )


def _drenar_marcadores(ventana, timeout_ms=15000):
    return _esperar(
        lambda: not ventana.gestor_marcadores.activo
        and not ventana._cola_marcadores,
        timeout_ms=timeout_ms,
    )


def _activar_modo_segmento(tarjeta):
    tarjeta._boton_segmento.setChecked(True)


def _par(segmentos):
    return sorted(
        (s["inicio"], s["fin"], s["id"]) for s in segmentos
    )


def _par_db(ruta_db, video_id):
    return sorted(
        (inicio, fin, sid)
        for sid, inicio, fin, _color in listar_segmentos(video_id, ruta_db)
    )


def test_01():
    modulos = [
        "visor_videos.py",
        "prueba_robustez_segmentos_b55.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    """Reescaneo sin cambios conserva segmentos y no los duplica."""
    carpeta = tempfile.TemporaryDirectory()
    try:
        ruta = _crear_archivo(carpeta.name, "v1.mp4")
        temp, ruta_db = _crear_db()
        try:
            guardar_videos([_registro_ruta("v1.mp4", ruta)], ruta_db)
            id1 = _video_id(ruta_db, "v1.mp4")
            s = guardar_segmento(id1, 10.0, 20.0, ruta_db)
            # reescaneo del mismo registro (sin cambios)
            guardar_videos([_registro_ruta("v1.mp4", ruta)], ruta_db)
            id2 = _video_id(ruta_db, "v1.mp4")
            segs = listar_segmentos(id2, ruta_db)
            ok = (
                id1 == id2
                and segs == [(s[0], 10.0, 20.0, None)]
                and len(segs) == 1
            )
        finally:
            temp.cleanup()
        return ok, f"id={id1}->{id2} segs={segs}"
    finally:
        carpeta.cleanup()


def test_03():
    """Cambio de metadatos conserva identidad y segmentos (IDs intactos)."""
    carpeta = tempfile.TemporaryDirectory()
    try:
        ruta = _crear_archivo(carpeta.name, "v1.mp4", tamano=64)
        temp, ruta_db = _crear_db()
        try:
            guardar_videos([_registro_ruta("v1.mp4", ruta, duracion=100.0)], ruta_db)
            id1 = _video_id(ruta_db, "v1.mp4")
            s = guardar_segmento(id1, 5.0, 9.0, ruta_db)
            # se agranda el archivo y cambia la metadata (nuevo mtime/tamaño)
            with open(ruta, "wb") as archivo:
                archivo.write(b"\x00" * 4096)
            guardar_videos(
                [_registro_ruta("v1.mp4", ruta, duracion=200.0)], ruta_db
            )
            id2 = _video_id(ruta_db, "v1.mp4")
            segs = listar_segmentos(id2, ruta_db)
            ok = (
                id1 == id2
                and segs == [(s[0], 5.0, 9.0, None)]
                and segs[0][0] == s[0]
            )
        finally:
            temp.cleanup()
        return ok, f"id={id1}->{id2} segs={segs}"
    finally:
        carpeta.cleanup()


def test_04():
    """Video movido a otra carpeta conservando el nombre mantiene `video_id`."""
    carpeta_a = tempfile.TemporaryDirectory()
    carpeta_b = tempfile.TemporaryDirectory()
    try:
        ruta1 = _crear_archivo(carpeta_a.name, "v1.mp4")
        temp, ruta_db = _crear_db()
        try:
            guardar_videos([_registro_ruta("v1.mp4", ruta1)], ruta_db)
            id1 = _video_id(ruta_db, "v1.mp4")
            s = guardar_segmento(id1, 3.0, 7.0, ruta_db)
            # mover el archivo a otra carpeta manteniendo el nombre
            ruta2 = os.path.join(carpeta_b.name, "v1.mp4")
            shutil.move(ruta1, ruta2)
            # reescaneo de la nueva ubicación (upsert por nombre conserva id)
            guardar_videos([_registro_ruta("v1.mp4", ruta2)], ruta_db)
            id2 = _video_id(ruta_db, "v1.mp4")
            segs = listar_segmentos(id2, ruta_db)
            ok = id1 == id2 and segs == [(s[0], 3.0, 7.0, None)]
        finally:
            temp.cleanup()
        return ok, f"id={id1}->{id2} segs={segs}"
    finally:
        carpeta_a.cleanup()
        carpeta_b.cleanup()


def test_05():
    """Eliminación del video (sync) deja segmentos huérfanos en SQLite."""
    carpeta = tempfile.TemporaryDirectory()
    try:
        ruta = _crear_archivo(carpeta.name, "v1.mp4")
        temp, ruta_db = _crear_db()
        try:
            guardar_videos([_registro_ruta("v1.mp4", ruta)], ruta_db)
            id1 = _video_id(ruta_db, "v1.mp4")
            s = guardar_segmento(id1, 1.0, 2.0, ruta_db)
            os.remove(ruta)
            dif = detectar_diferencias(carpeta.name, ruta_db)
            plan = preparar_plan_sincronizacion(dif)
            eliminar_candidatos(plan, ruta_db)
            nombres = [fila[0] for fila in listar_videos(ruta_db)]
            orfanos = escanear_mod.listar_segmentos_de([id1], ruta_db)
            ok = (
                "v1.mp4" not in nombres
                and orfanos == [(s[0], id1, 1.0, 2.0, None)]
            )
        finally:
            temp.cleanup()
        return ok, f"videos={nombres} orfanos={orfanos}"
    finally:
        carpeta.cleanup()


def test_06():
    """Fallo al cargar: no crashea, no deja bandas falsas y permite reintento."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        original = tv.listar_segmentos
        reintento_ok = None
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]

            def _fallar(*args, **kwargs):
                raise RuntimeError("fallo de carga")

            tv.listar_segmentos = _fallar
            try:
                tarjeta.expandir()
                _drenar_segmentos(ventana)
            finally:
                tv.listar_segmentos = original
            ok_sin_crash = (
                tarjeta._segmentos == []
                and tarjeta._franja.segmentos() == []
                and tarjeta._extremo_segmento is None
            )
            ok_reintento_permitido = tarjeta._segmentos_cargados is False
            # reintento en una nueva expansión (ahora sin fallo)
            tarjeta.colapsar()
            tarjeta.expandir()
            reintento_ok = _esperar(
                lambda: tarjeta._segmentos_cargados
                and not ventana.gestor_segmentos.activo
                and not ventana._cola_segmentos,
                timeout_ms=15000,
            )
        finally:
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        return (
            ok_sin_crash and ok_reintento_permitido and bool(reintento_ok),
            f"sin_crash={ok_sin_crash} reintento_permitido={ok_reintento_permitido} reintento_ok={reintento_ok}",
        )


def test_07():
    """Fallo al crear: no queda segmento falso persistido y permite nueva operación."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            ventana = _abrir_ventana(ruta_db)
            original = tv.guardar_segmento
            nueva_ok = False
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                _expandir(tarjeta)
                _activar_modo_segmento(tarjeta)

                def _fallar(*args, **kwargs):
                    raise RuntimeError("fallo de creación")

                tv.guardar_segmento = _fallar
                try:
                    tarjeta._al_extremo_segmento_solicitado(20.0)
                    tarjeta._al_extremo_segmento_solicitado(40.0)
                    _drenar_segmentos(ventana)
                finally:
                    tv.guardar_segmento = original
                ok_sin_falso = (
                    tarjeta._segmentos == []
                    and tarjeta._franja.segmentos() == []
                    and listar_segmentos(id_a, ruta_db) == []
                )
                # nueva operación puede intentarse
                tarjeta._al_extremo_segmento_solicitado(50.0)
                tarjeta._al_extremo_segmento_solicitado(60.0)
                _drenar_segmentos(ventana)
                nueva_ok = (
                    len(tarjeta._segmentos) == 1
                    and len(listar_segmentos(id_a, ruta_db)) == 1
                )
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return (
                ok_sin_falso and nueva_ok,
                f"sin_falso={ok_sin_falso} nueva_ok={nueva_ok}",
            )
        finally:
            temp.cleanup()


def test_08():
    """Fallo al eliminar: el segmento reaparece (reconciliación) y la cola sigue."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            guardar_segmento(id_a, 10.0, 20.0, ruta_db)
            ventana = _abrir_ventana(ruta_db)
            original = tv.eliminar_segmento
            elimina_ok = False
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                _expandir(tarjeta)
                _esperar(
                    lambda: tarjeta._segmentos_cargados
                    and len(tarjeta._segmentos) == 1,
                    timeout_ms=15000,
                )
                seg = tarjeta._segmentos[0]

                def _fallar(*args, **kwargs):
                    raise RuntimeError("fallo de eliminación")

                tv.eliminar_segmento = _fallar
                try:
                    tarjeta._al_segmento_eliminar_solicitado(seg)
                    _drenar_segmentos(ventana)
                finally:
                    tv.eliminar_segmento = original
                ok_reaparece = _esperar(
                    lambda: len(tarjeta._segmentos) == 1
                    and not ventana.gestor_segmentos.activo
                    and not ventana._cola_segmentos,
                    timeout_ms=15000,
                )
                ok_db = len(listar_segmentos(id_a, ruta_db)) == 1
                # siguiente operación de eliminación puede ejecutarse
                if ok_reaparece and tarjeta._segmentos:
                    tarjeta._al_segmento_eliminar_solicitado(tarjeta._segmentos[0])
                    _drenar_segmentos(ventana)
                    elimina_ok = (
                        tarjeta._segmentos == []
                        and listar_segmentos(id_a, ruta_db) == []
                    )
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return (
                ok_reaparece and ok_db and elimina_ok,
                f"reaparece={ok_reaparece} db={ok_db} elimina_ok={elimina_ok}",
            )
        finally:
            temp.cleanup()


def test_09():
    """Ráfaga crear/crear/eliminar/crear/eliminar: RAM final == SQLite."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            ventana = _abrir_ventana(ruta_db)
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                _expandir(tarjeta)
                _activar_modo_segmento(tarjeta)
                # ráfaga sin esperar manualmente entre acciones
                a = _crear_directo(tarjeta, 10.0, 20.0)
                b = _crear_directo(tarjeta, 30.0, 40.0)
                tarjeta._al_segmento_eliminar_solicitado(a)
                c = _crear_directo(tarjeta, 50.0, 60.0)
                tarjeta._al_segmento_eliminar_solicitado(b)
                _drenar_segmentos(ventana)
                ram = _par(tarjeta._segmentos)
                db = _par_db(ruta_db, id_a)
                ok = ram == db and [s[0] for s in ram] == [50.0]
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return ok, f"ram={ram} db={db}"
        finally:
            temp.cleanup()


def _crear_directo(tarjeta, a, b):
    tarjeta._al_extremo_segmento_solicitado(a)
    tarjeta._al_extremo_segmento_solicitado(b)
    return tarjeta._segmentos[-1]


def test_10():
    """Cambio rápido A→B→A sin mezcla y sin A pendiente heredado."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4", "b.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            id_b = _video_id(ruta_db, "b.mp4")
            guardar_segmento(id_a, 1.0, 2.0, ruta_db)
            guardar_segmento(id_b, 8.0, 9.0, ruta_db)
            ventana = _abrir_ventana(ruta_db)
            try:
                ta = dict(ventana.tarjetas)["a.mp4"]
                tb = dict(ventana.tarjetas)["b.mp4"]
                _expandir(ta)
                _activar_modo_segmento(ta)
                _press(ta._franja, ta._franja.width() * 0.3)
                _esperar(lambda: ta._extremo_segmento is not None)
                # con A pendiente en ta, alternar rápidamente
                for _ in range(3):
                    tb.expandir()
                    ta.expandir()
                _esperar(
                    lambda: (
                        ta._segmentos_cargados
                        and tb._segmentos_cargados
                        and not ventana.gestor_segmentos.activo
                        and not ventana._cola_segmentos
                    ),
                    timeout_ms=20000,
                )
                ok = (
                    [s["inicio"] for s in ta._segmentos] == [1.0]
                    and [s["inicio"] for s in tb._segmentos] == [8.0]
                    and ta._extremo_segmento is None
                    and tb._extremo_segmento is None
                )
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return (
                ok,
                f"a={[s['inicio'] for s in ta._segmentos]} b={[s['inicio'] for s in tb._segmentos]}",
            )
        finally:
            temp.cleanup()


def test_11():
    """Reconstrucción de tarjetas durante una carga pendiente."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            guardar_segmento(id_a, 5.0, 9.0, ruta_db)
            ventana = _abrir_ventana(ruta_db)
            original = tv.listar_segmentos
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]

                def _lento(*args, **kwargs):
                    time.sleep(0.5)
                    return original(*args, **kwargs)

                tv.listar_segmentos = _lento
                try:
                    tarjeta.expandir()
                    # reconstruir antes de que termine la carga
                    filas = listar_videos(ruta_db)
                    ventana._reemplazar_tarjetas(filas)
                    _drenar_segmentos(ventana, timeout_ms=20000)
                finally:
                    tv.listar_segmentos = original
                nueva = dict(ventana.tarjetas)["a.mp4"]
                # el resultado de la carga anterior pertenece al card destruido;
                # el card nuevo carga el estado correcto al expandirse.
                _expandir(nueva)
                _esperar(
                    lambda: nueva._segmentos_cargados
                    and len(nueva._segmentos) == 1,
                    timeout_ms=15000,
                )
                ok = [s["inicio"] for s in nueva._segmentos] == [5.0]
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return ok, f"nueva={[s['inicio'] for s in nueva._segmentos]}"
        finally:
            temp.cleanup()


def test_12():
    """Reconstrucción de tarjetas durante una creación pendiente."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            ventana = _abrir_ventana(ruta_db)
            original = tv.guardar_segmento
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                _expandir(tarjeta)
                _activar_modo_segmento(tarjeta)

                def _lento(*args, **kwargs):
                    time.sleep(0.5)
                    return original(*args, **kwargs)

                tv.guardar_segmento = _lento
                try:
                    tarjeta._al_extremo_segmento_solicitado(20.0)
                    tarjeta._al_extremo_segmento_solicitado(40.0)
                    # reconstruir mientras la creación está en vuelo
                    filas = listar_videos(ruta_db)
                    ventana._reemplazar_tarjetas(filas)
                    _drenar_segmentos(ventana, timeout_ms=20000)
                finally:
                    tv.guardar_segmento = original
                db = listar_segmentos(id_a, ruta_db)
                nueva = dict(ventana.tarjetas)["a.mp4"]
                _expandir(nueva)
                _esperar(
                    lambda: nueva._segmentos_cargados
                    and len(nueva._segmentos) == 1,
                    timeout_ms=15000,
                )
                ok = len(db) == 1 and [s["inicio"] for s in nueva._segmentos] == [20.0]
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return ok, f"db={db} nueva={[s['inicio'] for s in nueva._segmentos]}"
        finally:
            temp.cleanup()


def test_13():
    """Reconstrucción de tarjetas durante una eliminación pendiente."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            guardar_segmento(id_a, 5.0, 9.0, ruta_db)
            ventana = _abrir_ventana(ruta_db)
            original = tv.eliminar_segmento
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                _expandir(tarjeta)
                _esperar(
                    lambda: tarjeta._segmentos_cargados
                    and len(tarjeta._segmentos) == 1,
                    timeout_ms=15000,
                )
                seg = tarjeta._segmentos[0]

                def _lento(*args, **kwargs):
                    time.sleep(0.5)
                    return original(*args, **kwargs)

                tv.eliminar_segmento = _lento
                try:
                    tarjeta._al_segmento_eliminar_solicitado(seg)
                    filas = listar_videos(ruta_db)
                    ventana._reemplazar_tarjetas(filas)
                    _drenar_segmentos(ventana, timeout_ms=20000)
                finally:
                    tv.eliminar_segmento = original
                db = listar_segmentos(id_a, ruta_db)
                ok = db == []
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return ok, f"db={db}"
        finally:
            temp.cleanup()


def test_14():
    """Cierre con A pendiente y timer de extremo activo (sin crash)."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            _activar_modo_segmento(tarjeta)
            _press(tarjeta._franja, tarjeta._franja.width() * 0.5)
            _esperar(lambda: tarjeta._extremo_segmento is not None)
            # cerrar con A pendiente (timer ya disparado)
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
            return True, "cerrado con A pendiente"
        finally:
            pass


def test_15():
    """Cierre con timer de extremo activo (sin esperar su disparo)."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            _activar_modo_segmento(tarjeta)
            _press(tarjeta._franja, tarjeta._franja.width() * 0.5)
            # cerrar inmediatamente: el timer aún está activo
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
            return True, "cerrado con timer activo"
        finally:
            pass


def test_16():
    """Cierre durante una carga de segmentos pendiente."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            guardar_segmento(_video_id(ruta_db, "a.mp4"), 1.0, 2.0, ruta_db)
            ventana = _abrir_ventana(ruta_db)
            original = tv.listar_segmentos

            def _lento(*args, **kwargs):
                time.sleep(1.0)
                return original(*args, **kwargs)

            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                tv.listar_segmentos = _lento
                tarjeta.expandir()
                ventana.close()
            finally:
                tv.listar_segmentos = original
                _limpiar(ventana)
                temp.cleanup()
            return True, "cerrado durante carga"
        finally:
            temp.cleanup()


def test_17():
    """Cierre durante creación/eliminación pendiente."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            guardar_segmento(id_a, 70.0, 80.0, ruta_db)
            ventana = _abrir_ventana(ruta_db)
            original_g = tv.guardar_segmento
            original_e = tv.eliminar_segmento

            def _lento(fn):
                def _envuelto(*args, **kwargs):
                    time.sleep(1.0)
                    return fn(*args, **kwargs)

                return _envuelto

            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                _expandir(tarjeta)
                _esperar(
                    lambda: tarjeta._segmentos_cargados
                    and len(tarjeta._segmentos) == 1,
                    timeout_ms=15000,
                )
                _activar_modo_segmento(tarjeta)
                tv.guardar_segmento = _lento(original_g)
                tarjeta._al_extremo_segmento_solicitado(20.0)
                tarjeta._al_extremo_segmento_solicitado(40.0)
                tv.eliminar_segmento = _lento(original_e)
                seg = tarjeta._segmentos[0]
                tarjeta._al_segmento_eliminar_solicitado(seg)
                ventana.close()
            finally:
                tv.guardar_segmento = original_g
                tv.eliminar_segmento = original_e
                _limpiar(ventana)
                temp.cleanup()
            return True, "cerrado durante crear/eliminar"
        finally:
            temp.cleanup()


def test_18():
    """Marcadores no se ven afectados por el endurecimiento de segmentos."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            guardar_marcador(id_a, 3.0, ruta_db)
            guardar_segmento(id_a, 5.0, 9.0, ruta_db)
            ventana = _abrir_ventana(ruta_db)
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                _expandir(tarjeta)
                _esperar(
                    lambda: tarjeta._marcadores_cargados
                    and tarjeta._segmentos_cargados
                    and len(tarjeta._marcadores) == 1
                    and len(tarjeta._segmentos) == 1,
                    timeout_ms=15000,
                )
                ok = (
                    tarjeta._marcadores[0]["tiempo"] == 3.0
                    and tarjeta._segmentos[0]["inicio"] == 5.0
                )
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return ok, f"marc={len(tarjeta._marcadores)} seg={len(tarjeta._segmentos)}"
        finally:
            temp.cleanup()


def test_19():
    """Cero cambios VLC: los handlers de segmentos no tocan el reproductor."""
    en_visor = [
        "_al_segmento_creado",
        "_al_segmento_eliminado",
        "_aplicar_segmentos_cargados",
        "_al_error_segmentos",
    ]
    en_tarjeta = [
        "_al_extremo_segmento_solicitado",
        "_al_segmento_eliminar_solicitado",
        "_al_toggle_segmento",
    ]
    ok = True
    detalles = []

    def _limpiar(fuente):
        return (
            "playlist_vlc" not in fuente
            and "subprocess" not in fuente
            and "generar_m3u" not in fuente
            and "Popen" not in fuente
            and "localizar_vlc" not in fuente
        )

    for nombre in en_visor:
        limpio = _limpiar(inspect.getsource(getattr(VisorVideos, nombre)))
        ok = ok and limpio
        detalles.append(f"{nombre}={limpio}")
    for nombre in en_tarjeta:
        limpio = _limpiar(inspect.getsource(getattr(Tarjeta, nombre)))
        ok = ok and limpio
        detalles.append(f"{nombre}={limpio}")
    return ok, " ".join(detalles)


def test_20():
    """Sin operación pesada nueva al operar segmentos (0 FFmpeg/FFprobe)."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        ventana = _abrir_ventana(ruta_db)
        llamadas = {"ffprobe": 0, "ffmpeg": 0}
        original_probe = escanear_mod.obtener_datos_ffprobe
        original_ffmpeg = escanear_mod.ffmpeg_disponible

        def _c_probe(*a, **k):
            llamadas["ffprobe"] += 1
            return original_probe(*a, **k)

        def _c_ffmpeg(*a, **k):
            llamadas["ffmpeg"] += 1
            return original_ffmpeg(*a, **k)

        escanear_mod.obtener_datos_ffprobe = _c_probe
        escanear_mod.ffmpeg_disponible = _c_ffmpeg
        try:
            tarjeta = dict(ventana.tarjetas)["a.mp4"]
            _expandir(tarjeta)
            _activar_modo_segmento(tarjeta)
            tarjeta._al_extremo_segmento_solicitado(20.0)
            tarjeta._al_extremo_segmento_solicitado(40.0)
            _drenar_segmentos(ventana)
        finally:
            escanear_mod.obtener_datos_ffprobe = original_probe
            escanear_mod.ffmpeg_disponible = original_ffmpeg
            ventana.close()
            _limpiar(ventana)
            temp.cleanup()
        ok = (
            llamadas["ffprobe"] == 0
            and llamadas["ffmpeg"] == 0
            and len(tarjeta._segmentos) == 1
        )
        return ok, f"llamadas={llamadas}"


def main():
    app = QApplication(sys.argv)
    QApplication.setDoubleClickInterval(100)
    pruebas = [
        test_01,
        test_02,
        test_03,
        test_04,
        test_05,
        test_06,
        test_07,
        test_08,
        test_09,
        test_10,
        test_11,
        test_12,
        test_13,
        test_14,
        test_15,
        test_16,
        test_17,
        test_18,
        test_19,
        test_20,
    ]
    resultados = []
    for i, fn in enumerate(pruebas, start=1):
        try:
            ok, detalle = fn()
        except Exception as exc:
            ok, detalle = False, f"excepcion: {type(exc).__name__}: {exc}"
        resultados.append((i, ok, detalle))
        print(f"P{i:02d} {'OK' if ok else 'FALLO'} - {detalle}")

    ok_total = all(ok for _, ok, _ in resultados)
    aprobadas = sum(1 for _, ok, _ in resultados if ok)
    print(f"TOTAL={aprobadas}/{len(pruebas)}")
    print(f"RESULTADO_FINAL={'OK' if ok_total else 'FALLO'}")
    return 0 if ok_total else 1


if __name__ == "__main__":
    sys.exit(main())
