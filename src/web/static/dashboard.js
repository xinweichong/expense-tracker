/* Expense Tracker — Dashboard JS */

const API = '';
let donutChart = null;
let lineChart = null;

// State
let currentPeriod = 'day';
let periodDate = new Date();
let txOffset = 0;
const TX_PAGE = 20;
let currentSort = 'date';
let allTransactions = [];

// Category color map
const CAT_COLORS = {
  Food: '#FF9F0A',
  Transport: '#0A84FF',
  Shopping: '#BF5AF2',
  Bills: '#30D158',
  Entertainment: '#FF375F',
  Other: '#8E8E93',
  Income: '#30D158',
};
const FALLBACK_COLOR = '#8E8E93';

function catColor(cat) {
  return CAT_COLORS[cat] || FALLBACK_COLOR;
}

function catClass(cat) {
  if (!cat) return 'cat-other';
  const key = cat.toLowerCase();
  if (key === 'food') return 'cat-food';
  if (key === 'transport') return 'cat-transport';
  if (key === 'shopping') return 'cat-shopping';
  if (key === 'bills') return 'cat-bills';
  if (key === 'entertainment') return 'cat-entertainment';
  if (key === 'income') return 'cat-income';
  return 'cat-other';
}

function catIconClass(cat) {
  return catClass(cat) + '-bg';
}

// === Date helpers ===
function fmtDate(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const MONTHS_FULL = ['January','February','March','April','May','June','July','August','September','October','November','December'];

function getPeriodLabel() {
  const d = periodDate;
  if (currentPeriod === 'day') {
    return `${MONTHS[d.getMonth()]} ${d.getDate()}`;
  } else if (currentPeriod === 'week') {
    const start = getWeekStart(d);
    const end = new Date(start);
    end.setDate(end.getDate() + 6);
    return `${MONTHS[start.getMonth()]} ${start.getDate()} \u2013 ${MONTHS[end.getMonth()]} ${end.getDate()}`;
  } else {
    return `${MONTHS_FULL[d.getMonth()]} ${d.getFullYear()}`;
  }
}

function getWeekStart(d) {
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1); // Monday
  const s = new Date(d);
  s.setDate(diff);
  s.setHours(0, 0, 0, 0);
  return s;
}

function getDateRange() {
  const d = periodDate;
  let start, end;
  if (currentPeriod === 'day') {
    start = new Date(d);
    start.setHours(0, 0, 0, 0);
    end = new Date(start);
  } else if (currentPeriod === 'week') {
    start = getWeekStart(d);
    end = new Date(start);
    end.setDate(end.getDate() + 6);
  } else {
    start = new Date(d.getFullYear(), d.getMonth(), 1);
    end = new Date(d.getFullYear(), d.getMonth() + 1, 0);
  }
  return { start: fmtDate(start), end: fmtDate(end) };
}

// === Period navigation ===
function shiftPeriod(delta) {
  if (currentPeriod === 'day') {
    periodDate.setDate(periodDate.getDate() + delta);
  } else if (currentPeriod === 'week') {
    periodDate.setDate(periodDate.getDate() + delta * 7);
  } else {
    periodDate.setMonth(periodDate.getMonth() + delta);
  }
  periodDate.setHours(0, 0, 0, 0);
  loadAll();
}

function setPeriod(period) {
  currentPeriod = period;
  periodDate = new Date();
  periodDate.setHours(0, 0, 0, 0);
  document.querySelectorAll('.period-tab').forEach(t => {
    t.classList.toggle('active', t.dataset.period === period);
  });
  loadAll();
}

// === Login ===
document.getElementById('login-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const password = document.getElementById('password').value;
  try {
    const res = await fetch(`${API}/api/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    });
    if (res.ok) {
      document.getElementById('login-overlay').style.display = 'none';
      document.getElementById('dashboard').style.display = 'block';
      initDashboard();
    } else {
      document.getElementById('login-error').style.display = 'block';
    }
  } catch {
    document.getElementById('login-error').style.display = 'block';
  }
});

// === Init ===
function initDashboard() {
  // Period tabs
  document.querySelectorAll('.period-tab').forEach(tab => {
    tab.addEventListener('click', () => setPeriod(tab.dataset.period));
  });
  // Period nav
  document.getElementById('prev-period').addEventListener('click', () => shiftPeriod(-1));
  document.getElementById('next-period').addEventListener('click', () => shiftPeriod(1));
  // Sort buttons
  document.querySelectorAll('.sort-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      currentSort = btn.dataset.sort;
      document.querySelectorAll('.sort-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      renderTransactions();
    });
  });
  // Filter selects
  document.getElementById('filter-category').addEventListener('change', () => { txOffset = 0; loadTransactions(); });
  document.getElementById('filter-merchant').addEventListener('change', () => { txOffset = 0; loadTransactions(); });
  // Load more
  document.getElementById('load-more').addEventListener('click', loadMoreTransactions);

  populateFilters();
  loadAll();
}

// === Populate filters ===
async function populateFilters() {
  try {
    const [cats, merchants] = await Promise.all([
      fetch(`${API}/api/categories`).then(r => r.json()),
      fetch(`${API}/api/merchants`).then(r => r.json()),
    ]);
    const catSelect = document.getElementById('filter-category');
    catSelect.innerHTML = '<option value="">All Categories</option>';
    cats.forEach(c => {
      const opt = document.createElement('option');
      opt.value = c.name;
      opt.textContent = c.name;
      catSelect.appendChild(opt);
    });
    const merSelect = document.getElementById('filter-merchant');
    merSelect.innerHTML = '<option value="">All Merchants</option>';
    merchants.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m;
      opt.textContent = m;
      merSelect.appendChild(opt);
    });
  } catch {
    // filters will remain with defaults
  }
}

// === Load all data ===
async function loadAll() {
  document.getElementById('period-label').textContent = getPeriodLabel();
  const { start, end } = getDateRange();
  try {
    const [summary, trend, insights, balance] = await Promise.all([
      fetch(`${API}/api/summary?start_date=${start}&end_date=${end}`).then(r => r.json()),
      fetch(`${API}/api/trend?start_date=${start}&end_date=${end}`).then(r => r.json()),
      fetch(`${API}/api/insights?start_date=${start}&end_date=${end}`).then(r => r.json()),
      fetch(`${API}/api/balance?start_date=${start}&end_date=${end}`).then(r => r.json()),
    ]);
    renderHero(summary, balance);
    renderDonut(summary);
    renderLine(trend);
    renderInsights(insights);
  } catch (err) {
    console.error('Failed to load dashboard data:', err);
  }
  // Reset and load transactions
  txOffset = 0;
  allTransactions = [];
  loadTransactions();
}

// === Render Hero ===
function renderHero(summary, balance) {
  const hero = document.getElementById('hero');
  const total = balance.income > 0 ? balance.net : summary.total;
  const isPositive = total >= 0;
  const prefix = balance.income > 0 ? 'Net Balance' : 'Total Spent';
  let html = `
    <div class="hero-label">${prefix}</div>
    <div class="hero-total ${isPositive ? 'positive' : 'negative'}">$${Math.abs(total).toFixed(2)}</div>
  `;
  if (balance.income > 0) {
    html += `
      <div class="hero-balance">
        <div class="balance-item earned">Earned <span>$${balance.income.toFixed(2)}</span></div>
        <div class="balance-item spent">Spent <span>$${balance.expenses.toFixed(2)}</span></div>
        <div class="balance-item net">Net <span>$${balance.net.toFixed(2)}</span></div>
      </div>
    `;
  }
  hero.innerHTML = html;
}

// === Render Donut ===
function renderDonut(summary) {
  const ctx = document.getElementById('donut-chart');
  if (donutChart) donutChart.destroy();
  const labels = Object.keys(summary.by_category);
  const data = Object.values(summary.by_category);
  if (labels.length === 0) {
    const legend = document.getElementById('donut-legend');
    legend.innerHTML = '<div class="empty-state" style="padding:1rem">No expenses</div>';
    return;
  }
  const colors = labels.map(l => catColor(l));
  donutChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data,
        backgroundColor: colors,
        borderColor: 'transparent',
        borderWidth: 0,
        hoverOffset: 6,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      cutout: '65%',
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#222228',
          titleColor: '#F0F0F2',
          bodyColor: '#F0F0F2',
          borderColor: 'rgba(255,255,255,0.06)',
          borderWidth: 1,
          padding: 10,
          cornerRadius: 8,
          callbacks: {
            label: (ctx) => ` $${ctx.parsed.toFixed(2)}`,
          },
        },
      },
    },
  });
  // Legend
  const legend = document.getElementById('donut-legend');
  legend.innerHTML = labels.map((l, i) => `
    <div class="legend-item">
      <span class="legend-dot" style="background:${colors[i]}"></span>
      ${l} ($${data[i].toFixed(2)})
    </div>
  `).join('');
}

// === Render Line Chart ===
function renderLine(trend) {
  const ctx = document.getElementById('line-chart');
  if (lineChart) lineChart.destroy();
  if (!trend || trend.length === 0) {
    return;
  }
  const labels = trend.map(t => {
    const d = new Date(t.date + 'T00:00:00');
    return `${MONTHS[d.getMonth()]} ${d.getDate()}`;
  });
  const data = trend.map(t => t.amount);

  lineChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        data,
        borderColor: '#FF6B6B',
        borderWidth: 2,
        pointRadius: 0,
        pointHitRadius: 10,
        pointHoverRadius: 4,
        pointHoverBackgroundColor: '#FF6B6B',
        fill: true,
        backgroundColor: (context) => {
          const chart = context.chart;
          const { ctx: c, chartArea } = chart;
          if (!chartArea) return 'rgba(255,107,107,0.1)';
          const gradient = c.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
          gradient.addColorStop(0, 'rgba(255,107,107,0.25)');
          gradient.addColorStop(1, 'rgba(255,107,107,0)');
          return gradient;
        },
        tension: 0.35,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      interaction: { intersect: false, mode: 'index' },
      scales: {
        x: {
          grid: { color: 'rgba(255,255,255,0.04)' },
          ticks: { color: '#6E6E78', font: { size: 10, family: "'DM Sans'" }, maxRotation: 0, maxTicksLimit: 7 },
          border: { color: 'rgba(255,255,255,0.06)' },
        },
        y: {
          grid: { color: 'rgba(255,255,255,0.04)' },
          ticks: {
            color: '#6E6E78',
            font: { size: 10, family: "'DM Sans'" },
            callback: (v) => '$' + v.toFixed(0),
          },
          border: { color: 'rgba(255,255,255,0.06)' },
          beginAtZero: true,
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#222228',
          titleColor: '#F0F0F2',
          bodyColor: '#F0F0F2',
          borderColor: 'rgba(255,255,255,0.06)',
          borderWidth: 1,
          padding: 10,
          cornerRadius: 8,
          callbacks: {
            label: (ctx) => ` $${ctx.parsed.y.toFixed(2)}`,
          },
        },
      },
    },
  });
}

// === Render Insights ===
function renderInsights(insights) {
  const panel = document.getElementById('insights-panel');
  if (!insights) {
    panel.innerHTML = '';
    return;
  }
  let html = '';

  // Average daily
  html += `
    <div class="insight-card">
      <div class="insight-title">Average Daily</div>
      <div class="insight-stat">$${(insights.average_daily || 0).toFixed(2)}</div>
    </div>
  `;

  // Top merchants
  const merchants = insights.merchants || [];
  if (merchants.length > 0) {
    html += `
      <div class="insight-card">
        <div class="insight-title">Top Merchants</div>
        <ul class="merchant-list">
          ${merchants.slice(0, 5).map(m => `
            <li>
              <div>
                <span class="merchant-name">${m.merchant}</span>
                <span class="merchant-meta">${m.visits} visit${m.visits !== 1 ? 's' : ''}</span>
              </div>
              <span class="merchant-total">$${m.total.toFixed(2)}</span>
            </li>
          `).join('')}
        </ul>
      </div>
    `;
  }

  panel.innerHTML = html;
}

// === Transactions ===
async function loadTransactions() {
  const { start, end } = getDateRange();
  const cat = document.getElementById('filter-category').value;
  const merchant = document.getElementById('filter-merchant').value;

  let url = `${API}/api/transactions?start_date=${start}&end_date=${end}&limit=${TX_PAGE}&offset=${txOffset}`;
  if (cat) url += `&category=${encodeURIComponent(cat)}`;
  if (merchant) url += `&merchant_search=${encodeURIComponent(merchant)}`;

  try {
    const txs = await fetch(url).then(r => r.json());
    if (txOffset === 0) {
      allTransactions = txs;
    } else {
      allTransactions = allTransactions.concat(txs);
    }
    document.getElementById('load-more').style.display = txs.length >= TX_PAGE ? 'block' : 'none';
    renderTransactions();
  } catch {
    document.getElementById('tx-list').innerHTML = '<div class="empty-state">Failed to load transactions</div>';
  }
}

function loadMoreTransactions() {
  txOffset += TX_PAGE;
  loadTransactions();
}

function renderTransactions() {
  const list = document.getElementById('tx-list');
  let txs = [...allTransactions];

  // Sort
  if (currentSort === 'amount') {
    txs.sort((a, b) => (b.amount * (b.exchange_rate || 1)) - (a.amount * (a.exchange_rate || 1)));
  } else if (currentSort === 'category') {
    txs.sort((a, b) => (a.category || '').localeCompare(b.category || ''));
  }
  // default: date desc (already from API)

  if (txs.length === 0) {
    list.innerHTML = '<div class="empty-state">No transactions for this period</div>';
    return;
  }

  list.innerHTML = txs.map(tx => {
    const sgd = tx.amount * (tx.exchange_rate || 1);
    const isIncome = tx.type === 'income';
    const amountClass = isIncome ? 'positive' : 'negative';
    const sign = isIncome ? '+' : '-';
    const cat = tx.category || 'Other';
    const cc = catClass(cat);
    const bg = catIconClass(cat);

    // Show SGD equivalent for foreign currency
    let sgdLine = '';
    if (tx.currency && tx.currency !== 'SGD' && tx.exchange_rate && tx.exchange_rate !== 1) {
      sgdLine = `<div class="tx-sgd">${tx.currency} ${tx.amount.toFixed(2)}</div>`;
    }

    const dateStr = (tx.transaction_date || '').split('T')[0];

    return `
      <div class="tx-item">
        <div class="tx-icon ${bg}">${(cat[0] || '?').toUpperCase()}</div>
        <div class="tx-body">
          <div class="tx-merchant">${tx.merchant || tx.description || 'Unknown'}</div>
          <div class="tx-date">${dateStr}</div>
          <span class="tx-cat-badge ${cc}">${cat}</span>
        </div>
        <div class="tx-right">
          <div class="tx-amount ${amountClass}">${sign}$${sgd.toFixed(2)}</div>
          ${sgdLine}
        </div>
      </div>
    `;
  }).join('');
}
