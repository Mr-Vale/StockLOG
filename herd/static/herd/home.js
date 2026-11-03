/* Context changes hide old farm data immediately; the server owns the pause deadline. */
(() => {
  const form = document.querySelector('#property-selection');
  if (!form) return;
  const properties = JSON.parse(document.querySelector('#property-data').textContent);
  const property = form.elements.property, pic = form.elements.pic;
  const data = document.querySelector('#farm-data'), switching = document.querySelector('#switching');
  const status = document.querySelector('#selection-status');
  const addPic = document.querySelector('#add-pic');
  let sequence = 0, timer;
  function fillPics(selected = '') {
    const chosen = properties.find(p => String(p.id) === property.value);
    pic.replaceChildren(new Option('Select PIC', ''));
    for (const p of chosen?.pics || []) pic.add(new Option(p.number, p.id));
    pic.disabled = !chosen; pic.value = selected;
    if (addPic) { addPic.hidden = !chosen; addPic.href = '/pics/add/?property=' + (chosen?.id || ''); }
  }
  function hideData() { sequence++; clearTimeout(timer); data.hidden = true; switching.hidden = true; }
  async function choose(save = false) {
    hideData();
    if (!property.value || !pic.value) { status.textContent = 'Select both a property and PIC.'; return; }
    const own = sequence;
    switching.hidden = false;
    const destination = properties.find(p => String(p.id) === property.value);
    document.querySelector('#switch-destination').textContent = `${destination.name} · PIC ${pic.selectedOptions[0].textContent}`;
    const body = new FormData(form); body.set('save', save ? '1' : '0');
    // Disable selectors until the session write completes; this prevents reordered selection requests.
    property.disabled = pic.disabled = form.querySelector('button').disabled = true;
    try {
      const response = await fetch(form.action, {method:'POST', body, credentials:'same-origin'});
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Selection failed.');
      property.disabled = pic.disabled = form.querySelector('button').disabled = false;
      if (own !== sequence) return;
      if (save) document.querySelector("#selection-card").open = false;
      status.textContent = save ? 'Selection saved for your next login.' : 'Selection changed for this session. Use Save selection to remember it.';
      timer = setTimeout(async () => {
        if (own !== sequence) return;
        try {
          const ready = await fetch('/context/ready/', {cache:'no-store'});
          if (!ready.ok || !(await ready.json()).ready) throw new Error('Selection is not ready. Please select it again.');
          if (save) {
            const url = new URL(location.href); url.searchParams.delete('selection');
            history.replaceState(null, '', url);
          }
          location.reload();
        } catch (error) { switching.hidden = true; status.textContent = error.message; }
      }, result.wait_ms + 100);
    } catch (error) {
      property.disabled = pic.disabled = form.querySelector('button').disabled = false;
      switching.hidden = true; status.textContent = error.message;
    }
  }
  fillPics(form.dataset.selectedPic);
  property.addEventListener('change', () => { hideData(); fillPics(); status.textContent = 'Choose a PIC for this property.'; });
  pic.addEventListener('change', () => choose());
  form.addEventListener('submit', e => {e.preventDefault(); choose(true);});
  if (data.hidden && property.value && pic.value) choose();
  const charts = JSON.parse(document.querySelector('#chart-data').textContent) || [];
  const colors = ['#1d6540','#c99b22','#488899','#925f85','#a44b3c','#758b3a','#6b709c'];
  function draw(chart) {
    const canvas = document.querySelector(`[data-chart="${chart.key}"]`);
    if (!canvas) return;
    const ctx = canvas.getContext('2d'), rows = chart.rows;
    ctx.clearRect(0,0,320,240);
    const total = rows.reduce((s,r) => s+r.count,0);
    if (!total) {ctx.fillText('No active cattle',100,120);return;}
    const style = document.querySelector(`[data-chart-select="${chart.key}"]`).value;
    let angle = -Math.PI/2;
    rows.forEach((r,i) => {
      ctx.fillStyle = colors[i % colors.length];
      if (style === 'pie') {
        const end = angle + r.count/total*Math.PI*2;
        ctx.beginPath();ctx.moveTo(160,120);ctx.arc(160,120,102,angle,end);ctx.closePath();ctx.fill();
        const mid=(angle+end)/2; ctx.fillStyle='white';ctx.font='bold 14px system-ui';ctx.textAlign='center';
        ctx.fillText(String(r.count),160+Math.cos(mid)*68,120+Math.sin(mid)*68);angle=end;
      } else {
        const height = Math.min(28,200/rows.length), y=15+i*(210/rows.length);
        ctx.fillRect(0,y,r.count/total*250,height);
        ctx.fillStyle='#20382b';ctx.font='12px system-ui';ctx.textAlign='left';ctx.fillText(String(r.count),r.count/total*250+5,y+height/2+4);
      }
    });
    const legend = canvas.parentElement.querySelectorAll('li');
    legend.forEach((li,i) => {li.style.color=colors[i%colors.length];});
  }
  charts.forEach(c=>{draw(c);document.querySelector(`[data-chart-select="${c.key}"]`).addEventListener('change',()=>draw(c));});
})();
