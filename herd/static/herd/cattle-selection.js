/* The server validates every submitted ID; this only enables Next for a nonempty choice. */
const selectionForm = document.querySelector('[data-cattle-selection]');
if (selectionForm) {
  const next = selectionForm.querySelector('[data-selection-next]');
  const count = selectionForm.querySelector('[data-selection-count]');
  const update = () => {
    const size = selectionForm.querySelectorAll('input[name="selected_ids"]:checked:not(:disabled)').length;
    next.disabled = size === 0;
    count.textContent = `${size} selected`;
  };
  selectionForm.addEventListener('change', update);
  update();
}
