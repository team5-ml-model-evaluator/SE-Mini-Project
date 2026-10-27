// Move focus to the error summary so keyboard and screen-reader users land on the problem.
document.addEventListener("DOMContentLoaded", function () {
  var summary = document.getElementById("error-summary");
  if (summary) { summary.focus(); }
});
