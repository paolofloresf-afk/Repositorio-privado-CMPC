# Monitor Territorial y Meteorológico CMPC — Cloud

## Arquitectura seleccionada

- **GitHub privado**: código, historial y workflows.
- **GitHub Actions**: ejecuta el proceso SIDCO aproximadamente cada 15 minutos.
- **ETL Python**: obtiene el KML/KMZ SIDCO, elimina duplicados, cruza coordenadas con los polígonos CMPC, calcula distancia, rumbo y categoría de alerta, y actualiza `data/events.json`.
- **Cloudflare Pages (Direct Upload con Wrangler)**: publica el HTML estático y los datos ya procesados.
- **Cloudflare Access**: restringe el acceso al dashboard mediante autenticación por correo y código de un solo uso.
- **Open-Meteo**: consulta viento, dirección, ráfagas, temperatura, humedad, precipitación y pronóstico horario para el aviso seleccionado.

El repositorio debe permanecer privado. No publicar este conjunto de datos en un sitio abierto.

## Contenido

- `index.html`: dashboard y módulo meteorológico integrado.
- `data/predios.geojson`: 3.169 polígonos CMPC depurados. Se conservaron nombre del predio y zona; se excluyeron teléfonos y contactos personales presentes en el KMZ de origen.
- `data/events.json`: snapshot inicial de avisos asociados a predios. El proceso cloud lo reemplaza al obtener una extracción válida.
- `scripts/refresh.py`: descarga y análisis espacial de SIDCO.
- `.github/workflows/deploy.yml`: actualización programada y publicación con Wrangler.
- `requirements.txt`: dependencias Python.

## Configuración necesaria

### A. Crear repositorio privado en GitHub

1. En https://github.com/new crear `monitor-cmpc-cloud`.
2. Elegir **Private**.
3. Crear el repositorio vacío, sin README, licencia ni `.gitignore`.
4. Descomprimir `monitor_cmpc_cloud.zip` y cargar al nivel raíz del repositorio el contenido interior de la carpeta `cmpc_cloud/` (no subir la carpeta contenedora como nivel adicional).

### B. Crear el proyecto Cloudflare Pages

1. Entrar a https://dash.cloudflare.com/ y abrir **Workers & Pages**.
2. Crear una aplicación Pages mediante **Direct Upload**.
3. Nombre de proyecto: `monitor-cmpc-cloud`.
4. El proyecto debe crearse antes de lanzar el workflow de GitHub Actions.
5. La publicación se hace desde GitHub Actions con Wrangler; no conectar Git integration de Pages en este proyecto.

### C. Configurar secretos del repositorio GitHub

En GitHub: **Settings → Secrets and variables → Actions → New repository secret**.

Crear los siguientes secretos:

| Nombre | Valor |
|---|---|
| `SIDCO_URL` | URL completa del NetworkLink SIDCO, incluyendo su clave de acceso |
| `CLOUDFLARE_API_TOKEN` | Token de Cloudflare con permiso de edición de Cloudflare Pages en la cuenta correcta |
| `CLOUDFLARE_ACCOUNT_ID` | ID de la cuenta Cloudflare |

No copiar la clave SIDCO en `README.md`, HTML, issues, commits, capturas o archivos visibles del repositorio. No pegarla en el chat. Guardarla solo como secreto de GitHub.

### D. Proteger el sitio con Cloudflare Access

1. En Cloudflare Zero Trust → Access → Applications, crear una aplicación **Self-hosted**.
2. Proteger el hostname `monitor-cmpc-cloud.pages.dev`.
3. Crear una política **Allow** que incluya únicamente los correos autorizados.
4. Habilitar el método de inicio de sesión **One-time PIN** para que cada persona autorizada reciba un código temporal por correo.
5. En el proyecto Pages, comprobar **Settings → Enable access policy** y proteger también el dominio `pages.dev` y los despliegues de vista previa. Si se configura un dominio propio, crear una política Access para ese hostname también.
6. Comprobar el sitio en una sesión privada del navegador: sin autenticación debe bloquearse; con un correo autorizado debe mostrar el dashboard.

**No dejar el dashboard público.** La autenticación debe verificarse antes de compartir el enlace con otras personas.

### E. Ejecutar la primera actualización

1. En GitHub → Actions → `Actualizar y publicar Monitor CMPC`.
2. Seleccionar **Run workflow**.
3. Revisar que finalicen correctamente los pasos de consulta SIDCO, cruce CMPC y publicación Cloudflare.
4. Abrir `https://monitor-cmpc-cloud.pages.dev` e iniciar sesión mediante Access.

## Frecuencias y límites

- SIDCO: el workflow intenta actualizar cada 15 minutos (minutos 7, 22, 37 y 52). GitHub Actions es un programador de mejor esfuerzo y puede retrasar ejecuciones.
- Meteorología: el navegador consulta Open-Meteo cada 15 minutos mientras la página está abierta. Los valores actuales son valores modelados en la coordenada seleccionada, no una medición real en terreno. La actualización de los modelos depende de sus ciclos, que normalmente son de varias horas.
- Cerrar el navegador no detiene el proceso SIDCO; la meteorología se consulta al abrir el informe y mientras permanezca abierto.
- El módulo meteorológico actual se alimenta del aviso SIDCO seleccionado; aún no representa una estación meteorológica fija ni una red de estaciones.
- El endpoint SIDCO debe validarse en la primera ejecución real. El parser se basó en el KML/KMZ facilitado; si la estructura del feed cambió, el job debe fallar y conservar la última extracción correcta.

## Licencias meteorológicas

La API gratuita pública de Open-Meteo está limitada a usos no comerciales. El uso interno de una empresa comercial como CMPC requiere revisar las condiciones y contratar el servicio comercial correspondiente o usar un proveedor institucional autorizado. No tratar la versión de prueba con API gratuita como un servicio operacional aprobado.

Documentación:
- API: https://open-meteo.com/en/docs
- Actualizaciones de modelos: https://open-meteo.com/en/docs/model-updates
- Términos: https://open-meteo.com/en/terms

## Nota metodológica y operacional

- Un aviso SIDCO es un aviso de quema, no necesariamente un incendio confirmado.
- “Dentro de predio CMPC” es una relación espacial con el polígono cargado; no identifica por sí sola quién ejecuta o autoriza la quema.
- El viento no indica la dirección de propagación del fuego.
- La información meteorológica no sustituye observaciones oficiales, estaciones locales ni protocolos de emergencia.

## Geometría del catastro

Para reducir el peso del despliegue web, los polígonos incluidos en `data/predios.geojson` fueron generalizados con una tolerancia de 5 metros en proyección UTM y redondeados a seis decimales. Esto facilita el rendimiento del dashboard; las distancias de avisos cercanos a los umbrales deben interpretarse como aproximadas respecto del catastro original.
