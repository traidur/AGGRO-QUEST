import os

with open('pnp-tool/src/spice.css', 'r', encoding='utf-8') as f:
    css = f.read()

with open('pnp-tool/src/spice_cards.json', 'r', encoding='utf-8') as f:
    cards_json = f.read()

with open('pnp-tool/src/spice.js', 'r', encoding='utf-8') as f:
    js = f.read()

# Replace the import with embedded json
js = js.replace("import spiceCards from './spice_cards.json';", f"const spiceCards = {cards_json};\n")

with open('pnp-tool/spice.html', 'r', encoding='utf-8') as f:
    html = f.read()

html = html.replace('<link rel="stylesheet" href="/src/spice.css">', f'<style>\n{css}\n</style>')
html = html.replace('<script type="module" src="/src/spice.js"></script>', f'<script>\n{js}\n</script>')

out_path = r'C:\Users\steph\.gemini\antigravity-cli\brain\5afabdb7-8abf-4e75-883e-3cf875111ffa\spice_preview.html'
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)

print('Created standalone spice_preview.html at', out_path)
