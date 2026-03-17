const dailyData = {
  mar13: [
    { time: '09:00 AM CST', price: '5045.80', isBullish: true, comment: 'Bullzen holds institutional floor.', summary: 'Friday London Open rejection @ $5,045.' },
    { time: '11:00 AM CST', price: '5050.60', isBullish: true, comment: 'Bullzen maintains momentum.', summary: 'Weekly high expansion continues.' },
    { time: '02:00 PM CST', price: '5022.00', isBullish: false, comment: 'Bearaku lands a liquidity sweep.', summary: 'Late-day profit taking flush.' }
  ],
  mar15: [
    { time: '07:16 PM CST', price: '4991.00', isBullish: true, comment: 'Bullzen holds $4,991 floor.', summary: 'Asia Moon open exhaustion pierce.' },
    { time: '07:45 PM CST', price: '5000.50', isBullish: true, comment: 'Stage 1 Strike Success.', summary: 'Rapid +9.5pt recovery from the lows.' }
  ],
  mar16: [
    { time: '02:15 UTC', price: '5019.80', isBullish: true, comment: 'Recovery drift continues.', summary: 'Market stabilizes in the value zone.' },
    { time: '08:30 PM CST', price: '5011.40', isBullish: false, comment: 'Consolidation pullback.', summary: 'Bearaku attempts to cool the rally.' }
  ]
};

let currentDay = 'mar16';
let idx = 0;
let timerHandle = null;

function loadDay(dayId) {
    currentDay = dayId;
    idx = 0;
    
    // Update active button state
    document.querySelectorAll('.day-selector .tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('onclick').includes(dayId));
    });

    restartReplay();
}

function applyFrame(frame) {
    document.getElementById('price').textContent = frame.price;
    document.getElementById('timer').textContent = frame.time;
    document.getElementById('winner').textContent = frame.isBullish ? "BULLZEN" : "BEARAKU";
    document.getElementById('commentary').textContent = `@Clawdy: ${frame.comment}`;

    const bull = document.getElementById('bullzenCard');
    const bear = document.getElementById('bearakuCard');

    if(frame.isBullish) {
        bull.className = "fighter-card active";
        bear.className = "fighter-card dim";
    } else {
        bull.className = "fighter-card dim";
        bear.className = "fighter-card active";
    }

    const timeline = document.getElementById('timelineList');
    const data = dailyData[currentDay];
    timeline.innerHTML = data.map((f, i) => `
        <div class="timeline-item ${i === idx ? 'active' : ''}">
            <strong>${f.time}</strong> - $${f.price} <br/>
            <small>${f.summary}</small>
        </div>
    `).join('');
}

const tradeHistory = [
  { date: '2026-03-15 07:38 PM', type: 'BUY', entry: '$4,994.10', exit: '$5,004.50', dur: '24m', res: 'WIN (DB RE-ENTRY)' },
  { date: '2026-03-15 07:16 PM', type: 'BUY', entry: '$4,991.00', exit: '$5,000.50', dur: '12m', res: 'WIN (ASIA PULSE)' },
  { date: '2026-03-12 03:00 PM', type: 'BUY', entry: '$5,084.10', exit: '$5,089.10', dur: '2.0h', res: 'WIN' },
  { date: '2026-03-05 10:00 AM', type: 'BUY', entry: '$5,086.50', exit: '$5,065.50', dur: '1.0h', res: 'LOSS' },
  { date: '2026-02-24 07:00 AM', type: 'BUY', entry: '$5,132.30', exit: '$5,162.20', dur: '2.0h', res: 'WIN' },
  { date: '2026-02-02 02:00 PM', type: 'BUY', entry: '$4,676.30', exit: '$4,699.10', dur: '1.0h', res: 'WIN' },
  { date: '2025-12-29 10:00 AM', type: 'BUY', entry: '$4,359.80', exit: '$4,403.60', dur: '18.0h', res: 'WIN' }
];

let pagedIdx = 0;
const pageSize = 5;

function renderTradeHistory() {
    const body = document.getElementById('tradeLogBody');
    const start = pagedIdx * pageSize;
    const end = start + pageSize;
    const pageData = tradeHistory.slice(start, end);
    const totalPages = Math.ceil(tradeHistory.length / pageSize);

    document.getElementById('pageIndicator').innerText = `PAGE ${pagedIdx + 1} / ${totalPages}`;

    body.innerHTML = pageData.map(t => `
        <tr>
            <td>${t.date}</td>
            <td>${t.type}</td>
            <td>${t.entry}</td>
            <td>${t.exit}</td>
            <td>${t.dur}</td>
            <td><span class="pill pill-${t.res.includes('WIN') ? 'win' : 'loss'}">${t.res}</span></td>
        </tr>
    `).join('');
}

function prevPage() {
    if(pagedIdx > 0) {
        pagedIdx--;
        renderTradeHistory();
    }
}

function nextPage() {
    const totalPages = Math.ceil(tradeHistory.length / pageSize);
    if(pagedIdx < totalPages - 1) {
        pagedIdx++;
        renderTradeHistory();
    }
}

// Update showTab to init history
const originalShowTab = window.showTab;
window.showTab = function(id) {
    if(typeof originalShowTab === 'function') originalShowTab(id);
    if(id === 'backtest') { 
        setTimeout(renderTradeHistory, 100); 
    }
}

// Pulse Timer Logic
let pulseTimerSeconds = 900; 
let pulseTimerHandle = null;

function startPulseTimer() {
    console.log("Aura: Initializing Heartbeat Relay...");
    if(pulseTimerHandle) clearInterval(pulseTimerHandle);
    
    // Reset to current 15-min block alignment if needed, or just start 15m
    pulseTimerHandle = setInterval(() => {
        if(pulseTimerSeconds > 0) {
            pulseTimerSeconds--;
            updatePulseUI();
        } else {
            pulseTimerSeconds = 900;
            const statusPill = document.getElementById('pulseStatus');
            if(statusPill) {
                statusPill.innerText = "FETCHING...";
                statusPill.className = "pill pill-loss"; // Change color during fetch
                setTimeout(() => {
                    statusPill.innerText = "LIVE SYNC";
                    statusPill.className = "pill pill-win";
                }, 3000);
            }
        }
    }, 1000);
}

function updatePulseUI() {
    const minutes = Math.floor(pulseTimerSeconds / 60);
    const seconds = pulseTimerSeconds % 60;
    const display = `${minutes}:${seconds < 10 ? '0' : ''}${seconds}`;
    const timerElem = document.getElementById('nextPulseTimer');
    if(timerElem) {
        timerElem.innerText = display;
    }
}

// Global Init
window.addEventListener('DOMContentLoaded', (event) => {
    restartReplay();
    startPulseTimer();
});
