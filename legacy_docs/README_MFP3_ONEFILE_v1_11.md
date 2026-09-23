# MFP-3 ONE FILE v1.11 — Historical Signal Discovery

La v1.11 mantiene todo en **un único archivo**.

## Nueva idea central

El modelo busca automáticamente señales históricas estables y mezclas ponderadas.

Para cada año de prueba:

1. usa dos años anteriores para descubrir señales estables;
2. usa el año inmediatamente anterior para ponderar modelos;
3. congela señales y pesos;
4. prueba el año futuro sin conocerlo;
5. una vez terminado ese año, sus resultados pasan a formar parte de la historia disponible para años posteriores.

Así existe retroalimentación sin reescribir el pasado.

## Señales que busca

- momentum 1/2/5/10/20/60/120;
- volatilidad 5/20/60;
- SMA 20/60/200;
- drawdown;
- RSI;
- SPY, EEM, FXI;
- cobre y oro;
- TLT y UUP;
- VIX;
- USD/CLP;
- IWM y HYG;
- correlaciones móviles 20/60 sesiones;
- spreads cross-market;
- interacciones entre riesgo, momentum, cobre y dólar.

## Mezcla ponderada

Compiten:
- Logistic Regression;
- HistGradientBoosting;
- Ridge;
- Stable Signal Vote.

Los pesos dependen del desempeño de validación y se penalizan modelos muy correlacionados.

## Uso

```powershell
cd $HOME\Downloads
py mfp3_onefile_v1_11.py
```

La investigación pesada se ejecuta automáticamente cada 7 días.

Para forzarla:

```powershell
py mfp3_onefile_v1_11.py --research
```

## Automatizar todo

```powershell
py mfp3_onefile_v1_11.py --install
```

## Importante

El Signal Discovery Lab sigue siendo Challenger. No modifica la v1.7-FROZEN.
