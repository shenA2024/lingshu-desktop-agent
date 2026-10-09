/* User-managed MCP connections. Server descriptions are data, always escaped. */
'use strict';
(() => {
  let entries=[];
  function secretRow(container,key='',stored=false){
    const row=document.createElement('div');row.className='secret-row';
    const name=document.createElement('input');name.value=key;name.placeholder=tr('名称');name.setAttribute('aria-label',tr('变量或标头名称'));
    const value=document.createElement('input');value.type='password';value.autocomplete='new-password';value.placeholder=tr(stored?'已加密保存，留空保留':'值');value.setAttribute('aria-label',tr('值'));
    const remove=document.createElement('button');remove.type='button';remove.className='text-button';remove.textContent='×';remove.setAttribute('aria-label',tr('移除此项'));remove.onclick=()=>row.remove();
    row.append(name,value,remove);container.append(row);
  }
  function transport(){const http=$('tool-transport').value==='streamable-http';$('tool-stdio-fields').hidden=http;$('tool-http-fields').hidden=!http;$('tool-command').required=!http;$('tool-url').required=http;}
  function open(entry){
    $('tool-form').reset();$('tool-name').readOnly=!!entry;
    for(const key of ['name','transport','command','cwd','url'])$('tool-'+key).value=entry?.[key]||(key==='transport'?'stdio':'');
    $('tool-args').value=(entry?.args||[]).join('\n');
    for(const kind of ['env','headers']){const container=$('tool-'+kind);container.replaceChildren();Object.keys(entry?.[kind]||{}).forEach(key=>secretRow(container,key,true));}
    $('tool-form-status').textContent='';transport();LingshuSelect.sync();$('tool-dialog').showModal();$('tool-name').focus();
  }
  function render(){
    $('external-tools').innerHTML=entries.map(entry=>{
      const check=entry.check;
      return `<article class="external-tool"><div class="external-tool-heading"><div><strong>${esc(entry.name)}</strong><small>${entry.transport==='stdio'?tr('本机进程'):tr('HTTP 服务')} · ${tr(entry.enabled?'已启用':'未启用')}</small></div><label class="tool-enable"><span class="sr-only">${tr('启用工具')} ${esc(entry.name)}</span><input type="checkbox" role="switch" data-tool-enable="${esc(entry.name)}" ${entry.enabled?'checked':''} ${!check?.ok?'disabled':''}></label></div><div class="tool-status">${check?check.ok?tr('连接成功')+' · '+check.tools.length+' '+tr('个工具'):tr(check.code==='MCP_TIMEOUT'?'连接检查超时':'连接失败，请检查命令、地址与凭据'):tr('尚未检查连接')}</div>${check?.ok?`<details><summary>${tr('查看工具')}</summary><div class="external-tool-catalog">${check.tools.map(t=>`<div><code>${esc(t.name)}</code><p>${esc(t.description)}</p></div>`).join('')||tr('服务未提供工具')}</div></details>`:''}<div class="external-tool-actions"><button class="button ghost" data-tool-check="${esc(entry.name)}">${tr('检查连接')}</button><button class="text-button" data-tool-edit="${esc(entry.name)}">${tr('编辑')}</button><button class="text-button" data-tool-delete="${esc(entry.name)}">${tr('移除')}</button></div></article>`;
    }).join('')||`<p class="settings-hint">${tr('还没有通用工具连接。添加你要使用的 MCP 服务，检查成功后启用。')}</p>`;
    $('external-tools').querySelectorAll('[data-tool-edit]').forEach(b=>b.onclick=()=>open(entries.find(e=>e.name===b.dataset.toolEdit)));
    $('external-tools').querySelectorAll('[data-tool-delete]').forEach(b=>b.onclick=()=>{$('tool-delete-name').textContent=b.dataset.toolDelete;$('tool-delete-dialog').dataset.name=b.dataset.toolDelete;$('tool-delete-dialog').showModal();});
    $('external-tools').querySelectorAll('[data-tool-enable]').forEach(b=>b.onchange=async()=>{b.disabled=true;try{await api('/agent/tools/'+encodeURIComponent(b.dataset.toolEnable),{method:'PATCH',body:JSON.stringify({enabled:b.checked})});await refresh();toast(tr('工具设置已保存，下一轮对话生效。'));}catch(e){toast(e.message,true);await refresh();}});
    $('external-tools').querySelectorAll('[data-tool-check]').forEach(b=>b.onclick=async()=>{b.disabled=true;b.textContent=tr('检查中…');try{const result=await post('/agent/tools/'+encodeURIComponent(b.dataset.toolCheck)+'/check');await refresh();toast(tr(result.ok?'工具连接检查成功。':'连接检查失败，请核对配置。'),!result.ok);}catch(e){toast(e.message,true);}finally{b.disabled=false;b.textContent=tr('检查连接');}});
  }
  async function refresh(){entries=await api('/agent/tools');render();}
  $('add-tool').onclick=()=>open();$('tool-transport').onchange=transport;
  for(const kind of ['env','headers'])$('add-tool-'+kind).onclick=()=>secretRow($('tool-'+kind));
  $('tool-form').onsubmit=async e=>{
    e.preventDefault();$('tool-save').disabled=true;
    try{
      const http=$('tool-transport').value==='streamable-http',values=kind=>Object.fromEntries([...$('tool-'+kind).children].map(row=>{const [key,value]=row.querySelectorAll('input');return [key.value.trim(),value.value];}).filter(([key])=>key));
      const spec={name:$('tool-name').value.trim(),transport:$('tool-transport').value,
        command:http?'':$('tool-command').value.trim(),args:http?[]:$('tool-args').value.split('\n').filter(Boolean),cwd:http?'':$('tool-cwd').value.trim(),
        url:http?$('tool-url').value.trim():'',env:http?{}:values('env'),headers:http?values('headers'):{}};
      await api('/agent/tools',{method:'PUT',body:JSON.stringify(spec)});$('tool-dialog').close();await refresh();toast(tr('已保存。检查连接后可以启用工具。'));
    }catch(error){$('tool-form-status').textContent=error.message;}finally{$('tool-save').disabled=false;}
  };
  $('tool-dialog').addEventListener('close',()=>{for(const kind of ['env','headers'])$('tool-'+kind).replaceChildren();});
  $('tool-delete-confirm').onclick=async()=>{const b=$('tool-delete-confirm');b.disabled=true;try{await api('/agent/tools/'+encodeURIComponent($('tool-delete-dialog').dataset.name),{method:'DELETE'});$('tool-delete-dialog').close();await refresh();}catch(e){toast(e.message,true);}finally{b.disabled=false;}};
  document.addEventListener('lingshu:page',e=>{if(e.detail==='connections')refresh().catch(e=>toast(e.message,true));});
  document.addEventListener('lingshu:language',render);
  refresh().catch(e=>toast(e.message,true));
})();
