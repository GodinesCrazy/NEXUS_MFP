# Arquitectura de NEXUS-MFP

## Motores principales

### v1.7-FROZEN — Champion
Motor histórico principal. Se mantiene congelado como referencia y no debe reescribirse durante investigación.

### Synergy Engine
Busca confluencias de señales. Históricamente aportó principalmente reducción de drawdown y volatilidad, no máximo retorno.

### v1.14 Adaptive Fusion
Combina v1.7 y Synergy con pesos walk-forward. Es el mejor Challenger verificado en la migración.

### Exogenous Engine
Evalúa factores indirectos como geopolítica, ENSO, clima, calendario, Juegos Olímpicos y luna. Las variables extrañas se tratan como hipótesis/placebos; sólo sobreviven si demuestran utilidad OOS.

### Relationship Engine
Busca relaciones e interacciones X, X×Y y confluencias entre mercados, macro, CFTC y variables exógenas.

### Causal Driver Engine (v1.19)
Busca causas candidatas con mecanismo explícito y secuencia temporal:

`causa -> shock -> transmisión -> retorno futuro`

Para cada año T utiliza T-5/T-4/T-3 para discovery, T-2/T-1 para validation y T para prueba futura.

## Methodology Foundation

La rama de saneamiento conserva el entrypoint único y extrae únicamente contratos críticos a `src/nexus_core/`:

- `temporal.py`: purga posicional de labels según sesiones reales;
- `provenance.py`: ledger de fuente, frecuencia, lag, vintage y fallback;
- `statistics.py`: p-values, combinación de evidencia y Benjamini-Hochberg;
- `reproducibility.py`: fingerprints deterministas de código, datos y features;
- `forecasting.py`: análogos históricos walk-forward, evaluación común y ledger append-only;
- `decisions.py`: contrato fail-closed que separa forecast direccional y asignación;
- `embedded.py`: compatibilidad segura con la cadena histórica ejecutada mediante `exec`.

Los archivos bajo `src/history/` permanecen inmutables. Las correcciones sólo se aplican a `src/nexus_mfp.py` y a su alias activo de compatibilidad.

La promoción es fail-closed: si una fuente causal no es point-in-time, el laboratorio puede producir diagnósticos pero el peso del Causal Engine permanece en cero.

## Research Terminal

`src/nexus_ui/` añade una capa local y estrictamente paper sobre los artefactos de investigación. El servidor sólo enlaza a localhost, no contiene credenciales ni endpoints de broker y ejecuta la entrada canónica como subproceso observable. La UI separa cotizaciones online dependientes de disponibilidad, señales locales, métricas históricas y gate de promoción para evitar que una degradación de fuente se presente como certeza.

`src/nexus_data/` contiene la adquisición point-in-time. El conector ALFRED consulta fechas de vintage y observaciones con un período de tiempo real exacto, escribe snapshots inmutables bajo `runtime/vintages/` y mantiene el gate cerrado hasta completar todas las series. La clave FRED sólo se lee desde el entorno.

`src/nexus_core/scenarios.py` concentra cálculos de escenarios auditables. La sensibilidad a costos conserva la misma ventana y cambia sólo el costo aplicado al turnover; el shock de cartera es lineal, de un período y con pesos fijos. La UI no recalibra modelos ni convierte estos diagnósticos en órdenes.

## Universo actual
- QQQ: tecnología/growth EE.UU.
- ECH: Chile.
- CPER: cobre.

## Benchmark
Cartera de referencia simple sobre los tres instrumentos. Su función es medir si la complejidad del modelo agrega valor; no es un motor predictivo.
