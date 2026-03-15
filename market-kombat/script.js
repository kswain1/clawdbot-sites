const replayData = [
  { time: 'Friday Close', price: '5061.70', isBullish: true, comment: 'Bullzen answer with a sharp comeback.', summary: 'Strong bullish recovery closes the week.' },
  { time: 'London Mid', price: '5045.80', isBullish: false, comment: 'Bearaku lands a heavy breakdown.', summary: 'Sellers drive price hard through local support.' },
  { time: 'NY Open', price: '5050.60', isBullish: true, comment: 'Bullzen attempts recovery bounce.', summary: 'Buyers step in to stabilize the floor.' }
];

let idx = 0;

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
    timeline.innerHTML = replayData.map((f, i) => `
        <div class="timeline-item ${i === idx ? 'active' : ''}">
            <strong>${f.time}</strong> - $${f.price} <br/>
            <small>${f.summary}</small>
        </div>
    `).join('');
}

setInterval(() => {
    applyFrame(replayData[idx]);
    idx = (idx + 1) % replayData.length;
}, 3000);

applyFrame(replayData[0]);
