// Poll without overlapping requests; reload only when model states change.
(function () {
  var live = document.getElementById("batch-live");
  if (!live) { return; }
  var note = document.getElementById("batch-refresh-note");
  var version = live.dataset.version;
  var stopped = false;

  function poll() {
    var controller = new AbortController();
    var timeout = setTimeout(function () { controller.abort(); }, 5000);
    return fetch(live.dataset.statusUrl, {
      credentials: "same-origin", headers: { Accept: "application/json" }, signal: controller.signal
    }).then(function (response) {
      if (!response.ok) { throw new Error("Status unavailable"); }
      return response.json();
    }).then(function (status) {
      note.hidden = true;
      if (status.version !== version || !status.active) {
        stopped = true;
        window.modelEvaluatorRefresh();
        return;
      }
      status.jobs.forEach(function (job) {
        var elapsed = document.getElementById("elapsed-" + job.key);
        if (elapsed) { elapsed.textContent = job.elapsed_s === null ? "—" : String(job.elapsed_s); }
      });
    }).catch(function () {
      note.hidden = false;
    }).finally(function () {
      clearTimeout(timeout);
      if (!stopped) { setTimeout(poll, 3000); }
    });
  }
  setTimeout(poll, 3000);
})();
