function initDailyChart(data) {
    const ctx = document.getElementById('dailyPnlChart');
    if (!ctx) return;
    const labels = data.map(d => d.date);
    const values = data.map(d => d.daily_pnl);
    let cumulative = 0;
    const cumulativeValues = values.map(v => { cumulative += v; return cumulative; });
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Daily P/L',
                    data: values,
                    borderColor: 'rgba(52, 211, 153, 0.8)',
                    backgroundColor: 'rgba(52, 211, 153, 0.1)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 3,
                    pointHoverRadius: 6,
                },
                {
                    label: 'Cumulative P/L',
                    data: cumulativeValues,
                    borderColor: 'rgba(56, 189, 248, 0.8)',
                    backgroundColor: 'rgba(56, 189, 248, 0.05)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 2,
                    borderDash: [5, 5],
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: 'index' },
            plugins: {
                legend: { labels: { color: '#94a3b8', font: { family: 'Inter' } } },
                tooltip: {
                    backgroundColor: 'rgba(15, 23, 42, 0.9)',
                    borderColor: 'rgba(148, 163, 184, 0.2)',
                    borderWidth: 1,
                    titleColor: '#f1f5f9',
                    bodyColor: '#cbd5e1',
                    callbacks: {
                        label: function(ctx) { return ctx.dataset.label + ': $' + ctx.parsed.y.toFixed(2); }
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(148, 163, 184, 0.05)' },
                    ticks: { color: '#64748b', font: { family: 'Inter', size: 11 } }
                },
                y: {
                    grid: { color: 'rgba(148, 163, 184, 0.05)' },
                    ticks: {
                        color: '#64748b',
                        font: { family: 'Inter', size: 11 },
                        callback: function(v) { return '$' + v.toFixed(0); }
                    }
                }
            }
        }
    });
}
