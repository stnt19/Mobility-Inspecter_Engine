import {unzip} from './vendor/fflate.js';
export async function hash(bytes){return [...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(v=>v.toString(16).padStart(2,'0')).join('')}
export async function unpack(file,allowed,maxBytes){
 if(file.size>maxBytes)throw Error('ZIP 파일이 허용 크기를 초과했습니다.');const bytes=new Uint8Array(await file.arrayBuffer());
 return new Promise((resolve,reject)=>{let total=0;unzip(bytes,{filter:entry=>{if(!allowed.includes(entry.name))return false;total+=entry.originalSize;if(!Number.isFinite(total)||total>maxBytes)throw Error('압축 해제 크기를 초과했습니다.');return true}},(err,files)=>{if(err){reject(err);return}if(allowed.some(k=>!files[k])){reject(Error('ZIP에 '+allowed.join(', ')+' 파일이 필요합니다.'));return}resolve(files)})});
}
// SQLite is owned by the Python runtime (inside the APK on Android).
async function request(url,options){const r=await fetch(url,options);if(!r.ok){let e;try{e=await r.json()}catch{}throw Error(e?.error||'자료 처리 실패')}return r}
function base64(bytes){let s='';const a=new Uint8Array(bytes);for(let i=0;i<a.length;i+=32768)s+=String.fromCharCode(...a.subarray(i,i+32768));return btoa(s)}
async function dataUrl(blob){return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(reader.error);reader.readAsDataURL(blob)})}
export async function readResource(key){
 const r=await fetch('/api/resources/'+key+'/metadata');if(r.status===404)return undefined;
 if(!r.ok)throw Error('자료 정보를 읽지 못했습니다.');
 const meta=await r.json(),bytes=await (await request('/api/resources/'+key+'/bytes')).arrayBuffer();
 return key==='model'?{manifest:meta,bytes}:{index:meta,bytes};
}
export async function storeResource(key,value){
 // loadModel already validates and commits the model atomically in Python.
 if(key==='model')return;
 await request('/api/catalog',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({index:value.index,bytes:base64(value.bytes)})});
}
export async function saveSession(session){const payload={...session,source_image:await dataUrl(session.source_image)};await request('/api/sessions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})}
export async function listSessions(){return (await request('/api/sessions')).json()}
export async function readSession(id){const s=await(await request('/api/sessions/'+encodeURIComponent(id))).json();s.source_image=await(await fetch(s.source_image)).blob();return s}
