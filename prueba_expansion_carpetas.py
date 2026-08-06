import os
import sys
import tempfile
import time
from unittest import mock

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractItemView, QApplication

import arbol_navegacion
import visor_videos
from arbol_navegacion import (
    ROL_CARGADO,
    ROL_PLACEHOLDER,
    ROL_RUTA,
    TEXTO_RAIZ,
    ArbolNavegacion,
    carpetas_de,
)
from tareas_videos import conectar_bd, guardar_videos
from visor_videos import VisorVideos


def _crear_arbol_tmp():
    tmp = tempfile.TemporaryDirectory()
    for carpeta in ["a", "b", "c"]:
        os.makedirs(os.path.join(tmp.name, carpeta))
    os.makedirs(os.path.join(tmp.name, "b", "sub1"))
    os.makedirs(os.path.join(tmp.name, "b", "sub2"))
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

    # --- carpetas_de: logica pura ---
    tmp = _crear_arbol_tmp()
    registrar("carpetas_de_solo_directorios", carpetas_de(tmp.name) == ["a", "b", "c"])
    registrar("carpetas_de_vacio", carpetas_de(os.path.join(tmp.name, "c")) == [])
    registrar("carpetas_de_inexistente", carpetas_de(os.path.join(tmp.name, "no_existe")) == [])
    registrar("carpetas_de_archivo", carpetas_de(os.path.join(tmp.name, "archivo.txt")) == [])
    with mock.patch("os.scandir", side_effect=PermissionError):
        registrar("carpetas_de_permiso_denegado", carpetas_de(tmp.name) == [])

    tmp_orden = tempfile.TemporaryDirectory()
    for carpeta in ["zeta", "Beta", "alfa"]:
        os.makedirs(os.path.join(tmp_orden.name, carpeta))
    registrar("carpetas_de_orden_insensible", carpetas_de(tmp_orden.name) == ["alfa", "Beta", "zeta"])

    # --- widget: carga diferida ---
    with mock.patch.object(
        arbol_navegacion, "discos_disponibles", return_value=[tmp.name]
    ), mock.patch.object(
        arbol_navegacion, "carpetas_de", wraps=arbol_navegacion.carpetas_de
    ) as fake_carpetas:
        arbol = ArbolNavegacion()
        raiz = arbol.topLevelItem(0)
        disco = raiz.child(0)
        registrar("widget_disco_creado", disco is not None)
        registrar("widget_disco_ruta", disco.data(0, ROL_RUTA) == tmp.name)
        registrar("widget_carga_diferida_inicial", fake_carpetas.call_count == 0)
        registrar(
            "widget_disco_placeholder",
            disco.childCount() == 1 and disco.child(0).data(0, ROL_PLACEHOLDER),
        )
        registrar(
            "widget_disco_no_cargado",
            disco.data(0, ROL_CARGADO) != True,
        )

        arbol.expandItem(disco)
        QApplication.processEvents()
        nombres_disco = [disco.child(i).text(0) for i in range(disco.childCount())]
        registrar("widget_expansion_disco", nombres_disco == ["a", "b", "c"])
        registrar(
            "widget_expansion_un_solo_nivel",
            fake_carpetas.call_count == 1 and _hijo_por_texto(disco, "b").childCount() == 1,
        )
        registrar("widget_disco_cargado", disco.data(0, ROL_CARGADO) == True)

        b = _hijo_por_texto(disco, "b")
        arbol.expandItem(b)
        QApplication.processEvents()
        nombres_b = [b.child(i).text(0) for i in range(b.childCount())]
        registrar("widget_expansion_carpeta", nombres_b == ["sub1", "sub2"])
        registrar("widget_expansion_contador", fake_carpetas.call_count == 2)

        arbol.collapseItem(disco)
        arbol.expandItem(disco)
        QApplication.processEvents()
        nombres_disco2 = [disco.child(i).text(0) for i in range(disco.childCount())]
        registrar("widget_reexpansion_sin_duplicados", nombres_disco2 == ["a", "b", "c"])
        registrar("widget_reexpansion_sin_recarga", fake_carpetas.call_count == 2)

        c = _hijo_por_texto(disco, "c")
        arbol.expandItem(c)
        QApplication.processEvents()
        registrar("widget_carpeta_vacia_sin_hijos", c.childCount() == 0)
        registrar("widget_carpeta_vacia_cargada", c.data(0, ROL_CARGADO) == True)

        arbol.collapseItem(raiz)
        arbol.expandItem(raiz)
        QApplication.processEvents()
        registrar(
            "widget_raiz_no_recarga",
            raiz.childCount() == 1 and fake_carpetas.call_count == 3,
        )

        registrar(
            "widget_seleccion_simple",
            arbol.selectionMode() == QAbstractItemView.SingleSelection,
        )

    # --- widget: carpeta inaccesible (carpetas_de devuelve vacio / lanza) ---
    with mock.patch.object(
        arbol_navegacion, "discos_disponibles", return_value=[tmp.name]
    ), mock.patch.object(
        arbol_navegacion, "carpetas_de", return_value=[]
    ):
        arbol2 = ArbolNavegacion()
        disco2 = arbol2.topLevelItem(0).child(0)
        arbol2.expandItem(disco2)
        QApplication.processEvents()
        registrar("widget_inaccesible_sin_hijos", disco2.childCount() == 0)
        registrar("widget_inaccesible_cargado", disco2.data(0, ROL_CARGADO) == True)

    with mock.patch.object(
        arbol_navegacion, "discos_disponibles", return_value=[tmp.name]
    ), mock.patch.object(
        arbol_navegacion, "carpetas_de", side_effect=PermissionError
    ):
        arbol3 = ArbolNavegacion()
        disco3 = arbol3.topLevelItem(0).child(0)
        try:
            arbol3.expandItem(disco3)
            QApplication.processEvents()
            registro_ok = disco3.childCount() == 0 and disco3.data(0, ROL_CARGADO) == True
        except Exception as e:  # noqa: BLE001
            print(f"widget_inaccesible_excepcion={type(e).__name__}: {e}")
            registro_ok = False
        registrar("widget_inaccesible_sin_excepcion", registro_ok)

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

    with mock.patch.object(
        arbol_navegacion, "discos_disponibles", return_value=[tmp.name]
    ):
        temp_config = tempfile.TemporaryDirectory()
        ruta_config = os.path.join(temp_config.name, "configuracion.json")
        inicio = time.perf_counter()
        ventana = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        ventana.resize(900, 600)
        ventana.show()
        esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        fin = time.perf_counter()
        print(f"tiempo_apertura_seg={fin - inicio:.3f}")

        arbol_v = ventana.findChild(ArbolNavegacion)
        disco_v = arbol_v.topLevelItem(0).child(0)
        carpeta_antes = ventana.carpeta_seleccionada
        etiqueta_antes = ventana.etiqueta_carpeta.text()
        tarjetas_antes = len(ventana.tarjetas)
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
        arbol_v.expandItem(disco_v)
        QApplication.processEvents()
        b_v = _hijo_por_texto(disco_v, "b")
        arbol_v.expandItem(b_v)
        QApplication.processEvents()
        registrar("integracion_expansion_sin_duplicados", disco_v.childCount() == 3)
        registrar("integracion_carpeta_sin_cambio", ventana.carpeta_seleccionada == carpeta_antes)
        registrar("integracion_etiqueta_sin_cambio", ventana.etiqueta_carpeta.text() == etiqueta_antes)
        registrar("integracion_gestor_inactivo", not ventana.gestor.activo)
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
        registrar("integracion_sin_pendientes", pendientes_despues == pendientes_antes)
        registrar("integracion_tarjetas_intactas", len(ventana.tarjetas) == tarjetas_antes)

        with mock.patch.object(
            visor_videos.VisorVideos, "iniciar_escaneo"
        ) as espia_escaneo:
            rect = arbol_v.visualItemRect(b_v)
            QTest.mouseClick(
                arbol_v.viewport(), Qt.LeftButton, Qt.NoModifier, rect.center()
            )
            QApplication.processEvents()
            registrar(
                "integracion_clic_actualiza_carpeta",
                ventana.carpeta_seleccionada == os.path.join(tmp.name, "b"),
            )
            registrar(
                "integracion_clic_dispara_escaneo",
                espia_escaneo.call_count == 1,
            )
            registrar("integracion_clic_sin_escaneo_real", not ventana.gestor.activo)

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
        temp_config.cleanup()

    tmp_orden.cleanup()
    tmp.cleanup()
    temp_db.cleanup()

    total_ok = sum(1 for _, ok in resultados if ok)
    print(f"TOTAL={total_ok}/{len(resultados)}")
    print(f"RESULTADO_FINAL={'OK' if total_ok == len(resultados) else 'FAIL'}")
    sys.exit(0)


if __name__ == "__main__":
    main()
