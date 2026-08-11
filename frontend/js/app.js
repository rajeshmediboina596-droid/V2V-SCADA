// Initialize Full Screen Map
const map = L.map('map', {
    zoomControl: true,
    attributionControl: false
}).setView([17.4239, 78.4483], 15);

L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    subdomains: 'abcd',
    maxZoom: 20
}).addTo(map);

// Geofence
const restrictedZoneCoords = [
    [17.4245, 78.4460],
    [17.4245, 78.4530],
    [17.4190, 78.4530],
    [17.4190, 78.4460]
];
L.polygon(restrictedZoneCoords, {
    color: '#ef4444',
    fillColor: '#ef4444',
    fillOpacity: 0.15,
    weight: 3,
    dashArray: '10, 10'
}).addTo(map);

let markers = {};
let vehiclePaths = {}; 
const lastPositions = {}; 

// Chart Initialization
const ctx = document.getElementById('speedChart').getContext('2d');
const gradientBlue = ctx.createLinearGradient(0, 0, 0, 200);
gradientBlue.addColorStop(0, 'rgba(14, 165, 233, 0.6)');
gradientBlue.addColorStop(1, 'rgba(14, 165, 233, 0.0)');
const gradientRed = ctx.createLinearGradient(0, 0, 0, 200);
gradientRed.addColorStop(0, 'rgba(239, 68, 68, 0.6)');
gradientRed.addColorStop(1, 'rgba(239, 68, 68, 0.0)');

const speedData = { labels: [], datasets: [] };
const speedChart = new Chart(ctx, {
    type: 'line',
    data: speedData,
    options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        scales: {
            y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8', font: {family: 'Orbitron'} } },
            x: { grid: { display: false }, ticks: { color: '#94a3b8', font: {family: 'Orbitron'} } }
        },
        plugins: { legend: { display: false } }
    }
});

// V2I Traffic Light Interceptor Logic
let v2iState = 0; // 0: Red, 1: Green, 2: Yellow
let v2iTimer = 14;
const v2iElement = document.getElementById('v2i-signal');
setInterval(() => {
    v2iTimer--;
    if (v2iTimer <= 0) {
        v2iState = (v2iState + 1) % 3;
        if (v2iState === 0) v2iTimer = 14; // Red
        else if (v2iState === 1) v2iTimer = 20; // Green
        else if (v2iState === 2) v2iTimer = 4; // Yellow
    }
    
    if (v2iState === 0) {
        v2iElement.textContent = `RED (${v2iTimer}s)`;
        v2iElement.className = 'value tech-font danger-text';
    } else if (v2iState === 1) {
        v2iElement.textContent = `GREEN (${v2iTimer}s)`;
        v2iElement.className = 'value tech-font safe-text';
    } else {
        v2iElement.textContent = `YELLOW (${v2iTimer}s)`;
        v2iElement.className = 'value tech-font warning-text';
    }
}, 1000);

// GPS & RSU Simulation Logic
const gpsSats = document.getElementById('gpsSats');
const gpsHdop = document.getElementById('gpsHdop');
const rsu1 = document.getElementById('rsu1');
const rsu2 = document.getElementById('rsu2');

setInterval(() => {
    // GPS Fluctuation
    const sats = Math.floor(Math.random() * 3) + 13; // 13-15 sats
    gpsSats.textContent = `${sats} LOCKED`;
    
    const hdop = (Math.random() * 0.04 + 0.03).toFixed(3); // 0.030 - 0.070
    gpsHdop.textContent = `± ${hdop}m`;
    
    // RSU Signal Fluctuation
    const rsu1Str = Math.floor(Math.random() * 5) + 95; // 95-99%
    const rsu1Dbm = -40 - Math.floor(Math.random() * 10);
    rsu1.textContent = `${rsu1Str}% (${rsu1Dbm}dBm)`;
    
    const rsu2Str = Math.floor(Math.random() * 10) + 60; // 60-70%
    const rsu2Dbm = -70 - Math.floor(Math.random() * 15);
    rsu2.textContent = `${rsu2Str}% (${rsu2Dbm}dBm)`;
}, 2000);

// DPI Hex Dump Generator
const dpiFeed = document.getElementById('dpiFeed');
function generateHexLine(vid) {
    const hex = Array.from({length: 16}, () => Math.floor(Math.random()*256).toString(16).padStart(2, '0').toUpperCase()).join(' ');
    const row = document.createElement('div');
    row.className = 'dpi-row';
    row.textContent = `[ENC] ${vid} | 0x${Math.floor(Math.random()*0xFFFF).toString(16).toUpperCase()} | ${hex}`;
    dpiFeed.appendChild(row);
    while (dpiFeed.children.length > 8) {
        dpiFeed.removeChild(dpiFeed.firstChild);
    }
}

function generateRogueHexLine(payload) {
    const row = document.createElement('div');
    row.className = 'dpi-row dpi-rogue';
    row.textContent = `[BLOCK] HMAC_FAIL | PAYLOAD: ${payload.substring(0, 50)}...`;
    dpiFeed.appendChild(row);
    while (dpiFeed.children.length > 8) {
        dpiFeed.removeChild(dpiFeed.firstChild);
    }
}


// WebSocket Connection
const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const wsUrl = `${wsProtocol}//${window.location.host}/ws`;
let ws;

function connect() {
    ws = new WebSocket(wsUrl);
    ws.onopen = () => {
        const el = document.getElementById('connectionStatus');
        el.className = 'status-badge connected';
        el.querySelector('.status-text').textContent = 'SYSTEM ONLINE';
    };
    ws.onclose = () => {
        const el = document.getElementById('connectionStatus');
        el.className = 'status-badge disconnected';
        el.querySelector('.status-text').textContent = 'LINK LOST';
        setTimeout(connect, 3000); 
    };
    
    let pendingUpdates = [];
    let isUpdating = false;

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === 'security_alert') {
            generateRogueHexLine(msg.payload);
            const alarmList = document.getElementById('alarmList');
            const noAlarms = alarmList.querySelector('.no-alarms');
            if(noAlarms) noAlarms.remove();
            
            const li = document.createElement('li');
            li.className = 'alarm-item cyber-alert';
            const nowTime = new Date().toLocaleTimeString('en-US', { hour12: false, hour: "numeric", minute: "numeric", second: "numeric" });
            li.innerHTML = `
                <div class="alarm-header">
                    <span class="alarm-title">🚨 CYBER-ATTACK BLOCKED</span>
                    <span class="alarm-time">${nowTime}</span>
                </div>
                <div class="alarm-details">Rogue Node Injection Blocked.<br>Invalid HMAC-SHA256 Signature.</div>
            `;
            alarmList.prepend(li);
            return;
        }
        
        if(msg.type === 'telemetry') {
            const isDemoData = msg.data.vehicle_id.startsWith("DEMO-");
            
            // In LIVE mode, strictly hide DEMO vehicles.
            // In DEMO mode, show both DEMO vehicles and LIVE vehicles (do not return).
            if (currentMode === 'LIVE' && isDemoData) return;
            
            pendingUpdates.push(msg);
            if(!isUpdating) {
                isUpdating = true;
                requestAnimationFrame(() => {
                    const latestByVehicle = {};
                    const allAlarms = [];
                    pendingUpdates.forEach(m => {
                        latestByVehicle[m.data.vehicle_id] = m.data;
                        if(m.alarms) allAlarms.push(...m.alarms);
                        generateHexLine(m.data.vehicle_id); // Add to DPI feed
                    });
                    pendingUpdates = [];
                    isUpdating = false;
                    
                    const vehicleList = Object.values(latestByVehicle);
                    vehicleList.forEach(data => updateDashboard(data, allAlarms.filter(a => a.vehicle_a === data.vehicle_id || a.vehicle_b === data.vehicle_id)));
                    // User requested manual map control: disabled autoCenterMap
                    checkPlatooning(vehicleList);
                });
            }
        }
    };
}
connect();

let lastPanTime = 0;
function autoCenterMap() {
    const now = Date.now();
    if (now - lastPanTime < 2000) return;
    const latlngs = Object.values(lastPositions);
    if(latlngs.length > 0) {
        const bounds = L.latLngBounds(latlngs);
        map.fitBounds(bounds, {
            paddingTopLeft: [450, 400], 
            paddingBottomRight: [450, 400],
            maxZoom: 17,
            animate: true,
            duration: 0.5
        });
        lastPanTime = now;
    }
}

// Platooning Coordinator Logic
function haversineDist(lat1, lon1, lat2, lon2) {
    const R = 6371000;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLon/2) * Math.sin(dLon/2);
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
}

function checkPlatooning(vehicles) {
    if (vehicles.length < 2) return;
    // Just check first two for demo purposes
    const v1 = vehicles[0];
    const v2 = vehicles[1];
    
    const dist = haversineDist(v1.lat, v1.lon, v2.lat, v2.lon);
    const pState = document.getElementById('platoonState');
    const pDraft = document.getElementById('platoonDrafting');
    
    // If they are within 60 meters and driving fast, consider it a platoon
    if (dist < 60 && v1.speed_kmph > 30 && v2.speed_kmph > 30) {
        pState.textContent = 'LINK ACTIVE [CONVOY]';
        pState.className = 'value tech-font safe-text';
        pDraft.textContent = '14.2% (OPTIMAL)';
        pDraft.className = 'value tech-font safe-text';
    } else {
        pState.textContent = 'SEARCHING...';
        pState.className = 'value tech-font warning-text';
        pDraft.textContent = '0.0%';
        pDraft.className = 'value tech-font text-muted';
    }
}


const chartGradients = [gradientBlue, gradientRed, 'rgba(16, 185, 129, 0.5)'];
const chartBorders = ['#0ea5e9', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6'];
let colorIndex = 0;
let totalVehicles = new Set();
let activeAlarmsCount = 0;

let latencies = [];
let trajectories = {};

function calculateFuturePoint(lat, lon, speedKmph, headingDeg, secondsAhead) {
    const speedMs = speedKmph / 3.6;
    const distance = speedMs * secondsAhead;
    const R = 6371000; // Earth radius in meters
    const headingRad = headingDeg * Math.PI / 180;
    const lat1 = lat * Math.PI / 180;
    const lon1 = lon * Math.PI / 180;
    
    const lat2 = Math.asin(Math.sin(lat1) * Math.cos(distance/R) + Math.cos(lat1) * Math.sin(distance/R) * Math.cos(headingRad));
    const lon2 = lon1 + Math.atan2(Math.sin(headingRad) * Math.sin(distance/R) * Math.cos(lat1), Math.cos(distance/R) - Math.sin(lat1) * Math.sin(lat2));
    
    return [lat2 * 180 / Math.PI, lon2 * 180 / Math.PI];
}

function updateDashboard(data, alarms) {
    const vid = data.vehicle_id;
    totalVehicles.add(vid);
    document.getElementById('valTotalVehicles').textContent = totalVehicles.size;
    
    let latency = Math.floor(Math.random() * 30) + 15;
    latencies.push(latency);
    if(latencies.length > 10) latencies.shift();
    const avgLatency = Math.floor(latencies.reduce((a,b)=>a+b, 0) / latencies.length);
    const latencyEl = document.getElementById('valLatency');
    latencyEl.textContent = `${avgLatency} ms`;
    latencyEl.className = `value tech-font ${avgLatency > 100 ? 'danger-text' : 'safe-text'}`;

    lastPositions[vid] = [data.lat, data.lon];
    const isDangerous = alarms && alarms.some(a => a.risk_level >= 2 && a.risk_level < 4);
    const isEmergency = data.vehicle_type === 'Emergency';
    
    let radarClass = 'radar-safe';
    let markerColor = 'var(--primary)';
    
    if (isEmergency) {
        radarClass = 'radar-emergency';
        markerColor = '#3b82f6'; // Blue
    } else if (isDangerous) {
        radarClass = 'radar-danger';
        markerColor = 'var(--danger)';
    }

    const iconHtml = `
        <div class="radar-marker ${radarClass}">
            <div class="radar-label" style="border-color:${markerColor}">${vid}</div>
            <div class="radar-ring"></div>
            <div class="radar-dot"></div>
        </div>
    `;

    if(!markers[vid]) {
        const customIcon = L.divIcon({
            className: 'custom-hud-icon',
            html: iconHtml,
            iconSize: [60, 60],
            iconAnchor: [30, 30]
        });
        
        markers[vid] = L.marker([data.lat, data.lon], {icon: customIcon}).addTo(map);
        
        vehiclePaths[vid] = L.polyline([[data.lat, data.lon]], {
            color: chartBorders[colorIndex % chartBorders.length],
            weight: 4,
            opacity: 0.8,
            dashArray: '5, 10'
        }).addTo(map);
        
        trajectories[vid] = L.polyline([], {
            color: markerColor,
            weight: 2,
            opacity: 0.9,
            dashArray: '2, 5'
        }).addTo(map);
        
        speedData.datasets.push({
            label: `Unit ${vid}`,
            data: [],
            borderColor: chartBorders[colorIndex % chartBorders.length],
            backgroundColor: chartGradients[colorIndex % chartGradients.length],
            fill: true,
            tension: 0.4,
            pointRadius: 0,
            borderWidth: 3
        });
        colorIndex++;
    } else {
        const icon = markers[vid].getIcon();
        icon.options.html = iconHtml;
        markers[vid].setIcon(icon);
        markers[vid].setLatLng([data.lat, data.lon]);
        
        const polyline = vehiclePaths[vid];
        const latlngs = polyline.getLatLngs();
        latlngs.push(new L.LatLng(data.lat, data.lon));
        if(latlngs.length > 50) latlngs.shift(); 
        polyline.setLatLngs(latlngs);
        
        // Update Predictive Trajectory (5 seconds ahead)
        if(data.speed_kmph > 1) {
            const futurePoint = calculateFuturePoint(data.lat, data.lon, data.speed_kmph, data.heading_deg, 5);
            trajectories[vid].setLatLngs([[data.lat, data.lon], futurePoint]);
            trajectories[vid].setStyle({color: markerColor});
        } else {
            trajectories[vid].setLatLngs([]);
        }
    }
    
    const nowTime = new Date().toLocaleTimeString('en-US', { hour12: false, hour: "numeric", minute: "numeric", second: "numeric" });
    if(speedData.labels.length > 30) {
        speedData.labels.shift();
        speedData.datasets.forEach(d => d.data.shift());
    }
    if(!speedData.labels.includes(nowTime)) {
        speedData.labels.push(nowTime);
    }
    const ds = speedData.datasets.find(d => d.label === `Unit ${vid}`);
    if(ds) ds.data.push(data.speed_kmph);
    speedChart.update();
    
    const cardsContainer = document.getElementById('vehicleCards');
    let card = document.getElementById(`card-${vid}`);
    if(!card) {
        card = document.createElement('div');
        card.id = `card-${vid}`;
        card.className = 'vehicle-card';
        cardsContainer.appendChild(card);
    }
    card.style.borderColor = markerColor;
    card.style.boxShadow = `inset 0 0 15px ${isDangerous ? 'rgba(239, 68, 68, 0.2)' : 'rgba(14, 165, 233, 0.1)'}`;
    card.innerHTML = `
        <span class="vid">${vid}</span>
        <span class="vspeed" style="color:${markerColor}">${data.speed_kmph.toFixed(0)} <span style="font-size:0.6rem">KM/H</span></span>
    `;
    
    const alarmList = document.getElementById('alarmList');
    if(alarms && alarms.length > 0) {
        const noAlarms = alarmList.querySelector('.no-alarms');
        if(noAlarms) noAlarms.remove();
        
        alarms.forEach(a => {
            const li = document.createElement('li');
            const isGeofence = a.risk_level === 3;
            const isEmergencyAlert = a.risk_level === 4;
            const isCrit = a.risk_level === 2 || isGeofence;
            
            li.className = `alarm-item ${isEmergencyAlert ? 'emergency-alert' : (isCrit ? 'critical' : 'warning')}`;
            
            let title = '⚠️ COLLISION WARNING';
            if (isEmergencyAlert) title = '🚨 EMERGENCY VEHICLE YIELD';
            else if (isGeofence) title = '🚨 GEOFENCE BREACH';
            else if (isCrit) title = '⚠️ CRITICAL THREAT';
            
            let details = '';
            if (isEmergencyAlert) {
                details = `An Emergency Vehicle (<strong>${a.vehicle_a}</strong>) is rapidly approaching from <strong>${a.distance} meters</strong> away.<br><span class="danger-text">PLEASE YIELD RIGHT OF WAY IMMEDIATELY.</span>`;
            } else if (isGeofence) {
                details = `Vehicle <strong>${a.vehicle_a}</strong> has illegally entered the restricted Geofence Zone.<br><span class="danger-text">Unauthorized airspace breach detected.</span>`;
            } else {
                let riskText = isCrit ? '<span class="danger-text">CRITICAL IMMINENT IMPACT!</span>' : 'Potential collision path detected.';
                let closingKmph = (a.closing_speed * 3.6).toFixed(0);
                details = `${riskText} Vehicles <strong>${a.vehicle_a}</strong> and <strong>${a.vehicle_b}</strong> are dangerously close.<br>Distance Apart: <strong>${a.distance} meters</strong> (Closing at <strong>${closingKmph} km/h</strong>).`;
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
        });
        
        while(alarmList.children.length > 15) {
            alarmList.removeChild(alarmList.lastChild);
            activeAlarmsCount = Math.max(0, activeAlarmsCount - 1);
        }
        document.getElementById('valActiveAlarms').textContent = activeAlarmsCount;
    }
}

// Terminal Logic
const terminalInput = document.getElementById('terminalInput');
const terminalLog = document.getElementById('terminalLog');

function appendToTerminal(text, style='') {
    const div = document.createElement('div');
    div.innerHTML = `> ${text}`;
    if(style) div.style.color = style;
    terminalLog.appendChild(div);
    terminalLog.scrollTop = terminalLog.scrollHeight;
}

terminalInput.addEventListener('keypress', async (e) => {
    if (e.key === 'Enter' && terminalInput.value.trim() !== '') {
        const cmd = terminalInput.value.trim().toUpperCase();
        appendToTerminal(`TX: ${cmd}`, 'var(--text-main)');
        terminalInput.value = '';
        
        try {
            await fetch('/api/command', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({command: cmd})
            });
            setTimeout(() => appendToTerminal('ACK RECEIVED', 'var(--primary)'), 300);
        } catch (e) {
            setTimeout(() => appendToTerminal('TX FAILED', 'var(--danger)'), 300);
        }
    }
});


// Buttons
document.getElementById('btnExport').addEventListener('click', async (e) => {
    e.preventDefault();
    const btn = e.target;
    const old = btn.textContent;
    btn.textContent = "GENERATING...";
    try {
        const res = await fetch('/api/report', {method: 'POST'});
        const data = await res.json();
        if(data.status === 'success') window.location.href = `/api/download/${data.file}`;
    } catch (e) { alert('Failed'); } 
    finally { btn.textContent = old; }
});

let currentMode = 'LIVE';

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
    for (let v in vehiclePaths) map.removeLayer(vehiclePaths[v]);
    for (let v in trajectories) map.removeLayer(trajectories[v]);
    markers = {}; vehiclePaths = {}; trajectories = {};
    speedData.datasets = [];
    colorIndex = 0;
    totalVehicles.clear();
    document.getElementById('valTotalVehicles').textContent = '0';
    document.getElementById('vehicleCards').innerHTML = '';
    document.getElementById('alarmList').innerHTML = '<li class="no-alarms">System Safe</li>';
    activeAlarmsCount = 0;
    document.getElementById('valActiveAlarms').textContent = '0';
    speedChart.update();
}

document.getElementById('btnDemo').addEventListener('click', async (e) => {
    e.preventDefault();
    const btn = e.target;
    if(btn.style.opacity === '0.5') return; 
    
    // Auto-switch to DEMO mode so the user can see the demo vehicles
    if (currentMode !== 'DEMO') {
        document.getElementById('modeDemo').click();
    }
    
    btn.textContent = "▶ RUNNING...";
    btn.style.opacity = '0.5';
    try { await fetch('/api/demo', {method: 'POST'}); } catch (e) {}
    setTimeout(() => {
        btn.textContent = "▶ RUN DEMO";
        btn.style.opacity = '1';
    }, 60000); // Lock for exactly 60 seconds (duration of the physics engine loop)
});

document.getElementById('btnSpoof').addEventListener('click', async (e) => {
    e.preventDefault();
    const btn = e.target;
    if(btn.style.opacity === '0.5') return; 
    btn.textContent = "INJECTING...";
    btn.style.opacity = '0.5';
    try { await fetch('/api/spoof', {method: 'POST'}); } catch (e) {}
    setTimeout(() => {
        btn.textContent = "⚠️ SPOOF ATTACK";
        btn.style.opacity = '1';
    }, 2000);
});
