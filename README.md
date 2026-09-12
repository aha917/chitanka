# odt2sfb

A small helper for the [Chitanka.info](https://chitanka.info) contribution workflow. 
It converts OpenDocument Text (`.odt`) files into Chitanka's **SFB** markup, so prepared books can be submitted with less manual reformatting.

## Features

- Converts `.odt` documents to `.sfb`
- Runs as a plain Python script `odt2sfb.py`
- Standalone Windows GUI `tofsb.exe` - no Python install needed
- Standalone Linux GUI `odt2sfb_gui.py`

<!-- TODO: list the structural elements it actually handles — headings, epigraphs, poems, footnotes, emphasis, etc. -->

## Requirements
Python Modules used: argparse, contextlib, io, os, queue, sys, threading, traceback, re, zipfile, xml.etree.ElementTree, tkinter - all standard library, nothing to pip install.


### GUI Building 
Only requirement for building is [PyInstaller](https://pyinstaller.org):; odt2sfb.py must sit in the same local directory as odt2sfb_gui.py since it's imported directly.

```bash
pip install pyinstaller
pyinstaller --noconsole --onefile --name tofsb.exe odt2sfb.py
```

This produces a single self-contained `tofsb.exe` in the `dist/` folder.


### Linux Requirements
* Python 3.x (only to run from source or rebuild the GUI)

### Windows Requirements
* The already-built odt2sfb_gui.exe in that folder needs nothing installed — it runs standalone on Windows.

## Usage

### GUI (Linux / Windows)

Run `tofsb.exe`, pick your `.odt` file, and the `.sfb` output is written for you.

### Shell Python

```bash
python odt2sfb.py
```

## License

<!-- TODO: -->

## Contributing

Issues and pull requests are welcome — this exists to smooth the Chitanka.info workflow, so suggestions from fellow contributors are appreciated.
