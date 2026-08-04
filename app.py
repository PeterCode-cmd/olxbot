"""
OLX Mieszkania – Streamlit Dashboard
Podgląd wszystkich znalezionych ogłoszeń z możliwością oceniania.
"""

import json
import re
from pathlib import Path
from datetime import datetime, timezone

import streamlit as st
import requests
import config

# ─── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="🏠 OLX Mieszkania",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Dark background */
.stApp {
    background: #0f1117;
}

/* Card container */
.listing-card {
    background: linear-gradient(135deg, #1a1d2e 0%, #16192b 100%);
    border: 1px solid rgba(99, 102, 241, 0.2);
    border-radius: 16px;
    padding: 0;
    margin-bottom: 24px;
    overflow: hidden;
    transition: border-color 0.3s ease, box-shadow 0.3s ease;
}
.listing-card:hover {
    border-color: rgba(99, 102, 241, 0.5);
    box-shadow: 0 8px 32px rgba(99, 102, 241, 0.15);
}

/* Status badges */
.badge-new {
    background: rgba(99, 102, 241, 0.2);
    color: #a5b4fc;
    border: 1px solid rgba(99, 102, 241, 0.4);
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
}
.badge-liked {
    background: rgba(16, 185, 129, 0.2);
    color: #6ee7b7;
    border: 1px solid rgba(16, 185, 129, 0.4);
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
}
.badge-disliked {
    background: rgba(239, 68, 68, 0.2);
    color: #fca5a5;
    border: 1px solid rgba(239, 68, 68, 0.4);
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
}

/* Price box */
.price-box {
    background: rgba(99, 102, 241, 0.1);
    border: 1px solid rgba(99, 102, 241, 0.3);
    border-radius: 12px;
    padding: 12px 16px;
    margin: 8px 0;
}
.price-total {
    font-size: 22px;
    font-weight: 700;
    color: #a5b4fc;
}
.price-breakdown {
    font-size: 12px;
    color: #6b7280;
    margin-top: 2px;
}

/* Info pills */
.info-pill {
    display: inline-block;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 4px 10px;
    font-size: 12px;
    color: #9ca3af;
    margin: 2px;
}

/* Section header */
.section-header {
    color: #e5e7eb;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    margin: 12px 0 6px 0;
    color: #6b7280;
}

/* Description box */
.desc-box {
    background: rgba(0,0,0,0.3);
    border-left: 3px solid rgba(99, 102, 241, 0.5);
    border-radius: 0 8px 8px 0;
    padding: 12px 16px;
    font-size: 13px;
    color: #9ca3af;
    line-height: 1.7;
    max-height: 200px;
    overflow-y: auto;
}

/* Sidebar stats */
.stat-card {
    background: rgba(99, 102, 241, 0.1);
    border: 1px solid rgba(99, 102, 241, 0.2);
    border-radius: 12px;
    padding: 16px;
    text-align: center;
    margin-bottom: 8px;
}
.stat-value {
    font-size: 28px;
    font-weight: 700;
    color: #a5b4fc;
}
.stat-label {
    font-size: 12px;
    color: #6b7280;
    margin-top: 2px;
}

/* Header */
.main-header {
    background: linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #1e1b4b 100%);
    border-bottom: 1px solid rgba(99, 102, 241, 0.3);
    padding: 20px 0 12px 0;
    margin-bottom: 24px;
    border-radius: 16px;
    text-align: center;
}

/* Buttons */
div.stButton > button {
    border-radius: 8px;
    font-weight: 600;
    font-size: 13px;
    transition: all 0.2s;
    border: none;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: rgba(255,255,255,0.03); }
::-webkit-scrollbar-thumb { background: rgba(99,102,241,0.4); border-radius: 3px; }

/* Lazy loading images */
img { loading: lazy; }
</style>
""", unsafe_allow_html=True)

# ─── Data helpers ─────────────────────────────────────────────────────────────
LISTINGS_FILE = Path(__file__).parent / "listings.json"


@st.cache_data(ttl=300)  # Cache na 5 minut
def load_listings_from_github() -> dict | None:
    """Pobiera listings.json z GitHub API jeśli skonfigurowane."""
    github_token = config.GITHUB_TOKEN
    github_repo = config.GITHUB_REPO
    
    if not github_token or not github_repo:
        return None
    
    try:
        url = f"https://api.github.com/repos/{github_repo}/contents/listings.json"
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("encoding") == "base64":
                import base64
                content = base64.b64decode(data["content"]).decode("utf-8")
                return json.loads(content)
        return None
    except Exception as e:
        st.warning(f"Błąd pobierania z GitHub: {e}")
        return None


@st.cache_data(ttl=300)  # Cache na 5 minut
def load_listings() -> dict:
    # Najpierw spróbuj pobrać z GitHub
    github_data = load_listings_from_github()
    if github_data:
        return github_data
    
    # Fallback na lokalny plik
    if LISTINGS_FILE.exists():
        try:
            return json.loads(LISTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_listings_to_github(records: dict) -> bool:
    """Zapisuje zmiany do GitHub API jeśli skonfigurowane."""
    github_token = config.GITHUB_TOKEN
    github_repo = config.GITHUB_REPO
    
    if not github_token or not github_repo:
        return False
    
    try:
        # Najpierw pobierz aktualny sha
        url = f"https://api.github.com/repos/{github_repo}/contents/listings.json"
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        sha = None
        if response.status_code == 200:
            sha = response.json().get("sha")
        
        # Przygotuj content
        import base64
        content = base64.b64encode(
            json.dumps(records, ensure_ascii=False, indent=2).encode("utf-8")
        ).decode("utf-8")
        
        # Wyślij aktualizację
        data = {
            "message": f"Update listings from Streamlit {datetime.now().isoformat()}",
            "content": content,
        }
        if sha:
            data["sha"] = sha
        
        response = requests.put(url, headers=headers, json=data, timeout=10)
        return response.status_code in [200, 201]
    except Exception as e:
        st.warning(f"Błąd zapisu do GitHub: {e}")
        return False


def save_listings(records: dict) -> None:
    # Zapisz lokalnie (fallback)
    try:
        LISTINGS_FILE.write_text(
            json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as e:
        st.warning(f"Error saving locally: {e}")
    
    # Zapisz do GitHub jeśli skonfigurowane
    success = save_listings_to_github(records)
    if not success:
        st.warning("Failed to save to GitHub - check GITHUB_TOKEN and GITHUB_REPO in secrets")


def get_param(params: list, key: str) -> str:
    for p in params:
        if p.get("key") == key:
            val = p.get("value", {})
            return val.get("label", "") if isinstance(val, dict) else ""
    return ""


def parse_area(label: str) -> int | None:
    if not label:
        return None
    match = re.search(r"(\d+)(?:[\.,]?\d*)", label.replace("m²", "").replace("m2", ""))
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def get_photos(listing: dict) -> list[str]:
    """Zwraca wszystkie zdjęcia w optymalnej rozdzielczości."""
    urls = []
    for photo in listing.get("photos", []):
        link = photo.get("link", "")
        if link:
            urls.append(link.replace("{width}", "800").replace("{height}", "600"))
    return urls


def clean_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fmt_price(val: float) -> str:
    return f"{val:,.0f} zł".replace(",", " ")


def format_date(iso: str) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return iso[:10]


# ─── Status actions ───────────────────────────────────────────────────────────
def set_status(lid: str, status: str) -> None:
    records = load_listings()
    if lid in records:
        records[lid]["status"] = status
        save_listings(records)
        # Clear cache to force reload
        st.cache_data.clear()
        st.success(f"Status updated to {status}")
        st.rerun()


def set_notes(lid: str, notes: str) -> None:
    records = load_listings()
    if lid in records:
        records[lid]["notes"] = notes
        save_listings(records)
        # Clear cache to force reload
        st.cache_data.clear()
        st.success("Notes saved")
        st.rerun()


# ─── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏠 OLX Mieszkania")
    st.markdown("---")

    all_records = load_listings()
    listings_list = list(all_records.values())

    total      = len(listings_list)
    liked      = sum(1 for l in listings_list if l.get("status") == "liked")
    disliked   = sum(1 for l in listings_list if l.get("status") == "disliked")
    new_count  = sum(1 for l in listings_list if l.get("status") == "new")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-value">{total}</div>
            <div class="stat-label">Wszystkich</div>
        </div>""", unsafe_allow_html=True)
        st.markdown(f"""
        <div class="stat-card" style="background:rgba(16,185,129,0.1);border-color:rgba(16,185,129,0.3)">
            <div class="stat-value" style="color:#6ee7b7">{liked}</div>
            <div class="stat-label">❤️ Polubionych</div>
        </div>""", unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="stat-card" style="background:rgba(251,191,36,0.1);border-color:rgba(251,191,36,0.3)">
            <div class="stat-value" style="color:#fcd34d">{new_count}</div>
            <div class="stat-label">🆕 Nowych</div>
        </div>""", unsafe_allow_html=True)
        st.markdown(f"""
        <div class="stat-card" style="background:rgba(239,68,68,0.1);border-color:rgba(239,68,68,0.3)">
            <div class="stat-value" style="color:#fca5a5">{disliked}</div>
            <div class="stat-label">👎 Odrzuconych</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 🔍 Filtry")

    # Status filter
    status_filter = st.multiselect(
        "Status",
        options=["new", "liked", "disliked"],
        default=["new", "liked"],
        format_func=lambda x: {"new": "🆕 Nowe", "liked": "❤️ Polubione", "disliked": "👎 Odrzucone"}[x],
    )

    # District filter - tylko jeśli jest dużo danych
    if len(listings_list) > 50:
        districts = sorted(set(l.get("district_name", "—") for l in listings_list if l.get("district_name")))
        district_filter = st.multiselect("Dzielnica", options=districts, default=[])
    else:
        district_filter = []

    # Area filter
    areas = [parse_area(get_param(l.get("params", []), "m")) for l in listings_list]
    area_values = [a for a in areas if a is not None]
    min_area, max_area = (min(area_values), max(area_values)) if area_values else (0, 100)
    area_range = st.slider("Powierzchnia (m²)", min_area, max_area, (min_area, max_area), step=1)

    # Rooms filter - tylko jeśli jest dużo danych
    if len(listings_list) > 50:
        room_options = sorted({get_param(l.get("params", []), "rooms") for l in listings_list if get_param(l.get("params", []), "rooms")})
        room_options = [r for r in room_options if r]
        rooms_filter = st.multiselect("Pokoje", options=room_options, default=room_options)
    else:
        rooms_filter = []

    # Price filter
    prices = [l.get("total_price", 0) for l in listings_list if l.get("total_price")]
    min_p, max_p = (int(min(prices)), int(max(prices))) if prices else (0, 5000)
    price_range = st.slider("Łączna cena (zł)", min_p, max_p, (min_p, max_p), step=50)

    # Sort
    sort_by = st.selectbox(
        "Sortuj wg",
        ["Cena rosnąco", "Cena malejąco", "Najnowsze", "Najstarsze"],
    )

    st.markdown("---")
    if st.button("🔄 Odśwież dane", use_container_width=True):
        st.rerun()
        st.cache_data.clear()

# ─── Filter & sort ────────────────────────────────────────────────────────────
records = load_listings()
listings_all = list(records.values())

filtered = [
    l for l in listings_all
    if (not status_filter or l.get("status", "new") in status_filter)
    and (not district_filter or l.get("district_name") in district_filter)
    and price_range[0] <= l.get("total_price", 0) <= price_range[1]
    and (not rooms_filter or get_param(l.get("params", []), "rooms") in rooms_filter)
    and area_range[0] <= (parse_area(get_param(l.get("params", []), "m")) or 0) <= area_range[1]
]

if sort_by == "Cena rosnąco":
    filtered.sort(key=lambda x: x.get("total_price", 0))
elif sort_by == "Cena malejąco":
    filtered.sort(key=lambda x: x.get("total_price", 0), reverse=True)
elif sort_by == "Najnowsze":
    filtered.sort(key=lambda x: x.get("last_refresh_time", ""), reverse=True)
else:
    filtered.sort(key=lambda x: x.get("last_refresh_time", ""))

# ─── Header ───────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="main-header">
    <h1 style="color:#a5b4fc;margin:0;font-size:28px;font-weight:700">🏠 OLX Mieszkania Dashboard</h1>
    <p style="color:#6b7280;margin:6px 0 0 0;font-size:14px">
        Znaleziono <b style="color:#a5b4fc">{len(filtered)}</b> ogłoszeń (z {total} łącznie)
    </p>
</div>
""", unsafe_allow_html=True)

if not filtered:
    st.info("😔 Brak ogłoszeń pasujących do filtrów. Zmień kryteria lub uruchom bota żeby pobrać nowe oferty.")
    st.stop()

# ─── Dynamic loading ──────────────────────────────────────────────────────────
# Inicjalizuj session_state
if "items_shown" not in st.session_state:
    st.session_state.items_shown = 10

ITEMS_PER_LOAD = 10
total_items = len(filtered)

# Pokaż przycisk reset jeśli zmieniono filtry
if "last_filter_hash" not in st.session_state:
    st.session_state.last_filter_hash = hash(str(filtered))

current_filter_hash = hash(str(filtered))
if current_filter_hash != st.session_state.last_filter_hash:
    st.session_state.items_shown = 10
    st.session_state.last_filter_hash = current_filter_hash

# Pokaż aktualną ilość
items_to_show = min(st.session_state.items_shown, total_items)
display_listings = filtered[:items_to_show]

st.markdown(f"<small>Pokazuję {items_to_show} z {total_items} ogłoszeń</small>", unsafe_allow_html=True)

# ─── Listings ─────────────────────────────────────────────────────────────────
for listing in display_listings:
    lid        = listing["id"]
    title      = listing.get("title", "Brak tytułu")
    url        = listing.get("url", "#")
    status     = listing.get("status", "new")
    district   = listing.get("district_name", "—")
    rent_price = listing.get("rent_price", 0)
    admin_rent = listing.get("admin_rent", 0)
    total_price = listing.get("total_price", 0)
    params     = listing.get("params", [])
    photos     = get_photos(listing)
    desc       = clean_html(listing.get("description", ""))
    contact    = listing.get("contact", {})
    found_at   = format_date(listing.get("found_at", ""))
    created    = format_date(listing.get("last_refresh_time", ""))

    # Params
    area      = get_param(params, "m")
    rooms     = get_param(params, "rooms")
    floor     = get_param(params, "floor_select")
    furniture = get_param(params, "furniture")
    elevator  = get_param(params, "winda")
    pets      = get_param(params, "pets")
    builttype = get_param(params, "builttype")

    # Status badge
    badge_html = {
        "new":      '<span class="badge-new">🆕 Nowe</span>',
        "liked":    '<span class="badge-liked">❤️ Polubione</span>',
        "disliked": '<span class="badge-disliked">👎 Odrzucone</span>',
    }.get(status, "")

    # Card border color
    border_colors = {
        "liked": "rgba(16, 185, 129, 0.4)",
        "disliked": "rgba(239, 68, 68, 0.3)",
        "new": "rgba(99, 102, 241, 0.2)",
    }
    border_col = border_colors.get(status, "rgba(99, 102, 241, 0.2)")

    with st.container():
        st.markdown(f'<div style="border:1px solid {border_col};border-radius:16px;padding:20px;margin-bottom:20px;background:linear-gradient(135deg,#1a1d2e,#16192b)">', unsafe_allow_html=True)

        # ── Header row ────────────────────────────────────────────────────────
        ai_data = listing.get("ai_analysis", {})
        ai_total_price = ai_data.get("ai_total_price")

        hcol1, hcol2 = st.columns([2, 2])
        with hcol1:
            st.markdown(
                f'<div style="margin-bottom:6px">{badge_html}<span style="color:#6b7280;font-size:12px;margin-left:8px">📍 {district} · 📅 Dodane: {created}</span></div>'
                f'<h3 style="color:#e5e7eb;margin:0 0 4px 0;font-size:17px;line-height:1.4"><a href="{url}" target="_blank" style="color:#a5b4fc;text-decoration:none">{title}</a></h3>',
                unsafe_allow_html=True,
            )
        with hcol2:
            ai_price_html = ""
            if ai_total_price:
                ai_price_html = (
                    f'<div class="price-box" style="text-align:right;background:rgba(168,85,247,0.1);border-color:rgba(168,85,247,0.3);padding:12px 16px;border-radius:12px">'
                    f'<div style="font-size:11px;color:#c084fc;font-weight:600">🤖 Suma AI (z mediami)</div>'
                    f'<div class="price-total" style="color:#c084fc">{fmt_price(ai_total_price)}</div>'
                    f'<div class="price-breakdown">media/opłaty: ~{fmt_price(ai_data.get("media_cost", 200))}</div>'
                    f'</div>'
                )

            bot_price_html = (
                f'<div class="price-box" style="text-align:right;padding:12px 16px;border-radius:12px">'
                f'<div style="font-size:11px;color:#9ca3af;font-weight:600">🤖 Suma Bot</div>'
                f'<div class="price-total">{fmt_price(total_price)}</div>'
                f'<div class="price-breakdown">czynsz: {fmt_price(rent_price)} | admin: {fmt_price(admin_rent) if admin_rent else "—"}</div>'
                f'</div>'
            )

            st.markdown(
                f'<div style="display:flex;gap:10px;justify-content:flex-end">{bot_price_html}{ai_price_html}</div>',
                unsafe_allow_html=True,
            )

        st.markdown("<hr style='border-color:rgba(255,255,255,0.06);margin:12px 0'>", unsafe_allow_html=True)

        # ── Main content ──────────────────────────────────────────────────────
        img_col, info_col = st.columns([2, 3])

        with img_col:
            if photos:
                # Interaktywna galeria z podglądem i Lightboxem po kliknięciu
                photos_json = json.dumps(photos)
                gallery_id = f"gallery_{lid}"
                
                lightbox_html = f"""
                <div id="{gallery_id}" style="position:relative; width:100%; font-family:sans-serif;">
                    <div style="position:relative; width:100%; border-radius:12px; overflow:hidden; background:#000; cursor:pointer;" onclick="openLightbox_{lid}(currentIndex_{lid})">
                        <img id="main_img_{lid}" src="{photos[0]}" style="width:100%; height:260px; object-fit:cover; display:block; transition: transform 0.2s;" onmouseover="this.style.transform='scale(1.02)'" onmouseout="this.style.transform='scale(1)'"/>
                        <div style="position:absolute; bottom:10px; right:10px; background:rgba(0,0,0,0.7); color:#fff; padding:4px 10px; border-radius:12px; font-size:12px; backdrop-filter:blur(4px);">
                            🔍 Kliknij, aby powiększyć (<span id="counter_{lid}">1</span>/{len(photos)})
                        </div>
                    </div>

                    <!-- Miniatury -->
                    <div style="display:flex; gap:6px; margin-top:8px; overflow-x:auto; padding-bottom:4px;">
                        {''.join([f'<img src="{p}" onclick="setPhoto_{lid}({i})" style="width:50px; height:50px; object-fit:cover; border-radius:6px; cursor:pointer; opacity:{"1" if i==0 else "0.5"}; border:2px solid {"#6366f1" if i==0 else "transparent"};" id="thumb_{lid}_{i}"/>' for i, p in enumerate(photos)])}
                    </div>

                    <!-- Lightbox Modal -->
                    <div id="modal_{lid}" style="display:none; position:fixed; z-index:999999; left:0; top:0; width:100vw; height:100vh; background:rgba(0,0,0,0.95); backdrop-filter:blur(8px); flex-direction:column; align-items:center; justify-content:center;">
                        <button onclick="closeLightbox_{lid}()" style="position:absolute; top:20px; right:35px; background:rgba(255,255,255,0.2); border:none; color:#fff; font-size:40px; font-weight:bold; cursor:pointer; z-index:1000000; width:60px; height:60px; border-radius:50%; transition:0.2s;" onmouseover="this.style.background='rgba(255,255,255,0.3)'" onmouseout="this.style.background='rgba(255,255,255,0.2)'">✕</button>
                        
                        <button onclick="prevPhoto_{lid}()" style="position:absolute; left:20px; background:rgba(255,255,255,0.15); border:none; color:#fff; font-size:30px; padding:15px 20px; border-radius:50%; cursor:pointer; transition:0.2s;" onmouseover="this.style.background='rgba(255,255,255,0.3)'" onmouseout="this.style.background='rgba(255,255,255,0.15)'">❮</button>
                        
                        <img id="modal_img_{lid}" src="" style="max-width:90vw; max-height:85vh; border-radius:8px; box-shadow:0 10px 40px rgba(0,0,0,0.8); object-fit:contain;"/>
                        
                        <button onclick="nextPhoto_{lid}()" style="position:absolute; right:20px; background:rgba(255,255,255,0.15); border:none; color:#fff; font-size:30px; padding:15px 20px; border-radius:50%; cursor:pointer; transition:0.2s;" onmouseover="this.style.background='rgba(255,255,255,0.3)'" onmouseout="this.style.background='rgba(255,255,255,0.15)'">❯</button>
                        
                        <div id="modal_counter_{lid}" style="color:#aaa; font-size:14px; margin-top:15px;"></div>
                    </div>
                </div>

                <script>
                    (function() {{
                        const photos_{lid} = {photos_json};
                        window.currentIndex_{lid} = 0;

                        window.setPhoto_{lid} = function(index) {{
                            window.currentIndex_{lid} = index;
                            document.getElementById('main_img_{lid}').src = photos_{lid}[index];
                            document.getElementById('counter_{lid}').innerText = index + 1;
                            
                            photos_{lid}.forEach((_, i) => {{
                                const thumb = document.getElementById('thumb_{lid}_' + i);
                                if (thumb) {{
                                    thumb.style.opacity = (i === index) ? '1' : '0.5';
                                    thumb.style.borderColor = (i === index) ? '#6366f1' : 'transparent';
                                }}
                            }});
                        }};

                        window.openLightbox_{lid} = function(index) {{
                            window.currentIndex_{lid} = index;
                            document.getElementById('modal_img_{lid}').src = photos_{lid}[index];
                            document.getElementById('modal_counter_{lid}').innerText = (index + 1) + ' / ' + photos_{lid}.length;
                            document.getElementById('modal_{lid}').style.display = 'flex';
                            document.body.style.overflow = 'hidden';
                        }};

                        window.closeLightbox_{lid} = function() {{
                            document.getElementById('modal_{lid}').style.display = 'none';
                            document.body.style.overflow = 'auto';
                        }};

                        window.nextPhoto_{lid} = function() {{
                            window.currentIndex_{lid} = (window.currentIndex_{lid} + 1) % photos_{lid}.length;
                            document.getElementById('modal_img_{lid}').src = photos_{lid}[window.currentIndex_{lid}];
                            document.getElementById('modal_counter_{lid}').innerText = (window.currentIndex_{lid} + 1) + ' / ' + photos_{lid}.length;
                            setPhoto_{lid}(window.currentIndex_{lid});
                        }};

                        window.prevPhoto_{lid} = function() {{
                            window.currentIndex_{lid} = (window.currentIndex_{lid} - 1 + photos_{lid}.length) % photos_{lid}.length;
                            document.getElementById('modal_img_{lid}').src = photos_{lid}[window.currentIndex_{lid}];
                            document.getElementById('modal_counter_{lid}').innerText = (window.currentIndex_{lid} + 1) + ' / ' + photos_{lid}.length;
                            setPhoto_{lid}(window.currentIndex_{lid});
                        }};

                        document.addEventListener('keydown', function(e) {{
                            const modal = document.getElementById('modal_{lid}');
                            if (modal && modal.style.display === 'flex') {{
                                if (e.key === 'ArrowRight') nextPhoto_{lid}();
                                if (e.key === 'ArrowLeft') prevPhoto_{lid}();
                                if (e.key === 'Escape') closeLightbox_{lid}();
                            }}
                        }});
                    }})();
                </script>
                """
                st.components.v1.html(lightbox_html, height=340)
            else:
                st.markdown("""
                <div style="background:rgba(0,0,0,0.3);border-radius:12px;height:200px;
                            display:flex;align-items:center;justify-content:center;color:#4b5563">
                    🚫 Brak zdjęć
                </div>
                """, unsafe_allow_html=True)

        with info_col:
            # Pills z parametrami
            pills_html = ""
            if area:      pills_html += f'<span class="info-pill">📐 {area}</span>'
            if rooms:     pills_html += f'<span class="info-pill">🛏 {rooms}</span>'
            if floor:     pills_html += f'<span class="info-pill">🏗 piętro {floor}</span>'
            if furniture: pills_html += f'<span class="info-pill">🪑 {furniture}</span>'
            if elevator:  pills_html += f'<span class="info-pill">🛗 winda: {elevator}</span>'
            if pets:      pills_html += f'<span class="info-pill">🐾 zwierzęta: {pets}</span>'
            if builttype: pills_html += f'<span class="info-pill">🏢 {builttype}</span>'

            if contact.get("phone"):       pills_html += f'<span class="info-pill">📞 telefon</span>'
            if contact.get("chat"):        pills_html += f'<span class="info-pill">💬 czat OLX</span>'
            if contact.get("negotiation"): pills_html += f'<span class="info-pill">🤝 negocjacje</span>'

            st.markdown(f'<div style="margin-bottom:12px">{pills_html}</div>', unsafe_allow_html=True)

            # Box informacyjny od AI (Groq)
            if ai_data:
                ai_notes = ai_data.get("ai_notes", "")
                ai_deposit = ai_data.get("deposit", "Brak info")
                ai_lease = ai_data.get("lease_type", "Brak info")
                
                ai_box_html = (
                    f'<div style="background:linear-gradient(135deg, rgba(168,85,247,0.12) 0%, rgba(147,51,234,0.06) 100%);'
                    f'border:1px solid rgba(168,85,247,0.3); border-radius:12px; padding:14px 16px; margin-bottom:14px">'
                    f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px">'
                    f'<span style="font-weight:700; color:#c084fc; font-size:13px">🤖 Informacja od AI (Groq Llama 3.3 70B)</span>'
                    f'<span style="font-size:11px; color:#9ca3af">Kaucja: <b style="color:#e5e7eb">{ai_deposit}</b> | Umowa: <b style="color:#e5e7eb">{ai_lease}</b></span>'
                    f'</div>'
                    f'<div style="font-size:13px; color:#e9d5ff; line-height:1.5">{ai_notes}</div>'
                    f'</div>'
                )
                st.markdown(ai_box_html, unsafe_allow_html=True)

            # Opis
            if desc:
                with st.expander("📄 Pokaż opis ogłoszenia"):
                    st.markdown(f'<div class="desc-box">{desc[:800]}{"…" if len(desc)>800 else ""}</div>', unsafe_allow_html=True)

            # Notatki
            st.markdown('<div class="section-header" style="margin-top:12px">📝 Notatki</div>', unsafe_allow_html=True)
            notes_val = listing.get("notes", "")
            new_notes = st.text_area(
                "Notatki",
                value=notes_val,
                key=f"notes_{lid}",
                placeholder="Wpisz swoje uwagi...",
                height=68,
                label_visibility="collapsed",
            )
            if new_notes != notes_val:
                set_notes(lid, new_notes)

        # ── Action buttons ────────────────────────────────────────────────────
        st.markdown("<div style='margin-top:12px'>", unsafe_allow_html=True)
        acol1, acol2, acol3, acol4 = st.columns([1, 1, 1, 2])

        with acol1:
            if st.button("❤️ Lubię", key=f"like_{lid}", use_container_width=True,
                         type="primary" if status == "liked" else "secondary"):
                set_status(lid, "liked" if status != "liked" else "new")

        with acol2:
            if st.button("👎 Nie lubię", key=f"dislike_{lid}", use_container_width=True,
                         type="primary" if status == "disliked" else "secondary"):
                set_status(lid, "disliked" if status != "disliked" else "new")

        with acol3:
            st.link_button("🔗 Otwórz OLX", url, use_container_width=True)

        with acol4:
            if listing.get("map", {}).get("lat"):
                lat = listing["map"]["lat"]
                lon = listing["map"]["lon"]
                maps_url = f"https://www.google.com/maps?q={lat},{lon}"
                st.link_button("🗺️ Google Maps", maps_url, use_container_width=True)

        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

# ─── Load more button ─────────────────────────────────────────────────────────
if items_to_show < total_items:
    remaining = total_items - items_to_show
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        c1, c2 = st.columns(2)
        with c1:
            if st.button(f"📥 Więcej ({remaining})", use_container_width=True):
                st.session_state.items_shown += ITEMS_PER_LOAD
                st.rerun()
        with c2:
            if st.button("📋 Wszystko", use_container_width=True):
                st.session_state.items_shown = total_items
                st.rerun()
