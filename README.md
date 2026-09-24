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

Para verificar contratos metodológicos, sintaxis y dependencias sin ejecutar una investigación completa:

```powershell
.\verify.ps1
```

Para abrir la terminal gráfica local:

```powershell
.\dashboard.ps1
```

Luego visita `http://127.0.0.1:8765`. La portada **Decisiones** separa la recomendación direccional de la acción de asignación; **Wallet paper** muestra efectivo, posiciones, P&L estimado, costos y ledger, y **Research** conserva la evidencia técnica y el progreso de la cadena. No contiene ejecución de órdenes reales.

Mientras no exista un forecast probabilístico calibrado, promovido y con al menos 252 observaciones OOS, el sistema muestra `SIN RECOMENDACIÓN`. No transforma automáticamente un peso objetivo en `COMPRAR` o `VENDER`.

El Risk & Scenario Lab recalcula sensibilidad a costos sobre una ventana común, permite shocks lineales sobre la exposición actual y centraliza alertas de fuentes, vigencia y gates. Los shocks son simulaciones mecánicas de una sesión, no pronósticos ni VaR.

La vista por activo explica la diferencia entre exposición actual y objetivo, desglosa el ensemble y separa explícitamente esa señal de la evidencia causal. Para iniciar el backfill resumible de ALFRED:

```powershell
$env:FRED_API_KEY = "tu_clave_personal"
.\vintages.ps1 --max-new-vintages 25
```

La clave no se persiste. Sin ella, el comando registra `credential_missing` y no fabrica datos. Un estado parcial tampoco habilita promoción.

## Estructura

- `src/nexus_mfp.py`: versión actual de trabajo (v1.19 al migrar).
- `src/nexus_core/`: contratos testeables de temporalidad, proveniencia, estadística, snapshots point-in-time, bootstrap y reproducibilidad.
- `tests/`: pruebas que tienen prioridad sobre cualquier mejora de métricas.
- `src/nexus_ui/`: API local, agregación de artefactos y terminal gráfica.
- `src/nexus_data/`: conectores point-in-time resumibles con proveniencia explícita.
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
