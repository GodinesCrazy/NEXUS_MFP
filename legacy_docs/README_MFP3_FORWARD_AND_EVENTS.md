# MFP-3 — Forward Champion + Event Intelligence

Se entregan dos programas independientes.

## 1. Forward Paper de v1.7-FROZEN

Archivo:

`mfp3_forward_paper_v17.py`

Lee:

`mfp3_output_v17/current_signals.csv`

y crea:

`mfp3_forward_v17/`

con:

- `state.json`
- `ledger.csv`
- `rebalance_events.jsonl`
- `frozen_model_fingerprint.json`

### Primera ejecución

```powershell
cd $HOME\Downloads
py mfp3_forward_paper_v17.py
```

Cada ejecución posterior valora la cartera y, si detecta una señal nueva de v1.7,
rebalancea automáticamente el paper portfolio.

**No envía órdenes reales.**

---

## 2. Global Event Intelligence Collector

Archivo:

`mfp3_event_intelligence_v1.py`

Recopila:

- noticias QQQ / tecnología / Fed;
- Chile / Banco Central / peso / cobre / litio;
- cobre / China / minas / oferta / demanda;
- riesgo geopolítico;
- mercado global;
- VIX;
- USD/CLP;
- cobre;
- oro;
- SPY/EEM/FXI;
- Treasury;
- WTI/FRED;
- Fed Funds;
- dólar amplio.

Guarda cada evento con:

- hora en que lo vio nuestro sistema;
- hora de publicación cuando está disponible;
- título;
- fuente;
- URL;
- query;
- tag de activo;
- score léxico reproducible.

### Ejecutar

```powershell
cd $HOME\Downloads
py mfp3_event_intelligence_v1.py
```

Crea:

`mfp3_event_intelligence/`

con:

- `events_raw.jsonl`
- `daily_event_features.csv`
- `market_context.csv`
- `seen_event_ids.txt`

## Flujo diario recomendado

1. Ejecutar v1.7-FROZEN para actualizar señales.
2. Ejecutar `mfp3_forward_paper_v17.py`.
3. Ejecutar `mfp3_event_intelligence_v1.py`.

La v1.7 permanece congelada.
El dataset de eventos alimentará únicamente al Challenger v1.8.
