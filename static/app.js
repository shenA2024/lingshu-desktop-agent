"use strict";
const $ = (id) => document.getElementById(id);
const icons = {
  trash:'M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7',
  plus:'M12 5v14M5 12h14',grid:'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z',
  brain:'M9 18a4 4 0 0 1-4-4 4 4 0 0 1-1-7 4 4 0 0 1 7-3v15a3 3 0 0 1-5 2m9-3a4 4 0 0 0 4-4 4 4 0 0 0 1-7 4 4 0 0 0-7-3v15a3 3 0 0 0 5 2M7 10h4m2 4h4',
  plug:'M7 3v5m10-5v5M5 8h14v4a7 7 0 0 1-14 0zM12 19v3',folder:'M3 6h6l2 2h10v12H3z',lock:'M5 10h14v11H5zM8 10V6a4 4 0 0 1 8 0v4',panel:'M3 4h18v16H3zM9 4v16',
  download:'M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5',orbit:'M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6M3 12a9 9 0 1 0 9-9M3 5v7h7',
  bolt:'M13 2 4 14h7l-1 8 10-13h-7z',route:'M5 5h8a4 4 0 0 1 0 8H9a4 4 0 0 0 0 8h9M5 2a3 3 0 1 0 0 6 3 3 0 0 0 0-6M18 18l3 3-3 3',radio:'M8 8a6 6 0 0 0 0 8m8-8a6 6 0 0 1 0 8M5 5a10 10 0 0 0 0 14M19 5a10 10 0 0 1 0 14M12 10a2 2 0 1 0 0 4 2 2 0 0 0 0-4',
  spark:'m12 3 2.3 6.7L21 12l-6.7 2.3L12 21l-2.3-6.7L3 12l6.7-2.3z',play:'m8 4 12 8-12 8z',stop:'M6 6h12v12H6z',
  activity:'M2 12h5l3-9 4 18 3-9h5',sliders:'M4 3v5m0 4v9M12 3v11m0 4v3M20 3v2m0 4v12M1 8h6m2 6h6m2-9h6',info:'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20M12 10v6m0-9v.5',
  message:'M3 3h18v14H8l-5 4zM7 7h10M7 11h7',arrow:'M4 12h16m-6-6 6 6-6 6',layers:'m12 3 10 5-10 5L2 8zm-10 9 10 5 10-5M2 16l10 5 10-5',
  search:'M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14m5 12 6 6',edit:'m15 3 6 6-12 12H3v-6zm-3 3 6 6',refresh:'M20 8a9 9 0 0 0-15-3L3 8m0-6v6h6M4 16a9 9 0 0 0 15 3l2-3m0 6v-6h-6',copy:'M8 8h13v13H8zM16 8V3H3v13h5',external:'M14 3h7v7m0-7L10 14M10 3H3v18h18v-7',check:'m5 12 4 4L19 6',warning:'m12 3 10 18H2zm0 6v5m0 3v.5',clock:'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20M12 6v6l4 2',chevron:'m9 5 7 7-7 7',settings:'M9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1zM12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8'
};
function icon(name){return `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${icons[name]||icons.activity}"/></svg>`;}
function hydrate(root=document){root.querySelectorAll('[data-icon]').forEach(el=>{el.innerHTML=icon(el.dataset.icon);});}
function esc(value){return String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
const colors=['var(--entity-1)','var(--entity-2)','var(--entity-3)','var(--entity-4)'];
const preferences=window.LingshuPreferences;
const statusNames={running:'运行中',saving:'保存记忆中',cancelling:'正在停止',completed:'已完成',cancelled:'已停止',failed:'运行失败',interrupted:'已中断'};
const behaviorNames={wander:'游走',seek:'趋近',avoid:'避让',flee:'远离',follow:'沿方向运动',unknown:'待推断'};
const state={page:'workspace',tab:'scene',view:'space',scenario:'pursuit',scenarios:[],run:null,runs:[],preview:null,frameIndex:null,entity:null,integrations:null,connected:false,loading:false};
let toastTimer, pollTimer, polling=false, generation=0;

async function api(path,options={}){
  const response=await fetch('/api'+path,{...options,headers:{'Content-Type':'application/json',...(options.headers||{})}});
  if(!response.ok){let message;try{const body=await response.json();message=typeof body.detail==='string'?body.detail:JSON.stringify(body.detail);}catch{message=`请求失败 (${response.status})`;}throw new Error(message);}
  return response.json();
}
function post(path,body={}){return api(path,{method:'POST',body:JSON.stringify(body)});}
function toast(message,error=false){clearTimeout(toastTimer);$('toast').textContent=message;$('toast').className='toast'+(error?' error':'');toastTimer=setTimeout(()=>$('toast').classList.add('hidden'),4500);}
function dateText(iso){return new Date(iso).toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false});}
function timeText(iso){return new Date(iso).toLocaleTimeString('zh-CN',{hour12:false});}
function isActive(run=state.run){return run&&['running','cancelling','saving'].includes(run.status);}
function selectedFrame(){if(!state.run?.frames.length)return state.preview;const i=state.frameIndex===null?state.run.frames.length-1:Math.min(state.frameIndex,state.run.frames.length-1);return state.run.frames[i];}

function switchPage(page){if(!['agent','workspace'].includes(page)&&!preferences.get(page))page='agent';state.page=page;for(const name of ['agent','workspace','results','events','memory','connections'])$(name+'-page').classList.toggle('hidden',name!==page);document.querySelectorAll('[data-page]').forEach(el=>el.classList.toggle('active',el.dataset.page===page));$('breadcrumb-page').textContent={agent:'对话',workspace:'世界场景',results:'预测分析',events:'执行记录',memory:'记忆库',connections:'连接管理'}[page];if(['events','memory','connections'].includes(page))$('tools-group').open=true;if(page==='events'){state.tab='events';renderEvents();}if(page==='results')renderStatistics();if(page==='memory')searchMemory();if(page==='connections')loadConnections();document.dispatchEvent(new CustomEvent('lingshu:page',{detail:page}));}
function setTab(tab){state.tab=tab;switchPage(tab==='events'?'events':'workspace');renderEvents();}

function renderScenarios(){
  const descriptions={pursuit:'追逐随机目标，验证下一步位置',perturbation:'移动目标，观察预测如何失效',avoidance:'远离障碍，推断运动方向'};
  $('scenario-options').innerHTML=state.scenarios.map(s=>`<button class="scenario ${s.id===state.scenario?'selected':''}" data-scenario="${esc(s.id)}" title="${esc(s.description)}">${icon(s.icon)}<span>${esc(s.name)}</span><small class="scenario-description">${esc(descriptions[s.id])}</small><span class="scenario-check">✓</span></button>`).join('');
  $('scenario-options').querySelectorAll('button').forEach(button=>button.onclick=async()=>{if(isActive()){toast('当前任务正在运行；请等待完成或停止运行。');return;}state.scenario=button.dataset.scenario;state.run=null;state.frameIndex=null;state.entity=null;renderScenarios();try{state.preview=await api('/preview/'+state.scenario);renderRun();renderSessions();}catch(e){toast(e.message,true);}});
}
const pageItems=[
  {id:'agent',name:'对话',icon:'message'},
  {id:'workspace',name:'世界场景',icon:'grid'}, {id:'results',name:'预测分析',icon:'sliders'},
  {id:'events',name:'执行记录',icon:'activity'}, {id:'memory',name:'记忆库',icon:'brain'},
  {id:'connections',name:'连接管理',icon:'plug'}
];
function matchesRun(run,query){return [run.title,run.note,run.id,statusNames[run.status]].join(' ').toLocaleLowerCase().includes(query);}
function sessionMarkup(run){return `<button class="session ${state.run?.id===run.id?'active':''}" data-id="${esc(run.id)}"><i class="session-dot ${esc(run.status)}"></i><span><strong>${esc(run.title)}</strong><small>${dateText(run.created_at)} · ${statusNames[run.status]||esc(run.status)}</small></span></button>`;}
function updateList(id,markup){
  const container=$(id);if(container.dataset.markup===markup)return;
  const focused=container.contains(document.activeElement)?document.activeElement.dataset.id:null;
  const scroll=container.scrollTop;container.innerHTML=markup;container.dataset.markup=markup;container.scrollTop=scroll;
  container.querySelectorAll('[data-id]').forEach(button=>{button.onclick=()=>{document.querySelectorAll('dialog[open]').forEach(d=>d.close());selectRun(button.dataset.id);};if(button.dataset.id===focused)button.focus({preventScroll:true});});
}
function renderSessions(){
  $('history-count').textContent=state.runs.length;
  updateList('sessions',state.runs.slice(0,3).map(sessionMarkup).join('')||'<div class="sidebar-empty">暂无实验</div>');
  const query=$('history-query').value.trim().toLocaleLowerCase(),matches=state.runs.filter(run=>matchesRun(run,query));
  updateList('history-sessions',matches.map(sessionMarkup).join('')||`<div class="list-empty">${query?'没有匹配的实验':'暂无实验'}</div>`);
  if($('search-dialog').open)renderSearch();
}
function renderSearch(){
  const query=$('global-query').value.trim().toLocaleLowerCase(),pages=pageItems.filter(item=>(['agent','workspace'].includes(item.id)||preferences.get(item.id))&&item.name.includes(query)),runs=state.runs.filter(run=>matchesRun(run,query));
  let markup=pages.length?'<div class="search-section">功能</div>'+pages.map(item=>`<button class="search-result" data-destination="${item.id}">${icon(item.icon)}<span>${item.name}</span>${icon('arrow')}</button>`).join(''):'';
  if(!query||'设置'.includes(query))markup+=`<button class="search-result" data-settings>${icon('settings')}<span>设置</span>${icon('arrow')}</button>`;
  if(runs.length)markup+='<div class="search-section">实验</div>'+(query?runs:runs.slice(0,6)).map(sessionMarkup).join('');
  updateList('search-results',markup||'<div class="list-empty">没有匹配结果</div>');
  $('search-results').querySelectorAll('[data-destination]').forEach(button=>button.onclick=()=>{$('search-dialog').close();switchPage(button.dataset.destination);});
  const settings=$('search-results').querySelector('[data-settings]');if(settings)settings.onclick=()=>{$('search-dialog').close();$('open-settings').click();};
}
function setSidebar(collapsed){
  document.body.classList.toggle('sidebar-collapsed',collapsed);
  const button=$('toggle-sidebar'),label=collapsed?'展开侧栏':'收起侧栏';
  button.setAttribute('aria-expanded',String(!collapsed));button.setAttribute('aria-label',label);button.title=label;
  $('setting-sidebar').checked=collapsed;
}
function applyUIPreferences(changed){
  setSidebar(preferences.get('sidebar'));
  if(['init','replay','reset'].includes(changed))$('replay-details').open=preferences.get('replay');
  for(const page of ['results','events','memory','connections'])document.querySelectorAll(`[data-page="${page}"]`).forEach(el=>el.classList.toggle('hidden',!preferences.get(page)));
  $('tools-group').classList.toggle('hidden',!['events','memory','connections'].some(page=>preferences.get(page)));
  $('open-results').classList.toggle('hidden',!preferences.get('results'));
  $('see-connections').classList.toggle('hidden',!preferences.get('connections'));
  document.querySelector('[data-view="graph"]').classList.toggle('hidden',!preferences.get('graph'));
  if(!preferences.get('graph')&&state.view==='graph')state.view='space';
  document.querySelectorAll('[data-view]').forEach(button=>button.classList.toggle('active',button.dataset.view===state.view));
  if(!['agent','workspace'].includes(state.page)&&!preferences.get(state.page))switchPage('agent');
  if(changed==='reset'){$('tools-group').open=false;toast('已恢复默认设置。');}
  if(['init','autoMemory','reset'].includes(changed)&&!isActive())$('save-memory').checked=preferences.get('autoMemory');
  LingshuScene.reset();renderWorld();
  if($('search-dialog').open)renderSearch();
}
function openSearch(){if(document.querySelector('dialog[open]'))return;$('global-query').value='';renderSearch();$('search-dialog').showModal();$('global-query').focus();}
async function selectRun(id){const token=++generation;try{const run=await api('/runs/'+id);if(token!==generation)return;state.run=run;state.scenario=run.scenario;state.entity=null;state.frameIndex=null;$('task-note').value=run.note;switchPage('workspace');setTab('scene');renderScenarios();renderRun();renderSessions();}catch(e){toast(e.message,true);}}
function renderRun(){
  const run=state.run,frame=selectedFrame();
  $('task-title').textContent=run?run.title:'世界场景';
  $('task-state').textContent=run?statusNames[run.status]||run.status:'待运行';$('task-state').className='state-badge '+(run?.status||'');
  $('export-run').classList.toggle('hidden',!run);if(run)$('export-run').href='/api/runs/'+run.id+'/export';
  $('analysis-run-label').textContent=run?`${run.title} · ${run.completed_ticks} 步`:'选择或运行实验后查看结果。';
  $('events-run-label').textContent=run?`${run.title} · ${run.completed_ticks} 步`:'选择实验后查看完整执行记录。';
  $('workspace-summary').textContent=run?`${run.completed_ticks} / ${run.requested_ticks} 步${run.anomaly_count?' · '+run.anomaly_count+' 次异常':''}`:`${Object.keys(frame?.scene.entities??{}).length} 个实体`;
  const active=isActive();$('run-button').classList.toggle('hidden',!!active);$('stop-button').classList.toggle('hidden',!active);$('stop-button').disabled=run?.status==='saving'||run?.status==='cancelling';$('stop-button').innerHTML=icon('stop')+(run?.status==='saving'?'正在保存':run?.status==='cancelling'?'正在停止':'停止运行');
  $('workspace-new-task').classList.toggle('hidden',!!active);
  for(const id of ['task-note','tick-count','save-memory'])$(id).disabled=!!active;
  $('metric-tick').innerHTML=run?`${run.completed_ticks}<small> / ${run.requested_ticks}</small>`:`—<small> / ${$('tick-count').value}</small>`;
  $('metric-rate').textContent=run?.total?`${(run.hit_rate*100).toFixed(0)}%`:'—';$('metric-rate').title=run?.total?`${run.hits} / ${run.total} 个已观测预测落在边界内`:'';
  $('metric-anomalies').textContent=run?run.anomaly_count:'—';$('metric-entities').textContent=frame?.graph.node_count??'—';
  $('metric-anomalies').parentElement.classList.toggle('anomalous',!!run?.anomaly_count);
  $('inspector-mode').textContent=state.frameIndex!==null?`回看第 ${frame?.tick??0} 步`:isActive()?'实时运行':run?'实验汇总':'准备就绪';
  const max=run?.frames.length?run.frames.length-1:0;$('playback').max=max;$('playback').disabled=!max;$('playback').value=state.frameIndex??max;$('live-view').classList.toggle('active',state.frameIndex===null);$('playback-label').textContent=run?`${frame?.tick??0} / ${run.completed_ticks} 步`:'尚未运行';
  $('tick-label').textContent=`第 ${frame?.tick??0} / ${run?.requested_ticks??$('tick-count').value} 步`;
  const banner=$('completion-banner');banner.classList.add('hidden');
  if(run&&!active){const warning=run.events.findLast(e=>e.kind==='warning'&&e.title.includes('写入'));const saved=!!run.memory_id;banner.className='completion-banner'+(run.status==='completed'&&!warning?'':' warning');banner.innerHTML=icon(saved?'check':run.status==='completed'?'check':'warning')+`<span>${state.frameIndex!==null?'实验结束后的状态：':''}${saved?'实验完成，运行结果已写入记忆。':warning?'实验完成；记忆未保存，可在连接页检查原因。':run.status==='completed'?'实验完成，轨迹与执行记录已保存。':run.status==='cancelled'?'运行已停止，已完成的观测与执行记录保留。':run.status==='interrupted'?'服务重启中断了运行，已有记录保留。':'运行失败，请在执行记录中查看原因。'}</span>`;}
  renderPipeline();renderWorld();renderEntities();renderEvents();renderVerification();renderStatistics();
}

function renderPipeline(){
  const run=state.run,frame=selectedFrame(),verification=frame?.verification;
  const plannedSave=run?.events[0]?.data.save_memory??$('save-memory').checked;
  const stages=[
    {name:'观测',icon:'orbit',value:frame?`${frame.graph.node_count} 个实体`:'等待观测',done:!!run?.frames.length},
    {name:'预测',icon:'spark',value:verification?`${verification.total+verification.pending} 项预测`:'下一步位置',done:!!verification},
    {name:'验证',icon:'check',value:verification?.total?`${verification.hits} / ${verification.total} 命中`:'与新观测对比',done:!!verification?.total},
    {name:'记忆',icon:'brain',value:state.frameIndex!==null?'运行结束后另行保存':run?.memory_id?'已写入':run?.status==='saving'?'正在保存':!plannedSave?'不保存':run&&!isActive()?'未写入':'等待运行结果',done:state.frameIndex===null&&!!run?.memory_id,active:state.frameIndex===null&&run?.status==='saving'}
  ];
  $('pipeline').innerHTML=stages.map(s=>`<div class="pipeline-step ${s.done?'complete':''} ${s.active?'active':''}"><span class="pipeline-icon">${icon(s.icon)}</span><span><strong>${s.name}</strong><small>${esc(s.value)}</small></span></div>`).join('');
}

function renderVerification(){
  const frames=state.run?.frames??[],actual=frames.map((frame,index)=>({frame,index})).filter(x=>x.frame.verification);
  const displayed=state.frameIndex??Math.max(0,frames.length-1),count=state.run?.requested_ticks??Number($('tick-count').value);
  const bars=Array.from({length:count},(_,i)=>actual[i]??null);
  $('verification-bars').innerHTML=bars.map((item,index)=>{
    if(!item)return '<span class="verification-bar placeholder" aria-hidden="true"></span>';
    const v=item.frame.verification,hasAnomaly=v.details.some(d=>d.hit===false),height=v.total?Math.max(8,v.hits/v.total*100):0;
    return `<button class="verification-bar ${hasAnomaly?'has-anomaly':''} ${displayed===item.index?'selected':''}" style="--hit-height:${height}%" data-frame="${item.index}" aria-label="回看第 ${item.frame.tick} 步：命中 ${v.hits}/${v.total}${hasAnomaly?'，存在预测偏离':''}" title="第 ${item.frame.tick} 步 · 命中 ${v.hits} / ${v.total}${hasAnomaly?' · 预测偏离':''}"></button>`;
  }).join('');
  $('verification-caption').textContent=actual.length?`已验证 ${actual.length} 步 · 点击回看`:'运行后查看';
  $('find-anomaly').disabled=!actual.some(item=>item.frame.verification.details.some(d=>d.hit===false));
  $('verification-bars').querySelectorAll('[data-frame]').forEach(button=>button.onclick=()=>{state.frameIndex=Number(button.dataset.frame);renderRun();});
}

function renderWorld(){
  const frame=selectedFrame();if(!frame)return;
  const entries=Object.entries(frame.scene.entities),width=Math.max(220,$('world-canvas').clientWidth),height=$('world-canvas').clientHeight||350;
  const graphView=state.view==='graph';
  $('view-caption').textContent=graphView?'历史推断':'场景投影';
  $('view-legend').innerHTML=graphView?'<span class="legend-item"><i class="solid-dot"></i>实体节点</span><span class="legend-item"><i class="line-dot"></i>推断关系</span>':'<span class="legend-item"><i class="solid-dot"></i>观测位置</span>'+(preferences.get('predictions')?'<span class="legend-item"><i class="ring-dot"></i>预测范围</span>':'')+(preferences.get('trails')?'<span class="legend-item"><i class="line-dot"></i>运动轨迹</span>':'');
  if(graphView){LingshuScene.reset();renderGraph(frame,width,height,entries);return;}
  LingshuScene.draw({container:$('world-canvas'),frame,frames:state.run?.frames??[],frameIndex:state.frameIndex,runId:state.run?.id,scenario:state.scenario,entity:state.entity,settings:preferences,attach:attachEntityTargets});
}
function renderGraph(frame,width,height,entries){
  const compact=width<500,cardWidth=compact?112:160,cardHeight=72,positions={},paired={};
  entries.forEach(([id,e],i)=>{let angle=-Math.PI/2+i*2*Math.PI/entries.length;positions[id]=[width/2+Math.cos(angle)*width*(compact?.28:.27),height*.55+Math.sin(angle)*height*.28];});
  const edges=frame.graph.edges.map(edge=>{
    if(!positions[edge.source]||!positions[edge.target])return '';
    let [x,y]=positions[edge.source],[tx,ty]=positions[edge.target],dx=tx-x,dy=ty-y,length=Math.hypot(dx,dy);
    const scale=Math.max(Math.abs(dx)/(cardWidth/2+3),Math.abs(dy)/(cardHeight/2+3)),offsetX=dx/scale,offsetY=dy/scale;
    x+=offsetX;y+=offsetY;tx-=offsetX;ty-=offsetY;
    const key=edge.source+'|'+edge.target,ordinal=paired[key]??0;paired[key]=ordinal+1;
    const curve=compact?16+ordinal*26:26+ordinal*28,cx=(x+tx)/2-dy/length*curve,cy=(y+ty)/2+dx/length*curve;
    const labelX=(x+2*cx+tx)/4-dy/length*5,labelY=(y+2*cy+ty)/4+dx/length*5;
    const text=`${behaviorNames[edge.relation]||esc(edge.relation)} ${Math.round(edge.confidence*100)}%`,pillWidth=compact?61:70;
    return `<path d="M${x} ${y}Q${cx} ${cy} ${tx} ${ty}" fill="none" stroke="var(--scene-edge)" stroke-opacity=".55" stroke-width="1.2" marker-end="url(#arrowhead)"/><rect x="${labelX-pillWidth/2}" y="${labelY-9}" width="${pillWidth}" height="18" rx="5" fill="var(--paper)" stroke="var(--line)" stroke-width=".7"/><text x="${labelX}" y="${labelY+3}" fill="var(--muted)" font-size="${compact?13:14}" text-anchor="middle">${text}</text>`;
  }).join('');
  const nodes=entries.map(([id,e],i)=>{let [x,y]=positions[id],color=colors[i%colors.length],node=frame.graph.nodes[id],selected=state.entity===id;return `<g class="entity-target" data-entity="${esc(id)}" tabindex="0" role="button" aria-label="查看${esc(e.category)}"><rect x="${x-cardWidth/2}" y="${y-cardHeight/2}" width="${cardWidth}" height="${cardHeight}" rx="9" fill="var(--paper)" stroke="${color}" stroke-opacity="${selected?.9:.4}" stroke-width="${selected?1.5:.8}"/><circle cx="${x-cardWidth/2+14}" cy="${y-9}" r="3.5" fill="${color}"/><text x="${x-cardWidth/2+25}" y="${y-5}" fill="var(--ink)" font-size="${compact?13:14}" font-weight="500">${esc(e.category)}</text><text x="${x-cardWidth/2+13}" y="${y+15}" fill="${color}" font-size="${compact?13:14}">${behaviorNames[node.behavior_inferred]} · ${Math.round(node.confidence*100)}%</text></g>`;}).join('');
  $('world-canvas').innerHTML=`<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="由观测推断的实体关系图"><defs><marker id="arrowhead" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="none" stroke="var(--scene-edge)"/></marker><pattern id="graph-dots" x="0" y="0" width="20" height="20" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r=".6" fill="var(--scene-grid)"/></pattern></defs><rect width="${width}" height="${height}" fill="var(--scene-bg)"/><rect width="${width}" height="${height}" fill="url(#graph-dots)" opacity=".5"/><text x="18" y="23" fill="var(--muted)" font-size="12">历史认知图</text><text x="${width-18}" y="23" fill="var(--muted)" font-size="12" text-anchor="end">观测推断</text>${edges}${nodes}<text x="18" y="${height-17}" fill="var(--muted)" font-size="12">历史关系 · 不代表当前关系</text><text x="${width-18}" y="${height-17}" fill="var(--muted)" font-size="12" text-anchor="end">${compact?'':`${entries.length} 节点 · ${frame.graph.edges.length} 关系`}</text></svg>`;attachEntityTargets();
}
function attachEntityTargets(){document.querySelectorAll('[data-entity]').forEach(el=>{el.onclick=()=>{state.entity=el.dataset.entity;renderWorld();renderEntities();$('entity-dialog').showModal();};el.onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();el.onclick();}};});}
function renderEntities(){
  const frame=selectedFrame();if(!frame)return;
  const entries=Object.entries(frame.scene.entities);$('entity-count').textContent=entries.length;
  $('entities').innerHTML=entries.map(([id,e],index)=>{const n=frame.graph.nodes[id];return `<button class="entity-item ${state.entity===id?'selected':''}" data-eid="${esc(id)}"><i class="entity-color" style="background:${colors[index%colors.length]}"></i><span><strong>${esc(e.category)}</strong><small>${behaviorNames[n.behavior_inferred]||'待推断'} · (${e.pos[0].toFixed(1)}, ${e.pos[2].toFixed(1)})</small></span><span class="entity-confidence" title="模型置信度">${(n.confidence*100).toFixed(0)}%</span></button>`;}).join('');
  $('entities').querySelectorAll('[data-eid]').forEach(el=>el.onclick=()=>{state.entity=el.dataset.eid;renderEntities();renderWorld();});
  const detail=$('entity-detail'),entity=frame.scene.entities[state.entity];detail.classList.toggle('hidden',!entity);
  if(entity){const node=frame.graph.nodes[state.entity],v=frame.verification?.details.find(d=>d.entity===state.entity);detail.innerHTML=`<strong>${esc(entity.category)}</strong><br>位置 (${entity.pos.map(p=>p.toFixed(2)).join(', ')})<br>模拟器策略：${behaviorNames[entity.behavior]}<br>模型推断：${behaviorNames[node.behavior_inferred]}<br>观测来源：${esc(node.conditions.observation_tool)}${v?`<br>模式：${esc(modeLabels[v.mode]||v.mode)}<br>预测误差 ${v.distance===null?'待验证':v.distance.toFixed(3)} · 边界 ${v.bound.toFixed(3)}<br>${v.hit===null?'待验证':v.hit?'本步预测命中':'本步预测偏离'}`:''}`;}
}
function eventSummary(event){const d=event.data;if(event.kind==='tick')return `命中 ${d.verification.hits} / ${d.verification.total} · 异常 ${d.observation.anomalies} · 实际观测 ${d.observation.observed} 个实体`;if(event.kind==='memory')return `记忆节点 ${d.id}`;if(event.kind==='recall')return `${memoryItems(d).length} 条相关记忆`;if(d.error)return d.error;if(event.kind==='perturbation')return '外部事件造成真实位置突变；验证仍使用新的真实观测。';if(event.kind==='scene')return '场景模拟器 → 世界模型';if(event.kind==='completed')return `${d.ticks} 个时间步 · ${d.hits} / ${d.total} 个预测命中`;if(event.kind==='start')return `${state.run?.title} · ${d.ticks} 步`;return '记录已保存到本地会话';}
function renderEvents(){
  const events=state.run?.events??[];$('event-count').textContent=events.length;if(!events.length){$('events').innerHTML=`<div class="empty-events">${icon('activity')}<p>点击「新建实验」，开始第一次运行。</p><small>每一步预测、观测和验证都会留下记录。</small></div>`;return;}
  // Keep user-opened details stable as live results arrive.
  const opened=new Set([...$('events').querySelectorAll('details[open]')].map(d=>d.dataset.event));
  const selected=events;
  $('events').innerHTML=selected.map((e,i)=>{const key=events.length-selected.length+i,symbol={start:'play',recall:'search',scene:'orbit',tick:'activity',perturbation:'bolt',memory:'brain',completed:'check',cancelled:'stop',warning:'warning',error:'warning',interrupted:'warning'}[e.kind]||'clock';return `<article class="event ${esc(e.kind)}"><span class="event-symbol">${icon(symbol)}</span><div class="event-body"><div class="event-row"><strong>${esc(e.title)}</strong><time>${timeText(e.at)}</time></div><div class="event-summary">${esc(eventSummary(e))}</div>${Object.keys(e.data).length?`<details data-event="${key}" ${opened.has(String(key))?'open':''}><summary>工具返回数据</summary><pre>${esc(JSON.stringify(e.data,null,2))}</pre></details>`:''}</div></article>`;}).join('');
}
function memoryItems(result){const items=result?.pack??result?.items??result?.results??result?.memories??[];return Array.isArray(items)?items:[];}
async function searchMemory(){
  const container=$('memory-results');container.innerHTML='<div class="loading">正在召回记忆…</div>';
  try{const query=$('memory-query').value||'工作台',data=await api('/memory?query='+encodeURIComponent(query)+'&limit=20'),items=memoryItems(data);$('recall-count').textContent=items.length;$('recall-meta').textContent='真实检索 · '+timeText(new Date().toISOString());
    container.innerHTML=items.length?items.map(item=>{const node=item.node??item,fm=node.frontmatter??item.frontmatter??{},content=item.content??item.excerpt??item.text??node.content??'';return `<article class="memory-item"><div class="memory-item-top"><span>${icon('brain')} ${esc(item.id??node.id??fm.id??'记忆节点')}</span><span>${item.truncated?'摘录 · ':''}${item.score!=null?'得分 '+Number(item.score).toFixed(3):'召回结果'}</span></div><div class="memory-content">${esc(content)}</div><div class="memory-tags">${(fm.tags??item.tags??[]).map(t=>`<span>${esc(t)}</span>`).join('')}</div></article>`;}).join(''):`<div class="empty-events">${icon('brain')}<p>暂无匹配记忆。</p><small>完成一次实验，或点击「写笔记」记录新发现。</small></div>`;
  }catch(e){container.innerHTML=`<div class="empty-events">${icon('warning')}<p>${esc(e.message)}</p><small>在“连接与能力”中重新连接记忆。</small></div>`;$('recall-meta').textContent='检索失败';toast(e.message,true);}
}
async function loadConnections(){try{const data=await api('/integrations');state.integrations=data;updateMemoryStatus(data.memory);renderConnectionPaths();$('dsh-status-note').textContent=data.dsh.note;$('connection-agent-status').textContent=data.dsh.ready?'已配置':'待连接模型';$('connection-agent-status').className='cap-state '+(data.dsh.ready?'connected':'');$('mcp-tools').innerHTML=data.tools.map(t=>`<span>${esc(t)}</span>`).join('');}catch(e){toast(e.message,true);}}
function updateMemoryStatus(memory){for(const id of ['connection-memory-status']){$(id).textContent=memory.connected?'已接入':'未连接';$(id).className='cap-state '+(memory.connected?'connected':'error');}$('memory-nav-dot').classList.toggle('connected',memory.connected);$('memory-root').textContent=$('show-local-paths').checked?memory.root:'独立实验记忆库';$('connection-memory-error').textContent=memory.error??'';$('connection-memory-error').classList.toggle('hidden',!memory.error);}
async function poll(){if(polling)return;clearTimeout(pollTimer);polling=true;try{const [health,list]=await Promise.all([api('/health'),api('/runs')]);state.connected=true;state.runs=list;updateMemoryStatus(health.memory);$('service-status').className='connection-pill';$('service-status').innerHTML='<i class="status-dot"></i>本地引擎在线';
    if(state.run&&isActive()){const id=state.run.id,token=generation,run=await api('/runs/'+id);if(state.run?.id===id&&token===generation){const wasActive=isActive();state.run=run;renderRun();if(wasActive&&!isActive())toast(run.memory_id?'实验完成，结果已写入记忆。':`实验${statusNames[run.status]||run.status}。`);}}
    renderSessions();
  }catch(e){state.connected=false;$('service-status').className='connection-pill offline';$('service-status').innerHTML='<i class="status-dot"></i>本地服务未连接';}finally{polling=false;pollTimer=setTimeout(poll,isActive()?180:2500);}}

async function init(){
  hydrate();switchPage('agent');new ResizeObserver(()=>renderWorld()).observe($('world-canvas'));document.querySelectorAll('[data-page]').forEach(el=>el.onclick=()=>switchPage(el.dataset.page));document.querySelector('.brand').onclick=event=>{event.preventDefault();switchPage('agent');};document.querySelectorAll('[data-tab]').forEach(el=>el.onclick=()=>setTab(el.dataset.tab));document.querySelectorAll('[data-view]').forEach(el=>el.onclick=()=>{state.view=el.dataset.view;document.querySelectorAll('[data-view]').forEach(button=>button.classList.toggle('active',button===el));renderWorld();});
  $('see-connections').onclick=()=>switchPage('connections');
  preferences.bind(applyUIPreferences);
  $('toggle-sidebar').onclick=()=>preferences.set('sidebar',!preferences.get('sidebar'));
  $('open-search').onclick=openSearch;$('global-query').oninput=renderSearch;$('history-query').oninput=renderSessions;
  $('all-history').onclick=()=>$('open-history').click();
  $('open-settings').onclick=()=>$('settings-dialog').showModal();
  // Settings controls are bound by LingshuPreferences.
  // Replay preference follows both the settings switch and the disclosure.
  $('replay-details').ontoggle=()=>{if(preferences.get('replay')!==$('replay-details').open)preferences.set('replay',$('replay-details').open);};
  // Restore defaults is handled by LingshuPreferences.
  $('open-results').onclick=()=>switchPage('results');
  $('open-entities').onclick=()=>{renderEntities();$('entity-dialog').showModal();};
  $('open-history').onclick=()=>{$('history-query').value='';renderSessions();$('history-dialog').showModal();$('history-query').focus();};
  $('open-help').onclick=()=>$('help-dialog').showModal();
  $('workspace-help').onclick=()=>$('open-help').click();
  $('workspace-new-task').onclick=()=>$('new-task').click();
  $('open-memory-note').onclick=()=>$('note-dialog').showModal();
  document.querySelectorAll('[data-back-scene]').forEach(b=>b.onclick=()=>switchPage('workspace'));
  document.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>$(b.dataset.close).close());
  document.querySelectorAll('dialog').forEach(d=>d.addEventListener('click',e=>{if(e.target===d){const r=d.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)d.close();}}));
  $('new-task').onclick=async()=>{if(isActive()){toast('当前实验正在运行，请先完成或停止运行。');return;}if($('experiment-dialog').open)return;++generation;state.run=null;state.frameIndex=null;state.entity=null;$('task-note').value='';$('save-memory').checked=preferences.get('autoMemory');switchPage('workspace');setTab('scene');renderScenarios();try{state.preview=await api('/preview/'+state.scenario);renderRun();renderSessions();$('experiment-dialog').showModal();}catch(e){toast(e.message,true);}};
  $('run-button').onclick=async()=>{if(state.loading)return;state.loading=true;$('run-button').disabled=true;try{const run=await post('/runs',{scenario:state.scenario,note:$('task-note').value,ticks:Number($('tick-count').value),interval_ms:300,save_memory:$('save-memory').checked});++generation;state.run=run;state.frameIndex=null;state.entity=null;$('experiment-dialog').close();switchPage('workspace');renderRun();await poll();}catch(e){toast(e.message,true);}finally{state.loading=false;$('run-button').disabled=false;}};
  $('stop-button').onclick=async()=>{if(!state.run)return;$('stop-button').disabled=true;try{await post('/runs/'+state.run.id+'/cancel');toast('已请求停止运行。');await poll();}catch(e){toast(e.message,true);$('stop-button').disabled=false;}};
  $('playback').oninput=()=>{state.frameIndex=Number($('playback').value);renderRun();};$('live-view').onclick=()=>{state.frameIndex=null;renderRun();};$('tick-count').onchange=()=>{if(!state.run)renderRun();};
  $('find-anomaly').onclick=()=>{const frames=state.run?.frames??[],anomalies=frames.map((frame,index)=>({frame,index})).filter(item=>item.frame.verification?.details.some(d=>d.hit===false));if(!anomalies.length)return;const next=anomalies.find(item=>state.frameIndex!==null&&item.index>state.frameIndex)??anomalies[0];$('replay-details').open=true;state.frameIndex=next.index;state.entity=next.frame.verification.details.find(d=>d.hit===false).entity;renderRun();$('entity-dialog').showModal();};
  $('save-memory').onchange=renderPipeline;
  $('statistics-range').onchange=renderStatistics;
  $('show-local-paths').onchange=renderConnectionPaths;
  $('memory-search').onsubmit=event=>{event.preventDefault();searchMemory();};
  $('remember-form').onsubmit=async event=>{event.preventDefault();const content=$('memory-note').value.trim();if(!content)return;$('remember-button').disabled=true;try{const result=await post('/memory',{content});$('memory-note').value='';$('note-dialog').close();toast('记忆已写入：'+result.id);await searchMemory();}catch(e){toast(e.message,true);}finally{$('remember-button').disabled=false;}};
  $('reconnect-button').onclick=async()=>{$('reconnect-button').disabled=true;try{const result=await post('/memory/reconnect');updateMemoryStatus(result);toast(result.connected?'记忆已重新连接。':result.error??'连接失败',!result.connected);}catch(e){toast(e.message,true);}finally{$('reconnect-button').disabled=false;}};
  $('copy-config').onclick=async()=>{try{if(!state.integrations)await loadConnections();await navigator.clipboard.writeText(state.integrations.dsh.cordis_patch);toast('MCP 配置已复制。');}catch(e){toast('复制失败，请选择配置文本后手动复制。',true);}};
  document.addEventListener('keydown',event=>{if(event.key==='Escape'){const dialog=document.querySelector('dialog[open]');if(dialog){event.preventDefault();dialog.close();return;}}if(event.key==='\\'&&(event.ctrlKey||event.metaKey)&&!document.querySelector('dialog[open]')){event.preventDefault();preferences.set('sidebar',!preferences.get('sidebar'));return;}if(event.key.toLowerCase()==='k'&&(event.ctrlKey||event.metaKey)){event.preventDefault();openSearch();return;}if(event.key.toLowerCase()==='n'&&!event.ctrlKey&&!event.metaKey&&!document.querySelector('dialog[open]')&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName))$('new-task').click();});
  try{state.scenarios=await api('/scenarios');state.preview=await api('/preview/'+state.scenario);renderScenarios();renderRun();await poll();}catch(e){toast('无法连接工作台：'+e.message,true);poll();}
}
const modeLabels={exact:'点位置外推（有容差）',bounded_noisy:'方向外推 / 扰动容差',bounded_stochastic:'随机运动可达域',chase_stochastic:'追逐随机目标可达域'};
function renderStatistics(){
  const step=$('statistics-range').value==='step',frame=selectedFrame();
  const details=step?(frame?.verification?.details??[]):(state.run?.frames??[]).flatMap(f=>f.verification?.details??[]);
  const groups={};
  for(const d of details){const g=groups[d.mode]??={hits:0,verified:0,pending:0,distance:0,bound:0,max:0};if(d.status==='pending'||d.actual===null){g.pending++;continue;}g.verified++;g.hits+=d.hit===true?1:0;g.distance+=d.distance;g.bound+=d.bound;g.max=Math.max(g.max,d.distance);}
  $('statistics-scope').textContent=step?`本步 · 第 ${frame?.tick??0} 步`:`实验汇总 · ${state.run?.completed_ticks??0} 步`;
  $('mode-statistics').innerHTML=Object.entries(groups).sort().map(([mode,g])=>`<div class="mode-stat"><strong>${esc(modeLabels[mode]||mode)}</strong><span>命中 ${g.hits} / 已验证 ${g.verified} · 待验证 ${g.pending}</span><small>平均误差 ${g.verified?(g.distance/g.verified).toFixed(3):'—'} · 最大 ${g.verified?g.max.toFixed(3):'—'}<br>平均边界 ${g.verified?(g.bound/g.verified).toFixed(3):'—'}</small></div>`).join('')||'<p class="statistics-note">暂无已验证预测。</p>';
}
function renderConnectionPaths(){
  const data=state.integrations;if(!data)return;
  $('memory-root').textContent=$('show-local-paths').checked?data.memory.root:'独立实验记忆库';
  $('mcp-config').textContent=$('show-local-paths').checked?data.dsh.cordis_patch:data.dsh.public_patch;
}
init();
