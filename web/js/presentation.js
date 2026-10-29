/* Bible presentation output.
 *
 * Two modes:
 *   - Live (default): connects to the app's local server with Server-Sent
 *     Events (/events) and re-renders whenever the operator changes the live
 *     slide. Polls /api/state as a fallback and reconnects automatically.
 *   - Preview (?preview=1): used inside the operator window; the app calls
 *     window.BiblePresenter.render(state) directly. It never connects to the server.
 */
(function () {
  "use strict";

  var params = new URLSearchParams(window.location.search);
  var PREVIEW = params.get("preview") === "1";
  var DEBUG = params.get("debug") === "1";

  var stage = document.getElementById("stage");
  var slide = document.getElementById("slide");
  var inner = document.getElementById("content-inner");
  var content = document.getElementById("content");
  var refTop = document.getElementById("ref-top");
  var refBottom = document.getElementById("ref-bottom");
  var dot = document.getElementById("status-dot");
  var root = document.documentElement;

  var lastJson = null;
  var lastState = null;
  var lastInstance = null;
  var lastVersion = -1;

  /* ---------- scale the 1920x1080 stage to the window (letterboxed) ---------- */
  function scaleStage() {
    var w = window.innerWidth, h = window.innerHeight;
    var s = Math.min(w / 1920, h / 1080);
    var x = (w - 1920 * s) / 2, y = (h - 1080 * s) / 2;
    stage.style.transform = "translate(" + x + "px," + y + "px) scale(" + s + ")";
  }
  window.addEventListener("resize", scaleStage);
  if (window.ResizeObserver) new ResizeObserver(scaleStage).observe(document.documentElement);
  scaleStage();

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function verseNode(tag, lang, v, showNum) {
    var node = el(tag, "verse lang-" + lang);
    if (showNum) node.appendChild(el("span", "num", v.num));
    if (v.missing) node.appendChild(el("span", "missing", v.text));
    else node.appendChild(document.createTextNode(v.text));
    return node;
  }

  function hexToRgba(hex, alpha) {
    var h = hex.replace("#", "");
    if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
    var n = parseInt(h, 16);
    return "rgba(" + ((n >> 16) & 255) + "," + ((n >> 8) & 255) + "," + (n & 255) + "," + alpha + ")";
  }

  function applyStyle(st) {
    var set = function (k, v) { root.style.setProperty(k, v); };
    set("--bg", st.background || "#0b1530");
    set("--text", st.text_color || "#fff8ec");
    set("--ref", st.reference_color || "#e9c46a");
    set("--font", '"' + (st.font_family || "EB Garamond") + '", "EB Garamond", Garamond, Georgia, serif');
    set("--en-size", (st.en_size || 56) + "px");
    set("--fr-size", (st.fr_size || 56) + "px");
    set("--ref-size", (st.ref_size || 40) + "px");
    set("--line", String(st.line_spacing || 1.3));
    set("--gap", (st.stacked_gap != null ? st.stacked_gap : 48) + "px");
    set("--align", st.align || "center");
    document.body.classList.toggle("transparent", !!st.transparent_background);
    var footer = st.display_mode !== "fullscreen";
    document.body.classList.toggle("footer", footer);
    set("--footer-h", Math.round(1080 * (st.footer_height || 34) / 100) + "px");
    set("--band", hexToRgba(st.background || "#0b1530", st.footer_opacity != null ? st.footer_opacity / 100 : 0.85));
  }

  function orderedColumns(s, st) {
    var cols = (s.columns || []).filter(function (c) {
      return c.lang === "en" ? st.show_en !== false : st.show_fr !== false;
    });
    if (st.order === "fr-en") cols.sort(function (a, b) { return a.lang === "fr" ? -1 : 1; });
    else cols.sort(function (a, b) { return a.lang === "en" ? -1 : 1; });
    return cols;
  }

  function referenceText(s, cols) {
    var refs = [];
    cols.forEach(function (c) {
      var r = s.reference && s.reference[c.lang];
      if (r && refs.indexOf(r) < 0) refs.push(r);
    });
    if (!refs.length && s.reference) refs.push(s.reference.en || s.reference.fr || "");
    var text = refs.join("  ·  ");
    if (s.pages > 1) text += "   (" + s.page + "/" + s.pages + ")";
    return text;
  }

  function renderSlide(s, st) {
    inner.innerHTML = "";
    refTop.textContent = "";
    refBottom.textContent = "";
    var cols = orderedColumns(s, st);
    var showNum = st.show_verse_numbers !== false;
    var layout = st.layout === "stacked" ? "stacked" : "side";
    slide.className = "layout-" + layout;

    if (layout === "side") {
      var grid = el("div", "grid" + (cols.length < 2 ? " single" : ""));
      if (st.show_labels) cols.forEach(function (c) { grid.appendChild(el("div", "label", c.label)); });
      var rows = cols.length ? cols[0].verses.length : 0;
      for (var i = 0; i < rows; i++) {
        cols.forEach(function (c) { grid.appendChild(verseNode("div", c.lang, c.verses[i], showNum)); });
      }
      inner.appendChild(grid);
    } else {
      var stack = el("div", "stack");
      cols.forEach(function (c) {
        var block = el("div", "block");
        if (st.show_labels) block.appendChild(el("div", "label", c.label));
        var p = el("p", "lang-" + c.lang);
        c.verses.forEach(function (v, idx) {
          if (idx) p.appendChild(document.createTextNode(" "));
          var span = verseNode("span", c.lang, v, showNum);
          span.className = "";   // font size comes from the paragraph
          p.appendChild(span);
        });
        block.appendChild(p);
        stack.appendChild(block);
      });
      inner.appendChild(stack);
    }

    if (st.show_reference !== false && cols.length) {
      var target = st.reference_position === "top" ? refTop : refBottom;
      target.textContent = referenceText(s, cols);
    }
    fitText();
  }

  /* ---------- shrink text until the passage fits on the slide ---------- */
  function fits() {
    return inner.scrollHeight <= content.clientHeight + 1 && inner.scrollWidth <= content.clientWidth + 1;
  }
  function fitText() {
    root.style.setProperty("--fit", "1");
    if (fits()) return;
    var lo = 0.4, hi = 1;
    for (var i = 0; i < 9; i++) {
      var mid = (lo + hi) / 2;
      root.style.setProperty("--fit", String(mid));
      if (fits()) lo = mid; else hi = mid;
    }
    root.style.setProperty("--fit", String(lo));
  }

  function render(state) {
    if (!state || state.type !== "state") return;
    lastState = state;
    scaleStage();          // the embedding window may have been resized without an event
    var st = state.style || {};
    applyStyle(st);
    document.body.classList.toggle("black", state.mode === "black");
    if (state.mode === "live" && state.slide) {
      renderSlide(state.slide, st);
      slide.classList.remove("hidden");
    } else {
      slide.classList.add("hidden");
      if (state.mode === "clear") { inner.innerHTML = ""; refTop.textContent = ""; refBottom.textContent = ""; }
    }
  }

  function handleMessage(json) {
    if (json === lastJson) return;
    var msg;
    try { msg = JSON.parse(json); } catch (e) { return; }
    if (msg.type === "reload") { window.location.reload(); return; }
    // A slow poll reply can arrive after a newer live update: never go backwards.
    if (msg.instance === lastInstance && msg.version < lastVersion) return;
    lastInstance = msg.instance;
    lastVersion = msg.version;
    lastJson = json;
    render(msg);
  }

  window.BiblePresenter = {
    render: function (state) { render(state); },
    refit: function () { if (lastState) render(lastState); }
  };

  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(function () { if (lastState) render(lastState); });
  }

  if (PREVIEW) return;

  /* ---------- live connection ---------- */
  if (DEBUG) dot.hidden = false;
  var source = null;
  function setConnected(ok) { dot.classList.toggle("ok", ok); }

  function connect() {
    if (!window.EventSource) return;
    source = new EventSource("/events");
    source.onopen = function () { setConnected(true); };
    source.onmessage = function (ev) { handleMessage(ev.data); };
    source.onerror = function () {
      setConnected(false);
      // The browser retries automatically; if the stream was closed for good, start a new one.
      if (source.readyState === 2) setTimeout(connect, 2000);
    };
  }

  function poll() {
    if (source && source.readyState === 1) return;   // SSE is healthy
    var xhr = new XMLHttpRequest();
    xhr.open("GET", "/api/state", true);
    xhr.timeout = 2500;
    xhr.onload = function () { if (xhr.status === 200) handleMessage(xhr.responseText); };
    xhr.send();
  }

  connect();
  poll();
  setInterval(poll, 3000);
})();
