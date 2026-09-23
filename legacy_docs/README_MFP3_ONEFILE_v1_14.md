# MFP-3 ONE FILE v1.14 — Adaptive Fusion Lab

La v1.13 mostró que Synergy tiene menor drawdown, pero menor retorno que v1.7.
La v1.14 prueba si ambas arquitecturas se complementan.

## Motores

- v1.7-FROZEN: motor principal.
- Synergy v1.13: motor de confirmación / defensa.

## Método

Cada mes, usando sólo datos anteriores, prueba distintas asignaciones:

- 50% v1.7 / 50% Synergy
- 67% / 33%
- 75% / 25%
- 85% / 15%
- 100% / 0%

Se evalúan ventanas de 126, 252 y 504 sesiones.

Los tres mejores candidatos se combinan con un ensemble y una regla de histéresis
evita cambios pequeños e innecesarios.

## Comparación

Todo se compara en exactamente la misma ventana:

- Adaptive Fusion
- v1.7
- Synergy
- Benchmark

## Uso

```powershell
cd $HOME\Downloads
py mfp3_onefile_v1_14.py
```

Forzar Fusion Lab:

```powershell
py mfp3_onefile_v1_14.py --fusion
```

Automatizar:

```powershell
py mfp3_onefile_v1_14.py --install
```

Adaptive Fusion sigue siendo Challenger y no modifica v1.7-FROZEN.
