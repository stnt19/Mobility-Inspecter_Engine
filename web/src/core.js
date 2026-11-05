export const CLASSES=['battery','fuse_box','air_cleaner','coolant_reservoir','fuel_filter','oil_filler_cap','oil_dipstick','alternator','ac_compressor','belt_tensioner','egr_valve','washer_fluid_reservoir'];
export const NAMES=['배터리','퓨즈 박스','에어 클리너','냉각수 보조 탱크','연료 필터','오일 주입구 캡','오일 레벨 게이지','발전기','에어컨 컴프레서','벨트 텐셔너','EGR 밸브','워셔액 탱크'];
export function nameOf(cls){return NAMES[CLASSES.indexOf(cls)]||cls}
export function validateManifest(m){
 if(m?.schema_version!==1||m.task!=='rexton_sports_2023_engine_parts'||!['yolov8','yolo11'].includes(m.architecture)||![640,960,1280].includes(m.input_size)||m.class_schema!=='engine-seed-v2'||!Array.isArray(m.classes)||!m.classes.length||new Set(m.classes).size!==m.classes.length||m.classes.some(c=>!CLASSES.includes(c))||!/^[a-f0-9]{64}$/i.test(m.sha256))throw Error('지원하지 않는 모델 manifest입니다.');return m;
}
export function letterbox(width,height,size=640){
 if(!(width>0&&height>0))throw Error('이미지 크기가 올바르지 않습니다.');
 const scale=Math.min(size/width,size/height), w=Math.round(width*scale),h=Math.round(height*scale);
 return {width,height,size,scale,w,h,left:Math.max(0,Math.round((size-w)/2-.1)),top:Math.max(0,Math.round((size-h)/2-.1))};
}
export function iou(a,b){const iw=Math.max(0,Math.min(a[2],b[2])-Math.max(a[0],b[0])),ih=Math.max(0,Math.min(a[3],b[3])-Math.max(a[1],b[1]));const inter=iw*ih;return inter/Math.max(1e-9,(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter)}
export function nms(rows,threshold=.45,limit=50){const kept=[];for(const row of [...rows].sort((a,b)=>b.score-a.score)){if(!kept.some(k=>k.class===row.class&&iou(k.box,row.box)>threshold)){kept.push(row);if(kept.length>=limit)break}}return kept}
export function decode(data,dims,classes,geometry,confidence=.05){
 if(dims.length!==3||dims[0]!==1||dims[1]!==classes.length+4||dims[2]!==8400||data.length!==dims[1]*dims[2])throw Error('모델 출력은 [1, 4+클래스 수, 8400]이어야 합니다.');
 const count=dims[2], rows=[],{left,top,scale,width,height}=geometry;
 for(let i=0;i<count;i++){
 let score=-Infinity,cls=-1;for(let c=0;c<classes.length;c++){const s=data[(c+4)*count+i];if(s>score){score=s;cls=c}}
 if(!Number.isFinite(score)||score<confidence||score>1)continue;
 const x=data[i],y=data[count+i],w=data[2*count+i],h=data[3*count+i];if(![x,y,w,h].every(Number.isFinite)||w<=0||h<=0)continue;
 const clamp=(v,max)=>Math.max(0,Math.min(max,v));
 const box=[clamp((x-w/2-left)/scale,width),clamp((y-h/2-top)/scale,height),clamp((x+w/2-left)/scale,width),clamp((y+h/2-top)/scale,height)];
 if(box[2]>box[0]&&box[3]>box[1])rows.push({class:classes[cls],score,box});
 }return nms(rows);
}
export function validateCatalog(c){
 if(c?.schema_version!==1||!Array.isArray(c.rows)||!c.rows.length||c.rows.length>20000||!Number.isInteger(c.page_count)||c.page_count<1||c.page_count>3000||!/^[a-f0-9]{64}$/i.test(c.source_sha256))throw Error('올바른 카탈로그 색인이 아닙니다.');
 const ids=new Set();for(const r of c.rows){
 if(typeof r.id!=='string'||ids.has(r.id)||typeof r.part_number!=='string'||!r.relations||typeof r.relations!=='object'||!Number.isInteger(r.pdf_page)||r.pdf_page<1||r.pdf_page>c.page_count||![r.page_width,r.page_height].every(v=>Number.isFinite(v)&&v>0)||!Array.isArray(r.row_rect)||r.row_rect.length!==4||!r.row_rect.every(Number.isFinite)||r.row_rect[0]<0||r.row_rect[1]<0||r.row_rect[2]<=r.row_rect[0]||r.row_rect[3]<=r.row_rect[1]||r.row_rect[2]>r.page_width||r.row_rect[3]>r.page_height||!Array.isArray(r.diagram_pages)||r.diagram_pages.some(p=>!Number.isInteger(p)||p<1||p>c.page_count)||Object.entries(r.relations).some(([k,v])=>!CLASSES.includes(k)||!['primary','related'].includes(v)))throw Error('카탈로그 행 또는 페이지 좌표가 올바르지 않습니다.');ids.add(r.id);
 }return c;
}
export function searchCatalog(c,cls,query=''){
 const norm=s=>String(s??'').normalize('NFKC').toLocaleLowerCase().replace(/[\s-]/g,'');const q=norm(query);
 return c.rows.filter(r=>(!cls||r.relations[cls])&&norm([r.part_number,r.name_ko,r.name_en,r.options,r.remarks,r.group_code].join(' ')).includes(q)).sort((a,b)=>(a.relations[cls]!=='primary')-(b.relations[cls]!=='primary')||a.pdf_page-b.pdf_page||a.row_rect[1]-b.row_rect[1]);
}
