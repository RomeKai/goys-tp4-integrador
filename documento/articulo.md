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

El monitoreo de redes basado en umbrales estáticos detecta los incidentes tarde y no explica sus causas. Este artículo revisa la evolución de la telemetría de red (SNMP, NetFlow/IPFIX, gNMI, OpenTelemetry y eBPF) y de la analítica operativa (detección de anomalías con aprendizaje automático y análisis de causa raíz asistido por modelos de lenguaje). Los autores identifican una convergencia hacia estándares abiertos de telemetría y de programación del kernel, y se documentan los límites medidos del análisis asistido por inteligencia artificial. La seguridad se aborda en dos planos: las anomalías como señales de ataque y el propio pipeline de telemetría como superficie de ataque. Se discuten brechas abiertas y oportunidades para la ingeniería en sistemas de información.

**Palabras clave:** observabilidad, AIOps, OpenTelemetry, eBPF, detección de anomalías, seguridad de red.

## 1. Introducción

La red dejó de ser un conjunto de dispositivos estáticos: hoy conviven el tráfico este-oeste entre contenedores y los servicios efímeros. A criterio de los autores, el monitoreo reactivo por umbrales fijos produce ruido de alertas, correlaciona poco las señales y no explica las causas; un incidente sutil, dentro de rangos aceptables, no cruza ningún umbral. AIOps aplica aprendizaje automático a la gestión de fallas (Notaro et al., 2021). A criterio de los autores, los estándares abiertos de telemetría (OpenTelemetry, OTLP) y eBPF abarataron la observación, y el aprendizaje automático y los modelos de lenguaje grandes (LLM) prometen pasar de avisar a anticipar y explicar.

La seguridad atraviesa el tema en dos planos. La telemetría es un sensor: los flujos y los eventos del kernel revelan escaneos de puertos, movimiento lateral y exfiltración. A la vez, el pipeline de observabilidad concentra datos sensibles y, si acepta tráfico sin cifrado ni autenticación, se convierte en un punto de ataque (OpenTelemetry, s.f.).

Este artículo revisa el estado del arte y las innovaciones de 2023-2026, identifica brechas y presenta un caso mínimo reproducible (Figura 1), apoyado en la investigación previa del proyecto IntellOps (Equipo InfraIT GIDAS, 2026), citada y no reproducida. Las secciones 2 a 5 abordan el estado del arte, las innovaciones, las oportunidades y las conclusiones.

## 2. Estado del arte

### 2.1. Evolución de la telemetría de red

La telemetría evolucionó por acumulación de capas: cada una resolvió una limitación de la anterior y abrió un problema de seguridad nuevo (Tabla 1). El eje de la evolución es doble: la unidad de observación se acerca a la aplicación y al kernel, y el dato pasa del sondeo (*pull*) a la emisión por eventos (*push*). En ese recorrido, eBPF permite observar el comportamiento del kernel y de las aplicaciones sin modificarlas y, a criterio de los autores, es el paso más reciente hacia el dato de origen.

**Tabla 1:** Evolución de la telemetría de red y la observabilidad, del monitoreo reactivo al AIOps

| Hito temporal | Tecnología | Modelo | Qué resuelve | Limitación | Seguridad |
|---|---|---|---|---|---|
| 1990 | SNMPv1 (Case et al., 1990) | Pull: el NMS sondea al agente; MIB | Gestión estandarizada y multivendor | Sin contexto de flujo ni de aplicación | *Community string* en texto claro |
| Década de 1990 | SNMPv3 (evolución de SNMP) | Pull, con *informs* | Agrega autenticación y cifrado por usuario | Configuración compleja; atado al sondeo | Mensajes autenticados y cifrados |
| 2013 | IPFIX, heredero de NetFlow (Claise et al., 2013) | Push: registros de flujo | Quién habla con quién, sin capturar paquetes | Sin semántica de aplicación | Base forense y de detección de escaneos |
| Década de 2010 | gNMI | Push por suscripción sobre gRPC; YANG | Telemetría modelada y de baja latencia | Exige soporte del equipo y modelos YANG | gRPC con TLS; *Set* amplía la superficie |
| Década de 2020 | OpenTelemetry / OTLP | Push al Collector: trazas, métricas y logs | Estándar abierto de tres señales | Instrumentación; cardinalidad y costo | El Collector concentra datos sensibles (OpenTelemetry, s.f.) |
| ISA estandarizada en 2024 | eBPF (Thaler, 2024) | Push desde el kernel: syscall, paquete | Visibilidad sin modificar aplicaciones | Requiere soporte del kernel | Programas cargados con privilegios del kernel |
| Década de 2020 | AIOps: ML y LLM (Notaro et al., 2021; Xu et al., 2025) | Analítica sobre datos ya recolectados | Patrones bajo el umbral; causas probables | Falsos positivos; los LLM pueden errar (Xu et al., 2025) | Anomalías como señales de ataque; proteger el modelo |

### 2.2. Herramientas dominantes en la industria

Prometheus y Grafana son herramientas de código abierto habituales para métricas, tableros y alertas por umbral, y se complementan con *blackbox_exporter* (sondeo HTTP, TCP e ICMP). OpenTelemetry aporta SDK, Collector y el protocolo OTLP para trazas, métricas y logs. En el plano de eBPF existen herramientas como Cilium con Hubble, orientada a la visibilidad de la comunicación de red; Tetragon, que observa eventos de seguridad en el kernel; y Falco, dedicada a la detección de amenazas en ejecución. Para anomalías en series de métricas, Isolation Forest (Liu et al., 2008) es una técnica liviana y no supervisada que aísla las observaciones atípicas con árboles aleatorios, lo que la vuelve adecuada como primer detector sin datos etiquetados.

### 2.3. Limitaciones del estado actual

Los umbrales estáticos no se adaptan a la estacionalidad ni detectan degradaciones graduales. Los datos viven en silos (SNMP, flujos, métricas, trazas y logs), por lo que, a criterio de los autores, la correlación es manual y eleva el tiempo de resolución; la literatura clasifica los métodos de AIOps para gestionar fallas (Notaro et al., 2021). A escala, a criterio de los autores, OpenTelemetry enfrenta costo y cardinalidad, y un puntaje de anomalía no es una causa raíz. La propia telemetría es además vulnerable: *endpoints* OTLP abiertos, datos sensibles (por ejemplo, tokens o números de tarjeta) en los atributos y falta de cifrado y autenticación entre agentes y Collector (OpenTelemetry, s.f.).

## 3. Innovaciones emergentes

### 3.1. Telemetría: estandarización y convergencia

En octubre de 2024 el IETF estandarizó el conjunto de instrucciones de BPF (RFC 9669), lo que aporta una referencia común para la portabilidad de los programas eBPF entre implementaciones (Thaler, 2024). Con ello eBPF deja de depender de implementaciones particulares y pasa a tener una especificación abierta, que permite razonar sobre qué puede ejecutar un programa y en qué condiciones. A criterio de los autores, el ecosistema converge en dos direcciones complementarias: OpenTelemetry como punto de encuentro para trazas, métricas y logs, y herramientas basadas en eBPF, como Cilium, Tetragon y Falco, como fuentes de datos que no exigen modificar las aplicaciones. Esa convergencia reduce la cantidad de agentes y formatos que el operador debe mantener, pero también concentra más datos y más privilegios en menos componentes, lo que refuerza la importancia de la seguridad del pipeline (sección 3.3).

### 3.2. Analítica operativa: LLM para el análisis de causa raíz

Ahmed et al. (2023) evaluaron LLM para recomendar causa raíz y mitigación sobre más de 40 000 incidentes de Microsoft, y RCACopilot (Chen et al., 2024) combina diagnósticos con un LLM para predecir la categoría de la causa y explicarla. El contrapeso es OpenRCA: sobre 335 fallas y más de 68 GB de telemetría, el mejor resultado del artículo original resolvió solo el 11,34 % de los casos, aun con un agente diseñado a medida (Xu et al., 2025). De ello los autores infieren que el análisis de causa raíz con LLM es prometedor, pero no confiable sin verificación humana.

### 3.3. Seguridad de la telemetría como tema emergente

Las guías oficiales de OpenTelemetry recomiendan acotar las direcciones de los receptores, configurar cifrado y autenticación, y usar el procesador *redaction* para enmascarar atributos sensibles antes de exportar (OpenTelemetry, s.f.). Estas medidas tratan al Collector como un componente expuesto y no como infraestructura interna confiable. Además, a criterio de los autores, los programas eBPF se ejecutan con privilegios del kernel, por lo que controlar qué programas se cargan y con qué permisos sigue siendo tarea del operador.

### 3.4. Caso ilustrativo: umbrales, aprendizaje automático y telemetría protegida

Se construyó una demostración de laboratorio en tres actos, con contenedores y sin conexión a internet (Figura 1): umbrales con Prometheus y Grafana; detección con Isolation Forest (Liu et al., 2008); y explicación de causa raíz con un LLM local (*llama3.2:1b* sobre Ollama, de alrededor de 1.200 millones de parámetros) y telemetría protegida con mTLS. Ante un retardo inyectado y un escaneo lento de puertos, el detector alcanzó puntajes de 0,785 y 0,744 (escala de 0 a 1) con cero alertas por umbral. Con mTLS, el Collector rechazó la telemetría falsa y aceptó al agente legítimo. Advertencias: son valores de una única corrida con tráfico sintético; el LLM de 1B a veces afirma lo que la evidencia no respalda; mTLS no cubre certificados robados; y la telemetría falsa engañó al operador, no al detector.

![Diagrama de arquitectura de la demostración en tres actos. Acto 1: cliente, servicios web y api, exporters, Prometheus con umbrales y Grafana. Acto 2: el atacante 1 realiza un escaneo lento de puertos hacia los servicios y el detector de anomalías con Isolation Forest lo detecta. Acto 3: un módulo de causa raíz con LLM local explica el incidente en Grafana, y el atacante 2, que envía telemetría falsa sin credenciales, es rechazado en la puerta mTLS del OpenTelemetry Collector, mientras un agente legítimo con certificado de cliente sí ingresa.](../diagramas/figura-1-arquitectura.svg)

**Figura 1:** Arquitectura de la demostración en tres actos: (1) monitoreo por umbrales, (2) detección con aprendizaje automático y (3) explicación con LLM local y protección de la telemetría con mTLS. Elaboración propia.

## 4. Oportunidades y desafíos

**Detección predictiva y explicable.** Pasar de «anomalía detectada» a «causa probable y evidencia» es, a criterio de los autores, el principal problema abierto. El caso de la sección 3.4 mostró que un puntaje de anomalía alerta cuando los umbrales callan, pero no dice qué falló, y que la explicación de un modelo pequeño debe contrastarse con evidencia medida. Además, el desempeño sobre tráfico sintético sirve para comparar modelos, no para anticipar una red real: predecir una degradación antes de que ocurra exige series largas y etiquetadas de redes reales.

**LLM locales y verificables.** Operar modelos cuantizados en CPU, sin enviar telemetría a terceros, mejora la privacidad y reduce el costo, y es un objetivo de IntellOps (Equipo InfraIT GIDAS, 2026), no un resultado demostrado aquí. El desafío es anclar cada respuesta en evidencia verificable y medir de forma sistemática las alucinaciones, de modo que el operador pueda auditar el origen de cada afirmación. Los resultados de OpenRCA (Xu et al., 2025) indican que el margen de mejora es amplio.

**Seguridad del pipeline.** Se considera que aún falta generalizar el cifrado y la autenticación mutua entre agentes y Collector, la redacción de datos sensibles (por ejemplo, tokens o números de tarjeta) por diseño (OpenTelemetry, s.f.), a lo que se suma, a criterio de los autores, el control del privilegio de los agentes eBPF. La sección 3.4 mostró que mTLS no cubre certificados robados; a criterio de los autores, convendría combinarlo con rotación y revocación de certificados y con la detección de telemetría anómala en el propio Collector.

**Datos y estandarización.** A criterio de los autores, faltan conjuntos públicos etiquetados que combinen tráfico de red con métricas de aplicación, lo que dificulta comparar métodos de detección de forma reproducible. Además, a criterio de los autores, llevar la telemetría de dispositivos (SNMP, gNMI) a OTLP exige un trabajo de conversión de modelos de datos que aún no está resuelto de forma general.

**Perfil profesional.** Estas brechas encajan con el perfil de la Ingeniería en Sistemas de Información orientado a la operación y la seguridad de redes. A criterio de los autores, los roles de ingeniería de confiabilidad (SRE), NetDevOps y seguridad de redes demandan modelado de datos de red, Linux y eBPF, Prometheus y OpenTelemetry, y fundamentos de aprendizaje automático y de seguridad. Se considera que integrar estas áreas, y no dominar una herramienta aislada, distingue a quien podrá diseñar y operar plataformas de observabilidad confiables.

## 5. Conclusiones

La telemetría evolucionó de contadores sondeados a eventos de kernel y señales correlacionadas con estándares abiertos, y el aprendizaje automático agrega valor donde fallan los umbrales, con límites medidos: el mejor resultado de OpenRCA en el artículo original es 11,34 % (Xu et al., 2025). El hallazgo central es que observabilidad y seguridad convergen: los mismos datos sirven para operar y detectar ataques, y el pipeline de telemetría es un activo crítico.

Como proyección propia a 3-5 años, y no como dato, se espera la consolidación de OTLP y de la instrumentación basada en eBPF como base común, detección de anomalías integrada en el Collector y LLM locales como asistentes de diagnóstico con verificación humana. El impacto abarca las tres áreas: visibilidad de las capas 3 a 7 sin instrumentar aplicaciones (redes), menor tiempo de resolución y menos ruido (operación), y detección temprana con telemetría protegida (seguridad). El caso ilustrativo indica que las ideas centrales de detección, explicación y mTLS pueden reproducirse a pequeña escala y sin conexión a internet, aunque no que escalen a producción.

## Referencias

Ahmed, T., Ghosh, S., Bansal, C., Zimmermann, T., Zhang, X., y Rajmohan, S. (2023). Recommending root-cause and mitigation steps for cloud incidents using large language models. En *2023 IEEE/ACM 45th International Conference on Software Engineering (ICSE)* (pp. 1737-1749). IEEE. https://doi.org/10.1109/ICSE48619.2023.00149

Case, J. D., Fedor, M., Schoffstall, M. L., y Davin, J. (1990). *A Simple Network Management Protocol (SNMP)* (RFC 1157). Internet Engineering Task Force. https://datatracker.ietf.org/doc/html/rfc1157

Chen, Y., Xie, H., Ma, M., Kang, Y., Gao, X., Shi, L., Cao, Y., Gao, X., Fan, H., Wen, M., Zeng, J., Ghosh, S., Zhang, X., Zhang, C., Lin, Q., Rajmohan, S., Zhang, D., y Xu, T. (2024). Automatic root cause analysis via large language models for cloud incidents. En *Proceedings of the Nineteenth European Conference on Computer Systems* (pp. 674-688). ACM. https://doi.org/10.1145/3627703.3629553

Claise, B. (Ed.), Trammell, B. (Ed.), y Aitken, P. (2013). *Specification of the IP Flow Information Export (IPFIX) Protocol for the Exchange of Flow Information* (RFC 7011; STD 77). Internet Engineering Task Force. https://datatracker.ietf.org/doc/html/rfc7011

Equipo InfraIT GIDAS. (2026). *IntellOps: Sistema de Observabilidad Predictiva UX-Céntrica + AI/LLM Open-Source* [Repositorio de código]. GitHub. https://github.com/infraitgidas/intellops

Liu, F. T., Ting, K. M., y Zhou, Z.-H. (2008). Isolation forest. En *2008 Eighth IEEE International Conference on Data Mining* (pp. 413-422). IEEE. https://doi.org/10.1109/ICDM.2008.17

Notaro, P., Cardoso, J., y Gerndt, M. (2021). A survey of AIOps methods for failure management. *ACM Transactions on Intelligent Systems and Technology, 12*(6), Artículo 81. https://doi.org/10.1145/3483424

OpenTelemetry. (s.f.). *Collector configuration best practices*. OpenTelemetry Documentation. Recuperado el 10 de noviembre de 2026 de https://opentelemetry.io/docs/security/config-best-practices/

Thaler, D. (Ed.). (2024). *BPF Instruction Set Architecture (ISA)* (RFC 9669). Internet Engineering Task Force. https://datatracker.ietf.org/doc/html/rfc9669

Xu, J., Zhang, Q., Zhong, Z., He, S., Zhang, C., Lin, Q., Pei, D., He, P., Zhang, D., y Zhang, Q. (2025). OpenRCA: Can large language models locate the root cause of software failures? En *The Thirteenth International Conference on Learning Representations (ICLR 2025)*. https://proceedings.iclr.cc/paper_files/paper/2025/file/d29b8d53678015079e1d245c023e49d2-Paper-Conference.pdf
