# Demo TP4 — Acto 1: monitoreo tradicional, Acto 2: detección de anomalías y Acto 3: causa raíz con LLM local y seguridad de la telemetría

Demo de la Feria de Redes (tema: *Observabilidad inteligente en redes: del monitoreo reactivo al AIOps predictivo*). El **Acto 1** establece la línea base: un entorno con monitoreo por umbrales donde todo se ve en verde. El **Acto 2** (sección [Acto 2](#acto-2-anomalías-que-los-umbrales-no-ven)) inyecta dos incidentes sutiles que esos umbrales no detectan, pero sí un detector ML. El **Acto 3** (sección [Acto 3](#acto-3-causa-raíz-con-un-llm-local-y-telemetría-falsa)) agrega la explicación de la causa con un LLM local y un escenario de falla de seguridad (telemetría falsa y mTLS). **Orden de ejecución completo de los tres actos para la presentación de 4 minutos: [Presentación de 4 minutos](#presentación-de-4-minutos-los-tres-actos).**

## Qué muestra el Acto 1

- Dos servicios internos pequeños, `web` y `api` (nginx), que solo son accesibles dentro de la red de Docker.
- **Prometheus** sondea ambos con `blackbox_exporter` por HTTP, TCP (puerto 80) e ICMP cada 5 segundos, y recolecta métricas del host con `node_exporter`.
- Un **OpenTelemetry Collector** (distribución contrib) recibe OTLP y expone sus propias métricas a Prometheus.
- **Reglas de alerta clásicas por umbral** (`prometheus/rules/traditional-alerts.yml`): sonda caída, latencia HTTP > 500 ms, RTT ICMP > 100 ms, CPU o memoria > 90 %, target caído.
- Un dashboard de **Grafana** en español con disponibilidad, latencia, métricas del host y estado del Collector. En el Acto 1 muestra 100 % de disponibilidad y 0 alertas activas.

Mensaje del acto: con umbrales estáticos el panel está "en verde". El Acto 2 mostrará una anomalía sutil que no cruza ninguno de estos umbrales.

## Arquitectura

```
                      red Docker "demo-net" (172.28.0.0/24)
 ┌────────┐  ┌────────┐
 │  web   │  │  api   │   <- servicios monitoreados (nginx)
 │ .0.10  │  │ .0.11  │
 └───▲────┘  └───▲────┘
     │ HTTP / TCP / ICMP
 ┌───┴───────────┴──┐   ┌───────────────┐   ┌──────────────────┐
 │ blackbox (.0.20) │   │ node-exporter │   │ otel-collector   │
 └────────▲─────────┘   │    (.0.21)    │   │     (.0.22)      │
          │ /probe      └──────▲────────┘   └───────▲──────────┘
          └──────────┬─────────┴────────────────────┘ scrape
              ┌──────┴───────┐        ┌──────────┐
              │ prometheus   │◄───────│ grafana  │
              │   (.0.30)    │        │ (.0.31)  │
              └──────────────┘        └──────────┘
```

## Puertos

Todos los puertos se publican solo en `127.0.0.1` de la laptop.

| Servicio | URL / puerto | Notas |
|----------|--------------|-------|
| Grafana | http://localhost:3000 | Acceso anónimo como *Viewer*; el dashboard es la página de inicio. Administrador: `admin` / contraseña de `.env` (por defecto `admin`, solo para la demo). |
| Prometheus | http://localhost:9090 | Targets en `/targets`, alertas en `/alerts`. |
| OTLP gRPC | `localhost:4317` | Sin TLS (a propósito: base del escenario de falla del Acto 3). Con mTLS activo exige certificado de cliente. |
| OTLP HTTP | `localhost:4318` | Sin TLS (igual que arriba). |
| Explicación de causa raíz | http://localhost:8085 | Solo con el override del Acto 3: página de solo lectura con la evidencia y el texto del LLM. |

`web`, `api`, `blackbox`, `node-exporter`, `ollama` y los puertos 8888/8889/13133 del Collector son internos y no se publican.

## Cómo ejecutarlo

Requisitos: Docker Desktop (contenedores Linux) con Docker Compose v2.

```bash
cd demo

# Opcional: cambiar la contraseña de administrador de Grafana
cp .env.example .env

# Levantar
docker compose up -d

# Ver el estado (api y web deben quedar "healthy")
docker compose ps

# Apagar (conserva los datos de Prometheus y Grafana)
docker compose down

# Apagar y borrar los datos (arranque limpio)
docker compose down -v
```

Abrir http://localhost:3000: el dashboard *Monitoreo tradicional — Acto 1: todo en verde* aparece como página de inicio. Esperar unos 30 segundos desde `up` para que haya datos.

### Verificación rápida desde la terminal

```bash
# Todos los targets deben estar "up"
curl -s localhost:9090/api/v1/targets | python -c "import json,sys; [print(t['labels']['job'], t['labels']['instance'], t['health']) for t in json.load(sys.stdin)['data']['activeTargets']]"

# Salud de Grafana
curl -s localhost:3000/api/health
```

### Probar que los umbrales funcionan

```bash
docker compose stop api      # en ~15-30 s se disparan las alertas ProbeDown
docker compose start api     # vuelve a verde
```

## Preparación offline

Hacer esto **una vez, con internet**, antes de la Feria:

```bash
cd demo
bash scripts/pull-images.sh    # descarga las imágenes públicas (versión fija) y CONSTRUYE las 4 locales (Actos 2 y 3)
bash scripts/pull-model.sh     # descarga el modelo del LLM (llama3.2:1b) al volumen Docker goys-ollama-models
bash scripts/save-images.sh    # demo/images/goys-demo-images.tar (1,97 GB, 11 imágenes, ignorado por git)
bash scripts/save-model.sh     # demo/images/goys-ollama-model.tar (1,32 GB, el volumen del modelo, ignorado por git)
bash scripts/certs.sh          # certificados de demo para mTLS (demo/certs/, ignorado por git); se genera en segundos y se puede repetir en el lugar
```

Copiar **los dos `.tar`** a un pendrive (en total unos 3,3 GB). En la laptop de la Feria, sin internet:

```bash
bash scripts/load-images.sh    # docker load del tar (no hace falta si las imágenes ya están en Docker)
bash scripts/load-model.sh     # restaura el volumen del modelo (no hace falta si el volumen ya existe)
bash scripts/certs.sh          # certificados (usa openssl del host o, si no hay, el contenedor goys-demo/sender)
docker compose up -d                                                                                      # solo Acto 1
docker compose -f docker-compose.yml -f docker-compose.act2.yml up -d                                     # Acto 1 + Acto 2
docker compose -f docker-compose.yml -f docker-compose.act2.yml -f docker-compose.act3.yml up -d          # Actos 1 + 2 + 3 (o: bash scripts/act3.sh up)
```

Las cuatro imágenes locales (`goys-demo/tools:1.0.0` con nmap y tc, `goys-demo/detector:1.1.0` con scikit-learn, `goys-demo/rca:1.0.0` y `goys-demo/sender:1.0.0` con curl y openssl) se construyen en `pull-images.sh`, así `pip` y `apk` corren con internet y no hacen falta en la Feria. Todas las imágenes tienen versión fija (sin `latest`). Una vez descargadas o cargadas, el stack no necesita internet: Grafana tiene desactivados los chequeos de actualización y la telemetría, y no se instalan plugins.

**El modelo no es una imagen.** Vive en el volumen `goys-ollama-models`, declarado `external` en el override del Acto 3: por eso `act3.sh down -v` (arranque limpio) **no lo borra**. Para borrarlo a propósito: `docker volume rm goys-ollama-models`.

**Espacio en disco** (medido): los dos tars ocupan 1,97 GB (11 imágenes) y 1,32 GB (modelo `llama3.2:1b`), unos 3,3 GB en total; `docker image ls` muestra la imagen `ollama/ollama:0.40.10-rocm` en 4,65 GB (la etiqueta sin `-rocm` pesa 8,43 GB por las bibliotecas CUDA, y aquí se usa solo CPU). Los tars son sin comprimir. Sin la imagen de Ollama ni el modelo, los Actos 1 y 2 siguen funcionando.

## Acto 2: anomalías que los umbrales no ven

### Qué muestra

Dos incidentes **sutiles**, cada uno se inicia y se revierte con un solo comando. En ambos casos las alertas por umbral del Acto 1 siguen en cero y todas las sondas siguen en verde; el detector ML sí lo nota.

| Incidente | Qué ocurre | Por qué no lo ve un umbral |
|-----------|------------|----------------------------|
| **Degradación gradual** | `tc netem` agrega 50 ms ± 25 ms de retardo a las respuestas de `api` | La sonda HTTP pasa de ~2 ms a ~100 ms y el RTT ICMP a 25-75 ms. Las reglas exigen más de 500 ms y más de 100 ms. |
| **Escaneo lento de puertos** | Un contenedor "atacante" ejecuta `nmap -sS -T2` contra la red de la demo | No cae ningún servicio y no hay una regla sobre escaneos. El volumen total de paquetes casi no cambia; cambia la *forma* del tráfico (paquetes que nunca se convierten en conexión). |

El detector (`detector/`) aprende cómo se ve lo normal durante un calentamiento y publica `goys_anomaly_score` (0 a 1) y `goys_anomaly_flag`. Usa IsolationForest de scikit-learn.

### Servicios nuevos

Se agregan con `docker-compose.act2.yml` (un archivo de override sobre el del Acto 1). No se publica ningún puerto nuevo.

| Servicio | IP | Qué hace |
|----------|----|----------|
| `detector` | 172.28.0.40 | Servicio Python con IsolationForest: lee Prometheus y expone `/metrics` en el puerto 8000 (interno). |
| `attacker` | 172.28.0.50 | Contenedor inactivo con `nmap`. El escaneo solo corre mientras `scan on` está activo. |
| `client` | 172.28.0.51 | Tráfico normal de fondo: 2-3 peticiones por segundo a `web` y `api`, con pausas al azar. Sin él la red sería perfectamente regular y no habría nada que aprender. |
| `netem` | (la de `api`) | Sidecar con `NET_ADMIN` que comparte el espacio de red de `api`. Ahí corre `tc qdisc ... netem`. |
| `web-sensor` | (la de `web`) | `node_exporter` (misma imagen que el Acto 1) dentro del espacio de red de `web`, con solo los colectores de red. Mide los paquetes y conexiones que `web` realmente recibe. |

Además: la regla `prometheus/rules/ml-alerts.yml` (alerta `AnomalyDetected`), el tablero `grafana/dashboards/act2-deteccion-anomalias.json` (es la página de inicio cuando se usa el override) y `prometheus/targets-act2/detector.yml`, que registra `detector` y `web-sensor` como targets. El override monta esa carpeta sobre `prometheus/targets/`; por eso el Acto 1 solo no tiene targets muertos.

### Cómo ejecutarlo

```bash
cd demo

# Levantar el Acto 1 + Acto 2
docker compose -f docker-compose.yml -f docker-compose.act2.yml up -d

# Esperar el calentamiento (3 minutos) y abrir http://localhost:3000
bash scripts/inject-incident.sh status
```

**Calentamiento: 3 minutos** desde que arranca el contenedor `detector` (180 s: los primeros 30 s se descartan porque las ventanas de 30 s todavía no están llenas; los siguientes 150 s son las ~30 muestras de "lo normal"). Mientras tanto el tablero muestra *Línea base aprendida* avanzando hasta 100 % y el puntaje en 0. Se puede cambiar con `DETECTOR_WARMUP_SECONDS` (variable de entorno o `.env`); menos de ~120 s da modelos más pobres.

**Importante:** durante el calentamiento no debe haber ningún incidente activo, porque todo lo que el detector ve entonces lo aprende como normal. Antes de empezar, `inject-incident.sh status` debe mostrar `latency: off` y `scan: off`.

### Inyectar y revertir incidentes

```bash
bash scripts/inject-incident.sh latency on          # degradación de api (por defecto 50 ms ± 25 ms)
bash scripts/inject-incident.sh latency on 80 20    # otros valores: retardo y jitter en ms
bash scripts/inject-incident.sh latency off

bash scripts/inject-incident.sh scan on             # escaneo lento
bash scripts/inject-incident.sh scan off

bash scripts/inject-incident.sh status              # qué está activo, puntaje y alertas clásicas
```

Los comandos son idempotentes (repetirlos no hace daño). Con retardos muy altos (del orden de 400 ms o más) las alertas clásicas también se disparan: la demo requiere quedar por debajo de 500 ms (HTTP) y 100 ms (ICMP).

### Qué se observó (corrida de verificación)

Entorno: Docker Desktop 29 en Windows, una laptop con solo la demo corriendo. Los tiempos se midieron consultando Prometheus cada ~20 s, por lo que tienen esa resolución.

| Situación | Puntaje de anomalía | Alertas por umbral | Alerta del detector |
|-----------|---------------------|--------------------|---------------------|
| Sin incidente (varios minutos, con Grafana abierto) | 0,38 a 0,45 | 0 | no |
| Latencia activa (HTTP ~100 ms, RTT ICMP ~45 ms) | 0,785 | 0 (ni pendientes) | sí, en ~25-30 s |
| Escaneo activo (paquetes entrantes por conexión: de ~7 a ~9) | 0,744 | 0 (ni pendientes) | sí, en ~30-50 s |
| Tras revertir cualquiera de los dos | vuelve a ~0,39 en ~30 s | 0 | se apaga en ~30-50 s |

El tiempo de reacción lo marcan las ventanas de 30 s de las métricas y los 15 s de antirrebote (3 muestras seguidas por encima de 0,6).

### Qué esperar y qué no

- Antes de ensayar, cerrar programas pesados: las sondas miden milisegundos y una laptop saturada cambia la línea base.
- El detector solo dice que "algo raro pasa", no qué ni por qué (eso es el Acto 3).
- Reiniciar el detector (`docker compose -f docker-compose.yml -f docker-compose.act2.yml restart detector`) borra lo aprendido y reinicia el calentamiento.

### Solución de problemas del Acto 2

| Síntoma | Causa probable | Qué hacer |
|---------|----------------|-----------|
| `inject-incident.sh` dice que un servicio no está corriendo | Se levantó solo el Acto 1 | Usar los dos archivos: `docker compose -f docker-compose.yml -f docker-compose.act2.yml up -d` |
| El tablero muestra "Detector apagado" | El contenedor `detector` no corre o Prometheus aún no lo scrapea | `docker compose -f docker-compose.yml -f docker-compose.act2.yml logs detector`; revisar http://localhost:9090/targets (job `extra`) |
| Puntaje en 0 y *Línea base aprendida* por debajo de 100 % | Calentamiento en curso | Esperar 3 minutos desde que arrancó el detector |
| El puntaje no sube con `latency on` | La regla de `netem` no se aplicó | `inject-incident.sh status` debe decir `latency: ON`. Si se reinició `api`, el script recrea `netem` solo; si no, `docker compose ... up -d --force-recreate netem` |
| Falsa alarma sin incidentes | Máquina cargada, o el calentamiento incluyó un incidente | Cerrar programas pesados, verificar `status` en `off` y reiniciar el detector |
| `scan on` no cambia nada | `client` caído (sin tráfico normal no hay razón paquetes/conexión) o `attacker` sin `NET_RAW` | `docker compose ... logs client`; `docker compose ... exec attacker nmap -sS -p 80 172.28.0.10` |
| Windows: `bash` ejecuta WSL y falla | `bash` apunta a WSL en lugar de Git Bash | Usar la terminal de Git Bash |
| `up -d` intenta construir imágenes sin internet | No se cargaron las imágenes locales | `bash scripts/load-images.sh` antes de `up` (el tar incluye `goys-demo/detector` y `goys-demo/tools`) |

## Acto 3: causa raíz con un LLM local y telemetría falsa

### Qué muestra

Dos escenas, que se pueden mostrar juntas o por separado.

| Escena | Qué ocurre | Qué se ve |
|--------|------------|-----------|
| **3a. Causa raíz** | Cuando el detector del Acto 2 se activa, el servicio `rca` reúne **evidencia medida** (qué señales se desviaron, cuánto, desde cuándo) y un LLM chico y local (`llama3.2:1b` en Ollama, solo CPU, sin internet) la explica en español. | Una anotación en el tablero del Acto 2 («analizando…» y luego la explicación) y una página de solo lectura en http://localhost:8085 con la evidencia a la izquierda y el texto del LLM a la derecha. |
| **3b. Telemetría falsa** | Un contenedor «atacante» le habla al Collector OTLP **sin autenticación** e inyecta 5 réplicas falsas de `api` que dicen 0 % de errores. Después se activa **mTLS**. | Tablero *Seguridad de la telemetría*: el promedio de errores cae y aparecen 5 emisores falsos. Con mTLS el atacante recibe un error TLS y el emisor legítimo (con certificado) sigue entrando. |

### Servicios nuevos

Se agregan con `docker-compose.act3.yml` (override sobre los del Acto 1 y 2). El único puerto nuevo es el 8085, solo en `127.0.0.1`.

| Servicio | IP | Qué hace |
|----------|----|----------|
| `ollama` | 172.28.0.60 | Servidor del modelo (`ollama/ollama:0.40.10-rocm`, usa solo CPU). Límite: 4 CPU y 3 GB de RAM. El modelo vive en el volumen externo `goys-ollama-models`. |
| `rca` | 172.28.0.61 | Servicio Python: consulta Prometheus, abre un incidente cuando `goys_anomaly_flag` sube, arma la evidencia con reglas fijas, pregunta al LLM (máx. 220 tokens, salida JSON acotada), controla la respuesta contra la evidencia y publica la anotación en Grafana y la página del puerto 8085. |
| `otlp-agent` | 172.28.0.53 | Emisor **legítimo**: manda la métrica real de `api` al Collector cada pocos segundos (en texto plano o con certificado de cliente, según el modo). |
| `poisoner` | 172.28.0.52 | Contenedor inactivo; mientras `poison on` esté activo es el atacante. No tiene certificados. |

Además se reemplaza el servicio `otel-collector` (misma imagen) para agregarle una segunda configuración (`otel/overlay-plain.yaml` u `otel/overlay-mtls.yaml`), se suma el tablero `grafana/dashboards/act3-telemetria-falsa-mtls.json` y, en el tablero del Acto 2, una fila con la última explicación del LLM. **Esa fila solo se llena si el Acto 3 está levantado**; con los Actos 1 y 2 solos queda vacía.

### Cómo ejecutarlo

```bash
cd demo
bash scripts/certs.sh        # una vez (certificados de demo; ignorados por git)
bash scripts/act3.sh up      # Actos 1 + 2 + 3 (equivale al docker compose con los tres archivos)
```

Esperar el **calentamiento del detector (3 minutos)**, igual que en el Acto 2. En ese tiempo `rca` carga el modelo en RAM; el estado se ve arriba en http://localhost:8085 (*LLM local: listo*).

**Escena 3a**

```bash
bash scripts/inject-incident.sh latency on     # o: scan on
# ~25 s: el detector se activa y aparece «analizando…» en el tablero del Acto 2
# ~15-30 s más: la explicación (anotación + http://localhost:8085)
bash scripts/inject-incident.sh latency off
```

**Escena 3b** (abrir http://localhost:3000/d/act3-telemetria-falsa-mtls)

```bash
bash scripts/act3.sh poison on         # el atacante inyecta 5 réplicas falsas; en ~15 s el tablero lo muestra
bash scripts/act3.sh poison logs       # lo que ve el atacante: «ACEPTADO por el Collector (HTTP 200)»
bash scripts/act3.sh mtls on           # el Collector exige certificado de cliente (se recrea en unos segundos)
bash scripts/act3.sh try attacker      # error TLS exacto (ver abajo)
bash scripts/act3.sh try legit         # el emisor con certificado sí entra: HTTP 200
bash scripts/act3.sh mtls off          # vuelve al OTLP plano (lo que usan los Actos 1 y 2)
bash scripts/act3.sh poison off
bash scripts/act3.sh status            # modo, ataque, réplicas, puntos aceptados, apretones TLS rechazados
bash scripts/act3.sh down -v           # apagar todo (el volumen del modelo se conserva)
```

El modo por defecto es **OTLP plano**, por eso los Actos 1 y 2 se comportan exactamente igual que antes. Cambiar a mTLS recrea solo el Collector y el `otlp-agent`.

### Qué se observó (corrida de verificación)

Entorno: Docker Desktop en Windows, laptop con solo la demo corriendo, VM de Docker con 6,7 GiB. Los tiempos se cuentan desde el comando `on`.

**3a. LLM local**

| Situación | Resultado medido |
|-----------|------------------|
| `latency on` | Detector activo a los ~22 s; explicación lista a los ~47 s (el LLM tardó 20 s). |
| `scan on` | Detector activo a los ~28 s; explicación lista a los ~50 s (el LLM tardó 14 s). |
| Duración del LLM en general | De 12 a 28 s por incidente en las corridas de verificación. Si un control de la respuesta salta, se reintenta una vez con otra semilla y el tiempo se acerca a 30 s. |
| Ollama detenido (`docker compose ... stop ollama`) | A los ~4-8 s de preguntar el incidente pasa a *LLM no disponible, solo evidencia* y la anotación muestra la evidencia sin texto del LLM. Nada se cuelga. |
| Primera vez que se carga el modelo | Hasta ~60 s (el servicio lo precarga al arrancar para evitarlo en la demo). |

**Importante sobre la calidad del texto.** Es un modelo de 1B parámetros: la redacción es genérica y a veces dice cosas que la evidencia no respalda (por ejemplo, atribuir el problema «a la aplicación web» sin datos para eso, o hablar de «latencia» cuando las señales eran paquetes por conexión). La demo está diseñada para que **no dependa de que acierte**: la evidencia (izquierda) es medida; el texto (derecha) se contrasta con ella. Los controles automáticos detectan cifras inventadas, cifras junto a otra señal, el sentido invertido («bajó» donde subió) y un «límite» que no existe, y los muestran como **«Atención: …»**; no detectan todos los errores de significado.

**3b. Telemetría falsa y mTLS**

| Situación | Resultado medido |
|-----------|------------------|
| Base | 1 réplica de `api` por OTLP; 0,4 puntos aceptados por segundo. |
| `poison on` (plano) | 6 réplicas; 5,2 puntos por segundo; el promedio de errores pasa de 0,13 a ~0,02. El atacante recibe `ACEPTADO por el Collector (HTTP 200, texto plano)`. |
| `mtls on`, `try attacker` | `RECHAZADO`. Texto plano: `HTTP 400 ... Connection reset by peer`. HTTPS sin certificado: `OpenSSL SSL_read: OpenSSL/3.3.7: error:0A00045C:SSL routines::tlsv13 alert certificate required`. |
| `mtls on`, `try legit` | `ACEPTADO por el Collector (HTTP 200)`. |
| Con el ataque aún activo y mTLS | Vuelve a 1 réplica y 0,4 puntos por segundo. El Collector registró 54 apretones TLS rechazados. |
| `mtls off` con el ataque activo | El atacante vuelve a ser aceptado (por eso se apaga con `poison off`). |

**Qué no se puede medir.** Un apretón TLS rechazado ocurre antes de que algún dato entre al pipeline, por lo que **no existe una métrica de Prometheus** de rechazos. El tablero lo dice con un cartel; el único conteo del lado del servidor es el log del Collector (`act3.sh status` lo cuenta) y el resultado que ve el atacante.

**Recursos** (`docker stats --no-stream`, con el LLM recién usado): `ollama` ~1,5 GiB de 3 GiB, `rca` ~20 MiB y el resto de los contenedores suma ~0,3 GiB. Total ~1,8 GiB de RAM con los tres actos.

### Qué esperar y qué no

- El LLM **no** está para encontrar la causa por sí solo: las reglas fijas dicen qué pasó; el LLM redacta una hipótesis y pasos a verificar. Decirlo en voz alta.
- El envenenamiento de la demo cambia lo que **ve un operador** del Collector (el tablero del Acto 3). No engaña al detector del Acto 2, que lee las sondas y el sensor directamente.
- Con mTLS el atacante no puede inyectar, pero **nada protege contra un certificado robado** (quien tenga un certificado válido entra como emisor legítimo).
- Los certificados son de demo: la clave de la CA se queda en `certs/ca/` y no se monta en ningún contenedor. No se versionan.
- Si el LLM tarda, la anotación «analizando…» ya está visible: no hay que esperar en silencio.

### Solución de problemas del Acto 3

| Síntoma | Causa probable | Qué hacer |
|---------|----------------|-----------|
| `external volume "goys-ollama-models" not found` | No se descargó ni se restauró el modelo | `bash scripts/pull-model.sh` (con internet) o `bash scripts/load-model.sh` (desde el tar) |
| `http://localhost:8085` dice *LLM local: no disponible* | Ollama sigue cargando o está caído | `docker compose -f docker-compose.yml -f docker-compose.act2.yml -f docker-compose.act3.yml logs ollama`; esperar 30 s tras el arranque |
| No aparece ninguna explicación | El detector sigue en calentamiento o no se activó | `bash scripts/inject-incident.sh status` debe mostrar `flag=1`; el calentamiento dura 3 minutos |
| Hay una segunda explicación | El detector bajó y volvió a subir (nuevo episodio) | Es normal; la más reciente es la que cuenta |
| Texto con «Atención: …» | Un control automático detectó algo dudoso | Es parte de la demo: mostrar que la evidencia permite verlo |
| `act3.sh mtls on` falla al crear certificados | No hay `openssl` en el host y Docker no tiene la imagen `goys-demo/sender` | `bash scripts/pull-images.sh`, o `CERTS_USE_DOCKER=1 bash scripts/certs.sh` |
| `try attacker` sigue ACEPTADO con mTLS activo | El Collector no se recreó | `bash scripts/act3.sh status` debe decir `mTLS requested: mtls`; repetir `mtls on` |
| Git Bash cambia rutas (`C:/Program Files/Git/...`) | Conversión de rutas de MSYS | Los scripts ya exportan `MSYS_NO_PATHCONV=1`; si se corre un comando a mano, anteponerlo |
| Con los Actos 1 y 2 solos, el tablero muestra una fila «Acto 3» vacía | Esperado | No hace falta hacer nada |

## Presentación de 4 minutos: los tres actos

Preparación (antes de que entre el público): `bash scripts/act3.sh down -v` (con los tres archivos; un `docker compose down -v` a secas deja los contenedores de los Actos 2 y 3 en pie), `bash scripts/act3.sh up`, **esperar 3 minutos de calentamiento**, abrir en pestañas http://localhost:3000 (tableros de los Actos 1 y 2), http://localhost:3000/d/act3-telemetria-falsa-mtls y http://localhost:8085. Comprobar que `inject-incident.sh status` dice `latency: off` y `scan: off`.

| Tiempo | Acto | Qué se hace | Qué se dice (idea) |
|--------|------|-------------|---------------------|
| 0:00 - 0:45 | **1. Tradicional** | Tablero del Acto 1: sondas en verde, alertas por umbral en cero. | «Un monitoreo clásico mira umbrales: está todo verde.» |
| 0:45 - 1:00 | | `bash scripts/inject-incident.sh latency on` | «Ahora degrado la red de `api`, pero poco.» |
| 1:00 - 1:45 | **2. Anomalías** | Tablero del Acto 2: sube el puntaje y la alerta ML se activa (~25 s); las alertas por umbral siguen en cero. | «Los umbrales no ven nada; el modelo aprendió lo normal y nota que la forma cambió.» |
| 1:45 - 2:30 | **3a. Causa raíz** | Aparece la anotación del LLM (~45-50 s desde el comando); abrir http://localhost:8085. Luego `latency off`. | «El LLM solo recibió la columna de la izquierda, medida. Es una hipótesis, no un veredicto.» |
| 2:30 - 3:05 | **3b. Telemetría falsa** | `act3.sh poison on`; tablero del Acto 3: aparecen 5 réplicas falsas y el promedio de errores cae. | «Si alguien puede hablar con el Collector, puede mentirnos: HTTP 200, sin preguntar quién era.» |
| 3:05 - 3:45 | **3b. mTLS** | `act3.sh mtls on`, `act3.sh try attacker` (error TLS), `act3.sh try legit` (HTTP 200). | «Ahora el Collector exige certificado. El atacante queda afuera, el agente legítimo entra.» |
| 3:45 - 4:00 | Cierre | `act3.sh mtls off` y `act3.sh poison off` (si falta tiempo, después). | «Detectar, explicar y proteger: los tres pasos.» |

Notas: el LLM tarda entre 15 y 30 s, pero el detector se activa antes, así que el Acto 3a se solapa con el segundo acto; si hay prisa se muestra la anotación en el tablero y la página se abre después. Plan B si el LLM falla: la página y la anotación muestran la evidencia sola («LLM no disponible») y la demo sigue. Después de ensayar: `act3.sh poison off`, `act3.sh mtls off` y `bash scripts/inject-incident.sh latency off`.

## Puntos de extensión

- **Red `demo-net`**: bridge con subred fija `172.28.0.0/24` e IPs fijas por servicio (ver arquitectura). Un contenedor adicional se puede sumar con un archivo de override, como hace `docker-compose.act2.yml`.
- **Nuevos targets de Prometheus**: agregar un archivo YAML en `prometheus/targets/` (formato `file_sd`); se recarga solo cada 10 s. No hace falta tocar `prometheus.yml`. Con el override del Acto 2 esa ruta apunta a `prometheus/targets-act2/`.
- **Nuevas reglas**: agregar archivos `.yml` en `prometheus/rules/` y recargar con `curl -X POST localhost:9090/-/reload`.
- **Collector**: `otel/collector-config.yaml` tiene el pipeline de métricas (OTLP → Prometheus en el puerto 8889). El Acto 3 le suma una segunda configuración (`otel/overlay-plain.yaml` u `otel/overlay-mtls.yaml`) con `--config` repetido: el Collector combina ambos archivos.
- **Otro modelo de LLM**: `RCA_MODEL` en `.env` (por ejemplo, otro modelo ya descargado con `ollama pull` dentro del volumen). Cambia la calidad del texto y la duración; las pruebas de la demo se hicieron con `llama3.2:1b`.
- **Más señales para el LLM**: agregar el nombre y su descripción en `GLOSSARY` y en `FAMILY_TARGET` de `rca/main.py`.

## Solución de problemas

| Síntoma | Causa probable | Qué hacer |
|---------|----------------|-----------|
| `failed to connect to the docker API` / `dockerDesktopLinuxEngine` | Docker Desktop no está corriendo | Abrir Docker Desktop y esperar a que diga *Engine running* (puede tardar 30-60 s). |
| `port is already allocated` (3000, 9090, 4317 o 4318) | Otro programa usa el puerto | Cerrarlo o cambiar el puerto publicado en `docker-compose.yml`. |
| Dashboard con "No data" | Aún no hay muestras o Prometheus no levantó | Esperar 30 s; revisar `docker compose ps` y http://localhost:9090/targets. |
| Sondas ICMP en 0 | El contenedor `blackbox` no tiene `NET_RAW` | Verificar `cap_add: [NET_RAW]` en el servicio `blackbox`. |
| `pull access denied` / `no such host` sin internet | Imágenes no descargadas | Correr `scripts/load-images.sh` con el tar de respaldo. |
| Grafana no muestra el dashboard | Error de aprovisionamiento | `docker compose logs grafana` y revisar `grafana/provisioning/` y `grafana/dashboards/`. |
| Con el Acto 3: `docker compose up` falla por el volumen `goys-ollama-models` | El volumen del modelo es externo y no existe | Ver «Solución de problemas del Acto 3» |
| Windows: los scripts `.sh` no corren | No hay bash | Usar Git Bash o WSL, o ejecutar a mano los comandos `docker compose pull` y `docker save`. |
| Las métricas del host no son las de Windows | `node_exporter` mide la VM Linux de Docker Desktop | Es esperable; es suficiente para la demo. |

## Estructura

```
demo/
├── docker-compose.yml
├── docker-compose.act2.yml            # override del Acto 2 (detector, atacante, cliente, netem, sensor)
├── docker-compose.act3.yml            # override del Acto 3 (ollama, rca, otlp-agent, poisoner, Collector con overlay)
├── .env.example
├── blackbox/blackbox.yml              # módulos HTTP, TCP e ICMP
├── nginx/api.conf                     # configuración del servicio api
├── otel/
│   ├── collector-config.yaml          # OpenTelemetry Collector (base)
│   ├── overlay-plain.yaml             # Acto 3: OTLP sin TLS (por defecto)
│   └── overlay-mtls.yaml              # Acto 3: OTLP con mTLS
├── prometheus/
│   ├── prometheus.yml
│   ├── rules/traditional-alerts.yml   # alertas por umbral (línea base)
│   ├── rules/ml-alerts.yml            # alerta del detector ML (Acto 2)
│   ├── targets/extra.yml              # punto de extensión (file_sd)
│   └── targets-act2/detector.yml      # targets del Acto 2 (solo con el override)
├── detector/                          # detector de anomalías (Python, IsolationForest)
│   ├── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── rca/                               # Acto 3a: evidencia + LLM local + anotación de Grafana
│   ├── main.py                        # monitor, evidencia, prompt, controles, anotación
│   ├── page.py                        # página de solo lectura (puerto 8085)
│   ├── requirements.txt
│   └── Dockerfile
├── sender/                            # Acto 3b: imagen con curl y openssl (emisor legítimo y atacante)
│   ├── Dockerfile
│   ├── otlp.sh
│   ├── legit.sh
│   └── attack.sh
├── tools/                             # imagen con nmap y tc (atacante, cliente, netem)
│   ├── Dockerfile
│   ├── scan.sh
│   └── client.sh
├── grafana/
│   ├── provisioning/                  # datasource y proveedor de dashboards
│   └── dashboards/
│       ├── act1-monitoreo-tradicional.json
│       ├── act2-deteccion-anomalias.json
│       └── act3-telemetria-falsa-mtls.json
├── certs/                             # generada por certs.sh (ignorada por git)
└── scripts/                           # pull/save/load-images.sh, pull/save/load-model.sh, inject-incident.sh, act3.sh, certs.sh
```
