/* All supplied text is data. No fetch, model calls, telemetry or browser storage. */
(function () {
'use strict';
const own=(o,k)=>Object.prototype.hasOwnProperty.call(o,k);
const obj=x=>x!==null&&typeof x==='object'&&!Array.isArray(x);
const fail=s=>{throw new Error(s);};
function text(x,where){
  if(typeof x!=='string'||!(/[^\s\u0085\u001c-\u001f]/u.test(x))||Array.from(x).length>12000)fail(where+' must be a nonempty string of at most 12000 characters');
  for(let i=0;i<x.length;i++){
    const n=x.charCodeAt(i);
    if(n<32&&![9,10,13].includes(n))fail(where+' contains a control character');
    if(n>=0xD800&&n<=0xDBFF){const m=x.charCodeAt(++i);if(!(m>=0xDC00&&m<=0xDFFF))fail(where+' contains invalid Unicode');}
    else if(n>=0xDC00&&n<=0xDFFF)fail(where+' contains invalid Unicode');
  }
}
function fields(x,required,optional,where){
  if(!obj(x))fail(where+' must be an object');
  if(required.some(k=>!own(x,k))||Object.keys(x).some(k=>!required.includes(k)&&!optional.includes(k)))fail(where+' has missing or unexpected fields');
}
function bool(x,where){if(x!==null&&typeof x!=='boolean')fail(where+' must be true, false, or null');}
function validate(c){
  if(!obj(c)||c.schema_version!==1)fail('Expected a case object with schema_version 1');
  fields(c,['schema_version','id','title','provenance','initial','later','correction'],['comparison','guard'],'case');
  ['id','title'].forEach(k=>text(c[k],k));
  if(!['synthetic','user_supplied'].includes(c.provenance))fail('provenance must be synthetic or user_supplied');
  ['initial','later'].forEach(k=>{
    const a=c[k];fields(a,['decision_id','action','context','outcome'],[],k);
    ['decision_id','action'].forEach(v=>text(a[v],k+'.'+v));
    if(!obj(a.context)||Object.keys(a.context).length<1||Object.keys(a.context).length>30)fail(k+'.context must contain 1 to 30 named string fields');
    Object.keys(a.context).forEach(v=>{text(v,k+'.context key');text(a.context[v],k+'.context.'+v);});
    fields(a.outcome,['status','evidence'],[],k+'.outcome');
    if(!['failure','success','unknown'].includes(a.outcome.status))fail(k+'.outcome.status must be failure, success, or unknown');
    text(a.outcome.evidence,k+'.outcome.evidence');
  });
  if(c.initial.decision_id===c.later.decision_id)fail('The initial and later decisions must have distinct IDs');
  fields(c.correction,['after_decision_id','content','intended_action','visible_to_later'],[],'correction');
  if(c.correction.after_decision_id!==c.initial.decision_id)fail('Correction must refer to the initial decision ID');
  ['content','intended_action'].forEach(k=>text(c.correction[k],'correction.'+k));bool(c.correction.visible_to_later,'correction.visible_to_later');
  if(c.comparison!==undefined&&c.comparison!==null){fields(c.comparison,['comparable','basis'],[],'comparison');bool(c.comparison.comparable,'comparison.comparable');text(c.comparison.basis,'comparison.basis');}
  if(c.guard!==undefined&&c.guard!==null){
    fields(c.guard,['allowed_actions','basis'],[],'guard');
    const a=c.guard.allowed_actions;
    if(!Array.isArray(a)||a.length<1||a.length>20)fail('guard.allowed_actions must have 1 to 20 explicit actions');
    a.forEach(x=>text(x,'guard.allowed_actions entry'));
    if(new Set(a).size!==a.length)fail('guard.allowed_actions contains duplicate entries');text(c.guard.basis,'guard.basis');
  }
  return c;
}
function parseCase(raw){
  if(new TextEncoder().encode(raw).length>100000)fail('Input exceeds the 100 KB local case limit');
  // Small bounded JSON parser preserves duplicate-key and schema-version checks.
  let i=0;const ws=()=>{while(/[ \r\n\t]/.test(raw[i]||'!'))i++;};
  function string(){const start=i++;while(i<raw.length){if(raw[i]==='\\'){i+=2;continue;}if(raw[i++]==='"')return JSON.parse(raw.slice(start,i));}fail('Unterminated JSON string');}
  function value(depth,path){
    if(depth>64)fail('JSON nesting exceeds 64 levels');ws();const ch=raw[i];
    if(ch==='"')return string();
    if(ch==='{'){
      i++;ws();const result=Object.create(null);if(raw[i]==='}'){i++;return result;}
      while(true){ws();if(raw[i]!=='"')fail('Expected a JSON field name');const key=string();if(own(result,key))fail('Duplicate JSON field: '+key);ws();if(raw[i++]!==':')fail('Expected a colon');result[key]=value(depth+1,path?path+'.'+key:key);ws();if(raw[i]==='}'){i++;return result;}if(raw[i++]!==',')fail('Expected a comma');}
    }
    if(ch==='['){i++;ws();const result=[];if(raw[i]===']'){i++;return result;}while(true){result.push(value(depth+1,path+'[]'));ws();if(raw[i]===']'){i++;return result;}if(raw[i++]!==',')fail('Expected a comma');}}
    for(const [s,v] of [['true',true],['false',false],['null',null]])if(raw.slice(i,i+s.length)===s){i+=s.length;return v;}
    const m=raw.slice(i).match(/^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/);
    if(m){i+=m[0].length;if(path==='schema_version'&&m[0]!=='1')fail('schema_version must be integer literal 1');const n=Number(m[0]);if(!Number.isFinite(n))fail('Invalid JSON number');return n;}
    fail('Invalid JSON value');
  }
  const c=value(0,'');ws();if(i!==raw.length)fail('Unexpected content after JSON value');return validate(c);
}
function codepointCompare(x,y){
  const a=Array.from(x,c=>c.codePointAt(0)),b=Array.from(y,c=>c.codePointAt(0));
  for(let i=0;i<Math.min(a.length,b.length);i++)if(a[i]!==b[i])return a[i]-b[i];
  return a.length-b.length;
}
function analyze(c,rules){
  validate(c);const a=c.initial,b=c.later,k=c.correction;
  const differences=Array.from(new Set([...Object.keys(a.context),...Object.keys(b.context)])).filter(x=>a.context[x]!==b.context[x]).sort(codepointCompare);
  const same=a.action===b.action,firstFailure=a.outcome.status==='failure',laterFailure=b.outcome.status==='failure';
  const comparable=c.comparison?.comparable??null,visible=k.visible_to_later;
  const facts={context_changed:!!differences.length,not_comparable:comparable===false,missing_outcome:a.outcome.status==='unknown'||b.outcome.status==='unknown',initial_not_failure:!firstFailure,different_action:!same,later_not_failure:!laterFailure,comparability_unknown:comparable!==true,same_intended_action:k.intended_action===a.action,correction_unavailable:visible===false,correction_available:visible===true,always:true};
  const rule=rules.find(r=>facts[r.when]);
  const guard={available:c.guard!==undefined&&c.guard!==null};
  if(guard.available)Object.assign(guard,{later_action_allowed:c.guard.allowed_actions.includes(b.action),correction_action_allowed:c.guard.allowed_actions.includes(k.intended_action),allowed_actions:c.guard.allowed_actions,basis:c.guard.basis,limit:'This checks a declared allowlist. It does not execute an agent, choose a repair, or prove task success.'});
  else guard.limit='No allowlist was supplied. No rule result is inferred.';
  return {id:c.id,title:c.title,provenance:c.provenance,diagnosis:rule.code,conclusion:rule.conclusion,next_check:rule.next_check,scope_differences:differences,same_action:same,declared_comparable_repeat_failure:!differences.length&&comparable===true&&firstFailure&&laterFailure&&same,reported_failure_pattern:firstFailure&&laterFailure&&same,comparison_declared:comparable,evidence_limit:'All fields are supplied declarations. This tool cannot verify their truth, causal explanation, action equivalence or outcome quality.',recorded_correction:{intended_action:k.intended_action,visible_in_recorded_later_attempt:visible,limit:'The intended action is read from the authored correction. No model was tested for following it, and no counterfactual outcome was measured.'},declared_allowlist_check:guard,claim_boundary:'This inspects a supplied record. It does not run an agent, test Hebbrix, establish causality, or compare model or product performance.',case:c};
}
if(typeof module!=='undefined')module.exports={parseCase,validate,analyze};
if(typeof document==='undefined')return;
const editor=document.getElementById('input'),error=document.getElementById('error'),result=document.getElementById('result');
let report=null,generation=0;
function clearResult(){report=null;result.replaceChildren();error.textContent='';document.getElementById('download').disabled=true;}
function clear(){generation++;editor.value='';document.getElementById('file').value='';document.getElementById('examples').selectedIndex=0;clearResult();}
const declaration=x=>x===null?'unknown':(x?'yes':'no');
function show(){clearResult();try{
  report=analyze(parseCase(editor.value),window.REPLAY_DATA.rules);
  function append(tag,s,parent=result){const n=document.createElement(tag);n.textContent=s;parent.append(n);return n;}
  append('span',report.provenance+' / supplied record').className='tag';
  append('h2',report.conclusion);
  const table=append('table',''),head=append('thead','',table),hr=append('tr','',head);
  ['Supplied field','Initial attempt','Later attempt'].forEach(x=>append('th',x,hr));
  const body=append('tbody','',table);
  const c=report.case;
  [['Action',c.initial.action,c.later.action],['Outcome label',c.initial.outcome.status,c.later.outcome.status],['Result description',c.initial.outcome.evidence,c.later.outcome.evidence]].forEach(row=>{const tr=append('tr','',body);row.forEach((x,i)=>append(i===0?'th':'td',x,tr));});
  append('p','Correction text: '+c.correction.content);
  append('p','Intended action: '+c.correction.intended_action);
  if(c.comparison)append('p','Comparison basis: '+c.comparison.basis);
  append('p','Next check: '+report.next_check);
  append('p','Exact action strings match: '+report.same_action+'. Reported same-action failure pattern: '+report.reported_failure_pattern+'.');
  append('p','Changed context fields: '+(report.scope_differences.join(', ')||'none')+'. Declared comparable: '+declaration(report.comparison_declared)+'.');
  append('p','Declared correction visibility: '+declaration(report.recorded_correction.visible_in_recorded_later_attempt)+'.');
  if(report.declared_allowlist_check.available){append('p','Declared allowlist accepts the later action: '+report.declared_allowlist_check.later_action_allowed+'. Accepts the correction action: '+report.declared_allowlist_check.correction_action_allowed+'.');append('p',report.declared_allowlist_check.basis);}
  append('p',report.evidence_limit);append('p',report.claim_boundary);
  const detail=append('details','');append('summary','Inspect the complete report',detail);append('pre',JSON.stringify(report,null,2),detail);
  document.getElementById('download').disabled=false;
}catch(e){report=null;error.textContent='Cannot inspect record: '+e.message;}}
document.getElementById('analyze').addEventListener('click',show);
editor.addEventListener('input',()=>{generation++;clearResult();});
document.getElementById('clear').addEventListener('click',clear);
const examples=document.getElementById('examples');
window.REPLAY_DATA.cases.forEach((c,i)=>{const o=document.createElement('option');o.value=String(i);o.textContent=c.title;examples.append(o);});
examples.addEventListener('change',()=>{generation++;clearResult();if(examples.value==='')return;editor.value=JSON.stringify(window.REPLAY_DATA.cases[Number(examples.value)],null,2);show();});
document.getElementById('file').addEventListener('change',async event=>{const ticket=++generation;clearResult();const file=event.target.files[0];if(!file)return;if(file.size>100000){error.textContent='File exceeds the 100 KB local case limit';return;}try{const bytes=await file.arrayBuffer();const raw=new TextDecoder('utf-8',{fatal:true}).decode(bytes);if(ticket!==generation)return;editor.value=raw;show();}catch(e){if(ticket===generation)error.textContent='Cannot read UTF-8 file: '+e.message;}});
document.getElementById('download').addEventListener('click',()=>{if(!report)return;const blob=new Blob([JSON.stringify(report,null,2)+'\n'],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='record-inspection.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
})();
