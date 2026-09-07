import os

html_path = 'board.html'
css_path = 'src/board.css'
js_path = 'src/board.js'
out_path = r'C:\Users\steph\.gemini\antigravity-cli\brain\5afabdb7-8abf-4e75-883e-3cf875111ffa\board_preview.html'

with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()

with open(css_path, 'r', encoding='utf-8') as f:
    css = f.read()

with open(js_path, 'r', encoding='utf-8') as f:
    js = f.read()

style_block = f"""
<style>
{css}
.page {{
    transform: scale(0.65);
    transform-origin: top center;
    margin-bottom: -3.5in;
}}
body {{
    background: #2b2b2b;
    overflow-x: hidden;
}}
</style>
"""

script_block = f"""
<script>
{js}
</script>
"""

html = html.replace('<link rel="stylesheet" href="src/board.css">', style_block)
html = html.replace('<script src="src/board.js"></script>', script_block)
# Remove the back link since they are not on the local server
html = html.replace('<a href="index.html" class="back-link">&larr; Back to PnP Tools</a>', '')

with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)
