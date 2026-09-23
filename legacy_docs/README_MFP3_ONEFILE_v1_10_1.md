# MFP-3 ONE FILE v1.10.1 — Evidence-Gated Causal Engine

Corrección metodológica de v1.10.

## Problema detectado

En el primer día, con `Grupos memoria causal = 0`, v1.10 mostraba exactamente el
mismo `causal_pressure` para QQQ, ECH y CPER y para los horizontes 1/5/20.

Eso era incorrecto: todavía no existía evidencia causal madura.

## Corrección

Ahora existen dos conceptos separados:

### informational_pressure

Describe noticias recientes y se calcula con:
- categoría;
- relevancia específica para QQQ/ECH/CPER;
- fuentes;
- duplicación;
- novedad;
- sentimiento;
- sorpresa;
- decaimiento temporal;
- horizonte.

No es una señal causal.

### causal_pressure

Permanece en **0** hasta que haya al menos 5 ejemplos maduros comparables.
Después utiliza únicamente retornos observados posteriores de eventos anteriores.

La tabla también informa:
- `recent_relevant_clusters`
- `clusters_with_causal_evidence`
- `matured_examples_used`
- `causal_ready`

## Automatización corregida

Ahora:

```powershell
py mfp3_onefile_v1_10_1.py --install
```

programa específicamente **este mismo archivo v1.10.1** para las 18:30.

## Uso normal

```powershell
cd $HOME\Downloads
py mfp3_onefile_v1_10_1.py
```

No borres las carpetas existentes. Todo el historial acumulado se reutiliza.
