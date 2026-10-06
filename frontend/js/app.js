// ============================================================================
// V2V SCADA HUD — Advanced Vehicular Safety & Highway Monitoring Controller
// ============================================================================

// Initialize Fullscreen Leaflet Map
const map = L.map('map', {
    zoomControl: true,
    attributionControl: false
}).setView([17.4239, 78.4483], 15);

let speedChart;
let tollgateMarkers = {};
let markers = {};
const lastPositions = {};
const latestTelemetry = new Map();
const RENDER_INTERVAL_MS = 200;
const MAX_CHART_SERIES = 4;
const ALARM_COOLDOWN_MS = 4000;
let trafficFitTimer;
let hasFittedTraffic = false;
let selectedVehicleId = null;
let lastDpiUpdate = 0;
const alarmCooldowns = new Map();
let activeRouteTollInfo = null;

// Global State Variables for Sound & Calling
let isSpeakerMuted = false;
let isMicMuted = false;

// Sound Synthesizer (Web Audio API)
let audioCtx = null;
function getAudioContext() {
    if (!audioCtx && (window.AudioContext || window.webkitAudioContext)) {
        try {
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        } catch (_) {}
    }
    return audioCtx;
}

// User-gesture audio unlocker to comply with modern browser autoplay policies
function unlockAudioContext() {
    const ctx = getAudioContext();
    if (ctx && ctx.state === 'suspended') {
        ctx.resume().catch(() => {});
    }
}
['click', 'keydown', 'touchstart', 'pointerdown'].forEach(evt => {
    window.addEventListener(evt, unlockAudioContext, { once: true, passive: true });
});

function playAlarmTone(freq = 880, duration = 0.25, type = 'square', gainLevel = 0.08) {
    if (isSpeakerMuted) return;
    try {
        const ctx = getAudioContext();
        if (!ctx) return;

        const scheduleTone = () => {
            try {
                const now = ctx.currentTime;
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.type = type;
                osc.frequency.setValueAtTime(Math.max(20, Math.min(freq, 20000)), now);
                gain.gain.setValueAtTime(gainLevel, now);
                gain.gain.exponentialRampToValueAtTime(0.0001, now + duration);
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.start(now);
                osc.stop(now + duration + 0.05);
            } catch (_) {}
        };

        if (ctx.state === 'suspended') {
            ctx.resume().then(scheduleTone).catch(() => {});
        } else {
            scheduleTone();
        }
    } catch (_) {}
}

// Theme Management
const themeToggle = document.getElementById('themeToggle');
const themeToggleLabel = document.getElementById('themeToggleLabel');

function applyTheme(theme) {
    const isLight = theme === 'light';
    document.body.classList.toggle('light-theme', isLight);
    document.documentElement.style.colorScheme = isLight ? 'light' : 'dark';
    if (themeToggle) {
        themeToggle.dataset.theme = theme;
        themeToggle.setAttribute('aria-pressed', String(isLight));
    }
    if (themeToggleLabel) {
        themeToggleLabel.textContent = isLight ? 'Dark mode' : 'Light mode';
    }

    if (speedChart && speedChart.options && speedChart.options.scales) {
        const textColor = isLight ? '#475569' : '#8896ab';
        const gridColor = isLight ? 'rgba(15, 23, 42, 0.10)' : 'rgba(255, 255, 255, 0.04)';
        if (speedChart.options.scales.y) {
            if (!speedChart.options.scales.y.grid) speedChart.options.scales.y.grid = {};
            speedChart.options.scales.y.grid.color = gridColor;
            if (!speedChart.options.scales.y.ticks) speedChart.options.scales.y.ticks = {};
            speedChart.options.scales.y.ticks.color = textColor;
        }
        if (speedChart.options.scales.x) {
            if (!speedChart.options.scales.x.ticks) speedChart.options.scales.x.ticks = {};
            speedChart.options.scales.x.ticks.color = textColor;
        }
        speedChart.update('none');
    }
    try {
        localStorage.setItem('v2v-theme', theme);
    } catch (_) {}
}

let savedTheme = 'dark';
try {
    savedTheme = localStorage.getItem('v2v-theme') || 'dark';
} catch (_) {}
applyTheme(savedTheme);

if (themeToggle) {
    themeToggle.addEventListener('click', () => {
        applyTheme(document.body.classList.contains('light-theme') ? 'dark' : 'light');
    });
}

// Map Tile Layer
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    crossOrigin: true,
    attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);

// Restricted Geofence Polygon Overlay
const restrictedZoneCoords = [
    [17.4245, 78.4460],
    [17.4245, 78.4530],
    [17.4190, 78.4530],
    [17.4190, 78.4460]
];
L.polygon(restrictedZoneCoords, {
    color: '#ef4444',
    fillColor: '#ef4444',
    fillOpacity: 0.12,
    weight: 2.5,
    dashArray: '8, 8'
}).addTo(map);

// Speed Chart Initialization
const ctx = document.getElementById('speedChart').getContext('2d');
const gradientBlue = ctx.createLinearGradient(0, 0, 0, 180);
gradientBlue.addColorStop(0, 'rgba(14, 165, 233, 0.5)');
gradientBlue.addColorStop(1, 'rgba(14, 165, 233, 0.0)');
const gradientRed = ctx.createLinearGradient(0, 0, 0, 180);
gradientRed.addColorStop(0, 'rgba(239, 68, 68, 0.5)');
gradientRed.addColorStop(1, 'rgba(239, 68, 68, 0.0)');
const gradientGreen = ctx.createLinearGradient(0, 0, 0, 180);
gradientGreen.addColorStop(0, 'rgba(16, 185, 129, 0.5)');
gradientGreen.addColorStop(1, 'rgba(16, 185, 129, 0.0)');

const speedData = { labels: [], datasets: [] };
speedChart = new Chart(ctx, {
    type: 'line',
    data: speedData,
    options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        interaction: { mode: 'index', intersect: false },
        scales: {
            y: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#8896ab', font: { family: 'Inter', size: 10 } } },
            x: { grid: { display: false }, ticks: { color: '#8896ab', font: { family: 'Inter', size: 10 } } }
        },
        plugins: { legend: { display: false } }
    }
});
// Synchronize chart styling with active theme
applyTheme(savedTheme);

// V2I Traffic Signal Intercept Simulation
let v2iState = 0;
let v2iTimer = 15;
const v2iElement = document.getElementById('v2i-signal');
setInterval(() => {
    v2iTimer--;
    if (v2iTimer <= 0) {
        v2iState = (v2iState + 1) % 3;
        v2iTimer = v2iState === 0 ? 15 : (v2iState === 1 ? 22 : 4);
    }
    if (v2iState === 0) {
        v2iElement.textContent = `RED (${v2iTimer}s)`;
        v2iElement.className = 'value tech-font danger-text';
    } else if (v2iState === 1) {
        v2iElement.textContent = `GREEN (${v2iTimer}s)`;
        v2iElement.className = 'value tech-font safe-text';
    } else {
        v2iElement.textContent = `AMBER (${v2iTimer}s)`;
        v2iElement.className = 'value tech-font warning-text';
    }
}, 1000);

// GNSS HDOP/Sats Simulation
const gpsSats = document.getElementById('gpsSats');
const gpsHdop = document.getElementById('gpsHdop');
setInterval(() => {
    gpsSats.textContent = `${Math.floor(Math.random() * 3) + 14} LOCKED`;
    gpsHdop.textContent = `± ${(Math.random() * 0.03 + 0.04).toFixed(3)}m`;
}, 3000);

// Deep Packet Inspection Hex Stream
const dpiFeed = document.getElementById('dpiFeed');
function generateHexLine(label) {
    const hex = Array.from({ length: 14 }, () => Math.floor(Math.random() * 256).toString(16).padStart(2, '0').toUpperCase()).join(' ');
    const row = document.createElement('div');
    row.className = 'dpi-row';
    row.textContent = `[RF_2.4G] ${label} | CRC:OK | HMAC:VALID | 0x${Math.floor(Math.random() * 0xFFFF).toString(16).toUpperCase()} ${hex}`;
    dpiFeed.appendChild(row);
    while (dpiFeed.children.length > 5) dpiFeed.removeChild(dpiFeed.firstChild);
}

function generateRogueHexLine(payload) {
    const row = document.createElement('div');
    row.className = 'dpi-row dpi-rogue';
    row.textContent = `[DROPPED] HMAC_FAIL | REPLAY_CHECK_FAIL | ${payload.substring(0, 55)}...`;
    dpiFeed.appendChild(row);
    while (dpiFeed.children.length > 5) dpiFeed.removeChild(dpiFeed.firstChild);
}

// ============================================================================
// Highway Tollgates & Interactive Map Markers
// ============================================================================
function renderTollgateMarkers(tollgates) {
    tollgates.forEach(tg => {
        if (tollgateMarkers[tg.tollgate_id]) return;

        const iconHtml = `<div class="tollgate-marker-container">🏛️</div>`;
        const tollIcon = L.divIcon({
            html: iconHtml,
            className: 'custom-toll-icon',
            iconSize: [28, 28],
            iconAnchor: [14, 14]
        });

        const popupContent = `
            <div style="font-family:'Inter',sans-serif; min-width:210px;">
                <div style="font-weight:700; color:#fbbf24; font-size:12px; margin-bottom:4px;">${tg.tollgate_name}</div>
                <div style="font-size:11px; color:#94a3b8; margin-bottom:6px;">${tg.highway_name} (ID: ${tg.tollgate_id})</div>
                <div style="font-size:11px; margin-bottom:3px;"><strong>Toll Contact:</strong> <a href="tel:${tg.toll_phone}" style="color:#38a3dc;">${tg.toll_phone}</a></div>
                <div style="font-size:11px; margin-bottom:3px;"><strong>Emergency:</strong> <a href="tel:${tg.emergency_phone}" style="color:#f87171;">${tg.emergency_phone}</a></div>
                <div style="font-size:10px; color:#64748b; margin-top:5px;"><strong>Hospital:</strong> ${tg.nearby_hospital}</div>
                <div style="font-size:10px; color:#64748b; margin-bottom:8px;"><strong>Police:</strong> ${tg.nearby_police}</div>
                <a href="tel:${tg.toll_phone}" style="display:block; text-align:center; background:#0284c7; color:#fff; text-decoration:none; padding:4px 8px; border-radius:4px; font-weight:600; font-size:11px;">📞 Call Tollgate</a>
            </div>
        `;

        const marker = L.marker([tg.lat, tg.lon], { icon: tollIcon })
            .bindPopup(popupContent)
            .addTo(map);

        // Also draw detection radius zone
        L.circle([tg.lat, tg.lon], {
            radius: tg.detection_radius_m || 300,
            color: '#fbbf24',
            weight: 1,
            fillColor: '#fbbf24',
            fillOpacity: 0.05,
            dashArray: '4, 4'
        }).addTo(map);

        tollgateMarkers[tg.tollgate_id] = marker;
    });
}

// Tollgate Crossed Toast Notification
const tollModal = document.getElementById('tollgateCrossedModal');
const closeTollModalBtn = document.getElementById('closeTollModal');
let tollModalTimer = null;

function displayTollgateCrossed(eventData) {
    document.getElementById('tollModalId').textContent = eventData.tollgate_id;
    document.getElementById('tollModalName').textContent = eventData.tollgate_name;
    document.getElementById('tollModalHighway').textContent = eventData.highway;
    document.getElementById('tollModalLocation').textContent = eventData.location;
    document.getElementById('tollModalTime').textContent = eventData.time;
    document.getElementById('tollModalHospital').textContent = eventData.nearby_hospital || "Regional Trauma Hospital";
    document.getElementById('tollModalPolice').textContent = eventData.nearby_police || "Highway Traffic Police (100)";

    const callBtn = document.getElementById('tollModalCallBtn');
    const phone = eventData.toll_phone || "1033";
    document.getElementById('tollModalPhone').textContent = phone;
    callBtn.onclick = (e) => {
        e.preventDefault();
        tollModal.classList.add('hidden');
        if (typeof initiateLiveVoiceCall === 'function') {
            initiateLiveVoiceCall(eventData.tollgate_id, eventData.tollgate_name, eventData.highway);
        }
    };

    tollModal.classList.remove('hidden');
    playAlarmTone(1046, 0.4, 'sine'); // High chime for tollgate crossing

    clearTimeout(tollModalTimer);
    tollModalTimer = setTimeout(() => {
        tollModal.classList.add('hidden');
    }, 15000);
}

closeTollModalBtn.addEventListener('click', () => {
    tollModal.classList.add('hidden');
    clearTimeout(tollModalTimer);
});

// ============================================================================
// Custom Directional Vehicle SVG Marker
// ============================================================================
function createVehicleIcon(vid, headingDeg, color) {
    const svg = `
        <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
            <g transform="rotate(${headingDeg} 16 16)">
                <!-- Directional Arrow / Chevron -->
                <polygon points="16,3 27,27 16,21 5,27" fill="${color}" stroke="#ffffff" stroke-width="1.8" stroke-linejoin="round"/>
                <!-- Center Core Dot -->
                <circle cx="16" cy="16" r="3" fill="#ffffff"/>
            </g>
        </svg>
    `;
    return L.divIcon({
        html: svg,
        className: 'vehicle-svg-marker',
        iconSize: [32, 32],
        iconAnchor: [16, 16]
    });
}

// ============================================================================
// WebSocket Connection & Real-Time Ingestion
// ============================================================================
const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const wsUrl = `${wsProtocol}//${window.location.host}/ws`;
let ws;
let currentMode = 'LIVE';

function connect() {
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        const el = document.getElementById('connectionStatus');
        el.className = 'status-badge connected';
        el.querySelector('.status-text').textContent = 'System Online';
    };

    ws.onclose = () => {
        const el = document.getElementById('connectionStatus');
        el.className = 'status-badge disconnected';
        el.querySelector('.status-text').textContent = 'DISCONNECTED (Retrying...)';
        document.querySelectorAll('.v-status-pill').forEach(p => {
            p.className = 'v-status-pill disconnected';
            p.textContent = 'DISCONNECTED';
        });
        setTimeout(connect, 2500);
    };

    const pendingUpdates = new Map();
    let renderTimer = null;

    function flushTelemetry() {
        renderTimer = null;
        const messages = [...pendingUpdates.values()];
        pendingUpdates.clear();
        if (!messages.length) return;

        const alarmsByVehicle = new Map();
        const alarms = new Map();

        messages.forEach(({ data, alarms: messageAlarms = [], route_info, toll_events = [] }) => {
            data.localReceivedAt = Date.now();
            latestTelemetry.set(data.vehicle_id, data);

            // Handle Toll Events (Approach / Crossed)
            toll_events.forEach(tEvt => {
                if (tEvt.type === 'tollgate_crossed') {
                    displayTollgateCrossed(tEvt);
                }
            });

            // Update Route Awareness HUD
            if (route_info) {
                document.getElementById('currentHighway').textContent = route_info.current_highway;
                document.getElementById('nextTollName').textContent = route_info.next_tollgate;
                document.getElementById('nextTollDist').textContent = `${route_info.distance_to_next_m} m`;
                document.getElementById('nextTollEta').textContent = `${route_info.eta_seconds} s`;
                activeRouteTollInfo = route_info;

                const callTollNameEl = document.getElementById('callTollName');
                if (callTollNameEl) callTollNameEl.textContent = `${route_info.tollgate_id} (${route_info.next_tollgate})`;
                const callHighwayEl = document.getElementById('callHighway');
                if (callHighwayEl) callHighwayEl.textContent = route_info.current_highway;
                const callTollDistEl = document.getElementById('callTollDist');
                if (callTollDistEl) callTollDistEl.textContent = `${route_info.distance_to_next_m} m`;
            }

            // Process Collision / Threat Alarms
            messageAlarms.forEach(alarm => {
                const pair = [alarm.vehicle_a, alarm.vehicle_b].sort().join('|');
                const key = `${alarm.risk_level}|${pair}`;
                alarms.set(key, alarm);
                [alarm.vehicle_a, alarm.vehicle_b].forEach(vehicleId => {
                    if (!alarmsByVehicle.has(vehicleId)) alarmsByVehicle.set(vehicleId, []);
                    alarmsByVehicle.get(vehicleId).push(alarm);
                });
            });
        });

        const vehicleList = messages.map(message => message.data);
        vehicleList.forEach(data => updateDashboard(data, alarmsByVehicle.get(data.vehicle_id) || []));
        updateDashboardMetrics();
        updateSpeedChart();
        renderAlarms([...alarms.values()]);

        const now = Date.now();
        if (now - lastDpiUpdate >= 1000) {
            generateHexLine(`${vehicleList.length} UNITS [STM32/SX1281]`);
            lastDpiUpdate = now;
        }
    }

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);

        // Initial snapshot from server
        if (msg.type === 'init_state') {
            if (msg.tollgates) renderTollgateMarkers(msg.tollgates);
            if (msg.gateway_health) updateGatewayBadge(msg.gateway_health);
            return;
        }

        // Gateway Node Heartbeat
        if (msg.type === 'gateway_health') {
            updateGatewayBadge(msg.data);
            return;
        }

        // Live Voice Translation Event
        if (msg.type === 'translation_event') {
            renderTranslationMessage(msg.data);
            return;
        }

        // Security Alert (Intrusion / Replay Blocked)
        if (msg.type === 'security_alert') {
            generateRogueHexLine(msg.payload || '');
            const alarmList = document.getElementById('alarmList');
            const noAlarms = alarmList.querySelector('.no-alarms');
            if (noAlarms) noAlarms.remove();

            const li = document.createElement('li');
            li.className = 'alarm-item cyber-alert';
            const nowTime = new Date().toLocaleTimeString('en-US', { hour12: false });
            li.innerHTML = `
                <div class="alarm-header">
                    <span class="alarm-title">🛡️ Cyber-Attack Intercepted (${msg.reason || 'HMAC Drop'})</span>
                    <span class="alarm-time">${nowTime}</span>
                </div>
                <div class="alarm-details">Rogue telemetry rejected by STM32 crypto engine. Source: <strong>${msg.source_id || 'Unknown'}</strong>.</div>
            `;
            alarmList.prepend(li);
            playAlarmTone(330, 0.35, 'sawtooth');
            return;
        }

        // Telemetry Stream
        if (msg.type === 'telemetry') {
            const isDemoData = msg.data.vehicle_id.startsWith("DEMO-");
            if (currentMode === 'LIVE' && isDemoData) return;

            pendingUpdates.set(msg.data.vehicle_id, msg);
            if (!renderTimer) renderTimer = setTimeout(flushTelemetry, RENDER_INTERVAL_MS);
        }
    };
}
connect();

function updateGatewayBadge(gw) {
    const badge = document.getElementById('gatewayStatusBadge');
    if (!badge) return;
    if (gw.status === 'Online') {
        badge.className = 'gateway-badge online';
        badge.textContent = `RSU GATEWAY: ONLINE [${gw.port || 'COM3'}] (${gw.packets_rx || 0} PKTS)`;
    } else {
        badge.className = 'gateway-badge disconnected';
        badge.textContent = `RSU GATEWAY: DISCONNECTED [${gw.port || 'COM3'}]`;
    }
}

// ============================================================================
// Dashboard Rendering: Markers, Vehicle Cards, Orientation Metrics
// ============================================================================
let totalVehicles = new Set();
let activeAlarmsCount = 0;

function updateDashboard(data, alarms) {
    const vid = data.vehicle_id;
    totalVehicles.add(vid);
    lastPositions[vid] = [data.lat, data.lon];

    const isDangerous = alarms && alarms.some(a => a.risk_level >= 2 && a.risk_level < 4);
    const isEmergency = data.vehicle_type === 'Emergency';
    const markerColor = isEmergency ? '#3b82f6' : (isDangerous ? '#ef4444' : '#0ea5e9');
    const heading = data.heading_deg || 0;

    // Update or Create Leaflet Marker with directional SVG rotation
    if (!markers[vid]) {
        markers[vid] = L.marker([data.lat, data.lon], {
            icon: createVehicleIcon(vid, heading, markerColor)
        })
            .bindTooltip(`<strong>${vid}</strong> (${data.vehicle_type})`, { direction: 'top', offset: [0, -12] })
            .on('click', () => selectVehicle(vid))
            .addTo(map);

        if (!hasFittedTraffic) {
            hasFittedTraffic = true;
            map.setView([data.lat, data.lon], 16);
        }
    } else {
        markers[vid].setLatLng([data.lat, data.lon]);
        markers[vid].setIcon(createVehicleIcon(vid, heading, markerColor));
    }

    // Vehicle Card Update
    const cardsContainer = document.getElementById('vehicleCards');
    let card = document.getElementById(`card-${vid}`);
    if (!card) {
        card = document.createElement('div');
        card.id = `card-${vid}`;
        card.className = 'vehicle-card';
        cardsContainer.appendChild(card);
        card.addEventListener('click', () => selectVehicle(vid));
    }

    card.classList.toggle('selected', selectedVehicleId === vid);
    card.style.borderColor = markerColor;

    const pitch = data.pitch_deg !== undefined ? `${data.pitch_deg > 0 ? '+' : ''}${data.pitch_deg}°` : '0.0°';
    const roll = data.roll_deg !== undefined ? `${data.roll_deg > 0 ? '+' : ''}${data.roll_deg}°` : '0.0°';
    const alt = data.alt ? `${data.alt}m` : '540m';
    const batt = data.battery_level ? `${Math.round(data.battery_level)}%` : '98%';

    const speedDisplay = (typeof data.speed_kmph === 'number' && !isNaN(data.speed_kmph)) ? data.speed_kmph.toFixed(0) : (data.speed_kmph || 0);

    card.innerHTML = `
        <div class="card-header-row">
            <span class="vid">${vid} <span style="font-size:0.65rem; color:#64748b;">(${data.vehicle_type || 'Car'})</span><span class="v-status-pill live">LIVE</span></span>
            <span class="vspeed" style="color:${markerColor}">
                ${speedDisplay} <span style="font-size:0.55rem; opacity:0.6">km/h</span>
                <span class="heading-arrow" style="transform:rotate(${heading}deg);">⬆</span>
            </span>
        </div>
        <div class="card-dynamics-row">
            <div class="card-dyn-item">Pitch: <span>${pitch}</span></div>
            <div class="card-dyn-item">Roll: <span>${roll}</span></div>
            <div class="card-dyn-item">Alt: <span>${alt}</span></div>
            <div class="card-dyn-item">Batt: <span>${batt}</span></div>
        </div>
    `;
}

// Periodic Stale Telemetry Pruner & Visual Indicator (Runs every 2.5s)
const STALE_TIMEOUT_MS = 15000;
setInterval(() => {
    const now = Date.now();
    latestTelemetry.forEach((data, vid) => {
        const ageMs = now - (data.localReceivedAt || now);
        const card = document.getElementById(`card-${vid}`);
        const marker = markers[vid];
        if (ageMs > STALE_TIMEOUT_MS) {
            const ageSec = Math.floor(ageMs / 1000);
            if (card) {
                card.classList.add('stale-card');
                const pill = card.querySelector('.v-status-pill');
                if (pill) {
                    pill.className = 'v-status-pill stale';
                    pill.textContent = `STALE (${ageSec}s)`;
                }
            }
            if (marker && marker.getElement && marker.getElement()) {
                marker.getElement().style.opacity = '0.45';
                marker.getElement().style.filter = 'grayscale(80%)';
            }
        } else {
            if (card) {
                card.classList.remove('stale-card');
                const pill = card.querySelector('.v-status-pill');
                if (pill && pill.textContent !== 'LIVE') {
                    pill.className = 'v-status-pill live';
                    pill.textContent = 'LIVE';
                }
            }
            if (marker && marker.getElement && marker.getElement()) {
                marker.getElement().style.opacity = '1.0';
                marker.getElement().style.filter = 'none';
            }
        }
    });
}, 2500);

function updateDashboardMetrics() {
    document.getElementById('valTotalVehicles').textContent = totalVehicles.size;
}

function updateSpeedChart() {
    let chartVehicleIds = [];
    latestTelemetry.forEach((data, vid) => {
        if (chartVehicleIds.length < MAX_CHART_SERIES && !chartVehicleIds.includes(vid)) chartVehicleIds.push(vid);
    });
    if (!chartVehicleIds.length) return;

    const nowTime = new Date().toLocaleTimeString('en-US', { hour12: false });
    speedData.labels.push(nowTime);
    if (speedData.labels.length > 25) speedData.labels.shift();

    const chartBorders = ['#0ea5e9', '#ef4444', '#10b981', '#f59e0b'];
    const chartGradients = [gradientBlue, gradientRed, gradientGreen, gradientBlue];

    chartVehicleIds.forEach((vid, index) => {
        let dataset = speedData.datasets.find(item => item.label === `Unit ${vid}`);
        if (!dataset) {
            dataset = {
                label: `Unit ${vid}`,
                data: [],
                borderColor: chartBorders[index % chartBorders.length],
                backgroundColor: chartGradients[index % chartGradients.length],
                fill: true,
                tension: 0.35,
                pointRadius: 0,
                borderWidth: 2
            };
            speedData.datasets.push(dataset);
        }
        dataset.data.push(latestTelemetry.get(vid)?.speed_kmph ?? null);
        if (dataset.data.length > 25) dataset.data.shift();
    });
    speedChart.update('none');
}

// Render Threat Detection Radar
function renderAlarms(alarms) {
    const alarmList = document.getElementById('alarmList');
    const nowTime = new Date().toLocaleTimeString('en-US', { hour12: false });

    alarms.forEach(a => {
        const key = `${a.risk_level}|${[a.vehicle_a, a.vehicle_b].sort().join('|')}`;
        const now = Date.now();
        if (now - (alarmCooldowns.get(key) || 0) < ALARM_COOLDOWN_MS) return;
        alarmCooldowns.set(key, now);

        const noAlarms = alarmList.querySelector('.no-alarms');
        if (noAlarms) noAlarms.remove();

        const li = document.createElement('li');
        const isGeofence = a.risk_level === 3;
        const isEmergencyAlert = a.risk_level === 4;
        const isCrit = a.risk_level === 2 || isGeofence;

        li.className = `alarm-item ${isEmergencyAlert ? 'emergency-alert' : (isCrit ? 'critical' : 'warning')}`;

        let title = '⚠️ Forward Collision Risk';
        if (isEmergencyAlert) title = '🚨 Emergency Vehicle Approaching';
        else if (isGeofence) title = '🚫 Geofence Boundary Breach';
        else if (isCrit) title = '🛑 CRITICAL COLLISION IMMINENT (AEB ENGAGED)';

        let details = '';
        if (isEmergencyAlert) {
            details = `Ambulance/Emergency <strong>${a.vehicle_a}</strong> is ${a.distance}m away. <span class="danger-text">YIELD RIGHT OF WAY.</span>`;
            playAlarmTone(600, 0.3, 'sawtooth');
        } else if (isGeofence) {
            details = `Vehicle <strong>${a.vehicle_a}</strong> entered restricted safety boundary.`;
        } else {
            const ttcText = a.ttc ? ` | TTC: <strong>${a.ttc}s</strong>` : '';
            details = `Vehicles <strong>${a.vehicle_a}</strong> ↔ <strong>${a.vehicle_b}</strong> — Dist: ${a.distance}m, Closing: ${(a.closing_speed * 3.6).toFixed(0)} km/h${ttcText}.`;
            if (isCrit) playAlarmTone(750, 0.4, 'square');
        }

        li.innerHTML = `
            <div class="alarm-header">
                <span class="alarm-title">${title}</span>
                <span class="alarm-time">${nowTime}</span>
            </div>
            <div class="alarm-details">${details}</div>
        `;
        alarmList.prepend(li);
        activeAlarmsCount++;

        while (alarmList.children.length > 8) {
            alarmList.removeChild(alarmList.lastChild);
            activeAlarmsCount = Math.max(0, activeAlarmsCount - 1);
        }
        document.getElementById('valActiveAlarms').textContent = activeAlarmsCount;
    });
}

function selectVehicle(vid) {
    selectedVehicleId = vid;
    document.querySelectorAll('.vehicle-card').forEach(card => card.classList.toggle('selected', card.id === `card-${vid}`));
    const marker = markers[vid];
    if (marker) {
        marker.openTooltip();
        map.panTo(marker.getLatLng(), { animate: true, duration: 0.3 });
    }
}

// ============================================================================
// Real-Time Multi-Indian-Language Voice Call & Telephony Controller
// ============================================================================

const BCP47_MAP = {
    auto: 'te-IN',
    te: 'te-IN',
    hi: 'hi-IN',
    ta: 'ta-IN',
    kn: 'kn-IN',
    ml: 'ml-IN',
    mr: 'mr-IN',
    bn: 'bn-IN',
    gu: 'gu-IN',
    pa: 'pa-IN',
    or: 'or-IN',
    as: 'as-IN',
    en: 'en-IN'
};

const LANG_DISPLAY = {
    auto: 'Auto Detect',
    te: 'Telugu',
    hi: 'Hindi',
    ta: 'Tamil',
    kn: 'Kannada',
    ml: 'Malayalam',
    mr: 'Marathi',
    bn: 'Bengali',
    gu: 'Gujarati',
    pa: 'Punjabi',
    or: 'Odia',
    as: 'Assamese',
    en: 'English'
};

// State Variables for Voice Call Session
let callActive = false;
let activeCallId = null;
let activeCallSession = null;
let callSeconds = 0;
let callTimerInterval = null;
let activeSpeakingRole = 'Driver'; // 'Driver' or 'Operator'
let callWebSocket = null;
let continuousRecognition = null;
let isRecognizing = false;

// DOM Element References (Panel)
const driverLangSelect = document.getElementById('driverLangSelect');
const operatorLangSelect = document.getElementById('operatorLangSelect');
const btnStartCall = document.getElementById('btnStartCall');
const btnEndCall = document.getElementById('btnEndCall');
const btnToggleMute = document.getElementById('btnToggleMute');
const btnToggleSpeaker = document.getElementById('btnToggleSpeaker');
const btnExpandCall = document.getElementById('btnExpandCall');
const callStatusBadge = document.getElementById('callStatusBadge');
const callStatusBar = document.getElementById('callStatusBar');
const callStatusText = document.getElementById('callStatusText');
const callTimerEl = document.getElementById('callTimer');
const activeSpeakerBadge = document.getElementById('activeSpeakerBadge');
const micWaveform = document.getElementById('micWaveform');
const livePartialText = document.getElementById('livePartialText');
const liveConversationBox = document.getElementById('liveConversationBox');
const transInput = document.getElementById('transTextInput');
const btnVoiceRecord = document.getElementById('btnVoiceRecord');
const btnTranslateSend = document.getElementById('btnTranslateSend');

// DOM Element References (Modal)
const liveCallModal = document.getElementById('liveCallModal');
const closeCallModal = document.getElementById('closeCallModal');
const modalCallStatus = document.getElementById('modalCallStatus');
const modalCallTimer = document.getElementById('modalCallTimer');
const modalBtnShareDossier = document.getElementById('modalBtnShareDossier');
const modalDriverLang = document.getElementById('modalDriverLang');
const modalOperatorLang = document.getElementById('modalOperatorLang');
const modalDriverLiveSpeech = document.getElementById('modalDriverLiveSpeech');
const modalDriverTransText = document.getElementById('modalDriverTransText');
const modalOperatorLiveSpeech = document.getElementById('modalOperatorLiveSpeech');
const modalOperatorTransText = document.getElementById('modalOperatorTransText');
const modalDriverTgtLangLbl = document.getElementById('modalDriverTgtLangLbl');
const modalOperatorTgtLangLbl = document.getElementById('modalOperatorTgtLangLbl');
const driverWaveform = document.getElementById('driverWaveform');
const operatorWaveform = document.getElementById('operatorWaveform');
const driverMicStatusText = document.getElementById('driverMicStatusText');
const operatorSpeakerStatusText = document.getElementById('operatorSpeakerStatusText');
const modalCallTranscript = document.getElementById('modalCallTranscript');
const modalBtnMute = document.getElementById('modalBtnMute');
const modalBtnSpeaker = document.getElementById('modalBtnSpeaker');
const modalBtnRoleToggle = document.getElementById('modalBtnRoleToggle');
const modalSpeechInput = document.getElementById('modalSpeechInput');
const modalBtnSendTurn = document.getElementById('modalBtnSendTurn');
const modalBtnEndCall = document.getElementById('modalBtnEndCall');

// Sync language selectors between Panel & Modal
function syncLanguageSelectors() {
    const driverVal = driverLangSelect ? driverLangSelect.value : (modalDriverLang ? modalDriverLang.value : 'te');
    const operatorVal = operatorLangSelect ? operatorLangSelect.value : (modalOperatorLang ? modalOperatorLang.value : 'hi');

    if (modalDriverLang && modalDriverLang.value !== driverVal) {
        modalDriverLang.value = driverVal;
    }
    if (driverLangSelect && driverLangSelect.value !== driverVal) {
        driverLangSelect.value = driverVal;
    }

    if (modalOperatorLang && modalOperatorLang.value !== operatorVal) {
        modalOperatorLang.value = operatorVal;
    }
    if (operatorLangSelect && operatorLangSelect.value !== operatorVal) {
        operatorLangSelect.value = operatorVal;
    }

    const driverTgtName = LANG_DISPLAY[operatorVal] || operatorVal;
    const operatorTgtName = LANG_DISPLAY[driverVal] || driverVal;

    if (modalDriverTgtLangLbl) modalDriverTgtLangLbl.textContent = driverTgtName;
    if (modalOperatorTgtLangLbl) modalOperatorTgtLangLbl.textContent = operatorTgtName;
}

if (driverLangSelect) {
    driverLangSelect.addEventListener('change', () => {
        if (modalDriverLang) modalDriverLang.value = driverLangSelect.value;
        syncLanguageSelectors();
        updateRecognitionLanguage();
    });
}
if (modalDriverLang) {
    modalDriverLang.addEventListener('change', () => {
        if (driverLangSelect) driverLangSelect.value = modalDriverLang.value;
        syncLanguageSelectors();
        updateRecognitionLanguage();
    });
}
if (operatorLangSelect) {
    operatorLangSelect.addEventListener('change', () => {
        if (modalOperatorLang) modalOperatorLang.value = operatorLangSelect.value;
        syncLanguageSelectors();
    });
}
if (modalOperatorLang) {
    modalOperatorLang.addEventListener('change', () => {
        if (operatorLangSelect) operatorLangSelect.value = modalOperatorLang.value;
        syncLanguageSelectors();
    });
}

function updateRecognitionLanguage() {
    if (!continuousRecognition) return;
    const driverVal = driverLangSelect ? driverLangSelect.value : 'te';
    const operatorVal = operatorLangSelect ? operatorLangSelect.value : 'hi';
    const currentLang = activeSpeakingRole === 'Driver' ? driverVal : operatorVal;
    continuousRecognition.lang = BCP47_MAP[currentLang] || 'te-IN';
}

// Initialize Continuous Speech Recognition
if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    continuousRecognition = new SpeechRecognition();
    continuousRecognition.continuous = true;
    continuousRecognition.interimResults = true;
    continuousRecognition.maxAlternatives = 1;

    continuousRecognition.onstart = () => {
        isRecognizing = true;
        setMicVisualState(true);
    };

    continuousRecognition.onresult = (e) => {
        let interimTranscript = '';
        let finalTranscript = '';

        for (let i = e.resultIndex; i < e.results.length; ++i) {
            const part = e.results[i][0].transcript;
            if (e.results[i].isFinal) {
                finalTranscript += part;
            } else {
                interimTranscript += part;
            }
        }

        // Show live partial streaming text
        if (interimTranscript) {
            if (livePartialText) livePartialText.textContent = interimTranscript;
            if (activeSpeakingRole === 'Driver' && modalDriverLiveSpeech) {
                modalDriverLiveSpeech.textContent = interimTranscript;
            } else if (activeSpeakingRole === 'Operator' && modalOperatorLiveSpeech) {
                modalOperatorLiveSpeech.textContent = interimTranscript;
            }
        }

        // Execute translation on complete phrase
        if (finalTranscript.trim()) {
            if (livePartialText) livePartialText.textContent = finalTranscript;
            if (activeSpeakingRole === 'Driver' && modalDriverLiveSpeech) {
                modalDriverLiveSpeech.textContent = finalTranscript;
            } else if (activeSpeakingRole === 'Operator' && modalOperatorLiveSpeech) {
                modalOperatorLiveSpeech.textContent = finalTranscript;
            }
            executeCallSpeechTurn(finalTranscript.trim(), activeSpeakingRole);
        }
    };

    continuousRecognition.onerror = (e) => {
        console.warn("[Speech Recognition Warning]:", e.error);
        if (e.error === 'not-allowed' && livePartialText) {
            livePartialText.textContent = "Microphone permission required for continuous live speech.";
        }
    };

    continuousRecognition.onend = () => {
        isRecognizing = false;
        setMicVisualState(false);
        // Automatically restart if call is still active and mic is not muted
        if (callActive && !isMicMuted) {
            setTimeout(() => {
                if (callActive && !isMicMuted && !isRecognizing) {
                    try {
                        updateRecognitionLanguage();
                        continuousRecognition.start();
                    } catch (_) {}
                }
            }, 200);
        }
    };
}

function setMicVisualState(active) {
    if (active && !isMicMuted) {
        micWaveform.className = 'waveform-anim active';
        driverWaveform.className = 'waveform-anim active';
        driverMicStatusText.className = 'ind-status live';
        driverMicStatusText.textContent = 'LIVE STREAMING';
        btnVoiceRecord.classList.add('recording');
    } else {
        micWaveform.className = 'waveform-anim idle';
        driverWaveform.className = 'waveform-anim idle';
        driverMicStatusText.className = 'ind-status';
        driverMicStatusText.textContent = isMicMuted ? 'MUTED' : 'STANDBY';
        btnVoiceRecord.classList.remove('recording');
    }
}

// Call Initiation & Teardown Lifecycle
window.initiateLiveVoiceCall = async function (tollgateId, tollName, highway) {
    const vid = selectedVehicleId || (totalVehicles.size > 0 ? Array.from(totalVehicles)[0] : 'DEMO-1');
    const tgId = tollgateId || (activeRouteTollInfo ? activeRouteTollInfo.tollgate_id : 'TG-DEMO');
    const tgName = tollName || (activeRouteTollInfo ? activeRouteTollInfo.next_tollgate : 'Jubilee Hills Plaza');
    const hWay = highway || (activeRouteTollInfo ? activeRouteTollInfo.current_highway : 'NH-65 Bypass');

    // Update UI status
    callStatusBadge.className = 'call-badge connecting';
    callStatusBadge.textContent = 'CONNECTING...';
    callStatusBar.className = 'call-status-bar connecting';
    callStatusText.textContent = `Connecting to ${tgName} (${tgId})...`;

    try {
        const payload = {
            vehicle_id: vid,
            tollgate_id: tgId,
            driver_lang: driverLangSelect.value,
            operator_lang: operatorLangSelect.value,
            incident_type: 'Emergency Tollgate Call',
            emergency_info_shared: false
        };

        const res = await fetch('/calls/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();

        activeCallId = data.call_id;
        activeCallSession = data;
        callActive = true;
        callSeconds = 0;

        // UI Updates for Active Call
        updateCallActiveUI(data);

        // Connect WebSocket for live communication channel
        connectCallWebSocket(activeCallId);

        // Start Continuous Speech Recognition
        if (continuousRecognition && !isMicMuted) {
            try {
                updateRecognitionLanguage();
                continuousRecognition.start();
            } catch (_) {}
        }

        // Open Call Modal
        liveCallModal.classList.remove('hidden');
        playAlarmTone(880, 0.25, 'sine');
    } catch (err) {
        console.error("[Call Initiation Failed]:", err);
        callStatusBadge.className = 'call-badge idle';
        callStatusBadge.textContent = 'ERROR';
        callStatusText.textContent = "Call initiation failed. Operating in offline lexicon fallback.";
    }
};

function updateCallActiveUI(data) {
    callStatusBadge.className = 'call-badge active';
    callStatusBadge.textContent = 'CALL ACTIVE';
    callStatusBar.className = 'call-status-bar active';
    callStatusText.textContent = `CALL ACTIVE: ${data.tollgate_name || data.tollgate_id}`;

    btnStartCall.classList.add('hidden');
    btnEndCall.classList.remove('hidden');
    btnToggleMute.disabled = false;
    btnToggleSpeaker.disabled = false;
    const shareGpsBtn = document.getElementById('btnShareIncident');
    if (shareGpsBtn) shareGpsBtn.disabled = false;

    // Timer
    clearInterval(callTimerInterval);
    callTimerInterval = setInterval(() => {
        callSeconds++;
        const mins = String(Math.floor(callSeconds / 60)).padStart(2, '0');
        const secs = String(callSeconds % 60).padStart(2, '0');
        const timeStr = `${mins}:${secs}`;
        callTimerEl.textContent = timeStr;
        if (modalCallTimer) modalCallTimer.textContent = timeStr;
    }, 1000);

    // Modal Dossier Fields
    document.getElementById('dossierTollName').textContent = `${data.tollgate_id} (${data.tollgate_name})`;
    document.getElementById('dossierHighway').textContent = data.highway_name || 'NH-65';
    document.getElementById('dossierVehicleId').textContent = data.vehicle_id;
    document.getElementById('dossierLocation').textContent = data.vehicle_location || '17.4270° N, 78.4450° E';
    document.getElementById('modalDriverVehId').textContent = `Vehicle Unit: ${data.vehicle_id}`;
    document.getElementById('modalOperatorPlazaId').textContent = `Control Console: ${data.tollgate_id}`;
    modalCallStatus.className = 'call-status-tag active';
    modalCallStatus.textContent = 'CALL ACTIVE';

    syncLanguageSelectors();
}

window.terminateLiveVoiceCall = async function (reason = 'User Ended') {
    if (!activeCallId) {
        liveCallModal.classList.add('hidden');
        return;
    }

    try {
        await fetch('/calls/end', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ call_id: activeCallId, reason: reason })
        });
    } catch (_) {}

    callActive = false;
    clearInterval(callTimerInterval);
    if (callWebSocket) {
        try { callWebSocket.close(); } catch (_) {}
        callWebSocket = null;
    }

    if (continuousRecognition && isRecognizing) {
        try { continuousRecognition.stop(); } catch (_) {}
    }

    callStatusBadge.className = 'call-badge ended';
    callStatusBadge.textContent = 'CALL ENDED';
    callStatusBar.className = 'call-status-bar idle';
    callStatusText.textContent = 'CALL ENDED';
    btnStartCall.classList.remove('hidden');
    btnEndCall.classList.add('hidden');
    btnToggleMute.disabled = true;
    btnToggleSpeaker.disabled = true;
    const shareGpsBtn = document.getElementById('btnShareIncident');
    if (shareGpsBtn) shareGpsBtn.disabled = true;
    setMicVisualState(false);

    if (modalCallStatus) {
        modalCallStatus.className = 'call-status-tag';
        modalCallStatus.textContent = 'CALL ENDED';
    }

    setTimeout(() => {
        if (!callActive) {
            callStatusBadge.className = 'call-badge idle';
            callStatusBadge.textContent = 'STANDBY';
            callStatusText.textContent = 'IDLE — Press Start Call to Connect';
        }
    }, 3000);
};

// WebSocket Real-time Voice Relay Channel
function connectCallWebSocket(callId) {
    const locProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${locProtocol}//${window.location.host}/ws/call/${callId}`;

    try {
        callWebSocket = new WebSocket(wsUrl);
        callWebSocket.onopen = () => {
            console.log(`[Call WS Connected]: Channel established for ${callId}`);
        };
        callWebSocket.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                if (msg.type === 'speech_turn') {
                    renderCallConversationTurn(msg.data);
                } else if (msg.type === 'incident_dossier_shared') {
                    handleDossierSharedEvent(msg.dossier);
                } else if (msg.type === 'call_ended') {
                    terminateLiveVoiceCall('Remote Ended Call');
                }
            } catch (_) {}
        };
        callWebSocket.onerror = (e) => console.warn("[Call WS Error]:", e);
    } catch (e) {
        console.warn("[Call WS Connection Failed]:", e);
    }
}

// Process Speech Turn & Automatic Speech Synthesis
async function executeCallSpeechTurn(text, senderRole = 'Driver') {
    if (!text || !text.trim()) return;

    let srcLang = senderRole === 'Driver' ? driverLangSelect.value : operatorLangSelect.value;
    let tgtLang = senderRole === 'Driver' ? operatorLangSelect.value : driverLangSelect.value;

    if (tgtLang === 'auto') tgtLang = (srcLang === 'hi' ? 'te' : 'hi');

    try {
        const payload = {
            call_id: activeCallId || `CALL-LOCAL-${Date.now()}`,
            sender_role: senderRole,
            text: text,
            source_lang: srcLang,
            target_lang: tgtLang
        };

        const res = await fetch('/calls/simulate-turn', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const respData = await res.json();
        if (respData.status === 'success' && respData.turn) {
            renderCallConversationTurn(respData.turn);
        }
    } catch (err) {
        console.error("[Speech Turn Error]:", err);
    }
}

function renderCallConversationTurn(turn) {
    const roleClass = turn.sender_role.toLowerCase().includes('driver') ? 'driver' : 'operator';
    const srcName = LANG_DISPLAY[turn.detected_lang || turn.source_lang] || turn.source_lang;
    const tgtName = LANG_DISPLAY[turn.target_lang] || turn.target_lang;

    // Update Live Transcript Box on Participant Cards
    if (roleClass === 'driver') {
        if (modalDriverLiveSpeech) modalDriverLiveSpeech.textContent = turn.original_text;
        if (modalDriverTransText) modalDriverTransText.textContent = turn.translated_text;
    } else {
        if (modalOperatorLiveSpeech) modalOperatorLiveSpeech.textContent = turn.original_text;
        if (modalOperatorTransText) modalOperatorTransText.textContent = turn.translated_text;
    }

    // Build Bubble HTML
    const bubble = document.createElement('div');
    bubble.className = `trans-item ${roleClass}`;
    bubble.innerHTML = `
        <div class="trans-meta">
            <span>${turn.sender_role.toUpperCase()} [${srcName} ➔ ${tgtName}] • <small>${turn.engine || 'hybrid'}</small></span>
            <span>${turn.timestamp ? turn.timestamp.split(' ')[1] : ''}</span>
        </div>
        <div class="trans-orig"><strong>Original:</strong> "${turn.original_text}"</div>
        <div class="trans-target">
            <span><strong>Translation:</strong> "${turn.translated_text}"</span>
            <button class="trans-speak-btn" title="Replay voice audio" onclick="speakText('${encodeURIComponent(turn.translated_text)}', '${turn.target_lang}')">🔊</button>
        </div>
    `;

    // Append to Panel conversation stream
    if (liveConversationBox) {
        liveConversationBox.prepend(bubble.cloneNode(true));
        while (liveConversationBox.children.length > 20) liveConversationBox.removeChild(liveConversationBox.lastChild);
    }

    // Append to Modal conversation stream
    if (modalCallTranscript) {
        modalCallTranscript.prepend(bubble);
        while (modalCallTranscript.children.length > 30) modalCallTranscript.removeChild(modalCallTranscript.lastChild);
    }

    // Automatically Synthesize & Speak Target Language
    speakText(turn.translated_text, turn.target_lang);
}

function safeDecode(str) {
    if (!str) return '';
    try {
        return decodeURIComponent(str);
    } catch (_) {
        return str;
    }
}

// Client Speech Synthesis (TTS)
window.speakText = function (textOrEncoded, langCode) {
    if (isSpeakerMuted || !('speechSynthesis' in window)) return;

    try {
        const text = textOrEncoded.includes('%') ? safeDecode(textOrEncoded) : textOrEncoded;
        window.speechSynthesis.cancel();

        const utter = new SpeechSynthesisUtterance(text);
        const targetLang = BCP47_MAP[langCode] || 'en-IN';
        utter.lang = targetLang;
        utter.rate = 1.0;
        utter.pitch = 1.0;

        const voices = window.speechSynthesis.getVoices();
        if (voices && voices.length) {
            const prefix = targetLang.split('-')[0];
            const voice = voices.find(v => v.lang === targetLang) || voices.find(v => v.lang.startsWith(prefix));
            if (voice) utter.voice = voice;
        }

        utter.onstart = () => {
            if (operatorWaveform) operatorWaveform.className = 'waveform-anim active';
            if (operatorSpeakerStatusText) {
                operatorSpeakerStatusText.className = 'ind-status live';
                operatorSpeakerStatusText.textContent = 'SPEAKING';
            }
        };

        utter.onend = () => {
            if (operatorWaveform) operatorWaveform.className = 'waveform-anim idle';
            if (operatorSpeakerStatusText) {
                operatorSpeakerStatusText.className = 'ind-status';
                operatorSpeakerStatusText.textContent = isSpeakerMuted ? 'MUTED' : 'READY';
            }
        };

        utter.onerror = () => {
            if (operatorWaveform) operatorWaveform.className = 'waveform-anim idle';
            if (operatorSpeakerStatusText) {
                operatorSpeakerStatusText.className = 'ind-status';
                operatorSpeakerStatusText.textContent = isSpeakerMuted ? 'MUTED' : 'READY';
            }
        };

        window.speechSynthesis.speak(utter);
    } catch (_) {}
};

if ('speechSynthesis' in window) {
    window.speechSynthesis.onvoiceschanged = () => {
        try { window.speechSynthesis.getVoices(); } catch (_) {}
    };
}

// Emergency Incident Sharing Confirmation
async function handleShareIncidentDossier() {
    if (!activeCallId) {
        alert("Please initiate a live call first before sharing telemetry dossier.");
        return;
    }

    const confirmed = confirm(
        "CONFIRM EMERGENCY DATA SHARING:\n\n" +
        "Share real-time vehicular incident telemetry (GPS Coordinates, Speed, Orientation, Emergency SOS status, and Collision alerts) with the Toll Plaza Operator?"
    );

    if (!confirmed) return;

    try {
        const res = await fetch(`/calls/${activeCallId}/share-incident`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ confirmed: true })
        });
        const data = await res.json();
        if (data.status === 'success') {
            handleDossierSharedEvent(data.dossier);
            alert("Incident Telemetry Dossier successfully transmitted to Tollgate Operator.");
        }
    } catch (e) {
        alert("Failed to transmit incident dossier.");
    }
}

function handleDossierSharedEvent(dossier) {
    playAlarmTone(1046, 0.35, 'triangle');
    const div = document.createElement('div');
    div.className = 'trans-item system';
    const latStr = (dossier.gps_position && typeof dossier.gps_position.lat === 'number')
        ? `${dossier.gps_position.lat.toFixed(4)}° N`
        : (dossier.gps_position?.lat || '17.4245° N');
    const lonStr = (dossier.gps_position && typeof dossier.gps_position.lon === 'number')
        ? `${dossier.gps_position.lon.toFixed(4)}° E`
        : (dossier.gps_position?.lon || '78.4483° E');
    div.innerHTML = `
        <div class="trans-meta">
            <span>📡 TELEMETRY DOSSIER TRANSMITTED TO OPERATOR</span>
            <span>${dossier.timestamp || ''}</span>
        </div>
        <div class="trans-body">
            <strong>Vehicle:</strong> ${dossier.vehicle_id || 'DEMO-1'} | <strong>Location:</strong> ${latStr}, ${lonStr} | <strong>Speed:</strong> ${dossier.speed_kmph ?? 0} km/h | <strong>Status:</strong> ${dossier.emergency_status || 'NORMAL'}
        </div>
    `;
    if (liveConversationBox) liveConversationBox.prepend(div.cloneNode(true));
    if (modalCallTranscript) modalCallTranscript.prepend(div);
}

// User Action Event Handlers
if (btnStartCall) {
    btnStartCall.addEventListener('click', () => {
        initiateLiveVoiceCall();
    });
}

if (btnEndCall) {
    btnEndCall.addEventListener('click', () => {
        terminateLiveVoiceCall('User Clicked End Call');
    });
}

if (modalBtnEndCall) {
    modalBtnEndCall.addEventListener('click', () => {
        terminateLiveVoiceCall('User Clicked End Call in Modal');
    });
}

if (btnToggleMute) {
    btnToggleMute.addEventListener('click', () => {
        isMicMuted = !isMicMuted;
        btnToggleMute.textContent = isMicMuted ? '🔇 Unmute' : '🔇 Mute';
        if (modalBtnMute) modalBtnMute.textContent = isMicMuted ? '🔇 Unmute Mic' : '🔇 Mute Mic';
        setMicVisualState(!isMicMuted);
        if (isMicMuted && continuousRecognition && isRecognizing) {
            continuousRecognition.stop();
        } else if (!isMicMuted && continuousRecognition && !isRecognizing && callActive) {
            try { continuousRecognition.start(); } catch (_) {}
        }
    });
}

if (modalBtnMute) {
    modalBtnMute.addEventListener('click', () => btnToggleMute && btnToggleMute.click());
}

if (btnToggleSpeaker) {
    btnToggleSpeaker.addEventListener('click', () => {
        isSpeakerMuted = !isSpeakerMuted;
        btnToggleSpeaker.textContent = isSpeakerMuted ? '🔈 Unmute Spk' : '🔊 Speaker';
        if (modalBtnSpeaker) modalBtnSpeaker.textContent = isSpeakerMuted ? '🔈 Unmute Speaker' : '🔊 Speaker Active';
        if (isSpeakerMuted && 'speechSynthesis' in window) window.speechSynthesis.cancel();
    });
}

if (modalBtnSpeaker) {
    modalBtnSpeaker.addEventListener('click', () => btnToggleSpeaker && btnToggleSpeaker.click());
}

if (btnExpandCall) {
    btnExpandCall.addEventListener('click', () => {
        if (liveCallModal) liveCallModal.classList.remove('hidden');
    });
}

if (closeCallModal) {
    closeCallModal.addEventListener('click', () => {
        if (liveCallModal) liveCallModal.classList.add('hidden');
    });
}

const shareGpsBtn = document.getElementById('btnShareIncident');
if (shareGpsBtn) shareGpsBtn.addEventListener('click', handleShareIncidentDossier);
if (modalBtnShareDossier) modalBtnShareDossier.addEventListener('click', handleShareIncidentDossier);

// Role Toggle for Client A (Driver) vs Client B (Operator) Simulation
if (modalBtnRoleToggle) {
    modalBtnRoleToggle.addEventListener('click', () => {
        activeSpeakingRole = activeSpeakingRole === 'Driver' ? 'Operator' : 'Driver';
        modalBtnRoleToggle.textContent = `Role: ${activeSpeakingRole} ⇄`;
        if (activeSpeakerBadge) activeSpeakerBadge.textContent = `${activeSpeakingRole} Mic:`;
        updateRecognitionLanguage();
    });
}

// Push to Speak / Manual Transmit Handlers
if (btnVoiceRecord) {
    btnVoiceRecord.addEventListener('click', (e) => {
        e.preventDefault();
        if (!continuousRecognition) {
            alert("Speech recognition is not supported in this browser. Please use Chrome/Edge or type your phrase.");
            return;
        }
        if (isRecognizing) {
            try { continuousRecognition.stop(); } catch (_) {}
        } else {
            if (!callActive) {
                initiateLiveVoiceCall();
            }
            try {
                updateRecognitionLanguage();
                continuousRecognition.start();
            } catch (_) {}
        }
    });
}

if (btnTranslateSend) {
    btnTranslateSend.addEventListener('click', () => {
        const text = transInput ? transInput.value.trim() : '';
        if (text) {
            executeCallSpeechTurn(text, activeSpeakingRole);
            if (transInput) transInput.value = '';
        }
    });
}
if (transInput) {
    transInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && transInput.value.trim()) {
            executeCallSpeechTurn(transInput.value.trim(), activeSpeakingRole);
            transInput.value = '';
        }
    });
}

if (modalBtnSendTurn) {
    modalBtnSendTurn.addEventListener('click', () => {
        const text = modalSpeechInput.value.trim();
        if (text) {
            executeCallSpeechTurn(text, activeSpeakingRole);
            modalSpeechInput.value = '';
        }
    });
}
if (modalSpeechInput) {
    modalSpeechInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && modalSpeechInput.value.trim()) {
            executeCallSpeechTurn(modalSpeechInput.value.trim(), activeSpeakingRole);
            modalSpeechInput.value = '';
        }
    });
}

// Fast Language Simulation Test Buttons (Testing Indian Language Pairs)
document.querySelectorAll('.btn-preset').forEach(btn => {
    btn.addEventListener('click', async (e) => {
        e.preventDefault();
        const src = btn.dataset.src;
        const tgt = btn.dataset.tgt;
        const phrase = btn.dataset.phrase;

        driverLangSelect.value = src;
        operatorLangSelect.value = tgt;
        if (modalDriverLang) modalDriverLang.value = src;
        if (modalOperatorLang) modalOperatorLang.value = tgt;
        syncLanguageSelectors();

        if (!callActive) {
            await initiateLiveVoiceCall();
        }

        executeCallSpeechTurn(phrase, src === driverLangSelect.value ? 'Driver' : 'Operator');
    });
});

// Tollgate Next Button Click Handler
const btnCallNextTollEl = document.getElementById('btnCallNextToll');
if (btnCallNextTollEl) {
    btnCallNextTollEl.addEventListener('click', (e) => {
        e.preventDefault();
        const tId = activeRouteTollInfo ? activeRouteTollInfo.tollgate_id : 'TG-DEMO';
        const tName = activeRouteTollInfo ? activeRouteTollInfo.next_tollgate : 'Jubilee Hills Plaza';
        const hWay = activeRouteTollInfo ? activeRouteTollInfo.current_highway : 'NH-65';
        initiateLiveVoiceCall(tId, tName, hWay);
    });
}


// ============================================================================
// Terminal & Command Dispatcher
// ============================================================================
const terminalInput = document.getElementById('terminalInput');
const terminalLog = document.getElementById('terminalLog');

function appendToTerminal(text, style = '') {
    const div = document.createElement('div');
    div.innerHTML = `&gt; ${text}`;
    if (style) div.style.color = style;
    terminalLog.appendChild(div);
    terminalLog.scrollTop = terminalLog.scrollHeight;
}

terminalInput.addEventListener('keypress', async (e) => {
    if (e.key === 'Enter' && terminalInput.value.trim() !== '') {
        const cmd = terminalInput.value.trim().toUpperCase();
        appendToTerminal(`TX: ${cmd}`, 'var(--accent)');
        terminalInput.value = '';

        try {
            await fetch('/api/command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command: cmd })
            });
            setTimeout(() => appendToTerminal('ACK RECEIVED: COMMAND BROADCAST TO VEHICLES', 'var(--safe)'), 250);
        } catch (_) {
            setTimeout(() => appendToTerminal('TX FAILED', 'var(--danger)'), 250);
        }
    }
});

// ============================================================================
// Toolbar Actions & Mode Switcher
// ============================================================================
document.getElementById('btnExport').addEventListener('click', async (e) => {
    e.preventDefault();
    const btn = e.target;
    const old = btn.textContent;
    btn.textContent = "GENERATING...";
    try {
        const res = await fetch('/api/report', { method: 'POST' });
        const data = await res.json();
        if (data.status === 'success') window.location.href = `/api/download/${data.file}`;
    } catch (_) {
        alert("Report generation failed");
    } finally {
        btn.textContent = old;
    }
});

document.getElementById('modeLive').addEventListener('click', (e) => {
    currentMode = 'LIVE';
    e.target.classList.add('active');
    document.getElementById('modeDemo').classList.remove('active');
    clearMap();
});

document.getElementById('modeDemo').addEventListener('click', (e) => {
    currentMode = 'DEMO';
    e.target.classList.add('active');
    document.getElementById('modeLive').classList.remove('active');
    clearMap();
});

function clearMap() {
    for (let v in markers) map.removeLayer(markers[v]);
    markers = {};
    Object.keys(lastPositions).forEach(vid => delete lastPositions[vid]);
    latestTelemetry.clear();
    selectedVehicleId = null;
    hasFittedTraffic = false;
    clearTimeout(trafficFitTimer);
    speedData.datasets = [];
    speedData.labels = [];
    totalVehicles.clear();
    document.getElementById('valTotalVehicles').textContent = '0';
    document.getElementById('vehicleCards').innerHTML = '';
    document.getElementById('alarmList').innerHTML = '<li class="no-alarms">System Safe — No Active Hazards</li>';
    activeAlarmsCount = 0;
    document.getElementById('valActiveAlarms').textContent = '0';
    speedChart.update();
}

document.getElementById('btnDemo').addEventListener('click', async (e) => {
    e.preventDefault();
    const btn = e.target;
    if (btn.style.opacity === '0.5') return;

    if (currentMode !== 'DEMO') {
        document.getElementById('modeDemo').click();
    }

    btn.textContent = "▶ RUNNING...";
    btn.style.opacity = '0.5';
    try { await fetch('/api/demo', { method: 'POST' }); } catch (_) {}
    setTimeout(() => {
        btn.textContent = "▶ Run Demo";
        btn.style.opacity = '1';
    }, 60000);
});

document.getElementById('btnSpoof').addEventListener('click', async (e) => {
    e.preventDefault();
    const btn = e.target;
    if (btn.style.opacity === '0.5') return;
    btn.textContent = "INJECTING...";
    btn.style.opacity = '0.5';
    try { await fetch('/api/spoof', { method: 'POST' }); } catch (_) {}
    setTimeout(() => {
        btn.textContent = "⚠ Spoof Attack";
        btn.style.opacity = '1';
    }, 2000);
});
