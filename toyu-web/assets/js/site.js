/* ─────────────────────────────────────────────────────────
   ToYu 宣传站 · 交互
   零依赖。所有演示功能都在浏览器本地跑，不发任何网络请求
   （只有下载地址是启动时读一次 download.json）。
   ───────────────────────────────────────────────────────── */

(function () {
  'use strict';

  /* ── 工具 ───────────────────────────────────────────── */
  function reduceMotion() {
    return !!(window.matchMedia &&
              window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }

  /* ── 深色模式 ───────────────────────────────────────── */
  var root = document.documentElement;
  var themeBtn = document.getElementById('themeBtn');
  var STORE_KEY = 'toyu-theme';

  function applyTheme(mode) {
    root.setAttribute('data-theme', mode === 'dark' ? 'dark' : 'light');
    if (themeBtn) themeBtn.textContent = mode === 'dark' ? '☀️ 浅色' : '🌙 深色';
  }

  var saved = null;
  try { saved = localStorage.getItem(STORE_KEY); } catch (e) { /* 隐私模式 */ }
  if (!saved) {
    saved = (window.matchMedia &&
             window.matchMedia('(prefers-color-scheme: dark)').matches)
            ? 'dark' : 'light';
  }
  applyTheme(saved);

  if (themeBtn) {
    themeBtn.addEventListener('click', function () {
      var next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      applyTheme(next);
      try { localStorage.setItem(STORE_KEY, next); } catch (e) { /* 忽略 */ }
    });
  }

  /* ── 界面截图切换 ───────────────────────────────────── */
  var shotImg = document.getElementById('shotImg');
  var shotTabs = document.getElementById('shotTabs');
  if (shotImg && shotTabs) {
    shotTabs.addEventListener('click', function (ev) {
      var btn = ev.target.closest('.seg-btn');
      if (!btn) return;
      shotTabs.querySelectorAll('.seg-btn').forEach(function (b) {
        b.classList.toggle('is-on', b === btn);
      });
      var name = btn.getAttribute('data-shot');
      // 切换前先预载，避免白屏闪一下
      var pre = new Image();
      pre.onload = function () { shotImg.src = pre.src; };
      pre.src = 'assets/img/' + name + '.png';
    });
  }

  /* ── 专注计时 ───────────────────────────────────────── */
  var RING_LEN = 327;              // 2πr, r = 52
  var ringFill = document.getElementById('ringFill');
  var timerText = document.getElementById('timerText');
  var tStart = document.getElementById('tStart');
  var tReset = document.getElementById('tReset');
  var timerChips = document.querySelectorAll('.timer-btns .chip');

  var tState = {
    totalMs: 25 * 60 * 1000,
    endAt: 0,          // 结束时间戳（0 = 未开始）
    pausedLeft: 0,
    running: false,
    tick: null
  };

  function fmt(ms) {
    ms = Math.max(0, ms);
    var s = Math.ceil(ms / 1000);
    var m = Math.floor(s / 60);
    var r = s % 60;
    return (m < 10 ? '0' : '') + m + ':' + (r < 10 ? '0' : '') + r;
  }

  function paintTimer(leftMs) {
    var ratio = tState.totalMs > 0 ? 1 - leftMs / tState.totalMs : 0;
    ratio = Math.max(0, Math.min(1, ratio));
    if (ringFill) ringFill.style.strokeDashoffset = String(RING_LEN * (1 - ratio));
    if (timerText) timerText.textContent = fmt(leftMs);
  }

  function stopTick() {
    if (tState.tick) { clearInterval(tState.tick); tState.tick = null; }
  }

  function leftNow() {
    if (!tState.running) return tState.pausedLeft;
    return Math.max(0, tState.endAt - Date.now());
  }

  function startTimer() {
    if (tState.running) {           // 暂停
      tState.pausedLeft = leftNow();
      tState.running = false;
      stopTick();
      if (tStart) tStart.textContent = '继续';
      return;
    }
    // 关键：用「结束时间戳」而不是累加，切标签页/休眠回来依然准确
    var left = tState.pausedLeft > 0 ? tState.pausedLeft : tState.totalMs;
    tState.endAt = Date.now() + left;
    tState.running = true;
    if (tStart) tStart.textContent = '暂停';
    stopTick();
    tState.tick = setInterval(function () {
      var l = leftNow();
      paintTimer(l);
      if (l <= 0) {
        stopTick();
        tState.running = false;
        tState.pausedLeft = 0;
        if (tStart) tStart.textContent = '开始';
        if (timerText) timerText.textContent = '完成!';
        if (ringFill) ringFill.style.stroke = 'var(--ok)';
      }
    }, 200);
    paintTimer(left);
  }

  function setMinutes(min) {
    stopTick();
    tState.running = false;
    tState.totalMs = min * 60 * 1000;
    tState.pausedLeft = 0;
    if (tStart) tStart.textContent = '开始';
    if (ringFill) {
      ringFill.style.stroke = 'var(--accent)';
      ringFill.style.strokeDashoffset = String(RING_LEN);
    }
    paintTimer(tState.totalMs);
  }

  if (timerChips.length) {
    timerChips.forEach(function (chip) {
      chip.addEventListener('click', function () {
        timerChips.forEach(function (c) { c.classList.toggle('is-on', c === chip); });
        setMinutes(parseInt(chip.getAttribute('data-min'), 10) || 25);
      });
    });
    timerChips[0].classList.add('is-on');
  }
  if (tStart) tStart.addEventListener('click', startTimer);
  if (tReset) tReset.addEventListener('click', function () {
    setMinutes(Math.round(tState.totalMs / 60000) || 25);
  });

  /* ── 每日目标 ───────────────────────────────────────── */
  var GOAL_LEN = 264;              // 2πr, r = 42
  var goalFill = document.getElementById('goalFill');
  var goalPct = document.getElementById('goalPct');
  var goalRange = document.getElementById('goalRange');
  var goalLabel = document.getElementById('goalLabel');
  var goalDone = document.getElementById('goalDone');
  var rmStudy = document.getElementById('rmStudy');
  var addStudy = document.getElementById('addStudy');
  var resetStudy = document.getElementById('resetStudy');

  var studyMin = 0;

  function paintGoal() {
    var goal = goalRange ? parseInt(goalRange.value, 10) : 120;
    var ratio = goal > 0 ? Math.min(1, studyMin / goal) : 0;
    if (goalFill) {
      goalFill.style.strokeDashoffset = String(GOAL_LEN * (1 - ratio));
      goalFill.style.stroke = ratio >= 1 ? 'var(--ok)' : 'var(--accent)';
    }
    if (goalPct) goalPct.textContent = Math.round(ratio * 100) + '%';
    if (goalLabel) goalLabel.textContent = goal + ' 分钟';
    if (goalDone) {
      goalDone.textContent = '已完成 ' + studyMin + ' 分钟' +
        (ratio >= 1 ? ' · 达成 🎉' : '');
    }
    if (rmStudy) rmStudy.textContent = studyMin + ' 分钟';
  }

  if (goalRange) goalRange.addEventListener('input', paintGoal);
  if (addStudy) addStudy.addEventListener('click', function () {
    studyMin += 15; paintGoal();
  });
  if (resetStudy) resetStudy.addEventListener('click', function () {
    studyMin = 0; paintGoal();
  });
  paintGoal();

  /* ── 报告日期 ───────────────────────────────────────── */
  var rmDate = document.getElementById('rmDate');
  if (rmDate) {
    var d = new Date();
    rmDate.textContent = d.getFullYear() + '-' +
      String(d.getMonth() + 1).padStart(2, '0') + '-' +
      String(d.getDate()).padStart(2, '0');
  }

  /* ── 下载信息（读 download.json，缺失则优雅降级）───── */
  var dlBtn = document.getElementById('dlBtn');
  var dlHint = document.getElementById('dlHint');
  var dlVersion = document.getElementById('dlVersion');
  var dlSize = document.getElementById('dlSize');
  var dlBtnVer = document.getElementById('dlBtnVer');

  function setDownload(cfg) {
    var ver = cfg.version || 'v0.80.0';
    if (dlVersion) dlVersion.textContent = ver;
    if (dlBtnVer) dlBtnVer.textContent = ver;
    if (dlSize && cfg.size) dlSize.textContent = cfg.size;

    var hasUrl = !!(cfg.url && cfg.url !== '#download');
    if (dlBtn && hasUrl) {
      dlBtn.setAttribute('href', cfg.url);
      dlBtn.setAttribute('rel', 'noopener');
      if (cfg.external) dlBtn.setAttribute('target', '_blank');
    }
    if (dlHint) {
      // 没配地址时给访客一句得体的话，而不是把部署提示露出来
      dlHint.textContent = hasUrl
        ? (cfg.note || '')
        : (cfg.noteEmpty || '下载通道准备中。');
      dlHint.classList.toggle('is-err', !!cfg.error);
    }
    if (!hasUrl && dlBtn) {
      // 未配置时不要让人点了没反应：降级为跳到在线体验
      dlBtn.setAttribute('href', '#demo');
      dlBtn.style.opacity = '.6';
      if (dlBtn.lastChild) dlBtn.lastChild.textContent = '（通道准备中）';
    }
  }

  function loadDownload() {
    fetch('download.json', { cache: 'no-store' })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(setDownload)
      .catch(function () {
        // 本地 file:// 打开或静态预览时 fetch 会失败，降级即可
        setDownload({
          version: 'v0.80.0',
          size: '67.4 MB',
          url: '#demo',
          noteEmpty: '下载通道准备中。可先在线体验下面的功能。'
        });
      });
  }
  loadDownload();

  /* ── 首屏小卡片轻微视差 ─────────────────────────────── */
  var heroArt = document.querySelector('.hero-art');
  if (heroArt && !reduceMotion() && window.matchMedia('(pointer: fine)').matches) {
    var cards = heroArt.querySelectorAll('.float-card');
    heroArt.addEventListener('mousemove', function (ev) {
      var box = heroArt.getBoundingClientRect();
      var dx = (ev.clientX - box.left) / box.width - 0.5;
      var dy = (ev.clientY - box.top) / box.height - 0.5;
      cards.forEach(function (c, i) {
        var k = (i + 1) * 7;
        c.style.transform = 'translate(' + (-dx * k) + 'px,' + (-dy * k) + 'px)';
      });
    });
    heroArt.addEventListener('mouseleave', function () {
      cards.forEach(function (c) { c.style.transform = ''; });
    });
  }

  /* ── 数字滚动 ───────────────────────────────────────── */
  var statsInner = document.querySelector('.stats-inner');
  if (statsInner && !reduceMotion()) {
    var counted = false;
    var io2 = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting || counted) return;
        counted = true;
        statsInner.querySelectorAll('.stat b').forEach(function (el) {
          var target = parseInt(el.getAttribute('data-count'), 10) || 0;
          var suffix = el.getAttribute('data-suffix') || '';
          var t0 = null;
          function step(ts) {
            if (!t0) t0 = ts;
            var p = Math.min(1, (ts - t0) / 900);
            // easeOutCubic
            var v = Math.round(target * (1 - Math.pow(1 - p, 3)));
            el.textContent = v + suffix;
            if (p < 1) requestAnimationFrame(step);
          }
          requestAnimationFrame(step);
        });
        io2.disconnect();
      });
    }, { threshold: .4 });
    io2.observe(statsInner);
  }

  /* ── 滚动渐显 ───────────────────────────────────────── */
  var revealTargets = document.querySelectorAll(
    '.sec-head, .card, .ai-card, .demo-card, .agent-chat, .side-card,' +
    ' .vision-box, .dl-box, .shot-frame, .theme-compare, .tc-item, .faq, .notice');
  if (revealTargets.length && !reduceMotion() && 'IntersectionObserver' in window) {
    revealTargets.forEach(function (el, i) {
      el.classList.add('reveal');
      // 同组内错开一点，避免整屏一起弹
      el.style.transitionDelay = (Math.min(i % 6, 5) * 55) + 'ms';
    });
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) {
          en.target.classList.add('is-in');
          io.unobserve(en.target);
        }
      });
    }, { threshold: .12, rootMargin: '0px 0px -40px 0px' });
    revealTargets.forEach(function (el) { io.observe(el); });
  }

  /* ── 导航阴影：滚动后才出现 ─────────────────────────── */
  var nav = document.getElementById('nav');
  if (nav) {
    var onScroll = function () {
      nav.style.boxShadow = window.scrollY > 6
        ? '0 4px 18px rgba(80,50,20,.07)' : 'none';
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }
})();
