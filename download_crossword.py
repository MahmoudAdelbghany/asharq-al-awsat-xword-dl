import base64
import datetime
import json
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
import ipuz
import os

def remove_invalid_chars_from_filename(filename):
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '')
    return filename

def pick_filename(outlet_prefix, title, author, date):
    tokens = {
        'prefix': outlet_prefix or '',
        'title': title or '',
        'author': author or ''
    }
    template = f"{tokens['prefix']} - {date.strftime('%Y%m%d')} - {tokens['title']}"
    for token, value in tokens.items():
        template = template.replace(token, remove_invalid_chars_from_filename(value))
    template = ' '.join(template.split())
    if not template.endswith('.ipuz'):
        template += '.ipuz'
    return template

def fetch_latest_puzzle_id(picker_url):
    session = requests.Session()
    res = session.get(picker_url)
    soup = BeautifulSoup(res.text, 'html.parser')
    puzzles = soup.find('div', attrs={'class': 'puzzles'})
    if not puzzles:
        raise Exception("Could not find puzzles div in picker page")
    puzzle_ids = puzzles.findAll('div', attrs={'class': 'tile'}) or puzzles.findAll('li', attrs={'class': 'tile'})
    if not puzzle_ids:
        raise Exception("No puzzle tiles found")
    puzzle_id = puzzle_ids[0].get('data-id', '')
    if not puzzle_id:
        raise Exception("No puzzle ID found in first tile")
    
    load_token = None
    if 'pickerParams.rawsps' in res.text:
        rawsps = next((line.strip().split("'")[1] for line in res.text.splitlines() if 'pickerParams.rawsps' in line), None)
        if rawsps:
            picker_params = json.loads(base64.b64decode(rawsps).decode("utf-8"))
            load_token = picker_params.get('loadToken', None)
    
    return puzzle_id, load_token

def fetch_puzzle_data(solver_url):
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36',
        'Referer': 'https://aawsat.com/'
    })
    res = session.get(solver_url)
    
    # # Debug: Save and print the response
    # with open('response.html', 'w', encoding='utf-8') as f:
    #     f.write(res.text)
    # print(f"Response status: {res.status_code}")
    # print(f"Response snippet: {res.text[:500]}")


    if 'window.rawc' in res.text or 'window.puzzleEnv.rawc' in res.text:
        rawc = next((line.strip().split("'")[1] for line in res.text.splitlines()
                     if ('window.rawc' in line or 'window.puzzleEnv.rawc' in line)), None)
    else:
        soup = BeautifulSoup(res.text, 'html.parser')
        param_tag = soup.find('script', id='params')
        rawc = json.loads(param_tag.string)['rawc'] if param_tag else None
    
    if not rawc:
        soup = BeautifulSoup(res.text, 'html.parser')
        for script in soup.find_all('script'):
            if script.string:
                match = re.search(r"'([A-Za-z0-9+/=]{50,})'", script.string)
                if match:
                    rawc = match.group(1)
                    print(f"Found potential rawc: {rawc[:50]}...")
                    break
        if not rawc:
            raise Exception("Crossword puzzle data (rawc) not found")

    m1 = re.search(r'"([^"]+c-min.js[^"]+)"', res.text)
    if not m1:
        raise Exception("Could not find JavaScript URL for decoding key")
    js_url_fragment = m1.groups()[0]
    js_url = urllib.parse.urljoin(solver_url, js_url_fragment)
    res2 = session.get(js_url)

    m2 = re.search(r'="([0-9a-f]{7})"', res2.text)
    if m2:
        amuseKey = [int(c, 16) + 2 for c in m2.groups()[0]]
    else:
        amuseKey = [int(x) for x in re.findall(r'=\[\]\).push\(([0-9]{1,2})\)', res2.text)]
    
    key_2_order_regex = r'[a-z]+=(\d+);[a-z]+<[a-z]+.length;[a-z]+\+='
    key_2_digit_regex = r'<[a-z]+.length\?(\d+)'
    key_digits = [int(x) for x in re.findall(key_2_digit_regex, res2.text)]
    key_orders = [int(x) for x in re.findall(key_2_order_regex, res2.text)]
    amuseKey2 = [x for x, _ in sorted(zip(key_digits, key_orders), key=lambda pair: pair[1])]

    def load_rawc(rawc, amuseKey):
        try:
            return json.loads(base64.b64decode(rawc).decode("utf-8"))
        except:
            try:
                E = rawc.split('.')
                A = list(E[0])
                H = E[1][::-1]
                F = [int(A, 16) + 2 for A in H]
                B, G = 0, 0
                while B < len(A) - 1:
                    C = min(F[G % len(F)], len(A) - B)
                    for D in range(C // 2):
                        A[B + D], A[B + C - D - 1] = A[B + C - D - 1], A[B + D]
                    B += C
                    G += 1
                newRawc = ''.join(A)
                return json.loads(base64.b64decode(newRawc).decode("utf-8"))
            except:
                def amuse_b64(e, amuseKey):
                    e = list(e)
                    H = amuseKey
                    E = []
                    F = 0
                    while F < len(H):
                        J = H[F]
                        E.append(J)
                        F += 1
                    A, G, I = 0, 0, len(e) - 1
                    while A < I:
                        B = E[G]
                        L = I - A + 1
                        C = A
                        B = min(B, L)
                        D = A + B - 1
                        while C < D:
                            M = e[D]
                            e[D] = e[C]
                            e[C] = M
                            D -= 1
                            C += 1
                        A += B
                        G = (G + 1) % len(E)
                    return ''.join(e)
                return json.loads(base64.b64decode(amuse_b64(rawc, amuseKey)).decode("utf-8"))

    try:
        xword_data = load_rawc(rawc, amuseKey)
    except (UnicodeDecodeError, base64.binascii.Error):
        xword_data = load_rawc(rawc, amuseKey2)
    
    return xword_data

def parse_to_ipuz(xword_data):
    """Parse AmuseLabs JSON data into an .ipuz dictionary with correct RTL orientation."""
    puzzle = {
        "version": "http://ipuz.org/v2",
        "kind": ["http://ipuz.org/crossword#1"],
        "title": xword_data.get('title', '').strip(),
        "author": xword_data.get('author', '').strip(),
        "copyright": xword_data.get('copyright', '').strip(),
        "block": "#",
        "empty": "0",
        "dimensions": {"width": xword_data.get('w'), "height": xword_data.get('h')},
        "puzzle": [],
        "clues": {"Across:Across": [], "Down:Down": []},
        "solution": [],
        "showenumerations": False
    }

    width, height = xword_data.get('w'), xword_data.get('h')
    box = xword_data['box']
    placed_words = xword_data['placedWords']
    
    def get_clue_number(word):
        clue_dict = word.get('clue', {})
        return (clue_dict.get('num') or 
                word.get('clueNum') or 
                word.get('number') or 
                None)

    number_map = {}
    for word in placed_words:
        num = get_clue_number(word)
        if num is not None:
            # Adjust x-coordinate for RTL: width - x
            pos = (width - word['x'], word['y'] + 1)  # x is mirrored, y is 1-based
            number_map[pos] = num

    for y in range(height):
        row = []
        sol_row = []
        for x in range(width):
            cell = box[x][y]
            pos = (width - x, y + 1)  # Mirror x-coordinate for number lookup
            if cell == '\x00':
                row.append("#")
                sol_row.append(None)
            else:
                num = number_map.get(pos)
                row.append(int(num) if num else 0)
                sol_row.append(cell)
        # Reverse the row to ensure RTL order
        puzzle["puzzle"].append(row[::-1])
        puzzle["solution"].append(sol_row[::-1])

    across_clues = []
    down_clues = []
    for word in placed_words:
        num = get_clue_number(word)
        if num is None:
            pos = (width - word['x'], word['y'] + 1)
            num = number_map.get(pos)
        clue_text = word.get('clue', {}).get('clue', '')
        if word['acrossNotDown']:
            across_clues.append([int(num), clue_text])
        else:
            down_clues.append([int(num), clue_text])
    
    puzzle["clues"]["Across:Across"] = sorted(across_clues, key=lambda x: x[0])
    puzzle["clues"]["Down:Down"] = sorted(down_clues, key=lambda x: x[0])

    # Handle circled cells (if any)
    markup_data = xword_data.get('cellInfos', '')
    circled = [(width - square['x'], square['y'] + 1) for square in markup_data if square['isCircled']]
    if circled:
        for y, row in enumerate(puzzle["puzzle"], 1):
            for x, cell in enumerate(row, 1):
                if (x, y) in circled and cell != "#":
                    puzzle["puzzle"][y-1][x-1] = {"cell": cell, "style": {"shapebg": "circle"}}

    return puzzle

def download_latest_asharq_al_awsat_crossword():
    picker_url = 'https://cdn-eu1.amuselabs.com/pmm/date-picker?set=srmg-awsat-crossword'
    url_from_id = 'https://cdn-eu1.amuselabs.com/pmm/crossword?id={puzzle_id}&set=srmg-awsat-crossword'
    outlet_prefix = 'Asharq Al-Awsat'

    puzzle_id, load_token = fetch_latest_puzzle_id(picker_url)
    solver_url = url_from_id.format(puzzle_id=puzzle_id)
    if load_token:
        solver_url += f'&loadToken={load_token}'
    print(f"Fetching puzzle from: {solver_url}")

    xword_data = fetch_puzzle_data(solver_url)
    ipuz_data = parse_to_ipuz(xword_data)

    # print("Generated ipuz data:")
    # print(json.dumps(ipuz_data, ensure_ascii=False, indent=2))

    date = datetime.datetime.today()
    filename = pick_filename(outlet_prefix, ipuz_data["title"], ipuz_data["author"], date)
    
    try:
        ipuz.write(ipuz_data, filename)
        if not os.path.exists(filename):
            print(f"ipuz.write failed silently, writing manually...")
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(ipuz_data, f, ensure_ascii=False, indent=2)
        print(f"Puzzle saved as: {filename}")
        print(f"File exists: {os.path.exists(filename)}")
        print(f"File path: {os.path.abspath(filename)}")
    except Exception as e:
        print(f"Error saving file: {e}")

if __name__ == "__main__":
    download_latest_asharq_al_awsat_crossword()
