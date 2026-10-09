/* Accessible single-choice popovers; the native select remains the form value. */
'use strict';
window.LingshuSelect = (() => {
  const widgets = new Map();
  let opened;
  function enhance(select) {
    if (widgets.has(select)) return;
    const trigger=document.createElement('button');trigger.type='button';trigger.className='select-trigger';
    trigger.id=select.id+'-trigger';trigger.setAttribute('role','combobox');trigger.setAttribute('aria-haspopup','listbox');
    trigger.setAttribute('aria-expanded','false');trigger.setAttribute('aria-controls',select.id+'-listbox');
    const menu=document.createElement('div');menu.id=select.id+'-listbox';menu.className='select-popover';
    menu.setAttribute('role','listbox');menu.setAttribute('popover','manual');
    select.after(trigger);(select.closest('dialog')||document.body).append(menu);
    // Keep labels and form bindings, with one accessible focus target.
    select.classList.add('enhanced-select');select.tabIndex=-1;select.setAttribute('aria-hidden','true');
    const ownerLabel=select.closest('label')?.cloneNode(true);
    ownerLabel?.querySelectorAll('small,select,button,input').forEach(n=>n.remove());
    const label=select.getAttribute('aria-label')||ownerLabel?.textContent.trim()||select.id;
    trigger.setAttribute('aria-label',label);menu.setAttribute('aria-label',label);
    const widget={select,trigger,menu,index:0,search:'',searchTimer:null,snapshot:null};widgets.set(select,widget);
    const choices=()=>[...select.options].filter(o=>!o.disabled&&!o.hidden);
    function sync(){
      const aria=select.getAttribute('aria-label')||tr(label);
      const snapshot=JSON.stringify([select.disabled,select.value,aria,[...select.options].map(o=>[o.value,o.textContent,o.disabled,o.hidden])]);
      if(snapshot===widget.snapshot)return;widget.snapshot=snapshot;
      trigger.disabled=select.disabled;
      trigger.replaceChildren();const value=document.createElement('span');value.textContent=select.selectedOptions[0]?.textContent||'';
      const caret=document.createElement('span');caret.className='select-caret';caret.textContent='⌄';trigger.append(value,caret);
      trigger.setAttribute('aria-label',aria);menu.setAttribute('aria-label',aria);
      menu.replaceChildren();choices().forEach((option,index)=>{
        const row=document.createElement('div');row.id=select.id+'-option-'+index;row.className='select-option';
        row.setAttribute('role','option');row.setAttribute('aria-selected',String(option.selected));
        const check=document.createElement('span');check.className='select-check';check.textContent=option.selected?'✓':'';
        const text=document.createElement('span');text.textContent=option.textContent;row.append(check,text);
        row.onpointermove=()=>highlight(index,false);row.onpointerdown=e=>e.preventDefault();row.onclick=()=>commit(index);
        menu.append(row);
      });
      if(opened===widget)highlight(widget.index,false);
    }
    function position(){
      const rect=trigger.getBoundingClientRect(),margin=8,width=Math.min(Math.max(rect.width,160),innerWidth-margin*2);
      const availableBelow=innerHeight-rect.bottom-margin-6,availableAbove=rect.top-margin-6;
      const below=availableBelow>=Math.min(menu.scrollHeight,240)||availableBelow>=availableAbove;
      const height=Math.max(40,Math.min(320,below?availableBelow:availableAbove));
      menu.style.width=width+'px';menu.style.maxHeight=height+'px';
      menu.style.left=Math.max(margin,Math.min(rect.left,innerWidth-width-margin))+'px';
      menu.style.top=(below?rect.bottom+6:Math.max(margin,rect.top-6-Math.min(menu.scrollHeight,height)))+'px';
      menu.dataset.side=below?'bottom':'top';
    }
    function highlight(index,scroll=true){
      widget.index=Math.max(0,Math.min(index,choices().length-1));
      [...menu.children].forEach((row,i)=>row.classList.toggle('highlighted',i===widget.index));
      const row=menu.children[widget.index];if(row){trigger.setAttribute('aria-activedescendant',row.id);if(scroll)row.scrollIntoView({block:'nearest'});}
    }
    function open(){
      if(select.disabled||!choices().length)return;if(opened===widget)return;
      close();sync();widget.index=Math.max(0,choices().findIndex(o=>o.selected));opened=widget;
      menu.showPopover();position();trigger.setAttribute('aria-expanded','true');highlight(widget.index);trigger.focus({preventScroll:true});
    }
    function commit(index){const option=choices()[index];if(!option)return;select.value=option.value;close();sync();select.dispatchEvent(new Event('change',{bubbles:true}));trigger.focus({preventScroll:true});}
    widget.sync=sync;widget.position=position;
    trigger.onclick=()=>opened===widget?close():open();
    trigger.onkeydown=e=>{
      if(['ArrowDown','ArrowUp','Home','End'].includes(e.key)){
        e.preventDefault();const wasOpen=opened===widget;open();
        if(e.key==='Home')highlight(0);else if(e.key==='End')highlight(choices().length-1);
        else if(wasOpen)highlight((widget.index+(e.key==='ArrowDown'?1:-1)+choices().length)%choices().length);
      }else if(['Enter',' '].includes(e.key)){e.preventDefault();opened===widget?commit(widget.index):open();}
      else if(e.key==='Escape'&&opened===widget){e.preventDefault();e.stopPropagation();close();}
      else if(e.key==='Tab')close();
      else if(e.key.length===1&&!e.ctrlKey&&!e.metaKey&&!e.altKey){
        open();clearTimeout(widget.searchTimer);widget.search+=e.key.toLocaleLowerCase();
        const index=choices().findIndex(o=>o.textContent.trim().toLocaleLowerCase().startsWith(widget.search));
        if(index>=0)highlight(index);widget.searchTimer=setTimeout(()=>widget.search='',600);
      }
    };
    select.addEventListener('change',sync);
    new MutationObserver(sync).observe(select,{subtree:true,childList:true,characterData:true,attributes:true});
    for(const label of select.labels||[])label.addEventListener('click',e=>{if(!trigger.contains(e.target)&&e.target!==select){e.preventDefault();trigger.focus();}});
    sync();
  }
  function close(){if(!opened)return;const {trigger,menu}=opened;menu.hidePopover();trigger.setAttribute('aria-expanded','false');trigger.removeAttribute('aria-activedescendant');opened=undefined;}
  document.addEventListener('pointerdown',e=>{if(opened&&!opened.trigger.contains(e.target)&&!opened.menu.contains(e.target))close();},true);
  document.addEventListener('close',close,true);
  addEventListener('resize',()=>opened?.position());
  document.addEventListener('scroll',e=>{if(opened&&!opened.menu.contains(e.target))opened.position();},true);
  document.addEventListener('lingshu:language',()=>{for(const widget of widgets.values())widget.sync();});
  return {init:()=>document.querySelectorAll('select').forEach(enhance),sync:()=>{for(const widget of widgets.values())widget.sync();},close};
})();
