# NEXUS-MFP

**Nombre oficial del modelo:** NEXUS-MFP — *Network for Exogenous, Unified Signals & Causality / Market Forecasting Platform*.

NEXUS-MFP es la continuación formal del proyecto MFP-3. La migración preserva toda la historia disponible y adopta un directorio estable para seguir evolucionando el modelo desde VS Code + Codex.

## Estado de migración

- **Champion congelado:** v1.7-FROZEN.
- **Mejor Challenger comprobado hasta ahora:** v1.14 Adaptive Fusion.
- **Motores auxiliares:** Synergy, Exogenous, Relationship.
- **Línea de investigación actual:** v1.19 Causal Driver Discovery Engine.
- **Entrada canónica:** `src/nexus_mfp.py`.
- **Operaciones reales:** deshabilitadas; el proyecto trabaja en paper/backtest.

## Inicio rápido

En PowerShell, desde `C:\NEXUS_MFP`:

```powershell
.\setup.ps1
.\run.ps1
```

Para abrir el proyecto en VS Code:

```powershell
code C:\NEXUS_MFP
```

## Estructura

- `src/nexus_mfp.py`: versión actual de trabajo (v1.19 al migrar).
- `src/history/`: versiones históricas y motores previos.
- `docs/`: explicación técnica, arquitectura, estado y reglas de investigación.
- `legacy_docs/`: README históricos del proyecto MFP-3.
- `outputs/archive/`: archivos ZIP de resultados históricos conservados.
- `outputs/extracted/`: resultados históricos extraídos disponibles.
- `data/`: datos locales/cachés futuros del proyecto.
- `runtime/`: salidas de nuevas ejecuciones.
- `AGENTS.md`: instrucciones para Codex dentro de VS Code.

## Principio central

Una nueva señal no se promueve porque “parece funcionar”. Debe demostrar valor fuera de muestra, sin fuga temporal, con costos, ventana común y comparación contra el Champion/Challenger vigente.
