# Monitor Territorial y Meteorológico CMPC

## Actualización de avisos mediante KMZ

El dashboard incluye un panel para cargar manualmente un archivo `.kmz` o `.kml` descargado desde SIDCO.

1. Abrir el dashboard alojado.
2. Seleccionar el archivo KMZ actualizado en el panel **Actualizar avisos desde archivo KMZ**.
3. Presionar **Procesar KMZ y actualizar mapa**.
4. El navegador lee las fechas y coordenadas de los avisos, evita duplicados, cruza cada aviso con los predios CMPC y actualiza mapa, filtros, listado y selector meteorológico.
5. Presionar **Descargar events.json actualizado** para conservar la versión procesada.
6. Reemplazar el archivo `events.json` en la raíz del repositorio privado y guardar el cambio. El workflow de GitHub volverá a publicar el dashboard si están configuradas las credenciales de Cloudflare.

La importación se procesa en el navegador. No envía el KMZ a SIDCO ni transmite los datos a un servicio externo. Los datos importados permanecen en esa sesión hasta que se recarga la página; para publicarlos para otros usuarios hay que reemplazar el archivo `events.json` en el repositorio.

## Archivos del repositorio

- `index.html`: dashboard, filtros, meteorología y cargador KMZ.
- `events.json`: última extracción procesada.
- `predios.geojson`: geometrías CMPC depuradas, sin teléfonos ni datos personales de contacto.
- `.github/workflows/deploy.yml`: publica el dashboard actualizado en Cloudflare Pages.

## Meteorología

Open-Meteo entrega condiciones actuales modeladas y pronóstico horario para la coordenada del aviso seleccionado. El panel consulta cada 15 minutos mientras la página permanece abierta. Estos valores no son observaciones tomadas por una estación meteorológica instalada en la ubicación de la quema.

Para uso operacional/comercial de CMPC se debe utilizar un proveedor con una licencia que autorice dicho uso.

## Seguridad y despliegue

- Mantener el repositorio GitHub privado.
- Proteger el sitio Cloudflare Pages con Cloudflare Access antes de compartirlo.
- El workflow requiere los secretos `CLOUDFLARE_API_TOKEN` y `CLOUDFLARE_ACCOUNT_ID`.
- El secreto `SIDCO_URL` ya no es necesario con el método de importación manual KMZ.
- El despliegue copia únicamente `index.html`, `events.json` y `predios.geojson` al sitio; no publica scripts de procesamiento ni el README del repositorio.

## Criterios metodológicos

- Un aviso SIDCO es un aviso de quema, no necesariamente un incendio confirmado.
- “Dentro de predio CMPC” indica que la coordenada del aviso cae dentro del polígono; no identifica quién realizó o autorizó la quema.
- La distancia se calcula como distancia mínima en línea recta al polígono CMPC más cercano.
- La orientación desde el borde del predio hacia el aviso no representa dirección del viento ni propagación del fuego.
