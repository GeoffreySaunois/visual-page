/* Chart.js instances: colored from the charte, rebuilt whenever the page changes
   theme or palette (`vr-theme-change`). */
(function () {
  "use strict";
  var CONFIGS = {{CHART_CONFIGS}};
  var instances = [];

  /* A token as a color Chart.js's parser reads: the browser resolves var() and
     color-mix() on a probe, and one painted pixel gives it back as rgb(). The
     probe sits in the document, which keeps its own dark canvas under every
     palette, so the figure matches the page around it, not the chrome. */
  var probe = document.createElement("span");
  var paint = document.createElement("canvas").getContext("2d", { willReadFrequently: true });
  function color(name) {
    probe.style.color = "var(" + name + ")";
    (document.querySelector("main") || document.body).appendChild(probe);
    var resolved = getComputedStyle(probe).color;
    probe.remove();
    paint.clearRect(0, 0, 1, 1);
    paint.fillStyle = resolved;
    paint.fillRect(0, 0, 1, 1);
    var p = paint.getImageData(0, 0, 1, 1).data;
    return "rgb(" + p[0] + ", " + p[1] + ", " + p[2] + ")";
  }
  function palette() {
    return ["--accent", "--teal", "--amber", "--blue", "--green", "--rose"].map(color);
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
    Chart.defaults.color = color("--text-soft");
    Chart.defaults.borderColor = color("--border");
    Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
    instances.forEach(function (chart) { chart.destroy(); });
    instances = CONFIGS.map(function (config, index) {
      return new Chart(document.getElementById("vr-chart-" + (index + 1)), colorize(config));
    });
  }

  document.addEventListener("vr-theme-change", renderAll);
  if (document.readyState !== "loading") renderAll();
  else document.addEventListener("DOMContentLoaded", renderAll);
})();
