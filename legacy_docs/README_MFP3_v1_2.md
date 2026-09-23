# MFP-3 Adaptive v1.2

Motor experimental de predicción financiera y **paper trading**.

## Qué hace

1. Descarga datos diarios públicos desde FRED, sin API key.
2. Usa tres objetivos:
   - NASDAQ-100 Total Return (`NASDAQXNDX`)
   - NASDAQ Chile Large Cap Net Total Return (`NASDAQNQCLLCN`)
   - Nasdaq Sprott Copper Miners Total Return (`NASDAQNSCOPPT`)
3. Incorpora variables explicativas:
   - VIX
   - Fed Funds
   - Treasury 2Y / 10Y
   - WTI
   - índice amplio del dólar
   - Nasdaq Composite
   - relaciones cruzadas entre los tres objetivos
4. Genera momentum, volatilidad, medias móviles, drawdown, RSI y aceleración.
5. Hace walk-forward:
   - el modelo en fecha `t` no usa etiquetas que necesiten información posterior a `t`;
   - reentrena mensualmente;
   - usa una ventana móvil de aproximadamente 6 años.
6. Hace competir:
   - Logistic Regression
   - Random Forest
   - HistGradientBoosting
   - Gradient Boosting
   - Ridge para retorno esperado
7. Pesa los clasificadores según **Brier Score de validación reciente**.
8. Aprende el umbral de entrada únicamente en la ventana de validación.
9. Simula posiciones de 0%, 10%, 20% o 30% por instrumento.
10. Aplica 0,15% de costo por lado y una ejecución conservadora al cierre siguiente.
11. Genera métricas de predicción y cartera.

## Instalación

En Windows:

```bash
py -m pip install pandas numpy scikit-learn
```

## Ejecución

```bash
py mfp3_adaptive_v1_2.py
```

Se genera la carpeta:

```text
mfp3_output/
  metrics.csv
  portfolio_daily.csv
  model_weights.csv
  predictions_NASDAQ100_TR.csv
  predictions_CHILE_LARGECAP_NTR.csv
  predictions_COPPER_MINERS_TR.csv
```

## Principio central

El objetivo no es encontrar el modelo que mejor explica el pasado. Es seleccionar
el modelo que mejor se comporta **fuera de muestra**, después de costos y sin
acceso a información futura.

Esta versión es un laboratorio de investigación/paper trading; los índices no son
órdenes de compra o venta de instrumentos reales.
