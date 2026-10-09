/* Actual committed Harness events; this interface does not simulate token deltas. */
'use strict';
(() => {
  const chatState = {chat:null, list:[], matches:[], status:null, sending:false, generation:0, drafts:new Map(), retries:new Map()};
  let timer, searchTimer, lastList=0, searchGeneration=0;
  const active = turn => turn && ['running','cancelling'].includes(turn.status);
  const latest = () => chatState.chat?.turns.at(-1);
  const terminalNames = {completed:'已完成',failed:'未完成',cancelled:'已停止',interrupted:'已中断',running:'回复中',cancelling:'正在停止',empty:'新对话'};
  const toolNames = {lingshu_list_scenarios:'查看可用场景',lingshu_run_scene:'运行实验',lingshu_get_run:'查询实验结果',lingshu_cancel_run:'停止实验',lingshu_recall:'召回实验记忆',lingshu_remember:'记录观察'};
  const jsonText = value => typeof value==='string'?value:JSON.stringify(value,null,2);
  function formatText(text) {
    // Escape first. Only fixed markup is inserted; model HTML remains literal.
    return String(text??'').split(/(```[^\n]*\n[\s\S]*?```)/g).map(part=>{
      if(part.startsWith('```'))return '<pre><code>'+esc(part.replace(/^```[^\n]*\n/,'').replace(/```$/,''))+'</code></pre>';
      const inline=value=>esc(value).replace(/^#{1,4} (.+)$/gm,'<strong class="message-section">$1</strong>').replace(/\*\*([^*\n]+)\*\*/g,'<strong>$1</strong>').replace(/`([^`\n]+)`/g,'<code>$1</code>');
      const lines=part.split('\n'), chunks=[];let prose=[];
      const flush=()=>{if(prose.length)chunks.push('<div class="message-prose">'+inline(prose.join('\n'))+'</div>');prose=[];};
      const cells=line=>line.trim().replace(/^\||\|$/g,'').split('|').map(c=>c.trim());
      for(let i=0;i<lines.length;i++){
        if(lines[i].includes('|')&&i+1<lines.length&&/^\s*\|?\s*:?-{3,}:?\s*\|/.test(lines[i+1])){
          flush();const headers=cells(lines[i]);i+=2;const rows=[];
          while(i<lines.length&&lines[i].includes('|')&&lines[i].trim()){rows.push(cells(lines[i]));i++;}i--;
          chunks.push('<div class="message-table"><table><thead><tr>'+headers.map(c=>'<th>'+inline(c)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(row=>'<tr>'+headers.map((_,j)=>'<td>'+inline(row[j]||'')+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>');
        }else prose.push(lines[i]);
      }
      flush();return chunks.join('');
    }).join('');
  }
  function chatButton(c) {
    return `<button class="session ${c.id===chatState.chat?.id?'active':''}" data-chat-id="${esc(c.id)}"><i class="session-dot ${esc(c.status)}"></i><span><strong>${esc(c.title)}</strong><small>${dateText(c.updated_at)} · ${c.read_only?'恢复的历史':terminalNames[c.status]||'对话'}</small></span></button>`;
  }
  function renderList() {
    const q=$('chats-query').value.trim().toLowerCase();
    for(const [id,items] of [['chat-sessions',chatState.list.slice(0,5)],['all-chats',q?chatState.matches:chatState.list]]){
      const container=$(id),markup=items.map(chatButton).join('')||`<div class="sidebar-empty">${q&&id==='all-chats'?'没有匹配的对话':'暂无对话'}</div>`;
      if(container.dataset.markup===markup)continue;
      const focused=container.contains(document.activeElement)?document.activeElement.dataset.chatId:null;
      container.innerHTML=markup;container.dataset.markup=markup;
      container.querySelectorAll('[data-chat-id]').forEach(b=>{b.onclick=()=>{if($('chats-dialog').open)$('chats-dialog').close();loadChat(b.dataset.chatId);};if(b.dataset.chatId===focused)b.focus({preventScroll:true});});
    }
  }
  async function searchChats() {
    const query=$('chats-query').value.trim(),revision=++searchGeneration;
    if(!query){chatState.matches=[];renderList();return;}
    try{
      const matches=await api('/agent/chats?query='+encodeURIComponent(query));
      if(revision!==searchGeneration)return;
      chatState.matches=matches;renderList();
    }catch(e){if(revision===searchGeneration)toast(e.message,true);}
  }
  function saveDraft() {
    chatState.drafts.set(chatState.chat?.id||'new',$('chat-input').value);
  }
  async function loadChat(id) {
    saveDraft();const generation=++chatState.generation;
    try {
      const chat=await api('/agent/chats/'+id);
      if(generation!==chatState.generation)return;
      chatState.chat=chat;
      try{localStorage.setItem('lingshu-last-chat',chat.id);}catch{}
      $('chat-input').value=chatState.drafts.get(chat.id)||'';
      $('chat-messages').innerHTML='';
      switchPage('agent');render();renderList();$('chat-scroll').scrollTop=$('chat-scroll').scrollHeight;
    } catch(e){toast(e.message,true);}
  }
  function newChat() {
    saveDraft();++chatState.generation;chatState.chat=null;
    try{localStorage.removeItem('lingshu-last-chat');}catch{}
    $('chat-input').value=chatState.drafts.get('new')||'';
    $('chat-messages').innerHTML='';switchPage('agent');render();renderList();$('chat-input').focus();
  }
  function toolMarkup(turn) {
    const calls=turn.events.filter(e=>e.type==='tool_call');
    if(!calls.length)return '';
    return `<details class="agent-tools" data-preserve="tools-${turn.id}"><summary>${icon('activity')}<span>${calls.length} 次工具调用</span>${icon('chevron')}</summary><div class="agent-tool-list">${calls.map(call=>{
      const result=turn.events.find(e=>e.type==='tool_result'&&e.callId===call.callId),label=toolNames[String(call.tool).split('__').at(-1)]||call.tool;
      const status=result?(result.status==='error'?'失败':'完成'):(active(turn)?'执行中':'已中断');
      return `<details class="agent-tool" data-preserve="call-${esc(call.callId)}"><summary><span>${esc(label)}</span><small class="${result?.status==='error'?'error-text':''}">${status}</small></summary><div class="tool-data"><span>参数</span><pre>${esc(jsonText(call.input))}</pre>${result?`<span>返回结果${result.truncated?'（运行时已截断）':''}</span><pre>${esc(jsonText(result.result))}</pre>`:''}</div></details>`;
    }).join('')}</div></details>`;
  }
  function renderTurn(turn) {
    const lastText=turn.events.filter(e=>e.type==='text').map(e=>e.text).join('\n\n');
    const answer=active(turn)?lastText:turn.answer;
    return `<article class="chat-turn" data-turn-id="${turn.id}"><div class="user-message">${esc(turn.user)}</div><div class="assistant-message"><div class="assistant-label"><span>灵枢</span><small>${turn.model==='deepseek-v4-pro'?'DeepSeek V4 Pro':'DeepSeek Flash'} · ${turn.effort==='max'?'最高':'高'}</small></div>${toolMarkup(turn)}${answer?`<div class="assistant-body">${formatText(answer)}</div>`:''}${active(turn)?`<div class="agent-working">${icon('activity')}<span>${turn.status==='cancelling'?'正在停止…':turn.events.some(e=>e.type==='tool_call')?'正在处理工具结果…':'正在思考…'}</span></div>`:''}${(turn.run_ids||[]).map(id=>`<button class="button ghost run-link" data-agent-run="${esc(id)}">${icon('orbit')}打开实验沙盘${icon('arrow')}</button>`).join('')}${turn.error?`<div class="chat-turn-error">${icon('info')}<span>${esc(turn.error)}</span></div>`:''}${!active(turn)?`<div class="message-footer"><span>${terminalNames[turn.status]} · ${timeText(turn.finished_at||turn.created_at)}</span>${answer?`<button class="text-button" data-copy-answer="${turn.id}">${icon('copy')}复制</button>`:''}</div>`:''}</div></article>`;
  }
  function render() {
    const turns=chatState.chat?.turns||[],busy=active(latest()),scroll=$('chat-scroll');
    const nearBottom=scroll.scrollHeight-scroll.scrollTop-scroll.clientHeight<100;
    $('chat-title').textContent=chatState.chat?.title||'新对话';
    $('chat-welcome').classList.toggle('hidden',turns.length>0);
    for(const turn of turns){
      let node=document.querySelector(`[data-turn-id="${turn.id}"]`);
      const markup=renderTurn(turn);
      if(node?.dataset.markup===markup)continue;
      const open=new Set(node?[...node.querySelectorAll('details[open]')].map(d=>d.dataset.preserve):[]);
      const wasFocused=node?.contains(document.activeElement)?document.activeElement.closest('[data-preserve]')?.dataset.preserve:null;
      const holder=document.createElement('div');holder.innerHTML=markup;
      const replacement=holder.firstElementChild;replacement.dataset.markup=markup;
      if(node)node.replaceWith(replacement);else $('chat-messages').append(replacement);
      replacement.querySelectorAll('details').forEach(d=>{if(open.has(d.dataset.preserve))d.open=true;if(d.dataset.preserve===wasFocused)d.querySelector('summary').focus({preventScroll:true});});
      replacement.querySelectorAll('[data-agent-run]').forEach(b=>b.onclick=()=>selectRun(b.dataset.agentRun));
      replacement.querySelectorAll('[data-copy-answer]').forEach(b=>b.onclick=async()=>{try{await navigator.clipboard.writeText(turn.answer);toast('回答已复制。');}catch{toast('复制失败，请手动选择文本。',true);}});
    }
    $('chat-stop').classList.toggle('hidden',!busy);
    $('chat-stop').disabled=latest()?.status==='cancelling';
    $('chat-send').classList.toggle('hidden',busy);
    const readOnly=!!chatState.chat?.read_only;
    $('chat-input').disabled=readOnly;
    $('chat-input').placeholder=readOnly?'这是恢复的历史记录，请新建对话继续工作。':'和灵枢聊聊，或描述一个实验…';
    $('chat-send').disabled=readOnly||chatState.sending||!$('chat-input').value.trim();
    $('chat-rename').disabled=!chatState.chat;
    $('chat-delete').disabled=!chatState.chat||busy||chatState.sending;
    $('chat-export').disabled=!turns.length;
    $('chat-progress').textContent=busy?'正在执行 · 可随时停止':`${chatState.status?.effort==='max'?'最高':'高'}强度思考 · 本机工具`;
    $('chat-subtitle').textContent=readOnly?'恢复的历史记录 · 可查看和导出':chatState.status?.ready?'会话保存在本机':'请连接模型，开始对话';
    if(nearBottom)scroll.scrollTop=scroll.scrollHeight;
  }
  async function refreshStatus(force=false) {
    chatState.status=await api('/agent/status'+(force?'?refresh=true':''));
    const s=chatState.status;
    $('agent-model-label').textContent=s.ready?`${s.model==='deepseek-v4-pro'?'V4 Pro':'Flash'} · ${s.effort==='max'?'最高':'高'}`:'连接模型';
    $('model-status').textContent=!s.ready?s.diagnostic:`Harness ${s.version} · ${s.verified?'当前配置上次成功：'+dateText(s.last_success_at):'凭据已配置 · 当前配置尚待真实请求验证'}`;
    render();return s;
  }
  async function openModel() {
    try {
      const s=await refreshStatus();
      $('model-executable').value=s.executable;$('model-name').value=s.model;$('model-effort').value=s.effort;
      $('model-local-credentials').checked=s.local_credentials;$('model-key').value='';$('model-clear-key').checked=false;
      $('model-key').placeholder=s.has_saved_key?'已加密保存，留空保留':'留空沿用本机配置';
      $('model-dialog').showModal();
    } catch(e){toast(e.message,true);}
  }
  async function send(event) {
    event.preventDefault();const content=$('chat-input').value.trim();
    if(!content||chatState.sending||active(latest())||chatState.chat?.read_only)return;
    chatState.sending=true;render();const generation=chatState.generation;
    try {
      if(!chatState.status?.ready){await openModel();return;}
      if(!chatState.chat){
        const chat=await post('/agent/chats');
        if(generation!==chatState.generation)return;
        chatState.chat=chat;
        try{localStorage.setItem('lingshu-last-chat',chat.id);}catch{}
      }
      const id=chatState.chat.id, retry=chatState.retries.get(id),request_id=retry?.content===content?retry.request_id:crypto.randomUUID();
      chatState.retries.set(id,{content,request_id});
      const turn=await post(`/agent/chats/${id}/messages`,{content,request_id});
      chatState.retries.delete(id);
      if(generation!==chatState.generation||chatState.chat?.id!==id){toast('消息已发送，可以从对话历史查看。');return;}
      if(!chatState.chat.turns.some(t=>t.id===turn.id))chatState.chat.turns.push(turn);
      if(chatState.chat.turns.length===1)chatState.chat.title=[...content].slice(0,36).join('');
      $('chat-input').value='';chatState.drafts.delete(id);chatState.drafts.delete('new');
      $('chat-notice').classList.add('hidden');
      render();$('chat-scroll').scrollTop=$('chat-scroll').scrollHeight;
      await refreshList();
    } catch(e){$('chat-notice').textContent=e.message;$('chat-notice').classList.remove('hidden');}
    finally {chatState.sending=false;render();}
  }
  async function refreshList() {chatState.list=await api('/agent/chats');lastList=Date.now();renderList();if($('chats-query').value.trim())await searchChats();}
  async function pollChat() {
    clearTimeout(timer);
    try {
      const chat=chatState.chat, turn=latest(),generation=chatState.generation;
      if(active(turn)){
        const update=await api(`/agent/chats/${chat.id}/turns/${turn.id}?after=${turn.events.at(-1)?.seq||0}`);
        if(generation===chatState.generation&&chatState.chat?.id===chat.id){
          const events=[...turn.events,...update.events];Object.assign(turn,update,{events});render();
          if(!active(turn))await refreshStatus();
        }
      }
      if(Date.now()-lastList>5000)await refreshList();
    } catch { $('chat-progress').textContent='连接暂时中断，正在重连…'; }
    finally {timer=setTimeout(pollChat,active(latest())?800:2500);}
  }
  async function initAgent() {
    $('new-chat').onclick=newChat;$('agent-model').onclick=openModel;$('connection-agent-settings').onclick=openModel;
    $('chat-form').onsubmit=send;
    $('chat-input').oninput=()=>{saveDraft();$('chat-send').disabled=!!chatState.chat?.read_only||chatState.sending||!$('chat-input').value.trim();};
    $('chat-input').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();$('chat-form').requestSubmit();}};
    $('chat-stop').onclick=async()=>{const id=chatState.chat?.id;if(!id)return;$('chat-stop').disabled=true;try{await post(`/agent/chats/${id}/stop`);if(chatState.chat?.id===id&&active(latest()))latest().status='cancelling';render();}catch(e){toast(e.message,true);$('chat-stop').disabled=false;}};
    document.querySelectorAll('[data-prompt]').forEach(b=>b.onclick=()=>{$('chat-input').value=b.dataset.prompt;$('chat-input').oninput();$('chat-input').focus();});
    $('open-chats').onclick=()=>{$('chats-query').value='';++searchGeneration;renderList();$('chats-dialog').showModal();$('chats-query').focus();};
    $('chats-query').oninput=()=>{clearTimeout(searchTimer);searchTimer=setTimeout(searchChats,180);};
    $('model-refresh').onclick=async()=>{try{await refreshStatus(true);}catch(e){toast(e.message,true);}};
    $('model-form').onsubmit=async e=>{
      e.preventDefault();$('model-save').disabled=true;
      try {
        const data={executable:$('model-executable').value.trim(),model:$('model-name').value,effort:$('model-effort').value,
          local_credentials:$('model-local-credentials').checked,clear_key:$('model-clear-key').checked};
        if($('model-key').value.trim())data.api_key=$('model-key').value.trim();
        await api('/agent/settings',{method:'PUT',body:JSON.stringify(data)});$('model-key').value='';
        await refreshStatus();toast('模型设置已保存。');
        if(chatState.status.ready)$('model-dialog').close();
      } catch(e){$('model-status').textContent=e.message;}finally{$('model-save').disabled=false;}
    };
    $('model-dialog').addEventListener('close',()=>{$('model-key').value='';});
    $('chat-rename').onclick=()=>{if(!chatState.chat)return;$('chat-rename-input').value=chatState.chat.title;$('chat-rename-dialog').showModal();$('chat-rename-input').select();};
    $('chat-rename-form').onsubmit=async e=>{e.preventDefault();if(!chatState.chat)return;try{const result=await api(`/agent/chats/${chatState.chat.id}`,{method:'PATCH',body:JSON.stringify({title:$('chat-rename-input').value.trim()})});chatState.chat.title=result.title;$('chat-rename-dialog').close();render();await refreshList();}catch(error){toast(error.message,true);}};
    $('chat-delete').onclick=()=>{if(!chatState.chat||active(latest()))return;$('chat-delete-title').textContent=chatState.chat.title;$('chat-delete-dialog').dataset.chatId=chatState.chat.id;$('chat-delete-dialog').showModal();};
    $('chat-delete-confirm').onclick=async()=>{
      const id=$('chat-delete-dialog').dataset.chatId;$('chat-delete-confirm').disabled=true;
      try{await api('/agent/chats/'+id,{method:'DELETE'});$('chat-delete-dialog').close();chatState.drafts.delete(id);chatState.retries.delete(id);if(chatState.chat?.id===id)newChat();await refreshList();toast('对话记录已删除。');}
      catch(e){toast(e.message,true);}finally{$('chat-delete-confirm').disabled=false;}
    };
    $('backup-data').onclick=async()=>{
      const button=$('backup-data');button.disabled=true;
      try{
        const response=await fetch('/api/backup',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
        if(!response.ok){const body=await response.json();throw new Error(body.detail||'备份失败。');}
        const url=URL.createObjectURL(await response.blob()),a=document.createElement('a');a.href=url;
        a.download='灵枢数据备份-'+new Date().toLocaleDateString('sv-SE')+'.zip';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('备份已生成。');
      }catch(e){toast(e.message,true);}finally{button.disabled=false;}
    };
    $('chat-export').onclick=()=>{
      const c=chatState.chat;if(!c?.turns.length)return;
      const text='# '+c.title+'\n\n'+c.turns.map(t=>'## 我\n\n'+t.user+'\n\n## 灵枢\n\n'+t.answer+(t.error?'\n\n'+t.error:'')).join('\n\n');
      const url=URL.createObjectURL(new Blob([text],{type:'text/markdown;charset=utf-8'}));
      const a=document.createElement('a');a.href=url;a.download='灵枢对话-'+c.id.slice(0,8)+'.md';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    };
    document.addEventListener('lingshu:page',e=>{if(e.detail==='agent')render();});
    try {
      await Promise.all([refreshList(),refreshStatus()]);
      let id;try{id=localStorage.getItem('lingshu-last-chat');}catch{}
      if(id&&chatState.list.some(c=>c.id===id))await loadChat(id);else render();
    } catch(e){toast('对话服务连接失败：'+e.message,true);}
    pollChat();
  }
  initAgent();
})();
