"""Snelle unit-tests voor de pure (audio-vrije) logica van sample_finder.

Deze tests importeren enkel `sample_finder` (dat alleen numpy bovenaan importeert);
librosa/soundfile/ffmpeg zijn niet nodig, dus ze draaien snel in CI.
"""
import argparse
import json

import sample_finder as sf


# ---------------------------------------------------------------- CFG-overrides
def test_apply_cfg_overrides_coerce_unknown_and_comment(capsys):
    orig = dict(sf.CFG)
    try:
        applied = sf.apply_cfg_overrides({
            "solo_min_bars": "3",        # str -> int
            "sparseness_min": "0.4",     # str -> float
            "_comment": "negeren",       # underscore -> stil overgeslagen
            "bogus_key": 1,              # onbekend -> waarschuwing, niet toegepast
        })
        assert applied["solo_min_bars"] == 3
        assert isinstance(sf.CFG["solo_min_bars"], int)
        assert applied["sparseness_min"] == 0.4
        assert "bogus_key" not in applied and "_comment" not in applied
        assert "onbekende drempel" in capsys.readouterr().out
    finally:
        sf.CFG.clear()
        sf.CFG.update(orig)


def test_load_config_file(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"CFG": {"solo_min_bars": 2}}))   # {'CFG': {...}} vorm
    assert sf.load_config_file(str(p)) == {"solo_min_bars": 2}
    q = tmp_path / "d.json"
    q.write_text(json.dumps({"sparseness_min": 0.3}))         # platte vorm
    assert sf.load_config_file(str(q)) == {"sparseness_min": 0.3}
    assert sf.load_config_file(str(tmp_path / "nope.json")) == {}


# ----------------------------------------------------------- export-resolutie
def test_resolve_original_pcm_vs_lossy():
    pcm = sf.resolve_export_spec(
        "original", {"ext": "wav", "samplerate": 48000, "bit_depth": 24, "bitrate_kbps": None})
    assert pcm == {"fmt": "wav", "bit_depth": 24, "samplerate": 48000, "bitrate": None}
    lossy = sf.resolve_export_spec(
        "original", {"ext": "mp3", "samplerate": 44100, "bit_depth": None, "bitrate_kbps": 320})
    assert lossy["fmt"] == "mp3" and lossy["bit_depth"] is None and lossy["bitrate"] == 320


def test_resolve_presets_bare_string_and_custom():
    assert sf.resolve_export_spec("wav16", {}) == {
        "fmt": "wav", "bit_depth": 16, "samplerate": 44100, "bitrate": None}
    # kale lossless formaatnaam -> default 24-bit
    assert sf.resolve_export_spec("flac", {})["bit_depth"] == 24
    # kale lossy formaatnaam -> bit_depth blijft None (geen betekenis)
    m = sf.resolve_export_spec("mp3", {})
    assert m["bit_depth"] is None and m["bitrate"] == 320
    # custom dict overlay
    assert sf.resolve_export_spec({"fmt": "wav", "bit_depth": 32}, {})["bit_depth"] == 32


def test_resolve_aif_normalised():
    s = sf.resolve_export_spec("original", {"ext": "aif", "samplerate": 44100, "bit_depth": 16})
    assert s["fmt"] == "aiff"


def test_spec_from_args():
    a = argparse.Namespace(format="original", bit_depth=None, samplerate=None, bitrate=None)
    assert sf.spec_from_args(a) == "original"
    a2 = argparse.Namespace(format="wav", bit_depth=24, samplerate=48000, bitrate=None)
    s = sf.spec_from_args(a2)
    assert s["fmt"] == "wav" and s["bit_depth"] == 24 and s["samplerate"] == 48000


# --------------------------------------------------------------- bestandsnaam
def test_build_filename_and_sanitize():
    c = sf.Candidate("break", 72.0, 81.0, 32, 36, 0.9, "drums", "x")
    name = sf.build_filename({"artist": "Chem Bros", "title": "Setting/Sun"}, c, "24b-44k", "wav")
    assert name.startswith("Chem-Bros_SettingSun__break__bars032-036__")
    assert name.endswith("__24b-44k.wav")
    t = sf.Candidate("tail", 1.0, 2.5, -1, -1, 0.6, "auto", "")
    assert "__tail__free__" in sf.build_filename({}, t, "320k", "mp3")


def test_timestamp():
    assert sf._timestamp(68.011) == "01m0801s"
    assert sf._timestamp(0.0) == "00m0000s"


# ------------------------------------------------------------ candidate-JSON
def test_cand_from_dict_backcompat():
    d = {"type": "solo", "start": 1.0, "end": 2.0, "start_bar": 0, "end_bar": 1,
         "score": 0.5, "dominant_stem": "other", "note": "n"}     # oude sleutel
    c = sf._cand_from_dict(d)
    assert c.stem_hint == "other" and c.type == "solo"
    d2 = {**d}; d2.pop("dominant_stem"); d2["stem_hint"] = "drums"
    assert sf._cand_from_dict(d2).stem_hint == "drums"


# -------------------------------------------------------------- invoer/sidecar
def test_collect_inputs(tmp_path):
    (tmp_path / "a.wav").write_bytes(b"x")
    (tmp_path / "b.txt").write_text("no")
    sub = tmp_path / "sub"; sub.mkdir(); (sub / "c.mp3").write_bytes(b"y")
    assert [p.name for p in sf.collect_inputs(str(tmp_path))] == ["a.wav"]
    assert {p.name for p in sf.collect_inputs(str(tmp_path), recursive=True)} == {"a.wav", "c.mp3"}
    assert sf.collect_inputs(str(tmp_path / "a.wav")) == [tmp_path / "a.wav"]
    assert sf.collect_inputs(str(tmp_path / "ghost.wav")) == []


def test_find_sidecar_config(tmp_path):
    cfg = tmp_path / sf.CONFIG_FILENAME
    cfg.write_text("{}")
    assert sf.find_sidecar_config([str(tmp_path)]) == str(cfg)
    assert sf.find_sidecar_config([str(tmp_path / "sub")]) is None


# -------------------------------------------------------------------- ffmpeg
def test_ffmpeg_env_override(monkeypatch, tmp_path):
    fake = tmp_path / "ffmpeg"
    fake.write_text("#")
    monkeypatch.setenv("SAMPLEFINDER_FFMPEG", str(fake))
    assert sf._ffmpeg() == str(fake)
    monkeypatch.setenv("SAMPLEFINDER_FFMPEG", str(tmp_path / "nope"))   # bestaat niet
    assert sf._ffmpeg() != str(tmp_path / "nope")                      # genegeerd


# ----------------------------------------------------------- gevoeligheid / stop
def test_sensitivity_to_overrides_bounds_and_monotonic():
    lo = sf.sensitivity_to_overrides(0)
    mid = sf.sensitivity_to_overrides(70)
    hi = sf.sensitivity_to_overrides(100)
    # hoger = lossere gate (lagere sparseness_min) en ruimere solo-chroma
    assert hi["sparseness_min"] < mid["sparseness_min"] < lo["sparseness_min"]
    assert hi["solo_chroma_entropy_max"] > lo["solo_chroma_entropy_max"]
    assert lo["solo_min_bars"] >= hi["solo_min_bars"] >= 1
    assert set(lo).issubset(set(sf.CFG))                 # alle keys bestaan in CFG
    assert sf.sensitivity_to_overrides(-5) == sf.sensitivity_to_overrides(0)      # clamp
    assert sf.sensitivity_to_overrides(150) == sf.sensitivity_to_overrides(100)   # clamp


def test_reset_cfg_restores_defaults():
    sf.apply_cfg_overrides({"sparseness_min": 0.123})
    assert sf.CFG["sparseness_min"] == 0.123
    sf.reset_cfg()
    assert sf.CFG == sf.CFG_DEFAULTS


def test_analyze_one_cancellation(tmp_path):
    import pytest
    # een cancel die meteen True geeft -> direct AnalysisCancelled (raakt geen audio)
    with pytest.raises(sf.AnalysisCancelled):
        sf.analyze_one("x.wav", str(tmp_path), ["break"], "librosa", cancel=lambda: True)
