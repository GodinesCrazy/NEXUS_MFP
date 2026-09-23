# MFP-3 ONE FILE v1.15 — Regime-Gated Fusion

La v1.14 mejoró el Sharpe y drawdown de v1.7, sacrificando algo de retorno.
La v1.15 intenta usar Synergy sólo cuando históricamente ayudó bajo un régimen parecido.

## Régimen

Se determina usando exclusivamente datos anteriores:

- retorno benchmark 21/63/126 días;
- volatilidad 21/63 días;
- drawdown benchmark;
- drawdown v1.7;
- ventaja reciente v1.7 vs Synergy;
- correlación entre ambos motores.

Estados:
- RISK_ON
- NEUTRAL
- RISK_OFF

## Pesos candidatos

Asignación a v1.7:

- 50%
- 60%
- 67%
- 75%
- 85%
- 93%
- 100%

El resto va a Synergy.

## Entrenamiento

Cada mes evalúa ventanas de:

- 252 sesiones
- 504 sesiones
- 756 sesiones

Busca rendimiento global y rendimiento dentro del mismo régimen.
Si el régimen tiene pocos ejemplos, el peso se contrae prudentemente hacia 100% v1.7.

## Uso

```powershell
cd $HOME\Downloads
py mfp3_onefile_v1_15.py
```

Forzar investigación:

```powershell
py mfp3_onefile_v1_15.py --regime
```

Automatizar:

```powershell
py mfp3_onefile_v1_15.py --install
```

Sigue siendo Challenger; no modifica v1.7-FROZEN.
