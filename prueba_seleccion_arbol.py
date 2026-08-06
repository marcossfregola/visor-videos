import os
import sys
import tempfile
import time
from unittest import mock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QApplication

import arbol_navegacion
import visor_videos
from arbol_navegacion import (
    ROL_PLACEHOLDER,
    ROL_RUTA,
    ArbolNavegacion,
)
from tareas_videos import conectar_bd, guardar_videos
from visor_videos import VisorVideos


def _crear_arbol_tmp():
    tmp = tempfile.TemporaryDirectory()
    os.makedirs(os.path.join(tmp.name, "a", "x", "y"))
    os.makedirs(os.path.join(tmp.name, "b"))
    os.makedirs(os.path.join(tmp.name, "c"))
    with open(os.path.join(tmp.name, "archivo.txt"), "w", encoding="utf-8") as f:
        f.write("x")
    return tmp


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

    def esperar(predicado, intentos=400):
        for _ in range(intentos):
            QApplication.processEvents()
            if predicado():
                return True
            time.sleep(0.02)
        QApplication.processEvents()
        return predicado()

    tmp = _crear_arbol_tmp()
    emitidas = []

    with mock.patch.object(
        arbol_navegacion, "discos_disponibles", return_value=[tmp.name]
    ):
        arbol = ArbolNavegacion()
        arbol.ruta_seleccionada.connect(lambda r: emitidas.append(r))
        raiz = arbol.topLevelItem(0)
        disco = raiz.child(0)

        registrar("seleccion_inicial_none", arbol.carpeta_actual() is None)
        registrar(
            "seleccion_modo_simple",
            arbol.selectionMode() == QAbstractItemView.SingleSelection,
        )

        arbol.setCurrentItem(disco)
        QApplication.processEvents()
        registrar("seleccion_disco_ruta", arbol.carpeta_actual() == tmp.name)
        registrar("seleccion_disco_visual", arbol.currentItem() is disco)
        registrar(
            "seleccion_disco_senal",
            bool(emitidas) and emitidas[-1] == tmp.name,
        )

        arbol.expandItem(disco)
        QApplication.processEvents()
        a = _hijo_por_texto(disco, "a")
        arbol.setCurrentItem(a)
        QApplication.processEvents()
        ruta_a = os.path.join(tmp.name, "a")
        registrar("seleccion_carpeta_ruta", arbol.carpeta_actual() == ruta_a)
        registrar("seleccion_carpeta_visual", arbol.currentItem() is a)
        registrar(
            "seleccion_carpeta_senal",
            bool(emitidas) and emitidas[-1] == ruta_a,
        )

        antes = arbol.carpeta_actual()
        n_emitidas = len(emitidas)
        arbol.setCurrentItem(raiz)
        QApplication.processEvents()
        registrar("seleccion_raiz_no_modifica", arbol.carpeta_actual() == antes)
        registrar("seleccion_raiz_sin_senal", len(emitidas) == n_emitidas)

        b = _hijo_por_texto(disco, "b")
        placeholder = None
        if b.childCount() == 1 and b.child(0).data(0, ROL_PLACEHOLDER):
            placeholder = b.child(0)
        if placeholder is not None:
            antes2 = arbol.carpeta_actual()
            n2 = len(emitidas)
            arbol.setCurrentItem(placeholder)
            QApplication.processEvents()
            registrar(
                "seleccion_placeholder_no_modifica",
                arbol.carpeta_actual() == antes2 and len(emitidas) == n2,
            )
        else:
            registrar("seleccion_placeholder_no_modifica", True)

        arbol.expandItem(a)
        QApplication.processEvents()
        x = _hijo_por_texto(a, "x")
        arbol.expandItem(x)
        QApplication.processEvents()
        y = _hijo_por_texto(x, "y")
        arbol.setCurrentItem(y)
        QApplication.processEvents()
        ruta_y = os.path.join(tmp.name, "a", "x", "y")
        registrar("seleccion_profunda", arbol.carpeta_actual() == ruta_y)

        n_emitidas3 = len(emitidas)
        arbol.collapseItem(a)
        QApplication.processEvents()
        registrar("seleccion_conservada_contraer", arbol.carpeta_actual() == ruta_y)
        registrar("seleccion_sin_emision_contraer", len(emitidas) == n_emitidas3)
        arbol.expandItem(a)
        QApplication.processEvents()
        registrar("seleccion_conservada_expandir", arbol.carpeta_actual() == ruta_y)
        registrar("seleccion_sin_emision_expandir", len(emitidas) == n_emitidas3)

        registrar(
            "senal_siempre_valida",
            all(isinstance(r, str) and r.startswith(tmp.name) for r in emitidas),
        )

    # --- integracion en VisorVideos ---
    temp_db = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp_db.name, "catalogo.db")
    conn = conectar_bd(ruta_db)
    conn.commit()
    conn.close()
    guardar_videos(
        [
            {
                "nombre": f"v{i:02d}.mp4",
                "ruta": os.path.join(temp_db.name, f"v{i:02d}.mp4"),
                "extension": ".mp4",
                "fecha_importacion": "2026-08-06T00:00:00",
            }
            for i in range(1, 6)
        ],
        ruta_db,
    )
    temp_config = tempfile.TemporaryDirectory()
    ruta_config = os.path.join(temp_config.name, "configuracion.json")

    with mock.patch.object(
        arbol_navegacion, "discos_disponibles", return_value=[tmp.name]
    ):
        ventana = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        ventana.resize(900, 600)
        ventana.show()
        esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)

        arbol_v = ventana.findChild(ArbolNavegacion)
        disco_v = arbol_v.topLevelItem(0).child(0)
        arbol_v.expandItem(disco_v)
        QApplication.processEvents()
        a_v = _hijo_por_texto(disco_v, "a")
        ruta_a_v = os.path.join(tmp.name, "a")

        antes_tarjetas = len(ventana.tarjetas)
        pendientes_antes = (
            ventana._escaneo_pendiente
            or ventana._tamanos_pendiente
            or ventana._ffprobe_pendiente
            or ventana._miniaturas_pendiente
            or ventana._guardado_pendiente
            or ventana._sincronizacion_pendiente
            or ventana._recarga_catalogo_pendiente
            or ventana._pagina_pendiente
        )

        with mock.patch.object(
            visor_videos.VisorVideos, "iniciar_escaneo"
        ) as espia_escaneo:
            arbol_v.setCurrentItem(a_v)
            QApplication.processEvents()
            registrar(
                "integracion_arbol_carpeta_actual",
                arbol_v.carpeta_actual() == ruta_a_v,
            )
            registrar(
                "integracion_visor_carpeta_actualizada",
                ventana.carpeta_seleccionada == ruta_a_v,
            )
            registrar(
                "integracion_etiqueta_actualizada",
                ventana.etiqueta_carpeta.text() == ruta_a_v,
            )
            registrar(
                "integracion_dispara_escaneo", espia_escaneo.call_count == 1
            )
            registrar("integracion_sin_escaneo_real", not ventana.gestor.activo)
            pendientes_despues = (
                ventana._escaneo_pendiente
                or ventana._tamanos_pendiente
                or ventana._ffprobe_pendiente
                or ventana._miniaturas_pendiente
                or ventana._guardado_pendiente
                or ventana._sincronizacion_pendiente
                or ventana._recarga_catalogo_pendiente
                or ventana._pagina_pendiente
            )
            registrar(
                "integracion_sin_pendientes",
                pendientes_despues == pendientes_antes,
            )
            registrar(
                "integracion_tarjetas_intactas",
                len(ventana.tarjetas) == antes_tarjetas,
            )

            splitter = ventana.centralWidget()
            splitter.setSizes([300, 620])
            QApplication.processEvents()
            tamanos = list(splitter.sizes())
            registrar(
                "integracion_splitter_redimensionable",
                tamanos[0] > 220 and abs(tamanos[0] - 300) <= 1,
            )

        ventana.close()
        ventana.gestor.cerrar()

    tmp.cleanup()
    temp_db.cleanup()
    temp_config.cleanup()

    total_ok = sum(1 for _, ok in resultados if ok)
    print(f"TOTAL={total_ok}/{len(resultados)}")
    print(f"RESULTADO_FINAL={'OK' if total_ok == len(resultados) else 'FAIL'}")
    sys.exit(0)


if __name__ == "__main__":
    main()
