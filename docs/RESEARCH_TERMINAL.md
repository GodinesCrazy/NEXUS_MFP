# NEXUS Research Terminal

## Objetivo

La terminal convierte la cadena de investigación en un sistema observable para usuarios no técnicos, sin mezclar investigación con ejecución real. La interfaz debe responder cuatro preguntas:

1. ¿Qué está haciendo NEXUS ahora?
2. ¿Qué evidencia y fuentes está usando?
3. ¿Qué exposición paper sugiere para QQQ, ECH y CPER?
4. ¿Por qué un motor puede o no recibir peso?

## Arquitectura de la primera fase

- `nexus_ui.server`: servidor HTTP local, enlazado sólo a `127.0.0.1`.
- `DashboardRepository`: lectura de los artefactos más recientes con fallback a outputs históricos.
- `MarketCache`: actualización asíncrona de Yahoo Finance, cache local en memoria y fallo visible.
- `RunManager`: una sola ejecución de NEXUS a la vez, como subproceso sin shell.
- `RunProgress`: fases monotónicas, objetivo actual, PID, timestamps, código de salida y consola.
- HTML/CSS/JavaScript nativo: no depende de CDN ni transmite archivos o credenciales.

## Contrato de la señal visible

La columna `Acción` compara el peso objetivo del Champion con el peso actual de la cartera paper:

- `AUMENTAR`: diferencia superior a 2 puntos porcentuales;
- `REDUCIR`: diferencia inferior a -2 puntos porcentuales;
- `MANTENER`: diferencia dentro de esa banda.

No se presenta como orden ni asesoría. La UI muestra permanentemente `PAPER ONLY`, no contiene integración con brokers y el servidor no expone endpoints de compra/venta.

## Datos online

Las cotizaciones QQQ, ECH y CPER se solicitan en segundo plano a Yahoo Finance con intervalo de 5 minutos y timeout. Deben interpretarse como datos retrasados y dependientes de disponibilidad, no como market data institucional. Cada snapshot incluye proveedor, timestamp y estado; si falla, la interfaz conserva la señal local y muestra la degradación.

## Observabilidad

La barra representa hitos reales emitidos por la cadena, no una estimación de tiempo. Es monotónica y separa Champion, Forward, eventos, discovery, fusión, causal y cierre. El porcentaje 100 sólo aparece con código de salida 0. Un fallo conserva logs y nunca promueve un motor.

## Explicabilidad por activo

QQQ, ECH y CPER disponen de una ficha seleccionable con exposición actual, objetivo, diferencia y componentes del ensemble. La intensidad de asignación no se etiqueta como confianza ni probabilidad. Si `current_causal_drivers.csv` no contiene evidencia promovible, la ficha declara 0% causal en lugar de construir una narrativa retrospectiva.

## Ingesta ALFRED

`src/nexus_data/alfred.py` usa los endpoints oficiales de observaciones y fechas de vintage de FRED/ALFRED. Cada snapshot separa:

- `retrieved_at_utc`: momento real de descarga;
- `knowledge_at_utc`: momento histórico declarado por ALFRED;
- `source_vintage_date`: fecha de vintage de la fuente;
- hash SHA-256 del contenido y política de lag.

La ingesta es incremental mediante `vintages.ps1`. Los estados `credential_missing`, `partial` y cualquier error son fail-closed. Sólo `ready`, con todas las series completas, puede satisfacer esta parte del gate; aun así siguen siendo necesarios walk-forward, bootstrap y los demás controles.

## Roadmap profesional

### Fase 2 — point-in-time y estadística (infraestructura ejecutada)

- almacén inmutable de snapshots propios y consulta `as_of` implementados;
- block bootstrap emparejado y gate fail-closed implementados;
- poblar vintages ALFRED y snapshots históricos verificables (pendiente de datos);
- calendarios de publicación por serie;
- estabilidad por régimen;
- presupuestos de hipótesis por familia.

### Fase 3 — terminal analítica (primera entrega ejecutada)

- detalle por activo y componentes de asignación implementado;
- estado causal vacío explícito, sin narrativa inventada;
- detalle por horizonte y waterfall causal (pendiente de evidencia OOS);
- comparación de escenarios y sensibilidad a costos;
- alertas locales de fuentes, drift y vencimiento de evidencia.

### Fase 4 — operación paper multiusuario

- autenticación local/privada y roles;
- persistencia de jobs y eventos;
- WebSocket/SSE para logs de alta frecuencia;
- despliegue privado con observabilidad y backups.

No se contempla trading real hasta una autorización separada, revisión de seguridad, controles regulatorios, kill switch y validación paper prolongada.
