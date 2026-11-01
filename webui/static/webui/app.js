// Move focus to the error summary so keyboard and screen-reader users land on the problem.
document.addEventListener("DOMContentLoaded", function () {
  var summary = document.getElementById("error-summary");
  if (summary) { summary.focus(); }
});

// Say in words which column is the target, and hide its feature/excluded choice.
document.addEventListener("DOMContentLoaded", function () {
  var select = document.getElementById("id_target");
  if (!select) { return; }
  var rows = document.querySelectorAll("tr[data-column]");
  function sync() {
    Array.prototype.forEach.call(rows, function (row) {
      var isTarget = select.value !== "" && row.dataset.column === select.value;
      row.querySelector("[data-target-note]").hidden = !isTarget;
      row.querySelector("[data-role-control]").hidden = isTarget;
    });
  }
  select.addEventListener("change", sync);
  sync();
});

// Avoid discarding keyboard focus when a background training job completes.
window.modelEvaluatorRefresh = function () {
  var active = document.activeElement;
  var update = document.getElementById("results-update");
  if (update && active && active !== document.body && active !== document.documentElement) {
    update.hidden = false;
    return;
  }
  window.location.reload();
};
document.addEventListener("DOMContentLoaded", function () {
  var refresh = document.getElementById("refresh-results");
  if (refresh) { refresh.addEventListener("click", function () { window.location.reload(); }); }
});
