(function () {
  function scheduleProcessingRefresh() {
    if (!document.querySelector("[data-processing-progress='1']")) {
      return;
    }
    window.setTimeout(function () {
      window.location.reload();
    }, 5000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", scheduleProcessingRefresh);
  } else {
    scheduleProcessingRefresh();
  }
})();
