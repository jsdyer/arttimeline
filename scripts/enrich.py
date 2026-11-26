#!/usr/bin/env python3
"""Extend the saved opening selection from official open museum data.
No image harvesting: only metadata exports, configured Getty records and IIIF manifests.
Write only after every configured object has been found and validated.
"""
import argparse,csv,hashlib,json,re,tempfile,time
from datetime import datetime,timezone
from html import unescape
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parents[1]
CMA='https://media.githubusercontent.com/media/ClevelandMuseumArt/openaccess/master/data.json'
NGA='https://raw.githubusercontent.com/NationalGalleryOfArt/opendata/main/data/'
UA='CoolCode ArtTimeline/1.0 (https://coolcode.ca/arttimeline/; jeffdyer@gmail.com)'
def clean(value):return unescape(re.sub(r'<[^>]*>','',str(value or ''))).strip()
def safe(value,hosts):
 try:
  u=urlsplit(str(value));return str(value) if u.scheme=='https' and u.hostname in hosts and not u.username and not u.password else ''
 except ValueError:return ''
def number(value):
 try:
  x=int(value);return x if abs(x)<=100000 else None
 except (ValueError,TypeError):return None
def pixels(image,url):
 w,h=number(image.get('width')),number(image.get('height'))
 return {'width':w,'height':h,'url':url} if w and h and w>0 and h>0 and url else None
def core(provider,ident,title,stamp):
 if not clean(title):raise ValueError('Missing object title')
 return dict(key=f'{provider}:{ident}',id=ident,provider=provider,title=clean(title),retrievedAt=stamp,publicDomain=False,image='',pixelSize=None,start=None,end=None,artist='Artist unrecorded',date='Date unrecorded',place='Not recorded',medium='Not recorded',type='',department='',dimensions='',credit='',accession='',rights='No open image supplied')
def cma_record(x,stamp):
 r=core('cma',x['id'],x['title'],stamp);images=x.get('images') or {};opened=x.get('share_license_status')=='CC0';web=images.get('web') or {};large=images.get('print') or {}
 r.update(artist='; '.join(clean(a.get('description')) for a in x.get('creators',[]) if a.get('description')) or 'Artist unrecorded',date=clean(x.get('creation_date')) or 'Date unrecorded',start=number(x.get('creation_date_earliest')),end=number(x.get('creation_date_latest')),place='; '.join(x.get('culture') or []) or 'Not recorded',medium=clean(x.get('technique')) or 'Not recorded',type=clean(x.get('type')),department=clean(x.get('department')),dimensions=clean(x.get('measurements')),credit=clean(x.get('creditline')),accession=clean(x.get('accession_number')),publicDomain=opened,rights='CC0 · Cleveland Open Access' if opened else 'Not marked CC0',source=safe(x.get('url'),['clevelandart.org','www.clevelandart.org']) or f'https://www.clevelandart.org/art/{x.get("accession_number","")}',api=CMA,retrievedFrom=CMA,sourceKind='Cleveland official open-data export',sourceUpdatedAt=x.get('updated_at'))
 if opened:r.update(image=safe(web.get('url'),['openaccess-cdn.clevelandart.org']),pixelSize=pixels(large,safe(large.get('url'),['openaccess-cdn.clevelandart.org'])))
 return r

def nga_record(x,image,stamp):
 r=core('nga',int(x['objectid']),x['title'],stamp);opened=image.get('openaccess')=='1';service=safe(image.get('iiifurl'),['api.nga.gov'])
 r.update(artist=clean(x.get('attribution')) or 'Artist unrecorded',date=clean(x.get('displaydate')) or 'Date unrecorded',start=number(x.get('beginyear')),end=number(x.get('endyear')),medium=clean(x.get('medium')) or 'Not recorded',type=clean(x.get('classification')),department=clean(x.get('departmentabbr')),dimensions=clean(x.get('dimensions')),credit=clean(x.get('creditline')),accession=clean(x.get('accessionnum')),publicDomain=opened,rights='NGA Open Access · image openaccess=1' if opened else 'Not designated Open Access',source=f'https://www.nga.gov/collection/art-object-page.{x["objectid"]}.html',api=NGA+'objects.csv',retrievedFrom=NGA+'published_images.csv',sourceKind='NGA official collection and image CSV exports',sourceUpdatedAt=x.get('lastdetectedmodification'))
 if opened and service:r.update(image=service+'/full/!800,800/0/default.jpg',pixelSize=pixels(image,service+'/full/full/0/default.jpg'))
 return r

def getty_record(x,manifest,stamp):
 ident=x['id'].rsplit('/',1)[-1]
 def note(items,label):return next((clean(a.get('content')) for a in items if a.get('_label')==label),'')
 notes=x.get('referred_to_by',[]);production=x.get('produced_by') or {};timespan=production.get('timespan') or {}
 title=note(x.get('identified_by',[]),'Preferred Title') or x.get('_label');r=core('getty',ident,title,stamp)
 source=next((safe(a.get('id'),['www.getty.edu']) for a in x.get('subject_of',[]) if a.get('format')=='text/html'),'')
 canvas=next((a for a in manifest.get('items',[]) if a.get('type')=='Canvas'),{});rights=canvas.get('rights',manifest.get('rights',''));opened=rights in ['http://creativecommons.org/publicdomain/zero/1.0/','https://creativecommons.org/publicdomain/zero/1.0/']
 body=next((a.get('body',{}) for p in canvas.get('items',[]) for a in p.get('items',[]) if isinstance(a.get('body'),dict) and a['body'].get('type')=='Image'),{})
 thumb=next((safe(t.get('id'),['media.getty.edu']) for t in canvas.get('thumbnail',[])),'');full=safe(body.get('id'),['media.getty.edu'])
 def y(v):
  m=re.match(r'^(-?\d{4,})-',str(v or ''));return number(m[1]) if m else None
 r.update(artist=note(production.get('referred_to_by',[]),'Artist/Maker (Producer) Description') or 'Artist unrecorded',date=note(timespan.get('identified_by',[]),'Dates') or 'Date unrecorded',start=y(timespan.get('begin_of_the_begin')),end=y(timespan.get('end_of_the_end')),place=note(notes,'Place Created') or note(notes,'Culture Statement') or 'Not recorded',medium=note(notes,'Materials Description') or 'Not recorded',type=note(notes,'Object Type'),dimensions=note(notes,'Dimensions Statement'),credit=note(notes,'Source Credit Line'),accession=note(x.get('identified_by',[]),'Accession Number'),publicDomain=opened,rights='CC0 · Getty Open Content; metadata text CC BY 4.0' if opened else 'Image rights not explicitly CC0',source=source,api=x['id'],retrievedFrom=manifest['id'],sourceKind='Getty Linked Art record + image-level IIIF rights')
 if opened:r.update(image=thumb,pixelSize=pixels(body,full))
 return r

def fetch_file(url,path,max_bytes=550_000_000):
 if path.exists():return path
 request=Request(url,headers={'User-Agent':UA,'Accept':'application/json,text/csv,*/*'})
 temp=path.with_suffix(path.suffix+'.tmp');size=0
 try:
  with urlopen(request,timeout=90) as response,temp.open('wb') as out:
   while chunk:=response.read(1024*1024):
    size+=len(chunk)
    if size>max_bytes:raise ValueError('Upstream export exceeded bounded download size')
    out.write(chunk)
  temp.replace(path)
 except Exception:
  temp.unlink(missing_ok=True);raise
 return path

def jpeg_size(data):
 if data[:2]!=b'\xff\xd8':raise ValueError('Expected a JPEG image')
 i=2
 while i+4<=len(data):
  if data[i]!=255:raise ValueError('Invalid JPEG marker')
  while i<len(data) and data[i]==255:i+=1
  if i>=len(data):return None
  marker=data[i];i+=1
  if marker in [0xd8,0xd9,0x01] or 0xd0<=marker<=0xd7:continue
  length=int.from_bytes(data[i:i+2],'big')
  if length<2:raise ValueError('Invalid JPEG segment length')
  if marker in [0xc0,0xc1,0xc2,0xc3,0xc5,0xc6,0xc7,0xc9,0xca,0xcb,0xcd,0xce,0xcf]:
   if i+7>len(data):return None
   return int.from_bytes(data[i+5:i+7],'big'),int.from_bytes(data[i+3:i+5],'big')
  i+=length
 return None

def verify_pixels(record,cache,stamp):
 p=record['pixelSize'];cached=cache/(hashlib.sha256(p['url'].encode()).hexdigest()+'.pixels.json')
 if cached.exists():verified=json.loads(cached.read_text())
 else:
  request=Request(p['url'],headers={'User-Agent':UA,'Range':'bytes=0-131071'})
  with urlopen(request,timeout=35) as response:
   data=b'';size=None
   for _ in range(32):
    chunk=response.read(4096)
    if not chunk:break
    data+=chunk;size=jpeg_size(data)
    if size:break
  if not size or min(size)<=0:raise ValueError('Could not verify bounded JPEG pixel dimensions')
  verified={'width':size[0],'height':size[1],'verifiedAt':stamp};cached.write_text(json.dumps(verified));time.sleep(.15)
 record['pixelSize']={**p,'metadataWidth':p['width'],'metadataHeight':p['height'],**verified,'verification':'JPEG image header; at most 128 KiB read'}

def collect(cache,config,stamp):
 result=[];provenance=[]
 def read(url,name):
  path=fetch_file(url,cache/name)
  digest=hashlib.sha256()
  with path.open('rb') as stream:
   for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
  provenance.append({'url':url,'sha256':digest.hexdigest(),'bytes':path.stat().st_size,'retrievedAt':stamp});return path
 ids=set(config['baseline']['cmaObjectIds']);all_cma=json.loads(read(CMA,'cleveland.json').read_text());found={x['id']:x for x in all_cma if x['id'] in ids}
 if set(found)!=ids:raise ValueError('Configured Cleveland objects are missing from export')
 result.extend(cma_record(found[i],stamp) for i in config['baseline']['cmaObjectIds']);del all_cma,found
 ids={str(i) for i in config['baseline']['ngaObjectIds']}
 with read(NGA+'objects.csv','nga-objects.csv').open(newline='') as f:objects={x['objectid']:x for x in csv.DictReader(f) if x['objectid'] in ids}
 with read(NGA+'published_images.csv','nga-images.csv').open(newline='') as f:
  images={}
  for x in csv.DictReader(f):
   if x['depictstmsobjectid'] in ids and x['viewtype']=='primary' and x['openaccess']=='1':images.setdefault(x['depictstmsobjectid'],x)
 if set(objects)!=ids or set(images)!=ids:raise ValueError('Configured NGA objects or designated open images missing')
 result.extend(nga_record(objects[str(i)],images[str(i)],stamp) for i in config['baseline']['ngaObjectIds'])
 for ident in config['baseline']['gettyObjectIds']:
  if not re.fullmatch(r'[a-f0-9-]{36}',ident):raise ValueError('Invalid Getty identifier')
  url='https://data.getty.edu/museum/collection/object/'+ident;raw=json.loads(read(url,'getty-'+ident+'.json').read_text())
  manifesturl=next((a.get('id') for a in raw.get('subject_of',[]) if a.get('id','').startswith('https://media.getty.edu/iiif/manifest/3/')),None)
  if not manifesturl:raise ValueError('Getty IIIF v3 image manifest missing')
  manifest=json.loads(read(manifesturl,'getty-manifest-'+ident+'.json').read_text());result.append(getty_record(raw,manifest,stamp));time.sleep(.5)
 if not all(x['source'] and x['publicDomain'] and x['image'] and x['pixelSize'] for x in result):raise ValueError('Incomplete open-image provenance; previous collection retained')
 for record in result:verify_pixels(record,cache,stamp)
 return result,provenance

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--cache-dir',type=Path);args=parser.parse_args();config=json.loads((ROOT/'web/config.json').read_text());stamp=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
 with tempfile.TemporaryDirectory() as temporary:
  cache=args.cache_dir or Path(temporary);cache.mkdir(exist_ok=True,parents=True);extra,sources=collect(cache,config,stamp)
 target=ROOT/'web/data/collection.json';payload=json.loads(target.read_text());payload['records']=[r for r in payload['records'] if r['provider'] in ['met','aic']]+extra;payload['retrievedAt']=stamp;payload['source']='Configured opening selection; each record preserves its own metadata retrieval date. Not complete museum catalogues.';payload['additionalSources']=sources;payload['expandedSchemaVersion']=1
 temp=target.with_suffix('.tmp');temp.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n');temp.replace(target);print(f'Extended opening collection to {len(payload["records"])} real records across five museums')
if __name__=='__main__':main()
