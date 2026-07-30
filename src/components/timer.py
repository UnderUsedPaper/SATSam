"""The persistent focus timer.

One HTML/JS timer, rendered full-size on the Focus Timer page and as a compact
widget in the sidebar on every other page. Both read and write the same
localStorage key, so a session started anywhere stays visible everywhere.
"""

import streamlit as st
import streamlit.components.v1 as components


FOCUS_TIMER_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  * { box-sizing: border-box; }
  body { margin:0; padding:0; background:transparent; font-family:Arial, sans-serif; color:#28241F; }
  .timer-shell { width:100%; padding:22px 18px 10px 18px; text-align:center; }
  .timer-ring { width:230px; height:230px; margin:0 auto; position:relative; display:flex; align-items:center; justify-content:center; }
  .timer-ring svg { position:absolute; width:230px; height:230px; transform:rotate(-90deg); }
  .timer-ring circle { fill:none; stroke-width:10; }
  .ring-background { stroke:#E9DFD4; }
  .ring-progress { stroke:#C9694A; stroke-linecap:round; transition:stroke-dashoffset 0.3s linear; }
  .timer-content { position:relative; z-index:2; }
  .time-display { font-family:Georgia, serif; font-size:48px; font-weight:600; letter-spacing:-1px; color:#28241F; }
  .timer-status { margin-top:7px; font-size:13px; font-weight:600; color:#746D63; }
  .button-row { display:grid; grid-template-columns:1fr 1fr 1fr; gap:10px; max-width:520px; margin:24px auto 0 auto; }
  button { min-height:44px; border-radius:12px; border:1px solid #E6DDD1; font-size:13px; font-weight:700; cursor:pointer; transition:transform 0.15s ease, background 0.15s ease; }
  button:hover { transform:translateY(-1px); }
  .start-button { color:white; background:#C9694A; border-color:#C9694A; }
  .start-button:hover { background:#A95036; }
  .pause-button, .reset-button { color:#28241F; background:#FFFDF8; }
  .pause-button:hover, .reset-button:hover { background:#F7EFE6; }
  .session-message { min-height:22px; margin-top:18px; font-size:13px; font-weight:600; color:#6F856F; }
  .tip { max-width:520px; margin:16px auto 0 auto; padding:13px 15px; border-radius:12px; background:#F5E7BC; color:#705D34; font-size:12px; line-height:1.5; text-align:left; }
  @media (max-width:520px) {
    .timer-ring, .timer-ring svg { width:190px; height:190px; }
    .time-display { font-size:40px; }
    .button-row { grid-template-columns:1fr; }
  }
</style>
</head>
<body>
  <div class="timer-shell">
    <div class="timer-ring">
      <svg viewBox="0 0 240 240">
        <circle class="ring-background" cx="120" cy="120" r="104"></circle>
        <circle id="progressCircle" class="ring-progress" cx="120" cy="120" r="104"></circle>
      </svg>
      <div class="timer-content">
        <div id="timeDisplay" class="time-display">__LENGTH__:00</div>
        <div id="timerStatus" class="timer-status">Ready to focus</div>
      </div>
    </div>
    <div class="button-row">
      <button id="startButton" class="start-button" onclick="startTimer()">Start</button>
      <button id="pauseButton" class="pause-button" onclick="pauseTimer()">Pause</button>
      <button class="reset-button" onclick="resetTimer()">Reset</button>
    </div>
    <div id="sessionMessage" class="session-message"></div>
    <div class="tip">Keep only what you need for this session open. When the timer ends, take a short, kind break before starting another focused block.</div>
  </div>
  <script>
    const storageKey = "satsam_focus_timer_v2";
    const selectedDuration = __SECONDS__;
    const timeDisplay = document.getElementById("timeDisplay");
    const timerStatus = document.getElementById("timerStatus");
    const sessionMessage = document.getElementById("sessionMessage");
    const startButton = document.getElementById("startButton");
    const progressCircle = document.getElementById("progressCircle");
    const radius = 104;
    const circumference = 2 * Math.PI * radius;
    progressCircle.style.strokeDasharray = circumference;
    let timerInterval = null;
    let timerState = { duration: selectedDuration, remaining: selectedDuration, running: false, completed: false, endTime: null };
    function saveState() { localStorage.setItem(storageKey, JSON.stringify(timerState)); }
    function loadState() {
      const savedState = localStorage.getItem(storageKey);
      if (!savedState) { saveState(); return; }
      try {
        const p = JSON.parse(savedState);
        timerState = {
          duration: Number(p.duration) || selectedDuration,
          remaining: Number(p.remaining) || selectedDuration,
          running: Boolean(p.running),
          completed: Boolean(p.completed),
          endTime: p.endTime ? Number(p.endTime) : null
        };
        if (!timerState.running && !timerState.completed && timerState.remaining === timerState.duration && timerState.duration !== selectedDuration) {
          timerState.duration = selectedDuration;
          timerState.remaining = selectedDuration;
          timerState.endTime = null;
          saveState();
        }
      } catch (error) {
        timerState = { duration: selectedDuration, remaining: selectedDuration, running: false, completed: false, endTime: null };
        saveState();
      }
    }
    function calculateRemainingTime() {
      if (timerState.running && timerState.endTime) {
        timerState.remaining = Math.max(0, Math.ceil((timerState.endTime - Date.now()) / 1000));
      }
      return timerState.remaining;
    }
    function formatTime(totalSeconds) {
      const safeSeconds = Math.max(0, totalSeconds);
      const minutes = Math.floor(safeSeconds / 60);
      const seconds = safeSeconds % 60;
      return String(minutes).padStart(2, "0") + ":" + String(seconds).padStart(2, "0");
    }
    function updateDisplay() {
      const remaining = calculateRemainingTime();
      timeDisplay.textContent = formatTime(remaining);
      const duration = Math.max(timerState.duration, 1);
      const elapsed = duration - remaining;
      const progress = Math.min(Math.max(elapsed / duration, 0), 1);
      progressCircle.style.strokeDashoffset = circumference * progress;
      if (timerState.completed) {
        timerStatus.textContent = "Session complete";
        sessionMessage.textContent = "Wonderful focus. Take a short, intentional break.";
        startButton.textContent = "Complete";
      } else if (timerState.running) {
        timerStatus.textContent = "Focus in progress";
        sessionMessage.textContent = "";
        startButton.textContent = "Running";
      } else if (timerState.remaining < timerState.duration) {
        timerStatus.textContent = "Session paused";
        sessionMessage.textContent = "";
        startButton.textContent = "Resume";
      } else {
        timerStatus.textContent = "Ready to focus";
        sessionMessage.textContent = "";
        startButton.textContent = "Start";
      }
    }
    function startTimer() {
      if (timerState.running || timerState.completed || timerState.remaining <= 0) { return; }
      timerState.running = true;
      timerState.endTime = Date.now() + timerState.remaining * 1000;
      saveState(); updateDisplay(); beginInterval();
    }
    function pauseTimer() {
      if (!timerState.running) { return; }
      calculateRemainingTime();
      timerState.running = false;
      timerState.endTime = null;
      clearTimerInterval(); saveState(); updateDisplay();
    }
    function resetTimer() {
      clearTimerInterval();
      timerState = { duration: selectedDuration, remaining: selectedDuration, running: false, completed: false, endTime: null };
      saveState(); updateDisplay();
    }
    function completeTimer(playSound) {
      clearTimerInterval();
      timerState.remaining = 0;
      timerState.running = false;
      timerState.completed = true;
      timerState.endTime = null;
      saveState(); updateDisplay();
      if (playSound) { playCompletionSound(); }
    }
    function clearTimerInterval() {
      if (timerInterval !== null) { clearInterval(timerInterval); timerInterval = null; }
    }
    function beginInterval() {
      clearTimerInterval();
      timerInterval = setInterval(() => {
        const remaining = calculateRemainingTime();
        if (remaining <= 0) { completeTimer(true); return; }
        saveState(); updateDisplay();
      }, 250);
    }
    function playCompletionSound() {
      try {
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        const audioContext = new AudioContextClass();
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();
        oscillator.connect(gainNode); gainNode.connect(audioContext.destination);
        oscillator.frequency.value = 660; oscillator.type = "sine";
        gainNode.gain.setValueAtTime(0.14, audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.001, audioContext.currentTime + 1.2);
        oscillator.start(); oscillator.stop(audioContext.currentTime + 1.2);
      } catch (error) {}
    }
    loadState();
    if (timerState.running && timerState.endTime) {
      calculateRemainingTime();
      if (timerState.remaining <= 0) { completeTimer(false); } else { saveState(); updateDisplay(); beginInterval(); }
    } else { updateDisplay(); }
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") {
        if (timerState.running && timerState.endTime) {
          calculateRemainingTime();
          if (timerState.remaining <= 0) { completeTimer(false); } else { updateDisplay(); beginInterval(); }
        }
      }
    });
  </script>
</body>
</html>
"""


MINI_TIMER_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  * { box-sizing: border-box; }
  body { margin:0; padding:0; background:transparent; font-family:Arial, sans-serif; color:#28241F; }
  .mini { padding:2px 2px 6px 2px; }
  .mini-top { display:flex; align-items:center; gap:11px; }
  .mini-ring { position:relative; width:62px; height:62px; flex:0 0 62px; }
  .mini-ring svg { position:absolute; width:62px; height:62px; transform:rotate(-90deg); }
  .mini-ring circle { fill:none; stroke-width:6; }
  .mini-bg { stroke:#E4DACE; }
  .mini-fg { stroke:#C9694A; stroke-linecap:round; transition:stroke-dashoffset 0.3s linear; }
  .mini-time { font-family:Georgia, serif; font-size:19px; font-weight:600; line-height:1; color:#28241F; }
  .mini-status { font-size:11px; color:#8B8175; margin-top:4px; font-weight:600; }
  .mini-btns { display:flex; gap:6px; margin-top:11px; }
  .mini-btns button { flex:1; min-height:31px; border-radius:9px; border:1px solid #E0D5C7; background:#FFFDF8; color:#28241F; font-size:11px; font-weight:700; cursor:pointer; }
  .mini-btns button:hover { background:#F7EFE6; }
  .mini-btns .go { background:#C9694A; color:#fff; border-color:#C9694A; }
  .mini-btns .go:hover { background:#A95036; }
</style>
</head>
<body>
  <div class="mini">
    <div class="mini-top">
      <div class="mini-ring">
        <svg viewBox="0 0 62 62">
          <circle class="mini-bg" cx="31" cy="31" r="27"></circle>
          <circle id="mfg" class="mini-fg" cx="31" cy="31" r="27"></circle>
        </svg>
      </div>
      <div>
        <div id="mtime" class="mini-time">__LENGTH__:00</div>
        <div id="mstatus" class="mini-status">Ready</div>
      </div>
    </div>
    <div class="mini-btns">
      <button id="mgo" class="go" onclick="mStart()">Start</button>
      <button onclick="mPause()">Pause</button>
      <button onclick="mReset()">Reset</button>
    </div>
  </div>
  <script>
    const KEY = "satsam_focus_timer_v2";
    const SEL = __SECONDS__;
    const R = 27, C = 2 * Math.PI * R;
    const fg = document.getElementById("mfg");
    fg.style.strokeDasharray = C;
    const tEl = document.getElementById("mtime");
    const sEl = document.getElementById("mstatus");
    const goEl = document.getElementById("mgo");
    let iv = null;
    let s = { duration: SEL, remaining: SEL, running: false, completed: false, endTime: null };
    function save() { localStorage.setItem(KEY, JSON.stringify(s)); }
    function load() {
      const raw = localStorage.getItem(KEY);
      if (!raw) { save(); return; }
      try {
        const p = JSON.parse(raw);
        s = {
          duration: Number(p.duration) || SEL,
          remaining: Number(p.remaining) || SEL,
          running: Boolean(p.running),
          completed: Boolean(p.completed),
          endTime: p.endTime ? Number(p.endTime) : null
        };
        if (!s.running && !s.completed && s.remaining === s.duration && s.duration !== SEL) {
          s.duration = SEL; s.remaining = SEL; s.endTime = null; save();
        }
      } catch (e) {
        s = { duration: SEL, remaining: SEL, running: false, completed: false, endTime: null };
        save();
      }
    }
    function rem() {
      if (s.running && s.endTime) { s.remaining = Math.max(0, Math.ceil((s.endTime - Date.now()) / 1000)); }
      return s.remaining;
    }
    function fmt(x) {
      x = Math.max(0, x);
      const m = Math.floor(x / 60), ss = x % 60;
      return String(m).padStart(2, "0") + ":" + String(ss).padStart(2, "0");
    }
    function draw() {
      const r = rem();
      tEl.textContent = fmt(r);
      const d = Math.max(s.duration, 1);
      const p = Math.min(Math.max((d - r) / d, 0), 1);
      fg.style.strokeDashoffset = C * p;
      if (s.completed) { sEl.textContent = "Complete"; goEl.textContent = "Done"; }
      else if (s.running) { sEl.textContent = "Focusing…"; goEl.textContent = "Running"; }
      else if (s.remaining < s.duration) { sEl.textContent = "Paused"; goEl.textContent = "Resume"; }
      else { sEl.textContent = "Ready"; goEl.textContent = "Start"; }
    }
    function clr() { if (iv) { clearInterval(iv); iv = null; } }
    function tick() {
      clr();
      iv = setInterval(() => {
        const r = rem();
        if (r <= 0) { done(true); return; }
        save(); draw();
      }, 250);
    }
    function mStart() {
      if (s.running || s.completed || s.remaining <= 0) { return; }
      s.running = true; s.endTime = Date.now() + s.remaining * 1000;
      save(); draw(); tick();
    }
    function mPause() {
      if (!s.running) { return; }
      rem(); s.running = false; s.endTime = null; clr(); save(); draw();
    }
    function mReset() {
      clr();
      s = { duration: SEL, remaining: SEL, running: false, completed: false, endTime: null };
      save(); draw();
    }
    function done(sound) {
      clr(); s.remaining = 0; s.running = false; s.completed = true; s.endTime = null;
      save(); draw(); if (sound) { beep(); }
    }
    function beep() {
      try {
        const A = window.AudioContext || window.webkitAudioContext;
        const c = new A();
        const o = c.createOscillator(), g = c.createGain();
        o.connect(g); g.connect(c.destination);
        o.frequency.value = 660; o.type = "sine";
        g.gain.setValueAtTime(0.14, c.currentTime);
        g.gain.exponentialRampToValueAtTime(0.001, c.currentTime + 1.2);
        o.start(); o.stop(c.currentTime + 1.2);
      } catch (e) {}
    }
    load();
    if (s.running && s.endTime) {
      rem();
      if (s.remaining <= 0) { done(false); } else { draw(); tick(); }
    } else { draw(); }
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible" && s.running && s.endTime) {
        rem();
        if (s.remaining <= 0) { done(false); } else { draw(); tick(); }
      }
    });
  </script>
</body>
</html>
"""


def render_focus_timer(length):
    length = int(length)
    html = (
        FOCUS_TIMER_TEMPLATE
        .replace("__LENGTH__", str(length))
        .replace("__SECONDS__", str(length * 60))
    )
    components.html(html, height=430, scrolling=False)


def render_mini_timer():
    length = int(st.session_state.get("timer_length", 25))
    html = (
        MINI_TIMER_TEMPLATE
        .replace("__LENGTH__", str(length))
        .replace("__SECONDS__", str(length * 60))
    )
    components.html(html, height=140, scrolling=False)
