const feedForm = document.querySelector('[data-feed-form]');
if (feedForm) {
  const home = feedForm.elements.namedItem('home_grown');
  const tested = feedForm.elements.namedItem('product_tested');
  const showSources = () => {
    if (!home) return;
    for (const wrapper of feedForm.querySelectorAll('[data-feed-source]')) {
      wrapper.hidden = home.checked;
      for (const field of wrapper.querySelectorAll('input,select,textarea')) field.disabled = home.checked;
    }
    const residue = feedForm.querySelector('[data-feed-residue]');
    if (residue) {
      residue.hidden = home.checked || tested.value !== 'yes';
      residue.querySelector('textarea').disabled = residue.hidden;
    }
  };
  if (home) { home.addEventListener('change', showSources); tested.addEventListener('change', showSources); showSources(); }
  if (feedForm.dataset.operation === 'feed') {
    const products = JSON.parse(document.getElementById('feed-products').textContent || '[]');
    const type = feedForm.elements.namedItem('feed_type'), item = feedForm.elements.namedItem('item');
    const mode = feedForm.elements.namedItem('mode'), quantity = feedForm.elements.namedItem('quantity');
    const renderModes = () => {
      const previous = mode.value;
      const product = products.find(p => p.id === item.value);
      mode.replaceChildren(new Option('Unit', 'unit'));
      if (product && product.unit !== 'unit') mode.add(new Option(product.unit === 'mL' ? 'ml' : product.unit, 'measure'));
      mode.value = Array.from(mode.options).some(o => o.value === previous) ? previous : 'unit';
      quantity.step = mode.value === 'unit' ? '1' : 'any';
    };
    const renderProducts = () => {
      const previous = item.value;
      item.replaceChildren(new Option('Select feed', ''));
      for (const product of products.filter(p => p.type === type.value)) item.add(new Option(product.name, product.id));
      item.value = Array.from(item.options).some(o => o.value === previous) ? previous : '';
      renderModes();
    };
    type.addEventListener('change', renderProducts);
    item.addEventListener('change', renderModes);
    mode.addEventListener('change', () => { quantity.step = mode.value === 'unit' ? '1' : 'any'; });
    renderProducts();
  }
}
