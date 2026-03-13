<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zabbix GenAI Insights</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #0f172a;
            --card-bg: #1e293b;
            --accent: #38bdf8;
            --accent-pending: #fbbf24;
            --text: #f1f5f9;
            --text-muted: #94a3b8;
            --border: #334155;
        }}
        body {{
            font-family: 'Inter', sans-serif;
            background-color: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 40px 20px;
            display: flex;
            justify-content: center;
        }}
        .container {{
            max-width: 800px;
            width: 100%;
        }}
        h1 {{
            font-size: 2rem;
            margin-bottom: 2rem;
            color: var(--accent);
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .insight-list {{
            list-style: none;
            padding: 0;
            display: grid;
            gap: 16px;
        }}
        .insight-card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            overflow: hidden;
            transition: transform 0.2s, border-color 0.2s;
        }}
        .insight-card:hover {{
            transform: translateY(-2px);
            border-color: var(--accent);
        }}
        .insight-link {{
            text-decoration: none;
            color: inherit;
            display: block;
            padding: 20px;
        }}
        .insight-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }}
        .event-id {{
            font-weight: 600;
            color: var(--accent);
            font-size: 1.1rem;
        }}
        .status-badge {{
            font-size: 0.75rem;
            padding: 2px 8px;
            border-radius: 99px;
            font-weight: 600;
            text-transform: uppercase;
        }}
        .status-completed {{ background: rgba(56, 189, 248, 0.2); color: var(--accent); }}
        .status-pending {{ background: rgba(251, 191, 36, 0.2); color: var(--accent-pending); }}
        .status-error {{ background: rgba(239, 68, 68, 0.2); color: #ef4444; }}
        
        .timestamp {{
            font-size: 0.85rem;
            color: var(--text-muted);
        }}
        .preview {{
            font-size: 0.95rem;
            color: var(--text-muted);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .empty-state {{
            text-align: center;
            padding: 60px;
            color: var(--text-muted);
            background: var(--card-bg);
            border-radius: 12px;
            border: 2px dashed var(--border);
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1><span>🤖</span> GenAI Insights</h1>
        {content}
    </div>
</body>
</html>
