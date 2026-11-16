import os,io,json,zipfile,math,re
from pathlib import Path
from datetime import datetime,timezone
import requests
from xml.etree import ElementTree as ET
from shapely.geometry import Point,shape
from shapely.ops import transform,nearest_points
from shapely.strtree import STRtree
from pyproj import Transformer
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/"data"; OUT=DATA/"events.json"; MAX_DISTANCE=5000
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
def bearing(a,b):
 lo1,la1=map(math.radians,a);lo2,la2=map(math.radians,b);dl=lo2-lo1
 y=math.sin(dl)*math.cos(la2);x=math.cos(la1)*math.sin(la2)-math.sin(la1)*math.cos(la2)*math.cos(dl)
 return int(round((math.degrees(math.atan2(y,x))+360)%360))
def main():
 url=os.environ.get("SIDCO_URL","").strip()
 if not url:raise RuntimeError("Falta el secreto SIDCO_URL en GitHub.")
 r=requests.get(url,timeout=60,headers={"User-Agent":"CMPC-Territorial-Monitor/1.0"});r.raise_for_status()
 raw=parse_events(parse_root(r.content))
 if not raw:raise RuntimeError("SIDCO respondió sin avisos KML reconocibles; se conserva el último snapshot.")
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
