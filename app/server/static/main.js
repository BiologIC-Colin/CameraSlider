(() => {
  const $ = (sel) => document.querySelector(sel);

  // State
  let profile = {
    length_mm: 1200,
    keyframes: [
      { t: 0.0, pos_mm: 0.0, ease: { type: 'linear' } },
      { t: 4.0, pos_mm: 400.0, ease: { type: 'cubic-bezier', p: [0.25, 0.1, 0.25, 1.0] } },
      { t: 7.0, pos_mm: 1200.0, ease: { type: 'linear' } }
    ],
    max_speed_mm_s: 120,
    max_accel_mm_s2: 300
  };

  // UI Elements
  const lengthMmEl = $('#lengthMm');
  const maxSpeedEl = $('#maxSpeed');
  const maxAccelEl = $('#maxAccel');
  const kfBody = $('#kfBody');
  const presetSelect = $('#presetSelect');
  const primeBtn = document.getElementById('primeBtn');
  const primePresetBtn = document.getElementById('primePresetBtn');

  // Status
  const stState = $('#stState');
  const stPos = $('#stPos');
  const stHomed = $('#stHomed');
  const stProg = $('#stProg');

  // Chart
  const ctx = document.getElementById('chart').getContext('2d');
  const chart = new Chart(ctx, {
    type: 'line',
    data: { datasets: [{ label: 'pos (mm)', data: [], borderColor: '#9bb4ff', pointRadius: 0 } ] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      parsing: false, // we will feed {x,y}
      scales: {
        x: {
          type: 'linear',
          title: { display: true, text: 't (s)' },
          ticks: {
            stepSize: 1,
            callback: (v) => Number(v).toFixed(0)
          },
          suggestedMin: 0
        },
        y: { title: { display: true, text: 'pos (mm)' } }
      }
    }
  });

  // Easing
  const linear = (u) => u <= 0 ? 0 : (u >= 1 ? 1 : u);
  function cubicBezier(x1, y1, x2, y2) {
    function bx(t){ const mt=1-t; return 3*mt*mt*t*x1 + 3*mt*t*t*x2 + t**3; }
    function by(t){ const mt=1-t; return 3*mt*mt*t*y1 + 3*mt*t*t*y2 + t**3; }
    function dx(t){ return 3*(1-t)*(1-t)*x1 + 6*(1-t)*t*(x2-x1) + 3*t*t*(1-x2); }
    return function(u){
      if (u<=0) return 0; if (u>=1) return 1;
      let t=u;
      for(let i=0;i<6;i++){ const x=bx(t), d=dx(t); if(Math.abs(d)<1e-6) break; t-= (x-u)/d; if(t<0){t=0;break;} if(t>1){t=1;break;} }
      let x=bx(t);
      if (Math.abs(x-u)>1e-4){ let lo=0, hi=1; t=u; for(let i=0;i<12;i++){ x=bx(t); if(x<u) lo=t; else hi=t; t=(lo+hi)/2; if(Math.abs(x-u)<=1e-5) break; } }
      return by(t);
    }
  }

  function easeFn(kf){
    const e = kf.ease||{type:'linear'};
    if(e.type==='linear') return linear;
    if(e.type==='cubic-bezier' && e.p && e.p.length===4){ return cubicBezier(e.p[0], e.p[1], e.p[2], e.p[3]); }
    return linear;
  }

  function sampleProfile(p, dt=0.02) {
    const kfs = [...p.keyframes].sort((a,b)=>a.t-b.t);
    const totalT = kfs[kfs.length-1].t;
    const times=[], pos=[];
    let seg=0; let t=0;
    while(t<=totalT+1e-9){
      while(seg < kfs.length-2 && t > kfs[seg+1].t) seg++;
      const k0=kfs[seg], k1=kfs[seg+1];
      const u = k1.t===k0.t ? 0 : Math.max(0, Math.min(1, (t-k0.t)/(k1.t-k0.t)));
      const f = easeFn(k1);
      const y = k0.pos_mm + (k1.pos_mm - k0.pos_mm) * f(u);
      times.push(t);
      pos.push(y);
      t += dt;
    }
    if (times[times.length-1] < totalT){ times.push(totalT); pos.push(kfs[kfs.length-1].pos_mm); }
    return {times, pos};
  }

  function renderKeyframes() {
    // Sync top fields
    profile.length_mm = parseFloat(lengthMmEl.value);
    profile.max_speed_mm_s = parseFloat(maxSpeedEl.value);
    profile.max_accel_mm_s2 = parseFloat(maxAccelEl.value);

    // Table
    profile.keyframes.sort((a,b)=>a.t-b.t);
    kfBody.innerHTML = '';
    profile.keyframes.forEach((kf, idx)=>{
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><input type="number" step="0.1" value="${kf.t}" data-field="t" data-idx="${idx}"/></td>
        <td><input type="number" step="1" value="${kf.pos_mm}" data-field="pos_mm" data-idx="${idx}"/></td>
        <td>
          <select data-field="ease.type" data-idx="${idx}">
            <option value="linear" ${kf.ease?.type==='linear'?'selected':''}>linear</option>
            <option value="cubic-bezier" ${kf.ease?.type==='cubic-bezier'?'selected':''}>cubic-bezier</option>
          </select>
        </td>
        <td>
          <div class="row" style="gap:6px;">
            <input style="flex:1" type="text" placeholder="x1,y1,x2,y2" value="${(kf.ease?.p||[]).join(',')}" data-field="ease.p" data-idx="${idx}"/>
            <button class="secondary" data-action="edit-bezier" data-idx="${idx}">Edit…</button>
          </div>
        </td>
        <td><button data-action="del" data-idx="${idx}">✕</button></td>
      `;
      kfBody.appendChild(tr);
    });

    // Wire inputs
    kfBody.querySelectorAll('input,select,button').forEach(el=>{
      const idx = parseInt(el.getAttribute('data-idx'));
      const field = el.getAttribute('data-field');
      const action = el.getAttribute('data-action');
      if(action==='del'){
        el.addEventListener('click', ()=>{ profile.keyframes.splice(idx,1); renderKeyframes(); updateChart(); });
      } else if(action==='edit-bezier'){
        el.addEventListener('click', ()=> openBezierEditor(idx));
      } else {
        el.addEventListener('change', ()=>{
          if(field==='t') profile.keyframes[idx].t = parseFloat(el.value);
          else if(field==='pos_mm') profile.keyframes[idx].pos_mm = parseFloat(el.value);
          else if(field==='ease.type') profile.keyframes[idx].ease = { type: el.value, p: profile.keyframes[idx].ease?.p };
          else if(field==='ease.p'){
            const arr = el.value.split(',').map(s=>parseFloat(s.trim())).filter(v=>!Number.isNaN(v));
            profile.keyframes[idx].ease = { type: 'cubic-bezier', p: arr };
          }
          renderKeyframes();
          updateChart();
        });
      }
    });
  }

  function updateChart(){
    try{
      const {times, pos} = sampleProfile(profile, 0.02);
      chart.data.datasets[0].data = times.map((t,i)=>({x: t, y: pos[i]}));
      chart.update();
    } catch(e){ console.error(e); }
  }

  // Bezier editor modal
  let bezierModal, bezierSvg, bezPath, h1, h2, bezReadout, applyBtn, cancelBtn, resetBtn;
  let currentEditIdx = null;
  let dragTarget = null;

  function clamp01(v){ return Math.max(0, Math.min(1, v)); }

  function svgMap(x, y){
    // map [0,1]x[0,1] to SVG coords (padding 20, box 280), y inverted
    const pad=20, size=280;
    const sx = pad + clamp01(x)*size;
    const sy = pad + (1-clamp01(y))*size;
    return [sx, sy];
  }

  function svgUnmap(sx, sy){
    const pad=20, size=280;
    const x = clamp01((sx - pad)/size);
    const y = clamp01(1 - (sy - pad)/size);
    return [x, y];
  }

  function getCurrentBez(){
    const kf = profile.keyframes[currentEditIdx];
    let p = (kf.ease && kf.ease.p && kf.ease.p.length===4) ? kf.ease.p.slice(0,4) : [0.25,0.1,0.25,1.0];
    // ensure numbers and clamped
    p = [clamp01(+p[0]||0.25), clamp01(+p[1]||0.1), clamp01(+p[2]||0.25), clamp01(+p[3]||1.0)];
    return p;
  }

  function setHandlesFromP(p){
    const [x1,y1,x2,y2] = p;
    const [h1x,h1y] = svgMap(x1,y1);
    const [h2x,h2y] = svgMap(x2,y2);
    h1.setAttribute('cx', h1x); h1.setAttribute('cy', h1y);
    h2.setAttribute('cx', h2x); h2.setAttribute('cy', h2y);
    updateCurvePath();
  }

  function updateCurvePath(){
    const [x1,y1] = svgUnmap(parseFloat(h1.getAttribute('cx')), parseFloat(h1.getAttribute('cy')));
    const [x2,y2] = svgUnmap(parseFloat(h2.getAttribute('cx')), parseFloat(h2.getAttribute('cy')));
    const [sx,sy] = svgMap(0,0);
    const [ex,ey] = svgMap(1,1);
    const [c1x,c1y] = svgMap(x1,y1);
    const [c2x,c2y] = svgMap(x2,y2);
    bezPath.setAttribute('d', `M ${sx} ${sy} C ${c1x} ${c1y}, ${c2x} ${c2y}, ${ex} ${ey}`);
    bezReadout.textContent = `[${x1.toFixed(2)}, ${y1.toFixed(2)}, ${x2.toFixed(2)}, ${y2.toFixed(2)}]`;
  }

  function openBezierEditor(idx){
    currentEditIdx = idx;
    if(!bezierModal){
      // Cache dom refs
      bezierModal = document.getElementById('bezierModal');
      bezierSvg = document.getElementById('bezierSvg');
      bezPath = document.getElementById('bezPath');
      h1 = document.getElementById('handle1');
      h2 = document.getElementById('handle2');
      bezReadout = document.getElementById('bezReadout');
      applyBtn = document.getElementById('bezApply');
      cancelBtn = document.getElementById('bezCancel');
      resetBtn = document.getElementById('bezReset');

      // Dragging
      function onDown(e){
        const tgt = e.target;
        if(tgt===h1 || tgt===h2){ dragTarget = tgt; }
      }
      function onMove(e){
        if(!dragTarget) return;
        const pt = bezierSvg.createSVGPoint();
        pt.x = e.clientX; pt.y = e.clientY;
        const svgPt = pt.matrixTransform(bezierSvg.getScreenCTM().inverse());
        // Clamp within box (20..300)
        const x = Math.max(20, Math.min(300, svgPt.x));
        const y = Math.max(20, Math.min(300, svgPt.y));
        dragTarget.setAttribute('cx', x);
        dragTarget.setAttribute('cy', y);
        updateCurvePath();
      }
      function onUp(){ dragTarget = null; }
      bezierSvg.addEventListener('mousedown', onDown);
      window.addEventListener('mousemove', onMove);
      window.addEventListener('mouseup', onUp);

      cancelBtn.addEventListener('click', ()=>{ bezierModal.classList.add('hidden'); });
      resetBtn.addEventListener('click', ()=>{ setHandlesFromP([0.25,0.1,0.25,1.0]); });
      applyBtn.addEventListener('click', ()=>{
        const [x1,y1] = svgUnmap(parseFloat(h1.getAttribute('cx')), parseFloat(h1.getAttribute('cy')));
        const [x2,y2] = svgUnmap(parseFloat(h2.getAttribute('cx')), parseFloat(h2.getAttribute('cy')));
        profile.keyframes[currentEditIdx].ease = { type: 'cubic-bezier', p: [x1,y1,x2,y2] };
        renderKeyframes();
        updateChart();
        bezierModal.classList.add('hidden');
      });
    }

    // Init handles from keyframe
    const p = getCurrentBez();
    setHandlesFromP(p);
    bezierModal.classList.remove('hidden');
  }

  // Presets
  async function loadPresets(){
    const res = await fetch('/api/presets');
    const data = await res.json();
    presetSelect.innerHTML = '';
    Object.keys(data).sort().forEach(name=>{
      const opt = document.createElement('option');
      opt.value=name; opt.textContent=name; presetSelect.appendChild(opt);
    });
  }

  // Controls
  $('#homeBtn').addEventListener('click', ()=> fetch('/api/home', {method:'POST'}));
  $('#stopBtn').addEventListener('click', ()=> fetch('/api/stop', {method:'POST'}));
  $('#jogPos').addEventListener('click', ()=>{
    const d = parseFloat($('#jogDist').value)||0; const s = parseFloat($('#jogSpeed').value)||50;
    fetch('/api/jog', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({distance_mm:d, speed_mm_s:s})});
  });
  $('#jogNeg').addEventListener('click', ()=>{
    const d = parseFloat($('#jogDist').value)||0; const s = parseFloat($('#jogSpeed').value)||50;
    fetch('/api/jog', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({distance_mm:-d, speed_mm_s:s})});
  });

  // Profile fields
  lengthMmEl.addEventListener('change', ()=>{ profile.length_mm = parseFloat(lengthMmEl.value); updateChart(); });
  maxSpeedEl.addEventListener('change', ()=>{ profile.max_speed_mm_s = parseFloat(maxSpeedEl.value); });
  maxAccelEl.addEventListener('change', ()=>{ profile.max_accel_mm_s2 = parseFloat(maxAccelEl.value); });

  $('#addKfBtn').addEventListener('click', ()=>{
    const t = profile.keyframes.length ? profile.keyframes[profile.keyframes.length-1].t+1 : 0;
    const pos = profile.keyframes.length ? profile.keyframes[profile.keyframes.length-1].pos_mm : 0;
    profile.keyframes.push({ t, pos_mm: pos, ease: { type: 'linear' } });
    renderKeyframes(); updateChart();
  });

  primeBtn.addEventListener('click', ()=>{
    fetch('/api/prime', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(profile) });
  });

  $('#runBtn').addEventListener('click', ()=>{
    fetch('/api/run', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(profile) });
  });

  $('#savePresetBtn').addEventListener('click', async ()=>{
    const name = $('#presetName').value.trim(); if(!name){ alert('Enter a preset name'); return; }
    const res = await fetch(`/api/presets/${encodeURIComponent(name)}`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(profile) });
    if(res.ok){ await loadPresets(); presetSelect.value = name; }
  });
  primePresetBtn.addEventListener('click', ()=>{
    const name = presetSelect.value; if(!name) return; fetch(`/api/prime_preset/${encodeURIComponent(name)}`);
  });

  $('#runPresetBtn').addEventListener('click', ()=>{
    const name = presetSelect.value; if(!name) return; fetch(`/api/run_preset/${encodeURIComponent(name)}`);
  });
  $('#deletePresetBtn').addEventListener('click', async ()=>{
    const name = presetSelect.value; if(!name) return; await fetch(`/api/presets/${encodeURIComponent(name)}`, {method:'DELETE'}); await loadPresets();
  });

  // Status poll
  async function poll(){
    try{
      const res = await fetch('/api/status');
      const s = await res.json();
      stState.textContent = s.status; stPos.textContent = s.pos_mm?.toFixed?.(2) ?? s.pos_mm; stHomed.textContent = s.homed ? 'yes' : 'no'; stProg.textContent = ((s.progress||0)*100).toFixed(0)+'%';
    }catch(e){ /* ignore */ }
    setTimeout(poll, 1000);
  }

  // Init
  (function init(){
    lengthMmEl.value = profile.length_mm;
    maxSpeedEl.value = profile.max_speed_mm_s;
    maxAccelEl.value = profile.max_accel_mm_s2;
    renderKeyframes();
    updateChart();
    loadPresets();
    poll();
  })();
})();
