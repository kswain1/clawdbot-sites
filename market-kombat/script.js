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

function restartReplay() {
    if(timerHandle) clearInterval(timerHandle);
    
    applyFrame(dailyData[currentDay][idx]);
    
    timerHandle = setInterval(() => {
        idx = (idx + 1) % dailyData[currentDay].length;
        applyFrame(dailyData[currentDay][idx]);
    }, 4000);
}

// Init
restartReplay();
