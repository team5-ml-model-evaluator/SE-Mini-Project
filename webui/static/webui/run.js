// Poll the run status every 3 s (the SRS allows at most 5 s) and keep an elapsed-time counter moving.
(function () {
  var live = document.getElementById("run-live");
  if (!live || live.dataset.active !== "true") { return; }
  var url = live.dataset.statusUrl;
  var state = live.dataset.state;
  var elapsed = live.dataset.elapsed === "" ? null : parseFloat(live.dataset.elapsed);
  var polledAt = Date.now();
  var stateText = document.getElementById("state-text");
  var glyph = document.getElementById("state-glyph");
  var line = document.getElementById("elapsed");
  var note = document.getElementById("refresh-note");
  var pill = live.querySelector(".run-state");
  var glyphs = { Queued: "◷", Running: "▶" };

  function clock(seconds) {
    var m = Math.floor(seconds / 60), s = Math.floor(seconds % 60);
    return (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
  }
  function paint() {
    if (state === "Running" && elapsed !== null) {
      line.textContent = "Running for " + clock(elapsed + (Date.now() - polledAt) / 1000) + ". This page updates by itself.";
    } else if (state === "Queued") {
      line.textContent = "Waiting for a free worker. This page updates by itself.";
    }
  }
  function poll() {
    fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } })
      .then(function (r) { if (!r.ok) { throw new Error(r.status); } return r.json(); })
      .then(function (d) {
        note.hidden = true;
        if (d.state === "Completed" || d.state === "Failed") { window.location.reload(); return; }
        if (d.state !== state) {
          state = d.state;
          stateText.textContent = state;
          glyph.textContent = glyphs[state];
          pill.className = "run-state run-state--" + state.toLowerCase();
        }
        elapsed = d.elapsed_s;
        polledAt = Date.now();
        paint();
      })
      .catch(function () { note.hidden = false; });
  }
  paint();
  setInterval(paint, 1000);
  setInterval(poll, 3000);
})();
