(function () {
  function setFrameControlState(frame, active) {
    frame.classList.toggle("is-controlling", active);
    const video = frame.querySelector("video");
    if (!video || !frame.classList.contains("live-player-frame--native-controls")) {
      return;
    }
    video.controls = active;
  }

  function scheduleMobileHide(frame) {
    clearTimeout(frame.liveTvControlTimer);
    frame.liveTvControlTimer = setTimeout(function () {
      if (document.fullscreenElement && frame.contains(document.fullscreenElement)) {
        return;
      }
      setFrameControlState(frame, false);
    }, 4500);
  }

  document.querySelectorAll(".live-player-frame").forEach(function (frame) {
    const video = frame.querySelector("video");
    if (video && frame.classList.contains("live-player-frame--native-controls")) {
      video.controls = false;
    }

    frame.addEventListener("mouseenter", function () {
      setFrameControlState(frame, true);
    });

    frame.addEventListener("mouseleave", function () {
      if (document.fullscreenElement && frame.contains(document.fullscreenElement)) {
        return;
      }
      setFrameControlState(frame, false);
    });

    frame.addEventListener("focusin", function () {
      setFrameControlState(frame, true);
    });

    frame.addEventListener("focusout", function () {
      setFrameControlState(frame, false);
    });

    frame.addEventListener("touchstart", function () {
      setFrameControlState(frame, true);
      scheduleMobileHide(frame);
    }, { passive: true });

    frame.addEventListener("click", function () {
      setFrameControlState(frame, true);
      scheduleMobileHide(frame);
    });

    if (video) {
      video.addEventListener("play", function () {
        scheduleMobileHide(frame);
      });
      video.addEventListener("pause", function () {
        setFrameControlState(frame, true);
      });
    }
  });
})();
