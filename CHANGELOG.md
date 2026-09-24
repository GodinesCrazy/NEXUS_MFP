# Changelog resumido

- v1.2–v1.6: backtests, walk-forward, time-machine y robustez inicial.
- v1.7: meta-learning/Champion congelado; paper-forward.
- v1.8–v1.10: one-file, event intelligence y memoria causal.
- v1.11–v1.13: signal/confluence/true synergy discovery.
- v1.14: Adaptive Fusion; mejor Challenger verificado de combinación.
- v1.15: regime-gated fusion; demasiado conservador.
- v1.16: residual regime overlay; no supera globalmente v1.14.
- v1.17: exogenous discovery; factores externos no mejoran aún v1.14.
- v1.18: relationship discovery; encuentra estructuras pero la fusión queda por debajo de v1.14.
- v1.19: causal driver discovery; línea activa al migrar a NEXUS-MFP.

## Auditoría 2026-09-23

- Se verificó el manifiesto de migración y la compilación de todo `src/`.
- Se conectó el repositorio local con el `origin` oficial vacío.
- Se documentaron fallos de reproducibilidad, fuga potencial en fronteras temporales y ausencia de vintages point-in-time.
- Se endureció `.gitignore` para excluir secretos, entornos, cachés y directorios generados por la cadena one-file.
- No se modificó v1.7-FROZEN ni se promovió ningún Challenger.

## Methodology Foundation — rama de trabajo

- Corregida la compatibilidad de módulos embebidos con `dataclass` en Python 3.10, sin editar archivos históricos.
- Añadida purga posicional de labels forward en fronteras discovery/validation/future.
- Añadidos placebo circular y control FDR Benjamini-Hochberg en discovery/validation de v1.19 activo.
- Añadido `AvailabilityLedger`; fuentes sin vintage point-in-time bloquean promoción y fuerzan peso causal 0.
- Añadidos fingerprints reproducibles de código, inputs y features por corrida.
- Añadidos Sortino, hit rate, turnover y costo conservador del rebalanceo entre motores.
- Añadido `verify.ps1` y tests de temporalidad, proveniencia, estadística, ejecución embebida y reproducibilidad.
- Añadidos timeouts explícitos para Yahoo/FRED y salida fail-closed `CAUSAL_ENGINE_NO_EVIDENCE` cuando no existe OOS suficiente.
- Validada la cadena reanudable hasta v1.19: FRED falló visiblemente, los proxies quedaron declarados y el peso causal permaneció en 0%.
- Sincronizados `causal_state.json`, `causal_sources.json` y `run_manifest.json` con los blockers y conteos finales.
- Añadido almacén append-only de snapshots con hashes y selección temporal `as_of`; los vintages históricos aún deben poblarse.
- Añadido block bootstrap circular emparejado contra v1.14; sin evidencia positiva al 95%, la promoción falla de forma cerrada.
- `src/history/` y v1.7-FROZEN permanecen intactos.

## Research Terminal — rama de trabajo

- Añadido dashboard local estilo terminal bursátil para señales, cartera paper, métricas y gate causal.
- Añadida actualización asíncrona de QQQ, ECH y CPER con timestamp, cache y error visible.
- Añadido progreso observable de la cadena con fase, objetivo, PID, porcentaje monotónico, código de salida y consola viva.
- Las acciones `AUMENTAR/MANTENER/REDUCIR` comparan peso paper actual contra objetivo; no son órdenes ni asesoría.
- El servicio sólo escucha en localhost y no expone ninguna integración de trading real.
- Añadida ficha explicativa seleccionable para QQQ, ECH y CPER con exposición, objetivo y componentes del ensemble.
- La interfaz muestra 0% causal cuando no existen drivers promovibles y evita presentar intensidad como confianza.
- Añadida ingesta resumible ALFRED con tiempos de adquisición/conocimiento separados, hashes y estado fail-closed.
- Ejecutado el diagnóstico real: `FRED_API_KEY` ausente, estado `credential_missing`, cero vintages simulados.
