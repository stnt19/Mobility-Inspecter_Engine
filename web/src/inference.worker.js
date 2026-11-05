// Transport only: image preprocessing, ONNX and NMS run in Python.
let manifest;
self.onmessage=async({data:m})=>{try{
 let r;
 if(m.type==='load') r=await fetch('/api/model',{method:'POST',headers:{'Content-Type':'application/octet-stream','X-Metadata':btoa(unescape(encodeURIComponent(JSON.stringify(m.manifest))))},body:m.bytes});
 else if(m.type==='infer'){
  if(!manifest)throw Error('모델을 먼저 불러오세요.');
  r=await fetch('/api/infer',{method:'POST',headers:{'Content-Type':'application/octet-stream','X-Model-Sha256':manifest.sha256},body:m.image});
 }else throw Error('지원하지 않는 작업입니다.');
 const result=await r.json();if(!r.ok)throw Error(result.error||'Python 처리 실패');
 if(m.type==='load')manifest=result;
 self.postMessage({id:m.id,ok:true,result});
}catch(e){self.postMessage({id:m.id,ok:false,error:e.message})}};
