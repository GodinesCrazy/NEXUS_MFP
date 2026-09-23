# MFP-3 ONE FILE v1.17 — Exogenous Discovery Engine

La v1.17 incorpora factores indirectos como **hipótesis**, no como verdades.

## Familias

### EXPECTATIONS
- breakeven de inflación 5/10 años
- sentimiento del consumidor
- expectativas de inflación

### GEOPOLITICAL
- AI-GPR diario y componentes

### CLIMATE_ENSO
- Niño 3.4 / ENSO

### WEATHER
Clima histórico previo de:
- Nueva York
- Beijing
- Santiago
- Antofagasta

Incluye temperatura, precipitación y viento, con medias/anomalías previas.

### MOON
- fase lunar sen/cos
- cercanía a luna llena
- cercanía a luna nueva

### OLYMPICS
- durante Juegos
- 30 días antes
- 30 días después
- Summer / Winter

### CALENDAR
- mes
- trimestre
- ciclo anual
- enero
- ventanas de fin de año

## Método

Cada familia genera predicciones walk-forward de la ventaja futura de Synergy
frente a v1.7.

Una familia sólo recibe peso si, usando únicamente predicciones fuera de muestra
ya observadas, muestra:

- IC positivo;
- dirección suficientemente consistente;
- estabilidad entre subperíodos.

Si ninguna familia pasa el filtro:

`Delta = 0%`

y la mezcla v1.14 no se modifica.

También se genera un placebo por desplazamientos circulares para detectar
correlaciones accidentales. El placebo es diagnóstico y no reescribe el pasado.

## Fuentes

- FRED: expectativas/sentimiento
- NOAA PSL: Niño 3.4
- AI-GPR (Iacoviello/Tong): riesgo geopolítico
- Open-Meteo Archive: clima diario
- calendario astronómico calculado
- calendario olímpico incorporado

## Uso

```powershell
cd $HOME\Downloads
py mfp3_onefile_v1_17.py
```

Forzar laboratorio:

```powershell
py mfp3_onefile_v1_17.py --exogenous
```

Automatizar:

```powershell
py mfp3_onefile_v1_17.py --install
```

Sigue siendo Challenger. No modifica v1.7-FROZEN ni su Forward Paper.
