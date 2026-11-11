# Observabilidad inteligente en redes: del monitoreo reactivo al AIOps predictivo (OpenTelemetry, eBPF y aprendizaje automático)

![UTN Logo]

**Universidad Tecnológica Nacional** — Facultad Regional La Plata

**Carrera:** Ingeniería en Sistemas de Información

**Cátedra:** Gestión Operativa y Seguridad en Redes

**Trabajo Práctico N.º 4** — Proyecto Integrador

**Modalidad:** B — Artículo de Revisión del Estado del Arte

**Grupo:** 1

**Integrantes:**
- Cemino, Conrado
- Monfroglio, Romeo Lorenzo

**Docentes:** Osvaldo Falabella · Emanuel Rodríguez

**Fecha de entrega:** Noviembre 2026

---

## Resumen

El monitoreo de redes basado en umbrales estáticos detecta los incidentes tarde y no explica sus causas. Este artículo revisa la evolución de la telemetría de red (SNMP, NetFlow/IPFIX, gNMI, OpenTelemetry y eBPF) y de la analítica operativa (detección de anomalías con aprendizaje automático y análisis de causa raíz asistido por modelos de lenguaje). Se identifica una convergencia hacia OpenTelemetry como estándar de transporte y hacia eBPF como fuente de datos sin instrumentación, y se documentan los límites medidos del análisis asistido por inteligencia artificial. La seguridad se aborda en dos planos: las anomalías como señales de ataque y el propio pipeline de telemetría como superficie de ataque. Se discuten brechas abiertas y oportunidades para la ingeniería en sistemas de información.

**Palabras clave:** observabilidad, AIOps, OpenTelemetry, eBPF, detección de anomalías, seguridad de red.

## 1. Introducción

La red dejó de ser un conjunto de dispositivos estáticos: hoy conviven el tráfico este-oeste entre contenedores y los servicios efímeros. A criterio de los autores, el monitoreo reactivo por umbrales fijos produce ruido de alertas, correlaciona poco las señales y no explica las causas; un incidente sutil, dentro de rangos aceptables, no cruza ningún umbral. AIOps surgió para atender desafíos operativos de este tipo (cf. Dang et al., 2019). Los estándares abiertos de telemetría (OpenTelemetry, OTLP) y eBPF abarataron la observación, y el aprendizaje automático y los modelos de lenguaje grandes (LLM) prometen pasar de avisar a anticipar y explicar.

La seguridad atraviesa el tema en dos planos. La telemetría es un sensor: los flujos y los eventos del kernel revelan escaneos de puertos, movimiento lateral y exfiltración. A la vez, el pipeline de observabilidad concentra datos sensibles y, si acepta tráfico sin cifrado ni autenticación, se convierte en un punto de ataque (OpenTelemetry, s.f.-a).

Este artículo revisa el estado del arte y las innovaciones de 2023-2026, identifica brechas y presenta un caso mínimo reproducible (Figura 1), apoyado en la investigación previa del proyecto IntellOps (Equipo InfraIT GIDAS, 2026), citada y no reproducida. Las secciones 2 a 5 abordan el estado del arte, las innovaciones, las oportunidades y las conclusiones.

## 2. Estado del arte

### 2.1. Evolución de la telemetría de red

La telemetría evolucionó por acumulación de capas: cada una resolvió una limitación de la anterior y abrió un problema de seguridad nuevo (Tabla 1). El eje de la evolución es doble: la unidad de observación se acerca a la aplicación y al kernel, y el dato pasa del sondeo (*pull*) a la emisión por eventos (*push*). Cassagnes et al. (2020) documentan el auge de eBPF como alternativa no intrusiva para monitorear el desempeño de las aplicaciones.

**Tabla 1:** Evolución de la telemetría de red y la observabilidad, del monitoreo reactivo al AIOps

| Hito temporal | Tecnología | Modelo | Qué resuelve | Limitación | Seguridad |
|---|---|---|---|---|---|
| 1990 | SNMPv1 (Case et al., 1990) | Pull: el NMS sondea al agente; MIB | Gestión estandarizada y multivendor | Sin contexto de flujo ni de aplicación | *Community string* en texto claro |
| 1998; STD 62 en 2002 | SNMPv3 (Harrington et al., 2002) | Pull, con *informs* | Autenticación y privacidad por usuario (Blumenthal y Wijnen, 2002) | Configuración compleja; atado al sondeo | Canal confidencial; adopción desigual |
| 2004-2013 | NetFlow v9 e IPFIX (Claise, 2004; Claise et al., 2013) | Push: registros de flujo (5-tupla) | Quién habla con quién, sin capturar paquetes | Sin semántica de aplicación; el muestreo atenúa eventos | Base forense y de detección de escaneos |
| 2016 en adelante | gNMI (OpenConfig, s.f.) | Push por suscripción sobre gRPC; YANG | Telemetría modelada y de baja latencia | Exige soporte del equipo y modelos YANG | gRPC con TLS; *Set* amplía la superficie |
| 2019 en adelante (graduado en 2026) | OpenTelemetry / OTLP (OpenTelemetry, s.f.-b; Cloud Native Computing Foundation [CNCF], s.f.) | Push al Collector: trazas, métricas y logs | Estándar abierto de tres señales | Instrumentación; cardinalidad y costo | El Collector concentra datos sensibles |
| ISA estandarizada en 2024 | eBPF: Cilium, Tetragon, Falco (eBPF.io, s.f.; Thaler, 2024) | Push desde el kernel: syscall, paquete | Visibilidad sin modificar aplicaciones | Requiere kernel y privilegios | *Enforcement* en línea (Cilium, s.f.; Tetragon, s.f.); programas privilegiados |
| 2019 en adelante | AIOps: ML y LLM (Dang et al., 2019; Notaro et al., 2021) | Analítica sobre datos ya recolectados | Patrones bajo el umbral; causas probables | Falsos positivos; los LLM pueden errar (Xu et al., 2025) | Anomalías como señales de ataque; proteger el modelo |

### 2.2. Herramientas dominantes en la industria

Prometheus es una herramienta de código abierto ampliamente adoptada para métricas y alertas por umbral (Prometheus, s.f.), y se complementa con Grafana y *blackbox_exporter* (sondeo HTTP, TCP e ICMP). OpenTelemetry aporta SDK, Collector y OTLP, con trazas, métricas y logs estables (OpenTelemetry, s.f.-b). En eBPF se destacan Cilium con Hubble, que da visibilidad de la comunicación de red (Cilium, s.f.); Tetragon, que observa eventos de seguridad y aplica filtros y bloqueos dentro del kernel (Tetragon, s.f.); y Falco, para detección de amenazas en ejecución (CNCF, 2024). Para anomalías en series de métricas, Isolation Forest (Liu et al., 2008) es una técnica liviana y no supervisada que aísla las observaciones atípicas con árboles aleatorios.

### 2.3. Limitaciones del estado actual

Los umbrales estáticos no se adaptan a la estacionalidad ni detectan degradaciones graduales. Los datos viven en silos (SNMP, flujos, métricas, trazas y logs), por lo que, a criterio de los autores, la correlación es manual y eleva el tiempo de resolución; la literatura clasifica los métodos de AIOps para gestionar fallas (cf. Notaro et al., 2021). A escala, OpenTelemetry enfrenta costo y cardinalidad, y un puntaje de anomalía no es una causa raíz. La propia telemetría es además vulnerable: *endpoints* OTLP abiertos, datos sensibles (por ejemplo, tokens o números de tarjeta) en los atributos y falta de cifrado y autenticación entre agentes y Collector (OpenTelemetry, s.f.-a).

## 3. Innovaciones emergentes

### 3.1. Telemetría: perfilado, instrumentación sin código y estandarización

En marzo de 2024 OpenTelemetry anunció el soporte de perfilado continuo (señal de perfiles), con el compromiso de Elastic de donar su agente eBPF (OpenTelemetry, 2024b), aceptado en junio de 2024 (OpenTelemetry, 2024a); en 2026 la señal llegó a alfa pública, aún sin aptitud para cargas críticas (OpenTelemetry, 2026). En 2025 Grafana anunció la donación de Beyla a OpenTelemetry (en proceso a la fecha del anuncio), dando origen a OpenTelemetry eBPF Instrumentation (OBI), que instrumenta aplicaciones compiladas sin modificar su código (Grcevski, 2025) y conecta eBPF con OTLP. En octubre de 2024 el IETF estandarizó el conjunto de instrucciones de BPF (RFC 9669), lo que aporta portabilidad (Thaler, 2024). El ecosistema también maduró: Cilium se graduó en la CNCF en octubre de 2023 (CNCF, 2023), Falco en febrero de 2024, tras una auditoría de seguridad de terceros (CNCF, 2024), y OpenTelemetry en mayo de 2026 (CNCF, s.f.), lo que indica adopción y gobernanza, no ausencia de riesgos.

### 3.2. Analítica operativa: LLM para el análisis de causa raíz

Ahmed et al. (2023) evaluaron LLM para recomendar causa raíz y mitigación sobre más de 40 000 incidentes de Microsoft, y RCACopilot (Chen et al., 2024) combina diagnósticos con un LLM para predecir la categoría de la causa y explicarla. El contrapeso es OpenRCA: sobre 335 fallas y más de 68 GB de telemetría, el mejor resultado del artículo original resolvió solo el 11,34 % de los casos, aun con un agente diseñado a medida (Xu et al., 2025). De ello los autores infieren que el análisis de causa raíz con LLM es prometedor, pero no confiable sin verificación humana.

### 3.3. Seguridad de la telemetría como tema emergente

Las guías oficiales de OpenTelemetry recomiendan acotar las direcciones de los receptores, configurar cifrado y autenticación, y usar el procesador *redaction* para enmascarar atributos sensibles antes de exportar (OpenTelemetry, s.f.-a). Además, el verificador de eBPF garantiza que un programa es seguro de ejecutar, pero no qué hace (eBPF.io, s.f.); controlar qué programas se cargan y con qué privilegios sigue siendo tarea del operador.

### 3.4. Caso ilustrativo: umbrales, aprendizaje automático y telemetría protegida

Se construyó una demostración de laboratorio en tres actos, con contenedores y sin conexión a internet (Figura 1): umbrales con Prometheus y Grafana; detección con Isolation Forest (Liu et al., 2008); y explicación de causa raíz con un LLM local (*llama3.2:1b* sobre Ollama, de alrededor de 1.200 millones de parámetros) y telemetría protegida con mTLS. Ante un retardo inyectado y un escaneo lento de puertos, el detector alcanzó puntajes de 0,785 y 0,744 (escala de 0 a 1) con cero alertas por umbral. Con mTLS, el Collector rechazó la telemetría falsa y aceptó al agente legítimo. Advertencias: son valores de una única corrida con tráfico sintético; el LLM de 1B a veces afirma lo que la evidencia no respalda; mTLS no cubre certificados robados; y la telemetría falsa engañó al operador, no al detector.

![Diagrama de arquitectura de la demostración en tres actos. Acto 1: cliente, servicios web y api, exporters, Prometheus con umbrales y Grafana. Acto 2: el atacante 1 realiza un escaneo lento de puertos hacia los servicios y el detector de anomalías con Isolation Forest lo detecta. Acto 3: un módulo de causa raíz con LLM local explica el incidente en Grafana, y el atacante 2, que envía telemetría falsa sin credenciales, es rechazado en la puerta mTLS del OpenTelemetry Collector, mientras un agente legítimo con certificado de cliente sí ingresa.](../diagramas/figura-1-arquitectura.svg)

**Figura 1:** Arquitectura de la demostración en tres actos: (1) monitoreo por umbrales, (2) detección con aprendizaje automático y (3) explicación con LLM local y protección de la telemetría con mTLS. Elaboración propia.

## 4. Oportunidades y desafíos

**Detección predictiva y explicable.** Pasar de «anomalía detectada» a «causa probable y evidencia» es, a criterio de los autores, el principal problema abierto. El caso de la sección 3.4 mostró que un puntaje de anomalía alerta cuando los umbrales callan, pero no dice qué falló, y que la explicación de un modelo pequeño debe contrastarse con evidencia medida. Además, el desempeño sobre tráfico sintético sirve para comparar modelos, no para anticipar una red real: predecir una degradación antes de que ocurra exige series largas y etiquetadas de redes reales.

**LLM locales y verificables.** Operar modelos cuantizados en CPU, sin enviar telemetría a terceros, mejora la privacidad y reduce el costo, y es un objetivo de IntellOps (Equipo InfraIT GIDAS, 2026), no un resultado demostrado aquí. El desafío es anclar cada respuesta en evidencia verificable y medir de forma sistemática las alucinaciones, de modo que el operador pueda auditar el origen de cada afirmación. Los resultados de OpenRCA (Xu et al., 2025) indican que el margen de mejora es amplio.

**Seguridad del pipeline.** Se considera que aún falta generalizar el cifrado y la autenticación mutua entre agentes y Collector, la redacción de datos sensibles (por ejemplo, tokens o números de tarjeta) por diseño y el control del privilegio de los agentes eBPF (OpenTelemetry, s.f.-a; eBPF.io, s.f.). La sección 3.4 mostró que mTLS no cubre certificados robados; a criterio de los autores, convendría combinarlo con rotación y revocación de certificados y con la detección de telemetría anómala en el propio Collector.

**Datos y estandarización.** A criterio de los autores, faltan conjuntos públicos etiquetados que combinen tráfico de red con métricas de aplicación, lo que dificulta comparar métodos de detección de forma reproducible. Los perfiles siguen en alfa (OpenTelemetry, 2026) y llevar la telemetría de dispositivos (SNMP, gNMI) a OTLP exige trabajo de conversión de modelos de datos.

**Perfil profesional.** Estas brechas encajan con el perfil de la Ingeniería en Sistemas de Información orientado a la operación y la seguridad de redes. Los roles de ingeniería de confiabilidad (SRE), NetDevOps y seguridad de redes demandan modelado de datos de red, Linux y eBPF, Prometheus y OpenTelemetry, y fundamentos de aprendizaje automático y de seguridad. Se considera que integrar estas áreas, y no dominar una herramienta aislada, distingue a quien podrá diseñar y operar plataformas de observabilidad confiables.

## 5. Conclusiones

La telemetría evolucionó de contadores sondeados a eventos de kernel y señales correlacionadas con estándares abiertos, y el aprendizaje automático agrega valor donde fallan los umbrales, con límites medidos: el mejor resultado de OpenRCA en el artículo original es 11,34 % (Xu et al., 2025). El hallazgo central es que observabilidad y seguridad convergen: los mismos datos sirven para operar y detectar ataques, y el pipeline de telemetría es un activo crítico.

Como proyección propia a 3-5 años, y no como dato, se espera la consolidación de OTLP y OBI como base común, perfiles estables, detección de anomalías integrada en el Collector y LLM locales como asistentes de diagnóstico con verificación humana. El impacto abarca las tres áreas: visibilidad de las capas 3 a 7 sin instrumentar aplicaciones (redes), menor tiempo de resolución y menos ruido (operación), y detección temprana con telemetría protegida (seguridad). El caso ilustrativo indica que las ideas centrales de detección, explicación y mTLS pueden reproducirse a pequeña escala y sin conexión a internet, aunque no que escalen a producción.

## Referencias

Ahmed, T., Ghosh, S., Bansal, C., Zimmermann, T., Zhang, X., y Rajmohan, S. (2023). Recommending root-cause and mitigation steps for cloud incidents using large language models. En *2023 IEEE/ACM 45th International Conference on Software Engineering (ICSE)* (pp. 1737-1749). IEEE. https://doi.org/10.1109/ICSE48619.2023.00149

Blumenthal, U., y Wijnen, B. (2002). *User-based Security Model (USM) for version 3 of the Simple Network Management Protocol (SNMPv3)* (RFC 3414; STD 62). Internet Engineering Task Force. https://datatracker.ietf.org/doc/html/rfc3414

Case, J. D., Fedor, M., Schoffstall, M. L., y Davin, J. (1990). *A Simple Network Management Protocol (SNMP)* (RFC 1157). Internet Engineering Task Force. https://datatracker.ietf.org/doc/html/rfc1157

Cassagnes, C., Trestioreanu, L., Joly, C., y State, R. (2020). The rise of eBPF for non-intrusive performance monitoring. En *NOMS 2020 - 2020 IEEE/IFIP Network Operations and Management Symposium* (pp. 1-7). IEEE. https://doi.org/10.1109/NOMS47738.2020.9110434

Chen, Y., Xie, H., Ma, M., Kang, Y., Gao, X., Shi, L., Cao, Y., Gao, X., Fan, H., Wen, M., Zeng, J., Ghosh, S., Zhang, X., Zhang, C., Lin, Q., Rajmohan, S., Zhang, D., y Xu, T. (2024). Automatic root cause analysis via large language models for cloud incidents. En *Proceedings of the Nineteenth European Conference on Computer Systems* (pp. 674-688). ACM. https://doi.org/10.1145/3627703.3629553

Cilium. (s.f.). *Introduction to Cilium & Hubble*. Cilium Documentation. Recuperado el 10 de noviembre de 2026 de https://docs.cilium.io/en/stable/overview/intro/

Claise, B. (Ed.). (2004). *Cisco Systems NetFlow Services Export Version 9* (RFC 3954). Internet Engineering Task Force. https://datatracker.ietf.org/doc/html/rfc3954

Claise, B. (Ed.), Trammell, B. (Ed.), y Aitken, P. (2013). *Specification of the IP Flow Information Export (IPFIX) Protocol for the Exchange of Flow Information* (RFC 7011; STD 77). Internet Engineering Task Force. https://datatracker.ietf.org/doc/html/rfc7011

Cloud Native Computing Foundation. (s.f.). *OpenTelemetry* [Página de proyecto]. Recuperado el 10 de noviembre de 2026 de https://www.cncf.io/projects/opentelemetry/

Cloud Native Computing Foundation. (2023, 11 de octubre). *Cloud Native Computing Foundation announces Cilium graduation* [Comunicado de prensa]. https://cncf.io/announcements/2023/10/11/cloud-native-computing-foundation-announces-cilium-graduation/

Cloud Native Computing Foundation. (2024, 29 de febrero). *Cloud Native Computing Foundation announces Falco graduation* [Comunicado de prensa]. https://cncf.io/announcements/2024/02/29/cloud-native-computing-foundation-announces-falco-graduation

Dang, Y., Lin, Q., y Huang, P. (2019). AIOps: Real-world challenges and research innovations. En *2019 IEEE/ACM 41st International Conference on Software Engineering: Companion Proceedings (ICSE-Companion)* (pp. 4-5). IEEE. https://doi.org/10.1109/ICSE-Companion.2019.00023

eBPF.io. (s.f.). *What is eBPF? An introduction and deep dive into the eBPF technology*. Recuperado el 10 de noviembre de 2026 de https://ebpf.io/what-is-ebpf/

Equipo InfraIT GIDAS. (2026). *IntellOps: Sistema de Observabilidad Predictiva UX-Céntrica + AI/LLM Open-Source* [Repositorio de código]. GitHub. https://github.com/infraitgidas/intellops

Grcevski, N. (2025, 8 de mayo). *Introducing OpenTelemetry eBPF Instrumentation: Why we donated Grafana Beyla to OpenTelemetry* [Entrada de blog]. Grafana Labs. https://grafana.com/blog/2025/05/07/opentelemetry-ebpf-instrumentation-beyla-donation/

Harrington, D., Presuhn, R., y Wijnen, B. (2002). *An Architecture for Describing Simple Network Management Protocol (SNMP) Management Frameworks* (RFC 3411; STD 62). Internet Engineering Task Force. https://datatracker.ietf.org/doc/html/rfc3411

Liu, F. T., Ting, K. M., y Zhou, Z.-H. (2008). Isolation forest. En *2008 Eighth IEEE International Conference on Data Mining* (pp. 413-422). IEEE. https://doi.org/10.1109/ICDM.2008.17

Notaro, P., Cardoso, J., y Gerndt, M. (2021). A survey of AIOps methods for failure management. *ACM Transactions on Intelligent Systems and Technology, 12*(6), Artículo 81. https://doi.org/10.1145/3483424

OpenConfig. (s.f.). *gRPC Network Management Interface (gNMI)* (versión 0.10.0). Recuperado el 10 de noviembre de 2026 de https://github.com/openconfig/reference/blob/master/rpc/gnmi/gnmi-specification.md

OpenTelemetry. (s.f.-a). *Collector configuration best practices*. OpenTelemetry Documentation. Recuperado el 10 de noviembre de 2026 de https://opentelemetry.io/docs/security/config-best-practices/

OpenTelemetry. (s.f.-b). *OTLP specification 1.11.1*. OpenTelemetry Documentation. Recuperado el 10 de noviembre de 2026 de https://opentelemetry.io/docs/specs/otlp/

OpenTelemetry. (2024a, 7 de junio). *Elastic contributes its continuous profiling agent to OpenTelemetry* [Entrada de blog]. OpenTelemetry Blog. https://opentelemetry.io/blog/2024/elastic-contributes-continuous-profiling-agent/

OpenTelemetry. (2024b, 19 de marzo). *OpenTelemetry announces support for profiling* [Entrada de blog]. OpenTelemetry Blog. https://opentelemetry.io/blog/2024/profiling/

OpenTelemetry. (2026). *OpenTelemetry Profiles enters public alpha* [Entrada de blog]. OpenTelemetry Blog. https://opentelemetry.io/blog/2026/profiles-alpha/

Prometheus. (s.f.). *Overview*. Prometheus Documentation. Recuperado el 10 de noviembre de 2026 de https://prometheus.io/docs/introduction/overview/

Tetragon. (s.f.). *Overview | Tetragon - eBPF-based security observability and runtime enforcement*. Tetragon Documentation. Recuperado el 10 de noviembre de 2026 de https://tetragon.io/docs/overview/

Thaler, D. (Ed.). (2024). *BPF Instruction Set Architecture (ISA)* (RFC 9669). Internet Engineering Task Force. https://datatracker.ietf.org/doc/html/rfc9669

Xu, J., Zhang, Q., Zhong, Z., He, S., Zhang, C., Lin, Q., Pei, D., He, P., Zhang, D., y Zhang, Q. (2025). OpenRCA: Can large language models locate the root cause of software failures? En *The Thirteenth International Conference on Learning Representations (ICLR 2025)*. https://proceedings.iclr.cc/paper_files/paper/2025/file/d29b8d53678015079e1d245c023e49d2-Paper-Conference.pdf
