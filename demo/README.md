# Demo TP4 — Acto 1: monitoreo tradicional y Acto 2: detección de anomalías

Demo de la Feria de Redes (tema: *Observabilidad inteligente en redes: del monitoreo reactivo al AIOps predictivo*). El **Acto 1** establece la línea base: un entorno con monitoreo por umbrales donde todo se ve en verde. El **Acto 2** (sección [Acto 2](#acto-2-anomalías-que-los-umbrales-no-ven)) inyecta dos incidentes sutiles que esos umbrales no detectan, pero sí un detector ML. El Acto 3 (explicación con un LLM local y falla de mTLS) se construye sobre esta base y todavía no está implementado.

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
| OTLP gRPC | `localhost:4317` | Sin TLS (a propósito: base del escenario de falla del Acto 3). |
| OTLP HTTP | `localhost:4318` | Sin TLS. |

`web`, `api`, `blackbox`, `node-exporter` y los puertos 8888/8889/13133 del Collector son internos y no se publican.

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
bash scripts/pull-images.sh    # descarga las 6 imágenes públicas (versión fija) y CONSTRUYE las 2 locales del Acto 2
bash scripts/save-images.sh    # genera demo/images/goys-demo-images.tar (~480 MB, 8 imágenes, ignorado por git)
```

Copiar `goys-demo-images.tar` a un pendrive. En la laptop de la Feria, sin internet:

```bash
bash scripts/load-images.sh    # docker load del tar (no hace falta si las imágenes ya están en Docker)
docker compose up -d                                                   # solo Acto 1
docker compose -f docker-compose.yml -f docker-compose.act2.yml up -d  # Acto 1 + Acto 2
```

Las dos imágenes locales (`goys-demo/detector:1.0.0` con scikit-learn y `goys-demo/tools:1.0.0` con nmap y tc) se construyen en `pull-images.sh`, así `pip` y `apk` corren con internet y no hacen falta en la Feria. Todas las imágenes tienen versión fija (sin `latest`). Una vez descargadas o cargadas, el stack no necesita internet: Grafana tiene desactivados los chequeos de actualización y la telemetría, y no se instalan plugins.

## Acto 2: anomalías que los umbrales no ven

### Qué muestra

Dos incidentes **sutiles**, cada uno se inicia y se revierte con un solo comando. En ambos casos las alertas por umbral del Acto 1 siguen en cero y todas las sondas siguen en verde; el detector ML sí lo nota.

| Incidente | Qué ocurre | Por qué no lo ve un umbral |
|-----------|------------|----------------------------|
| **Degradación gradual** | `tc netem` agrega 50 ms ± 25 ms de retardo a las respuestas de `api` | La sonda HTTP pasa de ~2 ms a ~100 ms y el RTT ICMP a 25-75 ms. Las reglas exigen más de 500 ms y más de 100 ms. |
| **Escaneo lento de puertos** | Un contenedor "atacante" ejecuta `nmap -sS -T2` contra la red de la demo | No cae ningún servicio y no hay una regla sobre escaneos. El volumen total de paquetes casi no cambia; cambia la *forma* del tráfico (paquetes que nunca se convierten en conexión). |

El detector (`detector/`) aprende cómo se ve lo normal durante un calentamiento y publica `goys_anomaly_score` (0 a 1) y `goys_anomaly_flag`. Usa IsolationForest de scikit-learn. La explicación completa, con las preguntas probables del jurado, está en [`ACTO-2-GUIA.md`](ACTO-2-GUIA.md).

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
- Límites conocidos y falsos positivos posibles: ver [`ACTO-2-GUIA.md`](ACTO-2-GUIA.md), sección 8.

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

## Puntos de extensión

- **Red `demo-net`**: bridge con subred fija `172.28.0.0/24` e IPs fijas por servicio (ver arquitectura). Un contenedor adicional se puede sumar con un archivo de override, como hace `docker-compose.act2.yml`.
- **Nuevos targets de Prometheus**: agregar un archivo YAML en `prometheus/targets/` (formato `file_sd`); se recarga solo cada 10 s. No hace falta tocar `prometheus.yml`. Con el override del Acto 2 esa ruta apunta a `prometheus/targets-act2/`.
- **Nuevas reglas**: agregar archivos `.yml` en `prometheus/rules/` y recargar con `curl -X POST localhost:9090/-/reload`.
- **Collector**: `otel/collector-config.yaml` ya tiene un pipeline de métricas (OTLP → Prometheus en el puerto 8889) que el Acto 3 puede usar como entrada o salida.

## Solución de problemas

| Síntoma | Causa probable | Qué hacer |
|---------|----------------|-----------|
| `failed to connect to the docker API` / `dockerDesktopLinuxEngine` | Docker Desktop no está corriendo | Abrir Docker Desktop y esperar a que diga *Engine running* (puede tardar 30-60 s). |
| `port is already allocated` (3000, 9090, 4317 o 4318) | Otro programa usa el puerto | Cerrarlo o cambiar el puerto publicado en `docker-compose.yml`. |
| Dashboard con "No data" | Aún no hay muestras o Prometheus no levantó | Esperar 30 s; revisar `docker compose ps` y http://localhost:9090/targets. |
| Sondas ICMP en 0 | El contenedor `blackbox` no tiene `NET_RAW` | Verificar `cap_add: [NET_RAW]` en el servicio `blackbox`. |
| `pull access denied` / `no such host` sin internet | Imágenes no descargadas | Correr `scripts/load-images.sh` con el tar de respaldo. |
| Grafana no muestra el dashboard | Error de aprovisionamiento | `docker compose logs grafana` y revisar `grafana/provisioning/` y `grafana/dashboards/`. |
| Windows: los scripts `.sh` no corren | No hay bash | Usar Git Bash o WSL, o ejecutar a mano los comandos `docker compose pull` y `docker save`. |
| Las métricas del host no son las de Windows | `node_exporter` mide la VM Linux de Docker Desktop | Es esperable; es suficiente para la demo. |

## Estructura

```
demo/
├── docker-compose.yml
├── docker-compose.act2.yml            # override del Acto 2 (detector, atacante, cliente, netem, sensor)
├── ACTO-2-GUIA.md                     # guía de estudio del Acto 2
├── .env.example
├── blackbox/blackbox.yml              # módulos HTTP, TCP e ICMP
├── nginx/api.conf                     # configuración del servicio api
├── otel/collector-config.yaml         # OpenTelemetry Collector
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
├── tools/                             # imagen con nmap y tc (atacante, cliente, netem)
│   ├── Dockerfile
│   ├── scan.sh
│   └── client.sh
├── grafana/
│   ├── provisioning/                  # datasource y proveedor de dashboards
│   └── dashboards/
│       ├── act1-monitoreo-tradicional.json
│       └── act2-deteccion-anomalias.json
└── scripts/                           # pull-images.sh, save-images.sh, load-images.sh, inject-incident.sh
```
