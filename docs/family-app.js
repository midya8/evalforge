import {familyReport,parseInput} from './family-engine.js';
const $=id=>document.getElementById(id), txt=(tag,text)=>{const n=document.createElement(tag);n.textContent=text;return n;};
window.currentFamily=null;
function reset(message='Input changed. Enumerate again.'){window.currentFamily=null;$('results').hidden=true;$('export-input').disabled=true;$('export-report').disabled=true;$('status').textContent=message;}
function table(id,rows){$(id).replaceChildren(...rows.map(row=>{const tr=document.createElement('tr');row.forEach(v=>tr.append(txt('td',String(v))));return tr;}));}
const join=x=>x.join(', ')||'none', yn=x=>x?'yes':'no';
function chart(r){const svg=$('chart'),w=Math.max(240,svg.parentElement.clientWidth-2),h=240,pad=44,values=r.maximum_histogram,maxX=Math.max(1,...values.map(v=>v.value)),maxY=Math.max(1,...values.map(v=>v.count));svg.setAttribute('viewBox',`0 0 ${w} ${h}`);svg.replaceChildren();function node(tag,attrs,text){const n=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v]of Object.entries(attrs))n.setAttribute(k,v);if(text!==undefined)n.textContent=text;svg.append(n);return n;}
 const span=w-pad-24,barWidth=Math.max(2,Math.min(22,span/(values.length*2||1)));for(const v of values){const x=pad+v.value/maxX*span,y=185-v.count/maxY*140;node('rect',{class:'bar',x:x-barWidth/2,y,width:barWidth,height:185-y,'data-value':v.value,'data-count':v.count});}
 const x=pad+r.observed_maximum/maxX*span;node('line',{class:'observed',x1:x,x2:x,y1:30,y2:190});node('text',{x:pad,y:22},`count / ${r.orbit_size} signs`);node('text',{x:pad,y:212},'0');node('text',{x:w-24,y:212,'text-anchor':'end'},maxX);node('text',{x:w/2,y:233,'text-anchor':'middle'},'maximum absolute sum (ticks)');
}
function show(r){window.currentFamily=r;$('results').hidden=false;$('export-input').disabled=false;$('export-report').disabled=false;
 $('metrics').replaceChildren(...[[r.task_count,'matched tasks'],[r.cluster_count+' / '+r.active_cluster_count,'declared / active clusters'],[r.orbit_size,'full sign assignments'],[r.global_tail_fraction??'undefined','global maximum tail']].map(([value,label])=>{const d=txt('div','');d.className='metric';d.append(txt('b',String(value)),txt('span',label));return d;}));
 table('columns',r.columns.map(c=>[c.candidate,c.observed_sum,c.mean_difference_ticks??'undefined',`${c.raw_tail_count}/${r.orbit_size} = ${c.raw_tail_fraction??'undefined'}`,`${c.max_tail_count}/${r.orbit_size} = ${c.max_tail_fraction??'undefined'}`]));
 table('histogram',r.maximum_histogram.map(v=>[v.value,v.count,`${v.survival_count}/${r.orbit_size} = ${v.survival_fraction}`]));
 table('tasks',r.task_differences.map(t=>[t.id,t.cluster,t.baseline,join(t.scores),join(t.deltas)]));table('clusters',r.clusters.map(b=>[b.cluster,join(b.task_ids),join(b.sum_deltas)]));
 table('assignments',r.assignments.map(a=>[a.mask,a.signs.map(v=>v===1?'+':'-').join(' '),a.cluster_contributions.map(v=>'['+join(v)+']').join(' '),join(a.totals),join(a.absolute),a.maximum,join(a.raw_tail.map(yn)),join(a.max_tail.map(yn)),yn(a.global_tail)]));$('limits').textContent=r.limits;
 $('status').textContent=r.defined?'Complete orbit computed. Review joint-null assumptions before interpretation.':'No matched evidence: all tails undefined. This is not equivalence.';chart(r);
}
window.FamilyInputs.forEach((c,i)=>{const o=txt('option',c.id);o.value=i;$('fixture').append(o);});
function load(i){$('input').value=JSON.stringify(window.FamilyInputs[i].input,null,2);reset();}
$('fixture').addEventListener('change',()=>load(Number($('fixture').value)));$('input').addEventListener('input',()=>reset());
$('controls').addEventListener('submit',e=>{e.preventDefault();reset('Computing...');try{show(familyReport(parseInput($('input').value)));}catch(e){reset('Invalid input: '+e.message);}});
function download(value,name){const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)+'\n'],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),2000);}
$('export-input').addEventListener('click',()=>{if(window.currentFamily)download(window.currentFamily.input,'evalforge-family-input.json');});$('export-report').addEventListener('click',()=>{if(window.currentFamily)download(window.currentFamily,'evalforge-family-report.json');});
let generation=0;$('upload').addEventListener('change',async()=>{const g=++generation,f=$('upload').files[0];reset('Loading...');if(!f){reset();return;}try{if(f.size>131072)throw Error('Input exceeds 128 KiB');const s=await f.text();if(g!==generation)return;parseInput(s);$('input').value=s;reset('Input loaded. Enumerate to validate schema and compute.');}catch(e){if(g===generation)reset('Invalid upload: '+e.message);}});
$('input').addEventListener('input',()=>generation++);$('fixture').addEventListener('change',()=>generation++);window.addEventListener('resize',()=>{if(window.currentFamily)chart(window.currentFamily);});
load(0);$('controls').requestSubmit();
