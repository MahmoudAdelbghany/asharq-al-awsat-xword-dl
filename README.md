# Asharq Al-Awsat Crossword Downloader (.ipuz)

This script downloads the latest *Asharq Al-Awsat* crossword puzzle from AmuseLabs and saves it as a `.ipuz` file, suitable for Arabic and other RTL languages.

## Features

- Automatically fetches the most recent puzzle
- Parses and converts AmuseLabs format to `ipuz` 
- Preserves metadata (title, author, date)
- Handles circled cells and clue orientation

### Usage

```bash
python download_crossword.py
```
### Requirements
- requests
- beautifulsoup4
- ipuz-py

## Acknowledgments
This script is heavily inspired by [xword-dl by thisisparker](https://github.com/thisisparker/xword-dl), which focuses on downloading .puz files. This version adapts the logic for .ipuz format to support Arabic puzzles from Asharq Al-Awsat.

