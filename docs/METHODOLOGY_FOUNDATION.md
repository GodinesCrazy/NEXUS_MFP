# Methodology Foundation

## Problema que resuelve

Antes de investigar un nuevo Causal Shock Decomposition Engine, NEXUS-MFP debe poder demostrar que cada label, feature y decisión estaba disponible en su fecha histórica y que una corrida puede reconstruirse exactamente. La auditoría detectó una cadena no ejecutable, purga incompleta, historia macro revisada y control insuficiente de múltiples pruebas.

## Plan ejecutado

1. Restaurar la cadena canónica sin modificar `src/history/`.
2. Definir contratos temporales testeables y purgar por sesiones, no por días hábiles teóricos.
3. Registrar fuente, frecuencia, lag, vintage y fallback.
4. Bloquear promoción si cualquier input causal usado carece de historia point-in-time.
5. Registrar cantidad de hipótesis, q-values y placebos.
6. Guardar hashes de código, inputs y features.
7. Reportar costos y riesgo además de retorno/Sharpe.
8. Reproducir v1.7, v1.14 y benchmark en ventana común.

## Resultado de ejecución 2026-09-23

La cadena reanudable completó hasta v1.19 bajo Python 3.10. En la ventana común reproducida, v1.14 obtuvo +74.901% y Sharpe 0.6550, v1.7 obtuvo +83.121% y Sharpe 0.6354, y el benchmark +244.708% y Sharpe 0.7991. Son resultados con los datos ajustados/revisados disponibles en la fecha de corrida, no una sustitución de los artefactos históricos congelados.

v1.19 terminó sin evidencia causal suficiente: no produjo filas OOS promovibles, mantuvo peso causal 0 y registró los blockers `insufficient_oos_results` y `bootstrap_evidence_unavailable`. FRED falló para las siete series solicitadas; los proxies se identificaron como proxies y el ledger marcó todos los inputs actuales como no point-in-time. Estado y manifiesto coinciden en ambos gates finales.

La siguiente evolución ya incorpora dos piezas fail-closed: un almacén local inmutable de snapshots con selección `as_of` por fecha de conocimiento, y un block bootstrap circular emparejado que compara retornos netos del candidato contra v1.14. Son infraestructura validada; no convierten la historia revisada existente en point-in-time ni sustituyen la carga futura de vintages ALFRED.

El almacén ahora separa fecha real de descarga (`retrieved_at_utc`) de fecha histórica de conocimiento declarada por la fuente (`knowledge_at_utc`). El conector ALFRED está implementado y probado, pero el diagnóstico local permanece en `credential_missing` hasta configurar `FRED_API_KEY`; por tanto, cero series se consideran completas y la promoción continúa bloqueada.

## Información nueva requerida para la siguiente fase

- vintages ALFRED o snapshots propios con `retrieved_at` para macro;
- calendario de publicación por serie y no un lag genérico;
- expectativas consensuadas archivadas para construir `actual - expected`;
- timestamps verificables de FOMC, CFTC, noticias e inventarios;
- snapshots inmutables de precios y metadatos de ajustes corporativos.

## Prevención de overfitting

- hipótesis y mecanismos pre-registrados por familia;
- presupuesto explícito de pruebas;
- FDR en discovery y validation;
- placebos, controles negativos y pruebas inversas;
- nested walk-forward con purga/embargo;
- parámetros por grilla pequeña y prueba de sensibilidad;
- block bootstrap circular emparejado para dependencia serial antes de considerar promoción;
- peso inicial cero y promoción sólo usando OOS previamente observado.

La promoción exige simultáneamente: inputs point-in-time válidos, evidencia OOS suficiente y límite inferior 95% positivo para la mejora anualizada neta frente a v1.14. Si la evidencia bootstrap no existe o falla, el peso causal sigue en cero.

## Validación requerida

El candidato debe compararse contra v1.7-FROZEN, v1.14 y benchmark en la misma ventana, incluyendo retorno, CAGR, Sharpe, Sortino, drawdown, volatilidad, hit rate, IC por bloque, turnover, costos, estabilidad anual/regímenes, bootstrap y sensibilidad.

La corrida 2026 parcial se etiqueta como parcial y no puede tratarse como año completo.

## Criterio de éxito o descarte

Sólo justificaría continuar hacia asignación de capital si mejora de forma repetida y estadísticamente defendible la utilidad neta de v1.14 en validation y future OOS, sin empeorar materialmente drawdown o sensibilidad a costos.

Debe descartarse si:

- no supera v1.14 en ventana común después de costos;
- falla el signo entre discovery, validation y future;
- pierde significancia frente a FDR/placebos/block bootstrap;
- depende de un parámetro, año o régimen estrecho;
- utiliza datos sin disponibilidad point-in-time verificable;
- el aporte desaparece al separar el origen económico del shock.
