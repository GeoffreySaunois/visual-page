/* Mermaid diagrams, themed from the charte tokens and redrawn whenever the page
   changes theme or palette (`vr-theme-change`). Renders are coalesced: a burst
   of changes while one render runs ends in a single redraw with the last
   colors, and a render waits until a diagram has a size (Mermaid measures text
   in the live SVG). */
(function () {
  "use strict";
  var nodes = Array.prototype.slice.call(document.querySelectorAll(".mermaid"));
  if (!nodes.length) return;
  var sources = nodes.map(function (node) { return node.textContent; });

  /* A token as a color Mermaid's parser reads: the browser resolves var() and
     color-mix() on a probe, and one painted pixel gives it back as rgb(). */
  var probe = document.createElement("span");
  var paint = document.createElement("canvas").getContext("2d", { willReadFrequently: true });
  function color(name) {
    probe.style.color = "var(" + name + ")";
    document.body.appendChild(probe);
    var resolved = getComputedStyle(probe).color;
    probe.remove();
    paint.clearRect(0, 0, 1, 1);
    paint.fillStyle = resolved;
    paint.fillRect(0, 0, 1, 1);
    var p = paint.getImageData(0, 0, 1, 1).data;
    return "rgb(" + p[0] + ", " + p[1] + ", " + p[2] + ")";
  }
  function themeVariables() {
    return {
      primaryColor: color("--surface"),
      primaryTextColor: color("--text"),
      primaryBorderColor: color("--accent"),
      lineColor: color("--text-soft"),
      secondaryColor: color("--code-bg"),
      tertiaryColor: color("--bg"),
      background: color("--bg"),
      fontFamily: getComputedStyle(document.body).fontFamily,
      fontSize: "14.5px"
    };
  }

  var running = false, pending = false;
  function renderAll() {
    pending = true;
    if (running) return;
    running = true;
    drain();
  }
  async function drain() {
    try {
      while (pending) {
        await new Promise(function (resolve) { requestAnimationFrame(resolve); });
        if (!nodes.some(function (node) { return node.getBoundingClientRect().width > 0; })) continue;
        pending = false;
        mermaid.initialize({ startOnLoad: false, securityLevel: "strict",
                             theme: "base", themeVariables: themeVariables() });
        nodes.forEach(function (node, index) {
          node.removeAttribute("data-processed");
          node.textContent = sources[index];
        });
        await mermaid.run({ nodes: nodes });
        document.dispatchEvent(new CustomEvent("vr-diagrams-rendered"));
      }
    } catch (error) { console.error("Diagram rendering failed", error); }
    finally { running = false; }
  }

  document.addEventListener("vr-theme-change", renderAll);
  if (document.readyState !== "loading") renderAll();
  else document.addEventListener("DOMContentLoaded", renderAll);
})();
