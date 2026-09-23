# MFP-3 ONE FILE v1.8

Desde esta versión, para el uso diario necesitas **un solo archivo**:

`mfp3_onefile_v1_8.py`

## Uso diario

Guárdalo en `Descargas` y ejecuta:

```powershell
cd $HOME\Downloads
py mfp3_onefile_v1_8.py
```

El programa:

1. actualiza v1.7-FROZEN sólo si hace falta;
2. actualiza la cartera Forward Paper;
3. recolecta noticias;
4. actualiza mercado y macro;
5. etiqueta noticias contra QQQ/ECH/CPER a 1, 5 y 20 sesiones;
6. genera un reporte diario.

## Forzar recálculo completo

```powershell
py mfp3_onefile_v1_8.py --full
```

## Ver sólo estado

```powershell
py mfp3_onefile_v1_8.py --status
```

El programa es un solo `.py`, aunque mantiene las bases de datos y estados en carpetas separadas para no perder el aprendizaje acumulado.
