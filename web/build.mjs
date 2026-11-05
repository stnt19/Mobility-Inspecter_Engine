import {cp,mkdir,readFile,writeFile,rm,readdir} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
const root=path.dirname(fileURLToPath(import.meta.url));
const out=path.join(root,'dist');await rm(out,{recursive:true,force:true});await mkdir(path.join(out,'vendor'),{recursive:true});await cp(path.join(root,'src'),out,{recursive:true});
for(const name of ['pdf.mjs','pdf.worker.mjs'])await cp(path.join(root,'node_modules/pdfjs-dist/build',name),path.join(out,'vendor',name));
await cp(path.join(root,'node_modules/pdfjs-dist/cmaps'),path.join(out,'vendor/cmaps'),{recursive:true});
await cp(path.join(root,'node_modules/pdfjs-dist/standard_fonts'),path.join(out,'vendor/standard_fonts'),{recursive:true});
await cp(path.join(root,'node_modules/fflate/esm/browser.js'),path.join(out,'vendor/fflate.js'));
for(const [pkg,name] of [['pdfjs-dist','PDFJS-LICENSE'],['fflate','FFLATE-LICENSE']])await cp(path.join(root,'node_modules',pkg,'LICENSE'),path.join(out,'vendor',name));
await writeFile(path.join(out,'assets.json'),JSON.stringify({model:null,catalog:null,samples:[]}));
async function files(dir){let result=[];for(const e of await readdir(dir,{withFileTypes:true})){const p=path.join(dir,e.name);result.push(...(e.isDirectory()?await files(p):[path.relative(out,p).replaceAll('\\','/')]));}return result}
const list=await files(out);const digest=createHash('sha256');for(const f of list.sort())digest.update(await readFile(path.join(out,f)));const sw=path.join(out,'sw.js');await writeFile(sw,(await readFile(sw,'utf8')).replace(/const CACHE='[^']+'/,"const CACHE='mobility-engine-web-"+digest.digest('hex').slice(0,16)+"'"));
await writeFile(path.join(out,'cache-files.json'),JSON.stringify(list));
console.log('Built offline runtime: '+out);
