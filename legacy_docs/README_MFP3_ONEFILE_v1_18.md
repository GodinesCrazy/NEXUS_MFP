# MFP-3 ONE FILE v1.18 — Relationship Discovery Engine

## Objetivo

Buscar relaciones directas e indirectas con capacidad predictiva repetible,
no sólo señales aisladas.

## Nuevas variables

### Macro / condiciones financieras
- DFII10: tasa real 10 años
- T10Y2Y: curva 10Y-2Y
- NFCI: condiciones financieras
- T10YIE: breakeven inflación 10Y
- DGS2 / DGS10
- dólar broad

### CFTC cobre
Contrato COMEX `085692`:
- Managed Money net / open interest
- Producer/Merchant net / open interest
- Swap Dealer net / open interest
- cambios de 4 semanas

Los datos se desplazan 3 días desde la fecha de reporte para evitar usar la
posición del martes como si hubiera sido conocida ese mismo martes.

### Cross-market
- QQQ, ECH, CPER
- SPY, EEM, FXI
- cobre, oro
- TLT, UUP, HYG, IWM
- VIX
- USD/CLP
- correlaciones móviles
- spreads cobre/dólar, China/SPY, EM/SPY, crédito/tasas

### v1.17
Los factores exógenos anteriores pueden entrar con un mes de retraso
conservador.

## Descubrimiento

Para cada año futuro T:

- T-5/T-4/T-3: descubre variables estables e interacciones
- T-2/T-1: elige horizonte y regularización
- T: prueba fuera de muestra

Se prueban horizontes 1, 5 y 20 sesiones.

## Interacciones

Además de variables individuales busca relaciones como:

`PRODUCT(X,Y)`

y

`JOINT_MIN(X,Y)`

Las relaciones deben ser relativamente estables a través de varios años.

## Integración

Se crea un `RELATIONSHIP_ENGINE` independiente.

Después se prueba una fusión mensual walk-forward:

`v1.14 + Relationship Engine`

El Relationship Engine parte con peso cero y sólo recibe peso si su desempeño
OOS ya observado lo justifica.

## Uso

```powershell
cd $HOME\Downloads
py mfp3_onefile_v1_18.py
```

Forzar investigación:

```powershell
py mfp3_onefile_v1_18.py --relationships
```

Automatizar:

```powershell
py mfp3_onefile_v1_18.py --install
```

Sigue siendo Challenger; no modifica v1.7-FROZEN ni su Forward Paper.
