/* Explicit UI-only translations. Messages, notes, tool payloads and code are data. */
'use strict';
window.LingshuI18n = (() => {
  let dictionary={},captured=false;
  const texts=[],attributes=[];
  const isEnglish=()=>document.documentElement.lang==='en';
  function translate(value){
    const text=String(value??'');if(!isEnglish())return text;
    if(Object.hasOwn(dictionary,text))return dictionary[text];
    return text.replace(/[^<>"'{}\n]+/g,part=>{
      const key=part.trim();return Object.hasOwn(dictionary,key)?part.replace(key,dictionary[key]):part;
    });
  }
  function capture(root){
    if(captured)return;captured=true;
    const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
    while(walker.nextNode()){
      const node=walker.currentNode;
      if(/[\u3400-\u9fff]/.test(node.nodeValue)&&!node.parentElement?.closest('script,style,pre,code,textarea,[data-no-i18n]'))texts.push({node,source:node.nodeValue});
    }
    root.querySelectorAll('*').forEach(node=>{for(const key of ['title','placeholder','aria-label','data-prompt']){
      const source=node.getAttribute(key);if(source&&/[\u3400-\u9fff]/.test(source))attributes.push({node,key,source,previous:source});
    }});
  }
  function apply(){
    for(const item of texts)if(item.node.isConnected){const next=translate(item.source);if(item.node.nodeValue!==next)item.node.nodeValue=next;}
    for(const item of attributes)if(item.node.isConnected&&item.node.getAttribute(item.key)===item.previous){
      item.previous=translate(item.source);item.node.setAttribute(item.key,item.previous);
    }
    document.querySelectorAll('a[href*="-help.html"],a[href*="metric-notes.html"]').forEach(a=>{const url=new URL(a.href);url.searchParams.set('lang',isEnglish()?'en':'zh-CN');a.href=url.href;});
  }
  function install(values){dictionary=values;}
  return {translate,capture,apply,install};
})();
function tr(value){return LingshuI18n.translate(value);}
function localizeMap(value){return new Proxy(value,{get(target,key){return typeof target[key]==='string'?tr(target[key]):target[key];}});}
