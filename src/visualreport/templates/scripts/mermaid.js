/* Mermaid diagrams, themed from the charte tokens and re-rendered on theme change. */
(function () {
  "use strict";
  var nodes = Array.prototype.slice.call(document.querySelectorAll(".mermaid"));
  var sources = nodes.map(function (node) { return node.textContent; });

  function cssVar(name) {
    return getComputedStyle(document.body).getPropertyValue(name).trim();
  }
  function themeVariables() {
    return {
      primaryColor: cssVar("--surface"),
      primaryTextColor: cssVar("--text"),
      primaryBorderColor: cssVar("--accent"),
      lineColor: cssVar("--text-soft"),
      secondaryColor: cssVar("--code-bg"),
      tertiaryColor: cssVar("--bg"),
      fontFamily: getComputedStyle(document.body).fontFamily,
      fontSize: "14.5px"
    };
  }
  function renderAll() {
    mermaid.initialize({ startOnLoad: false, securityLevel: "loose",
                         theme: "base", themeVariables: themeVariables() });
    nodes.forEach(function (node, index) {
      node.removeAttribute("data-processed");
      node.textContent = sources[index];
    });
    mermaid.run({ nodes: nodes });
  }

  document.addEventListener("vr-themechange", renderAll);
  if (document.readyState !== "loading") renderAll();
  else document.addEventListener("DOMContentLoaded", renderAll);
})();
