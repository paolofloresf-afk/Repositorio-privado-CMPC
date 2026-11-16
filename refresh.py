import os,io,json,zipfile,math,re
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urljoin,urlparse
import requests
from xml.etree import ElementTree as ET
from shapely.geometry import Point,shape
from shapely.ops import transform,nearest_points
from shapely.strtree import STRtree
from pyproj import Transformer
ROOT=Path(__file__).resolve().parent; DATA=ROOT; OUT=DATA/"events.json"; MAX_DISTANCE=5000
def lname(t): return t.rsplit("}",1)[-1].split(":")[-1]
def txt(el,n):
 for x in el.iter():
  if lname(x.tag)==n and x.text:return x.text.strip()
 return ""
def parse_root(blob):
 if blob[:2]==b"PK":
  z=zipfile.ZipFile(io.BytesIO(blob));blob=z.read(next(n for n in z.namelist() if n.lower().endswith(".kml")))
 blob=re.sub(rb'\s+xsi:schemaLocation="[^"]*"',b'',blob)
 return ET.fromstring(blob)
def parse_date(v,fallback=""):
 v=(v or fallback or "").strip()
 if re.match(r"^\d{4}-\d{2}-\d{2}",v):return v[:10]
 months={"ene":"Jan","feb":"Feb","mar":"Mar","abr":"Apr","may":"May","jun":"Jun","jul":"Jul","ago":"Aug","sep":"Sep","oct":"Oct","nov":"Nov","dic":"Dec"}
 for a,b in months.items():v=re.sub(rf"\b{a}\b",b,v,flags=re.I)
 for f in ("%d-%b-%Y","%d/%m/%Y","%Y/%m/%d"):
  try:return datetime.strptime(v[:11],f).date().isoformat()
  except:pass
 return fallback[:10] if fallback else ""
def parse_events(root):
 out=[]
 for pm in root.iter():
  if lname(pm.tag)!="Placemark":continue
  d={}
  for x in pm.iter():
   if lname(x.tag)=="SimpleData":d[x.attrib.get("name","")]=(x.text or "").strip()
   elif lname(x.tag)=="Data" and x.attrib.get("name"):d[x.attrib["name"]]=txt(x,"value")
  d={str(k).strip().lower():v for k,v in d.items()}
  lat,lon=d.get("lat"),d.get("lon")
  if not lat or not lon:
   c=txt(pm,"coordinates").split()
   if not c:continue
   try:lon,lat=c[0].split(",")[:2]
   except:continue
  try:lat=float(lat);lon=float(lon)
  except:continue
  if not(-56<=lat<=-17 and -77<=lon<=-66):continue
  fecha=parse_date(d.get("avqu_fechainicio",""),txt(pm,"begin"))
  if not fecha:continue
  out.append({"id":d.get("ID") or "quema-"+d.get("avqu_id",""),"aviso":d.get("avqu_numeroaviso",""),"fecha":fecha,
   "quema":d.get("pred_nombre") or txt(pm,"name") or "Quema SIDCO","comuna":d.get("comu_nombre") or d.get("comuna",""),
   "lat":lat,"lon":lon,"inicio":d.get("avqu_horainicio",""),"termino":d.get("avqu_horafin",""),"fecha_fin":d.get("avqu_fechafin",""),
   "sup_agricola_ha":d.get("avqu_supquemaagricola",""),"sup_forestal_ha":d.get("avqu_supquemaforestal","")})
 return list({e["id"]:e for e in out}.values())
def response_diagnostic(response, root=None):
 # No imprimir URL, query string, contenido de credenciales ni datos personales.
 ctype=response.headers.get('Content-Type','desconocido')
 info=[f'HTTP {response.status_code}',f'Content-Type={ctype}',f'bytes={len(response.content)}']
 if response.content[:2]==b'PK':
  try:
   with zipfile.ZipFile(io.BytesIO(response.content)) as z:
    info.append('ZIP/KMZ; archivos='+','.join(Path(n).name for n in z.namelist()[:5]))
  except Exception: info.append('cabecera ZIP detectada, archivo ilegible')
 elif root is not None:
  from collections import Counter
  counts=Counter(lname(x.tag) for x in root.iter())
  info.append('raíz XML='+lname(root.tag))
  info.append('Placemark='+str(counts.get('Placemark',0)))
  info.append('coordinates='+str(counts.get('coordinates',0)))
  info.append('SimpleData='+str(counts.get('SimpleData',0)))
  info.append('NetworkLink='+str(counts.get('NetworkLink',0)))
  keys=[]
  for x in root.iter():
   if lname(x.tag)=='SimpleData' and x.attrib.get('name'): keys.append(x.attrib['name'])
  info.append('campos='+','.join(dict.fromkeys(keys[:25])))
 else:
  body=response.text[:20000]
  if '<html' in body.lower() or '<!doctype html' in body.lower():
   title=re.search(r'<title[^>]*>(.*?)</title>',body,re.I|re.S)
   info.append('respuesta HTML'+(' · título='+re.sub(r'\\s+',' ',title.group(1))[:100] if title else ''))
  elif body.lstrip().startswith('{'):
   try:
    obj=response.json()
    info.append('respuesta JSON; claves='+','.join(list(obj.keys())[:20]) if isinstance(obj,dict) else 'respuesta JSON tipo lista')
   except Exception: info.append('respuesta JSON no interpretable')
  else: info.append('respuesta no reconocida como KML/KMZ')
 return '; '.join(info)

def request_sidco(url):
 session=requests.Session()
 headers={'User-Agent':'GoogleEarth/7.3','Accept':'application/vnd.google-earth.kml+xml,application/vnd.google-earth.kmz,application/xml,text/xml,*/*'}
 response=session.get(url,timeout=60,headers=headers,allow_redirects=True)
 response.raise_for_status()
 try: root=parse_root(response.content)
 except Exception as exc:
  raise RuntimeError('No se pudo interpretar la respuesta SIDCO: '+response_diagnostic(response)+'; parser='+type(exc).__name__) from exc
 raw=parse_events(root)
 if raw: return response,root,raw
 nested=[]
 for x in root.iter():
  if lname(x.tag)=='href' and x.text and x.text.strip():
   candidate=urljoin(response.url,x.text.strip())
   if (urlparse(candidate).hostname or '').lower()=='sidco.conaf.cl': nested.append(candidate)
 for candidate in nested[:3]:
  child=session.get(candidate,timeout=60,headers=headers,allow_redirects=True)
  child.raise_for_status()
  try: child_root=parse_root(child.content)
  except Exception as exc:
   raise RuntimeError('El enlace interno SIDCO no devolvió KML/KMZ interpretable: '+response_diagnostic(child)+'; parser='+type(exc).__name__) from exc
  child_events=parse_events(child_root)
  if child_events: return child,child_root,child_events
  response,root=child,child_root
 raise RuntimeError('SIDCO respondió, pero no contiene avisos KML reconocibles. Diagnóstico seguro: '+response_diagnostic(response,root)+'; se conserva el último snapshot.')
def bearing(a,b):
 lo1,la1=map(math.radians,a);lo2,la2=map(math.radians,b);dl=lo2-lo1
 y=math.sin(dl)*math.cos(la2);x=math.cos(la1)*math.sin(la2)-math.sin(la1)*math.cos(la2)*math.cos(dl)
 return int(round((math.degrees(math.atan2(y,x))+360)%360))
def main():
 url=os.environ.get("SIDCO_URL","").strip()
 if not url:raise RuntimeError("Falta el secreto SIDCO_URL en GitHub.")
 response,root,raw=request_sidco(url)
 print("Fuente SIDCO validada: "+response_diagnostic(response,root))
 pred=json.loads((DATA/"predios.geojson").read_text(encoding="utf-8"));features=pred["features"];geoms=[shape(f["geometry"]) for f in features];tree=STRtree(geoms)
 selected=set();events=[]
 for e in raw:
  p=Point(e["lon"],e["lat"]);idx=int(tree.nearest(p));poly=geoms[idx]
  zone=int((e["lon"]+180)//6)+1;epsg=32700+zone if e["lat"]<0 else 32600+zone
  tr=Transformer.from_crs("EPSG:4326",f"EPSG:{epsg}",always_xy=True).transform
  pp=transform(tr,p);gp=transform(tr,poly);inside=gp.covers(pp)
  if inside:dist=0.;orient="Dentro";deg=None
  else:
   dist=float(gp.distance(pp))
   if dist>MAX_DISTANCE:continue
   edge,_=nearest_points(gp.boundary,pp)
   back=Transformer.from_crs(f"EPSG:{epsg}","EPSG:4326",always_xy=True).transform
   edge=transform(back,edge);deg=bearing((edge.x,edge.y),(e["lon"],e["lat"]))
   orient=["N","NE","E","SE","S","SO","O","NO"][int(round(deg/45))%8]
  if dist>MAX_DISTANCE:continue
  selected.add(idx);alert="ROJA" if dist<1000 else "NARANJA" if dist<3000 else "AMARILLA"
  events.append({**e,"predio_cercano":features[idx]["properties"].get("predio","Predio CMPC"),"zona_admin":features[idx]["properties"].get("zona",""),
   "distancia_m":round(dist,1),"distancia_km":round(dist/1000,3),"orientacion":orient,"rumbo_grados":deg,"alerta":alert})
 if not events:raise RuntimeError("No hay avisos a 5 km o menos; se conserva el último snapshot.")
 payload={"generated_at":datetime.now(timezone.utc).isoformat(),"source":"SIDCO CONAF","event_count":len(events),"events":events,
  "predios":{"type":"FeatureCollection","features":[features[i] for i in sorted(selected)]}}
 tmp=OUT.with_suffix(".tmp");tmp.write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":")),encoding="utf-8");tmp.replace(OUT)
 print(f"Actualizados {len(events)} avisos y {len(selected)} predios relacionados.")
if __name__=="__main__":main()
