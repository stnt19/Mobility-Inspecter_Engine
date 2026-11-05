import {NAMES, nameOf} from './core.js';
const $ = id => document.getElementById(id);
let stream, generation = 0, lastFrame = null, livePending = false, overlayTimer;
const titles = ['비전 점검','대상 지정','실시간 촬영','촬영 결과'];
const descriptions = ['차량 또는 부품을 촬영하여 현장 점검 내용을 기록합니다.','점검할 장비번호와 부위를 선택합니다.','대상을 화면 중앙에 맞춰 주세요.','원본 사진과 탐지 결과를 대조하고 점검 내용을 기록합니다.'];
export function stopCamera() {
  generation++;
  stream?.getTracks().forEach(track => track.stop());
  stream = null; lastFrame = null;
  clearTimeout(overlayTimer);
  $('liveVideo').srcObject = null;
  $('liveOverlay').width = 1;
  $('freezeAnalysis').disabled = true;
  $('takePhoto').disabled = true;
}
window.stopInspectionCamera = stopCamera;
function step(index) {
  if (index !== 2) stopCamera();
  document.querySelectorAll('[data-step]').forEach(el => el.hidden = Number(el.dataset.step) !== index);
  $('inspectionEditor').hidden = index !== 3;
  $('stepTitle').textContent = titles[index];
  $('stepDescription').textContent = descriptions[index];
  document.querySelectorAll('.steps li').forEach((el,i) => el.classList.toggle('current', i === index));
}
window.showInspectionStep = step;
for (const name of NAMES) {const o=document.createElement('option');o.textContent=name;$('inspectionArea').append(o)}
document.querySelectorAll('[data-mode]').forEach(button => button.onclick=()=>{
  $('captureMode').value=button.dataset.mode;
  document.querySelectorAll('[data-mode]').forEach(el=>el.classList.toggle('selected',el===button));
  $('inspectionArea').value=button.dataset.mode==='부품 촬영'?'엔진룸':'외관';
});
function target() {
  const value=$('vehicleId').value.trim();
  $('targetError').textContent=value?'':'장비번호를 입력하세요.';
  if (!value) $('vehicleId').focus();
  return !!value;
}
function fallback(){if(!target())return;step(3);window.inspectionEngine?.selectPhoto()}
function snapshot(){
  const video=$('liveVideo');if(!stream||!video.videoWidth)throw Error('카메라가 준비되지 않았습니다.');
  const ratio=Math.min(1,1920/Math.max(video.videoWidth,video.videoHeight));
  const canvas=document.createElement('canvas');canvas.width=Math.round(video.videoWidth*ratio);canvas.height=Math.round(video.videoHeight*ratio);
  canvas.getContext('2d').drawImage(video,0,0,canvas.width,canvas.height);
  return new Promise((resolve,reject)=>canvas.toBlob(blob=>blob?resolve({blob,width:canvas.width,height:canvas.height}):reject(Error('촬영 실패')),'image/png'));
}
async function loop(token) {
  if(token!==generation||!stream)return;
  if(!livePending&&$('liveAnalysis').checked&&window.inspectionEngine?.ready()&&$('captureMode').value==='부품 촬영'){
    livePending=true;
    try{
      const frame=await snapshot(),started=performance.now();
      const result=await window.inspectionEngine.analyze(frame.blob);
      if(token!==generation)return;
      lastFrame={...frame,result,started};$('freezeAnalysis').disabled=false;
      $('cameraStatus').textContent=`${result.detections.length}개 부품 후보 · ${(result.elapsed_ms/1000).toFixed(2)}초 분석`;
      const age=performance.now()-started;
      if(age<1500){
        const canvas=$('liveOverlay');canvas.width=frame.width;canvas.height=frame.height;
        const ctx=canvas.getContext('2d');ctx.strokeStyle='#03C75A';ctx.lineWidth=3;ctx.font='18px sans-serif';ctx.fillStyle='#03C75A';
        for(const row of result.detections){const [x,y,x2,y2]=row.box;ctx.strokeRect(x,y,x2-x,y2-y);ctx.fillText(nameOf(row.class),x,Math.max(20,y-5))}
        clearTimeout(overlayTimer);overlayTimer=setTimeout(()=>{if(token===generation)canvas.width=1},1500-age);
      }else $('liveOverlay').width=1;
    }catch(error){if(token===generation)$('cameraStatus').textContent=error.message}
    finally{livePending=false}
  }
  if(token===generation)setTimeout(()=>loop(token),500);
}
async function start(){
  if(!target())return;stopCamera();step(2);const token=generation;
  $('liveTarget').textContent=$('vehicleId').value+' · '+$('inspectionArea').value;
  $('cameraStatus').textContent='카메라를 연결합니다.';
  try{
    if(!navigator.mediaDevices?.getUserMedia)throw Error('이 환경에서는 카메라를 사용할 수 없습니다.');
    const next=await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:'environment'},width:{ideal:1280},height:{ideal:720}},audio:false});
    if(token!==generation){next.getTracks().forEach(t=>t.stop());return}
    stream=next;$('liveVideo').srcObject=next;await $('liveVideo').play();
    if(token!==generation)return;
    $('takePhoto').disabled=false;
    $('cameraStatus').textContent=window.inspectionEngine?.ready()?'촬영할 부품을 중앙에 맞춰 주세요.':'사진 촬영 가능 · 자동 탐지는 모델 ZIP을 가져온 뒤 사용할 수 있습니다.';
    loop(token);
  }catch(error){if(token===generation){stopCamera();$('cameraStatus').textContent=error.message+' 카메라 권한을 확인하거나 사진 선택·수동 점검을 이용하세요.'}}
}
$('beginInspection').onclick=()=>step(1);
$('targetBack').onclick=()=>step(0);
$('startCamera').onclick=start;
$('retryCamera').onclick=start;
$('changeTarget').onclick=()=>step(1);
$('selectInstead').onclick=fallback;
$('cameraFallback').onclick=fallback;
$('takePhoto').onclick=async()=>{try{const frame=await snapshot();await window.inspectionEngine.review(frame.blob)}catch(e){$('cameraStatus').textContent=e.message}};
$('freezeAnalysis').onclick=async()=>{
  const frame=lastFrame;if(!frame)return;
  const age=(performance.now()-frame.started)/1000;
  const restored=await window.inspectionEngine.review(frame.blob,frame.result.detections,frame.result.model);
  if(restored)$('appStatus').textContent=`${age.toFixed(1)}초 전 분석 장면을 고정했습니다. 사진과 박스는 같은 프레임입니다.`;
};
$('liveAnalysis').onchange=()=>{if(!$('liveAnalysis').checked){$('liveOverlay').width=1;lastFrame=null;$('freezeAnalysis').disabled=true}};
$('newInspection').onclick=()=>{if(!window.inspectionDirty?.()||confirm('저장하지 않은 변경 사항이 있습니다. 새 점검을 시작할까요?'))step(0)};
$('tabletHistory').onclick=()=>window.inspectionEngine?.history();
$('tabletResources').onclick=()=>$('resourcePanel').scrollIntoView({behavior:'smooth'});
document.addEventListener('visibilitychange',()=>{if(document.hidden)stopCamera()});
step(0);
