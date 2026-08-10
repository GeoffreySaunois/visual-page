/* Chart.js instances: colored from the charte, rebuilt on every theme change. */
(function () {
  "use strict";
  var CONFIGS = {{CHART_CONFIGS}};
  var instances = [];

  function cssVar(name) {
    return getComputedStyle(document.body).getPropertyValue(name).trim();
  }
  function palette() {
    return ["--accent", "--teal", "--amber", "--blue", "--green", "--rose"].map(cssVar);
  }
  function colorize(config) {
    var colors = palette();
    var copy = JSON.parse(JSON.stringify(config));
    (copy.data.datasets || []).forEach(function (dataset, index) {
      if (!dataset.backgroundColor) dataset.backgroundColor = colors[index % colors.length];
      if (!dataset.borderColor) dataset.borderColor = colors[index % colors.length];
    });
    copy.options = copy.options || {};
    copy.options.maintainAspectRatio = false;
    return copy;
  }
  function renderAll() {
    Chart.defaults.color = cssVar("--text-soft");
    Chart.defaults.borderColor = cssVar("--border");
    Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
    instances.forEach(function (chart) { chart.destroy(); });
    instances = CONFIGS.map(function (config, index) {
      return new Chart(document.getElementById("vr-chart-" + (index + 1)), colorize(config));
    });
  }

  document.addEventListener("vr-themechange", renderAll);
  if (document.readyState !== "loading") renderAll();
  else document.addEventListener("DOMContentLoaded", renderAll);
})();
