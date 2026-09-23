# MFP-3 Adaptive v1.6 — Robust Time Machine

La v1.6 corrige problemas detectados al analizar la salida completa de v1.5.

## Cambios principales

1. **Auditoría automática de datos**
   - detecta valores USD/CLP imposibles;
   - detecta saltos diarios anómalos;
   - compara el promedio mensual de `CLP=X` con la serie mensual OECD/FRED;
   - guarda `data_quality_report.csv`.

2. **Validación multi-año**
   - ya no selecciona una estrategia porque fue buena en un único año;
   - usa hasta 3 años anteriores como folds independientes;
   - exige consistencia mínima.

3. **Menos sobreajuste**
   - umbrales ML fijos: 0.52 / 0.56 / 0.60 / 0.64;
   - estrategia debe ganar en al menos 2/3 de los años de validación;
   - se penaliza inestabilidad, peor pérdida y drawdown.

4. **Regret**
   - compara la estrategia elegida contra el mejor método simple conocido a posteriori;
   - también compara contra Buy & Hold.

5. **Sensibilidad a costos**
   - 0%, 0,05%, 0,15% y 0,30% por lado.

6. **Monte Carlo**
   - bootstrap de retornos mensuales para medir robustez.

7. **Regla Champion**
   - no basta con ganar dinero;
   - debe pasar retorno, Sharpe, drawdown, años positivos, costos y comparación con benchmark.

## Ejecución

Si ya instalaste `yfinance`, no necesitas instalar nada nuevo.

Guarda `mfp3_robust_time_machine_v1_6.py` en Descargas y ejecuta:

```powershell
cd $HOME\Downloads
py mfp3_robust_time_machine_v1_6.py
```

Puede tardar más que v1.5 porque cada año usa varios folds históricos.

## Salida

Se crea:

```text
mfp3_output_v16/
```

con:

- `metrics.csv`
- `fold_selections.csv`
- `validation_candidates.csv`
- `time_machine_daily.csv`
- `portfolio_daily.csv`
- `regret_analysis.csv`
- `cost_sensitivity.csv`
- `monte_carlo.csv`
- `monte_carlo_summary.csv`
- `data_quality_report.csv`
- `current_signals.csv`
- `champion_decision.json`

## Importante

No borrar v1.2, v1.4 ni v1.5. El historial de versiones es parte del aprendizaje del proyecto.
