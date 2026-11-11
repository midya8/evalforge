// Independent browser implementation: Cartesian sign vectors, direct original-task sums.
export const LIMITS = 'Supplied common-task integer scores and cluster labels; shared cluster signs across every candidate. Exact inclusive absolute-sum/max tails, not studentized tests, automatic gates, proven joint symmetry or universal strong-FWER/model-superiority claims.';
function fields(v, keys) { if (!v || typeof v !== 'object' || Array.isArray(v) || Object.keys(v).sort().join('|')!==[...keys].sort().join('|')) throw Error('Exact object fields required: '+keys.join(', ')); }
function label(s) { if(typeof s!=='string'||! /^[A-Za-z][A-Za-z0-9_-]{0,23}$/.test(s))throw Error('ASCII labels: letter then letters/digits/_/-, at most 24 characters'); }
function ticks(x){if(!Number.isSafeInteger(x)||Object.is(x,-0)||x<0||x>1000)throw Error('Integer score ticks 0..1000 required');}
export function normalize(x){
 fields(x,['candidates','tasks']);const r=structuredClone(x), c=r.candidates, tasks=r.tasks;
 if(!Array.isArray(c)||c.length<1||c.length>4)throw Error('One to four candidates');c.forEach(label);
 if(new Set(c).size!==c.length)throw Error('Distinct candidate labels');
 if(!Array.isArray(tasks)||tasks.length>12)throw Error('At most twelve tasks');
 const ids=new Set(), blocks=new Set();for(const t of tasks){fields(t,['id','cluster','baseline','scores']);label(t.id);label(t.cluster);if(ids.has(t.id))throw Error('Duplicate task id');ids.add(t.id);blocks.add(t.cluster);ticks(t.baseline);if(!Array.isArray(t.scores)||t.scores.length!==c.length)throw Error('One score per candidate');t.scores.forEach(ticks);}
 if(blocks.size>8)throw Error('At most eight clusters');return r;
}
export function parseInput(text){
 if(new TextEncoder().encode(text).length>131072)throw Error('Input exceeds 128 KiB');
 // Token walk prevents JSON.parse from silently losing duplicate keys or number spelling.
 let i=0;const ws=()=>{while(/\s/.test(text[i]||'')&&i<text.length)i++;};
 const string=()=>{const start=i++;while(i<text.length){if(text[i]==='\\'){i+=2;continue;}if(text[i++]==='"')return JSON.parse(text.slice(start,i));}throw Error('Unterminated string');};
 function value(depth){if(depth>8)throw Error('Nesting exceeds 8');ws();let ch=text[i];
  if(ch==='{'){i++;const keys=new Set();ws();if(text[i]==='}'){i++;return;}while(true){ws();if(text[i]!=='"')throw Error('Object key required');const k=string();if(keys.has(k))throw Error('Duplicate JSON key');keys.add(k);ws();if(text[i++]!==':')throw Error('Colon required');value(depth+1);ws();ch=text[i++];if(ch==='}')return;if(ch!==',')throw Error('Comma required');}}
  if(ch==='['){i++;ws();if(text[i]===']'){i++;return;}while(true){value(depth+1);ws();ch=text[i++];if(ch===']')return;if(ch!==',')throw Error('Comma required');}}
  if(ch==='"'){string();return;}
  const rest=text.slice(i);const literal=/^(true|false|null)/.exec(rest);if(literal){i+=literal[0].length;return;}
  const num=/^[^\s,\]}]+/.exec(rest);if(!num||!/^(0|[1-9][0-9]*)$/.test(num[0]))throw Error('Nonnegative integer numeric tokens only');i+=num[0].length;
 }
 value(0);ws();if(i!==text.length)throw Error('Trailing input');return JSON.parse(text);
}
function frac(a,b){if(!b)return null;let x=a,y=b;while(y){[x,y]=[y,x%y];}return b/x===1?String(a/x):`${a/x}/${b/x}`;}
export function familyReport(input){
 const r=normalize(input), tasks=r.tasks, cols=r.candidates, names=[...new Set(tasks.map(t=>t.cluster))].sort();
 const differences=tasks.map(t=>({...t,deltas:t.scores.map(s=>s-t.baseline)}));
 const clusters=names.map(cluster=>({cluster,task_ids:tasks.filter(t=>t.cluster===cluster).map(t=>t.id),sum_deltas:cols.map((_,j)=>differences.filter(t=>t.cluster===cluster).reduce((a,t)=>a+t.deltas[j],0))}));
 const observed=cols.map((_,j)=>tasks.reduce((a,t)=>a+t.scores[j]-t.baseline,0));const abs=observed.map(Math.abs), maximum=Math.max(...abs);
 let signVectors=[[]];for(const _ of names)signVectors=signVectors.flatMap(s=>[[...s,1],[...s,-1]]);
 const assignments=tasks.length?signVectors.map(signs=>{
  const sign=Object.fromEntries(names.map((b,j)=>[b,signs[j]]));const totals=cols.map((_,j)=>tasks.reduce((v,t)=>v+sign[t.cluster]*(t.scores[j]-t.baseline),0));
  const absolute=totals.map(Math.abs), mx=Math.max(...absolute);return {mask:signs.reduce((v,s,i)=>v+(s<0?2**i:0),0),signs,cluster_contributions:clusters.map((b,i)=>b.sum_deltas.map(v=>v*signs[i]||0)),totals,absolute,maximum:mx,raw_tail:absolute.map((v,j)=>v>=abs[j]),max_tail:abs.map(v=>mx>=v),global_tail:mx>=maximum};
 }).sort((a,b)=>a.mask-b.mask):[];
 const den=assignments.length;function histogram(values){const counts=new Map();values.forEach(v=>counts.set(v,(counts.get(v)||0)+1));return [...counts].sort((a,b)=>a[0]-b[0]).map(([value,count])=>({value,count}));}
 const columns=cols.map((candidate,j)=>{const raw=assignments.filter(a=>a.raw_tail[j]).length, adj=assignments.filter(a=>a.max_tail[j]).length;let mean=null;if(tasks.length){const n=observed[j];mean=(n<0?'-':'')+frac(Math.abs(n),tasks.length);}
 return {candidate,observed_sum:observed[j],observed_absolute:abs[j],mean_difference_ticks:mean,raw_tail_count:raw,max_tail_count:adj,raw_tail_fraction:frac(raw,den),max_tail_fraction:frac(adj,den),absolute_histogram:histogram(assignments.map(a=>a.absolute[j]))};});
 const count=assignments.filter(a=>a.global_tail).length;
 return {schema:1,input:r,defined:!!tasks.length,task_count:tasks.length,cluster_count:names.length,orbit_size:den,active_cluster_count:clusters.filter(b=>b.sum_deltas.some(Boolean)).length,task_differences:differences,clusters,columns,observed_maximum:maximum,global_tail_count:count,global_tail_fraction:frac(count,den),assignments,maximum_histogram:histogram(assignments.map(a=>a.maximum)).map(h=>{const survival_count=assignments.filter(a=>a.maximum>=h.value).length;return {...h,survival_count,survival_fraction:frac(survival_count,den)};}),limits:LIMITS};
}
