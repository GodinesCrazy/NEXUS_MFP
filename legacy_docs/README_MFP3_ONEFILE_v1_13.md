# MFP-3 ONE FILE v1.13 — True Synergy Discovery

La v1.13 corrige el problema observado en v1.12: una sola señal podía terminar
ganando el torneo de “confluencia”.

## Ahora una sinergia DEBE ser una combinación

Sólo compiten:
- pares de señales;
- tríos de señales.

Las señales individuales sólo se usan como referencia.

Una combinación debe demostrar:

1. ventaja histórica positiva;
2. repetición en al menos 2 de 3 años de descubrimiento;
3. rendimiento mejor que su mejor componente individual;
4. supervivencia en dos años independientes de validación;
5. soporte mínimo;
6. diversidad frente a otros patrones elegidos.

## Split temporal

Para un año T:

- T-5, T-4, T-3: descubrimiento;
- T-2, T-1: validación;
- T: prueba ciega.

## Exposición base

El floor 0 / 25% / 50% / 67% también se selecciona usando los dos años de
validación, penalizando años negativos y rotación.

## Comparación justa

El benchmark y el Challenger se calculan en exactamente la misma ventana.
Si existe la salida de v1.7, también se agrega una referencia de v1.7 en esa
misma ventana.

## Uso

```powershell
cd $HOME\Downloads
py mfp3_onefile_v1_13.py
```

Forzar laboratorio:

```powershell
py mfp3_onefile_v1_13.py --synergy
```

Automatizar:

```powershell
py mfp3_onefile_v1_13.py --install
```

Sigue siendo Challenger. No modifica v1.7-FROZEN.
