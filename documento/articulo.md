<!--
ESQUELETO DEL ARTÍCULO — Modalidad B (Estado del Arte)
Estado: SKELETON. Cada sección tiene (1) la extensión objetivo del template como comentario y (2) un esquema de argumentos a redactar.
Convención: [n] = referencia numerada de la sección "Referencias" (formato IEEE). Todas las referencias de la lista fueron verificadas en línea
(ver nota de verificación al final del archivo). No agregar referencias sin verificar título, autores, año y URL.
Formato de entrega (template-documento.md): A4, márgenes 2.5 cm, Times New Roman/Arial 12 pt, interlineado 1.5, 5-7 páginas, PDF, español.
Presupuesto aproximado: 12 pt con interlineado 1.5 ≈ 350-400 palabras por página (sin tablas/figuras).
-->

# Observabilidad inteligente en redes: del monitoreo reactivo al AIOps predictivo (OpenTelemetry, eBPF y ML)

![UTN Logo]

**Universidad Tecnológica Nacional** — Facultad Regional La Plata

**Carrera:** [Ingeniería en Sistemas / Ingeniería Electrónica / según corresponda]

**Cátedra:** Gestión Operativa y Seguridad en Redes

**Trabajo Práctico N.º 4** — Proyecto Integrador

**Modalidad:** B — Artículo de Revisión del Estado del Arte

**Grupo:** [Nombre del grupo]

**Integrantes:**
- [Apellido, Nombre]
- [Apellido, Nombre]
- [Apellido, Nombre]
- [Apellido, Nombre]

**Fecha de entrega:** [Fecha]

---

## Resumen

<!-- Extensión objetivo: 100-150 palabras. Debe leerse de forma independiente al resto del artículo. Redactar AL FINAL, cuando las secciones 2-5 estén cerradas. -->

Esquema (una frase por punto, en este orden):

- Problema: el monitoreo por umbrales detecta tarde y no explica la causa; la red y los servicios son cada vez más dinámicos (contenedores, microservicios).
- Alcance: evolución de la telemetría de red (SNMP, NetFlow/IPFIX, gNMI, OpenTelemetry, eBPF) y de la operación (detección de anomalías con ML, RCA asistido por LLM).
- Hallazgos del estado del arte: convergencia hacia OpenTelemetry/OTLP como estándar de transporte y eBPF como fuente de datos sin instrumentación; madurez reciente de los proyectos (graduaciones CNCF, RFC 9669).
- Seguridad: las anomalías son señales de ataque (escaneo de puertos, exfiltración) y el propio pipeline de telemetría es superficie de ataque (PII en trazas, falta de mTLS en el Collector).
- Oportunidades: detección predictiva explicable, LLM locales con verificación, privacidad por diseño en telemetría.
- Palabras clave: observabilidad, AIOps, OpenTelemetry, eBPF, detección de anomalías, seguridad de red.

## 1. Introducción

<!-- Extensión objetivo: ½ página (~180-200 palabras). Incluye párrafo explícito de seguridad (el tema debe cubrir Redes, Operación y Seguridad). -->

- **Contexto (Redes):** la red dejó de ser un conjunto de dispositivos estáticos; hoy conviven tráfico este-oeste entre contenedores, overlays y servicios efímeros donde un contador de interfaz no alcanza.
- **Problema (Operación):** el monitoreo reactivo (umbrales estáticos tipo Nagios/Zabbix) produce ruido de alertas, no correlaciona señales y no explica causas [10]. Un incidente "sutil" (degradación gradual, patrón atípico dentro de rangos aceptables) no cruza ningún umbral.
- **Por qué importa hoy:** estándares abiertos (OpenTelemetry, OTLP) y captura en kernel (eBPF) bajaron el costo de observar; ML y LLM prometen pasar de "avisar" a "anticipar y explicar".
- **Seguridad (párrafo obligatorio):** (a) la telemetría es sensor de seguridad (flujos y syscalls revelan escaneos, movimiento lateral, exfiltración); (b) el pipeline de observabilidad es un activo crítico con datos sensibles (PII en atributos de trazas, credenciales en logs) y un punto de ataque si el Collector acepta tráfico sin TLS/mTLS [18].
- **Objetivo:** revisar el estado del arte y las innovaciones 2023-2026, identificar brechas, y mostrar un caso mínimo reproducible (demo de la Feria) que ilustra el contraste umbral vs. ML.
- **Estructura:** una oración por sección (2: estado del arte y Tabla 1; 3: innovaciones; 4: oportunidades; 5: conclusiones).
- **Trabajo previo:** se reutiliza la investigación de IntellOps (GIDAS, UTN FRLP) [25] como antecedente; se cita, no se reproduce.

## 2. Estado del arte

<!-- Extensión objetivo: 1½-2 páginas (~600-750 palabras + tabla). OBLIGATORIO: tabla comparativa o línea de tiempo (Tabla 1 abajo). -->

### 2.1. Evolución de la telemetría de red

Texto introductorio (3-4 líneas): la progresión no es un reemplazo sino una acumulación de capas; cada una resolvió una limitación de la anterior y abrió un nuevo problema de seguridad. Remitir a la Tabla 1 y a la Figura 1.

Tabla 1: Evolución de la telemetría de red y la observabilidad (de monitoreo reactivo a AIOps)

| Era / año | Tecnología (referencia) | Modelo | Granularidad | Qué resuelve | Limitación | Implicancia de seguridad |
|-----------|-------------------------|--------|--------------|--------------|------------|--------------------------|
| 1988-1990 (SNMPv1: RFC 1157, mayo 1990) [1] | SNMP v1/v2c | Pull (polling del NMS al agente, UDP) + traps asíncronos | Contadores de interfaz/dispositivo (MIB), sondeo típico de minutos | Gestión y monitoreo estandarizado y multi-vendor de dispositivos | Sin contexto de flujo ni de aplicación; el polling pierde picos entre muestras; MIBs rígidas | Autenticación débil basada en "community string" en texto claro; superficie de exposición si se deja abierto en la red |
| 2002 (SNMPv3: RFC 3411-3418) [2] | SNMPv3 (STD 62) | Pull + traps/informs | Igual que v1/v2c | Agrega autenticación y privacidad al mensaje (modelo de seguridad basado en usuario) y control de acceso por vista | Complejidad de configuración; sigue limitada al modelo de polling y a MIBs | Mejora el control de acceso y la confidencialidad del canal de gestión; su adopción real es desigual |
| 2004 (NetFlow v9: RFC 3954) [3] → 2013 (IPFIX: RFC 7011, STD 77) [4] | NetFlow v9 / IPFIX | Push (el exportador envía registros de flujo al colector) | Flujo (5-tupla + contadores), basado en plantillas | Visibilidad de quién habla con quién y cuánto, sin captura de paquetes completos | Sin contenido ni semántica de aplicación; muestreo y timeouts de caché retrasan/atenúan eventos | Base para forense y detección de escaneos, DDoS y exfiltración; el canal de exportación requiere protegerse (TLS/DTLS en IPFIX) |
| Mediados de 2010s (OpenConfig; spec v0.10.0, mayo 2023) [6] | gNMI / telemetría en streaming | Push por suscripción (STREAM con ON_CHANGE o SAMPLE sobre gRPC) | Hoja del modelo YANG, intervalos de nanosegundos o por cambio | Telemetría de baja latencia, modelada y orientada a eventos; unifica configuración y telemetría | Requiere soporte del equipamiento y modelos YANG/OpenConfig; cubre dispositivos, no aplicaciones | Canal gRPC con TLS y autenticación por RPC; amplía la superficie de gestión (acceso de escritura vía Set) |
| 2019-presente (proyecto CNCF; OTLP con trazas, métricas y logs estables) [7][24] | OpenTelemetry (OTLP) | Push (SDK/agente → Collector → backend), con opción de pull vía receptores | Señal de aplicación: traza/span, métrica con atributos, log correlacionado | Estándar abierto y vendor-neutral para métricas, trazas y logs correlacionados; el Collector desacopla fuente de destino | Instrumentación del código o agentes; cardinalidad y costo; el perfilado aún está en desarrollo | El Collector concentra datos sensibles: requiere TLS/mTLS, redacción de PII y endpoints acotados [18] |
| 2014-presente (eBPF en Linux; ISA estandarizada en RFC 9669, oct. 2024) [5][8] | eBPF (Cilium/Hubble, Tetragon, Falco, OBI) | Push desde el kernel hacia agentes en espacio de usuario | Evento de kernel: syscall, paquete, conexión, proceso | Observabilidad de red y de seguridad sin modificar aplicaciones ni cargar módulos del kernel, con verificación previa del programa | Requiere kernel/privilegios adecuados; dificultad de depuración; el verificador acota pero no elimina el riesgo | Visibilidad profunda y enforcement en línea [16][17]; los programas eBPF con privilegios son a su vez un vector a controlar |
| 2019-presente (AIOps; relevamiento en 2021) [10][9] | AIOps (detección de anomalías con ML; RCA asistido por LLM) | Analítica sobre datos ya recolectados (batch o casi tiempo real) | Serie temporal por métrica y correlación entre señales | Detecta patrones sutiles que no cruzan umbrales; reduce ruido; propone causa raíz | Falsos positivos, falta de explicabilidad, necesidad de datos etiquetados; los LLM pueden alucinar [13] | Las anomalías son señales de ataque; el modelo y sus datos de entrenamiento son un nuevo activo a proteger (envenenamiento, fuga de datos) |

Notas para la redacción de la tabla:
- Verificar el año de la primera versión de gNMI y el año de introducción de eBPF en el kernel antes de entregar (la tabla usa rangos prudentes; los años exactos no están respaldados por una de las referencias verificadas).
- Mantener la Tabla 1 en una sola hoja (fuente 9-10 pt es aceptable en tablas; el texto corrido va en 12 pt).

### 2.2. Herramientas dominantes en la industria

- **Métricas y alertas:** Prometheus (modelo pull, PromQL, reglas de alerta por umbral) + Grafana (visualización); blackbox_exporter para sondeo activo (HTTP, TCP, ICMP) y node_exporter para el host. Es el baseline "tradicional" que usa el Acto 1 de la demo.
- **Telemetría unificada:** OpenTelemetry (SDK + Collector, OTLP) con backends Jaeger/Tempo/Loki; el Collector expone sus propias métricas a Prometheus.
- **eBPF en redes y seguridad:** Cilium + Hubble (observabilidad de flujos L3-L7 y políticas de red) [16], Tetragon (observabilidad y enforcement de runtime en kernel) [17], Falco (detección de amenazas en tiempo de ejecución).
- **Plataformas comerciales vs. abiertas:** Datadog, Dynatrace (Davis AI), New Relic, Splunk frente a Grafana/Prometheus/Loki, SigNoz, OpenObserve, Netdata (tomar la comparación de IntellOps [25] y citarla como análisis propio de ese proyecto, no como dato verificado de mercado: los costos del cuadro de IntellOps son estimaciones y no deben citarse como cifras).
- **Detección de anomalías en producción:** Isolation Forest [14] como técnica liviana y no supervisada para series de métricas; alternativas: descomposición estacional, z-score dinámico, autoencoders.

### 2.3. Limitaciones del estado actual

- Umbrales estáticos: no se adaptan a estacionalidad (picos horarios) ni detectan degradación gradual o cambios de correlación entre métricas ("anomalías dentro del rango").
- Silos de datos: SNMP, flujos, métricas, trazas y logs viven en herramientas distintas; la correlación es manual y lenta (MTTR alto) [9][10].
- Costo y cardinalidad de OpenTelemetry a escala; instrumentación manual de aplicaciones heredadas.
- Brecha en explicabilidad: un score de anomalía no es una causa raíz; el operador no experto no sabe qué hacer con él.
- Seguridad de la propia telemetría: endpoints OTLP abiertos, PII en atributos, ausencia de mTLS [18].

### 2.4. Figura 1 (diagrama original, obligatorio en el template)

- Figura 1: línea de tiempo/arquitectura (a dibujar en `diagramas/` como SVG): fuentes de telemetría (dispositivos, hosts/kernel, aplicaciones) → OTel Collector → Prometheus/Grafana → detector ML → explicación LLM. Alt text y leyenda numerada ("Figura 1: ...").
- Si el tiempo no alcanza, la Tabla 1 cumple el requisito de línea de tiempo/tabla comparativa; la figura cubre el requisito de "al menos un diagrama original".

## 3. Innovaciones emergentes

<!-- Extensión objetivo: 1-1½ páginas (~400-550 palabras). Papers y anuncios de los últimos 3 años (2023-2026). Cada ítem: qué es, por qué es innovador, qué problema resuelve, referencia verificada. -->

Criterio de selección: solo se listan hitos con fuente verificada; el resto del material de IntellOps [25] se usa como contexto, no como evidencia de innovación.

1. **Perfilado continuo como cuarta señal de OpenTelemetry (2024-2026).** Anuncio de soporte de profiling en 2024 (modelo de datos de perfiles enlazado a trazas/métricas/logs; donación del agente eBPF de Elastic y del perfilador .NET de Splunk) [19]; la señal de perfiles llegó a alfa pública en 2026 y todavía no es apta para producción crítica [20]. Problema que resuelve: pasar del síntoma (latencia alta) al código responsable sin instrumentación manual. Limitación: estado alfa.
2. **OpenTelemetry eBPF Instrumentation (OBI), mayo 2025.** Grafana donó Beyla a OpenTelemetry: instrumentación de aplicaciones compiladas sin recompilar ni cambiar código, con métricas HTTP, trazas distribuidas, métricas de red y soporte de gRPC, SQL, Redis y Kafka [21]. Problema que resuelve: observabilidad "zero-code" de servicios heredados y de terceros. Conecta eBPF con el estándar OTLP (convergencia de dos líneas de la Tabla 1).
3. **Estandarización del ISA de BPF (RFC 9669, octubre 2024).** El IETF publicó el conjunto de instrucciones de BPF como Proposed Standard [5]. Por qué importa: portabilidad entre sistemas operativos y plataformas, y base común para herramientas de verificación y seguridad.
4. **Madurez institucional del ecosistema (CNCF).** Cilium se graduó en octubre de 2023 [22], Falco en febrero de 2024 (requirió auditoría de seguridad de terceros) [23] y OpenTelemetry en mayo de 2026 [24]. Lectura crítica: la graduación indica adopción y gobernanza, no ausencia de riesgos; conectar con la sección de seguridad.
5. **LLM para RCA de incidentes (2023-2025).** Ahmed et al. evaluaron LLM para recomendar causa raíz y mitigación sobre más de 40 000 incidentes de Microsoft [11]; RCACopilot (EuroSys 2024) combina recolección de diagnósticos con un LLM para predecir la categoría de causa raíz y redactar la explicación [12]; el benchmark OpenRCA (ICLR 2025, 335 fallas, más de 68 GB de telemetría) muestra que, aun con un agente diseñado a medida, el mejor modelo resolvió solo el 11,34 % de los casos [13]. Lectura crítica: el RCA con LLM es prometedor pero está lejos de ser confiable sin verificación humana; justifica el diseño del Acto 3 (LLM local que explica con evidencia de las métricas, y el operador decide).
6. **Seguridad de la telemetría como tema emergente.** Guías oficiales de OpenTelemetry sobre endpoints acotados, cifrado/autenticación y procesador `redaction` para enmascarar datos sensibles antes de exportar [18]; enforcement en kernel con Tetragon (filtros y acciones dentro del kernel, no solo alertas) [17]. Conectar con el escenario de falla de la demo (Collector sin mTLS).

Cierre de la sección (2-3 líneas): patrón común = convergencia (eBPF + OTLP), menos instrumentación manual, y analítica asistida con límites conocidos.

## 4. Oportunidades y desafíos

<!-- Extensión objetivo: 1 página (~350-400 palabras). Problemas abiertos, brechas, oportunidades de investigación y desarrollo profesional. Conectar con el perfil de la carrera. -->

- **Detección predictiva y explicable:** pasar de "anomalía detectada" a "causa probable y evidencia"; evaluación honesta (datos sintéticos vs. reales; los F1 de datos sintéticos sirven para comparar modelos, no para prometer rendimiento de producción; ver limitaciones del generador sintético de IntellOps [25]).
- **LLM local y verificable:** modelos cuantizados corriendo en CPU/edge, sin enviar telemetría a APIs externas (privacidad y costo); necesidad de anclar la respuesta en evidencia (métricas y trazas) y de medir alucinaciones [13].
- **Seguridad del pipeline de observabilidad:** mTLS entre agentes y Collector, redacción de PII por diseño, minimización de datos, control del privilegio de los agentes eBPF; amenaza de "envenenamiento" de métricas que engaña al detector.
- **Brechas de datos:** falta de datasets públicos etiquetados de tráfico de red combinado con métricas de aplicación; costo de etiquetar incidentes.
- **Estandarización incompleta:** perfiles en alfa; convenciones semánticas aún en evolución; interoperabilidad con telemetría de dispositivos de red (SNMP/gNMI → OTLP).
- **Hardware modesto / entornos académicos:** operar la solución con pocos recursos y costo cero (nicho identificado por IntellOps [25]).
- **Perfil profesional (conexión con la carrera):** roles de SRE/NetDevOps/seguridad de redes; habilidades: modelado de datos de red, Linux/eBPF, Prometheus/OpenTelemetry, fundamentos de ML y de seguridad. Mencionar oportunidades de investigación y de proyectos finales.

## 5. Conclusiones

<!-- Extensión objetivo: ½ página (~180-200 palabras). Síntesis, proyección 3-5 años, impacto esperado en redes, operación y seguridad. -->

- **Síntesis:** la telemetría evolucionó de contadores por polling a eventos de kernel y señales correlacionadas con estándares abiertos; la analítica (ML y LLM) agrega valor donde los umbrales fallan, con límites medidos (11,34 % en OpenRCA [13]).
- **Hallazgo central:** observabilidad y seguridad convergen: los mismos datos sirven para operar y para detectar ataques, y el pipeline de telemetría debe tratarse como activo crítico.
- **Proyección 3-5 años (marcar como proyección propia, no como dato):** consolidación de OTLP y de OBI como base común; perfiles estables; detección de anomalías integrada en el Collector o en la plataforma; LLM locales como asistentes de diagnóstico con verificación.
- **Impacto esperado:** Redes (visibilidad L3-L7 sin instrumentar), Operación (menor MTTR, menos ruido), Seguridad (detección temprana y telemetría protegida con mTLS y redacción).
- **Cierre:** vínculo con la demo de la Feria (Acto 1 verde pero ciego, Acto 2 detección por ML, Acto 3 explicación y falla de mTLS) como evidencia de que el contraste umbral vs. ML es reproducible con recursos mínimos.

## Referencias

<!-- Mínimo 6 exigidas por el template (modalidad B): aquí 25, todas verificadas. Incluye >=1 paper académico ([9]-[15]), >=1 documentación técnica oficial ([8], [16]-[18]) y >=1 RFC ([1]-[5]). Formato IEEE consistente. "Accedido" = fecha de verificación. -->

[1] J. D. Case, M. Fedor, M. L. Schoffstall y J. Davin, "Simple Network Management Protocol (SNMP)," IETF, RFC 1157, may. 1990. [En línea]. Disponible: https://datatracker.ietf.org/doc/html/rfc1157

[2] D. Harrington, R. Presuhn y B. Wijnen, "An Architecture for Describing Simple Network Management Protocol (SNMP) Management Frameworks," IETF, RFC 3411 (STD 62), dic. 2002. [En línea]. Disponible: https://datatracker.ietf.org/doc/html/rfc3411

[3] B. Claise, Ed., "Cisco Systems NetFlow Services Export Version 9," IETF, RFC 3954, oct. 2004. [En línea]. Disponible: https://datatracker.ietf.org/doc/html/rfc3954

[4] B. Claise, Ed., B. Trammell, Ed. y P. Aitken, "Specification of the IP Flow Information Export (IPFIX) Protocol for the Exchange of Flow Information," IETF, RFC 7011 (STD 77), sep. 2013. [En línea]. Disponible: https://datatracker.ietf.org/doc/html/rfc7011

[5] D. Thaler, Ed., "BPF Instruction Set Architecture (ISA)," IETF, RFC 9669, oct. 2024. [En línea]. Disponible: https://datatracker.ietf.org/doc/html/rfc9669

[6] OpenConfig, "gRPC Network Management Interface (gNMI)," especificación v0.10.0, 25 may. 2023. [En línea]. Disponible: https://github.com/openconfig/reference/blob/master/rpc/gnmi/gnmi-specification.md

[7] OpenTelemetry Authors, "OTLP Specification 1.11.1," OpenTelemetry. [En línea]. Disponible: https://opentelemetry.io/docs/specs/otlp/ (accedido nov. 2026).

[8] eBPF.io, "What is eBPF? An Introduction and Deep Dive into the eBPF Technology." [En línea]. Disponible: https://ebpf.io/what-is-ebpf/ (accedido nov. 2026).

[9] P. Notaro, J. Cardoso y M. Gerndt, "A Survey of AIOps Methods for Failure Management," *ACM Trans. Intell. Syst. Technol.*, vol. 12, n.º 6, art. 81, nov. 2021, doi: 10.1145/3483424.

[10] Y. Dang, Q. Lin y P. Huang, "AIOps: Real-World Challenges and Research Innovations," en *Proc. IEEE/ACM 41st Int. Conf. Softw. Eng.: Companion Proceedings (ICSE-Companion)*, Montreal, Canadá, 2019, pp. 4-5, doi: 10.1109/ICSE-Companion.2019.00023.

[11] T. Ahmed, S. Ghosh, C. Bansal, T. Zimmermann, X. Zhang y S. Rajmohan, "Recommending Root-Cause and Mitigation Steps for Cloud Incidents using Large Language Models," en *Proc. 45th Int. Conf. Softw. Eng. (ICSE)*, 2023, arXiv:2301.03797. [En línea]. Disponible: https://arxiv.org/abs/2301.03797

[12] Y. Chen *et al.*, "Automatic Root Cause Analysis via Large Language Models for Cloud Incidents," en *Proc. 19th European Conf. Computer Systems (EuroSys '24)*, Atenas, Grecia, abr. 2024, doi: 10.1145/3627703.3629553, arXiv:2305.15778.

[13] J. Xu *et al.*, "OpenRCA: Can Large Language Models Locate the Root Cause of Software Failures?," en *Proc. Int. Conf. Learning Representations (ICLR)*, 2025. [En línea]. Disponible: https://proceedings.iclr.cc/paper_files/paper/2025/file/d29b8d53678015079e1d245c023e49d2-Paper-Conference.pdf

[14] F. T. Liu, K. M. Ting y Z.-H. Zhou, "Isolation Forest," en *Proc. 8th IEEE Int. Conf. Data Mining (ICDM)*, Pisa, Italia, 2008, pp. 413-422, doi: 10.1109/ICDM.2008.17.

[15] C. Cassagnes, L. A. Trestioreanu, C. Joly y R. State, "The rise of eBPF for non-intrusive performance monitoring," en *Proc. NOMS 2020 - IEEE/IFIP Network Operations and Management Symposium*, Budapest, Hungría, abr. 2020. [En línea]. Disponible: https://orbilu.uni.lu/handle/10993/43564

[16] Cilium Authors, "Introduction to Cilium & Hubble," Cilium Documentation. [En línea]. Disponible: https://docs.cilium.io/en/stable/overview/intro/ (accedido nov. 2026).

[17] Tetragon Authors, "Overview | Tetragon - eBPF-based Security Observability and Runtime Enforcement," Tetragon Documentation. [En línea]. Disponible: https://tetragon.io/docs/overview/ (accedido nov. 2026).

[18] OpenTelemetry Authors, "Collector configuration best practices," OpenTelemetry Documentation. [En línea]. Disponible: https://opentelemetry.io/docs/security/config-best-practices/ (accedido nov. 2026).

[19] OpenTelemetry Authors, "OpenTelemetry announces support for profiling," OpenTelemetry Blog, 2024. [En línea]. Disponible: https://opentelemetry.io/blog/2024/profiling/ (accedido nov. 2026).

[20] OpenTelemetry Authors, "OpenTelemetry Profiles Enters Public Alpha," OpenTelemetry Blog, 2026. [En línea]. Disponible: https://opentelemetry.io/blog/2026/profiles-alpha/ (accedido nov. 2026).

[21] N. Grcevski, "Introducing OpenTelemetry eBPF Instrumentation: Why we donated Grafana Beyla to OpenTelemetry," Grafana Labs Blog, 8 may. 2025. [En línea]. Disponible: https://grafana.com/blog/2025/05/07/opentelemetry-ebpf-instrumentation-beyla-donation/

[22] Cloud Native Computing Foundation, "Cloud Native Computing Foundation Announces Cilium Graduation," 11 oct. 2023. [En línea]. Disponible: https://cncf.io/announcements/2023/10/11/cloud-native-computing-foundation-announces-cilium-graduation/

[23] Cloud Native Computing Foundation, "Cloud Native Computing Foundation Announces Falco Graduation," 29 feb. 2024. [En línea]. Disponible: https://cncf.io/announcements/2024/02/29/cloud-native-computing-foundation-announces-falco-graduation

[24] Cloud Native Computing Foundation, "OpenTelemetry," página de proyecto (nivel de madurez: Graduated desde el 11 may. 2026). [En línea]. Disponible: https://www.cncf.io/projects/opentelemetry/ (accedido nov. 2026).

[25] GIDAS (Grupo de Investigación, UTN FRLP), "IntellOps: plataforma de observabilidad predictiva en recursos escasos," repositorio institucional, UTN FRLP, 2026. [En línea]. Disponible: https://github.com/infraitgidas/intellops

<!--
NOTA DE VERIFICACIÓN (para el grupo, borrar antes de entregar)
- Verificadas en línea (nov. 2026): [1]-[5] (datatracker.ietf.org: títulos, autores, fechas, estado), [6] (spec gNMI v0.10.0, 25/05/2023), [7] (OTLP 1.11.1; trazas/métricas/logs estables, perfiles en desarrollo),
  [8], [16], [17], [18], [19], [20], [21], [22], [23], [24] (páginas oficiales), [9] (DOI 10.1145/3483424), [10] (DOI 10.1109/ICSE-Companion.2019.00023), [11] (arXiv + programa ICSE 2023),
  [12] (arXiv:2305.15778; DOI de ACM 10.1145/3627703.3629553), [13] (ICLR 2025; 335 fallas, 68 GB; mejor resultado 11,34 %), [14] (DOI 10.1109/ICDM.2008.17), [15] (repositorio ORBilu, NOMS 2020).
- DESCARTADAS por no poder verificarse o por estar mal citadas:
  * "Ahmed, T. et al. (2024). Towards Incident Response with Large Language Models. arXiv:2401.08754" (de IntellOps state-of-the-art.md): el identificador arXiv:2401.08754 corresponde a un artículo de física
    ("Floquet Flux Attachment in Cold Atomic Systems"); la referencia NO es válida. Se reemplazó por [11] (Ahmed et al., ICSE 2023, arXiv:2301.03797), que sí existe.
  * "Jiang, Y. et al. (2023). LLM-based Root Cause Analysis for Cloud Incidents. ACM SIGOPS" y "Chen, Z. et al. (2024). Auto-Remediation with LLMs: A Case Study. IEEE/ACM ICSE" (IntellOps): no se verificaron; no se usan.
  * "Notaro, P. et al. (2021). A Systematic Mapping Study on AIOps. J. Systems and Software" (IntellOps): el título/venue es incorrecto; el trabajo real es [9] (ACM TIST) y un preprint "A Systematic Mapping Study in AIOps" (arXiv:2012.09108).
  * "Schmid, P. et al. (2024). Anomaly Detection in Time Series: A Comprehensive Evaluation. VLDB" (IntellOps): no se verificó; no se usa.
  * Gartner (2025) Magic Quadrant, CNCF (2026) Cloud Native Survey, Netdata (2025) benchmark: no se verificaron; los costos anuales de plataformas comerciales de IntellOps son estimaciones: no citar como cifras.
- Datos que NO tienen referencia verificada y deben confirmarse o quitarse antes de entregar: año exacto de la primera versión de gNMI; año de introducción de eBPF en el kernel (2014 / Linux 3.18);
  datos de fecha de las entradas de blog [19] y [20] (las páginas no muestran fecha en el texto: 2024 por el contexto del anuncio y 2026 por la entrada de URL).
- Nota: IntellOps indica "OpenTelemetry (CNCF graduated)"; al 2026-11 la página oficial de CNCF lo confirma (graduado el 11 may. 2026). Antes de esa fecha era Incubating: cuidado al citar fuentes anteriores.
-->
