const state = {
    history: [
        {time: "Session Start", price: "5061.70", isBullish: true},
        {time: "Volatility Peak", price: "5075.20", isBullish: false},
        {time: "Support Retest", price: "5058.40", isBullish: true}
    ],
    idx: 0
};

function update(data) {
    const bull = document.getElementById('bullzen-puppet');
    const bear = document.getElementById('bearaku-puppet');
    const priceText = document.getElementById('price');
    const winnerText = document.getElementById('winner');

    priceText.textContent = data.price;

    // Reset Classes
    bull.classList.remove('attacking');
    bear.classList.remove('attacking');

    if(data.isBullish) {
        bull.classList.add('attacking');
        bull.style.filter = "drop-shadow(0 0 30px rgba(57,217,138,0.6))";
        bear.style.filter = "brightness(0.4) grayscale(1)";
        winnerText.textContent = "BULLZEN";
        winnerText.style.color = "#39d98a";
    } else {
        bear.classList.add('attacking');
        bear.style.filter = "drop-shadow(0 0 30px rgba(255,93,93,0.6))";
        bull.style.filter = "brightness(0.4) grayscale(1)";
        winnerText.textContent = "BEARAKU";
        winnerText.style.color = "#ff5d5d";
    }
}

setInterval(() => {
    update(state.history[state.idx]);
    state.idx = (state.idx + 1) % state.history.length;
}, 3000);
