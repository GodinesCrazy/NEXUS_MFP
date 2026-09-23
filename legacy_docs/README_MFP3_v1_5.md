# MFP-3 Adaptive v1.5 — Time Machine Tournament

Esta versión hace múltiples backtests cronológicos sin mirar el futuro.

## Cambio importante

Los instrumentos simulados son ahora:

- `QQQ` — Nasdaq/tecnología
- `ECH` — Chile
- `CPER` — cobre

Como el capital está expresado en pesos chilenos, la rentabilidad de los tres
instrumentos se convierte a CLP incorporando `USD/CLP`.

## Instalar la única dependencia nueva

En PowerShell:

```powershell
py -m pip install yfinance
```

## Ejecutar

Guarda `mfp3_time_machine_v1_5.py` en Descargas y ejecuta:

```powershell
cd $HOME\Downloads
py mfp3_time_machine_v1_5.py
```

Puede tardar varios minutos porque realiza muchos viajes históricos.

## Qué produce

Dentro de `mfp3_output_v15`:

- `metrics.csv`
- `portfolio_daily.csv`
- `fold_selections.csv`
- `validation_candidates.csv`
- `leaderboard.csv`
- `time_machine_daily.csv`
- `current_signals.csv`

## Lógica

Para cada año desde 2017:

1. El modelo se coloca al inicio de ese año.
2. Sólo ve información anterior.
3. Usa una ventana anterior para seleccionar estrategia.
4. Compiten:
   - Logistic Regression
   - Random Forest
   - HistGradientBoosting
   - Buy & Hold
   - Momentum
   - Mean Reversion
   - Trend
   - Cash
5. Compiten horizontes de 1, 5 y 20 sesiones.
6. La estrategia ganadora se congela.
7. Se comprueba qué ocurrió realmente durante el año siguiente.
8. Se repite hasta 2026.

La elección del año futuro nunca usa el resultado de ese mismo año.

## No borrar v1.2/v1.4

Conservar esos resultados permite medir objetivamente si cada nueva versión mejora.
