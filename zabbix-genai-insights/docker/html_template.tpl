<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zabbix GenAI Insights</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #0a0f1e;
            --bg-surface: #111827;
            --card-bg: #1a2236;
            --card-bg-hover: #1e293b;
            --accent: #38bdf8;
            --accent-glow: rgba(56, 189, 248, 0.15);
            --accent-pending: #f59e0b;
            --accent-error: #ef4444;
            --accent-success: #10b981;
            --text: #f1f5f9;
            --text-secondary: #cbd5e1;
            --text-muted: #64748b;
            --border: #1e293b;
            --border-hover: #334155;
            --severity-disaster: #ff2d55;
            --severity-high: #ff6b35;
            --severity-average: #f59e0b;
            --severity-warning: #fbbf24;
            --severity-info: #38bdf8;
            --severity-default: #64748b;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }}

        /* --- Header --- */
        .header {{
            background: var(--bg-surface);
            border-bottom: 1px solid var(--border);
            padding: 20px 24px;
            position: sticky;
            top: 0;
            z-index: 100;
            backdrop-filter: blur(12px);
        }}
        .header-inner {{
            max-width: 1100px;
            margin: 0 auto;
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 16px;
        }}
        .logo {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .logo-icon {{
            width: 36px;
            height: 36px;
            background: linear-gradient(135deg, var(--accent), #818cf8);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.1rem;
        }}
        .logo h1 {{
            font-size: 1.25rem;
            font-weight: 600;
            color: var(--text);
            letter-spacing: -0.02em;
        }}
        .logo h1 span {{
            color: var(--accent);
        }}

        /* --- Stats bar --- */
        .stats-bar {{
            display: flex;
            gap: 6px;
            align-items: center;
            flex-wrap: wrap;
        }}
        .stat-pill {{
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 5px 12px;
            border-radius: 99px;
            font-size: 0.75rem;
            font-weight: 600;
            background: var(--card-bg);
            border: 1px solid var(--border);
            color: var(--text-secondary);
        }}
        .stat-pill .dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }}
        .stat-pill.total .dot {{ background: var(--accent); }}
        .stat-pill.completed .dot {{ background: var(--accent-success); }}
        .stat-pill.pending .dot {{ background: var(--accent-pending); animation: pulse 2s infinite; }}
        .stat-pill.error .dot {{ background: var(--accent-error); }}

        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.4; }}
        }}

        /* --- Search / Filter --- */
        .toolbar {{
            max-width: 1100px;
            margin: 20px auto 0;
            padding: 0 24px;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}
        .search-box {{
            flex: 1;
            min-width: 200px;
            position: relative;
        }}
        .search-box input {{
            width: 100%;
            padding: 10px 14px 10px 38px;
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 10px;
            color: var(--text);
            font-size: 0.875rem;
            font-family: inherit;
            outline: none;
            transition: border-color 0.2s;
        }}
        .search-box input::placeholder {{ color: var(--text-muted); }}
        .search-box input:focus {{ border-color: var(--accent); }}
        .search-box svg {{
            position: absolute;
            left: 12px;
            top: 50%;
            transform: translateY(-50%);
            width: 16px;
            height: 16px;
            color: var(--text-muted);
        }}
        .filter-btn {{
            padding: 10px 16px;
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 10px;
            color: var(--text-muted);
            font-size: 0.8rem;
            font-weight: 500;
            font-family: inherit;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .filter-btn:hover, .filter-btn.active {{
            border-color: var(--accent);
            color: var(--accent);
            background: var(--accent-glow);
        }}

        /* --- Main content --- */
        .main {{
            max-width: 1100px;
            margin: 0 auto;
            padding: 20px 24px 40px;
            width: 100%;
            flex: 1;
        }}

        /* --- Insight cards --- */
        .insight-list {{
            list-style: none;
            display: grid;
            gap: 12px;
        }}
        .insight-card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 14px;
            overflow: hidden;
            transition: all 0.2s ease;
        }}
        .insight-card:hover {{
            border-color: var(--border-hover);
            background: var(--card-bg-hover);
            box-shadow: 0 4px 24px rgba(0, 0, 0, 0.2);
        }}
        .insight-link {{
            text-decoration: none;
            color: inherit;
            display: block;
            padding: 18px 20px;
        }}

        /* Card top row */
        .card-top {{
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 10px;
        }}
        .card-title {{
            font-weight: 600;
            font-size: 0.95rem;
            color: var(--text);
            line-height: 1.4;
            flex: 1;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }}
        .status-badge {{
            flex-shrink: 0;
            font-size: 0.65rem;
            padding: 3px 10px;
            border-radius: 99px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }}
        .status-completed {{ background: rgba(16, 185, 129, 0.15); color: var(--accent-success); }}
        .status-pending {{ background: rgba(245, 158, 11, 0.15); color: var(--accent-pending); }}
        .status-error {{ background: rgba(239, 68, 68, 0.15); color: var(--accent-error); }}

        /* Card meta row */
        .card-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px 16px;
            margin-bottom: 10px;
        }}
        .meta-tag {{
            display: inline-flex;
            align-items: center;
            gap: 5px;
            font-size: 0.75rem;
            color: var(--text-muted);
        }}
        .meta-tag svg {{
            width: 13px;
            height: 13px;
            flex-shrink: 0;
        }}
        .severity-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            flex-shrink: 0;
        }}
        .severity-disaster {{ background: var(--severity-disaster); box-shadow: 0 0 6px var(--severity-disaster); }}
        .severity-high {{ background: var(--severity-high); box-shadow: 0 0 6px var(--severity-high); }}
        .severity-average {{ background: var(--severity-average); }}
        .severity-warning {{ background: var(--severity-warning); }}
        .severity-information {{ background: var(--severity-info); }}
        .severity-default {{ background: var(--severity-default); }}

        /* Card preview */
        .card-preview {{
            font-size: 0.825rem;
            color: var(--text-muted);
            line-height: 1.55;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }}

        /* --- Empty state --- */
        .empty-state {{
            text-align: center;
            padding: 80px 40px;
            color: var(--text-muted);
            background: var(--card-bg);
            border-radius: 16px;
            border: 2px dashed var(--border);
        }}
        .empty-state .empty-icon {{
            font-size: 3rem;
            margin-bottom: 16px;
            opacity: 0.5;
        }}
        .empty-state p {{
            font-size: 0.95rem;
            max-width: 360px;
            margin: 0 auto;
            line-height: 1.6;
        }}

        /* --- Footer --- */
        .footer {{
            border-top: 1px solid var(--border);
            padding: 16px 24px;
            text-align: center;
            font-size: 0.7rem;
            color: var(--text-muted);
        }}
        .footer span {{
            opacity: 0.7;
        }}

        /* --- Detail page --- */
        .detail-header {{
            margin-bottom: 24px;
        }}
        .detail-header h2 {{
            font-size: 1.3rem;
            font-weight: 600;
            margin-bottom: 8px;
        }}
        .detail-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px 20px;
            margin-bottom: 16px;
        }}
        .back-link {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            color: var(--accent);
            text-decoration: none;
            font-size: 0.85rem;
            font-weight: 500;
            margin-bottom: 20px;
        }}
        .back-link:hover {{ text-decoration: underline; }}
        .insight-body {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 24px;
            font-size: 0.9rem;
            line-height: 1.7;
            color: var(--text-secondary);
            white-space: pre-wrap;
            word-wrap: break-word;
            overflow-x: auto;
        }}
        .insight-body strong, .insight-body b {{
            color: var(--text);
        }}
        .pending-banner {{
            background: rgba(245, 158, 11, 0.1);
            border: 1px solid rgba(245, 158, 11, 0.3);
            border-radius: 12px;
            padding: 20px 24px;
            text-align: center;
            color: var(--accent-pending);
            font-weight: 500;
        }}
        .pending-banner .spinner {{
            display: inline-block;
            width: 18px;
            height: 18px;
            border: 2px solid rgba(245, 158, 11, 0.3);
            border-top-color: var(--accent-pending);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin-right: 8px;
            vertical-align: middle;
        }}
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}

        /* --- Responsive --- */
        @media (max-width: 640px) {{
            .header-inner {{ flex-direction: column; align-items: flex-start; }}
            .stats-bar {{ width: 100%; }}
            .toolbar {{ flex-direction: column; }}
            .search-box {{ min-width: 100%; }}
            .card-meta {{ gap: 6px 12px; }}
        }}
    </style>
</head>
<body>
    <header class="header">
        <div class="header-inner">
            <div class="logo">
                <div class="logo-icon">🤖</div>
                <h1>GenAI <span>Insights</span></h1>
            </div>
            {stats_bar}
        </div>
    </header>

    <div class="toolbar" id="toolbar" style="{toolbar_display}">
        <div class="search-box">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
            <input type="text" id="searchInput" placeholder="Search by host, trigger, event ID..." oninput="filterCards()">
        </div>
        <button class="filter-btn active" data-filter="all" onclick="setFilter('all', this)">All</button>
        <button class="filter-btn" data-filter="completed" onclick="setFilter('completed', this)">Completed</button>
        <button class="filter-btn" data-filter="pending" onclick="setFilter('pending', this)">Pending</button>
        <button class="filter-btn" data-filter="error" onclick="setFilter('error', this)">Error</button>
    </div>

    <main class="main">
        {content}
    </main>

    <footer class="footer">
        <span>Zabbix GenAI Insights &middot; {provider_info}</span>
    </footer>

    <script>
        let currentFilter = 'all';

        function setFilter(filter, btn) {{
            currentFilter = filter;
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            filterCards();
        }}

        function filterCards() {{
            const query = (document.getElementById('searchInput')?.value || '').toLowerCase();
            document.querySelectorAll('.insight-card').forEach(card => {{
                const text = card.textContent.toLowerCase();
                const status = card.dataset.status;
                const matchesSearch = !query || text.includes(query);
                const matchesFilter = currentFilter === 'all' || status === currentFilter;
                card.style.display = (matchesSearch && matchesFilter) ? '' : 'none';
            }});
        }}

        // Auto-refresh if any PENDING items exist
        if (document.querySelector('.insight-card[data-status="pending"]')) {{
            setTimeout(() => location.reload(), 8000);
        }}
    </script>
</body>
</html>
