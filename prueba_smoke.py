import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

import visor_videos
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QLabel

from rutas import ruta_carpeta_miniaturas
from tareas_videos import conectar_bd, guardar_videos
from visor_videos import VisorVideos, texto_resumen_sincronizacion


def main():
    app = QApplication(sys.argv)

    def esperar_smoke(predicado, intentos=400):
        for _ in range(intentos):
            QApplication.processEvents()
            if predicado():
                return True
            time.sleep(0.02)
        QApplication.processEvents()
        return predicado()

    temp_paginacion = tempfile.TemporaryDirectory()
    ruta_db_paginacion = os.path.join(temp_paginacion.name, "catalogo.db")
    conn = conectar_bd(ruta_db_paginacion)
    conn.commit()
    conn.close()
    guardar_videos(
        [
            {
                "nombre": f"v{i:03d}.mp4",
                "ruta": os.path.join(temp_paginacion.name, f"v{i:03d}.mp4"),
                "extension": ".mp4",
                "fecha_importacion": "2026-08-03T00:00:00",
            }
            for i in range(1, 151)
        ],
        ruta_db_paginacion,
    )
    ventana_paginacion = VisorVideos(ruta_db=ruta_db_paginacion)
    ventana_paginacion.resize(720, 540)
    ventana_paginacion.show()
    esperar_smoke(
        lambda v=ventana_paginacion: v._carga_completada and v.gestor.hilo is None
    )
    print(f"primera_pagina={len(ventana_paginacion.tarjetas)}")
    print(f"contador_primera_pagina={ventana_paginacion.contador.text()}")
    print(f"cargar_mas_habilitado={ventana_paginacion.boton_cargar_mas.isEnabled()}")
    ventana_paginacion.boton_cargar_mas.click()
    esperar_smoke(
        lambda v=ventana_paginacion: not v._pagina_pendiente
        and v.gestor.hilo is None
    )
    nombres_paginacion = [nombre for nombre, _ in ventana_paginacion.tarjetas]
    print(f"total_tras_cargar_mas={len(nombres_paginacion)}")
    print(
        f"duplicados_tras_cargar_mas="
        f"{len(nombres_paginacion) - len(set(nombres_paginacion))}"
    )
    print(
        f"primeras_conservadas="
        f"{nombres_paginacion[:100] == [f'v{i:03d}.mp4' for i in range(1, 101)]}"
    )
    print(f"contador_tras_cargar_mas={ventana_paginacion.contador.text()}")
    ventana_paginacion.close()
    ventana_paginacion.gestor.cerrar()
    temp_paginacion.cleanup()

    temp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp.name, "catalogo.db")
    conn = conectar_bd(ruta_db)
    conn.commit()
    conn.close()
    ventana = VisorVideos(ruta_db=ruta_db)
    ventana.resize(720, 540)
    ventana.show()

    print(f"carpeta_inicio={ventana.carpeta_seleccionada}")
    print(f"etiqueta_inicio={ventana.etiqueta_carpeta.text()}")
    print(f"estado_inicio={ventana.estado_carga.text()}")
    print(f"escanear_boton_inicio={ventana.boton_escanear.isEnabled()}")
    print(f"estado_escaneo_inicio={ventana.estado_escaneo.text()}")

    original_dialogo = QFileDialog.getExistingDirectory
    temp_carpeta = tempfile.TemporaryDirectory()
    try:
        for nombre in ["peli.mp4", "serie.mkv", "clip.avi", "doc.txt", "nota.log"]:
            Path(os.path.join(temp_carpeta.name, nombre)).write_text(
                "contenido", encoding="utf-8"
            )

        QFileDialog.getExistingDirectory = lambda *args, **kwargs: temp_carpeta.name
        ventana.seleccionar_carpeta()
        print(f"carpeta_seleccion={ventana.carpeta_seleccionada}")
        print(f"etiqueta_seleccion={ventana.etiqueta_carpeta.text()}")
        print(f"escanear_boton_activo={ventana.boton_escanear.isEnabled()}")

        QFileDialog.getExistingDirectory = lambda *args, **kwargs: ""
        ventana.seleccionar_carpeta()
        print(f"carpeta_tras_cancelar={ventana.carpeta_seleccionada}")
        print(f"etiqueta_tras_cancelar={ventana.etiqueta_carpeta.text()}")
        print(f"escanear_boton_tras_cancelar={ventana.boton_escanear.isEnabled()}")

        espera_carga = {"intentos": 0}
        espera_escaneo = {"intentos": 0}

        def comprobar_escaneo():
            if (
                ventana.gestor.activo
                or ventana._escaneo_pendiente
                or ventana._tamanos_pendiente
                or ventana._ffprobe_pendiente
                or ventana._miniaturas_pendiente
                or ventana._guardado_pendiente
                or ventana._sincronizacion_pendiente
                or ventana._recarga_catalogo_pendiente
            ) and espera_escaneo["intentos"] < 200:
                espera_escaneo["intentos"] += 1
                QTimer.singleShot(25, comprobar_escaneo)
                return
            print(f"videos_detectados={ventana.videos_detectados}")
            print(f"estado_escaneo_final={ventana.estado_escaneo.text()}")
            print(f"escanear_boton_final={ventana.boton_escanear.isEnabled()}")
            print(f"guardado_total={ventana.registros_guardados}")
            if ventana.resultado_sincronizacion is not None:
                print(
                    "resumen_sincronizacion="
                    + texto_resumen_sincronizacion(
                        ventana.resultado_sincronizacion.get("resumen")
                    )
                )
            print(
                "tarjetas_finales="
                + str([nombre for nombre, _ in ventana.tarjetas])
            )
            ventana.busqueda.setText("real")

            def verificar_y_cerrar():
                visibles = ventana.tarjetas_visibles()
                print(f"visibles_filtro={visibles}")
                print(f"contador_final={ventana.contador.text()}")
                ventana.close()
                app.quit()

            QTimer.singleShot(1500, verificar_y_cerrar)

        def comprobar_carga():
            if (
                not ventana._carga_completada or ventana.gestor.activo
            ) and espera_carga["intentos"] < 100:
                espera_carga["intentos"] += 1
                QTimer.singleShot(100, comprobar_carga)
                return
            print(f"visibles_cargados={ventana.tarjetas_visibles()}")
            print(f"contador_cargado={ventana.contador.text()}")
            print(f"escanear_boton_habilitado={ventana.boton_escanear.isEnabled()}")
            ventana.boton_escanear.click()
            print(f"estado_escaneo_mientras={ventana.estado_escaneo.text()}")
            print(f"escanear_boton_mientras={ventana.boton_escanear.isEnabled()}")
            espera_escaneo["intentos"] = 0
            QTimer.singleShot(0, comprobar_escaneo)

        QTimer.singleShot(200, comprobar_carga)
        codigo = app.exec()
    finally:
        QFileDialog.getExistingDirectory = original_dialogo
        temp_carpeta.cleanup()
        temp.cleanup()

    carpeta_real = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "videos_prueba"
    )
    if os.path.isdir(carpeta_real):
        temp_previews = tempfile.TemporaryDirectory()
        ruta_db_previews = os.path.join(temp_previews.name, "catalogo.db")
        conn = conectar_bd(ruta_db_previews)
        conn.commit()
        conn.close()
        ventana_previews = VisorVideos(ruta_db=ruta_db_previews)
        ventana_previews.resize(900, 600)
        ventana_previews.show()
        esperar_smoke(
            lambda v=ventana_previews: v._carga_completada and v.gestor.hilo is None
        )
        dialogo_real = QFileDialog.getExistingDirectory
        QFileDialog.getExistingDirectory = lambda *a, **k: carpeta_real
        ventana_previews.seleccionar_carpeta()
        QFileDialog.getExistingDirectory = dialogo_real
        ventana_previews.boton_escanear.click()
        print(
            f"previews_escanear_boton={ventana_previews.boton_escanear.isEnabled()}"
        )

        pasos_previews = {"cadena": 0, "fin": 0}

        def comprobar_cadena_previews():
            if (
                ventana_previews.gestor.activo
                or ventana_previews._escaneo_pendiente
                or ventana_previews._tamanos_pendiente
                or ventana_previews._ffprobe_pendiente
                or ventana_previews._miniaturas_pendiente
                or ventana_previews._guardado_pendiente
                or ventana_previews._sincronizacion_pendiente
                or ventana_previews._recarga_catalogo_pendiente
            ) and pasos_previews["cadena"] < 600:
                pasos_previews["cadena"] += 1
                QTimer.singleShot(25, comprobar_cadena_previews)
                return
            print(
                "previews_estado_escaneo=" + ventana_previews.estado_escaneo.text()
            )
            QTimer.singleShot(0, comprobar_fin_previews)

        def comprobar_fin_previews():
            if (
                ventana_previews.gestor_previews.activo
                or ventana_previews._cola_previews
                or ventana_previews._timer_previews.isActive()
            ) and pasos_previews["fin"] < 900:
                pasos_previews["fin"] += 1
                QTimer.singleShot(25, comprobar_fin_previews)
                return
            archivos = []
            if os.path.isdir(ruta_carpeta_miniaturas()):
                archivos = sorted(
                    a for a in os.listdir(ruta_carpeta_miniaturas())
                    if "_preview_" in a
                )
            print("previews_archivos=" + str(archivos))
            pixmaps = 0
            for _, tarjeta in ventana_previews.tarjetas:
                pixmaps += sum(
                    1
                    for l in tarjeta.findChildren(QLabel)
                    if l.pixmap() is not None and not l.pixmap().isNull()
                )
            print("previews_pixmaps=" + str(pixmaps))
            print("previews_tarjetas=" + str(len(ventana_previews.tarjetas)))
            ventana_previews.close()
            app.quit()

        QTimer.singleShot(0, comprobar_cadena_previews)
        app.exec()
        temp_previews.cleanup()

    if os.path.isdir(carpeta_real):
        temp_doble = tempfile.TemporaryDirectory()
        ruta_db_doble = os.path.join(temp_doble.name, "catalogo.db")
        conn = conectar_bd(ruta_db_doble)
        conn.commit()
        conn.close()
        ventana_doble = VisorVideos(ruta_db=ruta_db_doble)
        ventana_doble.resize(900, 600)
        ventana_doble.show()
        esperar_smoke(
            lambda v=ventana_doble: v._carga_completada and v.gestor.hilo is None
        )
        dialogo_doble = QFileDialog.getExistingDirectory
        QFileDialog.getExistingDirectory = lambda *a, **k: carpeta_real
        ventana_doble.seleccionar_carpeta()
        QFileDialog.getExistingDirectory = dialogo_doble
        ventana_doble.boton_escanear.click()

        pasos_doble = {"cadena": 0}

        def comprobar_cadena_doble():
            if (
                ventana_doble.gestor.activo
                or ventana_doble._escaneo_pendiente
                or ventana_doble._tamanos_pendiente
                or ventana_doble._ffprobe_pendiente
                or ventana_doble._miniaturas_pendiente
                or ventana_doble._guardado_pendiente
                or ventana_doble._sincronizacion_pendiente
                or ventana_doble._recarga_catalogo_pendiente
            ) and pasos_doble["cadena"] < 600:
                pasos_doble["cadena"] += 1
                QTimer.singleShot(25, comprobar_cadena_doble)
                return
            QTimer.singleShot(0, comprobar_fin_doble)

        def comprobar_fin_doble():
            por_nombre = {
                nombre: tarjeta for nombre, tarjeta in ventana_doble.tarjetas
            }
            tarjeta = por_nombre.get("video_real.mp4")
            if tarjeta is None:
                print("abrir_error=sin tarjeta de video_real.mp4")
                ventana_doble.close()
                app.quit()
                return
            original_abrir = visor_videos.abrir_video_con_aplicacion_predeterminada
            datos_abrir = {}

            def capturar_abrir(nombre, carpeta):
                ruta = original_abrir(nombre, carpeta)
                datos_abrir["nombre"] = nombre
                datos_abrir["carpeta"] = carpeta
                datos_abrir["ruta"] = ruta
                return ruta

            visor_videos.abrir_video_con_aplicacion_predeterminada = capturar_abrir
            try:
                QTest.mouseDClick(tarjeta, Qt.LeftButton)
                QApplication.processEvents()
            finally:
                visor_videos.abrir_video_con_aplicacion_predeterminada = original_abrir
            print("abrir_nombre=" + str(datos_abrir.get("nombre")))
            print("abrir_ruta=" + str(datos_abrir.get("ruta")))
            print("abrir_mensaje=" + ventana_doble.mensaje_carpeta.text())
            print(
                "abrir_con_aplicacion="
                + str(
                    "ruta" in datos_abrir and datos_abrir["ruta"] is not None
                )
            )
            ventana_doble.close()
            app.quit()

        QTimer.singleShot(0, comprobar_cadena_doble)
        app.exec()
        temp_doble.cleanup()

    temp_config = tempfile.TemporaryDirectory()
    ruta_config = os.path.join(temp_config.name, "configuracion.json")
    ruta_db_persistencia = os.path.join(temp_config.name, "catalogo.db")
    conn = conectar_bd(ruta_db_persistencia)
    conn.commit()
    conn.close()
    carpeta_persistencia = tempfile.TemporaryDirectory()
    carpeta_elegida = os.path.join(carpeta_persistencia.name, "carpeta_elegida")
    os.makedirs(carpeta_elegida)
    ventana_persistencia = VisorVideos(
        ruta_db=ruta_db_persistencia, ruta_config=ruta_config
    )
    ventana_persistencia.show()
    esperar_smoke(
        lambda v=ventana_persistencia: v._carga_completada and v.gestor.hilo is None
    )
    print(f"persistencia_inicio={ventana_persistencia.carpeta_seleccionada}")
    dialogo_persistencia = QFileDialog.getExistingDirectory
    QFileDialog.getExistingDirectory = lambda *a, **k: carpeta_elegida
    ventana_persistencia.seleccionar_carpeta()
    QFileDialog.getExistingDirectory = dialogo_persistencia
    print(f"persistencia_guardada={ventana_persistencia.carpeta_seleccionada}")
    ventana_persistencia.close()
    ventana_persistencia.gestor.cerrar()

    ventana_restaurada = VisorVideos(
        ruta_db=ruta_db_persistencia, ruta_config=ruta_config
    )
    ventana_restaurada.show()
    esperar_smoke(
        lambda v=ventana_restaurada: v._carga_completada and v.gestor.hilo is None
    )
    print(f"persistencia_restaurada={ventana_restaurada.carpeta_seleccionada}")

    shutil.rmtree(carpeta_elegida, ignore_errors=True)
    ventana_sin_carpeta = VisorVideos(
        ruta_db=ruta_db_persistencia, ruta_config=ruta_config
    )
    ventana_sin_carpeta.show()
    esperar_smoke(
        lambda v=ventana_sin_carpeta: v._carga_completada and v.gestor.hilo is None
    )
    print(f"persistencia_sin_carpeta={ventana_sin_carpeta.carpeta_seleccionada}")
    ventana_restaurada.close()
    ventana_sin_carpeta.close()
    ventana_restaurada.gestor.cerrar()
    ventana_sin_carpeta.gestor.cerrar()
    carpeta_persistencia.cleanup()
    temp_config.cleanup()

    sys.exit(codigo)


if __name__ == "__main__":
    main()
