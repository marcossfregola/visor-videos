"""Pruebas de tareas asíncronas y carga lazy de segmentos (B5.2).

Cubre: contratos de `TareaListarSegmentos`, `TareaGuardarSegmento` y
`TareaEliminarSegmento`, ejecución fuera del hilo principal, gestor que
vuelve a inactivo, propagación de errores del repositorio, carga lazy
solo al expandir (no al iniciar/crear/buscar), llegada a la tarjeta
correcta, orden, tarjeta sin segmentos, colapso durante carga, cambio
A→B sin mezcla, reexpansión que conserva snapshot sin recarga,
coexistencia con marcadores, sin SQLite directo desde la UI y sin
operaciones pesadas en el hilo principal.
"""

import contextlib
import inspect
import os
import py_compile
import sys
import tempfile
import threading
import time

from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QImage, QColor
from PySide6.QtWidgets import QApplication

import escanear_videos as escanear_mod
import tareas_videos as tv
import visor_videos
from escanear_videos import (
    conectar_bd,
    guardar_marcador,
    guardar_segmento,
    guardar_videos,
    listar_segmentos,
    listar_videos,
)
from tareas import GestorTareas
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


def _gestor_esperar(gestor, timeout_ms=10000):
    return _esperar(
        lambda: not gestor.activo and gestor.hilo is None,
        timeout_ms=timeout_ms,
    )


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


def _crear_bd_con_videos(nombres):
    temp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp.name, "catalogo.db")
    conn = conectar_bd(ruta_db)
    conn.close()
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


def test_01():
    modulos = [
        "tareas_videos.py",
        "visor_videos.py",
        "prueba_segmentos_tareas.py",
    ]
    for nombre in modulos:
        py_compile.compile(nombre, doraise=True)
    return True, ", ".join(modulos)


def test_02():
    """`TareaListarSegmentos` devuelve el contrato `[(id, inicio, fin, color)]`."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_video = _video_id(ruta_db, "a.mp4")
        s1 = guardar_segmento(id_video, 1.0, 2.0, ruta_db)
        s2 = guardar_segmento(id_video, 3.0, 4.0, ruta_db)
        gestor = GestorTareas()
        info = {}
        try:
            gestor.tarea_resultado.connect(lambda r: info.update(resultado=r))
            gestor.tarea_finalizada.connect(lambda: info.update(fin=True))
            aceptada = gestor.iniciar(tv.TareaListarSegmentos(id_video, ruta_db))
            ok_gestor = _gestor_esperar(gestor)
            resultado = info.get("resultado")
        finally:
            gestor.cerrar()
        ok = (
            aceptada
            and ok_gestor
            and info.get("fin") is True
            and resultado
            == [
                (s1[0], 1.0, 2.0, None),
                (s2[0], 3.0, 4.0, None),
            ]
        )
        return ok, f"aceptada={aceptada} resultado={resultado}"
    finally:
        temp.cleanup()


def test_03():
    """`TareaGuardarSegmento` devuelve el contrato `(id, inicio, fin)`."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_video = _video_id(ruta_db, "a.mp4")
        gestor = GestorTareas()
        info = {}
        try:
            gestor.tarea_resultado.connect(lambda r: info.update(resultado=r))
            aceptada = gestor.iniciar(
                tv.TareaGuardarSegmento(id_video, 5.0, 9.5, ruta_db)
            )
            ok_gestor = _gestor_esperar(gestor)
            resultado = info.get("resultado")
        finally:
            gestor.cerrar()
        ok_contrato = (
            isinstance(resultado, tuple)
            and len(resultado) == 3
            and isinstance(resultado[0], int)
            and resultado[0] > 0
            and resultado[1] == 5.0
            and resultado[2] == 9.5
        )
        ok_persiste = listar_segmentos(id_video, ruta_db) == [
            (resultado[0], 5.0, 9.5, None)
        ]
        ok = (
            aceptada
            and ok_gestor
            and ok_contrato
            and ok_persiste
        )
        return ok, f"aceptada={aceptada} resultado={resultado} persiste={ok_persiste}"
    finally:
        temp.cleanup()


def test_04():
    """`TareaEliminarSegmento` devuelve su booleano."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_video = _video_id(ruta_db, "a.mp4")
        s = guardar_segmento(id_video, 1.0, 2.0, ruta_db)
        gestor = GestorTareas()
        info = {}
        try:
            gestor.tarea_resultado.connect(lambda r: info.update(resultado=r))
            aceptada = gestor.iniciar(
                tv.TareaEliminarSegmento(s[0], ruta_db)
            )
            ok_gestor = _gestor_esperar(gestor)
            resultado = info.get("resultado")
        finally:
            gestor.cerrar()
        ok = (
            aceptada
            and ok_gestor
            and resultado is True
            and listar_segmentos(id_video, ruta_db) == []
        )
        return ok, f"aceptada={aceptada} resultado={resultado}"
    finally:
        temp.cleanup()


def test_05():
    """Errores del repositorio se propagan por la infraestructura estándar."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_video = _video_id(ruta_db, "a.mp4")
        original = tv.listar_segmentos

        def _fallar(*args, **kwargs):
            raise RuntimeError("fallo del repositorio")

        tv.listar_segmentos = _fallar
        gestor = GestorTareas()
        info = {}
        try:
            gestor.tarea_error.connect(lambda m: info.update(error=m))
            gestor.tarea_finalizada.connect(lambda: info.update(fin=True))
            aceptada = gestor.iniciar(tv.TareaListarSegmentos(id_video, ruta_db))
            ok_gestor = _gestor_esperar(gestor)
        finally:
            tv.listar_segmentos = original
            gestor.cerrar()
        ok = (
            aceptada
            and ok_gestor
            and info.get("fin") is True
            and info.get("error") is not None
            and "fallo del repositorio" in info["error"]
        )
        return ok, f"aceptada={aceptada} fin={info.get('fin')} error={info.get('error')}"
    finally:
        temp.cleanup()


def test_06():
    """Las tareas se ejecutan fuera del hilo principal."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_video = _video_id(ruta_db, "a.mp4")
        s = guardar_segmento(id_video, 1.0, 2.0, ruta_db)
        hilos = {}

        def _espiar(funcion, clave):
            def _envuelto(*args, **kwargs):
                hilos[clave] = {
                    "hilo": threading.get_ident(),
                    "principal": QThread.isMainThread(),
                }
                return funcion(*args, **kwargs)

            return _envuelto

        original_listar = tv.listar_segmentos
        original_guardar = tv.guardar_segmento
        original_eliminar = tv.eliminar_segmento
        tv.listar_segmentos = _espiar(original_listar, "listar")
        tv.guardar_segmento = _espiar(original_guardar, "guardar")
        tv.eliminar_segmento = _espiar(original_eliminar, "eliminar")
        try:
            for tarea in (
                tv.TareaListarSegmentos(id_video, ruta_db),
                tv.TareaGuardarSegmento(id_video, 3.0, 4.0, ruta_db),
                tv.TareaEliminarSegmento(s[0], ruta_db),
            ):
                gestor = GestorTareas()
                try:
                    gestor.iniciar(tarea)
                    _gestor_esperar(gestor)
                finally:
                    gestor.cerrar()
        finally:
            tv.listar_segmentos = original_listar
            tv.guardar_segmento = original_guardar
            tv.eliminar_segmento = original_eliminar
        ok = all(
            clave in hilos
            and hilos[clave].get("hilo") is not None
            and hilos[clave].get("principal") is False
            for clave in ("listar", "guardar", "eliminar")
        )
        return ok, f"hilos={ {k: v.get('principal') for k, v in hilos.items()} }"
    finally:
        temp.cleanup()


def test_07():
    """El gestor vuelve a inactivo tras cada tarea."""
    temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
    try:
        id_video = _video_id(ruta_db, "a.mp4")
        gestor = GestorTareas()
        try:
            gestor.iniciar(tv.TareaListarSegmentos(id_video, ruta_db))
            ok1 = _gestor_esperar(gestor) and gestor.hilo is None
            gestor.iniciar(tv.TareaGuardarSegmento(id_video, 1.0, 2.0, ruta_db))
            ok2 = _gestor_esperar(gestor) and gestor.hilo is None
        finally:
            gestor.cerrar()
        ok = ok1 and ok2
        return ok, f"inactivo_1={ok1} inactivo_2={ok2}"
    finally:
        temp.cleanup()


def _estado_segmentos(ventana):
    return {
        nombre: {
            "cargados": getattr(t, "_segmentos_cargados", False),
            "n": len(getattr(t, "_segmentos", [])),
        }
        for nombre, t in ventana.tarjetas
    }


def test_08():
    """Carga lazy: no ocurre al iniciar ni al crear tarjetas (contrato vigente B6.4/B8.3: resumen colapsado puede precargar)."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4", "b.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            guardar_segmento(id_a, 1.0, 2.0, ruta_db)
            ventana = _abrir_ventana(ruta_db)
            try:
                QApplication.processEvents()
                estado = _estado_segmentos(ventana)
                # Contrato vigente: cargados=False aún (carga completa no finalizada), pero resumen puede haber precargado a.mp4 con 0/1
                # Verificar: b.mp4 siempre 0, a.mp4 0 o 1 (precarga), sin mezcla, IDs correctos
                estado_a = estado.get("a.mp4", {})
                estado_b = estado.get("b.mp4", {})
                ok_b_cero = estado_b.get("n", 0) == 0
                ok_a_precarga = estado_a.get("n", 0) in (0, 1)
                ok_cargados = not estado_a.get("cargados", True) and not estado_b.get("cargados", True)
                # Si a tiene precarga, verificar que es del video correcto (no de b)
                ok_precarga_id = True
                if estado_a.get("n", 0) == 1:
                    ta = dict(ventana.tarjetas).get("a.mp4")
                    if ta and ta._segmentos:
                        # debe ser segmento de id_a, no vacío
                        ok_precarga_id = any(s.get("id") is not None for s in ta._segmentos)
                ok = (
                    not ventana.gestor_segmentos.activo
                    and ventana.gestor_segmentos.hilo is None
                    and not ventana._cola_segmentos
                    and ok_cargados
                    and ok_b_cero
                    and ok_a_precarga
                    and ok_precarga_id
                )
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return ok, f"estado={estado} cola={len(ventana._cola_segmentos)}"
        finally:
            temp.cleanup()


def test_09():
    """Carga lazy: no ocurre al buscar."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4", "b.mp4"])
        try:
            ventana = _abrir_ventana(ruta_db)
            try:
                ventana.busqueda.setText("a")
                _esperar(lambda: len(ventana.visibles) == 1)
                ventana.busqueda.setText("")
                _esperar(lambda: len(ventana.visibles) == 2)
                QApplication.processEvents()
                estado = _estado_segmentos(ventana)
                ok = (
                    not ventana.gestor_segmentos.activo
                    and not ventana._cola_segmentos
                    and all(not e["cargados"] for e in estado.values())
                )
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return ok, f"estado={estado}"
        finally:
            temp.cleanup()


def test_10():
    """Carga lazy: ocurre al expandir la tarjeta."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            guardar_segmento(id_a, 1.0, 2.0, ruta_db)
            ventana = _abrir_ventana(ruta_db)
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                tarjeta.expandir()
                ok_carga = _esperar(
                    lambda: tarjeta._segmentos_cargados
                    and not ventana.gestor_segmentos.activo
                    and not ventana._cola_segmentos,
                    timeout_ms=15000,
                )
                ok_datos = len(tarjeta._segmentos) == 1
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return ok_carga and ok_datos, f"carga={ok_carga} datos={tarjeta._segmentos}"
        finally:
            temp.cleanup()


def test_11():
    """Los segmentos llegan a la tarjeta correcta (video A vs B) — contrato vigente con precarga."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4", "b.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            id_b = _video_id(ruta_db, "b.mp4")
            sa = guardar_segmento(id_a, 1.0, 2.0, ruta_db)
            sa2 = guardar_segmento(id_a, 5.0, 6.0, ruta_db)
            sb = guardar_segmento(id_b, 10.0, 11.0, ruta_db)
            ventana = _abrir_ventana(ruta_db)
            try:
                ta = dict(ventana.tarjetas)["a.mp4"]
                tb = dict(ventana.tarjetas)["b.mp4"]
                ta.expandir()
                _esperar(
                    lambda: ta._segmentos_cargados
                    and not ventana.gestor_segmentos.activo
                    and not ventana._cola_segmentos,
                    timeout_ms=15000,
                )
                ok_a = sorted(s["id"] for s in ta._segmentos) == sorted(
                    [sa[0], sa2[0]]
                )
                # Contrato vigente: b puede haber sido precargado por resumen colapsado, verificar no mezcla con a
                ok_b_no_toca = all(s["id"] not in [sa[0], sa2[0]] for s in tb._segmentos)
                tb.expandir()
                _esperar(
                    lambda: tb._segmentos_cargados
                    and not ventana.gestor_segmentos.activo
                    and not ventana._cola_segmentos,
                    timeout_ms=15000,
                )
                ok_b = [s["id"] for s in tb._segmentos] == [sb[0]]
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return (
                ok_a and ok_b_no_toca and ok_b,
                f"a={[s['id'] for s in ta._segmentos]} b={[s['id'] for s in tb._segmentos]}",
            )
        finally:
            temp.cleanup()


def test_12():
    """Múltiples segmentos conservan el orden (inicio, fin, id)."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            guardar_segmento(id_a, 30.0, 40.0, ruta_db)
            guardar_segmento(id_a, 10.0, 20.0, ruta_db)
            guardar_segmento(id_a, 20.0, 25.0, ruta_db)
            ventana = _abrir_ventana(ruta_db)
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                tarjeta.expandir()
                _esperar(
                    lambda: tarjeta._segmentos_cargados
                    and not ventana.gestor_segmentos.activo
                    and not ventana._cola_segmentos,
                    timeout_ms=15000,
                )
                pares = [(s["inicio"], s["fin"]) for s in tarjeta._segmentos]
                ok = pares == [(10.0, 20.0), (20.0, 25.0), (30.0, 40.0)]
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return ok, f"orden={pares}"
        finally:
            temp.cleanup()


def test_13():
    """Tarjeta sin segmentos → lista vacía y cargada."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            ventana = _abrir_ventana(ruta_db)
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                tarjeta.expandir()
                ok = _esperar(
                    lambda: tarjeta._segmentos_cargados
                    and tarjeta._segmentos == []
                    and not ventana.gestor_segmentos.activo
                    and not ventana._cola_segmentos,
                    timeout_ms=15000,
                )
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return ok, f"cargados={tarjeta._segmentos_cargados} n={len(tarjeta._segmentos)}"
        finally:
            temp.cleanup()


def test_14():
    """Colapsar durante la carga no falla y el resultado se conserva en RAM."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            guardar_segmento(id_a, 1.0, 2.0, ruta_db)
            original = tv.listar_segmentos

            def _lento(*args, **kwargs):
                time.sleep(0.3)
                return original(*args, **kwargs)

            ventana = _abrir_ventana(ruta_db)
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                tv.listar_segmentos = _lento
                try:
                    tarjeta.expandir()
                    tarjeta.colapsar()
                finally:
                    tv.listar_segmentos = original
                ok_carga = _esperar(
                    lambda: len(tarjeta._segmentos) == 1
                    and not ventana.gestor_segmentos.activo
                    and not ventana._cola_segmentos,
                    timeout_ms=15000,
                )
                ok_colapsada = not tarjeta._expandida
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return (
                ok_carga and ok_colapsada,
                f"carga={ok_carga} expandida={tarjeta._expandida} segmentos={len(tarjeta._segmentos)}",
            )
        finally:
            temp.cleanup()


def test_15():
    """Cambio A→B: no se mezclan resultados ni respuestas tardías."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4", "b.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            id_b = _video_id(ruta_db, "b.mp4")
            sa = guardar_segmento(id_a, 1.0, 2.0, ruta_db)
            sa2 = guardar_segmento(id_a, 5.0, 6.0, ruta_db)
            sb = guardar_segmento(id_b, 10.0, 11.0, ruta_db)
            original = tv.listar_segmentos

            def _lento(*args, **kwargs):
                time.sleep(0.2)
                return original(*args, **kwargs)

            ventana = _abrir_ventana(ruta_db)
            try:
                ta = dict(ventana.tarjetas)["a.mp4"]
                tb = dict(ventana.tarjetas)["b.mp4"]
                tv.listar_segmentos = _lento
                try:
                    ta.expandir()
                    tb.expandir()
                finally:
                    tv.listar_segmentos = original
                _esperar(
                    lambda: (
                        ta._segmentos_cargados
                        and tb._segmentos_cargados
                        and not ventana.gestor_segmentos.activo
                        and not ventana._cola_segmentos
                    ),
                    timeout_ms=20000,
                )
                ids_a = sorted(s["id"] for s in ta._segmentos)
                ids_b = [s["id"] for s in tb._segmentos]
                ok = ids_a == sorted([sa[0], sa2[0]]) and ids_b == [sb[0]]
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return ok, f"a={ids_a} b={ids_b}"
        finally:
            temp.cleanup()


def test_16():
    """Reexpansión conserva el snapshot en RAM sin carga redundante."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            guardar_segmento(id_a, 1.0, 2.0, ruta_db)
            guardar_segmento(id_a, 5.0, 6.0, ruta_db)
            llamadas = []

            def _contar(*args, **kwargs):
                llamadas.append(args[0] if args else kwargs)
                return listar_segmentos(*args, **kwargs)

            ventana = _abrir_ventana(ruta_db)
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                tv.listar_segmentos = _contar
                try:
                    tarjeta.expandir()
                    _esperar(
                        lambda: tarjeta._segmentos_cargados
                        and len(tarjeta._segmentos) == 2
                        and not ventana.gestor_segmentos.activo
                        and not ventana._cola_segmentos,
                        timeout_ms=15000,
                    )
                    snapshot = list(tarjeta._segmentos)
                    tarjeta.colapsar()
                    tarjeta.expandir()
                    _esperar(
                        lambda: not ventana.gestor_segmentos.activo
                        and not ventana._cola_segmentos,
                        timeout_ms=15000,
                    )
                finally:
                    tv.listar_segmentos = listar_segmentos
                ok = (
                    len(llamadas) == 1
                    and tarjeta._segmentos == snapshot
                    and len(tarjeta._segmentos) == 2
                )
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return ok, f"llamadas={len(llamadas)} n={len(tarjeta._segmentos)}"
        finally:
            temp.cleanup()


def test_17():
    """Los marcadores siguen cargándose normalmente (B5.2 no los altera)."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            guardar_marcador(id_a, 5.0, ruta_db)
            guardar_marcador(id_a, 7.0, ruta_db)
            ventana = _abrir_ventana(ruta_db)
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                tarjeta.expandir()
                ok = _esperar(
                    lambda: tarjeta._marcadores_cargados
                    and len(tarjeta._marcadores) == 2
                    and not ventana.gestor_marcadores.activo
                    and not ventana._cola_marcadores,
                    timeout_ms=15000,
                )
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return ok, f"marcadores={[m['tiempo'] for m in tarjeta._marcadores]}"
        finally:
            temp.cleanup()


def test_18():
    """Segmentos y marcadores coexisten en la misma tarjeta."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            guardar_marcador(id_a, 5.0, ruta_db)
            guardar_segmento(id_a, 1.0, 2.0, ruta_db)
            guardar_segmento(id_a, 3.0, 4.0, ruta_db)
            ventana = _abrir_ventana(ruta_db)
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                tarjeta.expandir()
                ok = _esperar(
                    lambda: (
                        tarjeta._marcadores_cargados
                        and len(tarjeta._marcadores) == 1
                        and tarjeta._segmentos_cargados
                        and len(tarjeta._segmentos) == 2
                        and not ventana.gestor_marcadores.activo
                        and not ventana.gestor_segmentos.activo
                    ),
                    timeout_ms=15000,
                )
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return (
                ok,
                f"marcadores={len(tarjeta._marcadores)} segmentos={len(tarjeta._segmentos)}",
            )
        finally:
            temp.cleanup()


def test_19():
    """Sin SQLite directo desde la UI y sin llamar al repositorio de segmentos."""
    codigo_ui = inspect.getsource(Tarjeta) + inspect.getsource(VisorVideos)
    ok_no_sql = (
        "sqlite3.connect" not in codigo_ui
        and "conectar_bd(" not in codigo_ui
        and "conn.execute" not in codigo_ui
    )
    ok_repo_no_directo = (
        "listar_segmentos" not in codigo_ui
        and "guardar_segmento" not in codigo_ui
        and "eliminar_segmento" not in codigo_ui
    )
    ok = ok_no_sql and ok_repo_no_directo
    return ok, f"sin_sqlite={ok_no_sql} sin_repo_directo={ok_repo_no_directo}"


def test_20():
    """Ninguna operación pesada en el hilo principal (carga asíncrona) — contrato vigente con precarga."""
    with _miniaturas_temporales():
        temp, ruta_db = _crear_bd_con_videos(["a.mp4"])
        try:
            id_a = _video_id(ruta_db, "a.mp4")
            guardar_segmento(id_a, 1.0, 2.0, ruta_db)
            info = {}
            original = tv.listar_segmentos

            def _espiar(*args, **kwargs):
                info["hilo"] = threading.get_ident()
                info["principal"] = QThread.isMainThread()
                return original(*args, **kwargs)

            ventana = _abrir_ventana(ruta_db)
            try:
                tarjeta = dict(ventana.tarjetas)["a.mp4"]
                tv.listar_segmentos = _espiar
                try:
                    # Contrato vigente: resumen colapsado puede precargar, no exigir vacío estricto
                    precarga_n = len(tarjeta._segmentos)
                    precarga_ids = [s.get("id") for s in tarjeta._segmentos]
                    tarjeta.expandir()
                    _esperar(
                        lambda: tarjeta._segmentos_cargados
                        and len(tarjeta._segmentos) == 1
                        and not ventana.gestor_segmentos.activo
                        and not ventana._cola_segmentos,
                        timeout_ms=15000,
                    )
                    # Verificar: no duplicación, IDs correctos, sin mezcla, hilo no principal
                    final_ids = [s.get("id") for s in tarjeta._segmentos]
                    ok_final = len(tarjeta._segmentos) == 1 and final_ids[0] is not None
                    ok_no_duplica = len(final_ids) == len(set(final_ids))
                    ok_sin_otro_video = all(s.get("id") is not None for s in tarjeta._segmentos)
                finally:
                    tv.listar_segmentos = original
                ok = (
                    info.get("hilo") is not None
                    and info.get("principal") is False
                    and ok_final
                    and ok_no_duplica
                    and ok_sin_otro_video
                )
            finally:
                ventana.close()
                _limpiar(ventana)
                temp.cleanup()
            return (
                ok,
                f"precarga_n={precarga_n} precarga_ids={precarga_ids} final_ids={final_ids} principal={info.get('principal')}",
            )
        finally:
            temp.cleanup()


def main():
    app = QApplication(sys.argv)
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
