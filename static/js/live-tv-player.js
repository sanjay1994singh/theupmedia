(function () {
  const WEB_TICKER_GAP_PX = 42;

  function tickerElapsedSeconds(marquee) {
    const offset = Number.parseFloat(marquee.dataset.tickerOffsetSeconds || "0");
    if (!Number.isFinite(marquee.liveTickerClockStartedAt)) {
      marquee.liveTickerClockStartedAt = performance.now();
    }
    const elapsedOnPage = (performance.now() - marquee.liveTickerClockStartedAt) / 1000;
    return Math.max(0, (Number.isFinite(offset) ? offset : 0) + elapsedOnPage);
  }

  function syncWebTickerSpeed(marquee) {
    const tickerText = marquee.querySelector("p");
    if (!tickerText || marquee.clientWidth <= 0) {
      return;
    }

    const configuredDuration = Math.max(
      1,
      Number.parseFloat(marquee.dataset.tickerBaseDuration || "22") || 22
    );
    const baselineDistance = marquee.clientWidth + WEB_TICKER_GAP_PX;
    const actualDistance = tickerText.getBoundingClientRect().width + WEB_TICKER_GAP_PX;
    const pixelsPerSecond = baselineDistance / configuredDuration;
    const actualDuration = Math.max(1, actualDistance / pixelsPerSecond);
    const elapsed = tickerElapsedSeconds(marquee);

    marquee.style.setProperty("--ticker-speed", actualDuration.toFixed(3) + "s");
    marquee.style.setProperty("--ticker-delay", "-" + (elapsed % actualDuration).toFixed(3) + "s");
  }

  function initWebTickerSpeeds() {
    const marquees = Array.from(document.querySelectorAll(".web-live-ticker-marquee"));
    if (!marquees.length) {
      return;
    }

    const syncAll = function () {
      marquees.forEach(syncWebTickerSpeed);
    };
    syncAll();
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(syncAll);
    }

    let resizeTimer = null;
    window.addEventListener("resize", function () {
      window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(syncAll, 120);
    });
  }

  function getLiveFrame(element) {
    return element ? element.closest(".web-live-frame, .live-player-frame") : null;
  }

  function setFrameControlState(frame, active) {
    if (frame.classList.contains("web-live-frame")) {
      const video = frame.querySelector("video");
      if (video) {
        video.controls = false;
      }
      return;
    }
    frame.classList.toggle("is-controlling", active);
    const video = frame.querySelector("video");
    if (frame.dataset.hideNativeControls === "true") {
      if (video) {
        video.controls = false;
      }
      return;
    }
    if (!video || !frame.classList.contains("live-player-frame--native-controls")) {
      return;
    }
    video.controls = active;
  }

  function restartNativeVideo(frame) {
    const video = frame.querySelector("video");
    if (!video) {
      return false;
    }
    syncNativeVideoToLive(frame, video);
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
    const syncReload = frame.dataset.syncReload === "true";

    if (loopSame) {
      if (restartNativeVideo(frame) || restartYouTubeVideo(player)) {
        return;
      }
    }

    if (syncReload) {
      window.location.reload();
      return;
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
      src.searchParams.set("controls", "0");
      src.searchParams.set("disablekb", "1");
      src.searchParams.set("fs", "0");
      src.searchParams.set("rel", "0");
      src.searchParams.set("modestbranding", "1");
      src.searchParams.set("origin", window.location.origin);

      const frame = getLiveFrame(iframe);
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
              handlePlaybackEnded(getLiveFrame(iframe), event.target);
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
            handlePlaybackEnded(getLiveFrame(iframe), player);
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

  function parseNumber(value, fallback) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  }


  function liveTvScriptOnce(src) {
    return new Promise(function (resolve, reject) {
      const existing = document.querySelector('script[src="' + src + '"]');
      if (existing) {
        if (existing.dataset.loaded === "true") {
          resolve();
          return;
        }
        existing.addEventListener("load", resolve, { once: true });
        existing.addEventListener("error", reject, { once: true });
        return;
      }
      const script = document.createElement("script");
      script.src = src;
      script.async = true;
      script.dataset.liveTvDynamic = "true";
      script.addEventListener("load", function () {
        script.dataset.loaded = "true";
        resolve();
      }, { once: true });
      script.addEventListener("error", reject, { once: true });
      document.head.appendChild(script);
    });
  }

  function videoSource(video) {
    const source = video.querySelector("source");
    return source ? source.src || source.getAttribute("src") || "" : video.currentSrc || video.src || "";
  }

  function isHlsVideo(video) {
    const source = video.querySelector("source");
    const type = (source ? source.type : video.type || "").toLowerCase();
    const src = videoSource(video).toLowerCase();
    return type.indexOf("mpegurl") !== -1 || src.indexOf(".m3u8") !== -1;
  }

  function nativeHlsSupported(video) {
    return Boolean(video.canPlayType("application/vnd.apple.mpegurl") || video.canPlayType("application/x-mpegURL"));
  }


  function switchToFallbackVideo(frame, video) {
    const fallback = video.dataset.fallbackVideoUrl || "";
    if (!fallback || video.dataset.fallbackActive === "true") {
      setFrameControlState(frame, true);
      return false;
    }
    if (video.liveTvHls) {
      video.liveTvHls.destroy();
      video.liveTvHls = null;
    }
    video.dataset.fallbackActive = "true";
    video.liveTvHlsAttached = "";
    video.innerHTML = "";
    const source = document.createElement("source");
    source.src = fallback;
    source.type = video.dataset.fallbackVideoType || "video/mp4";
    video.appendChild(source);
    video.load();
    video.addEventListener("loadedmetadata", function () {
      syncNativeVideoToLive(frame, video);
      const playPromise = video.play();
      if (playPromise && typeof playPromise.catch === "function") {
        playPromise.catch(function () {
          setFrameControlState(frame, true);
        });
      }
    }, { once: true });
    return true;
  }

  function attachHlsIfNeeded(frame, video) {
    if (!isHlsVideo(video) || nativeHlsSupported(video)) {
      return Promise.resolve();
    }
    const src = videoSource(video);
    if (!src) {
      return Promise.resolve();
    }
    if (video.liveTvHlsAttached === src) {
      return Promise.resolve();
    }
    return liveTvScriptOnce("https://cdn.jsdelivr.net/npm/hls.js@1.5.17/dist/hls.min.js")
      .then(function () {
        if (!window.Hls || !window.Hls.isSupported()) {
          throw new Error("HLS is not supported in this browser.");
        }
        if (video.liveTvHls) {
          video.liveTvHls.destroy();
        }
        const hls = new window.Hls({
          enableWorker: true,
          lowLatencyMode: false,
          backBufferLength: 30,
          maxBufferLength: 45,
          maxMaxBufferLength: 90,
          manifestLoadingTimeOut: 12000,
          levelLoadingTimeOut: 12000,
          fragLoadingTimeOut: 20000,
        });
        video.liveTvHls = hls;
        video.liveTvHlsAttached = src;
        hls.loadSource(src);
        hls.attachMedia(video);
        hls.on(window.Hls.Events.ERROR, function (_event, data) {
          if (!data || !data.fatal) {
            return;
          }
          if (data.type === window.Hls.ErrorTypes.NETWORK_ERROR) {
            hls.startLoad();
          } else if (data.type === window.Hls.ErrorTypes.MEDIA_ERROR) {
            hls.recoverMediaError();
          } else {
            hls.destroy();
            video.liveTvHls = null;
            video.liveTvHlsAttached = "";
            switchToFallbackVideo(frame, video);
          }
        });
      })
      .catch(function () {
        switchToFallbackVideo(frame, video);
      });
  }

  function syncedStartSeconds(frame) {
    const seekPosition = parseNumber(frame.dataset.seekPosition, 0);
    const videoDuration = parseNumber(frame.dataset.videoDuration, 0);
    const serverTime = frame.dataset.serverTime ? new Date(frame.dataset.serverTime).getTime() : NaN;
    const elapsed = Number.isFinite(serverTime) ? Math.max(0, (Date.now() - serverTime) / 1000) : 0;
    const target = Math.max(0, seekPosition + elapsed);
    if (videoDuration > 0) {
      return Math.min(target, Math.max(0, videoDuration - 0.25));
    }
    return target;
  }

  function syncNativeVideoToLive(frame, video) {
    const target = syncedStartSeconds(frame);
    if (!Number.isFinite(target) || target <= 0) {
      return;
    }
    try {
      if (Math.abs((video.currentTime || 0) - target) > 1.25) {
        video.currentTime = target;
      }
    } catch (error) {
      return;
    }
  }

  function playNativeLiveVideo(frame, video) {
    if (frame.dataset.forceAutoplay === "true") {
      if (frame.dataset.userMuteTouched !== "true") {
        video.muted = true;
      }
      video.autoplay = true;
      video.preload = "auto";
    }
    attachHlsIfNeeded(frame, video).finally(function () {
      syncNativeVideoToLive(frame, video);
      if (frame.dataset.forceAutoplay === "true" || video.autoplay) {
        const playPromise = video.play();
        if (playPromise && typeof playPromise.catch === "function") {
          playPromise.catch(function () {
            setFrameControlState(frame, true);
          });
        }
      }
    });
  }

  function syncMuteButton(frame) {
    const video = frame.querySelector("video");
    const button = frame.querySelector(".web-live-mute, .live-mute-toggle");
    if (!video || !button) {
      return;
    }
    const muted = Boolean(video.muted);
    button.dataset.muted = muted ? "true" : "false";
    button.setAttribute("aria-label", muted ? "Unmute live TV" : "Mute live TV");
    const mutedIcon = button.querySelector(".web-live-mute-icon--muted");
    const soundIcon = button.querySelector(".web-live-mute-icon--sound");
    if (mutedIcon && soundIcon) {
      mutedIcon.style.display = muted ? "block" : "none";
      soundIcon.style.display = muted ? "none" : "block";
    }
  }

  function initMuteToggle(frame) {
    const video = frame.querySelector("video");
    const button = frame.querySelector(".web-live-mute, .live-mute-toggle");
    if (!video || !button || button.dataset.ready === "true") {
      return;
    }
    button.dataset.ready = "true";
    syncMuteButton(frame);
    function toggleMute(event) {
      const now = Date.now();
      if (button.liveMuteLastToggleAt && now - button.liveMuteLastToggleAt < 320) {
        event.preventDefault();
        event.stopPropagation();
        return;
      }
      button.liveMuteLastToggleAt = now;
      event.preventDefault();
      event.stopPropagation();
      frame.dataset.userMuteTouched = "true";
      video.muted = !video.muted;
      syncMuteButton(frame);
      if (video.paused) {
        const playPromise = video.play();
        if (playPromise && typeof playPromise.catch === "function") {
          playPromise.catch(function () {});
        }
      }
    }
    button.addEventListener("click", toggleMute);
    button.addEventListener("touchend", toggleMute, { passive: false });
    video.addEventListener("volumechange", function () {
      syncMuteButton(frame);
    });
  }

  function initLiveTvFrames() {
    initWebTickerSpeeds();
    document.querySelectorAll(".web-live-frame, .live-player-frame").forEach(function (frame) {
      const video = frame.querySelector("video");
      if (video && (frame.classList.contains("web-live-frame--native") || frame.classList.contains("live-player-frame--native-controls"))) {
        video.controls = false;
        video.preload = frame.dataset.forceAutoplay === "true" ? "auto" : "metadata";
        if (frame.dataset.forceAutoplay === "true") {
          video.muted = true;
          video.autoplay = true;
        }
        if (isHlsVideo(video) && !nativeHlsSupported(video)) {
          playNativeLiveVideo(frame, video);
        } else if (video.readyState >= 1) {
          playNativeLiveVideo(frame, video);
        } else {
          video.addEventListener("loadedmetadata", function () {
            playNativeLiveVideo(frame, video);
          }, { once: true });
        }
      }
      initMuteToggle(frame);

      if (video) {
        video.addEventListener("play", function () {
          setFrameControlState(frame, false);
        });
        video.addEventListener("pause", function () {
          if (frame.classList.contains("web-live-frame")) {
            video.controls = false;
            return;
          }
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
