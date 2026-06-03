# samplefinder

Find sparse, sample-ready sections in music and export them **non-destructively**
as clips cut straight from the original mix.

A local Python CLI that detects **sparse sections** in a track — a **drum break**
(drums solo), a **solo instrument**, or a **decay / tail** — and writes each one
out as an audio clip. **No stem separation here:** that's a later, bulk step. Every
exported clip is a candidate you can demux afterwards.

> The full design spec is in [`CLAUDE.md`](CLAUDE.md) (Dutch) — it is the single
> source of truth and embeds the complete script. Keep `sample_finder.py` and the
> script block in `CLAUDE.md` in sync.

## Download (Windows)

Grab `SampleFinder-<version>-win64.exe` from the [Releases](../../releases) page —
a single file with **ffmpeg bundled in**, no Python needed. Double-click it to pick
a file/folder, see the detected candidates, and choose an export resolution; or run
it from a terminal exactly like the CLI below (`SampleFinder.exe analyze ...`).

## How it works

1. **Ingest + metadata** — read-only decode (libsndfile, ffmpeg fallback for broad
   format coverage), tags via mutagen.
2. **Structure** — beats / downbeats / segments (allin1, with a librosa fallback).
3. **Density analysis on the mix** (no separation) — HPSS percussive ratio,
   chroma/spectral entropy, RMS envelope and onset strength give one *sparseness*
   score per bar.
4. **Candidate detection** (rule-based per type) — break / solo / tail.
5. **Audio-aware cutting + export** — cut the candidate window from the original
   mix, anti-click fade, then write it in the resolution you pick.

Precision over recall: only sparse passages are mined, so the candidates are clean.
The tool surfaces candidates — your ear picks the keepers.

## Install

```bash
pip install -r requirements.txt
# optional, better structure analysis (tricky on Windows):
pip install allin1
```

`ffmpeg` must be on `PATH` for broad decode coverage (m4a/opus/wma/…) and for lossy
export; `tkinter` ships with the Python stdlib. **No torch/Demucs** in v2.

## Usage

```bash
# analyse a single file (detect candidates -> writes <name>.candidates.json)
python sample_finder.py analyze "track.mp3" --out-dir ./out

# export the detected clips from the mix, keeping the original format
python sample_finder.py export "track.mp3" --out-dir ./out --format original

# whole folder (batch), incl. subfolders, analyze + export in one go:
python sample_finder.py run "music/" --recursive --types break solo --beat-backend librosa
```

`input` may always be a single file **or** a folder (batch). Double-clicking
`sample_finder.py` opens a file/folder picker, analyses, then shows a **menu to
choose the export resolution**. All common audio formats work for input and output
(wav, mp3, m4a, flac, aiff, ogg, opus, aac, wma).

### Export resolution

`--format` defaults to `original` (same container + sample rate as the source).
Or choose explicitly, with resolution controls:

```bash
python sample_finder.py export "track.flac" --format wav  --bit-depth 24 --samplerate 48000
python sample_finder.py export "track.flac" --format mp3  --bitrate 320
python sample_finder.py export "track.wav"  --format flac --index 0 2
```

- PCM formats (`wav`/`flac`/`aiff`) → `--bit-depth {16,24,32}` via soundfile.
- Lossy formats (`mp3`/`m4a`/`aac`/`opus`/`ogg`/`wma`) → `--bitrate <kbps>` via ffmpeg.
- `--samplerate <Hz>` resamples (default: keep original); `--index` picks candidates.

### Tuning detection thresholds

Every `CFG` detection threshold is overridable at runtime — no source edits — on
`analyze` and `run` (precedence: config file < named flags < `--set`):

```bash
# named flags (see `analyze --help` for the full list)
python sample_finder.py analyze "track.mp3" --sparseness-min 0.42 --solo-chroma-entropy-max 0.82

# generic, any CFG key, repeatable
python sample_finder.py analyze "track.mp3" --set solo_min_bars=2 --set tail_min_dur_s=0.3

# a JSON profile (or drop sample_finder.config.json next to your audio -> auto-loaded)
python sample_finder.py analyze "track.mp3" --config my_profile.json
```

Copy `sample_finder.config.example.json` to `sample_finder.config.json`, edit the
keys you care about (omitted keys keep their defaults), and both the CLI and the
double-click mode pick it up automatically. See [`CLAUDE.md`](CLAUDE.md) §6 for the
full reference and §7 for the filename template.

## Build & release

The Windows `.exe` is built by GitHub Actions: push a tag `vX.Y.Z` (or run the
**release** workflow manually) and `.github/workflows/release.yml` builds
`SampleFinder.exe` with PyInstaller, bundles ffmpeg (via `imageio-ffmpeg`), and
attaches it to the Release. Build locally with:

```bash
pip install -r requirements-dev.txt
pyinstaller --noconfirm SampleFinder.spec      # -> dist/SampleFinder(.exe)
```

The binary is large (~150 MB — librosa/numba/scipy are inside) and self-extracts on
first launch; that's normal for this stack. Tests run on every push (`tests`
workflow: pyflakes + the audio-free unit tests):

```bash
pip install numpy pytest && python -m pytest tests/ -q
```

## Status

v2 — analyse + mix-export, no Demucs (demux later in bulk). The thresholds in `CFG`
(top of `sample_finder.py`) are starting values meant to be adjusted to your
material; do that at runtime via `--config` / `--set` / named flags, no source
edits needed. Tail detection is the weakest link; start with `--types break solo`
if in doubt.
