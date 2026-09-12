# odt2sfb

A small helper for the [Chitanka.info](https://chitanka.info) contribution workflow.

It converts OpenDocument Text (`.odt`) files into Chitanka's **SFB** markup — the
plain-text format Chitanka uses for book submissions — so a prepared manuscript can be
uploaded with far less manual reformatting.

## Features

- Converts `.odt` documents to `.sfb`
- Command-line script: `odt2sfb.py`
- Graphical front-end: `odt2sfb_gui.py`
- Prebuilt standalone Windows GUI: `tofsb.exe` — no Python installation needed

## Download

Grab the prebuilt Windows executable from the [Releases page](https://github.com/aha917/chitanka/releases).
<!-- TODO: confirm this link, or remove this section if you don't publish releases. -->

Linux and macOS users run from source (see below).

## Usage

### GUI

- **Windows:** double-click `tofsb.exe`, pick your `.odt` file, and the `.sfb` output is
  written next to it.
- **Linux / macOS:** run the GUI from source:

  ```bash
  python odt2sfb_gui.py
  ```

### Command line

```bash
python odt2sfb.py input.odt output.sfb
```
<!-- TODO: replace with the real argument signature from your argparse setup. -->

## Requirements

### Running from source

- Python 3.x
- No third-party packages — `odt2sfb.py` uses only the standard library
  (`argparse`, `zipfile`, `xml.etree.ElementTree`, `tkinter`, etc.).

  On some Linux distributions `tkinter` is a separate package, e.g.:

  ```bash
  sudo apt install python3-tk      # Debian / Ubuntu
  ```

### Building the standalone GUI

Building the single-file executable needs [PyInstaller](https://pyinstaller.org).
`odt2sfb.py` must sit in the same directory as `odt2sfb_gui.py`, since the GUI imports it directly.

```bash
pip install pyinstaller
pyinstaller --noconsole --onefile --name tofsb odt2sfb_gui.py
```

This produces a self-contained `tofsb.exe` in the `dist/` folder.
(Note: the build entry point is `odt2sfb_gui.py`, not `odt2sfb.py`, and `--name tofsb`
lets PyInstaller add the `.exe` extension itself.)

## License

MIT License

Copyright (c) 2026 

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Contributing

Issues and pull requests are welcome — this exists to smooth the Chitanka.info workflow,
so suggestions from fellow contributors are appreciated.
