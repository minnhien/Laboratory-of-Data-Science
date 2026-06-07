import json
import statistics
import math
import calendar
from datetime import date
# CONFIGURATION
INPUT_FILE = "tracks.json"
OUTPUT_FILE = "tracks_final.json"
NULL_STRINGS = {"nan", "n/a", "null", "none", ""}
# HELPERS
def normalize_str(s):
    return s.strip().lower() if isinstance(s, str) else s

def is_empty(val) -> bool:
    if val is None:
        return True
    if isinstance(val, float) and math.isnan(val):
        return True
    if isinstance(val, str):
        return normalize_str(val) in NULL_STRINGS
    return False

def safe_float(val):
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return None if (isinstance(val, float) and math.isnan(val)) else float(val)
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return None
        if "." in s and "," in s:
            s = s.replace(".", "").replace(",", ".")
        elif "," in s and "." not in s:
            # decimal comma
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")
        try:
            x = float(s)
            return x if not math.isnan(x) else None
        except ValueError:
            return None
    return None

def _clean_int(val):
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None

def median_or_none(values_iter):
    vals = []
    for v in values_iter:
        fv = safe_float(v)
        if fv is not None:
            vals.append(fv)
    if not vals:
        return None
    return statistics.median(vals)

def parse_y_m_d_loose(s):
    if not isinstance(s, str) or is_empty(s):
        return (None, None, None)
    if len(s) == 4 and s.isdigit():
        return (int(s), None, None)
    sep = "-" if "-" in s else ("/" if "/" in s else None)
    if not sep:
        return (None, None, None)
    parts = s.split(sep)
    if not (1 <= len(parts) <= 3) or not all(p.isdigit() for p in parts):
        return (None, None, None)
    if len(parts[0]) != 4:
        return (None, None, None)
    y = int(parts[0])
    m = int(parts[1]) if len(parts) >= 2 else None
    d = int(parts[2]) if len(parts) >= 3 else None
    return (y, m, d)
# DEDUP
def _norm_key_part(x):
    if x is None:
        return None
    if isinstance(x, str):
        s = x.strip().lower()
        return None if s == "" else s
    return x

def remove_duplicates(data):
    indices_to_drop = {4627, 4647, 4648}
    # drop by index first
    filtered = [row for i, row in enumerate(data) if i not in indices_to_drop]

    seen = set()
    cleaned = []
    empty_key = (None, None, None)

    for row in filtered:
        key = (
            _norm_key_part(row.get("id_artist")),
            _norm_key_part(row.get("id")),
            _norm_key_part(row.get("title")),
        )
        if key == empty_key:
            if empty_key not in seen:
                seen.add(empty_key)
                cleaned.append(row)
            continue
        if key not in seen:
            seen.add(key)
            cleaned.append(row)
    return cleaned

# MEDIANS
def collect_medians(data, numeric_cols):
    med = {}
    for col in numeric_cols:
        med[col] = median_or_none((row.get(col) for row in data))
    return med
# ROW PROCESSOR
def process_single_row(row, medians):
    # 1) Album sync
    alb, name = row.get("album"), row.get("album_name")
    if is_empty(alb) and is_empty(name):
        row["album"] = None; row["album_name"] = None
    elif is_empty(alb):
        row["album"] = name
    elif is_empty(name):
        row["album_name"] = alb

    # 2) Numeric medians (skip when median is None)
    for col, med in medians.items():
        if med is not None and is_empty(row.get(col)):
            row[col] = med

    # 3) Explicit
    s_it = int(safe_float(row.get("swear_IT")) or 0)
    s_en = int(safe_float(row.get("swear_EN")) or 0)
    row["explicit"] = 1 if (s_it > 0 or s_en > 0) else 0

    # 4) Simple missing fields
    for col in ("popularity", "featured_artists", "album_type", "disc_number", "track_number"):
        if is_empty(row.get(col)):
            row[col] = None
    if is_empty(row.get("id_album")):
        row["id_album"] = -1
    # 6) Language: normalize empties only (auto-detect removed)
    row["language"] = row.get("language") if not is_empty(row.get("language")) else None

    # 5) Date recovery and features
    y = _clean_int(row.get("year"))
    m = _clean_int(row.get("month"))
    d = _clean_int(row.get("day"))

    alb_raw = row.get("album_release_date")
    alb_str = str(alb_raw) if alb_raw is not None else ""
    ay, am, ad = parse_y_m_d_loose(alb_str)

    if y is None and ay is not None:
        y = ay
    if m is None and am is not None:
        m = am
    if d is None and ad is not None:
        d = ad

    row["year"] = y
    row["month"] = m
    row["day"] = d
    # full_date
    if y is None:
        row["full_date"] = "-1"
    else:
        m_val = m if (m is not None and 1 <= m <= 12) else 0
        d_val = d if (d is not None and d > 0) else 0
        row["full_date"] = f"{y:04d}{m_val:02d}{d_val:02d}"

    # derived
    row["month_name"] = None
    row["month_hierarchy"] = None
    row["quarter"] = None
    row["the_day"] = None
    row["week_of_year"] = None

    if y is not None and m is not None and 1 <= m <= 12:
        row["month_name"] = calendar.month_name[m]
        row["month_hierarchy"] = f"{y}{m:02d}"
        row["quarter"] = (m - 1) // 3 + 1
        if d is not None and d > 0:
            try:
                dt = date(y, m, d)
                row["the_day"] = dt.strftime("%A")
                row["week_of_year"] = dt.isocalendar()[1]
            except ValueError:
                pass  # invalid calendar date: keep None

    # 7) Lyrics features (use non-empty lines)
    lyrics = row.get("lyrics")
    if not is_empty(lyrics) and isinstance(lyrics, str):
        txt = lyrics.strip()
        words = txt.split()
        lines = [ln for ln in txt.split("\n") if ln.strip() != ""]
        n_tokens = len(words)
        n_sentences = len(lines)
        row["n_tokens"] = n_tokens
        row["n_sentences"] = n_sentences
        row["char_per_tok"] = (sum(len(w) for w in words) / n_tokens) if n_tokens else 0
        row["avg_token_per_clause"] = (n_tokens / n_sentences) if n_sentences else 0
    else:
        row["lyrics"] = None
        row["n_tokens"] = 0
        row["n_sentences"] = 0
        row["char_per_tok"] = 0
        row["avg_token_per_clause"] = 0
# QA
def final_qa_report(data):
    print("\n Final QA Report (Missing Values) ")
    if not data:
        print("No data")
        return
    all_keys = set()
    for r in data:
        all_keys.update(r.keys())
    all_keys = sorted(all_keys)
    total = len(data)
    for k in all_keys:
        miss = sum(1 for r in data if is_empty(r.get(k)))
        if miss > 0:
            print(f"{k:<25} | {miss:<10} missing ({miss/total*100:.1f}%)")

# MAIN
def main():
    print(" Processing Pipeline Started ")
    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"Loaded {len(data)} rows.")
    except FileNotFoundError:
        print(f"Input file '{INPUT_FILE}' not found.")
        return
    # Dedup
    data = remove_duplicates(data)
    # Medians
    print("Calculating medians...")
    numeric_cols = ["flatness", "loudness", "pitch", "spectral_complexity",
                    "rms", "flux", "rolloff", "bpm", "duration_ms"]
    medians = collect_medians(data, numeric_cols)
    # Process
    print("Applying logic (Cleaning, Dates, Enrichment)...")
    for row in data:
        process_single_row(row, medians)
    # QA
    final_qa_report(data)
    # Save
    print(f"\nSaving final output to {OUTPUT_FILE} ...")
    try:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print("Done.")
    except Exception as e:
        print(f"Error saving: {e}")

if __name__ == "__main__":
    main()
