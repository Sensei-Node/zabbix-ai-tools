<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{page_title} — GenAI Insights</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #0a0f1e;
            --bg-surface: #111827;
            --card-bg: #1a2236;
            --accent: #38bdf8;
            --accent-pending: #f59e0b;
            --accent-error: #ef4444;
            --accent-success: #10b981;
            --text: #f1f5f9;
            --text-secondary: #cbd5e1;
            --text-muted: #64748b;
            --border: #1e293b;
            --severity-disaster: #ff2d55;
            --severity-high: #ff6b35;
            --severity-average: #f59e0b;
            --severity-warning: #fbbf24;
            --severity-info: #38bdf8;
            --severity-default: #64748b;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            min-height: 100vh;
        }}
        .header {{
            background: var(--bg-surface);
            border-bottom: 1px solid var(--border);
            padding: 16px 24px;
        }}
        .header-inner {{
            max-width: 900px;
            margin: 0 auto;
        }}
        .back-link {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            color: var(--accent);
            text-decoration: none;
            font-size: 0.85rem;
            font-weight: 500;
        }}
        .back-link:hover {{ text-decoration: underline; }}
        .main {{
            max-width: 900px;
            margin: 0 auto;
            padding: 28px 24px 60px;
        }}
        .detail-title {{
            font-size: 1.35rem;
            font-weight: 600;
            margin-bottom: 12px;
            line-height: 1.4;
        }}
        .detail-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px 18px;
            margin-bottom: 24px;
        }}
        .meta-tag {{
            display: inline-flex;
            align-items: center;
            gap: 5px;
            font-size: 0.78rem;
            color: var(--text-muted);
        }}
        .meta-tag svg {{ width: 14px; height: 14px; flex-shrink: 0; }}
        .severity-dot {{
            width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
        }}
        .severity-disaster {{ background: var(--severity-disaster); box-shadow: 0 0 6px var(--severity-disaster); }}
        .severity-high {{ background: var(--severity-high); box-shadow: 0 0 6px var(--severity-high); }}
        .severity-average {{ background: var(--severity-average); }}
        .severity-warning {{ background: var(--severity-warning); }}
        .severity-information {{ background: var(--severity-info); }}
        .severity-default {{ background: var(--severity-default); }}
        .status-badge {{
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

        .insight-body {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 28px;
            font-size: 0.88rem;
            line-height: 1.75;
            color: var(--text-secondary);
            white-space: pre-wrap;
            word-wrap: break-word;
            overflow-x: auto;
        }}
        .insight-body strong, .insight-body b {{ color: var(--text); }}

        .pending-banner {{
            background: rgba(245, 158, 11, 0.08);
            border: 1px solid rgba(245, 158, 11, 0.25);
            border-radius: 14px;
            padding: 40px 24px;
            text-align: center;
            color: var(--accent-pending);
        }}
        .spinner {{
            display: inline-block;
            width: 20px; height: 20px;
            border: 2px solid rgba(245, 158, 11, 0.3);
            border-top-color: var(--accent-pending);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin-right: 10px;
            vertical-align: middle;
        }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}

        .footer {{
            border-top: 1px solid var(--border);
            padding: 16px 24px;
            text-align: center;
            font-size: 0.7rem;
            color: var(--text-muted);
        }}

        @media (max-width: 640px) {{
            .detail-title {{ font-size: 1.1rem; }}
            .insight-body {{ padding: 18px; font-size: 0.82rem; }}
        }}
    </style>
</head>
<body>
    <header class="header">
        <div class="header-inner">
            <a href="/outputs" class="back-link">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="m15 18-6-6 6-6"/></svg>
                Back to Insights
            </a>
        </div>
    </header>
    <main class="main">
        <h1 class="detail-title">{detail_title}</h1>
        <div class="detail-meta">
            {detail_meta}
        </div>
        {detail_body}
    </main>
    <footer class="footer">
        <span>Zabbix GenAI Insights</span>
    </footer>
    {auto_refresh}
</body>
</html>
