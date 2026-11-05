// Controller integration with browser API doubles; not a real browser/IndexedDB test.
import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFile} from 'node:fs/promises';
import {webcrypto} from 'node:crypto';
import * as core from '../src/core.js';
import * as sessions from '../src/session.js';
class Element {
 constructor(){this.children=[];this.value='';this.checked=false;this.style={setProperty(){}};this.classList={remove(){},toggle(){}};this.parentElement={hidden:false}}
 append(e){this.children.push(e)} replaceChildren(){this.children=[]} setAttribute(){} removeAttribute(){} addEventListener(){} showModal(){this.open=true} close(){this.open=false}
 getContext(){return {drawImage(){},fillRect(){},getImageData(){return {data:new Uint8ClampedArray(640*640*4)}}}} toBlob(cb){cb(new Blob(['pixels'],{type:'image/png'}))} toDataURL(){return 'data:image/jpeg;base64,AA=='}
}
async function harness(){
 const nodes=new Map();const get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id)};get('threshold').value=35;
 const saved=new Map();let fail=false;
 const c=vm.createContext({...core,...sessions,Blob,URL,URLSearchParams,crypto:webcrypto,structuredClone,setTimeout,clearTimeout,console,
 document:{getElementById:get,createElement:()=>new Element(),querySelector:()=>get('frame')},window:{addEventListener(){}},navigator:{},location:{search:''},isSecureContext:true,
 pdfjs:{GlobalWorkerOptions:{}},Image:class {async decode(){}},createImageBitmap:async()=>({width:100,height:80,close(){}}),confirm:()=>true,
 fetch:async()=>({ok:true,json:async()=>({})}),readResource:async()=>null,storeResource:async()=>{},hash:async()=>'',unpack:async()=>{},
 saveSession:async s=>{if(fail)throw Error('QuotaExceeded');saved.set(s.id,structuredClone(s))},listSessions:async()=>[...saved.values()],readSession:async id=>structuredClone(saved.get(id)),
 Worker:class {postMessage(m){queueMicrotask(()=>this.onmessage({data:{id:m.id,ok:true,result:m.type==='infer'?{detections:[{class:'battery',box:[10,10,50,50],score:.9}],elapsed_ms:5}:{}}}))}terminate(){}}
 });
 let source=await readFile(new URL('../src/app.js',import.meta.url),'utf8');source=source.replace(/^import .*;\r?\n/gm,'').replaceAll('import.meta.url',"'https://example.test/app.js'");vm.runInContext(source,c);await new Promise(setImmediate);
 return {get,saved,run:code=>vm.runInContext(code,c),fail:()=>{fail=true}};
}
test('photo → inference → correction → save → reopen keeps original AI and user changes separate',async()=>{
 const h=await harness();
 await h.run("openPhoto(new Blob(['original-photo']),'engine.jpg')");
 await h.run("loadModel({manifest:{schema_version:1,architecture:'yolo11',task:'rexton_sports_2023_engine_parts',class_schema:'engine-seed-v2',input_size:640,classes:['battery'],sha256:'a'.repeat(64)},bytes:new ArrayBuffer(1)})");
 await h.get('infer').onclick();h.get('parts').children[0].onclick();h.get('editBox').onclick();h.get('editClass').value='fuse_box';h.get('editForm').onsubmit({preventDefault(){}});
 h.get('sessionNote').value='품번 확인 필요';h.get('sessionNote').oninput();await h.get('saveSession').onclick();
 const first=[...h.saved.values()][0];assert.equal(first.original[0].class,'battery');assert.equal(first.reviewed[0].class,'fuse_box');assert.equal(first.reviewed[0].score,null);assert.equal(await first.source_image.text(),'original-photo');
 await h.run("openPhoto(new Blob(['other']),'other.jpg')");await h.run(`restoreSession('${first.id}')`);
 assert.equal(h.get('sessionNote').value,'품번 확인 필요');assert.equal(h.run('predictions[0].class'),'fuse_box');assert.equal(h.run('resultModel.sha256'),'a'.repeat(64));assert.equal(h.run('dirty'),false);
});
test('quota failure keeps unsaved changes and does not replace previously saved record',async()=>{
 const h=await harness();await h.run("openPhoto(new Blob(['photo']),'engine.jpg')");await h.get('saveSession').onclick();const id=[...h.saved.keys()][0];h.get('sessionNote').value='새 메모';h.get('sessionNote').oninput();h.fail();await h.get('saveSession').onclick();
 assert.equal(h.saved.get(id).note,'');assert.equal(h.get('sessionNote').value,'새 메모');assert.equal(h.run('dirty'),true);assert.match(h.get('appStatus').textContent,/저장 실패/);assert.equal(h.get('saveSession').disabled,false);
});
