import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import requests


# Config

FILE = "artists.xml"

WIKI_LANG = ["it", "en"]

HEADERS = {
    "User-Agent": "LDS/1.0 (t.do1@studenti.unipi.it)"
}

TARGET_NAMES = [
    'alfa', 'anna pepe', 'beba', 'brusco', 'bushwaka', 'caneda',
    'club dogo', 'colle der fomento', "dargen d_amico", 'doll kill',
    'eva rea', 'guè pequeno', 'hindaco', 'joey funboy', 'johnny marsiglia',
    'mike24', 'miss keta', 'miss simpatia', 'mistico', 'nerone', 'o zulù',
    'samuel heron', 'skioffi', 'sottotono', 'yeиdry', '99 posse',
    'articolo 31', 'bigmama', 'cor veleno', 'dark polo gang', 'priestess',
    'shiva'
]

WIKI_TITLES = {
    "alfa": "Alfa (cantante)",
    "anna pepe": "Anna (rapper)",
    "brusco": "Brusco",
    "caneda": "Caneda",
    "club dogo": "Club Dogo",
    "colle der fomento": "Colle der Fomento",
    "dargen d_amico": "Dargen D'Amico",
    "guè piccolo": "Guè",
    "guè pequeno": "Guè",
    "johnny marsiglia": "Johnny Marsiglia",
    "miss keta": "Myss Keta",
    "nerone": "Nerone (rapper)",
    "o zulù": "'O Zulù",
    "sottotono": "Sottotono",
    "yeиdry": "Yendry",
    "99 posse": "99 Posse",
    "articolo 31": "Articolo 31",
    "bigmama": "BigMama",
    "cor veleno": "Cor Veleno",
    "dark polo gang": "Dark Polo Gang",
    "priestess": "Priestess (rapper)",
    "shiva": "Shiva (rapper)",
}


# XML helpers
def load_artists_xml(file_path: str):
    tree = ET.parse(file_path)
    root = tree.getroot()
    artists = list(root.findall("./*"))
    return tree, root, artists


def get_field(elem: ET.Element, tag: str) -> Optional[str]:
    child = elem.find(tag)
    if child is None or child.text is None:
        return None
    txt = child.text.strip()
    return txt if txt != "" else None


def set_field(elem: ET.Element, tag: str, value: Optional[str]) -> None:
    if value is None:
        return
    child = elem.find(tag)
    if child is None:
        child = ET.SubElement(elem, tag)
    child.text = str(value)


def ensure_field(elem: ET.Element, tag: str) -> ET.Element:
    child = elem.find(tag)
    if child is None:
        child = ET.SubElement(elem, tag)
        child.text = ""
    return child


def build_artist_index(artists: List[ET.Element]) -> Dict[str, ET.Element]:
    """Map lowercase artist name -> XML element (O(1) lookup)."""
    idx: Dict[str, ET.Element] = {}
    for a in artists:
        name = get_field(a, "name")
        if name:
            idx[name.lower()] = a
    return idx


# Wiki client (session + caches)
@dataclass
class WikiClient:
    session: requests.Session
    headers: Dict[str, str]
    preferred_langs: List[str]

    # simple in-memory caches
    _label_cache: Dict[Tuple[str, Tuple[str, ...]], Optional[str]] = None
    _entity_cache: Dict[str, Dict[str, Any]] = None
    _pageprops_cache: Dict[Tuple[int, str], Tuple[Optional[str], Optional[str]]] = None

    def __post_init__(self):
        self._label_cache = {}
        self._entity_cache = {}
        self._pageprops_cache = {}

    def wiki_search(self, title: str, langs: List[str]) -> Tuple[Optional[int], Optional[str], Optional[str]]:
        """Search Wikipedia and return (pageid, found_title, lang_used)."""
        for lang in langs:
            url = f"https://{lang}.wikipedia.org/w/api.php"
            params = {
                "action": "query",
                "list": "search",
                "srsearch": title,
                "format": "json",
                "srlimit": 1,
            }
            try:
                r = self.session.get(url, params=params, headers=self.headers, timeout=10)
                r.raise_for_status()
                data = r.json()
            except requests.RequestException as e:
                print(f"  [wiki_search] HTTP error ({lang}): {e}")
                continue

            hits = data.get("query", {}).get("search", [])
            if hits:
                return hits[0]["pageid"], hits[0]["title"], lang

        return None, None, None

    def wiki_get_page_by_title(self, title: str, lang: str) -> Tuple[Optional[int], Optional[str], str]:
        """Get a Wikipedia page by exact title: (pageid, title, lang)."""
        url = f"https://{lang}.wikipedia.org/w/api.php"
        params = {"action": "query", "titles": title, "format": "json"}
        try:
            r = self.session.get(url, params=params, headers=self.headers, timeout=10)
            r.raise_for_status()
            data = r.json()
        except requests.RequestException as e:
            print(f"  [wiki_get_page_by_title] HTTP error ({lang}): {e}")
            return None, None, lang

        pages = data.get("query", {}).get("pages", {})
        if not pages:
            return None, None, lang

        page = list(pages.values())[0]
        if "missing" in page:
            return None, None, lang

        return page.get("pageid"), page.get("title"), lang

    def wiki_pageprops(self, pageid: int, lang: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Given a pageid, return (summary_extract, wikidata_qid).
        Cached by (pageid, lang).
        """
        key = (pageid, lang)
        if key in self._pageprops_cache:
            return self._pageprops_cache[key]

        url = f"https://{lang}.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "pageids": pageid,
            "prop": "extracts|pageprops",
            "exintro": True,
            "explaintext": True,
            "format": "json",
        }
        r = self.session.get(url, params=params, headers=self.headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        page = list(data["query"]["pages"].values())[0]
        summary = page.get("extract")
        qid = page.get("pageprops", {}).get("wikibase_item")
        self._pageprops_cache[key] = (summary, qid)
        return summary, qid

    def wikidata_get_label(self, qid: str, langs: List[str]) -> Optional[str]:
        """Return label for a QID in the first available language from langs (cached)."""
        if not qid:
            return None
        key = (qid, tuple(langs))
        if key in self._label_cache:
            return self._label_cache[key]

        url = "https://www.wikidata.org/w/api.php"
        params = {
            "action": "wbgetentities",
            "ids": qid,
            "format": "json",
            "languages": "|".join(langs),
        }
        r = self.session.get(url, params=params, headers=self.headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        ent = data["entities"].get(qid, {})
        labels = ent.get("labels", {})

        out = None
        for lg in langs:
            if lg in labels:
                out = labels[lg]["value"]
                break

        self._label_cache[key] = out
        return out

    def wikidata_entity(self, qid: str) -> Dict[str, Any]:
        """Fetch Wikidata entity JSON (cached)."""
        if qid in self._entity_cache:
            return self._entity_cache[qid]
        url = f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
        r = self.session.get(url, headers=self.headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        self._entity_cache[qid] = data
        return data

    @staticmethod
    def _get_claim_date(claims: Dict[str, Any], pid: str) -> Optional[str]:
        """Extract YYYY-MM-DD; ignore dates with 00 month/day."""
        if pid not in claims:
            return None
        try:
            v = claims[pid][0]["mainsnak"]["datavalue"]["value"]
            iso = v["time"]        # +YYYY-MM-DDT...
            date_str = iso[1:11]   # YYYY-MM-DD
            if date_str[5:7] == "00" or date_str[8:10] == "00":
                return None
            return date_str
        except Exception:
            return None

    def _get_claim_item_label(self, claims: Dict[str, Any], pid: str) -> Optional[str]:
        """Resolve linked item QID -> label using preferred langs."""
        if pid not in claims:
            return None
        try:
            snak = claims[pid][0]["mainsnak"]["datavalue"]["value"]
            target_qid = snak["id"]
            return self.wikidata_get_label(target_qid, self.preferred_langs)
        except Exception:
            return None

    def wikidata_fetch(self, qid: str) -> Dict[str, Optional[str]]:
        """
        Extract person-like and group-like fields + description in preferred languages.
        """
        data = self.wikidata_entity(qid)
        entity = data["entities"][qid]
        claims = entity.get("claims", {})

        birth_date = self._get_claim_date(claims, "P569")
        birth_place = self._get_claim_item_label(claims, "P19")
        nationality = self._get_claim_item_label(claims, "P27")
        active_start = self._get_claim_date(claims, "P2031")
        active_end = self._get_claim_date(claims, "P2032")

        formation_date = self._get_claim_date(claims, "P571")
        formation_place = self._get_claim_item_label(claims, "P740")
        origin_country = self._get_claim_item_label(claims, "P495")

        desc_val = None
        descriptions = entity.get("descriptions", {})
        for lg in self.preferred_langs:
            if lg in descriptions:
                desc_val = descriptions[lg]["value"]
                break

        return {
            "birth_date": birth_date,
            "birth_place": birth_place,
            "nationality": nationality,
            "active_start": active_start,
            "active_end": active_end,
            "formation_date": formation_date,
            "formation_place": formation_place,
            "origin_country": origin_country,
            "wd_description": desc_val,
        }


def fetch_background_from_wiki(client: WikiClient, artist_name: str) -> Dict[str, Optional[str]]:
    """
    Wikipedia(it/en) + Wikidata info for an artist name.
    - Try forced exact title if present
    - Otherwise search
    """
    key = artist_name.lower()
    base_title = WIKI_TITLES.get(key, artist_name)

    pageid = None
    found_title = None
    lang_used = None

    # 1) Forced exact title (it/en)
    if key in WIKI_TITLES:
        for lang_try in ["it", "en"]:
            pid, t_found, _ = client.wiki_get_page_by_title(base_title, lang_try)
            if pid is not None:
                pageid, found_title, lang_used = pid, t_found, lang_try
                break

    # 2) Search fallback (it/en)
    if pageid is None:
        pageid, found_title, lang_used = client.wiki_search(base_title, langs=["it", "en"])

    if pageid is None:
        print(f"  No page found for '{artist_name}' (it/en)")
        return {}

    print(f"  → Wikipedia page: {found_title} (pageid={pageid}, lang={lang_used})")

    summary, qid = client.wiki_pageprops(pageid, lang_used)
    info: Dict[str, Optional[str]] = {"description": summary}

    if qid:
        wd = client.wikidata_fetch(qid)
        info.update({
            "birth_date": wd["birth_date"],
            "birth_place": wd["birth_place"],
            "nationality": wd["nationality"],
            "active_start": wd["active_start"],
            "active_end": wd["active_end"],
            "formation_date": wd["formation_date"],
            "formation_place": wd["formation_place"],
            "origin_country": wd["origin_country"],
        })

    return info

# Post-processing cleaning
def apply_cleaning_rules(artists: List[ET.Element]) -> None:
    wrong_names = [
        "beba", "doll kill", "eva rea", "hindaco", "joey funboy",
        "miss simpatia", "samuel heron", "skioffi", "mistico", "bushwaka",
    ]

    cols_to_clear = [
        "birth_date", "birth_place", "nationality", "active_start", "active_end",
        "description", "country",
    ]

    wrong_set = {n.lower() for n in wrong_names}

    for artist in artists:
        name_val = get_field(artist, "name")
        if name_val and name_val.lower() in wrong_set:
            for col in cols_to_clear:
                set_field(artist, col, "")

    # Clean dates like YYYY-00-00
    for artist in artists:
        for col in ["birth_date", "active_start", "active_end"]:
            v = get_field(artist, col)
            if v and "-00-" in v:
                set_field(artist, col, "")

    # Special case: Myss Keta
    for artist in artists:
        name_val = get_field(artist, "name")
        if name_val and name_val.lower() in ["miss keta", "myss keta"]:
            set_field(artist, "birth_date", "")

    # Numeric coords if present
    for artist in artists:
        for col in ["latitude", "longitude"]:
            v = get_field(artist, col)
            if v:
                try:
                    set_field(artist, col, str(float(v)))
                except ValueError:
                    set_field(artist, col, "")

    # Fill country if nationality contains "ital"
    for artist in artists:
        nat = (get_field(artist, "nationality") or "").lower()
        country = get_field(artist, "country")
        if "ital" in nat and not country:
            set_field(artist, "country", "Italia")


def main(in_file: str = FILE, out_file: str = "artists_enriched.xml") -> None:
    tree, root, artists = load_artists_xml(in_file)

    # Ensure description exists everywhere 
    for artist in artists:
        ensure_field(artist, "description")

    artist_index = build_artist_index(artists)

    with requests.Session() as session:
        client = WikiClient(session=session, headers=HEADERS, preferred_langs=WIKI_LANG)

        group_mapping = {
            "formation_date": "birth_date",
            "formation_place": "birth_place",
            "origin_country": "country",
        }

        for name in TARGET_NAMES:
            artist_elem = artist_index.get(name.lower())
            if artist_elem is None:
                print(f"Artist '{name}' not found in XML.")
                continue

            id_author = get_field(artist_elem, "id_author")
            print(f"\n=== Fetching data for: {name} (id_author={id_author}) ===")

            try:
                info = fetch_background_from_wiki(client, name)
            except requests.HTTPError as e:
                print(f"  HTTP error: {e}")
                continue
            except Exception as e:
                print(f"  Generic error: {e}")
                continue

            if not info:
                continue
 
            for col, val in info.items():
                if val is None:
                    continue

                if col == "description":
                    set_field(artist_elem, "description", val)  
                    print("  -> updated description")
                    continue

                if col in group_mapping:
                    target_col = group_mapping[col]
                    current_val = get_field(artist_elem, target_col)
                    if not current_val:
                        set_field(artist_elem, target_col, val)
                        print(f"  -> updated {target_col} = {val}")
                    continue

                current_val = get_field(artist_elem, col)
                if not current_val:
                    set_field(artist_elem, col, val)
                    print(f"  -> updated {col} = {val}")

            time.sleep(0.5) 

    apply_cleaning_rules(artists)

    tree.write(out_file, encoding="utf-8", xml_declaration=True)
    print(f"\n✅ Saved final cleaned file back to: {out_file}")


if __name__ == "__main__":
    main()
