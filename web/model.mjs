export const PROVIDERS = {met: 'The Metropolitan Museum of Art', aic: 'Art Institute of Chicago'};
export const AIC_FIELDS = 'id,title,date_display,date_start,date_end,artist_display,artist_title,place_of_origin,medium_display,dimensions,credit_line,is_public_domain,image_id,artwork_type_title,department_title,main_reference_number';
const str = value => typeof value === 'string' ? value.trim() : '';
const year = value => Number.isInteger(value) && Math.abs(value) <= 100000 ? value : null;
export function safeUrl(value, hosts) { try {const u = new URL(value);return u.protocol === 'https:' && !u.username && !u.password && (!hosts || hosts.includes(u.hostname)) ? u.href : '';} catch {return '';}}
export function normalizeMet(raw, retrievedAt) {
  if (!Number.isSafeInteger(raw.objectID) || !str(raw.title)) throw new Error('Invalid Met artwork');
  return {key:`met:${raw.objectID}`,id:raw.objectID,provider:'met',title:str(raw.title),artist:str(raw.artistDisplayName)||'Artist unrecorded',date:str(raw.objectDate)||'Date unrecorded',start:year(raw.objectBeginDate),end:year(raw.objectEndDate),place:str(raw.culture)||str(raw.artistNationality)||'Not recorded',medium:str(raw.medium)||'Not recorded',type:str(raw.objectName),department:str(raw.department),dimensions:str(raw.dimensions),credit:str(raw.creditLine),accession:str(raw.accessionNumber),publicDomain:raw.isPublicDomain===true,image:raw.isPublicDomain===true?safeUrl(raw.primaryImageSmall||raw.primaryImage,['images.metmuseum.org']):'',source:safeUrl(raw.objectURL,['www.metmuseum.org'])||`https://www.metmuseum.org/art/collection/search/${raw.objectID}`,api:`https://collectionapi.metmuseum.org/public/collection/v1/objects/${raw.objectID}`,retrievedAt};
}
export function normalizeAic(raw, retrievedAt) {
  if (!Number.isSafeInteger(raw.id) || !str(raw.title)) throw new Error('Invalid Chicago artwork');
  const id = str(raw.image_id);
  return {key:`aic:${raw.id}`,id:raw.id,provider:'aic',title:str(raw.title),artist:str(raw.artist_title)||str(raw.artist_display)||'Artist unrecorded',date:str(raw.date_display)||'Date unrecorded',start:year(raw.date_start),end:year(raw.date_end),place:str(raw.place_of_origin)||'Not recorded',medium:str(raw.medium_display)||'Not recorded',type:str(raw.artwork_type_title),department:str(raw.department_title),dimensions:str(raw.dimensions),credit:str(raw.credit_line),accession:str(raw.main_reference_number),publicDomain:raw.is_public_domain===true,image:raw.is_public_domain===true && /^[a-zA-Z0-9-]+$/.test(id)?`https://www.artic.edu/iiif/2/${id}/full/843,/0/default.jpg`:'',source:`https://www.artic.edu/artworks/${raw.id}`,api:`https://api.artic.edu/api/v1/artworks/${raw.id}`,retrievedAt};
}
export function validateConfig(c) {if (!c || !Array.isArray(c.presets) || !c.presets.every(x=>typeof x==='string'&&x.trim()) || !Number.isInteger(c.pageSize) || c.pageSize<1 || c.pageSize>100 || !Number.isInteger(c.requestTimeoutMs) || c.requestTimeoutMs<1000 || !Number.isInteger(c.metDetailDelayMs) || c.metDetailDelayMs<100 || typeof c.defaultQuery!=='string' || typeof c.aicUserAgent!=='string') throw new Error('Invalid collection configuration');return c;}
export function searchUrl(provider, query, page, pageSize) {
  if (!Number.isInteger(page)||page<1||!Number.isInteger(pageSize)||pageSize<1||pageSize>100) throw new Error('Invalid pagination');
  if (provider==='met') {const u=new URL('https://collectionapi.metmuseum.org/public/collection/v1.1/search');u.search=new URLSearchParams({q:query,hasImages:'true',offset:String((page-1)*pageSize),limit:String(pageSize)});return u.href;}
  if (provider==='aic') {const u=new URL('https://api.artic.edu/api/v1/artworks/search');u.searchParams.set('params',JSON.stringify({query:{bool:{must:[{multi_match:{query,fields:['title','artist_title','artist_display','medium_display','place_of_origin','subject_titles'],operator:'and'}}],filter:[{term:{is_public_domain:true}}]}},page,limit:pageSize,fields:AIC_FIELDS.split(',')}));return u.href;}
  throw new Error('Unsupported museum');
}
export function formatYear(value) {return value===null?'Undated':value<0?`${Math.abs(value)} BCE`:`${value} CE`;}
export function dateExtent(record) {if(record.start===null||record.end===null)return null;return [Math.min(record.start,record.end),Math.max(record.start,record.end)];}
export function filterRecords(records, {provider='all',text='',start=null,end=null,sort='oldest'}={}) {
  const needle=text.trim().toLocaleLowerCase();
  const result=records.filter(r=>{const extent=dateExtent(r);return(provider==='all'||r.provider===provider)&&(!needle||[r.title,r.artist,r.medium,r.place,r.type].join(' ').toLocaleLowerCase().includes(needle))&&(start===null||(extent&&extent[1]>=start))&&(end===null||(extent&&extent[0]<=end));});
  return result.sort((a,b)=>{if(sort==='title')return a.title.localeCompare(b.title);if(a.start===null&&b.start!==null)return 1;if(b.start===null&&a.start!==null)return -1;return (a.start-b.start)*(sort==='newest'?-1:1)||a.title.localeCompare(b.title);});
}
export function centuryGroups(records) {const groups=new Map();for(const r of records){const x=dateExtent(r);if(!x)continue;const mid=(x[0]+x[1])/2;const start=Math.floor(mid/100)*100;const group=groups.get(start)||{start,met:0,aic:0};group[r.provider]++;groups.set(start,group);}return [...groups.values()].sort((a,b)=>a.start-b.start);}
export function toCsv(records) {const fields=['title','artist','date','start','end','medium','place','provider','publicDomain','credit','source','retrievedAt'];const cell=v=>'"'+String(typeof v==='string'&&/^[=+@-]/.test(v)?"'"+v:(v??'')).replaceAll('"','""')+'"';return [fields,...records.map(r=>fields.map(k=>r[k]))].map(row=>row.map(cell).join(',')).join('\r\n');}
export function mergeRecords(before,after){return [...new Map([...before,...after].map(r=>[r.key,r])).values()];}
