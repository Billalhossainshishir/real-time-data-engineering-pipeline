'use strict';

const $ = (id) => document.getElementById(id);
const ROOM_IDS = Array.from({ length: 10 }, (_, i) => `ROOM-${String(i + 1).padStart(2, '0')}`);
const MAX_READINGS = 120;
const DISPLAY_READINGS = 14;
const INTERVAL_MS = 1100;

const roomProfiles = Object.fromEntries(ROOM_IDS.map((id, i) => [id, {
  temp: 20.4 + (i % 5) * 0.85,
  humidity: 42 + (i % 4) * 4.5,
  energy: 0.8 + (i % 6) * 0.42,
}]));

const state = {
  running: false,
  timer: null,
  readings: [],
  alerts: [],
  deadLetters: [],
  activity: [],
  eventTimes: [],
  throughputBuckets: [],
  roomLatest: {},
  totalAccepted: 0,
  latestAcceptedAt: null,
};

function rand(min, max) { return Math.random() * (max - min) + min; }
function round(value, digits = 1) { return Number(value.toFixed(digits)); }
function nowIso() { return new Date().toISOString(); }
function timeOnly(ts) { return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }); }

function addActivity(type, message) {
  state.activity.unshift({ type, message, timestamp: nowIso() });
  state.activity = state.activity.slice(0, 20);
}

function normalEvent(deviceId = ROOM_IDS[Math.floor(Math.random() * ROOM_IDS.length)]) {
  const p = roomProfiles[deviceId];
  const wave = Math.sin(Date.now() / 18000 + Number(deviceId.slice(-2))) * 0.35;
  return {
    device_id: deviceId,
    temperature: round(p.temp + wave + rand(-0.65, 0.65), 1),
    humidity: round(p.humidity + rand(-3.2, 3.2), 1),
    energy_usage: round(Math.max(0.2, p.energy + rand(-0.35, 0.55)), 2),
    timestamp: nowIso(),
  };
}

function anomalyEvent() {
  const event = normalEvent();
  const kind = ['temperature', 'humidity', 'energy'][Math.floor(Math.random() * 3)];
  if (kind === 'temperature') event.temperature = Math.random() > .3 ? 42.0 : 7.5;
  if (kind === 'humidity') event.humidity = Math.random() > .3 ? 95.0 : 9.0;
  if (kind === 'energy') event.energy_usage = 11.5;
  return event;
}

function invalidEvent() {
  const examples = [
    { device_id: 'ROOM-X7', temperature: 22.1, humidity: 55, energy_usage: 2.1, timestamp: nowIso() },
    { device_id: 'ROOM-04', temperature: 21.6, humidity: 135, energy_usage: 1.9, timestamp: nowIso() },
    { device_id: 'ROOM-08', temperature: 'hot', humidity: 58, energy_usage: -2, timestamp: 'not-a-timestamp' },
  ];
  return examples[Math.floor(Math.random() * examples.length)];
}

function validateEvent(e) {
  const errors = [];
  if (!/^ROOM-\d{2}$/.test(String(e.device_id ?? '')) || !ROOM_IDS.includes(e.device_id)) errors.push('device_id must match a registered ROOM-XX device');
  if (typeof e.temperature !== 'number' || !Number.isFinite(e.temperature)) errors.push('temperature must be numeric');
  if (typeof e.humidity !== 'number' || e.humidity < 0 || e.humidity > 100) errors.push('humidity must be between 0 and 100');
  if (typeof e.energy_usage !== 'number' || e.energy_usage < 0) errors.push('energy_usage cannot be negative');
  if (Number.isNaN(Date.parse(e.timestamp))) errors.push('timestamp must be ISO-8601');
  return errors;
}

function rollingStats(deviceId, field) {
  const values = state.readings.filter(r => r.device_id === deviceId && !r.anomaly).slice(-18).map(r => Number(r[field])).filter(Number.isFinite);
  if (values.length < 7) return null;
  const mean = values.reduce((a,b) => a+b, 0) / values.length;
  const variance = values.reduce((acc, v) => acc + (v - mean) ** 2, 0) / values.length;
  const sd = Math.sqrt(variance);
  return { mean, sd };
}

function detectAnomaly(e) {
  const reasons = [];
  if (e.temperature > 35 || e.temperature < 10) reasons.push(`temperature=${e.temperature}°C`);
  if (e.humidity > 85 || e.humidity < 15) reasons.push(`humidity=${e.humidity}%`);
  if (e.energy_usage > 7.5) reasons.push(`energy=${e.energy_usage} kW`);
  if (reasons.length) return { anomaly: true, method: 'Rule threshold', reason: reasons.join(', '), severity: (e.temperature > 40 || e.energy_usage > 10) ? 'Critical' : 'High' };

  const checks = [
    ['temperature', '°C'], ['humidity', '%'], ['energy_usage', ' kW']
  ];
  for (const [field, unit] of checks) {
    const stats = rollingStats(e.device_id, field);
    if (!stats || stats.sd < 0.08) continue;
    const z = Math.abs((e[field] - stats.mean) / stats.sd);
    if (z >= 3.0) return { anomaly: true, method: 'Rolling 3σ', reason: `${field}=${e[field]}${unit} (${z.toFixed(1)}σ from recent mean)`, severity: 'High' };
  }
  return { anomaly: false, method: null, reason: null, severity: null };
}

function processEvent(payload, { quiet = false } = {}) {
  addActivity('INGEST', `${payload.device_id ?? 'UNKNOWN'} event received`);
  const errors = validateEvent(payload);
  if (errors.length) {
    state.deadLetters.unshift({ payload, errors, timestamp: nowIso() });
    state.deadLetters = state.deadLetters.slice(0, 20);
    addActivity('DEAD LETTER', `Payload rejected: ${errors[0]}`);
    if (!quiet) showToast('Invalid event rejected and moved to the dead-letter queue.', 'warning');
    render();
    return false;
  }

  addActivity('VALIDATED', `${payload.device_id} passed schema checks`);
  const detection = detectAnomaly(payload);
  const event = { ...payload, ...detection, accepted_at: nowIso() };
  state.readings.push(event);
  if (state.readings.length > MAX_READINGS) state.readings.shift();
  state.roomLatest[payload.device_id] = event;
  state.totalAccepted += 1;
  state.latestAcceptedAt = new Date();
  state.eventTimes.push(Date.now());
  state.eventTimes = state.eventTimes.filter(t => t > Date.now() - 60000);
  addActivity('STORED', `${payload.device_id} reading persisted`);

  if (detection.anomaly) {
    state.alerts.unshift({ device_id: payload.device_id, ...detection, created_at: nowIso() });
    state.alerts = state.alerts.slice(0, 30);
    addActivity('ALERT', `${detection.severity} anomaly created for ${payload.device_id}`);
    if (!quiet) showToast(`${detection.severity} anomaly detected on ${payload.device_id}: ${detection.reason}`, 'danger');
  }
  render();
  return true;
}

function seedDemo() {
  ROOM_IDS.forEach(id => {
    for (let i = 0; i < 2; i++) {
      const e = normalEvent(id);
      e.timestamp = new Date(Date.now() - ((2 - i) * 8500 + Math.random() * 3000)).toISOString();
      processEvent(e, { quiet: true });
    }
  });
  state.activity = [
    { type: 'READY', message: '10 devices registered and demo seeded', timestamp: nowIso() },
    { type: 'INFO', message: 'Click Start Simulation to begin live ingestion', timestamp: nowIso() },
  ];
}

function startSimulation() {
  if (state.running) return;
  state.running = true;
  addActivity('START', 'Live sensor simulation started');
  $('demoStatus').textContent = 'Streaming';
  $('statusPill').textContent = 'RUNNING';
  $('statusPill').className = 'status-pill running';
  $('streamBadge').textContent = 'STREAMING';
  $('streamBadge').className = 'stream-badge running';
  document.querySelector('.pipeline-strip').classList.add('running');
  state.timer = setInterval(() => processEvent(normalEvent()), INTERVAL_MS);
  processEvent(normalEvent());
  showToast('Simulation started. Sensor events are now flowing through the pipeline.');
  render();
}

function pauseSimulation() {
  state.running = false;
  if (state.timer) clearInterval(state.timer);
  state.timer = null;
  addActivity('PAUSE', 'Sensor simulation paused');
  $('demoStatus').textContent = 'Paused';
  $('statusPill').textContent = 'PAUSED';
  $('statusPill').className = 'status-pill paused';
  $('streamBadge').textContent = 'WAITING';
  $('streamBadge').className = 'stream-badge';
  document.querySelector('.pipeline-strip').classList.remove('running');
  showToast('Simulation paused. Existing data remains visible.');
  render();
}

function injectAnomaly() {
  const e = anomalyEvent();
  processEvent(e);
}

function injectInvalid() {
  processEvent(invalidEvent());
}

function resetDemo() {
  pauseSimulation();
  state.readings = [];
  state.alerts = [];
  state.deadLetters = [];
  state.activity = [];
  state.eventTimes = [];
  state.throughputBuckets = [];
  state.roomLatest = {};
  state.totalAccepted = 0;
  state.latestAcceptedAt = null;
  seedDemo();
  $('demoStatus').textContent = 'Ready';
  render();
  showToast('Demo reset to a clean baseline.');
}

function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
function baseChartOptions() {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    interaction: { intersect: false, mode: 'index' },
    plugins: {
      legend: { display: false },
      tooltip: { backgroundColor: '#102236', borderColor: 'rgba(130,170,210,.22)', borderWidth: 1, titleColor: '#d8e8f6', bodyColor: '#9fb5ca', displayColors: false }
    },
    scales: {
      x: { grid: { color: 'rgba(124,159,196,.06)' }, ticks: { color: '#5f7891', maxTicksLimit: 7, font: { size: 9 } } },
      y: { grid: { color: 'rgba(124,159,196,.08)' }, ticks: { color: '#5f7891', font: { size: 9 } } }
    }
  };
}

const tempChart = new Chart($('tempChart'), {
  type: 'line',
  data: { labels: [], datasets: [{ data: [], borderColor: cssVar('--cyan'), backgroundColor: 'rgba(85,224,210,.08)', fill: true, tension: .34, pointRadius: 1.4, pointHoverRadius: 4, borderWidth: 1.8 }] },
  options: baseChartOptions()
});
const energyChart = new Chart($('energyChart'), {
  type: 'line',
  data: { labels: [], datasets: [{ data: [], borderColor: cssVar('--purple'), backgroundColor: 'rgba(154,140,255,.08)', fill: true, tension: .34, pointRadius: 1.4, pointHoverRadius: 4, borderWidth: 1.8 }] },
  options: baseChartOptions()
});
const throughputChart = new Chart($('throughputChart'), {
  type: 'bar',
  data: { labels: [], datasets: [{ data: [], backgroundColor: 'rgba(86,168,255,.42)', borderColor: cssVar('--blue'), borderWidth: 1, borderRadius: 4 }] },
  options: baseChartOptions()
});

function updateThroughput() {
  const now = Date.now();
  const count = state.eventTimes.filter(t => t > now - 10000).length;
  const label = new Date().toLocaleTimeString([], { minute: '2-digit', second: '2-digit' });
  const last = state.throughputBuckets[state.throughputBuckets.length - 1];
  if (!last || now - last.at >= 2000) {
    state.throughputBuckets.push({ label, count, at: now });
    state.throughputBuckets = state.throughputBuckets.slice(-16);
  } else {
    last.count = count;
  }
}

function renderCharts() {
  const sample = state.readings.slice(-48);
  const labels = sample.map(r => `${r.device_id.slice(-2)} · ${timeOnly(r.timestamp)}`);
  tempChart.data.labels = labels;
  tempChart.data.datasets[0].data = sample.map(r => r.temperature);
  tempChart.update('none');
  energyChart.data.labels = labels;
  energyChart.data.datasets[0].data = sample.map(r => r.energy_usage);
  energyChart.update('none');

  updateThroughput();
  throughputChart.data.labels = state.throughputBuckets.map(b => b.label);
  throughputChart.data.datasets[0].data = state.throughputBuckets.map(b => b.count);
  throughputChart.update('none');
}

function renderRooms() {
  $('rooms').innerHTML = ROOM_IDS.map(id => {
    const r = state.roomLatest[id];
    return `<div class="room-card ${r?.anomaly ? 'anomaly' : ''}">
      <div class="room-head"><strong>${id}</strong><span class="room-dot"></span></div>
      <div class="room-values">
        <span>TEMP<b>${r ? `${r.temperature.toFixed(1)}°C` : '—'}</b></span>
        <span>HUMIDITY<b>${r ? `${r.humidity.toFixed(0)}%` : '—'}</b></span>
        <span>ENERGY<b>${r ? `${r.energy_usage.toFixed(2)} kW` : '—'}</b></span>
        <span>STATE<b>${r?.anomaly ? 'ALERT' : 'NORMAL'}</b></span>
      </div>
    </div>`;
  }).join('');
}

function renderEvents() {
  const rows = state.readings.slice(-DISPLAY_READINGS).reverse();
  $('eventTable').innerHTML = rows.map(r => `<tr>
    <td>${r.device_id}</td><td>${r.temperature.toFixed(1)}°</td><td>${r.humidity.toFixed(0)}%</td><td>${r.energy_usage.toFixed(2)}</td>
    <td><span class="event-status ${r.anomaly ? 'bad' : 'ok'}">${r.anomaly ? 'ANOMALY' : 'ACCEPTED'}</span></td>
  </tr>`).join('');
}

function renderAlerts() {
  $('alertCount').textContent = `${state.alerts.length} alert${state.alerts.length === 1 ? '' : 's'}`;
  if (!state.alerts.length) {
    $('alerts').className = 'feed empty-state';
    $('alerts').innerHTML = `<div class="empty-icon">⚡</div><strong>No anomalies detected</strong><span>Use “Inject Anomaly” to test the detection path.</span>`;
    return;
  }
  $('alerts').className = 'feed';
  $('alerts').innerHTML = state.alerts.slice(0,10).map(a => `<div class="alert-item">
    <div class="feed-item-head"><strong>${a.device_id} · ${a.method}</strong><span class="severity">${a.severity.toUpperCase()}</span></div>
    <p>${a.reason}</p><div class="meta">${new Date(a.created_at).toLocaleString()}</div>
  </div>`).join('');
}

function renderDeadLetters() {
  $('deadCount').textContent = `${state.deadLetters.length} rejected`;
  if (!state.deadLetters.length) {
    $('deadLetters').className = 'feed empty-state';
    $('deadLetters').innerHTML = `<div class="empty-icon">⌁</div><strong>No rejected events</strong><span>Invalid payloads are isolated instead of crashing the pipeline.</span>`;
    return;
  }
  $('deadLetters').className = 'feed';
  $('deadLetters').innerHTML = state.deadLetters.slice(0,10).map(d => `<div class="dead-item">
    <div class="feed-item-head"><strong>Rejected payload · ${String(d.payload.device_id ?? 'UNKNOWN')}</strong></div>
    <p>${d.errors.join(' · ')}</p><div class="meta">${new Date(d.timestamp).toLocaleString()}</div>
  </div>`).join('');
}

function renderActivity() {
  $('activity').innerHTML = state.activity.slice(0,10).map(a => `<div class="activity-item">
    <div class="activity-time">${timeOnly(a.timestamp)}</div><div><strong>${a.type}</strong><span>${a.message}</span></div>
  </div>`).join('');
}

function renderMetrics() {
  $('eventsStored').textContent = state.totalAccepted.toLocaleString();
  $('activeAlerts').textContent = state.alerts.length;
  $('invalidEvents').textContent = state.deadLetters.length;
  $('pipelineHealth').textContent = state.running ? 'RUNNING' : 'PAUSED';
  $('healthSubtext').textContent = state.running ? 'All stages operational' : 'Demo ready';
  $('eventsRate').textContent = `${state.eventTimes.length} events/min`;
  $('alertSubtext').textContent = state.alerts.length ? `${state.alerts[0].severity} latest` : 'No anomalies';
  if (!state.latestAcceptedAt) $('freshness').textContent = '—';
  else {
    const seconds = Math.max(0, Math.floor((Date.now() - state.latestAcceptedAt.getTime()) / 1000));
    $('freshness').textContent = `${seconds}s`;
  }
}

function render() {
  renderMetrics();
  renderRooms();
  renderEvents();
  renderAlerts();
  renderDeadLetters();
  renderActivity();
  renderCharts();
}

let toastTimer = null;
function showToast(message, type = '') {
  const t = $('toast');
  t.textContent = message;
  t.className = `toast ${type} show`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.className = 'toast', 3300);
}

$('startBtn').addEventListener('click', startSimulation);
$('pauseBtn').addEventListener('click', pauseSimulation);
$('anomalyBtn').addEventListener('click', injectAnomaly);
$('invalidBtn').addEventListener('click', injectInvalid);
$('resetBtn').addEventListener('click', resetDemo);

seedDemo();
render();
setInterval(renderMetrics, 1000);
setInterval(() => { if (state.running) renderCharts(); }, 2000);
