# Sample Finder — projectcontext voor Claude Code

Een lokaal Python-CLI dat **sparse secties** in een muziekbestand detecteert en ze
**non-destructief** exporteert als clips, **rechtstreeks uit de originele mix**.
Drie types: een **drum-break** (drums solo), een **solo-instrument**, en een
**decay/uitklank-tail**.

> **v2 — analyse-only.** Er wordt NIET meer gescheiden. Bronscheiding (Demucs) is
> bewust uit het programma gehaald; dat doe je later, in **bulk**, als losse stap
> op de geexporteerde clips. Elke clip is dus een kandidaat om te demuxen.

> Dit document is de single source of truth voor het project. Het volledige script
> staat onderaan en is identiek aan `sample_finder.py`. Pas bij wijzigingen altijd
> beide aan, of genereer `sample_finder.py` opnieuw uit dit document.

---

## 1. Scope

**Wel:** dunne (sparse) secties vinden via goedkope analyse op de mix, die secties
audio-aware uit de **originele mix** knippen, en exporteren met instelbaar formaat
+ resolutie en een metadata-rijke bestandsnaam. Werkt op een enkel bestand of een
hele map (batch). Alle courante audioformaten in- én uitlezen.

**Niet:** bronscheiding (apart, later in bulk — buiten dit programma). Dichte,
volle mixsecties doorzoeken (bewuste keuze: precisie boven recall). Geen
automatische "beste sample"-beoordeling — de tool levert kandidaten, het oor beslist.

---

## 2. Vastgelegde ontwerpkeuzes

| Beslissing | Keuze | Reden |
|---|---|---|
| Structuur/beats | allin1, met **librosa-fallback** | allin1 is op Windows lastig (zie §5); fallback houdt je niet vast |
| Separatie | **Buiten scope (v2)**: clips zijn de kale mix; demux later in bulk | simpeler, sneller, stabieler; eerst de detectie hard maken |
| Recall vs precisie | **Precisie**: enkel sparse stukken | schone kandidaten, geen ruis |
| Snijden | **Audio-aware per type**: breaks bar-aligned, tails op decay-einde | een naklank eindigt niet op een downbeat |
| Resolutie | **Instelbaar**: `original` (default) of expliciet formaat/bit-depth/SR/bitrate | bron-getrouw houden, of bewust converteren |
| Drempels | **Runtime instelbaar** via vlaggen / `--set` / config-bestand | ijken zonder de broncode te wijzigen |
| Bron | **Non-destructief** | origineel wordt nooit aangeraakt |

---

## 3. Architectuur (pijplijn)

1. **Ingest + metadata** — decode via libsndfile (`soundfile`), met **ffmpeg-fallback**
   voor brede formaatdekking; `mutagen` voor artist/title/bpm en bron-resolutie.
   Alleen lezen.
2. **Structuur** — allin1 of librosa: beats, downbeats, bpm, segmenten.
3. **Density-analyse op de MIX** (geen separatie): HPSS percussief-ratio,
   chroma-entropie, spectrale entropie, RMS-envelope, onset-strength →
   één **sparseness-score** per maat.
4. **Kandidaat-detectie** (rule-based, per type):
   - *break*: sparse + percussief-dominant + lage chroma-entropie
   - *solo*: sparse + harmonisch + lage chroma-entropie, ≥N maten
   - *tail*: dalende RMS na laatste onset → decay-einde onder stilte-drempel
5. **Audio-aware snijden uit de mix + export** — venster uit de **originele** audio
   knippen, anti-klik-fade, resampling/conversie naar de gekozen resolutie,
   getemplate bestandsnaam. Elke kandidaat draagt een `stem_hint` mee (drums/other/
   auto) voor de latere bulk-demux.

Fase 3–4 zijn de detectie; bewijs die eerst (subcommando `analyze`) voordat je
exporteert (`export`).

---

## 4. Algoritmes & referenties (de lineage)

- **all-in-one (mir-aidj)** — functionele structuuranalyse; labels o.a.
  `intro/outro/break/inst/solo/...`, plus beats/downbeats.
- **López-Serrano, Dittmar & Müller (2018), *Finding Drum Breaks in Digital Music
  Recordings*** (AudioLabs Erlangen) — formaliseert drum-break-detectie via
  **CHRP** (cascaded harmonic-residual-percussive). Onze break-heuristiek (HPSS
  percussief-ratio + weggevallen harmonie) is hiervan een vereenvoudiging.
- **Tamagnan & Yang (2021), *Drum Fills Detection and Generation*** — een *fill*
  (overgangsroffel) ≠ een *break* (drums solo). v2 mikt op breaks; fills zijn een
  apart, onrijper probleem (weinig datasets).
- **Demucs / HTDemucs** — bronscheiding; **niet in dit programma (v2)**. Dit is de
  beoogde latere **bulk-stap** op de geexporteerde clips (zie §9).

---

## 5. Installatie (Windows)

```powershell
# kies je interpreter (zie runner-workflow); dan:
py -3.12 -m pip install librosa soundfile numpy scipy mutagen
# optioneel, betere structuur (kan tegenstribbelen op Windows):
py -3.12 -m pip install allin1
```

- **ffmpeg** op PATH: nodig voor brede **decode**-dekking (m4a/opus/wma/…) en voor
  **lossy export** (mp3/m4a/aac/opus/ogg/wma). PCM/lossless (wav/flac/aiff) gaat via
  `soundfile`. `tkinter` zit in de stdlib.
- **allin1-waarschuwing:** de dependency `natten` heeft beperkte Windows-wheels en
  faalt vaak. Lukt het niet, gebruik dan `--beat-backend librosa`. De
  interactieve/dubbelklik-modus gebruikt librosa al als veilige default.
- **geen torch/Demucs** in v2 — scheelt een zware, trage installatie.

---

## 6. Gebruik

### A. Als executable (dubbelklik) — bestand of map
Dubbelklik `sample_finder.py`. Er verschijnt een keuzevenster: **Ja = map** (batch),
**Nee = enkel bestand**. Het analyseert, en vraagt of je wilt exporteren — daarna
verschijnt een **keuzemenu voor de export-resolutie**. Output gaat naar
`sample_finder_out/` naast je invoer.

### B. CLI
```powershell
# enkel bestand: detecteren, daarna exporteren in het oorspronkelijke formaat
py -3.12 sample_finder.py analyze "track.mp3" --out-dir .\out
py -3.12 sample_finder.py export  "track.mp3" --out-dir .\out --format original

# hele map (batch), inclusief submappen, alles ineen:
py -3.12 sample_finder.py run "C:\muziek" --recursive --types break solo --beat-backend librosa
```
`input` mag altijd een bestand of een map zijn. `--types` kiest welke je zoekt.

### C. Export-resolutie
`--format` is standaard `original` (zelfde container + samplerate als de bron). Of
kies expliciet, met resolutie-knoppen:
```powershell
py -3.12 sample_finder.py export "track.flac" --format wav  --bit-depth 24 --samplerate 48000
py -3.12 sample_finder.py export "track.flac" --format mp3  --bitrate 320
py -3.12 sample_finder.py export "track.wav"  --format flac --index 0 2
```
- PCM (`wav`/`flac`/`aiff`) → `--bit-depth {16,24,32}` (via soundfile).
- Lossy (`mp3`/`m4a`/`aac`/`opus`/`ogg`/`wma`) → `--bitrate <kbps>` (via ffmpeg).
- `--samplerate <Hz>` resamplet (default: origineel behouden); `--index` kiest
  specifieke kandidaten. In de dubbelklik-modus kies je dit via een **menu**.

### D. Drempels afstellen (zonder de broncode te wijzigen)
Alle detectie-drempels uit `CFG` zijn op drie manieren te overschrijven; prioriteit
is *config-bestand < losse vlaggen < `--set`*:

```powershell
# 1) losse vlaggen (zie `analyze --help` voor de volledige lijst)
py -3.12 sample_finder.py analyze "track.mp3" --sparseness-min 0.42 --solo-chroma-entropy-max 0.82

# 2) generiek: élke CFG-sleutel, herhaalbaar
py -3.12 sample_finder.py analyze "track.mp3" --set solo_min_bars=2 --set tail_min_dur_s=0.3

# 3) een profiel in JSON (of leg sample_finder.config.json naast je audio -> auto-geladen)
py -3.12 sample_finder.py analyze "track.mp3" --config mijn_profiel.json
```
Kopieer `sample_finder.config.example.json` naar `sample_finder.config.json`, pas de
gewenste sleutels aan (ontbrekende sleutels houden hun default) en zowel de dubbelklik-
als de CLI-modus pikken het automatisch op. Onbekende sleutels worden genegeerd;
sleutels die met `_` beginnen gelden als commentaar. Werkt op `analyze` en `run`.

### E. Bouwen naar een `.exe` + GitHub-release
Een one-file Windows-executable wordt automatisch gebouwd door GitHub Actions:
push een tag `vX.Y.Z` (of start de **release**-workflow handmatig) en
`.github/workflows/release.yml` bouwt met PyInstaller een `SampleFinder.exe`,
**bundelt ffmpeg** (via `imageio-ffmpeg`) en hangt de exe aan de Release.

Lokaal bouwen kan ook:
```powershell
py -3.12 -m pip install -r requirements-dev.txt
py -3.12 -m PyInstaller --noconfirm SampleFinder.spec   # -> dist\SampleFinder.exe
```
> De exe is groot (~150 MB: librosa/numba/scipy zitten erin) en pakt zichzelf bij de
> eerste start even uit — normaal voor deze stack. Wil je ffmpeg lokaal meebundelen,
> zet dan een `ffmpeg.exe` in `./ffmpeg/` vóór het bouwen; anders moet ffmpeg op PATH
> staan. De `tests`-workflow draait bij elke push pyflakes + de (audio-vrije) unit-tests.

---

## 7. Bestandsnaam-template

```
{artist}_{title}__{type}__{pos}__{starttijd}-{eindtijd}__{resolutie}.{ext}
```
- `pos` = `bars026-028` (bar-aligned) of `free` (tails).
- `type` = `break` / `solo` / `tail`.
- `resolutie` = `24b-48k` (PCM) of `320k` (lossy).
- voorbeeld PCM:   `ChemBros_SettingSun__break__bars032-036__01m12s00-01m21s00__24b-44k.wav`
- voorbeeld lossy: `ChemBros_SettingSun__tail__free__03m01s10-03m03s40__320k.mp3`

Exports per track landen in `out/<tracknaam>/` om batch netjes te houden. De
`<naam>.candidates.json` bewaart meta, bron-resolutie en de kandidaten (incl.
`stem_hint` voor de latere demux).

---

## 8. Bekende beperkingen (lees dit eerlijk)

- **Drempels in `CFG` zijn startwaarden** en moeten op jouw materiaal worden
  afgesteld — runtime via `--config` / `--set` / losse vlaggen (§6D), zonder de
  broncode te wijzigen. Eerste run = kalibratie.
- **Export is de KALE MIX** van het venster — geen separatie. Dat is opzet: demux
  later in bulk. De `stem_hint` per kandidaat zegt welke stem je dan wil pakken.
- **Tail-detectie is de zwakste schakel** (heuristisch). Begin eventueel met
  `--types break solo`.
- **librosa-downbeats raden 4/4** (elke 4e beat). Klopt redelijk voor
  4-to-the-floor, fout bij rubato/oneven maat.
- **Precisie boven recall:** samples die in dichte secties begraven zitten worden
  per definitie gemist.
- **Lossy → hoge bit-resolutie is een illusie**; de tool waarschuwt maar verbiedt
  niet. `original` behoudt het bron-formaat (lossy blijft lossy).

---

## 9. Roadmap / open `[SPECIFY]`

- **Bulk-demux-stap** (de ex-Demucs): een losse tool/subcommando dat de
  geexporteerde clips in batch door `htdemucs_ft` haalt en per `stem_hint` de juiste
  stem bewaart. Bewust gescheiden van de detectie zodat die snel en torch-vrij blijft.
- v2+: **adaptieve drempels** (percentiel per track) bovenop de nu al
  runtime-instelbare drempels — features zijn niet per-track genormaliseerd, dus
  vaste absolute grenzen werken niet op elk nummer even goed (zie kalibratie).
- `[SPECIFY]` Doel-DAW-conventie voor naamgeving (Reaper-vriendelijk?).
- v2+: allin1 vervangen door madmom voor beats → vermijdt zware afhankelijkheden.
- v2+: drum-*fill*-detectie (Tamagnan-regel: maat met afwijkende noten t.o.v. buren).
- v2+: kandidaten-review-GUI i.p.v. console-tabel.

---

## 10. Handoff Block

```
TAAL:            Python 3.10+
ENTRYPOINT:      sample_finder.py  (dubbelklik => interactive_main)
SUBCOMMANDO'S:   analyze | export | run
INVOER:          bestand of map (+ --recursive); alle courante audioformaten
DECODE:          soundfile (libsndfile) + ffmpeg-fallback voor brede dekking
BEAT-BACKEND:    allin1 (default) | librosa (fallback/dubbelklik)
SEPARATIE:       GEEN (v2, bewust) -- demux later in bulk op de clips
EXPORT:          clip uit de MIX; formaat instelbaar (original/wav/flac/aiff/ogg/
                 mp3/m4a/aac/opus/wma); 16/24/32-bit (PCM) of bitrate (lossy);
                 SR instelbaar; dubbelklik = keuzemenu
DREMPELS:        runtime instelbaar via CLI-vlaggen, --set KEY=VALUE of --config JSON
                 (sidecar sample_finder.config.json wordt auto-geladen)
NON-DESTRUCTIEF: ja, bron alleen-lezen; output in sample_finder_out/<track>/
TESTS:           pytest tests/ (audio-vrij) + pyflakes; CI in .github/workflows/
RELEASE:         tag vX.Y.Z -> GitHub Actions bouwt SampleFinder.exe (ffmpeg gebundeld)
TE TESTEN:       1) analyze op 1 track  2) drempels ijken via --set/--config
                 3) export in gewenste resolutie  4) later: bulk-demux
```

---

## 11. Volledig script (`sample_finder.py`)

```python
# -*- coding: utf-8 -*-
"""
sample_finder.py  -- v2 (analyse-only; geen Demucs)
Vindt 'sample-bare' SPARSE secties in muziek en exporteert die NON-DESTRUCTIEF
als clips uit de ORIGINELE mix. Er wordt NIET meer gescheiden: dat doe je later
in bulk -- elke geexporteerde clip is een kandidaat om dan te demuxen.

Drie types kandidaten: drum-break, solo-instrument, decay/uitklank-tail.

GEBRUIK (drie manieren):
  1) Dubbelklik / zonder argumenten -> keuzevenster (BESTAND of MAP), analyse,
     daarna een KEUZEMENU voor de export-resolutie.
  2) python sample_finder.py analyze "track.mp3" --out-dir ./out
     python sample_finder.py export  "track.mp3" --out-dir ./out --format original
  3) python sample_finder.py run     "C:\\muziek\\map" --recursive

Invoer mag een ENKEL BESTAND of een MAP zijn (batch). Met --recursive ook submappen.
Alle courante audioformaten werken (wav/mp3/m4a/flac/aiff/ogg/opus/aac/wma); decode
gaat via libsndfile en valt terug op ffmpeg voor brede dekking.

DREMPELS INSTELBAAR (zonder de broncode te wijzigen):
  * losse vlaggen, bv. --sparseness-min 0.42 --solo-chroma-entropy-max 0.82
  * --set KEY=VALUE (herhaalbaar), bv. --set solo_min_bars=2 --set tail_min_dur_s=0.3
  * --config pad/naar.json, of leg `sample_finder.config.json` naast je invoer
    (wordt automatisch geladen). Zie `analyze --help` voor alle drempels.

EXPORT-RESOLUTIE:
  * --format original (default) behoudt de bron-extensie + samplerate
  * of kies expliciet: wav/flac/aiff/ogg/mp3/m4a/aac/opus/wma
  * --bit-depth {16,24,32} (PCM), --samplerate <Hz>, --bitrate <kbps> (lossy)
  * de dubbelklik-modus toont hiervoor een keuzemenu

EERLIJKE KANTTEKENINGEN:
  * v2; detectie-drempels onder CFG zijn startwaarden -> ijk ze op jouw materiaal.
  * Export is de KALE MIX van het venster (geen separatie); demux later in bulk.
  * lossy bron -> hoge bit-resolutie voegt GEEN informatie toe.

Afhankelijkheden:
  pip install librosa soundfile numpy scipy mutagen
  (optioneel) pip install allin1     # betere structuur, lastig op Windows
  + ffmpeg op PATH (decode brede formaten + lossy export). tkinter zit in de stdlib.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np

# ----------------------------------------------------------------------------
# CONFIG  -- detectie-drempels (precisie boven recall). Runtime overschrijfbaar
# via CLI-vlaggen, --set KEY=VALUE of een config-bestand (zie resolve_tuning).
# ----------------------------------------------------------------------------
CFG = {
    "hop_length": 512,
    "analysis_sr": 22050,
    "sparseness_min": 0.55,
    "break_perc_ratio_min": 0.62,
    "break_chroma_entropy_max": 0.78,
    "break_min_bars": 1,
    "solo_perc_ratio_max": 0.40,
    "solo_chroma_entropy_max": 0.55,
    "solo_min_bars": 2,
    "tail_rms_drop_db": -18.0,
    "tail_silence_db": -55.0,
    "tail_min_dur_s": 0.4,
    "tail_lookback_bars": 2,
    "pad_seconds": 0.05,
    "fade_ms": 5.0,
}

# In te lezen / uit te schrijven formaten.
AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".mp4", ".flac", ".aif", ".aiff",
              ".ogg", ".oga", ".wma", ".opus", ".aac"}
# PCM/lossless containers gaan via soundfile (bit-depth-controle); de rest
# (lossy) gaat via ffmpeg (bitrate-controle).
PCM_FORMATS = {"wav", "flac", "aif", "aiff"}

# Optioneel sidecar-configbestand: ligt het naast de invoer of in de werkmap,
# dan worden de CFG-drempels er automatisch uit overschreven (zie resolve_tuning).
CONFIG_FILENAME = "sample_finder.config.json"


def _coerce_cfg(key, val):
    """Cast een override-waarde naar het type van de bestaande CFG-default."""
    cur = CFG[key]
    if isinstance(cur, bool):
        if isinstance(val, str):
            return val.strip().lower() in ("1", "true", "yes", "y", "on")
        return bool(val)
    if isinstance(cur, int):
        return int(float(val))
    if isinstance(cur, float):
        return float(val)
    return str(val)


def apply_cfg_overrides(overrides: dict) -> dict:
    """Merge overrides in de globale CFG (type-gecoerced naar de default-types).

    Onbekende sleutels worden met een waarschuwing genegeerd; sleutels die met
    '_' beginnen zijn gereserveerd voor commentaar in config-bestanden. Geeft de
    daadwerkelijk toegepaste {sleutel: waarde} terug.
    """
    applied = {}
    for k, v in (overrides or {}).items():
        if isinstance(k, str) and k.startswith("_"):
            continue
        if k not in CFG:
            print(f"[cfg] onbekende drempel genegeerd: {k}")
            continue
        try:
            CFG[k] = _coerce_cfg(k, v)
            applied[k] = CFG[k]
        except (ValueError, TypeError) as e:
            print(f"[cfg] kon {k}={v!r} niet toepassen ({e})")
    return applied


def load_config_file(path) -> dict:
    """Lees CFG-overrides uit JSON. Accepteert {..} of {'CFG': {..}}."""
    p = Path(path)
    if not p.exists():
        print(f"[cfg] config niet gevonden: {path}")
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[cfg] kon config niet lezen ({path}): {e}")
        return {}
    if isinstance(data, dict) and isinstance(data.get("CFG"), dict):
        data = data["CFG"]
    return data if isinstance(data, dict) else {}


def find_sidecar_config(search_dirs):
    """Geef het eerste bestaande CONFIG_FILENAME terug uit search_dirs."""
    seen = set()
    for d in search_dirs:
        if not d:
            continue
        d = str(d)
        if d in seen:
            continue
        seen.add(d)
        cand = Path(d) / CONFIG_FILENAME
        if cand.exists():
            return str(cand)
    return None


@dataclass
class Candidate:
    type: str
    start: float
    end: float
    start_bar: int
    end_bar: int
    score: float
    stem_hint: str        # welke stem je later wil demuxen (drums/other/auto)
    note: str = ""


def _cand_from_dict(d: dict) -> "Candidate":
    """Bouw een Candidate uit JSON; tolerant voor oude sleutels (dominant_stem)."""
    if "stem_hint" not in d and "dominant_stem" in d:
        d = {**d, "stem_hint": d["dominant_stem"]}
    fields = {"type", "start", "end", "start_bar", "end_bar",
              "score", "stem_hint", "note"}
    return Candidate(**{k: d[k] for k in fields if k in d})


# ----------------------------------------------------------------------------
# Invoer: enkel bestand of map -> lijst bestanden
# ----------------------------------------------------------------------------
def collect_inputs(path: str, recursive: bool = False):
    p = Path(path)
    if p.is_file():
        return [p]
    if p.is_dir():
        it = p.rglob("*") if recursive else p.glob("*")
        return sorted(f for f in it if f.suffix.lower() in AUDIO_EXTS)
    return []


def pick_input_dialog():
    """Keuzevenster voor dubbelklik-gebruik: map (batch) of enkel bestand."""
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
    except Exception as e:
        print(f"tkinter niet beschikbaar ({e}); geef een pad als argument.")
        return None
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    is_folder = messagebox.askyesno(
        "Sample Finder",
        "Een hele MAP verwerken (batch)?\n\nJa = map kiezen\nNee = enkel bestand")
    if is_folder:
        path = filedialog.askdirectory(title="Kies een map met audio")
    else:
        path = filedialog.askopenfilename(
            title="Kies een audiobestand",
            filetypes=[("Audio", "*.wav *.mp3 *.m4a *.flac *.aif *.aiff *.ogg "
                                  "*.opus *.aac *.wma"),
                       ("Alle bestanden", "*.*")])
    root.destroy()
    return path or None


def _pause():
    try:
        input("\nDruk Enter om te sluiten...")
    except EOFError:
        pass


# ----------------------------------------------------------------------------
# Stap 0 -- Ingest + metadata + decode (non-destructief: alleen lezen)
# ----------------------------------------------------------------------------
def read_metadata(path: str) -> dict:
    meta = {"artist": "", "title": "", "bpm": None}
    try:
        from mutagen import File as MutagenFile
        m = MutagenFile(path, easy=True)
        if m is not None:
            meta["artist"] = (m.get("artist", [""]) or [""])[0]
            meta["title"] = (m.get("title", [""]) or [""])[0]
            bpm = m.get("bpm", [None])
            if bpm and bpm[0]:
                try:
                    meta["bpm"] = float(bpm[0])
                except ValueError:
                    pass
    except Exception as e:
        print(f"[meta] tags niet leesbaar ({e}); val terug op bestandsnaam")
    stem = Path(path).stem
    if not meta["title"]:
        meta["title"] = stem
    if not meta["artist"] and " - " in stem:
        meta["artist"] = stem.split(" - ", 1)[0]
    return meta


def probe_source_props(path: str) -> dict:
    """Best-effort bron-eigenschappen voor de 'original'-export-resolutie."""
    props = {"ext": Path(path).suffix.lower().lstrip("."),
             "samplerate": None, "channels": None,
             "bitrate_kbps": None, "bit_depth": None}
    try:
        import soundfile as sf
        info = sf.info(str(path))
        props["samplerate"] = int(info.samplerate)
        props["channels"] = int(info.channels)
        st = (info.subtype or "")
        if "PCM_16" in st:
            props["bit_depth"] = 16
        elif "PCM_24" in st:
            props["bit_depth"] = 24
        elif "PCM_32" in st or "FLOAT" in st or "DOUBLE" in st:
            props["bit_depth"] = 32
    except Exception:
        pass
    try:
        from mutagen import File as MutagenFile
        mf = MutagenFile(path)
        info = getattr(mf, "info", None)
        if info is not None:
            br = getattr(info, "bitrate", None)
            if br:
                props["bitrate_kbps"] = int(round(br / 1000.0))
            if not props["samplerate"]:
                srp = getattr(info, "sample_rate", None)
                if srp:
                    props["samplerate"] = int(srp)
            if not props["channels"]:
                ch = getattr(info, "channels", None)
                if ch:
                    props["channels"] = int(ch)
    except Exception:
        pass
    return props


def _ffmpeg() -> str:
    """Vind het ffmpeg-binary: env-override, gebundeld (frozen .exe), of op PATH."""
    import shutil
    cand = os.environ.get("SAMPLEFINDER_FFMPEG") or os.environ.get("IMAGEIO_FFMPEG_EXE")
    if cand and Path(cand).exists():
        return cand
    roots = []
    if getattr(sys, "frozen", False):                 # PyInstaller-bundel
        roots.append(Path(getattr(sys, "_MEIPASS", ".")))
        roots.append(Path(sys.executable).parent)
    for r in roots:
        for n in ("ffmpeg.exe", "ffmpeg"):
            if (r / n).exists():
                return str(r / n)
    return shutil.which("ffmpeg") or "ffmpeg"


def _have_ffmpeg() -> bool:
    """True als er een bruikbaar ffmpeg-binary gevonden wordt."""
    import shutil
    exe = _ffmpeg()
    return bool(Path(exe).exists() or shutil.which(exe))


def _ffmpeg_decode(path: str, target_sr=None, mono=False):
    """Fallback-decoder via ffmpeg -> float32; dekt formaten die libsndfile mist."""
    import soundfile as sf
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    try:
        cmd = [_ffmpeg(), "-y", "-v", "error", "-i", str(path)]
        if mono:
            cmd += ["-ac", "1"]
        if target_sr:
            cmd += ["-ar", str(int(target_sr))]
        cmd += ["-c:a", "pcm_f32le", tmp.name]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.PIPE)
        y, sr = sf.read(tmp.name, dtype="float32", always_2d=True)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
    y = y.T  # (channels, samples)
    if mono:
        y = y.mean(axis=0) if y.shape[0] > 1 else y[0]
    return y, sr


def _decode(path: str, target_sr=None, mono=False):
    """Decode via libsndfile/librosa; val stil terug op ffmpeg voor brede dekking."""
    try:
        import librosa
        return librosa.load(path, sr=target_sr, mono=mono)
    except Exception:
        pass
    try:
        return _ffmpeg_decode(path, target_sr=target_sr, mono=mono)
    except Exception as e:
        raise RuntimeError(
            f"kon audio niet decoderen: {Path(path).name} "
            f"(geen geldig/ondersteund audiobestand, of ffmpeg ontbreekt?)") from e


def load_mix_mono(path: str, sr: int):
    y, _ = _decode(path, target_sr=sr, mono=True)
    return np.asarray(y, dtype=np.float32)


def load_source_audio(path: str):
    """Decode de bron op originele samplerate, kanalen behouden -> (channels, n)."""
    y, sr = _decode(path, target_sr=None, mono=False)
    y = np.asarray(y, dtype=np.float32)
    if y.ndim == 1:
        y = y[None, :]            # mono -> (1, n); NIET dupliceren naar stereo
    return y, sr


# ----------------------------------------------------------------------------
# Stap 1a -- Beats/downbeats/segmenten  (allin1, met librosa-fallback)
# ----------------------------------------------------------------------------
def get_structure(path: str, backend: str):
    if backend == "allin1":
        try:
            import allin1
            r = allin1.analyze(path)
            return {
                "bpm": float(r.bpm),
                "beats": list(map(float, r.beats)),
                "downbeats": list(map(float, r.downbeats)),
                "segments": [
                    {"start": float(s.start), "end": float(s.end), "label": s.label}
                    for s in r.segments
                ],
            }
        except Exception as e:
            print(f"[structure] allin1 mislukte ({e}); val terug op librosa")
    import librosa
    y = load_mix_mono(path, CFG["analysis_sr"])
    tempo, beat_frames = librosa.beat.beat_track(
        y=y, sr=CFG["analysis_sr"], hop_length=CFG["hop_length"])
    beats = librosa.frames_to_time(
        beat_frames, sr=CFG["analysis_sr"], hop_length=CFG["hop_length"]).tolist()
    downbeats = beats[::4]  # ruwe 4/4-aanname
    dur = len(y) / CFG["analysis_sr"]
    return {"bpm": float(np.atleast_1d(tempo)[0]), "beats": beats,
            "downbeats": downbeats,
            "segments": [{"start": 0.0, "end": dur, "label": "unknown"}]}


# ----------------------------------------------------------------------------
# Stap 1b -- Density/sparseness op de MIX (geen separatie)
# ----------------------------------------------------------------------------
def analyze_density(y_mono, sr):
    import librosa
    hop = CFG["hop_length"]

    harm, perc = librosa.effects.hpss(y_mono)
    h_rms = librosa.feature.rms(y=harm, hop_length=hop)[0]
    p_rms = librosa.feature.rms(y=perc, hop_length=hop)[0]
    perc_ratio = p_rms / (h_rms + p_rms + 1e-9)

    chroma = librosa.feature.chroma_cqt(y=y_mono, sr=sr, hop_length=hop)
    cn = chroma / (chroma.sum(axis=0, keepdims=True) + 1e-9)
    chroma_entropy = -(cn * np.log(cn + 1e-9)).sum(axis=0) / np.log(12)

    S = np.abs(librosa.stft(y_mono, hop_length=hop)) ** 2
    Sn = S / (S.sum(axis=0, keepdims=True) + 1e-9)
    spec_entropy = -(Sn * np.log(Sn + 1e-9)).sum(axis=0) / np.log(S.shape[0])

    rms = librosa.feature.rms(y=y_mono, hop_length=hop)[0]
    rms_db = 20 * np.log10(rms + 1e-9)
    onset_env = librosa.onset.onset_strength(y=y_mono, sr=sr, hop_length=hop)

    n = min(len(perc_ratio), len(chroma_entropy), len(spec_entropy),
            len(rms_db), len(onset_env))
    sl = slice(0, n)
    sparseness = 1.0 - 0.5 * (spec_entropy[sl] + chroma_entropy[sl])
    times = librosa.frames_to_time(np.arange(n), sr=sr, hop_length=hop)
    return {"times": times, "perc_ratio": perc_ratio[sl],
            "chroma_entropy": chroma_entropy[sl], "spec_entropy": spec_entropy[sl],
            "rms_db": rms_db[sl], "onset_env": onset_env[sl], "sparseness": sparseness}


def _bar_windows(downbeats, total_dur):
    db = list(downbeats) + [total_dur]
    return [(db[i], db[i + 1], i) for i in range(len(db) - 1) if db[i + 1] > db[i]]


def _mean_in(feat, times, t0, t1):
    m = (times >= t0) & (times < t1)
    if not np.any(m):
        return None
    return {k: float(np.mean(v[m])) for k, v in feat.items()
            if k != "times" and len(v) == len(times)}


# ----------------------------------------------------------------------------
# Stap 2 -- Kandidaten detecteren (rule-based, per type)
# ----------------------------------------------------------------------------
def detect_candidates(feat, structure, total_dur, wanted_types):
    cands = []
    bars = _bar_windows(structure["downbeats"], total_dur)
    times = feat["times"]

    bar_class = []
    for (t0, t1, bi) in bars:
        agg = _mean_in(feat, times, t0, t1)
        if agg is None:
            bar_class.append((bi, t0, t1, None, 0.0))
            continue
        spars = agg["sparseness"]
        label = None
        if spars >= CFG["sparseness_min"]:
            if ("break" in wanted_types
                    and agg["perc_ratio"] >= CFG["break_perc_ratio_min"]
                    and agg["chroma_entropy"] <= CFG["break_chroma_entropy_max"]):
                label = "break"
            elif ("solo" in wanted_types
                    and agg["perc_ratio"] <= CFG["solo_perc_ratio_max"]
                    and agg["chroma_entropy"] <= CFG["solo_chroma_entropy_max"]):
                label = "solo"
        bar_class.append((bi, t0, t1, label, spars))

    cands += _merge_bars(bar_class, "break", CFG["break_min_bars"])
    cands += _merge_bars(bar_class, "solo", CFG["solo_min_bars"])
    if "tail" in wanted_types:
        cands += _detect_tails(feat, structure, total_dur)
    return cands


def _merge_bars(bar_class, label, min_bars):
    out, run = [], []
    for entry in bar_class + [(None, None, None, "__end__", 0.0)]:
        bi, t0, t1, lab, spars = entry
        if lab == label:
            run.append(entry)
        else:
            if len(run) >= min_bars:
                score = float(np.mean([r[4] for r in run]))
                hint = "drums" if label == "break" else "other"
                out.append(Candidate(label, run[0][1], run[-1][2], run[0][0],
                                      run[-1][0], round(score, 3), hint,
                                      note=f"{len(run)} maten"))
            run = []
    return out


def _detect_tails(feat, structure, total_dur):
    times = feat["times"]
    rms_db = feat["rms_db"]
    onset = feat["onset_env"]
    onset_thr = float(np.percentile(onset, 70))
    out = []
    for seg_end in [s["end"] for s in structure["segments"]]:
        look = CFG["tail_lookback_bars"] * 2.0
        t_start = max(0.0, seg_end - look)
        m = (times >= t_start) & (times <= min(seg_end + 1.0, total_dur))
        if not np.any(m):
            continue
        idx = np.where(m)[0]
        local_peak = float(np.max(rms_db[idx]))
        on_idx = idx[onset[idx] >= onset_thr]
        if len(on_idx) == 0:
            continue
        last_onset_t = float(times[on_idx[-1]])
        after = idx[times[idx] > last_onset_t]
        end_t = None
        for j in after:
            if rms_db[j] <= CFG["tail_silence_db"]:
                end_t = float(times[j])
                break
        if end_t is None:
            end_t = float(times[idx[-1]])
        dur = end_t - last_onset_t
        if dur < CFG["tail_min_dur_s"]:
            continue
        drop = float(rms_db[after].min() - local_peak) if len(after) else 0.0
        if drop > CFG["tail_rms_drop_db"]:
            continue
        spars = float(np.mean(feat["sparseness"][idx]))
        if spars < CFG["sparseness_min"]:
            continue
        out.append(Candidate("tail", round(last_onset_t, 3), round(end_t, 3),
                             -1, -1, round(spars, 3), "auto",
                             note=f"decay {dur:.2f}s, drop {drop:.0f}dB"))
    return out


# ----------------------------------------------------------------------------
# Stap 3 -- Export-resolutie (presets, CLI-spec, of interactief keuzemenu)
# ----------------------------------------------------------------------------
# (preset-sleutel, label) -- volgorde = volgorde in het keuzemenu.
RES_PRESETS = [
    ("original", "Origineel formaat + samplerate (aanrader)"),
    ("wav24", "WAV 24-bit / 48 kHz"),
    ("wav16", "WAV 16-bit / 44.1 kHz"),
    ("wav32", "WAV 32-bit float / originele SR"),
    ("flac24", "FLAC 24-bit / originele SR"),
    ("mp3-320", "MP3 320 kbps"),
]
PRESET_SPECS = {
    "wav24": {"fmt": "wav", "bit_depth": 24, "samplerate": 48000, "bitrate": None},
    "wav16": {"fmt": "wav", "bit_depth": 16, "samplerate": 44100, "bitrate": None},
    "wav32": {"fmt": "wav", "bit_depth": 32, "samplerate": None, "bitrate": None},
    "flac24": {"fmt": "flac", "bit_depth": 24, "samplerate": None, "bitrate": None},
    "mp3-320": {"fmt": "mp3", "bit_depth": None, "samplerate": None, "bitrate": 320},
}


def _original_spec(src_props):
    ext = (src_props.get("ext") or "wav").lower()
    if ext == "aif":
        ext = "aiff"
    is_pcm = ext in PCM_FORMATS
    return {"fmt": ext,
            # bit-depth telt enkel voor PCM; bitrate enkel voor lossy.
            "bit_depth": (src_props.get("bit_depth") or 24) if is_pcm else None,
            "samplerate": src_props.get("samplerate"),   # None -> bron-SR bij schrijven
            "bitrate": None if is_pcm else (src_props.get("bitrate_kbps") or 320)}


def resolve_export_spec(spec, src_props) -> dict:
    """Maak een concrete {fmt,bit_depth,samplerate,bitrate} uit preset/string/dict."""
    if spec is None:
        spec = "original"
    if isinstance(spec, str):
        if spec in ("original", "orig", ""):
            return _original_spec(src_props)
        if spec in PRESET_SPECS:
            return dict(PRESET_SPECS[spec])
        spec = {"fmt": spec}  # kale formaatnaam
    base = {"fmt": "wav", "bit_depth": None, "samplerate": None, "bitrate": None}
    base.update({k: v for k, v in (spec or {}).items()})
    fmt = (base.get("fmt") or "wav").lower()
    if fmt in ("original", "orig", ""):
        out = _original_spec(src_props)
        for k in ("bit_depth", "samplerate", "bitrate"):  # overlay expliciete waarden
            if base.get(k) is not None:
                out[k] = base[k]
        return out
    is_pcm = fmt in PCM_FORMATS
    return {"fmt": fmt,
            # PCM krijgt een default bit-depth (24); lossy houdt bit_depth=None zodat
            # er geen betekenisloze bit-depth wordt gesuggereerd.
            "bit_depth": ((base["bit_depth"] if base["bit_depth"] is not None else 24)
                          if is_pcm else base["bit_depth"]),
            "samplerate": base["samplerate"],
            "bitrate": base["bitrate"] if base["bitrate"] is not None else 320}


def pick_resolution_menu(src_props):
    """Toon het keuzemenu voor export-resolutie (dubbelklik-modus)."""
    print("\nKies export-resolutie:")
    for i, (key, label) in enumerate(RES_PRESETS):
        extra = ""
        if key == "original":
            sr = src_props.get("samplerate")
            extra = f"   [bron: .{src_props.get('ext', '?')}, {sr or '?'} Hz]"
        print(f"  {i}) {label}{extra}")
    print(f"  {len(RES_PRESETS)}) Aangepast (formaat / bit-depth / SR / bitrate)")
    raw = input("Keuze [0]: ").strip() or "0"
    try:
        idx = int(raw)
    except ValueError:
        idx = 0
    if 0 <= idx < len(RES_PRESETS):
        return RES_PRESETS[idx][0]
    # Aangepast
    fmt = (input("  Formaat [wav]: ").strip().lower() or "wav")
    spec = {"fmt": fmt, "bit_depth": None, "samplerate": None, "bitrate": None}
    if fmt in PCM_FORMATS:
        try:
            spec["bit_depth"] = int(input("  Bit-depth [24]: ").strip() or "24")
        except ValueError:
            spec["bit_depth"] = 24
    else:
        try:
            spec["bitrate"] = int(input("  Bitrate kbps [320]: ").strip() or "320")
        except ValueError:
            spec["bitrate"] = 320
    sr_in = input("  Samplerate Hz [origineel]: ").strip()
    if sr_in:
        try:
            spec["samplerate"] = int(sr_in)
        except ValueError:
            pass
    return spec


# ----------------------------------------------------------------------------
# Stap 4 -- Audio-aware snijden uit de mix + schrijven (geen separatie)
# ----------------------------------------------------------------------------
def _apply_fade(audio, sr):
    n = int(CFG["fade_ms"] / 1000.0 * sr)
    if n > 0 and audio.shape[1] > 2 * n:
        ramp = np.linspace(0, 1, n)
        audio[:, :n] *= ramp
        audio[:, -n:] *= ramp[::-1]
    return audio


def cut_region(src_audio, src_sr, t0, t1):
    """Knip [t0,t1] (met pad + anti-klik-fade) uit de originele mix."""
    i0 = max(0, int((t0 - CFG["pad_seconds"]) * src_sr))
    i1 = min(src_audio.shape[1], int((t1 + CFG["pad_seconds"]) * src_sr))
    audio = src_audio[:, i0:i1].astype(np.float32, copy=True)
    return _apply_fade(audio, src_sr)


def _sanitize(s: str) -> str:
    s = re.sub(r'[<>:"/\\|?*]', "", s).strip()
    s = re.sub(r"\s+", "-", s)
    return s or "x"


def _timestamp(sec: float) -> str:
    m, s = divmod(sec, 60)
    return f"{int(m):02d}m{s:05.2f}s".replace(".", "")


def build_filename(meta, cand, res_tag, ext):
    artist = _sanitize(meta.get("artist") or "unknown")
    title = _sanitize(meta.get("title") or "untitled")
    pos = (f"bars{cand.start_bar:03d}-{cand.end_bar:03d}"
           if cand.start_bar >= 0 else "free")
    times = f"{_timestamp(cand.start)}-{_timestamp(cand.end)}"
    return f"{artist}_{title}__{cand.type}__{pos}__{times}__{res_tag}.{ext}"


def export_candidate(meta, cand, src_audio, src_sr, src_props, out_dir, spec):
    """Knip de mix-clip en schrijf hem in de gekozen resolutie."""
    import soundfile as sf
    import librosa

    res = resolve_export_spec(spec, src_props)
    fmt = res["fmt"].lower()
    audio = cut_region(src_audio, src_sr, cand.start, cand.end)
    if audio.shape[1] < 1:
        raise ValueError("leeg venster (start >= end na padding)")

    out_sr = res["samplerate"] or src_sr
    if res["samplerate"] and res["samplerate"] != src_sr:
        audio = np.stack([librosa.resample(audio[c], orig_sr=src_sr,
                                            target_sr=res["samplerate"])
                          for c in range(audio.shape[0])])

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if fmt in PCM_FORMATS:
        bd = res["bit_depth"] or 24
        if fmt == "flac" and bd == 32:      # FLAC kent geen 32-bit float
            bd = 24
        subtype = {16: "PCM_16", 24: "PCM_24", 32: "FLOAT"}.get(bd, "PCM_24")
        ext = "aiff" if fmt in ("aif", "aiff") else fmt
        res_tag = f"{bd}b-{out_sr // 1000}k"
        fname = build_filename(meta, cand, res_tag, ext)
        sf.write(str(out_dir / fname), audio.T, out_sr, subtype=subtype)
    else:
        br = res["bitrate"] or 320
        res_tag = f"{br}k"
        fname = build_filename(meta, cand, res_tag, fmt)
        tmp = out_dir / (fname + ".tmp.wav")
        sf.write(str(tmp), audio.T, out_sr, subtype="PCM_24")
        try:
            subprocess.run([_ffmpeg(), "-y", "-v", "error", "-i", str(tmp), "-vn",
                            "-b:a", f"{br}k", str(out_dir / fname)], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        finally:
            tmp.unlink(missing_ok=True)
    print(f"    -> {fname}")
    return fname


# ----------------------------------------------------------------------------
# Per-bestand orkestratie
# ----------------------------------------------------------------------------
def print_candidates(cands):
    print(f"  {len(cands)} kandidaten:")
    print(f"  {'#':>2} {'type':<6} {'start':>8} {'end':>8} {'score':>6} {'hint':<7} note")
    for i, c in enumerate(cands):
        print(f"  {i:>2} {c.type:<6} {c.start:>8.2f} {c.end:>8.2f} "
              f"{c.score:>6.2f} {c.stem_hint:<7} {c.note}")


def analyze_one(input_path, out_dir, types, beat_backend):
    print(f"  [1/3] structuur ({beat_backend}) ...")
    meta = read_metadata(input_path)
    src_props = probe_source_props(input_path)
    structure = get_structure(input_path, beat_backend)
    print(f"        bpm~{structure['bpm']:.1f}, {len(structure['downbeats'])} downbeats")
    print("  [2/3] density-analyse op de mix ...")
    y = load_mix_mono(input_path, CFG["analysis_sr"])
    total_dur = len(y) / CFG["analysis_sr"]
    feat = analyze_density(y, CFG["analysis_sr"])
    print("  [3/3] kandidaten ...")
    cands = detect_candidates(feat, structure, total_dur, types)
    cands.sort(key=lambda c: c.score, reverse=True)
    print_candidates(cands)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    js = out / (Path(input_path).stem + ".candidates.json")
    js.write_text(json.dumps(
        {"meta": meta, "source": src_props,
         "structure": {"bpm": structure["bpm"]},
         "candidates": [asdict(c) for c in cands]}, indent=2), encoding="utf-8")
    return meta, cands, js


def export_one(input_path, out_dir, types, index, spec):
    js = Path(out_dir) / (Path(input_path).stem + ".candidates.json")
    if not js.exists():
        print(f"  geen kandidaten-JSON voor {Path(input_path).name}; sla over.")
        return
    data = json.loads(js.read_text(encoding="utf-8"))
    meta = data["meta"]
    # Bepaal de 'original'-resolutie uit het ECHTE invoerbestand (altijd aanwezig
    # bij export); de in JSON bewaarde 'source' is enkel een record.
    src_props = probe_source_props(input_path) or data.get("source") or {}
    cands = [_cand_from_dict(c) for c in data["candidates"] if c["type"] in types]
    if index:
        cands = [cands[i] for i in index if 0 <= i < len(cands)]
    if not cands:
        print("  niets te exporteren.")
        return
    res = resolve_export_spec(spec, src_props)
    if res["fmt"] not in PCM_FORMATS:
        if not _have_ffmpeg():
            print(f"  ffmpeg niet gevonden -- vereist voor '{res['fmt']}'-export. "
                  "Installeer ffmpeg (op PATH) of kies wav/flac/aiff.")
            return
        if (res.get("bit_depth") or 0) > 16:
            print("  LET OP: lossy export -- bit-depth telt niet; hogere resolutie "
                  "voegt geen informatie toe.")
    src, src_sr = load_source_audio(input_path)
    track_out = Path(out_dir) / Path(input_path).stem
    print(f"  export {len(cands)} clip(s) uit de mix als '{res['fmt']}' "
          f"-> {track_out}")
    for c in cands:
        print(f"  - {c.type} {c.start:.2f}-{c.end:.2f}s")
        try:
            export_candidate(meta, c, src, src_sr, src_props, track_out, spec)
        except Exception as e:
            print(f"    overgeslagen ({e})")


# ----------------------------------------------------------------------------
# CLI + interactieve (dubbelklik) modus
# ----------------------------------------------------------------------------
def _run_batch(files, out_dir, types, backend, do_export, spec=None, index=None):
    for f in files:
        print(f"\n=== {f.name} ===")
        try:
            analyze_one(str(f), out_dir, types, backend)
            if do_export:
                export_one(str(f), out_dir, types, index, spec)
        except Exception as e:
            print(f"  FOUT bij {f.name}: {e}")


def interactive_main():
    print("=" * 62)
    print(" Sample Finder v2  --  sparse-section finder (analyse + mix-export)")
    print("=" * 62)
    path = pick_input_dialog()
    if not path:
        print("Geen invoer gekozen.")
        _pause()
        return
    files = collect_inputs(path, recursive=False)
    if not files:
        print("Geen audiobestanden gevonden.")
        _pause()
        return
    base = Path(path).parent if Path(path).is_file() else Path(path)
    out_dir = str(base / "sample_finder_out")
    print(f"\n{len(files)} bestand(en). Output -> {out_dir}\n")

    resolve_tuning(search_dirs=[base])

    types = ["break", "solo", "tail"]
    for f in files:
        print(f"\n=== {f.name} ===")
        try:
            analyze_one(str(f), out_dir, types, "librosa")
        except Exception as e:
            print(f"  FOUT bij {f.name}: {e}")

    ans = input("\nKandidaten exporteren? (y/n): ").strip().lower()
    if ans == "y":
        spec = pick_resolution_menu(probe_source_props(str(files[0])))
        print()
        for f in files:
            print(f"=== export {f.name} ===")
            export_one(str(f), out_dir, types, None, spec)
    print("\nKlaar.")
    _pause()


# ----------------------------------------------------------------------------
# Drempels instelbaar maken (CLI-vlaggen / --set / config-bestand)
# ----------------------------------------------------------------------------
# (vlag, CFG-sleutel, type, hulptekst). Alleen de detectie-drempels krijgen een
# eigen vlag; elke andere CFG-sleutel blijft bereikbaar via --set of --config.
THRESHOLD_FLAGS = [
    ("--sparseness-min", "sparseness_min", float, "min. sparseness-score per maat"),
    ("--break-perc-ratio-min", "break_perc_ratio_min", float, "break: min. percussie-ratio"),
    ("--break-chroma-entropy-max", "break_chroma_entropy_max", float, "break: max. chroma-entropie"),
    ("--break-min-bars", "break_min_bars", int, "break: min. aantal maten"),
    ("--solo-perc-ratio-max", "solo_perc_ratio_max", float, "solo: max. percussie-ratio"),
    ("--solo-chroma-entropy-max", "solo_chroma_entropy_max", float, "solo: max. chroma-entropie"),
    ("--solo-min-bars", "solo_min_bars", int, "solo: min. aantal maten"),
    ("--tail-rms-drop-db", "tail_rms_drop_db", float, "tail: toegestane RMS-daling (dB)"),
    ("--tail-silence-db", "tail_silence_db", float, "tail: stilte-drempel (dB)"),
    ("--tail-min-dur-s", "tail_min_dur_s", float, "tail: min. duur (s)"),
    ("--tail-lookback-bars", "tail_lookback_bars", float, "tail: terugkijk in maten"),
]


def add_tuning_args(sp):
    """Voeg drempel-/config-vlaggen toe aan een subcommando-parser."""
    g = sp.add_argument_group(
        "drempels",
        "overschrijf CFG zonder de broncode te wijzigen "
        "(prioriteit: config-bestand < losse vlaggen < --set)")
    g.add_argument("--config", default=None,
                   help=f"JSON met CFG-overrides (auto: {CONFIG_FILENAME} naast invoer/werkmap)")
    g.add_argument("--set", dest="cfg_set", action="append", default=[],
                   metavar="KEY=VALUE",
                   help="overschrijf één CFG-sleutel; herhaalbaar (bv. --set solo_min_bars=2)")
    for flag, key, typ, helptxt in THRESHOLD_FLAGS:
        g.add_argument(flag, dest=f"cfg_{key}", type=typ, default=None, help=helptxt)


def resolve_tuning(args=None, search_dirs=()):
    """Verzamel en pas CFG-overrides toe (config-bestand < vlaggen < --set)."""
    overrides = {}
    cfg_path = getattr(args, "config", None) if args else None
    if not cfg_path:
        cfg_path = find_sidecar_config(list(search_dirs) + [Path.cwd()])
        if cfg_path:
            print(f"[cfg] sidecar-config gevonden: {cfg_path}")
    if cfg_path:
        overrides.update(load_config_file(cfg_path))
    if args is not None:
        for _flag, key, _typ, _h in THRESHOLD_FLAGS:
            v = getattr(args, f"cfg_{key}", None)
            if v is not None:
                overrides[key] = v
        for item in getattr(args, "cfg_set", []) or []:
            if "=" not in item:
                print(f"[cfg] negeer --set zonder '=': {item}")
                continue
            k, v = item.split("=", 1)
            overrides[k.strip()] = v.strip()
    applied = apply_cfg_overrides(overrides)
    if applied:
        print("[cfg] actieve overrides: "
              + ", ".join(f"{k}={CFG[k]}" for k in sorted(applied)))
    return applied


def _add_export_args(sp):
    """Resolutie-/selectievlaggen voor export en run."""
    sp.add_argument("--index", nargs="*", type=int, default=None,
                    help="exporteer enkel deze kandidaat-indices")
    sp.add_argument("--format", default="original",
                    help="export-formaat: original|wav|flac|aiff|ogg|mp3|m4a|aac|opus|wma")
    sp.add_argument("--bit-depth", type=int, default=None, choices=[16, 24, 32],
                    help="PCM bit-depth (wav/flac/aiff)")
    sp.add_argument("--samplerate", type=int, default=None,
                    help="doel-samplerate in Hz (default: origineel)")
    sp.add_argument("--bitrate", type=int, default=None,
                    help="bitrate in kbps voor lossy formaten (default 320)")


def spec_from_args(args):
    """Bouw een export-spec uit CLI-vlaggen; 'original' als niets gezet is."""
    if (args.format in ("original", "orig") and args.bit_depth is None
            and args.samplerate is None and args.bitrate is None):
        return "original"
    return {"fmt": args.format, "bit_depth": args.bit_depth,
            "samplerate": args.samplerate, "bitrate": args.bitrate}


def main():
    if len(sys.argv) == 1:          # dubbelklik / geen argumenten
        interactive_main()
        return

    p = argparse.ArgumentParser(description="Sparse-section sample finder (v2, analyse-only)")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, helptxt in [("analyze", "detecteer kandidaten"),
                          ("export", "snijd kandidaten uit de mix + schrijf"),
                          ("run", "analyze + export ineen")]:
        sp = sub.add_parser(name, help=helptxt)
        sp.add_argument("input", help="bestand OF map")
        sp.add_argument("--out-dir", default="./out")
        sp.add_argument("--types", nargs="+", default=["break", "solo", "tail"],
                        choices=["break", "solo", "tail"])
        sp.add_argument("--recursive", action="store_true")
        sp.add_argument("--beat-backend", default="allin1",
                        choices=["allin1", "librosa"])
        if name in ("analyze", "run"):
            add_tuning_args(sp)
        if name in ("export", "run"):
            _add_export_args(sp)

    args = p.parse_args()
    files = collect_inputs(args.input, args.recursive)
    if not files:
        print(f"Geen audiobestanden gevonden op: {args.input}")
        sys.exit(1)

    if args.cmd in ("analyze", "run"):
        in_dir = (args.input if Path(args.input).is_dir()
                  else str(Path(args.input).parent))
        resolve_tuning(args, search_dirs=[in_dir])

    if args.cmd == "analyze":
        _run_batch(files, args.out_dir, args.types, args.beat_backend,
                   do_export=False)
    elif args.cmd == "export":
        spec = spec_from_args(args)
        for f in files:
            print(f"\n=== {f.name} ===")
            export_one(str(f), args.out_dir, args.types, args.index, spec)
    elif args.cmd == "run":
        _run_batch(files, args.out_dir, args.types, args.beat_backend,
                   do_export=True, spec=spec_from_args(args), index=args.index)


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()   # nodig voor een bevroren (.exe) build
    main()
```
