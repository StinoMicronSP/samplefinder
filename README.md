# samplefinder

Identify breaks and intro's and stem-separate them via Demucs.

A local Python CLI that detects **sparse sections** in a music file and exports
them **non-destructively** as usable samples. Three types: a **drum break**
(drums solo), a **solo instrument**, and a **decay / tail**.

> The full design spec is in [`CLAUDE.md`](CLAUDE.md) (Dutch) — it is the single
> source of truth and embeds the complete script. Keep `sample_finder.py` and
> the script block in `CLAUDE.md` in sync.

## How it works

1. **Ingest + metadata** — read-only decode via librosa/ffmpeg, tags via mutagen.
2. **Structure** — beats / downbeats / segments (allin1, with a librosa fallback).
3. **Density analysis on the mix** (no separation) — HPSS percussive ratio,
   chroma/spectral entropy, RMS envelope and onset strength give one
   *sparseness* score per bar.
4. **Candidate detection** (rule-based per type) — break / solo / tail.
5. **Targeted Demucs pass** — `htdemucs_ft` runs **only** on candidate windows.
6. **Audio-aware cutting + export** — per-type stem choice, anti-click fades,
   resampling, and a metadata-rich filename.

Precision over recall: only sparse passages are mined, so the candidates are
clean. The tool surfaces candidates — your ear picks the keepers.

## Install

```bash
pip install -r requirements.txt
# optional, better structure analysis (tricky on Windows):
pip install allin1
```

`ffmpeg` must be on `PATH` (mp3/m4a decode + lossy export); `tkinter` ships with
the Python stdlib. For GPU acceleration install the CUDA build of PyTorch;
otherwise Demucs runs on CPU (slower, but these are only short windows).

## Usage

```bash
# single file
python sample_finder.py analyze "track.mp3" --out-dir ./out
python sample_finder.py export  "track.mp3" --out-dir ./out --format wav --bit-depth 24

# whole folder (batch), including subfolders, analyze + export in one go:
python sample_finder.py run "music/" --recursive --types break solo --beat-backend librosa
```

`input` may always be a single file **or** a folder (batch). Double-clicking
`sample_finder.py` (or a built `.exe`) opens an interactive file/folder picker.
See [`CLAUDE.md`](CLAUDE.md) §6 for the full flag reference, the filename
template (§7), and the known limitations (§8).

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
double-click mode pick it up automatically.

## Status

v1 — the first run is calibration. The thresholds in `CFG` (top of
`sample_finder.py`) are starting values meant to be adjusted to your material; do
that at runtime via `--config` / `--set` / named flags (see above), no source
edits needed. Tail detection is the weakest link; start with `--types break solo`
if in doubt.
