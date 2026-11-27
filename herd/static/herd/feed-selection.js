/* IDs, rather than row positions, survive server-side sorting. */
const feedSelection = document.querySelector('[data-feed-selection]');
if (feedSelection) {
  const update = () => {
    const chosen = [...feedSelection.querySelectorAll('[name=selected_ids]:checked:not(:disabled)')].map(box => box.value);
    feedSelection.querySelector('[data-selection-next]').disabled = chosen.length === 0;
    feedSelection.querySelector('[data-selection-count]').textContent = chosen.length + ' selected';
    for (const link of feedSelection.querySelectorAll('[data-feed-sort]')) {
      const url = new URL(link.href);
      url.searchParams.delete('chosen');
      chosen.forEach(id => url.searchParams.append('chosen', id));
      link.href = url.pathname + url.search;
    }
  };
  feedSelection.addEventListener('change', update);
  update();
}
