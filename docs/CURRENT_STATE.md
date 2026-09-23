# Estado actual al momento de la migración

## Referencias principales

| Motor | Retorno total | Sharpe | Max Drawdown |
|---|---:|---:|---:|
| v1.7 referencia | +136.402% | 0.8152 | -17.970% |
| v1.14 Adaptive Fusion | +127.639% | **0.8343** | **-13.599%** |
| Synergy | +59.573% | 0.6286 | **-8.898%** |
| Benchmark | +245.507% | 0.8006 | -23.058% |

Interpretación: v1.7 generó más retorno que v1.14, pero v1.14 consiguió mejor Sharpe y una reducción relevante de drawdown. Por eso v1.7 sigue congelado como Champion y v1.14 es el Challenger de combinación más sólido verificado.

## Experimentos posteriores

- v1.15 Regime-Gated Fusion: demasiado conservador; terminó frecuentemente en 100% v1.7.
- v1.16 Regime Residual Overlay: redujo marginalmente drawdown, pero no mejoró globalmente v1.14.
- v1.17 Exogenous: prácticamente igual pero ligeramente peor que v1.14; no justificó promoción.
- v1.18 Relationship Fusion: encontró relaciones interesantes, pero la fusión fue inferior a v1.14. En esa corrida varias series FRED fallaron.
- v1.19 Causal Driver Discovery: preparado para investigar causas candidatas; sus resultados aún deben validarse después de la migración.

## Resultado v1.18 conocido

| Motor | Retorno total | Sharpe | Max Drawdown |
|---|---:|---:|---:|
| Relationship Fusion | +118.840% | 0.8287 | -13.548% |
| v1.14 misma ventana | +127.639% | 0.8343 | -13.599% |
| Relationship Engine | +94.215% | 0.7764 | -12.851% |

La v1.18 asignó aproximadamente 33.3% al Relationship Engine, considerado demasiado agresivo dada su evidencia relativa. v1.19 corrige esto con promotion gating y peso inicial 0.

## Hallazgos de auditoría inicial 2026-09-23

Las cifras anteriores describen el estado documentado al migrar, pero no todas están respaldadas por artefactos incluidos en este repositorio:

- los outputs preservados permiten verificar la corrida histórica de v1.7;
- no se incluyeron los outputs finales de v1.14, v1.18 ni v1.19;
- antes de la Methodology Foundation, la ejecución integral de `src/nexus_mfp.py --causal` no llegaba a v1.19: la carga embebida de v1.7 fallaba bajo Python 3.10 y v1.14 abortaba porque no se generaba `mfp3_output_v17/portfolio_daily.csv`;
- v1.18 y v1.19 no purgan de forma completa los targets forward en las fronteras discovery/validation/future;
- las series FRED históricas se descargan en su versión revisada actual, no como vintages point-in-time.

Consecuencia: v1.7 permanece congelado como Champion por decisión de gobernanza, v1.14 conserva la etiqueta de mejor Challenger **documentado**, y v1.18/v1.19 deben tratarse como investigación no promovible hasta reconstruir una corrida point-in-time y libre de leakage. Véase `docs/AUDIT_2026-09-23.md`.

## Methodology Foundation ejecutada

La rama `methodology/point-in-time-foundation` corrige primero la infraestructura metodológica, sin crear v1.20:

- restauró la ejecución embebida de v1.7 bajo Python 3.10;
- añadió purga por sesiones reales en discovery, validation y pretest de v1.19 activo;
- añadió FDR y placebo de screening;
- introdujo ledger de disponibilidad y bloqueo fail-closed de promoción;
- registra fingerprints de código, inputs y features;
- amplió métricas con Sortino, hit rate, turnover y costos del overlay;
- añadió tests ejecutables mediante `verify.ps1`.

Hasta disponer de snapshots/vintages verdaderamente point-in-time, el peso permitido del Causal Engine es 0%.

### Validación reproducida el 2026-09-23

La cadena reanudable alcanzó v1.19 bajo Python 3.10. La reproducción con datos actuales obtuvo, en la ventana común de v1.14:

| Motor | Retorno total | Sharpe | Max Drawdown |
|---|---:|---:|---:|
| v1.14 Adaptive Fusion reproducido | +74.901% | 0.6550 | -11.755% |
| v1.7 referencia misma ventana | +83.121% | 0.6354 | -16.457% |
| Benchmark misma ventana | +244.708% | 0.7991 | -23.058% |

Estas cifras son una reproducción con historia ajustada/revisada disponible hoy; no reemplazan las referencias históricas de la migración ni recalibran el Champion.

La corrida causal final terminó con código 0 y `CAUSAL_ENGINE_NO_EVIDENCE`: 0 observaciones OOS utilizables, peso causal 0%, peso v1.14 100% y promoción bloqueada. Las siete consultas FRED fallaron de forma visible, se usaron proxies declarados para investigación y CFTC provino de cache. Además de la falta de vintages point-in-time, el estado registra `insufficient_oos_results`.
