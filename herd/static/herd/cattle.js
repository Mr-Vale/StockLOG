/* Native select remains usable without JavaScript. Selected values are submitted as text. */
const form = document.querySelector('[data-cattle-form]');
if (form) {
  const select = form.querySelector('[data-animal-selection]');
  if (select) {
    const search = document.createElement('input');
    search.type = 'search'; search.placeholder = 'Search NLIS / RFID'; search.ariaLabel = 'Search active animals';
    select.before(search);
    const list = document.createElement('ul'); list.className = 'selected-animals'; select.after(list);
    const render = () => {
      list.replaceChildren();
      for (const option of select.selectedOptions) {
        const item = document.createElement('li'); item.append(option.textContent);
        const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = 'Remove';
        remove.addEventListener('click', () => { option.selected = false; render(); });
        item.append(remove); list.append(item);
      }
    };
    select.addEventListener('change', render); render();
    search.addEventListener('input', () => {
      for (const option of select.options) option.hidden = !option.textContent.toLowerCase().includes(search.value.toLowerCase());
    });
    const mob = form.querySelector('[name=mob]');
    if (mob) {
      const toggle = () => { select.disabled = !!mob.value; search.disabled = !!mob.value; };
      mob.addEventListener('change', toggle); toggle();
    }
  }
  // Keep each mode's complete input and shared selections while switching forms.
  const storageKey = `cattle-exit:${document.body.dataset.account}:${form.querySelector('[name=farm_context]').value}`;
  const mode = form.querySelector('input[name=mode]');
  if (mode) {
    let saved = {};
    try { saved = JSON.parse(sessionStorage.getItem(storageKey) || '{}'); } catch (_) { /* empty draft */ }
    const previous = {...(saved[mode.value] || {}), ...(saved.shared || {})};
    for (const field of form.elements) {
      if (field.tagName === 'BUTTON' || ['csrfmiddlewaretoken', 'farm_context', 'mode', 'task'].includes(field.name)) continue;
      if (Object.hasOwn(previous, field.name)) {
        if (field.multiple) for (const option of field.options) option.selected = previous[field.name].includes(option.value);
        else field.value = previous[field.name];
      }
    }
    if (select) select.dispatchEvent(new Event('change'));
    const mob = form.querySelector('[name=mob]'); if (mob) mob.dispatchEvent(new Event('change'));
    form.addEventListener('submit', () => {
      const values = {};
      for (const field of form.elements) {
        if (!field.name || field.tagName === 'BUTTON' || ['csrfmiddlewaretoken','farm_context','mode','task'].includes(field.name)) continue;
        values[field.name] = field.multiple ? Array.from(field.selectedOptions, o => o.value) : field.value;
      }
      saved[mode.value] = values; saved.shared = values;
      try { sessionStorage.setItem(storageKey, JSON.stringify(saved)); } catch (_) { /* storage unavailable */ }
    });
  }
}
if (form) {
  for (const checkbox of form.querySelectorAll('input[name^="update_"]')) {
    const field = form.elements.namedItem(checkbox.name.slice(7));
    if (field) {
      const toggle = () => { field.disabled = !checkbox.checked; };
      checkbox.addEventListener('change', toggle); toggle();
    }
  }
}
