# MFP-3 Adaptive v1.4

Esta versión corrige los principales problemas detectados en la v1.2.

## No ejecutes v1.3 antigua

La v1.3 anterior podía nombrar Champion al primer modelo aunque fuera malo. Se reemplazará después.

## Cómo ejecutar

1. Descarga `mfp3_adaptive_v1_4.py`.
2. Guárdalo en `Descargas`.
3. Abre PowerShell.
4. Ejecuta:

```powershell
cd $HOME\Downloads
py mfp3_adaptive_v1_4.py
```

## Qué cambia

- Predice el retorno que realmente podría capturarse después de la ejecución.
- Purga y separa entrenamiento/validación.
- Valida con observaciones no solapadas.
- Compara Brier contra el baseline de prevalencia.
- Usa AUC como filtro de discriminación.
- Los clasificadores sin skill reciben peso cero.
- El modelo Ridge debe demostrar skill de retorno.
- Si no hay edge, la posición es 0% (CASH).
- El resultado todavía NO se nombra Champion.
- El siguiente paso será un Time Machine Tournament multi-período.
