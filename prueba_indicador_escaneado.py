import ast
import os
import sys
import tempfile
import time
from unittest import mock

from PySide6.QtWidgets import QApplication

import arbol_navegacion
from arbol_navegacion import (
    ROL_ESTADO,
    ROL_RUTA,
    ArbolNavegacion,
    EstadoNodo,
)
from tareas_videos import conectar_bd
from visor_videos import VisorVideos


def _crear_raiz():
    raiz = tempfile.TemporaryDirectory()
    for carpeta in ["a", "b"]:
        os.makedirs(os.path.join(raiz.name, carpeta))
    os.makedirs(os.path.join(raiz.name, "a", "x"))
    return raiz


def _crear_bd():
    temp_db = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp_db.name, "catalogo.db")
    conn = conectar_bd(ruta_db)
    conn.commit()
    conn.close()
    return temp_db, ruta_db


def _hijo_por_texto(item, texto):
    for i in range(item.childCount()):
        hijo = item.child(i)
        if hijo.text(0) == texto:
            return hijo
    return None


def main():
    app = QApplication(sys.argv)
    resultados = []

    def registrar(nombre, ok):
        resultados.append((nombre, bool(ok)))
        print(f"{nombre}={'OK' if ok else 'FAIL'}")

    def esperar(predicado, intentos=800):
        for _ in range(intentos):
            QApplication.processEvents()
            if predicado():
                return True
            time.sleep(0.02)
        QApplication.processEvents()
        return predicado()

    # --- Parte A: enum de estados ---
    registrar(
        "enum_estados",
        [
            EstadoNodo.SIN_ESCANEAR,
            EstadoNodo.ESCANEADA,
            EstadoNodo.PARCIAL,
            EstadoNodo.CAMBIOS_PENDIENTES,
            EstadoNodo.ERROR,
        ]
        == [0, 1, 2, 3, 4],
    )

    # --- Parte B: indicadores del arbol (widget) ---
    raiz = _crear_raiz()
    with mock.patch.object(
        arbol_navegacion, "discos_disponibles", return_value=[raiz.name]
    ):
        arbol = ArbolNavegacion()
        disco = arbol.topLevelItem(0).child(0)
        arbol.expandItem(disco)
        QApplication.processEvents()
        a = _hijo_por_texto(disco, "a")
        ruta_a = os.path.join(raiz.name, "a")

        registrar(
            "sin_escaneada_estado",
            a.data(0, ROL_ESTADO) == int(EstadoNodo.SIN_ESCANEAR),
        )
        registrar("sin_escaneada_icono", a.icon(0).isNull())

        arbol.marcar_carpeta_escaneada(ruta_a)
        registrar(
            "escaneada_estado",
            a.data(0, ROL_ESTADO) == int(EstadoNodo.ESCANEADA),
        )
        registrar("escaneada_icono", not a.icon(0).isNull())
        registrar("estado_es_int", isinstance(a.data(0, ROL_ESTADO), int))

        arbol.setCurrentItem(a)
        QApplication.processEvents()
        arbol.expandItem(a)
        QApplication.processEvents()
        current_antes = arbol.currentItem()
        expandido_antes = a.isExpanded()
        carpeta_antes = arbol.carpeta_actual()
        hijos_antes = [a.child(i).data(0, ROL_RUTA) for i in range(a.childCount())]
        arbol.marcar_carpeta_escaneada(ruta_a)
        registrar("solo_visual_seleccion", arbol.currentItem() is current_antes)
        registrar("solo_visual_expansion", a.isExpanded() == expandido_antes)
        registrar(
            "solo_visual_carpeta_actual", arbol.carpeta_actual() == carpeta_antes
        )
        registrar(
            "solo_visual_hijos",
            [a.child(i).data(0, ROL_RUTA) for i in range(a.childCount())]
            == hijos_antes,
        )

        ruta_x = os.path.join(ruta_a, "x")
        arbol.marcar_carpeta_escaneada(ruta_x)
        arbol.expandItem(a)
        QApplication.processEvents()
        x = _hijo_por_texto(a, "x")
        registrar(
            "carga_diferida_escaneada",
            x is not None
            and x.data(0, ROL_ESTADO) == int(EstadoNodo.ESCANEADA),
        )

    # --- Parte C: el arbol no conoce SQLite ---
    fuente = open(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "arbol_navegacion.py"),
        encoding="utf-8",
    ).read()
    arbol_ast = ast.parse(fuente)
    refs_sqlite = [
        n
        for n in ast.walk(arbol_ast)
        if (
            isinstance(n, ast.Import)
            and any(a.name == "sqlite3" for a in n.names)
        )
        or (
            isinstance(n, ast.ImportFrom)
            and any(a.name == "sqlite3" for a in n.names)
        )
        or (isinstance(n, ast.Name) and n.id == "sqlite3")
    ]
    registrar("arbol_sin_sqlite", not refs_sqlite)
    registrar("arbol_sin_conectar_bd", "conectar_bd" not in fuente)

    # --- Parte D: flujo real (escaneo -> indicador) ---
    carpeta_videos = tempfile.TemporaryDirectory()
    for nombre in ["peli_a.mp4", "serie_b.mkv"]:
        with open(os.path.join(carpeta_videos.name, nombre), "w") as f:
            f.write("x")
    temp_db, ruta_db = _crear_bd()
    temp_config = tempfile.TemporaryDirectory()
    ruta_config = os.path.join(temp_config.name, "configuracion.json")
    with mock.patch.object(
        arbol_navegacion, "discos_disponibles", return_value=[carpeta_videos.name]
    ):
        v = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        v.resize(900, 600)
        v.show()
        esperar(lambda w=v: w._carga_completada and w.gestor.hilo is None)
        arbol_v = v.findChild(ArbolNavegacion)
        disco_v = arbol_v.topLevelItem(0).child(0)
        arbol_v.setCurrentItem(disco_v)
        esperar(lambda w=v: w.resultado_sincronizacion is not None)
        registrar(
            "flujo_real_indicador",
            disco_v.data(0, ROL_ESTADO) == int(EstadoNodo.ESCANEADA),
        )
        v.close()
        v.gestor.cerrar()

    raiz.cleanup()
    carpeta_videos.cleanup()
    temp_db.cleanup()
    temp_config.cleanup()

    total_ok = sum(1 for _, ok in resultados if ok)
    print(f"TOTAL={total_ok}/{len(resultados)}")
    print(f"RESULTADO_FINAL={'OK' if total_ok == len(resultados) else 'FAIL'}")
    sys.exit(0)


if __name__ == "__main__":
    main()
