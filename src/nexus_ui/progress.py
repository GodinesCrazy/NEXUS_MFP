"""Observable progress contracts for the one-file research chain."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock


@dataclass(frozen=True)
class PhaseRule:
    token: str
    progress: int
    phase: str
    objective: str


PHASE_RULES = (
    PhaseRule("FORECAST_PHASE load_source", 12, "Forecast · fuente", "Verificar y cargar artefactos OOS de v1.7"),
    PhaseRule("FORECAST_PHASE walk_forward QQQ", 30, "Forecast · QQQ", "Evaluar análogos sin fuga temporal"),
    PhaseRule("FORECAST_PHASE walk_forward ECH", 52, "Forecast · ECH", "Evaluar análogos sin fuga temporal"),
    PhaseRule("FORECAST_PHASE walk_forward CPER", 74, "Forecast · CPER", "Evaluar análogos sin fuga temporal"),
    PhaseRule("FORECAST_PHASE persist", 94, "Forecast · ledger", "Registrar predicciones antes de observar resultados"),
    PhaseRule("FORECAST_COMPLETE", 99, "Forecast · gate", "Persistir métricas y resolver promoción"),
    PhaseRule("[1/4]", 8, "Champion v1.7", "Reconstruir o reutilizar el Champion congelado"),
    PhaseRule("[2/4]", 14, "Forward paper", "Actualizar la cartera paper, sin órdenes reales"),
    PhaseRule("[3/4]", 20, "Inteligencia de eventos", "Recolectar mercado, macro y noticias"),
    PhaseRule("[4/4]", 26, "Etiquetado", "Madurar outcomes disponibles sin mirar el futuro"),
    PhaseRule("[v1.9]", 32, "Eventos enriquecidos", "Clasificar eventos y régimen informativo"),
    PhaseRule("[v1.10]", 38, "Memoria causal", "Actualizar outcomes y presión causal"),
    PhaseRule("[v1.11]", 44, "Signal discovery", "Evaluar señales históricas walk-forward"),
    PhaseRule("[v1.12]", 50, "Confluence", "Evaluar coincidencias de señales"),
    PhaseRule("[v1.13]", 56, "Synergy", "Buscar interacciones sin promoverlas"),
    PhaseRule("[v1.14]", 62, "Adaptive Fusion", "Actualizar el Challenger de combinación"),
    PhaseRule("[v1.15]", 68, "Regime Fusion", "Evaluar gating por régimen"),
    PhaseRule("[v1.16]", 74, "Residual Overlay", "Medir aporte residual por régimen"),
    PhaseRule("[v1.17]", 80, "Exogenous", "Validar factores exógenos"),
    PhaseRule("[v1.18]", 87, "Relationships", "Validar relaciones y future OOS"),
    PhaseRule("Descargando mercados", 91, "Causal · mercado", "Actualizar precios y proxies de mercado"),
    PhaseRule("Obteniendo macro", 94, "Causal · fuentes", "Resolver FRED, fallbacks y proveniencia"),
    PhaseRule("Causal nested walk-forward", 97, "Causal · validación", "Ejecutar discovery, validation y future OOS"),
    PhaseRule("Interpretaci", 99, "Causal · cierre", "Escribir métricas, ledger y gate final"),
)


class RunProgress:
    """Thread-safe, monotonic state for a long-running research process."""

    def __init__(self, max_logs: int = 500):
        self._lock = RLock()
        self._max_logs = max_logs
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self.status = "idle"
            self.progress = 0
            self.phase = "En espera"
            self.objective = "Selecciona una ejecución para comenzar"
            self.started_at = None
            self.finished_at = None
            self.exit_code = None
            self.pid = None
            self.mode = None
            self.logs: list[str] = []

    def start(self, mode: str, pid: int | None = None) -> None:
        with self._lock:
            self.reset()
            self.status = "running"
            self.progress = 2
            self.phase = "Inicialización"
            self.objective = "Preparar entorno y cargar contratos históricos"
            self.started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            self.pid = pid
            self.mode = mode

    def set_pid(self, pid: int) -> None:
        with self._lock:
            self.pid = pid

    def ingest(self, line: str) -> None:
        clean = line.rstrip()
        if not clean:
            return
        with self._lock:
            self.logs.append(clean)
            self.logs = self.logs[-self._max_logs :]
            for rule in PHASE_RULES:
                if rule.token in clean and rule.progress >= self.progress:
                    self.progress = rule.progress
                    self.phase = rule.phase
                    self.objective = rule.objective

    def finish(self, exit_code: int) -> None:
        with self._lock:
            self.exit_code = exit_code
            self.finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            self.pid = None
            if exit_code == 0:
                self.status = "completed"
                self.progress = 100
                self.phase = "Completado"
                self.objective = "Artefactos actualizados; revisar gate y evidencia"
            else:
                self.status = "failed"
                self.phase = "Falló"
                self.objective = "Revisar la consola; no se promovió ningún motor"

    def snapshot(self) -> dict:
        with self._lock:
            elapsed_seconds = 0
            if self.started_at:
                start = datetime.fromisoformat(self.started_at)
                end = (
                    datetime.fromisoformat(self.finished_at)
                    if self.finished_at
                    else datetime.now(timezone.utc)
                )
                elapsed_seconds = max(0, int((end - start).total_seconds()))
            return {
                "status": self.status,
                "progress": self.progress,
                "phase": self.phase,
                "objective": self.objective,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "exit_code": self.exit_code,
                "pid": self.pid,
                "mode": self.mode,
                "elapsed_seconds": elapsed_seconds,
                "logs": list(self.logs),
            }
