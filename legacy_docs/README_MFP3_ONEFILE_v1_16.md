# MFP-3 ONE FILE v1.16 — Regime Residual Overlay

## Por qué existe

v1.15 terminó aplicando 100% v1.7 / 0% Synergy porque contraía cada decisión
hacia v1.7 y luego una histéresis de 7 puntos anulaba los ajustes pequeños.

Pero v1.14 ya había demostrado una mejora de Sharpe y drawdown.

## Nueva lógica

v1.16 toma como referencia el peso walk-forward de v1.14.

Después aprende sólo un ajuste:

`Peso final v1.7 = Peso v1.14 + Delta de régimen`

Deltas candidatos:

- -15%
- -10%
- -5%
- 0%
- +5%
- +10%

Si no existe evidencia suficiente, el delta se contrae hacia **0%**, no hacia
100% v1.7.

## Datos usados

Sólo información anterior a cada decisión:

- retorno benchmark 21/63/126 sesiones;
- volatilidad benchmark;
- drawdown;
- retorno y volatilidad de v1.7 y Synergy;
- correlación entre ambos.

## Uso

```powershell
cd $HOME\Downloads
py mfp3_onefile_v1_16.py
```

Forzar overlay:

```powershell
py mfp3_onefile_v1_16.py --overlay
```

Automatizar:

```powershell
py mfp3_onefile_v1_16.py --install
```

Sigue siendo Challenger y no modifica v1.7-FROZEN.
