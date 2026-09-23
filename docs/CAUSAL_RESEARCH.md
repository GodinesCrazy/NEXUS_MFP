# Investigación causal — marco de trabajo

## Objetivo
Distinguir una relación predictiva de una causa candidata útil.

Una causa candidata debe satisfacer:

1. **Temporalidad:** el dato estaba disponible antes del retorno que se intenta predecir.
2. **Mecanismo:** existe una vía económica plausible de transmisión.
3. **Repetición:** el signo/efecto aparece en múltiples subperiodos.
4. **Endogeneidad:** la relación con retornos futuros debe dominar explicaciones de reacción a retornos ya ocurridos.
5. **Validation:** sobrevive en años no usados para descubrirla.
6. **Future OOS:** mantiene señal en un periodo completamente futuro.
7. **Incrementalidad:** mejora un baseline técnico; de lo contrario no obtiene capital.

## Controles implementados en Methodology Foundation

- Los últimos `h+1` registros de cada partición se purgan por posición en el calendario real de sesiones.
- Discovery y validation registran número de hipótesis y q-values Benjamini-Hochberg.
- Cada driver debe superar un placebo por desplazamiento circular además de los filtros de temporalidad y signo.
- La historia revisada actual se identifica como no point-in-time y bloquea promoción.
- Cada corrida causal guarda hashes de entrypoint, inputs y matrices de drivers.

Los p-values de Spearman y FDR se consideran filtros de screening, no prueba causal definitiva. La siguiente capa debe incorporar inferencia robusta a dependencia serial mediante block bootstrap/permutaciones por bloques.

## Hipótesis actuales

### QQQ
- inflación/tasas reales -> descuento de flujos -> valoración growth;
- Fed/curva -> costo de capital y expectativas de ciclo;
- crédito/NFCI/VIX -> prima de riesgo;
- revisiones/sorpresas macro -> expectativas de beneficios.

### CPER
- actividad China -> demanda física esperada;
- inventarios/oferta minera -> disponibilidad física;
- dólar/tasas -> componente financiero del commodity;
- CFTC -> posicionamiento/expectativas;
- shocks no explicados por China/USD/rates -> candidatos a oferta/inventarios/eventos específicos.

### ECH
- cobre -> términos de intercambio/CLP/actividad Chile;
- China -> cobre y exportaciones;
- USD/CLP -> valoración local y condiciones financieras;
- riesgo global -> flujos de capital;
- diferencial de tasas -> moneda y valoración.

## Regla de lenguaje
Hasta tener identificación causal fuerte, llamar a estos factores **causas candidatas** o **drivers causales candidatos**, no “causas demostradas”.
