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

  function restartNativeVideo(frame) {
    const video = frame.querySelector("video");
    if (!video) {
      return false;
    }
    video.currentTime = 0;
    const playPromise = video.play();
    if (playPromise && typeof playPromise.catch === "function") {
      playPromise.catch(function () {
        setFrameControlState(frame, true);
      });
    }
    return true;
  }

  function restartYouTubeVideo(player) {
    if (!player || typeof player.seekTo !== "function" || typeof player.playVideo !== "function") {
      return false;
    }
    player.seekTo(0, true);
    player.playVideo();
    return true;
  }

  function handlePlaybackEnded(frame, player) {
    if (!frame) {
      return;
    }
    const loopSame = frame.dataset.loopSame === "true";
    const nextUrl = frame.dataset.nextUrl;

    if (loopSame) {
      if (restartNativeVideo(frame) || restartYouTubeVideo(player)) {
        return;
      }
    }

    if (nextUrl) {
      window.location.href = withAutoplayParam(nextUrl);
    }
  }

  function withAutoplayParam(url) {
    try {
      const next = new URL(url, window.location.origin);
      next.searchParams.set("autoplay", "1");
      return next.href;
    } catch (error) {
      return url.indexOf("?") === -1 ? url + "?autoplay=1" : url + "&autoplay=1";
    }
  }

  function syncYouTubeIframeParams(iframe) {
    try {
      const src = new URL(iframe.src, window.location.origin);
      src.searchParams.set("enablejsapi", "1");
      src.searchParams.set("playsinline", "1");
      src.searchParams.set("rel", "0");
      src.searchParams.set("modestbranding", "1");
      src.searchParams.set("origin", window.location.origin);

      const frame = iframe.closest(".live-player-frame");
      if (frame && frame.dataset.forceAutoplay === "true") {
        src.searchParams.set("autoplay", "1");
        src.searchParams.set("mute", "1");
      }

      if (iframe.src !== src.href) {
        iframe.src = src.href;
      }
    } catch (error) {
      return;
    }
  }

  function initYouTubePlayers() {
    if (!window.YT || typeof window.YT.Player !== "function") {
      return;
    }

    document.querySelectorAll(".youtube-live-iframe").forEach(function (iframe, index) {
      if (iframe.dataset.youtubePlayerReady === "true") {
        return;
      }
      iframe.dataset.youtubePlayerReady = "true";
      if (!iframe.id) {
        iframe.id = "live-tv-youtube-" + Date.now() + "-" + index;
      }
      syncYouTubeIframeParams(iframe);

      const player = new window.YT.Player(iframe.id, {
        host: "https://www.youtube-nocookie.com",
        events: {
          onStateChange: function (event) {
            if (event.data === window.YT.PlayerState.ENDED) {
              handlePlaybackEnded(iframe.closest(".live-player-frame"), event.target);
            }
          },
        },
      });

      iframe.liveTvEndedPoll = setInterval(function () {
        if (typeof player.getPlayerState !== "function") {
          return;
        }
        try {
          if (player.getPlayerState() === window.YT.PlayerState.ENDED) {
            clearInterval(iframe.liveTvEndedPoll);
            handlePlaybackEnded(iframe.closest(".live-player-frame"), player);
          }
        } catch (error) {
          clearInterval(iframe.liveTvEndedPoll);
        }
      }, 1000);
    });
  }

  function loadYouTubeApiIfNeeded() {
    if (!document.querySelector(".youtube-live-iframe")) {
      return;
    }
    if (window.YT && typeof window.YT.Player === "function") {
      initYouTubePlayers();
      return;
    }

    const previousReady = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = function () {
      if (typeof previousReady === "function") {
        previousReady();
      }
      initYouTubePlayers();
    };

    if (!document.querySelector('script[src="https://www.youtube.com/iframe_api"]')) {
      const tag = document.createElement("script");
      tag.src = "https://www.youtube.com/iframe_api";
      tag.async = true;
      document.head.appendChild(tag);
    }
  }

  function initLiveTvFrames() {
    document.querySelectorAll(".live-player-frame").forEach(function (frame) {
      const video = frame.querySelector("video");
      if (video && frame.classList.contains("live-player-frame--native-controls")) {
        video.controls = false;
        video.preload = "none";
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
        video.addEventListener("ended", function () {
          handlePlaybackEnded(frame);
        });
      }
    });

    loadYouTubeApiIfNeeded();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initLiveTvFrames);
  } else {
    initLiveTvFrames();
  }
})();
