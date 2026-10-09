/* Original SVG scene presentation; frame data remains the engine's observation. */
"use strict";
window.LingshuScene = (() => {
  let cache = null;
  const color = index => `var(--entity-${index % 4 + 1})`;
  const escapeText = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  function whale() {
    return `<g class="whale-body"><path class="whale-tail" d="M-23 1C-31-2-34-10-40-10C-42-3-37 3-30 5C-36 9-37 16-33 18C-26 17-22 10-21 5Z" fill="var(--whale-tail)"/>
      <path d="M-27 1C-25-19-1-24 17-15C31-8 35 11 21 19C6 29-23 20-27 1Z" fill="var(--whale-body)"/>
      <path d="M-24 7C-11 14 14 16 28 5C31 14 24 21 9 23C-8 24-20 18-24 7Z" fill="var(--whale-belly)"/>
      <path class="whale-fin" d="M-3 4C0 10 6 17 15 13C11 8 6 4 1 2Z" fill="var(--whale-tail)"/>
      <path d="M-12-14C-3-18 7-17 13-14" fill="none" stroke="var(--whale-highlight)" stroke-width="2.5" stroke-linecap="round"/>
      <circle class="whale-eye" cx="18" cy="-2" r="2.3" fill="var(--whale-eye)"/><circle cx="18.6" cy="-2.7" r=".7" fill="var(--paper)"/>
      <path d="M23 7Q26 8 28 5" fill="none" stroke="var(--whale-eye)" stroke-width="1.3" stroke-linecap="round"/>
      <ellipse cx="22" cy="3" rx="3" ry="1.5" fill="var(--whale-cheek)" fill-opacity=".55"/></g>`;
  }
  function ocean(width, height) {
    return `<g class="ocean-decor" aria-hidden="true"><path d="M0 ${height*.65}Q${width*.25} ${height*.57} ${width*.5} ${height*.65}T${width} ${height*.65}V${height}H0Z" fill="var(--ocean-wash)"/>
      <g class="ocean-wave"><path d="M-40 ${height*.79}Q${width*.2} ${height*.71} ${width*.48} ${height*.79}T${width+80} ${height*.79}" fill="none" stroke="var(--ocean-line)" stroke-width="1"/>
      <path d="M-50 ${height*.86}Q${width*.18} ${height*.91} ${width*.5} ${height*.86}T${width+100} ${height*.86}" fill="none" stroke="var(--ocean-line)" stroke-width="1"/></g>
      <circle cx="${width*.16}" cy="${height*.27}" r="3" fill="none" stroke="var(--ocean-line)"/><circle cx="${width*.81}" cy="${height*.32}" r="5" fill="none" stroke="var(--ocean-line)"/>
      <circle cx="${width*.85}" cy="${height*.24}" r="2" fill="var(--ocean-line)"/></g>`;
  }
  function radar(point, unitX, unitY) {
    const [cx,cy]=point([12,0,12]);
    let rings='',spokes='',ticks='';
    for(const radius of [4,8,12]) rings+=`<ellipse cx="${cx}" cy="${cy}" rx="${radius*Math.SQRT2*unitX}" ry="${radius*Math.SQRT2*unitY}" fill="none" stroke="var(--radar-line)" stroke-opacity="${radius===12?.7:.45}" stroke-width="${radius===12?1:.7}"/>`;
    for(let angle=0;angle<Math.PI*2;angle+=Math.PI/4){const [x,y]=point([12+Math.cos(angle)*12,0,12+Math.sin(angle)*12]);spokes+=`<path d="M${cx} ${cy}L${x} ${y}" stroke="var(--radar-grid)" stroke-width=".7"/>`;}
    for(let i=0;i<48;i++){const a=i*Math.PI/24,inner=i%4===0?11.6:11.8;const p=point([12+Math.cos(a)*inner,0,12+Math.sin(a)*inner]),q=point([12+Math.cos(a)*12,0,12+Math.sin(a)*12]);ticks+=`<path d="M${p.join(' ')}L${q.join(' ')}" stroke="var(--radar-line)" stroke-opacity=".6" stroke-width=".8"/>`;}
    return `<g class="scene-radar-grid" aria-hidden="true">${rings}${spokes}${ticks}<g transform="matrix(${unitX} ${unitY} ${-unitX} ${unitY} ${cx} ${cy})"><g class="radar-sweep" style="transform-origin:0px 0px;transform-box:view-box;--motion-phase:-${Math.round(performance.now()%24000)}ms"><path d="M0 0L12 0A12 12 0 0 0 10.392-6Z" fill="var(--radar-scan)" fill-opacity=".045"/><path d="M0 0L12 0" stroke="var(--radar-scan)" stroke-opacity=".4" stroke-width=".06"/></g></g><path d="M${cx-4} ${cy}h8M${cx} ${cy-4}v8" stroke="var(--radar-line)" stroke-width=".8"/></g>`;
  }
  function draw({container, frame, frames, frameIndex, runId, scenario, entity, settings, attach}) {
    const width = Math.max(220, container.clientWidth), height = container.clientHeight || 350;
    const identity = `${runId || 'preview'}|${scenario}`;
    const fingerprint = JSON.stringify([identity, frame.tick, frameIndex, width, height, entity, ...['style','background','whale','motion','grid','trails','predictions'].map(k => settings.get(k)), document.documentElement.dataset.theme, document.documentElement.dataset.motion]);
    if (cache?.fingerprint === fingerprint && container.querySelector('.scene-svg')) return;
    const previous = cache, entries = Object.entries(frame.scene.entities), compact = width < 500;
    const spanX = Math.min(width - (compact ? 36 : 110), 760, (height - 74) / .33);
    const spanY = Math.min(height - 74, spanX * .43);
    const unitX = spanX / 48, unitY = spanY / 48;
    const originY = (height - spanY) / 2 + 8;
    const point = pos => [width/2 + (pos[0]-pos[2])*unitX, originY + (pos[0]+pos[2])*unitY];
    const corners = [[0,0,0],[24,0,0],[24,0,24],[0,0,24]].map(point);
    const polygon = corners.map(p => p.join(',')).join(' ');
    const side = corners.slice(1).map(p => p.join(',')).join(' ') + ` ${corners[3][0]},${corners[3][1]+3} ${corners[2][0]},${corners[2][1]+3} ${corners[1][0]},${corners[1][1]+3}`;
    let grid = '', traces = '', halos = '', actors = '', labels = '';
    const placed = [], positions = {};
    if (settings.get('grid')) for (let i=0; i<=24; i+=2) {
      const a=point([i,0,0]), b=point([i,0,24]), c=point([0,0,i]), d=point([24,0,i]);
      grid += `<path d="M${a.join(' ')}L${b.join(' ')}M${c.join(' ')}L${d.join(' ')}" stroke="var(--scene-grid)" stroke-width="${i%8===0?1:.6}"/>`;
    }
    entries.forEach(([id,e],index) => {
      const hue = color(index), [x,y] = point(e.pos), verification = frame.verification?.details.find(d => d.entity===id);
      positions[id] = {x, y, pos: [...e.pos]};
      const upto = frameIndex === null ? frames.length : frameIndex + 1;
      const history = frames.slice(Math.max(0,upto-40),upto).map(f => f.scene.entities[id]?.pos).filter(Boolean);
      if (settings.get('trails')) {
        let path='', prior;
        for (const pos of history) {
          const [px,py]=point(pos);
          if (prior && Math.hypot(pos[0]-prior[0],pos[2]-prior[2])>2) {
            const [ox,oy]=point(prior);
            traces+=`<path d="M${ox} ${oy}L${px} ${py}" fill="none" stroke="${hue}" stroke-dasharray="3 5" opacity=".4"/>`;
            path+=`M${px} ${py}`;
          } else path+=`${prior?'L':'M'}${px} ${py}`;
          prior=pos;
        }
        if (path) traces+=`<path d="${path}" fill="none" stroke="${hue}" stroke-width="1.6" stroke-linejoin="round" opacity=".55"/>`;
      }
      if (verification && settings.get('predictions')) {
        const [px,py]=point(verification.predicted), failed=verification.hit===false;
        const stroke=failed?'var(--warning)':hue;
        halos+=`<ellipse cx="${px}" cy="${py}" rx="${Math.max(1,verification.bound*unitX*Math.SQRT2)}" ry="${Math.max(1,verification.bound*unitY*Math.SQRT2)}" fill="${stroke}" fill-opacity=".07" stroke="${stroke}" stroke-dasharray="3 4" stroke-opacity=".65"/><path d="M${px-3} ${py}h6M${px} ${py-3}v6" stroke="${stroke}"/>`;
        if (failed && verification.distance!==null) {
          const mx=(px+x)/2,my=(py+y)/2;
          halos+=`<path d="M${px} ${py}L${x} ${y}" stroke="var(--warning)" stroke-dasharray="4 4"/><rect x="${mx-37}" y="${my-24}" width="74" height="19" rx="4" fill="var(--warning-soft)"/><text x="${mx}" y="${my-11}" text-anchor="middle" fill="var(--warning)" font-size="11">误差 ${verification.distance.toFixed(2)}</text>`;
        }
      }
      const isWhale=settings.get('style')==='whale' && settings.get('whale') && index===0;
      const selected=entity===id, scale=compact?.7:.95;
      const radius=isWhale?(compact?28:36):18;
      const marker=index===0?'<path d="M0-10L9 5L0 11L-9 5Z"/>':index===1?'<rect x="-8" y="-8" width="16" height="16" rx="2"/>':'<circle r="9"/>';
      actors+=`<g class="entity-target scene-actor" data-entity="${escapeText(id)}" data-actor="${escapeText(id)}" transform="translate(${x} ${y})" tabindex="0" role="button" aria-label="查看${escapeText(e.category)}" style="--motion-phase:-${Math.round(performance.now()%5000)}ms"><circle r="${radius}" fill="${hue}" fill-opacity="${selected?.12:.035}" stroke="${hue}" stroke-opacity="${selected?.6:0}" stroke-width="1.2"/>${isWhale?`<g transform="scale(${scale})">${whale()}</g>`:`<ellipse cy="9" rx="13" ry="4" fill="${hue}" opacity=".09"/><g fill="var(--paper)" stroke="${hue}" stroke-width="1.3">${marker}</g><circle r="3.2" fill="${hue}"/>`}</g>`;
      // The exact observed point is distinct from any animated illustration.
      actors+=`<circle class="observation-point" cx="${x}" cy="${y}" r="2.6" fill="${hue}" stroke="var(--paper)" stroke-width="1" pointer-events="none"/>`;
      const labelWidth=e.category.length*12+18;
      const lx=Math.max(5,Math.min(width-labelWidth-5,x-labelWidth/2));
      let ly=Math.max(5,y-(isWhale?(compact?40:48):33));
      for (const offset of [0,-26,54,-52,80]) {
        const candidate=Math.max(5,Math.min(height-27,ly+offset));
        if (!placed.some(p=>lx<p.x+p.width+5&&lx+labelWidth+5>p.x&&candidate<p.y+25&&candidate+25>p.y)) {ly=candidate;break;}
      }
      placed.push({x:lx,y:ly,width:labelWidth});
      labels+=`<g pointer-events="none"><rect x="${lx}" y="${ly}" width="${labelWidth}" height="22" rx="4" fill="var(--paper)" fill-opacity=".94"/><text x="${lx+labelWidth/2}" y="${ly+15}" fill="var(--ink)" font-size="12" text-anchor="middle">${escapeText(e.category)}</text></g>`;
    });
    const water=settings.get('background')==='ocean';
    container.innerHTML=`<svg class="scene-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="场景实体：${settings.get('style')==='radar'?'雷达沙盘':'鲸鱼演示'}随观测位置更新，圆点为准确观测位置"><rect width="${width}" height="${height}" fill="var(--scene-bg)"/>${water?ocean(width,height):''}<g aria-hidden="true" fill="var(--muted)" font-family="Consolas,monospace" font-size="9" letter-spacing="1"><text x="24" y="26">OBSERVATION / ${frameIndex===null?'LIVE':'REPLAY'}</text><text x="${width-24}" y="26" text-anchor="end">24 × 24 · XZ</text></g><polygon points="${side}" fill="var(--scene-side)"/><polygon points="${polygon}" fill="var(--scene-plane)" stroke="var(--scene-edge)" stroke-width=".7" stroke-linejoin="round"/>${settings.get('style')==='radar'?radar(point,unitX,unitY):''}${grid}${traces}${halos}${actors}${labels}${settings.get('grid')?`<text x="${corners[1][0]-4}" y="${corners[1][1]-10}" fill="var(--muted)" font-size="10" text-anchor="end">X</text><text x="${corners[3][0]+4}" y="${corners[3][1]-10}" fill="var(--muted)" font-size="10">Z</text>`:''}</svg>`;
    if (settings.motionEnabled() && !document.hidden && frameIndex===null && previous?.identity===identity && previous.tick+1===frame.tick && previous.width===width && previous.height===height && previous.live) {
      container.querySelectorAll('[data-actor]').forEach(actor => {
        const id=actor.dataset.actor, before=previous.positions[id], after=positions[id];
        if (!before || !after || Math.hypot(before.pos[0]-after.pos[0],before.pos[2]-after.pos[2])>2) return;
        actor.animate([{transform:`translate(${before.x}px, ${before.y}px)`},{transform:`translate(${after.x}px, ${after.y}px)`}],{duration:240,easing:'ease-out'});
        actor.dataset.interpolated='true';
      });
    }
    cache={fingerprint, identity, tick:frame.tick, width, height, positions, live:frameIndex===null};
    attach();
  }
  function reset() { cache=null; }
  return {draw, reset};
})();
