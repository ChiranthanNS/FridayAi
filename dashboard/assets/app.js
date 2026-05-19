/* FRIDAY Dashboard — App Logic */

const API = 'http://localhost:8765';
let ws = null;
let micActive = false;
let recognition = null;
let voiceCtx = null, voiceAnalyser = null, voiceAnim = null;

// ── Boot Sequence ─────────────────────────────────────────────────────────
const BOOT_STEPS = [
  [10, 'Loading neural networks...'],
  [25, 'Connecting to memory core...'],
  [45, 'Initializing emotion engine...'],
  [60, 'Establishing system agent...'],
  [80, 'Syncing with FRIDAY brain...'],
  [95, 'Running diagnostics...'],
  [100, 'All systems online.'],
];

async function runBoot() {
  const bar = document.getElementById('boot-bar');
  const status = document.getElementById('boot-status');
  for (const [pct, msg] of BOOT_STEPS) {
    bar.style.width = pct + '%';
    status.textContent = msg;
    await sleep(350 + Math.random() * 250);
  }
  await sleep(400);
  document.getElementById('boot-screen').classList.add('fade-out');
  await sleep(800);
  document.getElementById('boot-screen').style.display = 'none';
  document.getElementById('app').classList.remove('hidden');
  initApp();
}

// ── Init ──────────────────────────────────────────────────────────────────
function initApp() {
  startClock();
  initParticles();
  connectWebSocket();
  loadMemories();
  loadFacts();
  setupInput();
  setupMic();
}

// ── Clock ─────────────────────────────────────────────────────────────────
function startClock() {
  const updateClock = () => {
    const now = new Date();
    document.getElementById('time-display').textContent =
      now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    document.getElementById('date-display').textContent =
      now.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }).toUpperCase();
  };
  updateClock();
  setInterval(updateClock, 1000);
}

// ── WebSocket ─────────────────────────────────────────────────────────────
function connectWebSocket() {
  const wsUrl = API.replace('http', 'ws') + '/ws';
  ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    setStatus('online', 'ONLINE');
    addSystemMsg('Connected to FRIDAY neural core.');
  };

  ws.onmessage = (evt) => {
    const data = JSON.parse(evt.data);
    handleWsMessage(data);
  };

  ws.onclose = () => {
    setStatus('error', 'DISCONNECTED');
    setTimeout(connectWebSocket, 3000);
  };

  ws.onerror = () => setStatus('error', 'ERROR');

  // Heartbeat
  setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'ping' }));
  }, 30000);
}

function handleWsMessage(data) {
  switch (data.type) {
    case 'connected':
      updateEmotion(data.emotion);
      break;
    case 'status':
      updateStatus(data);
      break;
    case 'chat':
      appendMessage(data.role, data.content, data.emotion, data.timestamp);
      if (data.role === 'friday') setVoiceState('SPEAKING');
      break;
    case 'speech':
      setVoiceState('SPEAKING');
      appendMessage('friday', data.content, data.emotion, data.timestamp);
      setTimeout(() => setVoiceState('LISTENING'), 3000);
      break;
    case 'pong':
      break;
  }
}

// ── Status Updates ────────────────────────────────────────────────────────
function updateStatus(data) {
  updateEmotion(data.emotion);

  const sys = data.system || {};
  if (sys.cpu_percent !== undefined) updateRing('cpu', sys.cpu_percent, sys.cpu_percent + '%');
  if (sys.ram_percent !== undefined) updateRing('ram', sys.ram_percent, sys.ram_percent + '%');
  if (sys.battery_percent !== null && sys.battery_percent !== undefined) {
    updateRing('bat', sys.battery_percent, sys.battery_percent + '%');
  }
  if (sys.disk_percent !== undefined) {
    document.getElementById('disk-fill').style.width = sys.disk_percent + '%';
    document.getElementById('disk-value').textContent = sys.disk_percent + '%';
  }

  const idleMin = data.idle_minutes || 0;
  document.getElementById('idle-time').textContent = idleMin < 1 ? 'Active' : Math.floor(idleMin) + 'm';
  if (data.memory_count) document.getElementById('memory-count').textContent = data.memory_count.toLocaleString();
}

function updateRing(id, percent, label) {
  const circumference = 2 * Math.PI * 42; // r=42
  const filled = (percent / 100) * circumference;
  const circle = document.getElementById(id + '-circle');
  if (circle) {
    circle.style.strokeDasharray = `${filled} ${circumference - filled}`;
    circle.style.strokeDashoffset = circumference * 0.25; // Start from top
  }
  const val = document.getElementById(id + '-value');
  if (val) val.textContent = label;

  // Color warning
  if (percent > 85 && circle) {
    circle.style.stroke = 'var(--red)';
    circle.style.filter = 'drop-shadow(0 0 6px var(--red))';
  } else if (percent > 65 && circle) {
    circle.style.stroke = '#ffa500';
    circle.style.filter = 'drop-shadow(0 0 6px #ffa500)';
  }
}

function updateEmotion(state) {
  if (!state) return;
  const label = document.getElementById('emotion-label');
  const badge = document.getElementById('emotion-badge');
  const icon = document.getElementById('emotion-icon');

  const emotionIcons = {
    happy: '◉', excited: '★', curious: '◎', focused: '◈',
    empathetic: '♡', neutral: '◎', concerned: '⚠', playful: '✦',
    proud: '◆', bored: '○',
  };

  const emotionColors = {
    happy: '#ffd700', excited: '#ff6b35', curious: '#7b68ee',
    focused: '#00ced1', empathetic: '#ff69b4', neutral: '#00d4ff',
    concerned: '#ffa500', playful: '#ff85c2', proud: '#ffd700', bored: '#708090',
  };

  const name = state.emotion || 'neutral';
  label.textContent = name.toUpperCase();
  icon.textContent = emotionIcons[name] || '◎';

  const color = emotionColors[name] || '#00d4ff';
  badge.style.borderColor = color + '60';
  badge.style.boxShadow = `0 0 15px ${color}30`;
  icon.style.color = color;
  label.style.color = color;

  // Emotion bars
  const v = ((state.valence || 0) + 1) / 2 * 100;
  const a = (state.arousal || 0) * 100;
  const r = (state.rapport || 0.5) * 100;
  setBar('em-valence', v, color);
  setBar('em-arousal', a, color);
  setBar('em-rapport', r, null);

  // Orb color
  const core = document.getElementById('orb-core');
  if (core) core.style.borderColor = color;
}

function setBar(id, pct, color) {
  const el = document.getElementById(id);
  if (!el) return;
  el.style.width = Math.max(0, Math.min(100, pct)) + '%';
  if (color) el.style.background = color;
}

// ── Chat ──────────────────────────────────────────────────────────────────
function appendMessage(role, content, emotion, timestamp) {
  const container = document.getElementById('chat-messages');
  const msg = document.createElement('div');
  msg.className = `msg ${role}`;

  const time = timestamp ? new Date(timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }) : '';
  const emotionTag = emotion ? `<span class="msg-emotion">[${emotion}]</span>` : '';

  msg.innerHTML = `
    <div class="msg-bubble">${escapeHtml(content)}</div>
    <div class="msg-meta">
      <span>${role === 'friday' ? 'FRIDAY' : 'YOU'}</span>
      ${emotionTag}
      <span>${time}</span>
    </div>
  `;

  container.appendChild(msg);
  container.scrollTop = container.scrollHeight;

  if (role === 'friday') {
    document.getElementById('voice-orb').classList.add('speaking');
    setTimeout(() => document.getElementById('voice-orb').classList.remove('speaking'), 4000);
  }
}

function addSystemMsg(text) {
  const container = document.getElementById('chat-messages');
  const el = document.createElement('div');
  el.style.cssText = 'text-align:center;font-family:var(--font-mono);font-size:10px;color:var(--text-dim);padding:4px;';
  el.textContent = `— ${text} —`;
  container.appendChild(el);
}

async function sendMessage() {
  const input = document.getElementById('chat-input');
  const text = input.value.trim();
  if (!text) return;
  input.value = '';

  appendMessage('user', text, null, new Date().toISOString());

  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'chat', content: text }));
  } else {
    // Fallback to REST
    try {
      const res = await fetch(`${API}/api/chat`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text })
      });
      const data = await res.json();
      appendMessage('friday', data.response, data.emotion, new Date().toISOString());
    } catch (e) {
      addSystemMsg('Connection error — check if FRIDAY is running.');
    }
  }

  setVoiceState('THINKING');
}

function setupInput() {
  document.getElementById('chat-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
}

// ── Voice / Mic ───────────────────────────────────────────────────────────
function setupMic() {
  if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
    document.getElementById('mic-toggle').style.opacity = '0.3';
    return;
  }

  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SR();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.lang = 'en-IN';

  recognition.onresult = (evt) => {
    const last = evt.results[evt.results.length - 1];
    if (last.isFinal) {
      const text = last[0].transcript.trim();
      if (text.toLowerCase().includes('friday')) {
        document.getElementById('chat-input').value = text;
        sendMessage();
      } else {
        document.getElementById('chat-input').value = text;
      }
    }
  };

  recognition.onend = () => {
    if (micActive) recognition.start();
    setVoiceState('STANDBY');
  };

  document.getElementById('mic-toggle').addEventListener('click', toggleMic);
}

function toggleMic() {
  micActive = !micActive;
  const btn = document.getElementById('mic-toggle');
  if (micActive) {
    recognition && recognition.start();
    btn.classList.add('active');
    setVoiceState('LISTENING');
    startVoiceVisualizer();
  } else {
    recognition && recognition.stop();
    btn.classList.remove('active');
    setVoiceState('STANDBY');
    stopVoiceVisualizer();
  }
}

function setVoiceState(state) {
  document.getElementById('voice-state').textContent = state;
}

// Voice visualizer canvas
function startVoiceVisualizer() {
  navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
    voiceCtx = new AudioContext();
    voiceAnalyser = voiceCtx.createAnalyser();
    voiceCtx.createMediaStreamSource(stream).connect(voiceAnalyser);
    voiceAnalyser.fftSize = 64;

    const canvas = document.getElementById('voice-canvas');
    const ctx = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;
    const buf = new Uint8Array(voiceAnalyser.frequencyBinCount);

    function draw() {
      voiceAnim = requestAnimationFrame(draw);
      voiceAnalyser.getByteFrequencyData(buf);
      ctx.clearRect(0, 0, W, H);
      ctx.strokeStyle = 'rgba(0,212,255,0.6)';
      ctx.lineWidth = 2;
      ctx.beginPath();
      const cx = W / 2, cy = H / 2, r = 30;
      const total = buf.length;
      for (let i = 0; i < total; i++) {
        const angle = (i / total) * Math.PI * 2;
        const amplitude = buf[i] / 255 * 28;
        const rx = cx + Math.cos(angle) * (r + amplitude);
        const ry = cy + Math.sin(angle) * (r + amplitude);
        i === 0 ? ctx.moveTo(rx, ry) : ctx.lineTo(rx, ry);
      }
      ctx.closePath();
      ctx.stroke();
    }
    draw();
  }).catch(() => {});
}

function stopVoiceVisualizer() {
  if (voiceAnim) cancelAnimationFrame(voiceAnim);
  if (voiceCtx) voiceCtx.close();
  const canvas = document.getElementById('voice-canvas');
  canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
}

// ── Memory ────────────────────────────────────────────────────────────────
async function loadMemories(query = '') {
  try {
    const url = query ? `${API}/api/memory?query=${encodeURIComponent(query)}` : `${API}/api/memory?limit=15`;
    const res = await fetch(url);
    const data = await res.json();
    renderMemories(data.memories || []);
  } catch (e) {
    document.getElementById('memory-list').innerHTML = '<div class="memory-loading">Offline</div>';
  }
}

function renderMemories(memories) {
  const list = document.getElementById('memory-list');
  if (!memories.length) { list.innerHTML = '<div class="memory-loading">No memories yet.</div>'; return; }
  list.innerHTML = memories.slice(0, 15).map(m => `
    <div class="memory-item">
      <div class="mem-type">${(m.memory_type || 'memory').toUpperCase()} · ${m.emotion || ''}</div>
      <div class="mem-content">${escapeHtml((m.content || '').substring(0, 120))}</div>
      <div class="mem-date">${m.timestamp ? new Date(m.timestamp).toLocaleDateString() : ''}</div>
    </div>
  `).join('');
}

function searchMemory() {
  const q = document.getElementById('memory-search').value.trim();
  if (q) loadMemories(q);
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('memory-search').addEventListener('keydown', e => {
    if (e.key === 'Enter') searchMemory();
  });
});

// ── Facts ─────────────────────────────────────────────────────────────────
async function loadFacts() {
  try {
    const res = await fetch(`${API}/api/facts`);
    const data = await res.json();
    const list = document.getElementById('facts-list');
    const facts = data.facts || {};
    const keys = Object.keys(facts);
    if (!keys.length) { list.innerHTML = '<div class="facts-loading">No profile data yet.</div>'; return; }
    list.innerHTML = keys.slice(0, 10).map(k => `
      <div class="fact-item">
        <span class="fact-key">${escapeHtml(k)}</span>
        <span class="fact-val">${escapeHtml(String(facts[k]).substring(0, 40))}</span>
      </div>
    `).join('');
  } catch (e) {
    document.getElementById('facts-list').innerHTML = '<div class="facts-loading">Offline</div>';
  }
}

// ── Quick Actions ─────────────────────────────────────────────────────────
async function quickAction(action, params) {
  addSystemMsg(`Executing: ${action}...`);
  try {
    const res = await fetch(`${API}/api/action`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, params })
    });
    const data = await res.json();
    appendMessage('friday', data.output || JSON.stringify(data.data, null, 2), 'focused', new Date().toISOString());
  } catch (e) {
    addSystemMsg('Action failed — check connection.');
  }
}

// ── Particles Background ──────────────────────────────────────────────────
function initParticles() {
  const canvas = document.getElementById('particles-bg');
  const ctx = canvas.getContext('2d');
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;

  const dots = Array.from({ length: 80 }, () => ({
    x: Math.random() * canvas.width, y: Math.random() * canvas.height,
    vx: (Math.random() - 0.5) * 0.3, vy: (Math.random() - 0.5) * 0.3,
    r: Math.random() * 1.5 + 0.5, opacity: Math.random() * 0.4 + 0.1,
  }));

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    dots.forEach(d => {
      d.x += d.vx; d.y += d.vy;
      if (d.x < 0) d.x = canvas.width;
      if (d.x > canvas.width) d.x = 0;
      if (d.y < 0) d.y = canvas.height;
      if (d.y > canvas.height) d.y = 0;
      ctx.beginPath();
      ctx.arc(d.x, d.y, d.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(0,212,255,${d.opacity})`;
      ctx.fill();
    });
    // Draw connections
    for (let i = 0; i < dots.length; i++) {
      for (let j = i + 1; j < dots.length; j++) {
        const dx = dots[i].x - dots[j].x, dy = dots[i].y - dots[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 100) {
          ctx.beginPath();
          ctx.moveTo(dots[i].x, dots[i].y);
          ctx.lineTo(dots[j].x, dots[j].y);
          ctx.strokeStyle = `rgba(0,212,255,${0.08 * (1 - dist / 100)})`;
          ctx.lineWidth = 0.5;
          ctx.stroke();
        }
      }
    }
    requestAnimationFrame(draw);
  }
  draw();

  window.addEventListener('resize', () => {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  });
}

// ── Status helpers ────────────────────────────────────────────────────────
function setStatus(state, text) {
  const dot = document.getElementById('status-dot');
  const label = document.getElementById('status-text');
  dot.className = 'status-dot ' + state;
  label.textContent = text;
}

// Refresh data periodically
setInterval(() => { loadMemories(); loadFacts(); }, 30000);

// ── Utils ─────────────────────────────────────────────────────────────────
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// ── Start ─────────────────────────────────────────────────────────────────
window.addEventListener('load', runBoot);
