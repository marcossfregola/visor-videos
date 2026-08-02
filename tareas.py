import warnings

from PySide6.QtCore import QObject, QThread, Signal


class Estado:
    INACTIVO = "inactivo"
    OCUPADO = "ocupado"
    FINALIZANDO = "finalizando"
    CERRADO = "cerrado"


class TareaBase(QObject):
    inicio = Signal()
    finalizada = Signal()
    error = Signal(str)
    resultado = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._iniciada = False

    def ejecutar(self):
        self._iniciada = True
        try:
            self.inicio.emit()
            valor = self._trabajo()
            self.resultado.emit(valor)
        except Exception as exc:
            self.error.emit(f"{type(exc).__name__}: {exc}")
        finally:
            self.finalizada.emit()

    def _trabajo(self):
        raise NotImplementedError(
            "Las subclases de TareaBase deben implementar _trabajo()"
        )


_GESTORES_ACTIVOS = set()


class _RelayTarea(QObject):
    def __init__(self, gestor):
        super().__init__()
        self._gestor = gestor
        self._token = gestor._token

    def _vigente(self):
        gestor = self._gestor
        return gestor is not None and gestor._token == self._token

    def al_inicio(self):
        if self._vigente():
            self._gestor.tarea_iniciada.emit()

    def al_resultado(self, valor):
        if self._vigente():
            self._gestor.tarea_resultado.emit(valor)

    def al_error(self, mensaje):
        if self._vigente():
            self._gestor.tarea_error.emit(mensaje)


class GestorTareas(QObject):
    tarea_iniciada = Signal()
    tarea_finalizada = Signal()
    tarea_error = Signal(str)
    tarea_resultado = Signal(object)
    actividad_cambiada = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._estado = Estado.INACTIVO
        self._hilo = None
        self._tarea = None
        self._relay = None
        self._token = 0
        self._rechazo = None

    @property
    def estado(self):
        return self._estado

    @property
    def activo(self):
        return self._estado in (Estado.OCUPADO, Estado.FINALIZANDO)

    @property
    def hilo(self):
        return self._hilo

    @property
    def tarea(self):
        return self._tarea

    @property
    def ultimo_rechazo(self):
        return self._rechazo

    def iniciar(self, tarea):
        if self._estado == Estado.CERRADO:
            self._rechazo = "gestor cerrado"
            return False
        if self.activo:
            self._rechazo = "ya hay una tarea en curso"
            return False
        if not isinstance(tarea, TareaBase):
            raise TypeError("Se espera una instancia de TareaBase")
        if tarea.parent() is not None:
            raise TypeError("La tarea no puede tener un QObject padre")
        if tarea._iniciada:
            self._rechazo = "la tarea ya fue ejecutada y no se reutiliza"
            return False

        tarea._iniciada = True
        self._token += 1
        relay = _RelayTarea(self)

        hilo = QThread()
        tarea.moveToThread(hilo)
        hilo.started.connect(tarea.ejecutar)
        tarea.finalizada.connect(hilo.quit)
        tarea.inicio.connect(relay.al_inicio)
        tarea.resultado.connect(relay.al_resultado)
        tarea.error.connect(relay.al_error)
        hilo.finished.connect(self._al_hilo_finalizado)

        self._hilo = hilo
        self._tarea = tarea
        self._relay = relay
        self._estado = Estado.OCUPADO
        _GESTORES_ACTIVOS.add(self)

        hilo.start()
        self.actividad_cambiada.emit(True)
        return True

    def cerrar(self, timeout_ms=5000):
        if self._estado == Estado.CERRADO:
            return True
        if self._estado == Estado.INACTIVO:
            self._estado = Estado.CERRADO
            return True
        if self._estado == Estado.OCUPADO:
            self._estado = Estado.FINALIZANDO

        hilo = self._hilo
        if hilo is None:
            self._estado = Estado.CERRADO
            return True

        hilo.quit()
        detenido = hilo.wait(timeout_ms)
        if detenido:
            self._al_hilo_finalizado()
            return True
        return False

    def _al_hilo_finalizado(self):
        if self._hilo is None:
            return
        hilo = self._hilo
        hilo.wait(0)
        if self._estado == Estado.FINALIZANDO:
            self._estado = Estado.CERRADO
        else:
            self._estado = Estado.INACTIVO
        self._token += 1
        self._hilo = None
        self._tarea = None
        self._relay = None
        _GESTORES_ACTIVOS.discard(self)
        self.tarea_finalizada.emit()
        self.actividad_cambiada.emit(False)

    def __del__(self):
        hilo = self._hilo
        if hilo is None:
            return
        try:
            en_marcha = hilo.isRunning()
        except RuntimeError:
            return
        if en_marcha:
            _GESTORES_ACTIVOS.add(self)
            warnings.warn(
                "GestorTareas destruido con la tarea aun en ejecucion; "
                "se mantiene vivo hasta que el hilo termine.",
                RuntimeWarning,
            )
