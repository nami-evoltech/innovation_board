const chartColor = "#006d77";
const chartAccent = "#d97706";
const chartState = [];

const compactLabel = (label) => {
  const text = String(label);
  return text.length > 18 ? `${text.slice(0, 18)}...` : text;
};

const filteredItems = (state, mode) => {
  let items = state.labels.map((label, index) => ({
    label,
    value: state.values[index],
    id: state.ids[index],
  }));

  if (mode === "nonzero") {
    items = items.filter((item) => item.value > 0);
  }

  if (mode === "top10") {
    items = items.slice(0, 10);
  }

  return items;
};

const applyChartMode = (mode) => {
  chartState.forEach((state) => {
    const items = filteredItems(state, mode);
    const labels = items.map((item) => item.label);
    const values = items.map((item) => item.value);
    state.visibleIds = items.map((item) => item.id);

    state.canvas.parentElement.style.height = `${Math.max(240, labels.length * 46 + 80)}px`;
    state.chart.data.labels = labels.map(compactLabel);
    state.chart.data.datasets[0].data = values;
    state.chart.data.datasets[0].backgroundColor = values.map((_, index) => (index === 0 ? chartAccent : chartColor));
    state.chart.options.plugins.tooltip.callbacks.title = (tooltipItems) => labels[tooltipItems[0].dataIndex];
    state.chart.update();
  });

  document.querySelectorAll("[data-chart-filter]").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.chartFilter === mode));
  });
};

document.querySelectorAll(".vote-chart").forEach((canvas) => {
  const labels = JSON.parse(canvas.dataset.labels || "[]");
  const values = JSON.parse(canvas.dataset.values || "[]");
  const ids = JSON.parse(canvas.dataset.ids || "[]");
  const state = { canvas, labels, values, ids, visibleIds: [] };

  const chart = new Chart(canvas, {
    type: "bar",
    data: {
      labels: [],
      datasets: [
        {
          data: [],
          backgroundColor: [],
          borderRadius: 7,
          barThickness: 24,
        },
      ],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      onClick: (_event, elements) => {
        if (!elements.length) return;
        const id = state.visibleIds[elements[0].index];
        if (id) window.location.href = `/ideas/${id}`;
      },
      onHover: (event, elements) => {
        event.native.target.style.cursor = elements.length ? "pointer" : "default";
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: () => "",
            label: (context) => `${context.parsed.x}票`,
          },
        },
      },
      scales: {
        x: {
          beginAtZero: true,
          ticks: { precision: 0 },
          grid: { color: "rgba(148, 163, 184, 0.25)" },
        },
        y: {
          grid: { display: false },
          ticks: {
            color: "#17202a",
            font: { weight: 700 },
            autoSkip: false,
          },
        },
      },
    },
  });

  state.chart = chart;
  chartState.push(state);
});

document.querySelectorAll("[data-chart-filter]").forEach((button) => {
  button.addEventListener("click", () => applyChartMode(button.dataset.chartFilter));
});

applyChartMode("all");
