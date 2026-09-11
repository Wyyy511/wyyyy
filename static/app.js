const $ = s => document.querySelector(s);
const state = {
  sessionId: localStorage.getItem('waterpulse_v5_session') || '',
  file: null,
  busy: false
};
const els = {
  welcome: $('#welcome'), messages: $('#messages'), input: $('#messageInput'), file: $('#fileInput'),
  fileChip: $('#fileChip'), fileName: $('#fileName'), send: $('#sendBtn'), toast: $('#toast')
};

function esc(s=''){return String(s).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]))}
function toast(t){els.toast.textContent=t;els.toast.classList.add('show');setTimeout(()=>els.toast.classList.remove('show'),2200)}
function fmt(v,n=4){const x=Number(v);return Number.isFinite(x)?x.toFixed(n):'—'}
function pct(v){const x=Number(v);return Number.isFinite(x)?(x*100).toFixed(1)+'%':'—'}
function md(text=''){
  let s=esc(text);
  s=s.replace(/^###\s+(.+)$/gm,'<h3>$1</h3>');
  s=s.replace(/\*\*(.*?)\*\*/g,'<strong>$1</strong>');
  s=s.replace(/^[-•]\s+(.+)$/gm,'<li>$1</li>');
  s=s.replace(/(<li>.*<\/li>\n?)+/g,m=>'<ul>'+m+'</ul>');
  s=s.replace(/\n{2,}/g,'</p><p>').replace(/\n/g,'<br>');
  return '<p>'+s+'</p>';
}
function showMessages(){els.welcome.style.display='none';document.body.classList.add('chatting')}
function scrollBottom(){setTimeout(()=>window.scrollTo({top:document.body.scrollHeight,behavior:'smooth'}),40)}
function resize(){els.input.style.height='auto';els.input.style.height=Math.min(150,els.input.scrollHeight)+'px'}
function setFile(f){state.file=f||null;if(f){els.fileName.textContent=f.name;els.fileChip.hidden=false}else{els.fileChip.hidden=true;els.fileName.textContent='';els.file.value=''}}

function addUser(text,file){
  showMessages();
  const el=document.createElement('div'); el.className='msg user';
  el.innerHTML=`<div class="content"><div class="bubble">${text?esc(text):'请分析这个文件'}${file?`<div style="margin-top:8px;font-size:10px;opacity:.78">📎 ${esc(file.name)}</div>`:''}</div></div><div class="avatar">你</div>`;
  els.messages.appendChild(el); scrollBottom();
}
function traceHtml(trace=[]){
  if(!trace.length)return'';
  return `<details class="trace-box"><summary>查看分析过程 · ${trace.length} 项</summary><div class="trace-list">${trace.map(x=>`<div class="trace-item ${esc(x.status||'done')}"><i class="trace-dot"></i><div><div class="trace-title">${esc(x.step)}</div>${x.detail?`<div class="trace-detail">${esc(x.detail)}</div>`:''}</div></div>`).join('')}</div></details>`;
}
function actionHtml(actions=[]){
  if(!actions.length)return'';
  return `<div class="actions">${actions.map((a,i)=>`<button class="action-btn ${i===0?'primary':''}" data-action="${encodeURIComponent(JSON.stringify(a))}">${esc(a.label)}</button>`).join('')}</div>`;
}
function baselineCard(b){
  const rows=b?.data?.summary; if(!Array.isArray(rows)||!rows.length)return'';
  const r=rows[0];
  return `<div class="result-card"><div class="result-title">Baseline 计算摘要</div><div class="metrics">
    <div class="metric"><span>PRWI</span><b>${fmt(r.PRWI)}</b></div>
    <div class="metric"><span>采购覆盖率</span><b>${pct(r.Coverage)}</b></div>
    <div class="metric"><span>可评分覆盖率</span><b>${pct(r.scored_coverage ?? r.Coverage)}</b></div>
    <div class="metric"><span>Unknown</span><b>${pct(r.unknown_share_U)}</b></div>
  </div></div>`;
}
function scenarioCard(s){
  const d=s?.data; if(!d||typeof d!=='object')return'';
  const t=d.scenario_type||'Scenario';
  let metrics=[];
  if(t==='NodeFailure') metrics=[['Gross Loss',fmt(d.gross_loss)],['未满足需求',fmt(d.unmet_demand)],['Conditional PRWI',fmt(d.conditional_PRWI)],['采购 HHI',fmt(d.procurement_hhi)]];
  else if(t==='AqueductFuture') metrics=[['Baseline',fmt(d.PRWI_baseline)],['Future',fmt(d.PRWI_future)],['ΔPRWI',fmt(d.PRWI_delta)],['路径',d.path||'—']];
  else metrics=[['Baseline',fmt(d.PRWI_baseline)],['Scenario',fmt(d.PRWI_scenario)],['ΔPRWI',fmt(d.PRWI_delta)],['类型',t]];
  return `<div class="result-card"><div class="result-title">${esc(t)} 结果摘要</div><div class="metrics">${metrics.map(([k,v])=>`<div class="metric"><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join('')}</div></div>`;
}
function addAI(data){
  showMessages();
  const el=document.createElement('div');el.className='msg ai';
  const provider=data.ai?.provider==='DeepSeek'?`DeepSeek · ${esc(data.ai.model||'')}`:'本地安全模板';
  const result=(data.result_summary?.baseline?baselineCard(data.result_summary.baseline):'')+(data.result_summary?.scenario?scenarioCard(data.result_summary.scenario):'');
  el.innerHTML=`<div class="avatar">AI</div><div class="content"><div class="bubble">${md(data.message||'')}${result}${actionHtml(data.actions||[])}${traceHtml(data.trace||[])}</div><div class="meta">WaterPulse AI · ${provider}</div></div>`;
  els.messages.appendChild(el); bindActions(el); scrollBottom();
}
function addTyping(){showMessages();const el=document.createElement('div');el.id='typingMsg';el.className='msg ai';el.innerHTML='<div class="avatar">AI</div><div class="content"><div class="bubble"><div class="typing"><i></i><i></i><i></i></div></div></div>';els.messages.appendChild(el);scrollBottom()}
function removeTyping(){$('#typingMsg')?.remove()}

async function callAgent({message='',action='',scenario_type='',material='',year='',path='',failure_fraction='',inventory='',file=null}={}){
  if(state.busy)return; state.busy=true; els.send.disabled=true; addTyping();
  try{
    const fd=new FormData();
    fd.append('session_id',state.sessionId);fd.append('message',message);fd.append('action',action);fd.append('scenario_type',scenario_type);fd.append('material',material);
    fd.append('year',year);fd.append('path',path);fd.append('failure_fraction',failure_fraction);fd.append('inventory',inventory);if(file)fd.append('file',file);
    const r=await fetch('/api/agent/message',{method:'POST',body:fd});
    const data=await r.json(); if(!r.ok)throw new Error(data.detail||'请求失败');
    if(data.session_id){state.sessionId=data.session_id;localStorage.setItem('waterpulse_v5_session',state.sessionId)}
    removeTyping();addAI(data);return data;
  }catch(e){removeTyping();addAI({message:'这次请求没有完成。请检查网络或后端服务后重试。',trace:[{step:'请求失败',status:'error',detail:String(e)}]})}
  finally{state.busy=false;els.send.disabled=false}
}
async function send(){
  const text=els.input.value.trim();const f=state.file;if(!text&&!f)return;
  addUser(text,f);els.input.value='';resize();setFile(null);await callAgent({message:text,file:f});
}
function bindActions(root=document){
  root.querySelectorAll('.action-btn').forEach(btn=>btn.onclick=async()=>{
    let a={};try{a=JSON.parse(decodeURIComponent(btn.dataset.action))}catch{}
    if(a.action==='download_template'){location.href='/api/template';return}
    if(a.action==='focus_upload'){els.file.click();return}
    if(a.action==='download_report'){if(!state.sessionId){toast('当前没有分析会话');return}location.href='/api/agent/report/'+encodeURIComponent(state.sessionId);return}
    addUser(a.label);
    await callAgent({action:a.action||'',scenario_type:a.scenario_type||'',material:a.material||'',year:a.year||'',path:a.path||'',failure_fraction:a.failure_fraction??'',inventory:a.inventory??'',message:a.label});
  })
}
function reset(){
  state.sessionId='';localStorage.removeItem('waterpulse_v5_session');state.file=null;els.messages.innerHTML='';els.welcome.style.display='block';document.body.classList.remove('chatting');setFile(null);els.input.value='';resize();
}

$('#attachBtn').onclick=()=>els.file.click();els.file.onchange=()=>setFile(els.file.files?.[0]);$('#removeFile').onclick=()=>setFile(null);els.send.onclick=send;
els.input.addEventListener('input',resize);els.input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}});$('#newChatBtn').onclick=reset;
document.querySelectorAll('.quick').forEach(b=>b.onclick=()=>{els.input.value=b.dataset.prompt||'';resize();els.input.focus()});

async function init(){
  try{
    const r=await fetch('/api/agent/status');const d=await r.json();const badge=$('#aiStatus');badge.classList.add(d.deepseek_configured?'online':'offline');
    badge.innerHTML=`<i></i><span>${d.deepseek_configured?'DeepSeek 已连接':'DeepSeek 待配置'}</span>`;
  }catch{$('#aiStatus').textContent='后端未连接'}
  if(state.sessionId){showMessages();addAI({message:'欢迎回来。你可以继续提问、上传新文件，或者点右上角“新分析”开始新的任务。',actions:[]})}
}

// Optional browser speech-to-text. It only fills the composer; no audio is uploaded.
(function setupSpeech(){
  const btn=document.querySelector('#micBtn');
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!btn)return;
  if(!SR){btn.style.display='none';return;}
  const rec=new SR();rec.lang='zh-CN';rec.interimResults=true;rec.continuous=false;
  let base='';
  btn.onclick=()=>{try{base=els.input.value.trim();btn.classList.add('listening');toast('正在听…');rec.start()}catch{}};
  rec.onresult=e=>{let text='';for(let i=e.resultIndex;i<e.results.length;i++)text+=e.results[i][0].transcript;els.input.value=(base?base+' ':'')+text;resize()};
  rec.onend=()=>btn.classList.remove('listening');
  rec.onerror=()=>{btn.classList.remove('listening');toast('语音输入暂不可用')};
})();

init();
