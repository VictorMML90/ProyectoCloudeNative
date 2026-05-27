# ProyectoCloudeNative
Victor Manuel Madrid Lugo

# Procesador de imágenes 
Aplicación web que permite subir imágenes, aplicar filtros y procesar las tareas de forma distribuida usando workers en Docker. El estado de cada tarea se actualiza en tiempo real en el navegador.

## Stack

- **Frontend** — HTML, CSS y JavaScript puro
- **Backend** — FastAPI con uvicorn
- **Cola de mensajes** — Redis
- **Workers** — Python + Pillow, corriendo en Docker
- **Almacenamiento** — AWS S3
- **Despliegue** — Docker Compose
- **Infraestructura** — Instancia EC2 en AWS

## Arquitectura

```
Frontend (JS)
    │
    ├── POST /presign   → obtiene URL firmada de S3
    ├── POST /jobs      → encola el trabajo en Redis
    └── GET  /status    → escucha estado via SSE
         │
    FastAPI (uvicorn)
         │
       Redis ──── Worker 1
                ├── Worker 2
                └── Worker 3
                      │
                   AWS S3
```

## Estructura del proyecto

```
proyecto/
├── docker-compose.yml
├── README.md
├── backend/
│   ├── main.py
│   ├── Dockerfile
│   └── requirements.txt
├── worker/
│   ├── worker.py
│   ├── Dockerfile
│   └── requirements.txt
└── frontend/
    └── index.html
```
## Explicación técnica

### Cola de mensajes con Redis

Cuando el usuario envía una tarea, el backend hace un `LPUSH` para meter el ID del job en una lista de Redis llamada `jobs_queue`. Los workers están en un loop infinito haciendo `BRPOP`, que es un bloqueo que espera hasta que llegue un elemento en la cola. El primer worker disponible toma el job y lo procesa. Así se distribuye el trabajo automáticamente entre los tres workers sin coordinarlos manualmente.

### Server-Sent Events (SSE)

El frontend abre una conexión con `EventSource` al endpoint `/status/{job_id}`. El backend mantiene esa conexión abierta y cada segundo consulta el estado del job en Redis. Cuando el estado cambia, manda un evento al cliente. Esto permite ver el progreso en tiempo real sin hacer polling desde el frontend.

### Signed POST a S3

El backend genera una URL prefirmada con `generate_presigned_post`. El frontend usa esa URL para subir la imagen directo a S3 sin pasar por el backend, lo que reduce la carga del servidor y el tiempo de transferencia.

### Workers distribuidos

Los tres workers son la misma imagen Docker corriendo en paralelo (`replicas: 3` en docker-compose). Cada uno corre de forma independiente y toma jobs de la misma cola. Si un worker está ocupado, el siguiente toma el trabajo. 

### FastAPI async

Todos los endpoints del backend usan `async def`. El endpoint de SSE usa un generador asíncrono con `asyncio.sleep` para no bloquear el servidor mientras espera cambios de estado. Esto permite atender múltiples conexiones simultáneas con un solo proceso.

## Criterios cubiertos

| Criterio | Implementación |
|---|---|
| Frontend HTML/CSS/JS puro | `frontend/index.html` |
| Event handlers | click, dragover, dragleave, drop, change, load — 8 handlers distintos |
| Fetch a API propia | `/presign`, `/jobs`, `/status`, `/download` |
| Almacenamiento con Storage | historial de jobs en `localStorage` |
| Modificar el DOM | cards de trabajos, estados, antes/despues |
| Animación | barra de progreso, fade-in de cards |
| Signed POST a S3 | endpoint `/presign` con `generate_presigned_post` |
| Canvas y Drag & Drop | preview de imagen antes de enviar |
| Instancia, Nix, Puertos, IP Estática| '(8000,3000,6379)'|
| 3 workers en Docker | `replicas: 3` en docker-compose |
| Docker Compose | `docker-compose.yml` |
| Redis como queue | `LPUSH` en backend, `BRPOP` en workers |
| FastAPI async | todos los endpoints son `async def` |
| SSE | `EventSource` en JS, `StreamingResponse` en FastAPI |
| Despliegue en cloud | instancia EC2 en AWS |
| Nix | entorno de desarrollo con `nix develop` |
| Puertos | 8000 (backend) y 3000 (frontend) abiertos en Security Group |
| IP estática | IP pública fija asignada a la instancia EC2 |













