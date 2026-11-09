# Demo TP4 — Acto 1: monitoreo tradicional

Primer acto de la demo de la Feria de Redes (tema: *Observabilidad inteligente en redes: del monitoreo reactivo al AIOps predictivo*). Este acto establece la **línea base**: un entorno con monitoreo por umbrales donde todo se ve en verde. Los actos 2 (anomalía que los umbrales no detectan, pero sí un detector ML) y 3 (explicación con un LLM local y falla de mTLS) se construyen sobre esta base y todavía no están implementados.

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
bash scripts/pull-images.sh    # descarga las 6 imágenes fijadas por versión
bash scripts/save-images.sh    # genera demo/images/goys-demo-images.tar (~350 MB, ignorado por git)
```

Copiar `goys-demo-images.tar` a un pendrive. En la laptop de la Feria, sin internet:

```bash
bash scripts/load-images.sh    # docker load del tar (no hace falta si las imágenes ya están en Docker)
docker compose up -d
```

Todas las imágenes tienen versión fija (sin `latest`). Una vez descargadas o cargadas, el stack no necesita internet: Grafana tiene desactivados los chequeos de actualización y la telemetría, y no se instalan plugins.

## Puntos de extensión para el Acto 2

- **Red `demo-net`**: bridge con subred fija `172.28.0.0/24` e IPs fijas por servicio (ver arquitectura). Un contenedor adicional (generador de tráfico, escáner de puertos, inyector de latencia) se puede sumar con un archivo de override: `docker compose -f docker-compose.yml -f docker-compose.act2.yml up -d`. Para inyectar latencia se puede usar `tc netem` en un contenedor con `NET_ADMIN`.
- **Nuevos targets de Prometheus**: agregar un archivo YAML en `prometheus/targets/` (formato `file_sd`); se recarga solo cada 10 s. No hace falta tocar `prometheus.yml`.
- **Nuevas reglas**: agregar archivos `.yml` en `prometheus/rules/` y recargar con `curl -X POST localhost:9090/-/reload`.
- **Collector**: `otel/collector-config.yaml` ya tiene un pipeline de métricas (OTLP → Prometheus en el puerto 8889) que el detector del Acto 2 puede usar como entrada o salida.

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
├── .env.example
├── blackbox/blackbox.yml              # módulos HTTP, TCP e ICMP
├── nginx/api.conf                     # configuración del servicio api
├── otel/collector-config.yaml         # OpenTelemetry Collector
├── prometheus/
│   ├── prometheus.yml
│   ├── rules/traditional-alerts.yml   # alertas por umbral (línea base)
│   └── targets/extra.yml              # punto de extensión (file_sd)
├── grafana/
│   ├── provisioning/                  # datasource y proveedor de dashboards
│   └── dashboards/act1-monitoreo-tradicional.json
└── scripts/                           # pull-images.sh, save-images.sh, load-images.sh
```
