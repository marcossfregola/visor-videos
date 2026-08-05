import os
import sys
import tempfile
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication, QFileDialog

import visor_videos
from visor_videos import VisorVideos


def main():
    app = QApplication(sys.argv)

    def esperar(predicado, intentos=400):
        for _ in range(intentos):
            QApplication.processEvents()
            if predicado():
                return True
            time.sleep(0.02)
        QApplication.processEvents()
        return predicado()

    temp = tempfile.TemporaryDirectory()
    ruta_db = os.path.join(temp.name, "catalogo.db")
    _CONFIG = tempfile.TemporaryDirectory()
    os.environ["VISOR_CONFIG"] = os.path.join(_CONFIG.name, "config.json")

    ventana = VisorVideos(ruta_db=ruta_db)
    ventana.resize(720, 540)
    ventana.show()

    esperar(lambda: ventana.gestor.hilo is None)

    print(f"inicio_visible={ventana.barra_progreso.isVisible()}")
    print(f"inicio_pipeline={ventana._pipeline_activo}")

    temp_carpeta = tempfile.TemporaryDirectory()
    for nombre in ["peli.mp4", "serie.mkv", "clip.avi"]:
        Path(os.path.join(temp_carpeta.name, nombre)).write_text(
            "contenido", encoding="utf-8"
        )

    original = QFileDialog.getExistingDirectory
    QFileDialog.getExistingDirectory = lambda *a, **k: temp_carpeta.name
    ventana.seleccionar_carpeta()
    QFileDialog.getExistingDirectory = original

    registros_visibilidad = []
    registros_texto = []

    def registrar_estado():
        registros_visibilidad.append(ventana.barra_progreso.isVisible())
        registros_texto.append(ventana.barra_progreso.format())

    ventana.boton_escanear.click()

    while True:
        QApplication.processEvents()
        time.sleep(0.03)
        registrar_estado()
        if (
            not ventana._pipeline_activo
            and ventana.gestor is not None
            and not ventana.gestor.activo
            and ventana._carga_completada
            and ventana._recarga_catalogo_pendiente is False
            and ventana._escaneo_pendiente is False
        ):
            break

    registrar_estado()

    print(f"fin_visible={ventana.barra_progreso.isVisible()}")
    print(f"fin_pipeline={ventana._pipeline_activo}")
    print(f"fin_carga={ventana._carga_completada}")

    alguna_visible = any(registros_visibilidad)
    print(f"barra_aparecio_durante={alguna_visible}")
    print(f"textos_unicos={list(dict.fromkeys(t for t in registros_texto if t))}")
    print(f"cantidad_muestras={len(registros_visibilidad)}")

    textos_esperados = [
        "Escaneando",
        "Obteniendo tama",
        "Leyendo metadatos",
        "Generando miniaturas",
        "Guardando",
        "Sincronizando",
        "Actualizando cat",
    ]
    for esperado in textos_esperados:
        encontrado = any(esperado in t for t in registros_texto)
        print(f"texto_{esperado}={encontrado}")

    ventana.close()
    ventana.gestor.cerrar()
    ventana.gestor_previews.cerrar()
    temp.cleanup()
    _CONFIG.cleanup()
    temp_carpeta.cleanup()

    ok = (
        alguna_visible
        and not ventana.barra_progreso.isVisible()
        and not ventana._pipeline_activo
    )
    print(f"RESULTADO_FINAL={'OK' if ok else 'ERROR'}")


if __name__ == "__main__":
    main()
