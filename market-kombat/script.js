// Market Kombat High-Fidelity script.js
const state = {
    mode: 'REPLAY',
    currentIndex: 0,
    history: [],
};

// Simulated History Data (representing fast-paced trading)
// In production, this can be fetched from a CSV or API
function generateMockHistory() {
    let startPrice = 2930;
    const history = [];
    for(let i=0; i<100; i++) {
        let change = (Math.random() - 0.5) * 5;
        let price = startPrice + change;
        history.push({
            timestamp: `Historical T-${100-i}m`,
            price: price.toFixed(2),
            isBullish: change > 0
        });
        startPrice = price;
    }
    return history;
}

function updateArena(data) {
    const bull = document.getElementById('bullzen');
    const bear = document.getElementById('bearaku');
    const priceDisplay = document.getElementById('priceDisplay');
    const sentiment = document.getElementById('sentimentDisplay');
    const timestamp = document.getElementById('timestamp');

    priceDisplay.textContent = data.price;
    timestamp.textContent = data.timestamp;

    if(data.isBullish) {
        bull.style.transform = "scale(1.1) translateX(20px)";
        bull.style.filter = "brightness(1.3) drop-shadow(0 0 30px rgba(57,217,138,0.5))";
        bear.style.transform = "scale(0.9) translateX(10px)";
        bear.style.filter = "brightness(0.5) grayscale(0.5)";
        sentiment.textContent = "BULLISH";
        sentiment.style.color = "#39d98a";
    } else {
        bear.style.transform = "scale(1.1) translateX(-20px)";
        bear.style.filter = "brightness(1.3) drop-shadow(0 0 30px rgba(255,93,93,0.5))";
        bull.style.transform = "scale(0.9) translateX(-10px)";
        bull.style.filter = "brightness(0.5) grayscale(0.5)";
        sentiment.textContent = "BEARISH";
        sentiment.style.color = "#ff5d5d";
    }
}

function startReplay() {
    state.history = generateMockHistory();
    setInterval(() => {
        let current = state.history[state.currentIndex];
        updateArena(current);
        state.currentIndex = (state.currentIndex + 1) % state.history.length;
    }, 1500);
}

document.addEventListener('DOMContentLoaded', () => {
    console.log("Kombat Replay Engine V1.0 - Ready");
    startReplay();
});
