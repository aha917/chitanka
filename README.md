# odt2sfb

A small helper for the [Chitanka.info](https://chitanka.info) contribution workflow. It converts OpenDocument Text (`.odt`) files into Chitanka's **SFB** markup, so prepared books can be submitted with less manual reformatting.

## Features

- Converts `.odt` documents to `.sfb`
- Runs as a plain Python script (`odt2sfb.py`)
- Ships as a standalone Windows GUI (`tofsb.exe`) — no Python install needed

<!-- TODO: list the structural elements it actually handles — headings, epigraphs, poems, footnotes, emphasis, etc. -->

## Requirements

- Python 3.x (only to run from source or rebuild the GUI)

<!-- TODO: -->

```bash
pip install -r requirements.txt
```

## Usage

### GUI (Linux / Windows)

Run `tofsb.exe`, pick your `.odt` file, and the `.sfb` output is written for you.

### From source

```bash
python odt2sfb.py
```

<!-- TODO: if the script takes command-line arguments instead of a file dialog,
     document them here, e.g.:  python odt2sfb.py input.odt output.sfb -->

## GUI building: 

The executable is built with [PyInstaller](https://pyinstaller.org):

```bash
pyinstaller --noconsole --onefile --name tofsb.exe odt2sfb.py
```

This produces a single self-contained `tofsb.exe` in the `dist/` folder.

## License

<!-- TODO: -->

## Contributing

Issues and pull requests are welcome — this exists to smooth the Chitanka.info workflow, so suggestions from fellow contributors are appreciated.
