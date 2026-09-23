# MFP-3 ONE FILE v1.19 — Causal Driver Discovery Engine

## Qué cambia

v1.19 deja de preguntar sólo:

`¿X está correlacionado con el precio?`

Ahora pregunta:

`¿X ocurre antes, tiene un mecanismo económico, repite el efecto, sobrevive validación y agrega valor frente a un baseline técnico?`

## Evidencia requerida

Cada causa candidata pasa por:

1. **Temporalidad**
2. **Mecanismo económico predefinido**
3. **Repetición en 3 años de discovery**
4. **Prueba de dirección/endogeneidad**
5. **2 años de validation**
6. **Año futuro OOS**
7. **Valor incremental vs baseline técnico**

## Causas candidatas por instrumento

### QQQ
- tasas reales
- Treasury corto / política monetaria
- curva
- inflación implícita
- condiciones financieras/crédito
- VIX
- dólar
- FOMC + movimiento del mercado de tasas
- breadth growth vs broad market

### CPER
- demanda China
- dólar
- tasas reales
- estrés financiero
- posicionamiento CFTC Managed Money
- posicionamiento productores
- cobre no explicado por demanda/USD/rates
- riesgo global

### ECH
- demanda China
- cobre vs petróleo / términos de intercambio
- USD/CLP
- tasas
- estrés financiero
- cobre no-demanda
- riesgo global

## Importante sobre "copper_non_demand_shock"

No se etiqueta como shock de oferta puro. Es un residuo heurístico del movimiento
del cobre después de descontar parcialmente China, dólar y tasas. Puede contener
oferta, inventarios, noticias específicas u otros factores.

## FRED

v1.19 intenta dos rutas públicas de CSV:

1. `fredgraph.csv`
2. `/series/<ID>/downloaddata/<ID>.csv`

Si FRED sigue bloqueado en el equipo, utiliza proxies de mercado explícitamente
identificados como `PROXY_...`; nunca los presenta como datos FRED reales.

## Fusión

El Causal Engine empieza en **0%**.

Pesos posibles máximos:

- 0%
- 5%
- 10%
- 15%
- 20%
- 25%

Sólo recibe peso si una mezcla histórica OOS mejora la utilidad de v1.14.

## Uso

```powershell
cd $HOME\Downloads
py mfp3_onefile_v1_19.py
```

Forzar investigación:

```powershell
py mfp3_onefile_v1_19.py --causal
```

Automatizar:

```powershell
py mfp3_onefile_v1_19.py --install
```

## Qué mirar al terminar

`CAUSAL DRIVER DISCOVERY — RESULTADO`

y especialmente:

- `CAUSAL_FUSION_CHALLENGER`
- `V14_ADAPTIVE_FUSION_REFERENCE`
- `CAUSAL_ENGINE_REFERENCE`
- `Causas candidatas actuales`
- columnas D/V/F de cada driver

D = discovery  
V = validation  
F = futuro OOS

El patrón deseable es una causa cuyo signo y magnitud sobrevivan D -> V -> F.
