# MFP-3 v1.3 — Regime Engine + Champion/Challenger

Este archivo se ejecuta **después** de que termine `mfp3_adaptive_v1_2.py`.

## Qué agrega

- Detecta regímenes simples de mercado:
  - `RISK_ON`
  - `RISK_OFF`
  - `INFLATIONARY`
  - `USD_STRENGTH`
  - `NEUTRAL`
- Calcula rendimiento de MFP-3 dentro de cada régimen.
- Guarda cada corrida en un registro experimental.
- Mantiene un `champion.json`.
- Rechaza Challengers que sólo mejoren rentabilidad a costa de demasiado riesgo.
- Envía modelos rechazados a `model_graveyard.csv`.

## Uso

Cuando v1.2 termine:

```powershell
cd $HOME\Downloads
py mfp3_v1_3_postprocess.py
```

Se generarán dentro de `mfp3_output`:

```text
regime_daily.csv
regime_performance.csv
experiment_registry.csv
champion.json
model_graveyard.csv
```

## Nota

La primera versión del Regime Engine usa reglas transparentes para poder auditarlo.
En una versión posterior podrá competir contra clustering, Hidden Markov Models y
otros detectores de régimen; sólo se conservarán si mejoran resultados fuera de muestra.
