# Bitácora del grupo — TP4

> Registrar acá el avance: qué hizo cada integrante, decisiones tomadas y pendientes.
> Esto ayuda a coordinar el trabajo y deja evidencia de la participación de todos.

---

## 👥 Integrantes

| Nombre | Usuario de GitHub | Rol en el grupo |
|--------|-------------------|-----------------|
|        |                   |                 |
|        |                   |                 |
|        |                   |                 |
|        |                   |                 |

## 🎯 Proyecto

- **Modalidad:** B — Artículo de Revisión del Estado del Arte
- **Tema:** Observabilidad inteligente en redes: del monitoreo reactivo al AIOps predictivo (OpenTelemetry, eBPF y ML)
- **Problema/objetivo:** El monitoreo por umbrales detecta los incidentes tarde y no explica su causa. Revisamos la evolución de la telemetría de red (SNMP → NetFlow/IPFIX → gNMI → OpenTelemetry → eBPF) y las innovaciones de AIOps (detección de anomalías con ML, RCA con LLM), con foco en el impacto sobre la seguridad de red.
- **Trabajo previo:** se reutiliza parcialmente IntellOps (GIDAS, UTN FRLP) — investigación de estado del arte y detector de anomalías — citado como referencia.

## 🎬 Demo (estación de la Feria)

Guion en 3 actos, ~4 min, 100 % offline (docker-compose):

1. **Monitoreo tradicional** — Prometheus + Grafana con métricas de red en verde.
2. **Incidente** — se inyecta tráfico anómalo (port scan / pico de latencia); los umbrales no lo detectan, el detector ML sí.
3. **Explicación** — un LLM local explica la causa raíz. Escenario de falla preparado: OTel Collector sin mTLS.

Plan B: video grabado + capturas en `capturas/`.

## 📅 Cronograma hasta la Feria (17/11)

| Fecha | Documento | Demo | Póster / presentación |
|-------|-----------|------|-----------------------|
| 9–10/11 | Esqueleto + referencias base + línea de tiempo | Acto 1: compose base (Prometheus, Grafana, exporters, OTel Collector) | Roles definidos |
| 11–12/11 | Secciones 2 (estado del arte) y 3 (innovaciones) | Acto 2: inyección de anomalía + detector ML | — |
| 13/11 | Secciones 4, 5 y resumen | Acto 3: RCA con LLM local + escenario de falla mTLS | Borrador del póster |
| 14/11 | Revisión cruzada | **Freeze** de la demo, ensayo 1, grabar plan B | Póster v1 |
| 15/11 | PDF final | Ensayo 2 | Póster final (editable + PDF) |
| 16/11 | — | Ensayo 3 con cronómetro | Imprimir póster, checklist completo |
| **17/11** | **Feria de Redes** | | |

## 🗓️ Registro de avance

| Fecha | Qué se hizo | Quién | Commit |
|-------|-------------|-------|--------|
|       |             |       |        |

## 🚧 Pendientes / decisiones

- [x] Definir tema definitivo
- [x] Elegir modalidad (A, B o C)
- [ ] Sumar integrantes y docentes (`ofalabel`, `rodriguezemautn`) como colaboradores
- [ ] Asignar roles (quién escribe el documento, quién arma la demo, quién el póster)

## 📝 Notas

- Ideas, dudas para el docente, riesgos, etc.
