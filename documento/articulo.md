# Observabilidad inteligente en redes: de las alertas por umbral al análisis de causa raíz con aprendizaje automático y modelos de lenguaje

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

Los umbrales estáticos detectan los incidentes tarde y no explican sus causas. Este artículo revisa la capa de análisis de la observabilidad de redes, y no la recolección de telemetría, que se menciona solo como contexto. Se examina la evolución de la detección de anomalías (métodos estadísticos, aprendizaje no supervisado y aprendizaje profundo), AIOps como disciplina y el análisis de causa raíz con modelos de lenguaje grandes (LLM) entre 2023 y 2026. Los autores documentan los límites medidos de estos modelos y analizan la seguridad del pipeline de análisis: envenenamiento de telemetría, autenticación mutua en la ingesta y datos sensibles. Una demostración reproducible de laboratorio ilustra los resultados. Se discuten brechas abiertas y oportunidades para la ingeniería en sistemas de información.

**Palabras clave:** observabilidad, AIOps, detección de anomalías, análisis de causa raíz, modelos de lenguaje, seguridad de red.

## 1. Introducción

La red dejó de ser un conjunto de dispositivos estáticos: hoy conviven el tráfico este-oeste y los servicios efímeros. A criterio de los autores, el monitoreo reactivo por umbrales fijos produce ruido de alertas, correlaciona poco las señales y no explica las causas; un incidente sutil, dentro de rangos aceptables, no cruza ningún umbral. AIOps aplica aprendizaje automático a la gestión de fallas (Notaro et al., 2021), y los modelos de lenguaje grandes (LLM) prometen además explicar el incidente en lenguaje natural.

La seguridad atraviesa el tema en dos planos. Un detector de anomalías es también un sensor de seguridad: escaneos de puertos y exfiltración alteran el comportamiento observado. A la vez, el pipeline de análisis concentra datos sensibles y, a criterio de los autores, si acepta telemetría sin autenticación un atacante puede inyectar datos falsos que desvíen el diagnóstico (OpenTelemetry, s.f.).

Este artículo se centra en la capa de análisis (detección de anomalías, AIOps y análisis de causa raíz, RCA, con LLM) y en su seguridad. Revisa el estado del arte y las innovaciones de 2023-2026, identifica brechas y presenta un caso mínimo reproducible (Figura 1).

### 1.1. Antecedentes y aporte

De IntellOps (Equipo InfraIT GIDAS, 2026) se toma su marco de referencia: el planteo de la observabilidad predictiva centrada en el usuario y sus objetivos de diseño (línea base con Isolation Forest, LLM pequeño y local, solo CPU). IntellOps declara metas de diseño, no resultados experimentales. El aporte propio es triple: una revisión crítica de la literatura de 2023-2026 sobre RCA con LLM y sus límites medidos; un análisis de la seguridad del pipeline de AIOps; y una demostración pequeña y reproducible con resultados medidos (sección 3.4).

## 2. Estado del arte

### 2.1. De dónde salen los datos

Esta sección no revisa los protocolos de recolección de telemetría, que exceden el foco del artículo. Como contexto, el análisis se alimenta de métricas, de registros de flujo como IPFIX (Claise et al., 2013) y de trazas y logs transportados por OpenTelemetry (OpenTelemetry, s.f.); SNMP y eBPF son otros mecanismos de captura.

### 2.2. Evolución de la detección y el diagnóstico

Cada enfoque resolvió una limitación del anterior y abrió un problema de seguridad nuevo (Tabla 1).

**Tabla 1:** Evolución de la detección y el diagnóstico de fallas en redes

| Período | Enfoque | Qué detecta/explica | Requisitos de datos | Limitación | Implicancia de seguridad |
|---|---|---|---|---|---|
| Décadas de 1990 y 2000 (aprox.) | Umbrales estáticos | Cruce de un valor fijo en una métrica | La métrica y un límite fijado a mano | Ruido de alertas; ciegos a la estacionalidad | Un ataque sutil, dentro del rango, no alerta |
| Décadas de 2000 y 2010 (aprox.) | Métodos estadísticos (Chandola et al., 2009) | Instancias improbables bajo un modelo del comportamiento normal | Historial representativo y supuestos sobre el modelo | Dependen del modelo supuesto | Un atacante gradual puede acostumbrar al modelo |
| 2008 | ML no supervisado: Isolation Forest (Liu et al., 2008) | Observaciones atípicas, aisladas con árboles aleatorios | Sin etiquetas; datos mayormente normales | Da un puntaje, no una causa; requiere fijar un umbral | Detecta escaneos sin firmas; datos de entrenamiento contaminados sesgan el modelo |
| Década de 2010 | Aprendizaje profundo: autoencoders y redes recurrentes (Notaro et al., 2021) | Anomalías en series, logs y trazas | Gran volumen de datos y cómputo | Difícil de explicar a un operador | Envenenamiento de los datos de entrenamiento |
| Década de 2020 | AIOps integrado (Notaro et al., 2021) | Prevención, predicción, detección, causa raíz y remediación | Métricas, logs y trazas; etiquetas escasas | Falsas alarmas; supuestos propios de cada solución | La plataforma concentra telemetría sensible |
| 2023 a 2025 | RCA con LLM (Ahmed et al., 2023; Chen et al., 2024; Xu et al., 2025) | Categoría de la causa raíz y explicación en lenguaje natural | Historial de incidentes, diagnósticos y telemetría | No confiable sin verificación: 11,34 % en OpenRCA (artículo original) | Telemetría falsa o datos sensibles en el contexto del modelo |

*Nota.* Los períodos de los dos primeros enfoques son aproximados. Las limitaciones y las implicancias de seguridad son análisis de los autores, salvo donde se cita una fuente.

Los umbrales estáticos comparan una métrica con un valor fijo; a criterio de los autores, no se adaptan a la estacionalidad ni detectan degradaciones graduales. Chandola et al. (2009) organizan la detección de anomalías por enfoque; las técnicas estadísticas suponen que los datos normales ocupan regiones de alta probabilidad de un modelo y marcan como anómalo lo improbable. Isolation Forest (Liu et al., 2008) es una técnica liviana y no supervisada que aísla las observaciones atípicas con árboles aleatorios, adecuada como primer detector sin datos etiquetados. Notaro et al. (2021) señalan que, como etiquetar lleva tiempo, la detección suele apoyarse en aprendizaje no supervisado, con autoencoders entre las técnicas más usadas, y que el aprendizaje profundo trajo nuevos enfoques. Como disciplina, AIOps ordena la gestión de fallas en cinco categorías (prevención, predicción en línea, detección, causa raíz y remediación) y catorce subcategorías según la ventana temporal de intervención (Notaro et al., 2021).

### 2.3. Limitaciones del estado actual

Las revisiones respaldan tres límites: las etiquetas son escasas y costosas (Chandola et al., 2009; Notaro et al., 2021), las falsas alarmas varían entre las soluciones (Notaro et al., 2021) y hay una tensión entre exactitud e interpretabilidad (Notaro et al., 2021). A criterio de los autores, la deriva de los datos (*concept drift*), que esas fuentes no tratan, degrada los modelos entrenados con tráfico antiguo, y un puntaje de anomalía no es una causa raíz.

## 3. Innovaciones emergentes (2023-2026)

### 3.1. LLM para el análisis de causa raíz

Ahmed et al. (2023) evaluaron LLM para recomendar causa raíz y mitigación sobre más de 40 000 incidentes de Microsoft, y RCACopilot (Chen et al., 2024) combina diagnósticos con un LLM para predecir la categoría de la causa y explicarla. El contrapeso es OpenRCA: sobre 335 fallas y más de 68 GB de telemetría, el mejor resultado del artículo original resolvió solo el 11,34 % de los casos, aun con un agente diseñado a medida (Xu et al., 2025). De ello los autores infieren que el análisis de causa raíz con LLM es prometedor, pero no confiable sin verificación humana.

### 3.2. LLM locales y respuestas ancladas en evidencia

Operar modelos pequeños y cuantizados en CPU, sin enviar telemetría a terceros, es un objetivo de IntellOps (Equipo InfraIT GIDAS, 2026), no un resultado demostrado aquí. A criterio de los autores, esto mejora la privacidad, pero exige anclar cada afirmación del modelo en evidencia medida y descartar las que no tengan respaldo.

### 3.3. Seguridad del pipeline de AIOps

A criterio de los autores, tres riesgos afectan al pipeline de análisis. El primero es el envenenamiento de la telemetría: métricas o logs falsos pueden ocultar un incidente o fabricar un diagnóstico. El segundo es la ingesta: las guías de OpenTelemetry recomiendan cifrar y autenticar el tráfico del Collector (OpenTelemetry, s.f.). TLS 1.3 define la autenticación con certificados y permite que el servidor solicite el del cliente (Rescorla, 2018), lo que habilita la autenticación mutua (mTLS); la guía citada no trata mTLS de forma específica. El tercero son los datos sensibles: el procesador *redaction* enmascara valores como números de tarjeta antes de exportarlos (OpenTelemetry, s.f.), y los mismos datos podrían llegar al contexto de un LLM.

### 3.4. Caso ilustrativo: umbrales, aprendizaje automático y telemetría protegida

Se construyó una demostración de laboratorio en tres actos, con contenedores y sin conexión a internet (Figura 1): umbrales con Prometheus y Grafana; detección con Isolation Forest (Liu et al., 2008); y explicación de causa raíz con un LLM local (*llama3.2:1b* sobre Ollama, de alrededor de 1.200 millones de parámetros) y telemetría protegida con mTLS. Ante un retardo inyectado y un escaneo lento de puertos, el detector alcanzó puntajes de 0,785 y 0,744 (escala de 0 a 1) con cero alertas por umbral. Con mTLS, el Collector rechazó la telemetría falsa y aceptó al agente legítimo. Advertencias: son valores de una única corrida con tráfico sintético; el LLM de 1B a veces afirma lo que la evidencia no respalda; mTLS no cubre certificados robados; y la telemetría falsa engañó al operador, no al detector.

![Diagrama de arquitectura de la demostración en tres actos. Acto 1: cliente, servicios web y api, exporters, Prometheus con umbrales y Grafana. Acto 2: el atacante 1 realiza un escaneo lento de puertos hacia los servicios y el detector de anomalías con Isolation Forest lo detecta. Acto 3: un módulo de causa raíz con LLM local explica el incidente en Grafana, y el atacante 2, que envía telemetría falsa sin credenciales, es rechazado en la puerta mTLS del OpenTelemetry Collector, mientras un agente legítimo con certificado de cliente sí ingresa.](../diagramas/figura-1-arquitectura.svg)

**Figura 1:** Arquitectura de la demostración en tres actos: (1) monitoreo por umbrales, (2) detección con aprendizaje automático y (3) explicación con LLM local y protección de la telemetría con mTLS. Elaboración propia.

## 4. Oportunidades y desafíos

**Detección y diagnóstico explicables.** Pasar de «anomalía detectada» a «causa probable y evidencia» es, a criterio de los autores, el principal problema abierto. El caso de la sección 3.4 mostró que un puntaje de anomalía alerta cuando los umbrales callan, pero no dice qué falló, y que la explicación de un modelo pequeño debe contrastarse con evidencia medida. Medir de forma sistemática las alucinaciones es otro desafío, y los resultados de OpenRCA (Xu et al., 2025) indican que el margen de mejora es amplio. Además, el desempeño sobre tráfico sintético no anticipa el de una red real: predecir una degradación exige series largas y etiquetadas.

**Seguridad del pipeline.** Se considera que aún falta generalizar la autenticación mutua entre agentes y Collector y la redacción de datos sensibles por diseño (OpenTelemetry, s.f.). La sección 3.4 mostró que mTLS no cubre certificados robados; a criterio de los autores, convendría combinarlo con rotación y revocación de certificados y con la detección de telemetría anómala en el propio Collector, además de defensas contra el envenenamiento de los datos.

**Datos y evaluación.** A criterio de los autores, faltan conjuntos públicos etiquetados que combinen tráfico de red con métricas de aplicación, lo que dificulta comparar métodos de forma reproducible.

**Perfil profesional.** Estas brechas encajan con el perfil de la Ingeniería en Sistemas de Información orientado a la operación y la seguridad de redes. A criterio de los autores, los roles de ingeniería de confiabilidad (SRE), NetDevOps y seguridad de redes demandan modelado de datos de red, Linux, Prometheus y OpenTelemetry, y fundamentos de aprendizaje automático y de seguridad. Se considera que integrar estas áreas, y no dominar una herramienta aislada, distingue a quien podrá diseñar y operar plataformas de observabilidad confiables.

## 5. Conclusiones

La detección evolucionó de umbrales fijos a métodos estadísticos, aprendizaje no supervisado y AIOps, y los LLM suman explicaciones en lenguaje natural, con límites medidos: el mejor resultado de OpenRCA en el artículo original es 11,34 % (Xu et al., 2025). El hallazgo central es que análisis y seguridad convergen: los mismos datos sirven para operar y para detectar ataques, y el pipeline que los analiza es un activo crítico que hay que autenticar y validar.

Como proyección propia a 3-5 años, y no como dato, se espera que los detectores livianos actúen como filtro previo, que los LLM locales asistan el diagnóstico con verificación humana y que la autenticación mutua y la validación de la telemetría de entrada se vuelvan práctica estándar. El impacto abarca redes (diagnósticos auditables), operación (menos ruido y menor tiempo de resolución) y seguridad (detección temprana con telemetría protegida). El caso ilustrativo indica que las ideas centrales de detección, explicación y mTLS pueden reproducirse a pequeña escala y sin conexión a internet, aunque no que escalen a producción.

## Referencias

Ahmed, T., Ghosh, S., Bansal, C., Zimmermann, T., Zhang, X., y Rajmohan, S. (2023). Recommending root-cause and mitigation steps for cloud incidents using large language models. En *2023 IEEE/ACM 45th International Conference on Software Engineering (ICSE)* (pp. 1737-1749). IEEE. https://doi.org/10.1109/ICSE48619.2023.00149

Chandola, V., Banerjee, A., y Kumar, V. (2009). Anomaly detection: A survey. *ACM Computing Surveys, 41*(3), Artículo 15. https://doi.org/10.1145/1541880.1541882

Chen, Y., Xie, H., Ma, M., Kang, Y., Gao, X., Shi, L., Cao, Y., Gao, X., Fan, H., Wen, M., Zeng, J., Ghosh, S., Zhang, X., Zhang, C., Lin, Q., Rajmohan, S., Zhang, D., y Xu, T. (2024). Automatic root cause analysis via large language models for cloud incidents. En *Proceedings of the Nineteenth European Conference on Computer Systems* (pp. 674-688). ACM. https://doi.org/10.1145/3627703.3629553

Claise, B. (Ed.), Trammell, B. (Ed.), y Aitken, P. (2013). *Specification of the IP Flow Information Export (IPFIX) Protocol for the Exchange of Flow Information* (RFC 7011; STD 77). Internet Engineering Task Force. https://datatracker.ietf.org/doc/html/rfc7011

Equipo InfraIT GIDAS. (2026). *IntellOps: Sistema de Observabilidad Predictiva UX-Céntrica + AI/LLM Open-Source* [Repositorio de código]. GitHub. https://github.com/infraitgidas/intellops

Liu, F. T., Ting, K. M., y Zhou, Z.-H. (2008). Isolation forest. En *2008 Eighth IEEE International Conference on Data Mining* (pp. 413-422). IEEE. https://doi.org/10.1109/ICDM.2008.17

Notaro, P., Cardoso, J., y Gerndt, M. (2021). A survey of AIOps methods for failure management. *ACM Transactions on Intelligent Systems and Technology, 12*(6), Artículo 81. https://doi.org/10.1145/3483424

OpenTelemetry. (s.f.). *Collector configuration best practices*. OpenTelemetry Documentation. Recuperado el 10 de noviembre de 2026 de https://opentelemetry.io/docs/security/config-best-practices/

Rescorla, E. (2018). *The Transport Layer Security (TLS) Protocol Version 1.3* (RFC 8446). Internet Engineering Task Force. https://datatracker.ietf.org/doc/html/rfc8446

Xu, J., Zhang, Q., Zhong, Z., He, S., Zhang, C., Lin, Q., Pei, D., He, P., Zhang, D., y Zhang, Q. (2025). OpenRCA: Can large language models locate the root cause of software failures? En *The Thirteenth International Conference on Learning Representations (ICLR 2025)*. https://proceedings.iclr.cc/paper_files/paper/2025/file/d29b8d53678015079e1d245c023e49d2-Paper-Conference.pdf
