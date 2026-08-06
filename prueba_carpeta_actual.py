import os
import sys
import tempfile
import time
from unittest import mock

from PySide6.QtWidgets import QApplication, QFileDialog

import arbol_navegacion
from arbol_navegacion import ArbolNavegacion
from configuracion import obtener_ultima_carpeta
from tareas_videos import conectar_bd, guardar_videos
from visor_videos import VisorVideos

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
        ruta_a = os.path.join(tmp.name, "a")

        arbol_v.setCurrentItem(a_v)
        QApplication.processEvents()
        registrar("arbol_aplica_carpeta", ventana.carpeta_seleccionada == ruta_a)
        registrar(
            "arbol_aplica_etiqueta", ventana.etiqueta_carpeta.text() == ruta_a
        )
        registrar(
            "arbol_sin_escaneo",
            not ventana.gestor.activo and not ventana._escaneo_pendiente,
        )
        registrar("arbol_tarjetas_intactas", len(ventana.tarjetas) == 5)

        etiqueta_antes = ventana.etiqueta_carpeta.text()
        ventana._al_carpeta_actual_arbol(ruta_a)
        registrar(
            "repeticion_sin_cambios",
            ventana.etiqueta_carpeta.text() == etiqueta_antes
            and ventana.carpeta_seleccionada == ruta_a,
        )

        ruta_no_cargada = os.path.join(tmp.name, "a", "x", "y")
        seleccion_antes = arbol_v.carpeta_actual()
        try:
            arbol_v.seleccionar_ruta(ruta_no_cargada)
            sin_excepcion = True
        except Exception as e:  # noqa: BLE001
            print(f"seleccionar_ruta_no_cargada_exc={type(e).__name__}: {e}")
            sin_excepcion = False
        registrar("seleccionar_ruta_no_cargada_sin_excepcion", sin_excepcion)
        registrar(
            "seleccionar_ruta_no_cargada_sin_cambio",
            arbol_v.carpeta_actual() == seleccion_antes
            and ventana.carpeta_seleccionada == ruta_a,
        )

        arbol_v.expandItem(a_v)
        QApplication.processEvents()
        x_v = _hijo_por_texto(a_v, "x")
        arbol_v.expandItem(x_v)
        QApplication.processEvents()
        y_v = _hijo_por_texto(x_v, "y")
        ruta_y = os.path.join(tmp.name, "a", "x", "y")

        original = QFileDialog.getExistingDirectory
        QFileDialog.getExistingDirectory = lambda *a, **k: ruta_y
        ventana.seleccionar_carpeta()
        QFileDialog.getExistingDirectory = original
        registrar(
            "dialogo_sincroniza_arbol",
            arbol_v.currentItem() is y_v and arbol_v.carpeta_actual() == ruta_y,
        )
        registrar(
            "dialogo_sincroniza_app",
            ventana.carpeta_seleccionada == ruta_y
            and ventana.etiqueta_carpeta.text() == ruta_y,
        )

        ruta_antes = ventana.carpeta_seleccionada
        QFileDialog.getExistingDirectory = lambda *a, **k: ""
        ventana.seleccionar_carpeta()
        QFileDialog.getExistingDirectory = original
        registrar("dialogo_cancelacion_conserva", ventana.carpeta_seleccionada == ruta_antes)

        archivo = os.path.join(tmp.name, "archivo.txt")
        QFileDialog.getExistingDirectory = lambda *a, **k: archivo
        ventana.seleccionar_carpeta()
        QFileDialog.getExistingDirectory = original
        registrar(
            "dialogo_invalido_mensaje",
            ventana.mensaje_carpeta.text() == MENSAJE_RUTA_INVALIDA,
        )
        registrar("dialogo_invalido_conserva", ventana.carpeta_seleccionada == ruta_antes)

        ruta_persistida = os.path.join(tmp.name, "c")
        QFileDialog.getExistingDirectory = lambda *a, **k: ruta_persistida
        ventana.seleccionar_carpeta()
        QFileDialog.getExistingDirectory = original
        registrar(
            "dialogo_persiste",
            obtener_ultima_carpeta(ruta_config) == ruta_persistida,
        )

        registrar("boton_escanear_habilitado", ventana.boton_escanear.isEnabled())
        registrar(
            "sin_escaneo_iniciado",
            not ventana._escaneo_pendiente and not ventana.gestor.activo,
        )
        registrar("total_intacto", ventana._total_catalogo == 5)
        registrar(
            "boton_seleccionar_carpeta_funciona",
            hasattr(ventana, "seleccionar_carpeta")
            and ventana.boton_seleccionar_carpeta.isEnabled(),
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
