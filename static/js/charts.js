/* Графики Chart.js. Данные приходят из Django через <script id="charts-data" type="application/json"> */
(function () {
  var node = document.getElementById('charts-data');
  if (!node || typeof Chart === 'undefined') return;
  var data = JSON.parse(node.textContent);
  var accent = getComputedStyle(document.documentElement).getPropertyValue('--accent-color').trim() || '#c85716';
  var palette = [accent, '#6c757d', '#e0a96d', '#8a5a44', '#b0b7bd', '#3d5a50', '#d9822b', '#5c6b73', '#a0522d', '#c9b79c'];
  Chart.defaults.font.family = 'Roboto, system-ui, sans-serif';

  var bar = document.getElementById('chart-categories');
  if (bar && data.categories) {
    new Chart(bar, {
      type: 'bar',
      data: {
        labels: data.categories.labels,
        datasets: [{ label: 'Заказов', data: data.categories.values, backgroundColor: accent, borderRadius: 6 }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true, ticks: { precision: 0 } }, x: { grid: { display: false } } }
      }
    });
  }

  var pie = document.getElementById('chart-statuses');
  if (pie && data.statuses) {
    new Chart(pie, {
      type: 'doughnut',
      data: {
        labels: data.statuses.labels,
        datasets: [{ data: data.statuses.values, backgroundColor: palette, borderWidth: 2 }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: 'right', labels: { boxWidth: 12 } } }
      }
    });
  }
})();
