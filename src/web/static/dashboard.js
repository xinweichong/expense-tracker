const API = '';
let trendChart = null;
let categoryChart = null;

document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const password = document.getElementById('password').value;
    try {
        const res = await fetch(`${API}/api/login`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({password}),
        });
        if (res.ok) {
            document.getElementById('login-overlay').style.display = 'none';
            document.getElementById('dashboard').style.display = 'block';
            setDefaultDates();
            loadDashboard();
        } else {
            document.getElementById('login-error').style.display = 'block';
        }
    } catch (err) {
        document.getElementById('login-error').style.display = 'block';
    }
});

function setDefaultDates() {
    const today = new Date();
    const start = new Date(today.getFullYear(), today.getMonth(), 1);
    document.getElementById('end-date').value = formatDate(today);
    document.getElementById('start-date').value = formatDate(start);
}

function formatDate(d) {
    return d.toISOString().split('T')[0];
}

async function loadDashboard() {
    const start = document.getElementById('start-date').value;
    const end = document.getElementById('end-date').value;
    const [summary, transactions] = await Promise.all([
        fetch(`${API}/api/summary?start_date=${start}&end_date=${end}`).then(r => r.json()),
        fetch(`${API}/api/transactions?start_date=${start}&end_date=${end}&limit=20`).then(r => r.json()),
    ]);
    renderSummary(summary);
    renderCategoryChart(summary);
    renderTransactions(transactions);
}

function renderSummary(summary) {
    const cards = document.getElementById('summary-cards');
    cards.innerHTML = `
        <div class="card"><h3>Total Spending</h3><div class="value">$${summary.total.toFixed(2)}</div></div>
        ${Object.entries(summary.by_category).map(([cat, amt]) =>
            `<div class="card"><h3>${cat}</h3><div class="value">$${amt.toFixed(2)}</div></div>`
        ).join('')}
    `;
}

function renderCategoryChart(summary) {
    const ctx = document.getElementById('category-chart').getContext('2d');
    if (categoryChart) categoryChart.destroy();
    const labels = Object.keys(summary.by_category);
    const data = Object.values(summary.by_category);
    const colors = ['#e94560','#0f3460','#16213e','#533483','#e94560','#1a1a2e'];
    categoryChart = new Chart(ctx, {
        type: 'doughnut',
        data: { labels, datasets: [{ data, backgroundColor: colors.slice(0, labels.length) }] },
        options: { responsive: true, plugins: { legend: { position: 'bottom' } } },
    });
}

function renderTransactions(transactions) {
    const tbody = document.querySelector('#tx-table tbody');
    tbody.innerHTML = transactions.map(tx => `
        <tr>
            <td>${(tx.transaction_date || '').split('T')[0]}</td>
            <td>${tx.merchant || '-'}</td>
            <td>${tx.category || '-'}</td>
            <td>$${tx.amount.toFixed(2)}</td>
        </tr>
    `).join('');
}
