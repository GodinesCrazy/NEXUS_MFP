# MFP-3 Adaptive v1.7 — Meta-Learning Ensemble

La v1.7 cambia de arquitectura.

## Qué aprendimos de v1.6

- El selector anual todavía elegía mal con demasiada frecuencia.
- El `robust_score` no anticipaba bien el año siguiente.
- La rotación y los costos estaban destruyendo gran parte del edge.
- La limpieza genérica de datos eliminaba eventos reales del VIX y del petróleo.

## Qué hace v1.7

1. **Meta-learning**
   - después de terminar un año histórico, guarda qué habría ocurrido con TODOS los candidatos;
   - esa experiencia puede usarse únicamente desde el año siguiente;
   - el meta-modelo aprende qué características de validación suelen anticipar éxito futuro;
   - sólo se usa si su propio backtest histórico supera al selector anterior.

2. **Ensemble**
   - ya no escoge un único ganador;
   - combina hasta los 3 mejores candidatos.

3. **Core + trend**
   - incorpora reglas de exposición parcial bajo SMA200:
     - 0%
     - 33%
     - 50%
     - 67%
   - todas deben ganarse su lugar usando exclusivamente información pasada.

4. **Menos rotación**
   - rebalanceo aproximadamente semanal;
   - modelos ML usan histéresis: un pequeño cambio de probabilidad no obliga a comprar/vender.

5. **Data quality específica**
   - corrige errores evidentes de USD/CLP;
   - NO elimina shocks reales del VIX;
   - utiliza WTI/FRED en vez de tratar el futuro de petróleo negativo como un error.

6. **Champion más estricto**
   - aun si supera las pruebas históricas, sólo recibe el estado:
     `HISTORICAL_CHAMPION_CANDIDATE`;
   - Champion definitivo requerirá forward paper con datos futuros que todavía no han ocurrido.

## Ejecutar

Ya tienes las dependencias. Descarga el archivo en `Descargas` y ejecuta:

```powershell
cd $HOME\Downloads
py mfp3_meta_learning_v1_7.py
```

Esta versión es más pesada que v1.6 y puede tardar varios minutos.

## Carpeta de salida

```text
mfp3_output_v17/
```

Contiene:

- metrics.csv
- portfolio_daily.csv
- yearly_ensembles.csv
- candidate_audit.csv
- meta_audit.csv
- current_signals.csv
- cost_sensitivity.csv
- monte_carlo.csv
- monte_carlo_summary.csv
- data_quality_report.csv
- decision.json
