# MFP-3 ONE FILE v1.12 — Confluence Discovery Engine

La v1.12 prueba la hipótesis de que la ventaja puede estar en la **coincidencia**
de varias señales, no en una sola.

## Método temporal

Para predecir un año T:

- T-4, T-3, T-2: descubre señales y combinaciones;
- T-1: valida combinaciones, aprende pesos y exposición base;
- T: prueba completamente fuera de muestra.

El año T sólo se incorpora al aprendizaje después de terminar.

## Qué busca

- señales individuales;
- pares de señales;
- tríos de señales;
- máximo 12 features estables;
- soporte mínimo;
- ventaja respecto del retorno base;
- confirmación en un año de validación independiente;
- diversidad entre patrones para no contar variantes casi iguales.

## Exposición

El Confluence Engine puede aprender una exposición base entre:
0%, 25%, 50% o 67%.

Sobre esa base, las coincidencias activas aumentan exposición.

## Uso normal

```powershell
cd $HOME\Downloads
py mfp3_onefile_v1_12.py
```

## Forzar investigación de coincidencias

```powershell
py mfp3_onefile_v1_12.py --confluence
```

## Automatizar

```powershell
py mfp3_onefile_v1_12.py --install
```

El laboratorio pesado se repite automáticamente cada 14 días.

## Importante

v1.12 sigue siendo Challenger. v1.7-FROZEN no se modifica.
