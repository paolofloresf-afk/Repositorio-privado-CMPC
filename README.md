# Monitor Territorial y Meteorológico CMPC

## Estructura del repositorio
- `index.html`: dashboard interactivo y panel meteorológico.
- `events.json`: snapshot de avisos SIDCO; el proceso automático lo actualiza.
- `predios.geojson`: polígonos CMPC depurados (sin información personal de contacto).
- `refresh.py`: procesamiento SIDCO y análisis espacial.
- `requirements.txt`: dependencias Python.
- `.github/workflows/deploy.yml`: actualización y publicación cloud.

## Automatización
GitHub Actions intenta consultar SIDCO cada 15 minutos, cruzar los avisos con los predios CMPC y publicar el dashboard en Cloudflare Pages. Se requiere configurar los secretos:
- `SIDCO_URL`
- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

No incluir credenciales en archivos, commits o conversaciones. Guardarlas exclusivamente en GitHub → Settings → Secrets and variables → Actions.

## Meteorología
El dashboard consulta Open-Meteo cada 15 minutos mientras está abierto. Los valores actuales son estimaciones modeladas para las coordenadas de los avisos, no mediciones locales de una estación. Para uso operacional/comercial se debe contratar un servicio con licencia adecuada.

## Limitaciones
- La automatización SIDCO se debe validar contra el endpoint autorizado durante la primera ejecución.
- Los horarios programados de GitHub Actions pueden retrasarse.
- Un aviso SIDCO es un aviso de quema, no necesariamente un incendio confirmado.
- La clasificación “dentro de predio” describe una relación espacial y no identifica quién realizó o autorizó la quema.
- El viento modelado no representa la dirección de propagación del fuego.

## Despliegue
Crear el proyecto Cloudflare Pages `monitor-cmpc-cloud`, configurar GitHub Secrets y proteger el dominio con Cloudflare Access antes de compartir el dashboard.
