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

  function readChartData() {
    const script = document.getElementById('visualizer-chart-data');
    if (!script) {
      return [];
    }

    try {
      return JSON.parse(script.textContent || '[]');
    } catch (error) {
      return [];
    }
  }

  function formatCurrency(value) {
    const amount = Number.isFinite(value) ? value : 0;
    return amount.toLocaleString('es-ES', {
      style: 'currency',
      currency: 'EUR',
    });
  }

  function formatDate(value) {
    if (!value) {
      return '';
    }

    const parsedDate = new Date(value);
    if (Number.isNaN(parsedDate.getTime())) {
      return value;
    }

    return parsedDate.toLocaleDateString('es-ES', {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
    });
  }

  function hexToRgba(hex, alpha = 1) {
    if (!/^#([0-9a-f]{3}){1,2}$/i.test(hex)) {
      return hex;
    }

    const normalized = hex.replace('#', '');
    const step = normalized.length === 3 ? 1 : 2;
    const expand = (value) =>
      step === 1 ? parseInt(value.repeat(2), 16) : parseInt(value, 16);

    const r = expand(normalized.substring(0, step));
    const g = expand(normalized.substring(step, step * 2));
    const b = expand(normalized.substring(step * 2, step * 3));

    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }

  function renderChart(container, parsed, onBarClick) {
    if (!container || !Array.isArray(parsed) || parsed.length === 0) {
      return;
    }

    const labels = parsed.map((item) => item.name);
    const data = parsed.map((item) => item.total);
    const colors = buildPalette(parsed.length);

    const ctx = container.querySelector('#spending-chart');
    if (!ctx) {
      return;
    }

    if (typeof window.Chart !== 'function') {
      return;
    }

    const defaultBackground = colors.slice();
    const defaultHoverBackground = colors.map((color) =>
      hexToRgba(color, 0.55)
    );
    let selectedIndex = null;

    const chart = new window.Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [
          {
            label: 'Gasto',
            data,
            backgroundColor: defaultBackground,
            hoverBackgroundColor: defaultHoverBackground,
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
        onHover(event, elements) {
          const canvas = event && event.chart ? event.chart.canvas : null;
          if (!canvas) {
            return;
          }

          canvas.style.cursor = elements.length ? 'pointer' : 'default';
        },
        onClick(_event, elements) {
          if (!elements || elements.length === 0 || typeof onBarClick !== 'function') {
            return;
          }

          const index = elements[0].index;
          if (typeof index !== 'number') {
            return;
          }

          const entry = parsed[index];
          if (!entry) {
            return;
          }

          selectedIndex = index;
          const dataset = chart.data.datasets[0];
          if (dataset) {
            dataset.backgroundColor = colors.map((color, idx) =>
              idx === selectedIndex ? color : hexToRgba(color, 0.35)
            );
            dataset.hoverBackgroundColor = colors.map((color, idx) =>
              idx === selectedIndex ? hexToRgba(color, 0.55) : hexToRgba(color, 0.25)
            );
            chart.update();
          }

          onBarClick(entry, index);
        },
      },
    });

    return chart;
  }

  function initDetailsSection() {
    const section = document.querySelector('[data-details]');
    if (!section) {
      return () => {};
    }

    const titleTarget = section.querySelector('[data-details-name]');
    const tbody = section.querySelector('[data-details-body]');
    const headerButtons = Array.from(
      section.querySelectorAll('[data-sort-key]')
    );

    let currentTransactions = [];
    let currentSort = { key: 'date', direction: 'desc' };

    const sortComparators = {
      name(a, b) {
        return (a.name || '').localeCompare(b.name || '', 'es', {
          sensitivity: 'base',
        });
      },
      date(a, b) {
        const left = new Date(a.date || '').getTime();
        const right = new Date(b.date || '').getTime();
        if (Number.isNaN(left) && Number.isNaN(right)) {
          return 0;
        }
        if (Number.isNaN(left)) {
          return 1;
        }
        if (Number.isNaN(right)) {
          return -1;
        }
        return left - right;
      },
      amount(a, b) {
        return (a.amount || 0) - (b.amount || 0);
      },
    };

    const updateSortIndicators = () => {
      headerButtons.forEach((button) => {
        const key = button.dataset.sortKey;
        const th = button.closest('th');
        if (!key || !th) {
          return;
        }

        const isActive = currentSort.key === key;
        button.dataset.sortIndicator = isActive
          ? currentSort.direction === 'asc'
            ? '▲'
            : '▼'
          : '';
        th.setAttribute(
          'aria-sort',
          isActive
            ? currentSort.direction === 'asc'
              ? 'ascending'
              : 'descending'
            : 'none'
        );
      });
    };

    const renderRows = () => {
      if (!tbody) {
        return;
      }

      tbody.innerHTML = '';
      if (!currentTransactions.length) {
        const emptyRow = document.createElement('tr');
        const cell = document.createElement('td');
        cell.colSpan = 3;
        cell.textContent = 'No hay movimientos registrados para este criterio.';
        emptyRow.appendChild(cell);
        tbody.appendChild(emptyRow);
        return;
      }

      const sorted = [...currentTransactions];
      const comparator = sortComparators[currentSort.key] || (() => 0);
      sorted.sort((a, b) => {
        const result = comparator(a, b);
        return currentSort.direction === 'asc' ? result : -result;
      });

      sorted.forEach((transaction) => {
        const row = document.createElement('tr');

        const nameCell = document.createElement('td');
        nameCell.textContent = transaction.name || '';
        row.appendChild(nameCell);

        const dateCell = document.createElement('td');
        dateCell.textContent = formatDate(transaction.date);
        row.appendChild(dateCell);

        const amountCell = document.createElement('td');
        amountCell.classList.add('visualizer__details-amount');
        amountCell.textContent = formatCurrency(transaction.amount);
        row.appendChild(amountCell);

        tbody.appendChild(row);
      });
    };

    headerButtons.forEach((button) => {
      button.dataset.sortIndicator = '';
      button.addEventListener('click', () => {
        const key = button.dataset.sortKey;
        if (!key) {
          return;
        }

        if (currentSort.key === key) {
          currentSort.direction = currentSort.direction === 'asc' ? 'desc' : 'asc';
        } else {
          currentSort = {
            key,
            direction: key === 'name' ? 'asc' : 'desc',
          };
        }

        updateSortIndicators();
        renderRows();
      });
    });

    const showDetails = (entry) => {
      if (!entry) {
        section.hidden = true;
        section.setAttribute('aria-hidden', 'true');
        return;
      }

      currentTransactions = Array.isArray(entry.transactions)
        ? entry.transactions.slice()
        : [];
      currentSort = { key: 'date', direction: 'desc' };
      if (titleTarget) {
        titleTarget.textContent = entry.name || '';
      }

      section.hidden = false;
      section.setAttribute('aria-hidden', 'false');
      updateSortIndicators();
      renderRows();
    };

    updateSortIndicators();
    renderRows();

    return showDetails;
  }

  document.addEventListener('DOMContentLoaded', () => {
    const container = document.querySelector('.chart-card__inner');
    const chartData = readChartData();
    const showDetails = initDetailsSection();
    renderChart(container, chartData, showDetails);

    const form = document.querySelector('.controls');
    if (!form) {
      return;
    }

    const monthSelect = form.querySelector('#month-select');
    const modeInputs = form.querySelectorAll('input[name="mode"]');
    const criteriaInputs = form.querySelectorAll('input[name="criteria"]');
    const yearSelect = form.querySelector('#year-select');

    const submitForm = () => {
      if (typeof form.requestSubmit === 'function') {
        form.requestSubmit();
      } else {
        form.submit();
      }
    };

    const updateMonthAvailability = () => {
      const selectedMode = form.querySelector('input[name="mode"]:checked');
      if (!monthSelect || !selectedMode) {
        return;
      }

      monthSelect.disabled = selectedMode.value === 'yearly';
    };

    if (monthSelect) {
      monthSelect.addEventListener('change', submitForm);
    }

    if (yearSelect) {
      yearSelect.addEventListener('change', submitForm);
    }

    modeInputs.forEach((input) => {
      input.addEventListener('change', () => {
        updateMonthAvailability();
        submitForm();
      });
    });

    criteriaInputs.forEach((input) => {
      input.addEventListener('change', submitForm);
    });

    updateMonthAvailability();
  });
})();
