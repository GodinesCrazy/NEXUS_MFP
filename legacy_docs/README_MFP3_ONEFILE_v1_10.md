# MFP-3 ONE FILE v1.10 — Event Causal Engine

Sigue siendo **un solo archivo**.

## Uso

```powershell
cd $HOME\Downloads
py mfp3_onefile_v1_10.py
```

## Qué agrega sobre v1.9.1

- agrupa titulares repetidos en eventos causales;
- cuenta fuentes independientes;
- penaliza duplicaciones;
- detecta patrones simples de actual vs esperado;
- asocia cada evento al régimen de mercado vigente;
- usa un solo representante por evento para evitar contar 100 titulares como 100 observaciones independientes;
- construye memoria causal por categoría / activo / régimen;
- genera `causal pressure` a 1, 5 y 20 sesiones para el Challenger.

## Importante

El `causal pressure` todavía no modifica v1.7-FROZEN. Sólo podrá hacerlo si,
después de acumular suficientes observaciones maduras, demuestra mejora fuera de muestra.

## Automatización

La automatización heredada sigue disponible:

```powershell
py mfp3_onefile_v1_10.py --install
```

## Health

```powershell
py mfp3_onefile_v1_10.py --health
```

## Status

```powershell
py mfp3_onefile_v1_10.py --status
```
