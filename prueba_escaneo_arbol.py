import os
import sys
import tempfile
import time
from unittest import mock

from PySide6.QtWidgets import QApplication, QFileDialog

import arbol_navegacion
import visor_videos
from arbol_navegacion import ArbolNavegacion
from configuracion import guardar_ultima_carpeta
from tareas_videos import conectar_bd
from visor_videos import VisorVideos


def _hijo_por_texto(item, texto):
    for i in range(item.childCount()):
        hijo = item.child(i)
        if hijo.text(0) == texto:
            return hijo
    return None


def _crear_bd():
    temp_db = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp_db.name, "catalogo.db")
    conn = conectar_bd(ruta_db)
    conn.commit()
    conn.close()
    return temp_db, ruta_db


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

    def sin_pipeline(v):
        return (
            not v.gestor.activo
            and not v._escaneo_pendiente
            and not v._tamanos_pendiente
            and not v._ffprobe_pendiente
            and not v._miniaturas_pendiente
            and not v._guardado_pendiente
            and not v._sincronizacion_pendiente
            and not v._recarga_catalogo_pendiente
        )

    tmp = tempfile.TemporaryDirectory()
    for carpeta in ["a", "b", "c"]:
        os.makedirs(os.path.join(tmp.name, carpeta))
    temp_db, ruta_db = _crear_bd()
    temp_config = tempfile.TemporaryDirectory()
    ruta_config = os.path.join(temp_config.name, "configuracion.json")

    # --- Parte 1: disparos con espi'a ---
    with mock.patch.object(
        arbol_navegacion, "discos_disponibles", return_value=[tmp.name]
    ), mock.patch.object(
        visor_videos.VisorVideos, "iniciar_escaneo"
    ) as espia:
        ventana = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        ventana.resize(900, 600)
        ventana.show()
        esperar(lambda v=ventana: v._carga_completada and v.gestor.hilo is None)
        arbol = ventana.findChild(ArbolNavegacion)
        disco = arbol.topLevelItem(0).child(0)
        arbol.expandItem(disco)
        QApplication.processEvents()
        a = _hijo_por_texto(disco, "a")
        b = _hijo_por_texto(disco, "b")

        arbol.setCurrentItem(a)
        QApplication.processEvents()
        registrar("arbol_dispara_escaneo", espia.call_count == 1)

        arbol.setCurrentItem(a)
        QApplication.processEvents()
        registrar("repetir_misma_sin_disparo", espia.call_count == 1)

        arbol.setCurrentItem(b)
        QApplication.processEvents()
        registrar("cambiar_carpeta_dispara", espia.call_count == 2)

        ventana.boton_escanear.click()
        QApplication.processEvents()
        registrar("boton_mismo_mecanismo", espia.call_count == 3)

        original = QFileDialog.getExistingDirectory
        ruta_c = os.path.join(tmp.name, "c")
        QFileDialog.getExistingDirectory = lambda *a, **k: ruta_c
        ventana.seleccionar_carpeta()
        QFileDialog.getExistingDirectory = original
        QApplication.processEvents()
        registrar("dialogo_un_disparo", espia.call_count == 4)

        ventana.close()
        ventana.gestor.cerrar()

    # --- Parte 2: restauracion inicial sin escaneo ---
    temp_config2 = tempfile.TemporaryDirectory()
    ruta_config2 = os.path.join(temp_config2.name, "configuracion.json")
    ruta_a = os.path.join(tmp.name, "a")
    guardar_ultima_carpeta(ruta_a, ruta_config2)
    with mock.patch.object(
        arbol_navegacion, "discos_disponibles", return_value=[tmp.name]
    ), mock.patch.object(
        visor_videos.VisorVideos, "iniciar_escaneo"
    ) as espia2:
        ventana2 = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config2)
        ventana2.resize(900, 600)
        ventana2.show()
        esperar(lambda v=ventana2: v._carga_completada and v.gestor.hilo is None)
        registrar("restaurar_sin_escaneo", espia2.call_count == 0)
        registrar("restaurar_carpeta", ventana2.carpeta_seleccionada == ruta_a)
        ventana2.close()
        ventana2.gestor.cerrar()

    # --- Parte 3: flujo real (el catalogo se actualiza; sin doble escaneo) ---
    carpeta_videos = tempfile.TemporaryDirectory()
    for nombre in ["peli_a.mp4", "serie_b.mkv"]:
        with open(os.path.join(carpeta_videos.name, nombre), "w") as f:
            f.write("x")
    temp_db2, ruta_db2 = _crear_bd()
    with mock.patch.object(
        arbol_navegacion, "discos_disponibles", return_value=[carpeta_videos.name]
    ):
        ventana3 = VisorVideos(ruta_db=ruta_db2)
        ventana3.resize(900, 600)
        ventana3.show()
        esperar(lambda v=ventana3: v._carga_completada and v.gestor.hilo is None)
        arbol3 = ventana3.findChild(ArbolNavegacion)
        disco3 = arbol3.topLevelItem(0).child(0)
        arbol3.setCurrentItem(disco3)
        QApplication.processEvents()
        registrar(
            "flujo_real_escaneo_iniciado", ventana3.tarea_escaneo is not None
        )

        esperar(
            lambda v=ventana3: v.gestor.activo and v.tarea_escaneo is not None
        )
        tarea_original = ventana3.tarea_escaneo
        ventana3.iniciar_escaneo()
        QApplication.processEvents()
        registrar(
            "sin_doble_escaneo", ventana3.tarea_escaneo is tarea_original
        )

        esperar(lambda v=ventana3: v._carga_completada and sin_pipeline(v), 2000)
        nombres = [n for n, _ in ventana3.tarjetas]
        registrar(
            "catalogo_actualizado",
            "peli_a.mp4" in nombres and "serie_b.mkv" in nombres,
        )
        registrar(
            "flujo_real_sin_errores",
            not ventana3._escaneo_pendiente and not ventana3._sincronizacion_pendiente,
        )
        ventana3.close()
        ventana3.gestor.cerrar()

    tmp.cleanup()
    temp_db.cleanup()
    temp_config.cleanup()
    temp_config2.cleanup()
    carpeta_videos.cleanup()
    temp_db2.cleanup()

    total_ok = sum(1 for _, ok in resultados if ok)
    print(f"TOTAL={total_ok}/{len(resultados)}")
    print(f"RESULTADO_FINAL={'OK' if total_ok == len(resultados) else 'FAIL'}")
    sys.exit(0)


if __name__ == "__main__":
    main()
