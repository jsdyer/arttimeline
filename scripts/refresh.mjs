#!/usr/bin/env node
// Fetch only the configured first-visit collection; live search is independent.
import {readFile,writeFile,mkdir,rename} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {normalizeMet,normalizeAic,validateConfig} from '../web/model.mjs';
const root=fileURLToPath(new URL('../',import.meta.url));
const config=validateConfig(JSON.parse(await readFile(root+'web/config.json','utf8')));
const stamp=new Date().toISOString();const records=[];const sources=[];
for(const [provider,key] of [['met','metObjectIds'],['aic','aicObjectIds']]) {
 const ids=config.baseline?.[key];if(!Array.isArray(ids)||!ids.every(Number.isSafeInteger)||new Set(ids).size!==ids.length)throw new Error('Invalid baseline IDs for '+provider);
 for(const id of ids){
  const url=provider==='met'?`https://collectionapi.metmuseum.org/public/collection/v1/objects/${id}`:`https://api.artic.edu/api/v1/artworks/${id}`;
  let r=await fetch(url,{headers:provider==='aic'?{'AIC-User-Agent':config.aicUserAgent}:{'User-Agent':config.aicUserAgent},signal:AbortSignal.timeout(config.requestTimeoutMs)});
  let sourceUrl=url, sourceKind='museum API';
  if(!r.ok && provider==='aic'){
    sourceUrl=`https://raw.githubusercontent.com/art-institute-of-chicago/api-data/main/json/artworks/${id}.json`;
    r=await fetch(sourceUrl,{signal:AbortSignal.timeout(config.requestTimeoutMs)});sourceKind='museum published API-data sample';
  }
  if(!r.ok)throw new Error(`${provider} ${id}: HTTP ${r.status}; prior collection retained`);
  const raw=await r.json();const art=provider==='met'?normalizeMet(raw,stamp):normalizeAic(raw.data||raw,stamp);
  art.retrievedFrom=sourceUrl;art.sourceKind=sourceKind;art.sourceUpdatedAt=(raw.data||raw).updated_at||null;records.push(art);sources.push(sourceUrl);
  console.log(provider,id,art.title,art.publicDomain?'public domain':'metadata only');
  await new Promise(resolve=>setTimeout(resolve,1100));
 }
}
if(!records.length)throw new Error('Baseline cannot be empty');
const payload={schemaVersion:1,retrievedAt:stamp,source:'Configured first-visit collection, not a complete collection or live search',records,sources};
await mkdir(root+'web/data',{recursive:true});await writeFile(root+'web/data/collection.tmp',JSON.stringify(payload,null,2)+'\n');await rename(root+'web/data/collection.tmp',root+'web/data/collection.json');
console.log('Saved',records.length,'artworks');
