# AGENTS.md — Reglas para Codex en NEXUS-MFP

## Objetivo
Evolucionar un sistema de investigación financiera reproducible que busque relaciones predictivas y causas candidatas para QQQ, ECH y CPER, manteniendo separación estricta entre investigación histórica, paper-forward y cualquier eventual uso real.

## Estado base obligatorio
- Champion congelado: `v1.7-FROZEN`.
- Mejor Challenger verificado al migrar: `v1.14 Adaptive Fusion`.
- Línea activa: `v1.19 Causal Driver Discovery Engine`.
- Entrada canónica: `src/nexus_mfp.py`.
- No ejecutar operaciones reales.

## Reglas no negociables
1. **No leakage:** una decisión en fecha T sólo puede usar información disponible en o antes de T, considerando retrasos reales de publicación.
2. **Walk-forward real:** discovery, validation y future/OOS deben permanecer separados.
3. **Ventana común:** toda comparación de capital, Sharpe y drawdown debe usar exactamente las mismas fechas.
4. **Costos:** incluir costos de transacción y turnover cuando corresponda.
5. **Champion congelado:** no sobrescribir v1.7-FROZEN. Toda mejora nace como Challenger.
6. **Promoción por evidencia:** un motor nuevo empieza con peso 0 salvo que su OOS previo demuestre mejora incremental.
7. **Proveniencia:** registrar fuente, variable, frecuencia, retraso de publicación y fallback. Un proxy nunca debe presentarse como dato original.
8. **Causalidad prudente:** usar “causa candidata” salvo identificación causal fuerte. Exigir temporalidad + mecanismo + repetición + validación + future OOS + placebo/endogeneity checks.
9. **No p-hacking:** registrar número de pruebas y usar controles por múltiples comparaciones cuando se busquen muchas señales.
10. **Reproducibilidad:** guardar configuración, semilla, versión, hashes y métricas de cada corrida relevante.
11. **No ocultar fallos de fuente:** si FRED/CFTC/otra fuente falla, mostrarlo claramente y marcar qué proxy se usó.
12. **No optimizar sólo Sharpe:** comparar retorno, CAGR, Sharpe, max drawdown, volatilidad, estabilidad anual y sensibilidad a costos.

## Flujo recomendado para cada nueva versión
1. Formular una hipótesis concreta.
2. Identificar mecanismo económico y disponibilidad temporal de cada dato.
3. Implementar como motor Challenger separado.
4. Ejecutar nested walk-forward.
5. Comparar contra v1.7, v1.14 y benchmark en ventana común.
6. Ejecutar placebos/lead-lag/endogeneity checks.
7. Guardar resultados en `runtime/<version>/`.
8. Actualizar `docs/CURRENT_STATE.md` y `CHANGELOG.md`.
9. No promover si la mejora no es robusta.

## Arquitectura
Codex puede modularizar el código para mejorar mantenibilidad, pero debe conservar:
- un comando único para ejecutar el sistema completo;
- compatibilidad con Python 3.10/Windows;
- posibilidad de reconstruir los resultados históricos;
- archivos históricos intactos bajo `src/history/`.

## Prioridad de investigación actual
Desarrollar el Causal Driver Engine para separar:
- shock de tasas/descuento;
- sorpresa macro/expectativas;
- shock de demanda China;
- shock de cobre por oferta/no-demanda;
- posicionamiento CFTC;
- USD/CLP y condiciones financieras;
- noticias/eventos con resultado posterior medible.

La pregunta central no es “¿qué correlaciona?”, sino “¿qué información conocida primero antecede repetidamente al movimiento futuro y conserva valor OOS?”.
