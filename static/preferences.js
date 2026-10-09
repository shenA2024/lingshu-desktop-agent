/* Browser-local presentation preferences. No credentials or engine configuration. */
"use strict";
window.LingshuPreferences = (() => {
  const key = 'lingshu-ui-v1';
  const defaults = Object.freeze({
    fontSize: '14', language: 'zh-CN', theme: 'light', background: 'clean', style: 'radar', motion: true, whale: true,
    grid: false, trails: true, predictions: true, sidebar: false,
    replay: false, autoMemory: true,
    results: true, events: true, memory: true, connections: true, graph: true
  });
  const choices = {fontSize: Array.from({length:9},(_,i)=>String(i+12)), language: ['zh-CN','en'], theme: ['light', 'dark', 'warm', 'system'], background: ['clean', 'warm', 'ocean'], style: ['radar', 'whale']};
  let prefs = {...defaults}, onChange = () => {};
  try {
    const saved = JSON.parse(localStorage.getItem(key));
    if (saved && typeof saved === 'object' && saved.version === 1) {
      for (const name of Object.keys(defaults)) {
        const value = saved[name];
        if (choices[name] ? choices[name].includes(value) : typeof value === 'boolean') prefs[name] = value;
      }
    } else {
      for (const name of ['sidebar', 'replay']) prefs[name] = localStorage.getItem('lingshu-layout-' + name) === 'true';
    }
  } catch { /* Storage may be unavailable. Defaults remain usable. */ }
  const darkQuery = matchMedia('(prefers-color-scheme: dark)');
  const reducedQuery = matchMedia('(prefers-reduced-motion: reduce)');
  function applyAppearance() {
    document.documentElement.style.setProperty('--ui-scale',String(Number(prefs.fontSize)/14));
    if(document.documentElement.lang!==prefs.language){document.documentElement.lang=prefs.language;window.LingshuI18n?.apply();}
    document.documentElement.dataset.theme = prefs.theme === 'system' ? (darkQuery.matches ? 'dark' : 'light') : prefs.theme;
    document.documentElement.dataset.background = prefs.background;
    document.documentElement.dataset.sceneStyle = prefs.style;
    document.documentElement.dataset.motion = prefs.motion && !reducedQuery.matches ? 'on' : 'off';
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = document.documentElement.dataset.theme === 'dark' ? '#171a20' : document.documentElement.dataset.theme === 'warm' ? '#fbf9f5' : '#ffffff';
  }
  function syncControls() {
    document.querySelectorAll('[data-theme-choice]').forEach(button => {
      button.setAttribute('aria-pressed', String(button.dataset.themeChoice === prefs.theme));
    });
    document.querySelectorAll('[data-preference]').forEach(control => {
      const value = prefs[control.dataset.preference];
      if (control.type === 'checkbox') control.checked = value;
      else control.value = value;
    });
    const fontOutput=document.getElementById('setting-font-output');if(fontOutput)fontOutput.value=prefs.fontSize+' px';
    const whaleToggle = document.querySelector('[data-preference="whale"]');
    if (whaleToggle) whaleToggle.disabled = prefs.style !== 'whale';
    const note = document.getElementById('motion-note');
    if (note) note.textContent = reducedQuery.matches ? tr('系统已启用减少动态效果，当前以静态方式显示。') : tr('实时运行时平滑移动；回看与外部扰动直接显示观测位置。');
  }
  function save() {
    try { localStorage.setItem(key, JSON.stringify({version: 1, ...prefs})); } catch { /* Keep the current session usable. */ }
  }
  function set(name, value) {
    if (!(name in defaults) || !(choices[name] ? choices[name].includes(value) : typeof value === 'boolean')) return;
    if(prefs[name]===value)return;
    prefs[name] = value;
    save(); applyAppearance(); syncControls(); onChange(name);
    window.LingshuSelect?.sync();if(name==='language')document.dispatchEvent(new CustomEvent('lingshu:language'));
  }
  function selectTab(name) {
    document.querySelectorAll('[data-settings-tab]').forEach(tab => {
      const active = tab.dataset.settingsTab === name;
      tab.setAttribute('aria-selected', String(active));
      tab.tabIndex = active ? 0 : -1;
    });
    document.querySelectorAll('[data-settings-panel]').forEach(panel => panel.hidden = panel.dataset.settingsPanel !== name);
  }
  function bind(callback) {
    onChange = callback;
    document.querySelectorAll('[data-theme-choice]').forEach(button => {
      button.onclick = () => set('theme', button.dataset.themeChoice);
    });
    document.querySelectorAll('[data-preference]').forEach(control => {
      control.onchange = () => set(control.dataset.preference, control.type === 'checkbox' ? control.checked : control.value);
      if(control.type==='range')control.oninput=control.onchange;
    });
    const tabs = [...document.querySelectorAll('[data-settings-tab]')];
    const compactQuery = matchMedia('(max-width: 760px)');
    const orientTabs = () => document.querySelector('.settings-tabs').setAttribute('aria-orientation', compactQuery.matches ? 'horizontal' : 'vertical');
    compactQuery.addEventListener('change', orientTabs);
    orientTabs();
    tabs.forEach((tab, index) => {
      tab.onclick = () => selectTab(tab.dataset.settingsTab);
      tab.onkeydown = event => {
        let next;
        if (event.key === 'ArrowRight' || event.key === 'ArrowDown') next = (index + 1) % tabs.length;
        if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') next = (index + tabs.length - 1) % tabs.length;
        if (event.key === 'Home') next = 0;
        if (event.key === 'End') next = tabs.length - 1;
        if (next !== undefined) { event.preventDefault(); selectTab(tabs[next].dataset.settingsTab); tabs[next].focus(); }
      };
    });
    document.getElementById('reset-layout').onclick = () => {
      prefs = {...defaults}; save(); applyAppearance(); syncControls(); onChange('reset');document.dispatchEvent(new CustomEvent('lingshu:language'));window.LingshuSelect?.sync();
    };
    syncControls(); onChange('init');
  }
  function mediaChanged() { applyAppearance(); syncControls(); onChange('media'); }
  darkQuery.addEventListener('change', mediaChanged);
  reducedQuery.addEventListener('change', mediaChanged);
  applyAppearance();
  return {get: name => prefs[name], set, bind, motionEnabled: () => prefs.motion && !reducedQuery.matches};
})();
