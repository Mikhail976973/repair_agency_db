// Живой подсчёт суммы заявки. Итог на сервере считается заново из цен в БД,
// здесь — только подсказка для посетителя.
(function () {
  const form = document.getElementById('order-form');
  if (!form) return;
  const steps = JSON.parse(document.getElementById('discount-steps').textContent);
  const fmt = n => Math.round(n).toLocaleString('ru-RU') + ' ₽';
  const $ = id => document.getElementById(id);

  function recalc() {
    let count = 0, subtotal = 0;
    form.querySelectorAll('.order-qty').forEach(input => {
      const qty = parseFloat(String(input.value).replace(',', '.'));
      if (qty > 0) { count++; subtotal += qty * parseFloat(input.dataset.price); }
    });
    const step = steps.find(s => subtotal >= s.threshold);
    const percent = step ? step.percent : 0;
    const discount = subtotal * percent / 100;
    $('order-count').textContent = count;
    $('order-subtotal').textContent = fmt(subtotal);
    $('order-percent').textContent = percent;
    $('order-discount').textContent = '−' + fmt(discount);
    $('order-total').textContent = fmt(subtotal - discount);
  }
  form.addEventListener('input', recalc);
  recalc();
})();
