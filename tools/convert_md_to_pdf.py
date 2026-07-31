import re
import os
import sys
import subprocess
import markdown

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def convert_md_to_pdf(md_file_path, pdf_file_path):
    abs_md_path = os.path.abspath(md_file_path)
    abs_pdf_path = os.path.abspath(pdf_file_path)
    abs_html_path = os.path.splitext(abs_pdf_path)[0] + ".html"

    if not os.path.exists(abs_md_path):
        print(f"Error: {abs_md_path} not found!")
        return False

    with open(abs_md_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    # Pre-process GitHub callouts > [!NOTE], > [!IMPORTANT], > [!TIP], etc.
    def replace_callout(match):
        c_type = match.group(1).upper()
        raw_body = match.group(2)
        lines = raw_body.strip().split('\n')
        cleaned_lines = [re.sub(r'^>\s?', '', line) for line in lines]
        content = '<br>'.join(cleaned_lines)
        
        icon_map = {
            "NOTE": "GHI CHÚ",
            "IMPORTANT": "QUAN TRỌNG",
            "TIP": "MẸO HAY",
            "WARNING": "CẢNH BÁO",
            "CAUTION": "LƯU Ý"
        }
        title = icon_map.get(c_type, c_type)
        return f'<div class="callout callout-{c_type.lower()}"><div class="callout-title">{title}</div><div class="callout-body">{content}</div></div>\n'

    pattern = r'>\s*\[\!(NOTE|IMPORTANT|TIP|WARNING|CAUTION)\]\s*\n((?:>[^\n]*\n?)+)'
    md_text = re.sub(pattern, replace_callout, md_text)

    # Convert MD to HTML
    html_content = markdown.markdown(
        md_text,
        extensions=['tables', 'fenced_code', 'toc', 'nl2br', 'attr_list']
    )

    # Styled HTML Template
    full_html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>Huong Dan Su Dung Auto KVTM</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap');
        
        @page {{
            size: A4;
            margin: 15mm;
        }}

        body {{
            font-family: 'Roboto', 'Segoe UI', Arial, sans-serif;
            font-size: 13px;
            line-height: 1.6;
            color: #24292e;
            background-color: #ffffff;
            margin: 0;
            padding: 20px 30px;
        }}

        h1 {{
            font-size: 24px;
            color: #1a365d;
            border-bottom: 2px solid #3182ce;
            padding-bottom: 8px;
            margin-top: 0;
            text-align: center;
        }}

        h2 {{
            font-size: 18px;
            color: #2b6cb0;
            border-bottom: 1px solid #e2e8f0;
            padding-bottom: 6px;
            margin-top: 24px;
            page-break-after: avoid;
        }}

        h3 {{
            font-size: 15px;
            color: #2c5282;
            margin-top: 18px;
            page-break-after: avoid;
        }}

        h4 {{
            font-size: 14px;
            color: #4a5568;
            margin-top: 14px;
            page-break-after: avoid;
        }}

        p {{
            margin-bottom: 10px;
        }}

        code {{
            font-family: 'Consolas', 'Courier New', monospace;
            background-color: #edf2f7;
            color: #c53030;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 12px;
        }}

        pre {{
            background-color: #1a202c;
            color: #f7fafc;
            padding: 12px 16px;
            border-radius: 6px;
            overflow-x: auto;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 12px;
            line-height: 1.45;
            page-break-inside: avoid;
        }}

        pre code {{
            background-color: transparent;
            color: inherit;
            padding: 0;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 16px 0;
            font-size: 12px;
            page-break-inside: avoid;
        }}

        table th {{
            background-color: #ebf8ff;
            color: #2b6cb0;
            font-weight: 600;
            text-align: left;
            padding: 8px 12px;
            border: 1px solid #cbd5e0;
        }}

        table td {{
            padding: 8px 12px;
            border: 1px solid #cbd5e0;
        }}

        table tr:nth-child(even) {{
            background-color: #f7fafc;
        }}

        ul, ol {{
            padding-left: 24px;
            margin-bottom: 12px;
        }}

        li {{
            margin-bottom: 4px;
        }}

        .callout {{
            border-left: 4px solid #3182ce;
            background-color: #ebf8ff;
            padding: 12px 16px;
            margin: 16px 0;
            border-radius: 0 6px 6px 0;
            page-break-inside: avoid;
        }}

        .callout-title {{
            font-weight: bold;
            color: #2b6cb0;
            margin-bottom: 4px;
        }}

        .callout-body {{
            color: #2d3748;
        }}

        hr {{
            border: none;
            border-top: 1px solid #e2e8f0;
            margin: 20px 0;
        }}

        a {{
            color: #3182ce;
            text-decoration: none;
        }}
    </style>
</head>
<body>
    {html_content}
</body>
</html>
"""

    with open(abs_html_path, "w", encoding="utf-8") as f:
        f.write(full_html)

    print(f"Created HTML file: {abs_html_path}")

    # Use Microsoft Edge to print HTML to PDF
    edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    if not os.path.exists(edge_path):
        edge_path = "msedge"

    html_url = "file:///" + abs_html_path.replace("\\", "/")

    cmd = [
        edge_path,
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={abs_pdf_path}",
        html_url
    ]

    print("Exporting PDF via Edge headless...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if os.path.exists(abs_pdf_path) and os.path.getsize(abs_pdf_path) > 0:
        print(f"SUCCESS: Exported PDF to {abs_pdf_path} ({os.path.getsize(abs_pdf_path)} bytes)")
        return True
    else:
        print(f"ERROR: Export failed: {result.stderr}")
        return False

if __name__ == "__main__":
    md_path = "HUONG_DAN_SU_DUNG.md"
    pdf_path = "HUONG_DAN_SU_DUNG.pdf"
    convert_md_to_pdf(md_path, pdf_path)
