(() => {
  const picker = document.querySelector('#cattle-picker');
  document.querySelector('#add-cattle')?.addEventListener('click', () => {
    const animals = document.querySelector('[name="animals"]');
    if (picker.value.trim()) animals.value += (animals.value.trim() ? '\n' : '') + picker.value.trim();
    picker.value = ''; picker.focus();
  });
})();
