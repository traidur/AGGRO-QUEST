def update_board():
    with open('pnp-tool/board.html', 'r', encoding='utf-8') as f:
        html = f.read()

    # Fix Zone 1 names
    z1_old = '''<div class="node std" id="waystation1" style="left: 38%; top: 55%;">Mud Trenches</div>
        <div class="node std" id="cove1" style="left: 15%; top: 50%;">Ruined Abbey</div>
        <div class="node std" id="ridge1" style="left: 33%; top: 35%;">Pyre Fields</div>
        <div class="node std" id="marsh1" style="left: 12%; top: 25%;">Broken Bridge</div>'''
    z1_new = '''<div class="node std" id="waystation1" style="left: 38%; top: 55%;">Waystation</div>
        <div class="node std" id="cove1" style="left: 15%; top: 50%;">Cove</div>
        <div class="node std" id="ridge1" style="left: 33%; top: 35%;">Ridge</div>
        <div class="node std" id="marsh1" style="left: 12%; top: 25%;">Marsh</div>'''
    html = html.replace(z1_old, z1_new)

    # Fix Zone 4 and 3 Labels
    html = html.replace('<div class="zone-label" style="left: 20%; top: 10%;">Zone 4</div>', '<div class="zone-label" style="left: 20%; top: 10%;">The Sunsworn Ascent</div>')
    html = html.replace('<div class="zone-label" style="left: 80%; top: 10%;">Zone 3</div>', '<div class="zone-label" style="left: 80%; top: 10%;">The Pale Wastes</div>')

    # Fix Town 4 and Town 3
    html = html.replace('<div class="node town" id="town4" style="left: 25%; top: 30%;">Town 4</div>', '<div class="node town" id="town4" style="left: 25%; top: 30%;">The Vanguard Camp</div>')
    html = html.replace('<div class="node town" id="town3" style="left: 75%; top: 30%;">Town 3</div>', '<div class="node town" id="town3" style="left: 75%; top: 30%;">The Vanguard Camp</div>')

    # Fix Border Node positions and text (North)
    html = html.replace('Border (4 - 3)', 'The Furnace Gates')
    html = html.replace('top: 97%;">Border (1 - 4)', 'top: 92%;">The King\'s Highway')
    html = html.replace('top: 97%;">Border (2 - 3)', 'top: 92%;">The Ashen Ascent')

    # Fix Border Node positions and text (South)
    html = html.replace('Border (1 - 2)', 'Thorne\'s Toll')
    html = html.replace('top: 3%;">Border (1 - 4)', 'top: 8%;">The King\'s Highway')
    html = html.replace('top: 3%;">Border (2 - 3)', 'top: 8%;">The Ashen Ascent')

    with open('pnp-tool/board.html', 'w', encoding='utf-8') as f:
        f.write(html)

if __name__ == '__main__':
    update_board()
