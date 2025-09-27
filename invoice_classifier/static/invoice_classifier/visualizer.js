(function () {
  function buildPalette(size) {
    const baseColors = [
      '#2563eb',
      '#14b8a6',
      '#f97316',
      '#f43f5e',
      '#a855f7',
      '#22c55e',
      '#0ea5e9',
      '#facc15',
      '#64748b',
    ];
    const colors = [];
    for (let i = 0; i < size; i += 1) {
      colors.push(baseColors[i % baseColors.length]);
    }
    return colors;
  }

  function renderChart(container) {
    if (!container) {
      return;
    }

    const rawData = container.dataset.chart || '[]';
    let parsed;
    try {
      parsed = JSON.parse(rawData);
    } catch (error) {
      parsed = [];
    }

    if (!Array.isArray(parsed) || parsed.length === 0) {
      return;
    }

    const labels = parsed.map((item) => item.name);
    const data = parsed.map((item) => item.total);
    const colors = buildPalette(parsed.length);

    const ctx = container.querySelector('#spending-chart');
    if (!ctx) {
      return;
    }

    new window.Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [
          {
            label: 'Gasto',
            data,
            backgroundColor: colors,
            borderRadius: 8,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: {
            beginAtZero: true,
            ticks: {
              callback(value) {
                return `${value.toLocaleString('es-ES', {
                  style: 'currency',
                  currency: 'EUR',
                  maximumFractionDigits: 0,
                })}`;
              },
            },
            grid: {
              color: 'rgba(148, 163, 184, 0.25)',
            },
          },
          x: {
            grid: {
              display: false,
            },
          },
        },
        plugins: {
          legend: {
            display: false,
          },
          tooltip: {
            callbacks: {
              label(context) {
                const amount = context.parsed.y || 0;
                return `Gasto: ${amount.toLocaleString('es-ES', {
                  style: 'currency',
                  currency: 'EUR',
                })}`;
              },
            },
          },
        },
      },
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    const container = document.querySelector('.chart-card__inner');
    renderChart(container);
  });
})();
