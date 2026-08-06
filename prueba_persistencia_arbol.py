import os
import shutil
import sys
import tempfile
import time
from unittest import mock

from PySide6.QtWidgets import QApplication, QFileDialog

import arbol_navegacion
import visor_videos
from arbol_navegacion import ROL_CARGADO, ROL_PLACEHOLDER, ArbolNavegacion
from configuracion import guardar_ultima_carpeta, obtener_ultima_carpeta
from tareas_videos import conectar_bd, guardar_videos
from visor_videos import MENSAJE_SIN_CARPETA, VisorVideos

MENSAJE_RUTA_INVALIDA = "La ruta no es válida o no es una carpeta"


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


def _preparar_bd():
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
    return temp_db, ruta_db


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
    ruta_y = os.path.join(tmp.name, "a", "x", "y")
    temp_db, ruta_db = _preparar_bd()
    temp_config = tempfile.TemporaryDirectory()
    ruta_config = os.path.join(temp_config.name, "configuracion.json")

    # --- Fase A: persistencia y escritura unica ---
    with mock.patch.object(
        arbol_navegacion, "discos_disponibles", return_value=[tmp.name]
    ), mock.patch.object(
        visor_videos, "guardar_ultima_carpeta", wraps=visor_videos.guardar_ultima_carpeta
    ) as escribir:
        ventana1 = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        ventana1.resize(900, 600)
        ventana1.show()
        esperar(lambda v=ventana1: v._carga_completada and v.gestor.hilo is None)

        arbol1 = ventana1.findChild(ArbolNavegacion)
        disco1 = arbol1.topLevelItem(0).child(0)
        arbol1.expandItem(disco1)
        QApplication.processEvents()
        a1 = _hijo_por_texto(disco1, "a")
        arbol1.expandItem(a1)
        QApplication.processEvents()
        x1 = _hijo_por_texto(a1, "x")
        arbol1.expandItem(x1)
        QApplication.processEvents()
        y1 = _hijo_por_texto(x1, "y")
        arbol1.setCurrentItem(y1)
        QApplication.processEvents()

        registrar("persistencia_carpeta", obtener_ultima_carpeta(ruta_config) == ruta_y)
        registrar("persistencia_una_escritura", escribir.call_count == 1)

        ventana1._al_carpeta_actual_arbol(ruta_y)
        registrar("persistencia_sin_reescritura", escribir.call_count == 1)

        ventana1.close()
        ventana1.gestor.cerrar()

    # --- Fase B: restauracion tras reinicio ---
    with mock.patch.object(
        arbol_navegacion, "discos_disponibles", return_value=[tmp.name]
    ):
        inicio = time.perf_counter()
        ventana2 = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config)
        ventana2.resize(900, 600)
        ventana2.show()
        esperar(lambda v=ventana2: v._carga_completada and v.gestor.hilo is None)
        fin = time.perf_counter()
        print(f"tiempo_restauracion_seg={fin - inicio:.3f}")

        arbol2 = ventana2.findChild(ArbolNavegacion)
        disco2 = arbol2.topLevelItem(0).child(0)
        a2 = _hijo_por_texto(disco2, "a")
        x2 = _hijo_por_texto(a2, "x")
        y2 = _hijo_por_texto(x2, "y")

        registrar("restauracion_carpeta", ventana2.carpeta_seleccionada == ruta_y)
        registrar("restauracion_etiqueta", ventana2.etiqueta_carpeta.text() == ruta_y)
        registrar(
            "restauracion_arbol_sincronizado",
            arbol2.carpeta_actual() == ruta_y and arbol2.currentItem() is y2,
        )
        registrar(
            "restauracion_rama_expandida",
            disco2.isExpanded() and a2.isExpanded() and x2.isExpanded(),
        )
        registrar(
            "restauracion_solo_rama_necesaria",
            a2.data(0, ROL_CARGADO) == True
            and x2.data(0, ROL_CARGADO) == True
            and _hijo_por_texto(disco2, "b").childCount() == 1
            and _hijo_por_texto(disco2, "b").child(0).data(0, ROL_PLACEHOLDER)
            and _hijo_por_texto(disco2, "c").childCount() == 1
            and _hijo_por_texto(disco2, "c").child(0).data(0, ROL_PLACEHOLDER),
        )
        registrar(
            "restauracion_sin_escaneo",
            not ventana2.gestor.activo
            and not ventana2._escaneo_pendiente
            and ventana2.estado_escaneo.text() == "Sin escanear",
        )
        registrar("restauracion_tarjetas", len(ventana2.tarjetas) == 5)

        ventana2.close()
        ventana2.gestor.cerrar()

    # --- Fase C: restauracion tolerante (carpeta borrada) ---
    temp_config2 = tempfile.TemporaryDirectory()
    ruta_config2 = os.path.join(temp_config2.name, "configuracion.json")
    borrada = os.path.join(tmp.name, "borrada")
    os.makedirs(borrada)
    guardar_ultima_carpeta(borrada, ruta_config2)
    shutil.rmtree(borrada)
    with mock.patch.object(
        arbol_navegacion, "discos_disponibles", return_value=[tmp.name]
    ):
        try:
            ventana3 = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config2)
            ventana3.resize(900, 600)
            ventana3.show()
            esperar(lambda v=ventana3: v._carga_completada and v.gestor.hilo is None)
            sin_excepcion = True
        except Exception as e:  # noqa: BLE001
            print(f"restauracion_tolerante_exc={type(e).__name__}: {e}")
            sin_excepcion = False
            ventana3 = None
        registrar("restauracion_tolerante_sin_excepcion", sin_excepcion)
        if ventana3 is not None:
            registrar(
                "restauracion_tolerante_sin_carpeta",
                ventana3.carpeta_seleccionada is None
                and ventana3.etiqueta_carpeta.text() == MENSAJE_SIN_CARPETA,
            )
            ventana3.close()
            ventana3.gestor.cerrar()

    # --- Fase D: boton "Seleccionar carpeta" intacto ---
    temp_config3 = tempfile.TemporaryDirectory()
    ruta_config3 = os.path.join(temp_config3.name, "configuracion.json")
    with mock.patch.object(
        arbol_navegacion, "discos_disponibles", return_value=[tmp.name]
    ):
        ventana4 = VisorVideos(ruta_db=ruta_db, ruta_config=ruta_config3)
        ventana4.resize(900, 600)
        ventana4.show()
        esperar(lambda v=ventana4: v._carga_completada and v.gestor.hilo is None)

        original = QFileDialog.getExistingDirectory
        ruta_c = os.path.join(tmp.name, "c")
        QFileDialog.getExistingDirectory = lambda *a, **k: ruta_c
        ventana4.seleccionar_carpeta()
        QFileDialog.getExistingDirectory = original
        registrar(
            "dialogo_valido_funciona",
            ventana4.carpeta_seleccionada == ruta_c
            and obtener_ultima_carpeta(ruta_config3) == ruta_c,
        )
        antes = ventana4.carpeta_seleccionada
        QFileDialog.getExistingDirectory = lambda *a, **k: ""
        ventana4.seleccionar_carpeta()
        QFileDialog.getExistingDirectory = original
        registrar("dialogo_cancelar_conserva", ventana4.carpeta_seleccionada == antes)
        archivo = os.path.join(tmp.name, "archivo.txt")
        QFileDialog.getExistingDirectory = lambda *a, **k: archivo
        ventana4.seleccionar_carpeta()
        QFileDialog.getExistingDirectory = original
        registrar(
            "dialogo_invalido_mensaje",
            ventana4.mensaje_carpeta.text() == MENSAJE_RUTA_INVALIDA,
        )

        ventana4.close()
        ventana4.gestor.cerrar()

    tmp.cleanup()
    temp_db.cleanup()
    temp_config.cleanup()
    temp_config2.cleanup()
    temp_config3.cleanup()

    total_ok = sum(1 for _, ok in resultados if ok)
    print(f"TOTAL={total_ok}/{len(resultados)}")
    print(f"RESULTADO_FINAL={'OK' if total_ok == len(resultados) else 'FAIL'}")
    sys.exit(0)


if __name__ == "__main__":
    main()
