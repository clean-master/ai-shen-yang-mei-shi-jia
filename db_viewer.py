"""极简 HTTP 数据库查看器。"""

import argparse
import datetime
import http.server
import sqlite3
import urllib.parse
from pathlib import Path

DB_PATH = Path(__file__).parent / "data.db"
ROWS_PER_PAGE = 20

PAGE_HTML = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI 沈阳美食家 数据库</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #f8f9fa;
    color: #333;
    padding: 40px 24px;
    line-height: 1.6;
    -webkit-font-smoothing: antialiased;
  }}
  .container {{
    max-width: 1200px;
    margin: 0 auto;
  }}
  h1 {{
    font-size: 24px;
    font-weight: 700;
    margin-bottom: 4px;
    color: #222;
    letter-spacing: -0.5px;
  }}
  .sub {{
    color: #888;
    font-size: 13px;
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .sub::before {{
    content: "";
    display: inline-block;
    width: 6px;
    height: 6px;
    background: #fb7299;
    border-radius: 50%;
  }}
  .tabs {{
    display: flex;
    gap: 4px;
    margin-bottom: 24px;
    border-bottom: 2px solid #e9ecef;
    padding-bottom: 0;
    flex-wrap: wrap;
  }}
  .tab {{
    padding: 10px 18px;
    font-size: 14px;
    font-weight: 500;
    color: #666;
    text-decoration: none;
    border-radius: 8px 8px 0 0;
    border-bottom: 2px solid transparent;
    margin-bottom: -2px;
    transition: all 0.2s ease;
    cursor: pointer;
  }}
  .tab:hover {{
    color: #fb7299;
    background: rgba(251, 114, 153, 0.05);
  }}
  .tab.active {{
    color: #fb7299;
    border-bottom-color: #fb7299;
    background: rgba(251, 114, 153, 0.08);
    font-weight: 600;
  }}
  h2 {{
    font-size: 16px;
    font-weight: 600;
    margin: 0 0 16px;
    color: #fb7299;
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  h2::before {{
    content: "";
    display: inline-block;
    width: 3px;
    height: 14px;
    background: #fb7299;
    border-radius: 2px;
  }}
  .count {{
    color: #888;
    font-weight: 400;
    font-size: 13px;
  }}
  .table-wrap {{
    background: #fff;
    border: 1px solid #e9ecef;
    border-radius: 10px;
    overflow: auto;
    margin-bottom: 24px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    min-width: 100%;
  }}
  th, td {{
    padding: 10px 14px;
    text-align: left;
  }}
  th {{
    background: #f1f3f5;
    color: #666;
    font-weight: 600;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    position: sticky;
    top: 0;
    z-index: 1;
    border-bottom: 1px solid #e9ecef;
    white-space: nowrap;
  }}
  td {{
    border-bottom: 1px solid #f1f3f5;
    color: #444;
    transition: color 0.15s ease;
  }}
  tbody tr:nth-child(even) {{
    background: #fafbfc;
  }}
  tr:hover {{
    background: #f1f3f5;
  }}
  tr:hover td {{
    color: #222;
  }}
  tr:last-child td {{
    border-bottom: none;
  }}
  .empty {{
    color: #aaa;
    padding: 24px;
    text-align: center;
    font-style: italic;
  }}
  .pagination {{
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 16px;
    margin-top: 8px;
    margin-bottom: 32px;
    font-size: 14px;
  }}
  .pagination a {{
    color: #fb7299;
    text-decoration: none;
    padding: 6px 14px;
    border-radius: 6px;
    border: 1px solid #fb7299;
    transition: all 0.2s ease;
    font-weight: 500;
  }}
  .pagination a:hover {{
    background: #fb7299;
    color: #fff;
  }}
  .pagination a.disabled {{
    color: #ccc;
    border-color: #ddd;
    pointer-events: none;
    cursor: default;
  }}
  .pagination .page-info {{
    color: #666;
    font-weight: 500;
  }}
  @media (max-width: 768px) {{
    body {{ padding: 20px 12px; }}
    th, td {{ padding: 8px 10px; font-size: 12px; }}
    h1 {{ font-size: 20px; }}
    .tab {{ padding: 8px 12px; font-size: 13px; }}
  }}
</style>
</head>
<body>
<div class="container">
<h1>📊 AI 沈阳美食家 数据库</h1>
<p class="sub">{db_path} · {total_rows} 行 · 刷新页面以更新</p>
<div class="tabs">
{tabs}
</div>
{table_section}
</div>
</body>
</html>"""

TABLE_HTML = """<h2>{name} <span class="count">({count} 行)</span></h2>
<div class="table-wrap">
<table>
<thead><tr>{headers}</tr></thead>
<tbody>{rows}</tbody>
</table>
</div>
{pagination}"""


def _get_valid_tables(cursor: sqlite3.Cursor) -> set[str]:
    """从 sqlite_master 获取合法表名白名单。"""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    return {row[0] for row in cursor.fetchall()}


def build_page(db_path: str, table_name: str, page: int) -> str:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    valid_tables = _get_valid_tables(cursor)
    if table_name not in valid_tables:
        table_name = next(iter(valid_tables), "")

    total_rows = 0
    for name in valid_tables:
        cursor.execute(f'SELECT COUNT(*) FROM "{name}"')
        total_rows += cursor.fetchone()[0]

    tabs_html = ""
    for name in valid_tables:
        active_class = "active" if name == table_name else ""
        tabs_html += f'<a class="tab {active_class}" href="/?table={name}&page=1">{name}</a>\n'

    table_section = ""
    if table_name:
        cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
        count = cursor.fetchone()[0]

        total_pages = max(1, (count + ROWS_PER_PAGE - 1) // ROWS_PER_PAGE)
        page = max(1, min(page, total_pages))
        offset = (page - 1) * ROWS_PER_PAGE

        cursor.execute(f'SELECT * FROM "{table_name}" LIMIT ? OFFSET ?', (ROWS_PER_PAGE, offset))
        col_names = [desc[0] for desc in cursor.description]
        rows_data = cursor.fetchall()

        timestamp_cols = [i for i, c in enumerate(col_names) if c in ("created_at", "sent_at") or c.endswith("_at")]

        headers = "".join(f"<th>{c}</th>" for c in col_names)
        if rows_data:
            row_html = ""
            for row in rows_data:
                cells = []
                for i, v in enumerate(row):
                    if i in timestamp_cols and isinstance(v, (int, float)):
                        try:
                            dt = datetime.datetime.fromtimestamp(float(v))
                            v = dt.strftime("%Y-%m-%d %H:%M:%S")
                        except (ValueError, OSError, OverflowError):
                            pass
                    cells.append(f"<td>{v}</td>")
                row_html += "<tr>" + "".join(cells) + "</tr>"
        else:
            row_html = '<tr><td class="empty" colspan="{}">（空）</td></tr>'.format(len(col_names))

        prev_link = f"/?table={table_name}&page={page - 1}" if page > 1 else ""
        next_link = f"/?table={table_name}&page={page + 1}" if page < total_pages else ""
        prev_class = "disabled" if not prev_link else ""
        next_class = "disabled" if not next_link else ""

        pagination_html = f"""<div class="pagination">
<a class="{prev_class}" href="{prev_link or '#'}">上一页</a>
<span class="page-info">第 {page} / {total_pages} 页</span>
<a class="{next_class}" href="{next_link or '#'}">下一页</a>
</div>"""

        table_section = TABLE_HTML.format(
            name=table_name,
            count=count,
            headers=headers,
            rows=row_html,
            pagination=pagination_html,
        )

    conn.close()
    return PAGE_HTML.format(
        db_path=db_path,
        total_rows=total_rows,
        tabs=tabs_html,
        table_section=table_section,
    )


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/":
            self.send_error(404)
            return

        query = urllib.parse.parse_qs(parsed.query)
        table_name = query.get("table", ["rejected_content"])[0]
        try:
            page = int(query.get("page", ["1"])[0])
        except ValueError:
            page = 1

        html = build_page(str(DB_PATH), table_name, page)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode())

    def do_POST(self):
        self.send_error(405)

    def do_PUT(self):
        self.send_error(405)

    def do_DELETE(self):
        self.send_error(405)

    def log_message(self, format, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description="AI 沈阳美食家 数据库查看器")
    parser.add_argument("--port", type=int, default=8080, help="监听端口（默认 8080）")
    args = parser.parse_args()

    url = f"http://localhost:{args.port}"

    server = http.server.HTTPServer(("", args.port), Handler)
    print(f"数据库查看器运行于 {url}  (Ctrl+C 停止)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
