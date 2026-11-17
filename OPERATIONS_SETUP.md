# Estado operacional compartido · despliegue de prueba

El módulo de interfaz está en `index.html`. La API compartida está preparada en `worker.js` y la estructura de datos en `migrations/0001_operational_resources.sql`.

## Requisitos antes de habilitar sincronización real

1. Crear una base D1 de prueba llamada `cmpc-operational-preview` en la cuenta Cloudflare correspondiente.
2. Ejecutar la migración SQL del directorio `migrations`.
3. Completar en `wrangler.preview.example.jsonc` el ID de D1, el dominio del equipo Cloudflare Access y el Audience Tag de la aplicación.
4. Desplegar el Worker de prueba usando ese archivo de configuración.
5. Proteger la ruta del sitio y `/api/*` con Cloudflare Access. El Worker verifica la firma del JWT, issuer, audience y vigencia antes de permitir lecturas o escrituras.

La interfaz muestra explícitamente cuándo está sin conexión central. En ese estado los cambios guardados son solo borradores locales y no se anuncian como compartidos.

## API

- `GET /api/operational/resources`: obtiene el último estado compartido.
- `PUT /api/operational/resources`: publica cambios con control optimista de versión.
- Cada publicación queda registrada en `operational_audit`.
