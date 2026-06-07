import xml.etree.ElementTree as ET
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import re


INPUT_XML = "artists_enriched.xml"
OUTPUT_XML = "artists_enriched.xml"  

DEBUG = False


MIN_DELAY_SECONDS = 1

# Normalizations 
CITY_NORMALIZATION = {"casteddu": "Cagliari"}
PROVINCE_NORMALIZATION = {
    "casteddu/cagliari": "Cagliari",
    "casteddu": "Cagliari",
    "roma capitale": "Roma",
}
REGION_NORMALIZATION = {"sardigna/sardegna": "Sardegna"}

# Regex compiled 
YEAR_PATTERN = re.compile(r"\((\d{4})-")
GROUP_PATTERN = re.compile(r"\bun gruppo musicale\b", re.IGNORECASE)
ITALIAN_WORD_PATTERN = re.compile(r"\bitalian[oa]\b")
ITALO_MIXED_PATTERN = re.compile(r"italo-([a-z]+)")



def is_empty(val) -> bool:
    if val is None:
        return True
    s = str(val).strip()
    return s == "" or s.lower() in {"none", "nan"}

def get_text(row: ET.Element, tag: str) -> str:
    txt = row.findtext(tag)
    return (txt or "").strip()

def set_text(row: ET.Element, tag: str, value) -> None:
    el = row.find(tag)
    if el is None:
        el = ET.SubElement(row, tag)
    el.text = "" if value is None else str(value)

def normalize_text(value, mapping: dict):
    if is_empty(value):
        return value
    key = str(value).strip().lower()
    return mapping.get(key, value)

import h3

if hasattr(h3, "geo_to_h3"): 
    def h3_from_latlon(lat, lon, resolution=8):
        return h3.geo_to_h3(lat, lon, resolution)
elif hasattr(h3, "latlng_to_cell"): 
    def h3_from_latlon(lat, lon, resolution=8):
        return h3.latlng_to_cell(lat, lon, resolution)
else:
    raise RuntimeError("H3 library has neither geo_to_h3 nor latlng_to_cell")


# Geocoders 
geolocator = Nominatim(user_agent="t.do1")

geocode = RateLimiter(
    geolocator.geocode,
    min_delay_seconds=MIN_DELAY_SECONDS,
    swallow_exceptions=True,
)
reverse = RateLimiter(
    geolocator.reverse,
    min_delay_seconds=MIN_DELAY_SECONDS,
    swallow_exceptions=True,
)

# Caches
_geocode_cache = {}      
_reverse_cache = {}      

def reverse_fill(lat: float, lon: float):
    # cache by rounded coordinates to avoid repeating identical reverse lookups
    key = (round(lat, 5), round(lon, 5))
    if key in _reverse_cache:
        return _reverse_cache[key]

    loc = reverse((lat, lon), language="it")
    if loc is None:
        result = (None, None, None, None)
        _reverse_cache[key] = result
        return result

    addr = loc.raw.get("address", {})
    if DEBUG:
        print("DEBUG reverse addr", key, "->", addr)

    country = addr.get("country")
    region = addr.get("state") or addr.get("region")
    province = addr.get("county") or addr.get("province") or addr.get("state_district")
    city = addr.get("city") or addr.get("town") or addr.get("village")

    result = (city, province, region, country)
    _reverse_cache[key] = result
    return result

def geocode_birth_place(birth_place: str):
    if is_empty(birth_place):
        return (None, None, None, None, None)

    bp = birth_place.strip()
    cache_key = bp.lower()
    if cache_key in _geocode_cache:
        return _geocode_cache[cache_key]

    locs = geocode(bp, addressdetails=True, exactly_one=False, limit=5)

    if not locs:
        result = (None, None, None, None, None)
        _geocode_cache[cache_key] = result
        return result

    if not isinstance(locs, list):
        locs = [locs]

    # Prefer Italy if present
    chosen = None
    for cand in locs:
        addr = cand.raw.get("address", {})
        if addr.get("country_code") == "it":
            chosen = cand
            break
    chosen = chosen or locs[0]

    addr = chosen.raw.get("address", {})
    country = addr.get("country")
    region = addr.get("state") or addr.get("region")
    province = addr.get("county") or addr.get("province")

    lat = chosen.latitude
    lon = chosen.longitude

    result = (province, region, country, lat, lon)
    _geocode_cache[cache_key] = result
    return result

# Processing steps
def fill_missing_geo_by_reverse(rows):
    
    to_process = []
    for row in rows:
        city = get_text(row, "city")
        province = get_text(row, "province")
        region = get_text(row, "region")
        country = get_text(row, "country")
        lat = get_text(row, "latitude")
        lon = get_text(row, "longitude")

        missing_geo = any(is_empty(x) for x in (city, province, region, country))
        has_coords = (not is_empty(lat)) and (not is_empty(lon))

        if missing_geo and has_coords:
            to_process.append(row)

    if DEBUG:
        print("Rows to reverse-geocode:", len(to_process))

    for row in to_process:
        id_author = get_text(row, "id_author")
        name = get_text(row, "name")

        try:
            lat = float(get_text(row, "latitude"))
            lon = float(get_text(row, "longitude"))
        except ValueError:
            if DEBUG:
                print(f"[WARN] {id_author} {name}: invalid coords")
            continue

        city_new, prov_new, reg_new, ctry_new = reverse_fill(lat, lon)

        # fill ONLY missing values
        if is_empty(get_text(row, "city")) and city_new:
            set_text(row, "city", city_new)
        if is_empty(get_text(row, "province")) and prov_new:
            set_text(row, "province", prov_new)
        if is_empty(get_text(row, "region")) and reg_new:
            set_text(row, "region", reg_new)
        if is_empty(get_text(row, "country")) and ctry_new:
            set_text(row, "country", ctry_new)

        if DEBUG:
            print(f"Reverse: {id_author} | {name} → {city_new}, {prov_new}, {reg_new}, {ctry_new}")

def fill_birth_fields_and_backfill_geo_for_italy(rows, h3_res=8):
    updated_rows = 0

    for row in rows:
        birth_place = get_text(row, "birth_place")
        if is_empty(birth_place):
            continue

        birth_place = normalize_text(birth_place, CITY_NORMALIZATION)
        birth_place = birth_place.strip()

        prov_new, reg_new, ctry_new, lat_new, lon_new = geocode_birth_place(birth_place)

        # City-states / countries without region/province: fallback to country
        if prov_new is None and ctry_new is not None:
            prov_new = ctry_new
        if reg_new is None and ctry_new is not None:
            reg_new = ctry_new

        prov_new = normalize_text(prov_new, PROVINCE_NORMALIZATION)
        reg_new = normalize_text(reg_new, REGION_NORMALIZATION)

       
        set_text(row, "birth_country", ctry_new)
        set_text(row, "birth_region", reg_new)
        set_text(row, "birth_province", prov_new)
        set_text(row, "birth_latitude", lat_new)
        set_text(row, "birth_longitude", lon_new)

        # birth_h3
        birth_h3 = None
        if lat_new is not None and lon_new is not None:
            try:
                birth_h3 = h3_from_latlon(float(lat_new), float(lon_new), resolution=h3_res)
            except (TypeError, ValueError):
                birth_h3 = None
        set_text(row, "birth_h3", birth_h3)

        if DEBUG:
            print(
                f"id_author={get_text(row,'id_author')}, name={get_text(row,'name')}, "
                f"birth_place={birth_place}, birth_province={prov_new}, birth_region={reg_new}, "
                f"birth_country={ctry_new}, birth_lat={lat_new}, birth_lon={lon_new}"
            )

        # Only backfill main geo fields for Italian birthplaces
        if ctry_new is None or ctry_new.strip().lower() != "italia":
            continue

        changed = False

        if is_empty(get_text(row, "city")) and birth_place:
            set_text(row, "city", birth_place); changed = True
        if is_empty(get_text(row, "province")) and prov_new:
            set_text(row, "province", prov_new); changed = True
        if is_empty(get_text(row, "region")) and reg_new:
            set_text(row, "region", reg_new); changed = True
        if is_empty(get_text(row, "country")) and ctry_new:
            set_text(row, "country", ctry_new); changed = True
        if is_empty(get_text(row, "latitude")) and lat_new is not None:
            set_text(row, "latitude", lat_new); changed = True
        if is_empty(get_text(row, "longitude")) and lon_new is not None:
            set_text(row, "longitude", lon_new); changed = True

        if changed:
            updated_rows += 1

    if DEBUG:
        print("Rows where some geo field was filled:", updated_rows)

# create h3 code from lat/lon
def add_h3_to_rows(rows, lat_tag="latitude", lon_tag="longitude", out_tag="h3", res=8):
    for row in rows:
        lat_text = get_text(row, lat_tag)
        lon_text = get_text(row, lon_tag)
        if is_empty(lat_text) or is_empty(lon_text):
            continue

        try:
            lat = float(lat_text)
            lon = float(lon_text)
        except ValueError:
            continue

        try:
            h3_code = h3_from_latlon(lat, lon, resolution=res)
        except Exception:
            h3_code = ""

        set_text(row, out_tag, h3_code)

# derive active_start from description
def fill_active_start_from_description(rows):
    filled = 0
    remaining_empty = 0

    for row in rows:
        desc = get_text(row, "description")
        active_start = get_text(row, "active_start")

        if active_start != "":
            continue

        m = YEAR_PATTERN.search(desc) if desc else None
        if m:
            year = m.group(1)
            set_text(row, "active_start", f"{year}-01-01")
            filled += 1

    for row in rows:
        if get_text(row, "active_start") == "":
            remaining_empty += 1

    if DEBUG:
        print("Rows filled with extracted year:", filled)
        print("Remaining <active_start> empty:", remaining_empty)

# derive groups from description
def fill_is_group(rows):
    for row in rows:
        desc = get_text(row, "description")
        flag = "yes" if desc and GROUP_PATTERN.search(desc) else "no"
        set_text(row, "is_group", flag)

# derive nationality from description
def nationality_from_description(desc: str):
    if is_empty(desc):
        return None
    text = desc.lower()

    if ITALIAN_WORD_PATTERN.search(text):
        return "Italia"

    m = ITALO_MIXED_PATTERN.search(text)
    if m:
        other = m.group(1)
        mapping = {"argentino": "Argentina", "tunisino": "Tunisia"}
        other_nat = mapping.get(other, other.capitalize())
        return f"Italia / {other_nat}"

    if "argentino" in text:
        return "Argentina"
    if "tunisino" in text:
        return "Tunisia"

    return None

def fill_missing_nationality(rows):
    updated = 0
    for row in rows:
        nat = get_text(row, "nationality")
        if not is_empty(nat):
            continue
        desc = get_text(row, "description")
        inferred = nationality_from_description(desc)
        if inferred:
            set_text(row, "nationality", inferred)
            updated += 1
    if DEBUG:
        print("Nationality filled for:", updated, "rows")


def main():
    tree = ET.parse(INPUT_XML)
    root = tree.getroot()
    rows = root.findall(".//row")

    if DEBUG:
        print("Total <row> elements:", len(rows))

    fill_missing_geo_by_reverse(rows)

    fill_birth_fields_and_backfill_geo_for_italy(rows, h3_res=8)

    add_h3_to_rows(rows, res=8)

    fill_active_start_from_description(rows)

    fill_is_group(rows)

    fill_missing_nationality(rows)


    ET.indent(tree, space="  ", level=0)  
    tree.write(OUTPUT_XML, encoding="utf-8", xml_declaration=True)
    print("Saved:", OUTPUT_XML)

if __name__ == "__main__":
    main()
