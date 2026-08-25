"""
Continuity Council — ClickHouse Seed Script

Creates the continuity_council database + all 11 tables (schema.sql), then seeds:
  - Rate card benchmark tables (indie, mid, tentpole)
  - 6 realistic demo productions with real geographical coordinates, local currencies, and day rates:
      1. prod_001 "The Long Dark Take" — Mid tier (Los Angeles, USD) · 3 days, 3 locs, 3 cast, 10 scenes
      2. prod_002 "IRON HORIZON" — Tentpole (Abu Dhabi & Jordan, AED/JOD) · 160 days, 12 locs, 26 cast, 140 scenes
      3. prod_003 "THE LAST REEL" — Mid tier (London, GBP) · 66 days, 9 locs, 18 cast, 80 scenes
      4. prod_004 "NIGHTFALL PROTOCOL" — Mid tier (Berlin, EUR) · 18 days, 7 locs, 14 cast, 34 scenes
      5. prod_005 "SALT & SMOKE" — Indie tier (Maine coast, USD) · 15 days, 5 locs, 9 cast, 26 scenes
      6. prod_006 "CRIMSON STATIC" — Indie tier (Vancouver, CAD) · 20 days, 6 locs, 11 cast, 30 scenes
  - Location + cast availability tables for all 6 productions
  - 200,000 realistic synthetic disruption_history rows (inserted in 10k batches)
  - Materialized view `strategy_performance_mv` with POPULATE

100% deterministic (fixed RNG seed). NO external LLM calls.
"""
import os
import random
import sys
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import clickhouse_connect
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / "backend" / ".env")

# Fixed RNG seed for 100% deterministic reproducibility
random.seed(42)

HOST = os.environ.get("CLICKHOUSE_HOST", "")
PORT = int(os.environ.get("CLICKHOUSE_PORT", "8443"))
USER = os.environ.get("CLICKHOUSE_USER", "default")
PASSWORD = os.environ.get("CLICKHOUSE_PASSWORD", "")
DATABASE = os.environ.get("CLICKHOUSE_DATABASE", "continuity_council")

if not HOST:
    print("ERROR: CLICKHOUSE_HOST is not set. Fill backend/.env first (see .env.example).")
    sys.exit(1)

print(f"Connecting to ClickHouse Cloud: {HOST}:{PORT} as {USER} ...")
client = clickhouse_connect.get_client(
    host=HOST, port=PORT, username=USER, password=PASSWORD, secure=True,
)
print("Connected. Server version:", client.command("SELECT version()"))

t_start = time.perf_counter()

# ---------------------------------------------------------------------------
# 1. Schema & Table Creation
# ---------------------------------------------------------------------------
# Drop existing tables/views so updated schema columns are cleanly applied
for tbl in [
    "strategy_performance_mv", "rate_cards", "production_schedule",
    "location_availability", "cast_availability", "disruption_history",
    "disruption_cases", "decision_ledger", "schedule_changes",
    "locations", "cast_members", "productions",
]:
    client.command(f"DROP TABLE IF EXISTS continuity_council.{tbl}")

schema_sql = (ROOT / "clickhouse" / "schema.sql").read_text()
clean = "\n".join(l for l in schema_sql.splitlines() if not l.strip().startswith("--"))
statements = [s.strip() for s in clean.split(";") if s.strip()]
for stmt in statements:
    client.command(stmt)
print(f"Schema created/verified ({len(statements)} statements).")

NOW = datetime.utcnow()
START_DATE = NOW.date()

# ---------------------------------------------------------------------------
# 2. Rate Cards (Industry Benchmarks)
# ---------------------------------------------------------------------------
rate_cards_data = [
    # Indie tier ($1M-$5M budget)
    ["indie", "crew_day", "day", 40000, "Industry day-cost benchmarks (indie crew blended scale)", NOW],
    ["indie", "sag_scale_day", "performer/day", 1100, "SAG-AFTRA 2024 scale (benchmark)", NOW],
    ["indie", "background_day", "performer/day", 200, "SAG-AFTRA background daily minimum", NOW],
    ["indie", "stunt_day", "performer/day", 1200, "Stunt coordinator / performer daily scale", NOW],
    ["indie", "stage_rental_day", "stage/day", 5000, "Basic soundstage four-wall daily fee", NOW],
    ["indie", "location_permit_day", "permit/day", 500, "Municipal location permit daily fee", NOW],
    ["indie", "practical_location_day", "location/day", 2500, "Practical domestic/commercial site fee", NOW],
    ["indie", "camera_package_day", "package/day", 1200, "Cinema camera + prime lens package rental", NOW],

    # Mid tier ($15M-$50M budget)
    ["mid", "crew_day", "day", 150000, "Industry day-cost benchmarks (IATSE/DGA blended tier 2)", NOW],
    ["mid", "sag_scale_day", "performer/day", 3500, "SAG-AFTRA theatrical schedule F baseline", NOW],
    ["mid", "background_day", "performer/day", 250, "SAG-AFTRA specialty background rate", NOW],
    ["mid", "stunt_day", "performer/day", 2500, "Advanced stunt rig & coordinator daily fee", NOW],
    ["mid", "stage_rental_day", "stage/day", 10000, "Major studio soundstage daily rate card", NOW],
    ["mid", "location_permit_day", "permit/day", 1500, "Urban metro filming permit & police detail", NOW],
    ["mid", "practical_location_day", "location/day", 6000, "Commercial practical location fee", NOW],
    ["mid", "camera_package_day", "package/day", 2000, "Dual camera package + specialty optics", NOW],

    # Tentpole tier ($100M-$250M+ budget)
    ["tentpole", "crew_day", "day", 500000, "Major studio tentpole full crew daily burn rate", NOW],
    ["tentpole", "sag_scale_day", "performer/day", 15000, "Top-tier principal talent holding & day scale", NOW],
    ["tentpole", "background_day", "performer/day", 300, "Ensemble wardrobe/prosthetics background rate", NOW],
    ["tentpole", "stunt_day", "performer/day", 5000, "Heavy stunt unit / wirework daily rate", NOW],
    ["tentpole", "stage_rental_day", "stage/day", 25000, "Stage volume / high-spec VFX LED volume stage", NOW],
    ["tentpole", "location_permit_day", "permit/day", 5000, "Complex closure & municipal security permit", NOW],
    ["tentpole", "practical_location_day", "location/day", 15000, "Exclusive landmark/remote base site fee", NOW],
    ["tentpole", "camera_package_day", "package/day", 3500, "65mm large format camera & technocrane kit", NOW],
]

client.insert(
    "continuity_council.rate_cards", rate_cards_data,
    column_names=["tier", "item", "unit", "daily_rate_usd", "source_note", "created_at"],
)
print(f"Rate cards seeded ({len(rate_cards_data)} benchmark items).")

# ---------------------------------------------------------------------------
# 3. Six Demo Productions Catalog
# ---------------------------------------------------------------------------
productions_rows = [
    # [prod_id, title, start_date, total_days, currency, director, tier, created_at]
    ["prod_001", "The Long Dark Take", START_DATE, 3, "USD", "Elena Marsh", "mid", NOW],
    ["prod_002", "IRON HORIZON", START_DATE, 160, "USD", "Vance Kord", "tentpole", NOW + timedelta(seconds=1)],
    ["prod_003", "THE LAST REEL", START_DATE, 66, "USD", "Julian Sterling", "mid", NOW + timedelta(seconds=2)],
    ["prod_004", "NIGHTFALL PROTOCOL", START_DATE, 18, "USD", "Elena Rostova", "mid", NOW + timedelta(seconds=3)],
    ["prod_005", "SALT & SMOKE", START_DATE, 15, "USD", "Clare Varden", "indie", NOW + timedelta(seconds=4)],
    ["prod_006", "CRIMSON STATIC", START_DATE, 20, "USD", "Damian Cross", "indie", NOW + timedelta(seconds=5)],
]

client.insert(
    "continuity_council.productions", productions_rows,
    column_names=["production_id", "title", "start_date", "total_shoot_days", "currency", "director", "tier", "created_at"],
)

# --- Locations Catalog (with real coordinates, daily fee, and currency) ---
locations_data = {
    "prod_001": [
        ("stage_a", "Stage A: Interrogation Set", "stage", 120, 8000, 34.0522, -118.2437, "USD", "Sound stage, fully lit"),
        ("loft_interior", "Downtown Loft Interior", "interior", 40, 3500, 34.0407, -118.2468, "USD", "Practical location, limited window"),
        ("harbor_exterior", "Harbor Pier 7 Exterior", "exterior", 200, 2500, 33.7405, -118.2720, "USD", "Permit covers Day 1-2 only"),
    ],
    "prod_002": [
        ("loc_p2_dunes_north", "North Erg Desert Dunes", "exterior", 400, 12000, 23.1311, 53.7744, "AED", "Permit covers days 1-120; high heat protocol"),
        ("loc_p2_sietch_cavern", "Sietch Tabr Cavern Interior", "interior", 180, 20000, 24.4539, 54.3773, "AED", "Stage-built cavern with practical moisture traps"),
        ("loc_p2_citadel_bastion", "Arrakeen Citadel Bastion", "exterior", 500, 15000, 24.4672, 54.3650, "AED", "Palace courtyard with heavy crane access"),
        ("loc_p2_stage_vfx_a", "Stage 4 VFX Void & Green", "stage", 250, 25000, 24.4320, 54.4500, "AED", "Full motion-capture rig & wirework gantries"),
        ("loc_p2_spice_canyon", "Canyon of the Great Worm", "exterior", 350, 18000, 29.5760, 35.4190, "JOD", "Remote rocky defile in Jordan, solar peak protocol (>100mi transit from Abu Dhabi unit)"),
        ("loc_p2_moisture_refinery", "Moisture Reclamation Plant", "interior", 120, 10000, 24.4400, 54.4000, "AED", "Industrial stage set, practical steam"),
        ("loc_p2_subterranean_vault", "Crysknife Subterranean Vault", "interior", 90, 9000, 24.4420, 54.4100, "AED", "Low ceilings, confined camera track"),
        ("loc_p2_landing_field", "Imperial Starport Landing Field", "exterior", 600, 14000, 24.4280, 54.6510, "AED", "Tarmac with pyrotechnic clearance"),
        ("loc_p2_observation_ridge", "Shield Wall Observation Ridge", "exterior", 150, 8000, 29.5900, 35.4300, "JOD", "Mountain pass in Jordan, sunrise/sunset golden hour"),
        ("loc_p2_smuggler_outpost", "Smuggler Desert Basin Outpost", "interior", 80, 6000, 23.1400, 53.7900, "AED", "Practical desert bunker set"),
        ("loc_p2_orbital_hangar", "Ornithopter Maintenance Hangar", "stage", 200, 22000, 24.4350, 54.4550, "AED", "Full-scale craft mockups on 6-axis gimbals"),
        ("loc_p2_deep_desert_basin", "Deep Basin Dune Sea", "exterior", 300, 15000, 23.1100, 53.7500, "AED", "Extreme remote location, sandstorm protocol"),
    ],
    "prod_003": [
        ("loc_p3_studio_backlot", "Paramount Lot A: 1940s Street", "exterior", 250, 12000, 51.5283, -0.1338, "GBP", "Period cobblestone, vintage vehicle access"),
        ("loc_p3_projection_booth", "Palace Cinema Projection Booth", "interior", 30, 3000, 51.5115, -0.1305, "GBP", "Confined vintage carbon arc projection room"),
        ("loc_p3_grand_ballroom", "Biltmore Grand Ballroom", "interior", 300, 15000, 51.5074, -0.1432, "GBP", "Historic landmark, no open flame permitted"),
        ("loc_p3_directors_mansion", "Spanish Revival Estate", "interior", 100, 9000, 51.4988, -0.1749, "GBP", "Private estate, sound restrictions after 9 PM"),
        ("loc_p3_vintage_diner", "Hollywood Blvd Diner Interior", "interior", 50, 4000, 51.5138, -0.1315, "GBP", "Practical neon, active kitchen set"),
        ("loc_p3_editing_suite", "Moviola Cutting Room Stage 2", "stage", 40, 6000, 51.5300, -0.1400, "GBP", "Sound stage build, insert camera friendly"),
        ("loc_p3_newspaper_office", "LA Examiner Pressroom", "interior", 120, 7000, 51.5142, -0.1064, "GBP", "Period printing press machinery"),
        ("loc_p3_train_station", "Union Station Departure Gate", "exterior", 200, 10000, 51.5317, -0.1243, "GBP", "Night filming permit only (Days 1-50)"),
        ("loc_p3_art_deco_theater", "Egyptian Theatre Auditorium", "interior", 450, 14000, 51.5108, -0.1290, "GBP", "1,000-seat vintage auditorium"),
    ],
    "prod_004": [
        ("loc_p4_helipad", "Skyline Tower Helipad", "exterior", 120, 8000, 52.5200, 13.4050, "EUR", "High altitude, strict wind limits > 25 knots"),
        ("loc_p4_server_bunker", "Sub-level Secure Data Center", "interior", 60, 6000, 52.5163, 13.3777, "EUR", "Reinforced server room, halon fire system"),
        ("loc_p4_cargo_docks", "Pier 42 Shipping Terminal", "exterior", 250, 9000, 52.4850, 13.5200, "EUR", "Night only, heavy container crane rigging"),
        ("loc_p4_metro_tunnel", "Decommissioned Subway Tube", "interior", 90, 7000, 52.5075, 13.3325, "EUR", "Atmospheric tunnel, ventilation monitored"),
        ("loc_p4_safehouse", "Industrial District Safehouse", "interior", 40, 3500, 52.5020, 13.4110, "EUR", "Practical apartment with armored door props"),
        ("loc_p4_police_hq", "Precinct Tactical Briefing Room", "interior", 80, 5000, 52.5205, 13.4120, "EUR", "Glass-walled squad room with LED wall"),
        ("loc_p4_embassy_roof", "Consulate Rooftop Perimeter", "exterior", 100, 7500, 52.5150, 13.3800, "EUR", "Diplomatic zone, strict noise perimeter"),
    ],
    "prod_005": [
        ("loc_p5_smokehouse", "Coastal Fish Smokehouse", "interior", 35, 2500, 43.6591, -70.2568, "USD", "Working smokehouse, practical smoker ovens"),
        ("loc_p5_weathered_pier", "Old Town Wooden Pier", "exterior", 75, 2000, 43.6550, -70.2500, "USD", "Tide dependent, high water access only"),
        ("loc_p5_family_kitchen", "Farmhouse Country Kitchen", "interior", 25, 1500, 43.6650, -70.2600, "USD", "Intimate practical domestic location"),
        ("loc_p5_local_tavern", "The Anchor & Bell Tavern", "interior", 60, 3000, 43.6570, -70.2530, "USD", "Dimly lit coastal bar, night shoots"),
        ("loc_p5_beach_overlook", "Bluff Top Ocean Overlook", "exterior", 50, 2500, 43.6300, -70.2200, "USD", "Coastal cliff, sunset golden hour only"),
    ],
    "prod_006": [
        ("loc_p6_radio_booth", "K-VOID 98.7 Broadcast Booth", "interior", 30, 3000, 49.2827, -123.1207, "CAD", "Acoustic insulated booth, analog reel decks"),
        ("loc_p6_attic_studio", "Victorian House Attic Studio", "interior", 25, 2200, 49.2700, -123.1100, "CAD", "Creaky floorboards, low slant ceiling"),
        ("loc_p6_forest_cabin", "Pine Ridge Remote Cabin", "exterior", 60, 3500, 49.3700, -123.0800, "CAD", "Night exterior, artificial fog generators"),
        ("loc_p6_tower_relay", "Black Mountain Relay Tower", "exterior", 40, 2800, 49.3800, -123.1000, "CAD", "Exposed peak, lightning hazard protocols"),
        ("loc_p6_tape_archive", "Town Hall Old Tape Archives", "interior", 35, 2000, 49.2600, -123.1300, "CAD", "Underground vault, humidity controlled"),
        ("loc_p6_sheriff_cell", "County Sheriff Holding Cell", "interior", 50, 2500, 49.2500, -123.1000, "CAD", "Steel bars, fluorescent flicker effects"),
    ],
}

all_locations = []
for pid, locs in locations_data.items():
    for lid, name, ltype, cap, fee, lat, lon, curr, notes in locs:
        all_locations.append([pid, lid, name, ltype, cap, fee, lat, lon, curr, notes, NOW])

client.insert(
    "continuity_council.locations", all_locations,
    column_names=["production_id", "location_id", "name", "location_type", "capacity", "daily_fee_usd", "latitude", "longitude", "currency_code", "notes", "created_at"],
)

# --- Cast Catalog (with day_rate_usd) ---
cast_data = {
    "prod_001": [
        ("lead_001", "Mara Voss", "lead", 3500),
        ("supp_001", "Dev Okafor", "supporting", 1500),
        ("supp_002", "Lena Petrov", "supporting", 1500),
    ],
    "prod_002": [
        ("cast_p2_001", "Kaelen Voss", "lead", 25000),
        ("cast_p2_002", "Sora Dane", "lead", 20000),
        ("cast_p2_003", "Baron Silas Vane", "lead", 22000),
        ("cast_p2_004", "Warmaster Theron", "supporting", 5000),
        ("cast_p2_005", "Reverend Mother Mohiam", "supporting", 6000),
        ("cast_p2_006", "Jaxen Reed", "supporting", 4500),
        ("cast_p2_007", "Cassian Vance", "supporting", 4000),
        ("cast_p2_008", "Naib Tarek", "supporting", 4500),
        ("cast_p2_009", "Princess Lyra Corrino", "supporting", 5500),
        ("cast_p2_010", "Dr. Aris Wellington", "supporting", 3500),
        ("cast_p2_011", "Lady Helene Voss", "supporting", 5000),
        ("cast_p2_012", "Raban Vane", "supporting", 4500),
        ("cast_p2_013", "Fremen Scout Anya", "supporting", 2500),
        ("cast_p2_014", "Ornithopter Pilot Miller", "supporting", 2500),
        ("cast_p2_015", "Guild Envoy Croll", "supporting", 2500),
        ("cast_p2_016", "Sandmaster Kynes", "supporting", 2500),
        ("cast_p2_017", "Citadel Commander Gault", "supporting", 2500),
        ("cast_p2_018", "Smuggler Captain Jax", "supporting", 2500),
        ("cast_p2_019", "Trooper Kovac", "supporting", 2500),
        ("cast_p2_020", "Elder Chani", "supporting", 2500),
        ("cast_p2_021", "Navigator Tertius", "supporting", 2500),
        ("cast_p2_022", "Lieutenant Varis", "supporting", 2500),
        ("cast_p2_023", "Fremen Healer Talia", "supporting", 2500),
        ("cast_p2_024", "Refinery Foreman Brant", "supporting", 2500),
        ("cast_p2_025", "Imperial Envoy Thorne", "supporting", 2500),
        ("cast_p2_026", "Subterranean Guide Seth", "supporting", 2500),
    ],
    "prod_003": [
        ("cast_p3_001", "Arthur Pendelton", "lead", 8000),
        ("cast_p3_002", "Clara Fontaine", "lead", 7500),
        ("cast_p3_003", "Max Gold", "lead", 7000),
        ("cast_p3_004", "Vivian Vance", "supporting", 2500),
        ("cast_p3_005", "George Kelly", "supporting", 2000),
        ("cast_p3_006", "Mabel Normand", "supporting", 2000),
        ("cast_p3_007", "Henry Wilcox", "supporting", 2000),
        ("cast_p3_008", "Beatrice Ward", "supporting", 2000),
        ("cast_p3_009", "Frankie Moretti", "supporting", 2000),
        ("cast_p3_010", "Evelyn Reed", "supporting", 2000),
        ("cast_p3_011", "Oscar Finch", "supporting", 2000),
        ("cast_p3_012", "Sylvia Plath", "supporting", 2000),
        ("cast_p3_013", "Walter Winchell", "supporting", 2000),
        ("cast_p3_014", "Rose O'Neill", "supporting", 2000),
        ("cast_p3_015", "Chester Bell", "supporting", 2000),
        ("cast_p3_016", "Gloria Swanson", "supporting", 2000),
        ("cast_p3_017", "Detective Harris", "supporting", 2000),
        ("cast_p3_018", "Projectionist Leo", "supporting", 2000),
    ],
    "prod_004": [
        ("cast_p4_001", "Agent Cole Mercer", "lead", 6000),
        ("cast_p4_002", "Dr. Maya Lin", "lead", 5500),
        ("cast_p4_003", "Viktor Ramos", "lead", 5000),
        ("cast_p4_004", "Commander Vance", "supporting", 2000),
        ("cast_p4_005", "Technician Sarah Cross", "supporting", 1800),
        ("cast_p4_006", "Sniper Kyle Graves", "supporting", 1800),
        ("cast_p4_007", "Agent Davis", "supporting", 1800),
        ("cast_p4_008", "Operative Novak", "supporting", 1800),
        ("cast_p4_009", "Director Sterling", "supporting", 1800),
        ("cast_p4_010", "Informant Chen", "supporting", 1800),
        ("cast_p4_011", "Pilot Bishop", "supporting", 1800),
        ("cast_p4_012", "Field Medic Jones", "supporting", 1800),
        ("cast_p4_013", "Tactical Officer Ruiz", "supporting", 1800),
        ("cast_p4_014", "Cyber Specialist Kim", "supporting", 1800),
    ],
    "prod_005": [
        ("cast_p5_001", "Elias Gray", "lead", 1500),
        ("cast_p5_002", "Nora Gray", "lead", 1400),
        ("cast_p5_003", "Caleb Scott", "lead", 1200),
        ("cast_p5_004", "Martha Gray", "supporting", 1100),
        ("cast_p5_005", "Tavern Owner Gus", "supporting", 1100),
        ("cast_p5_006", "Deckhand Tom", "supporting", 1100),
        ("cast_p5_007", "Sheriff Dalton", "supporting", 1100),
        ("cast_p5_008", "Harbor Master Cole", "supporting", 1100),
        ("cast_p5_009", "Doctor Warren", "supporting", 1100),
    ],
    "prod_006": [
        ("cast_p6_001", "Reese Miller", "lead", 1800),
        ("cast_p6_002", "Hanna Walsh", "lead", 1600),
        ("cast_p6_003", "Sheriff Jim Wade", "lead", 1500),
        ("cast_p6_004", "Occult Researcher Peter", "supporting", 1100),
        ("cast_p6_005", "Caller 'The Watcher'", "supporting", 1100),
        ("cast_p6_006", "Deputy Myers", "supporting", 1100),
        ("cast_p6_007", "Town Archivist Martha", "supporting", 1100),
        ("cast_p6_008", "Cabin Caretaker Frank", "supporting", 1100),
        ("cast_p6_009", "Station Manager Vance", "supporting", 1100),
        ("cast_p6_010", "Radio Engineer Tom", "supporting", 1100),
        ("cast_p6_011", "Mysterious Listener", "supporting", 1100),
    ],
}

all_cast = []
for pid, cast_list in cast_data.items():
    for cid, name, rtype, rate in cast_list:
        all_cast.append([pid, cid, name, rtype, rate, NOW])

client.insert(
    "continuity_council.cast_members", all_cast,
    column_names=["production_id", "cast_id", "name", "role_type", "day_rate_usd", "created_at"],
)

# --- Schedule Generation for all 6 Productions ---
prod_001_scenes = [
    ["prod_001", "sc_001", "Apartment: Mara finds the letter", 1, 1, "loft_interior", ["lead_001", "supp_001"], "interior", 0, 2, ["costume_day1"], [], "scheduled", NOW],
    ["prod_001", "sc_002", "Breakfast argument", 1, 2, "loft_interior", ["lead_001", "supp_001"], "dialogue", 0, 2, ["costume_day1", "emotional_continuity"], ["sc_001"], "scheduled", NOW],
    ["prod_001", "sc_003", "Harbor chase", 1, 3, "harbor_exterior", ["lead_001", "supp_002"], "exterior", 0, 1, ["stunt_rig"], [], "scheduled", NOW],
    ["prod_001", "sc_004", "Dock confrontation (Lena alone)", 1, 4, "harbor_exterior", ["supp_002"], "exterior", 0, 3, [], ["sc_003"], "scheduled", NOW],
    ["prod_001", "sc_005", "Interrogation room: first questioning", 2, 5, "stage_a", ["lead_001", "supp_001"], "interior", 0, 1, ["costume_interrogation", "emotional_continuity"], [], "scheduled", NOW],
    ["prod_001", "sc_006", "Lead confrontation scene", 2, 6, "stage_a", ["lead_001", "supp_001", "supp_002"], "interior", 0, 1, ["costume_interrogation", "costume_change"], ["sc_005"], "scheduled", NOW],
    ["prod_001", "sc_007", "Mara's phone call to the fixer", 2, 7, "loft_interior", ["lead_001"], "dialogue", 0, 2, ["costume_change"], [], "scheduled", NOW],
    ["prod_001", "sc_008", "Night stakeout (Dev & Lena)", 2, 8, "harbor_exterior", ["supp_001", "supp_002"], "exterior", 0, 3, [], [], "scheduled", NOW],
    ["prod_001", "sc_009", "Cover set: office B-roll & inserts", 3, 9, "stage_a", ["supp_001"], "cover", 1, 4, [], [], "scheduled", NOW],
    ["prod_001", "sc_010", "Finale: warehouse showdown", 3, 10, "stage_a", ["lead_001", "supp_001", "supp_002"], "interior", 0, 1, ["emotional_continuity"], ["sc_006"], "scheduled", NOW],
]

def generate_catalog_scenes(pid: str, total_days: int, target_scene_count: int, locs: list, cast_list: list, archetype_name: str) -> list:
    """Deterministically generate realistic schedule scenes for catalog productions."""
    scenes = []
    leads = [c[0] for c in cast_list if c[2] == "lead"]
    supps = [c[0] for c in cast_list if c[2] == "supporting"]
    loc_ids = [l[0] for l in locs]
    stage_locs = [l[0] for l in locs if l[2] in ("stage", "interior")] or loc_ids

    scene_idx = 1
    seq = 1

    for day in range(1, total_days + 1):
        count = 1
        if (day % 3 == 0 or day == 1 or day == total_days) and len(scenes) + 2 <= target_scene_count:
            count = 2
        if day == total_days // 2 and len(scenes) + 3 <= target_scene_count:
            count = 3

        for _ in range(count):
            if scene_idx > target_scene_count:
                break
            sid = f"sc_{pid[5:]}_{scene_idx:03d}"
            is_cover = 1 if (scene_idx % 12 == 0 or (scene_idx == target_scene_count and pid == "prod_002")) else 0

            loc_choice = loc_ids[(day + scene_idx) % len(loc_ids)]
            if is_cover:
                loc_choice = stage_locs[scene_idx % len(stage_locs)]

            if is_cover:
                assigned_cast = [supps[(scene_idx + day) % len(supps)]]
                stype = "cover"
                priority = 4
                title = f"Cover Insert: {archetype_name} B-roll #{scene_idx}"
                tags = []
                deps = []
            else:
                lead_pick = leads[scene_idx % len(leads)]
                supp_pick = supps[(scene_idx * 2) % len(supps)]
                assigned_cast = [lead_pick, supp_pick]
                if scene_idx % 4 == 0 and len(leads) > 1:
                    assigned_cast.append(leads[(scene_idx + 1) % len(leads)])
                stype = "interior" if "interior" in loc_choice or "cavern" in loc_choice or "vault" in loc_choice else "exterior"
                priority = 1 if (scene_idx % 5 == 0 or day == total_days) else (2 if scene_idx % 2 == 0 else 3)
                title = f"{archetype_name} Act {min(3, 1 + scene_idx // 30)}: Scene {scene_idx} ({loc_choice.replace('loc_', '').replace(pid+'_', '')})"
                tags = [f"costume_phase_{1 + (day % 4)}"]
                if priority == 1:
                    tags.append("climax_continuity")
                deps = [f"sc_{pid[5:]}_{scene_idx-1:03d}"] if (scene_idx > 1 and scene_idx % 3 == 0) else []

            scenes.append([
                pid, sid, title, day, seq, loc_choice, assigned_cast, stype, is_cover, priority, tags, deps, "scheduled", NOW,
            ])
            scene_idx += 1
            seq += 1

    while len(scenes) < target_scene_count:
        day = (len(scenes) % total_days) + 1
        sid = f"sc_{pid[5:]}_{scene_idx:03d}"
        loc_choice = stage_locs[len(scenes) % len(stage_locs)]
        assigned_cast = [leads[0], supps[0]]
        scenes.append([
            pid, sid, f"{archetype_name} Extra Slate #{scene_idx}", day, seq, loc_choice, assigned_cast, "interior", 0, 3, [], [], "scheduled", NOW,
        ])
        scene_idx += 1
        seq += 1

    return scenes

all_scenes = list(prod_001_scenes)
all_scenes.extend(generate_catalog_scenes("prod_002", 160, 140, locations_data["prod_002"], cast_data["prod_002"], "Desert Unit"))
all_scenes.extend(generate_catalog_scenes("prod_003", 66, 80, locations_data["prod_003"], cast_data["prod_003"], "Period Drama"))
all_scenes.extend(generate_catalog_scenes("prod_004", 18, 34, locations_data["prod_004"], cast_data["prod_004"], "Tactical Protocol"))
all_scenes.extend(generate_catalog_scenes("prod_005", 15, 26, locations_data["prod_005"], cast_data["prod_005"], "Coastal Memoir"))
all_scenes.extend(generate_catalog_scenes("prod_006", 20, 30, locations_data["prod_006"], cast_data["prod_006"], "Broadcast Horror"))

client.insert(
    "continuity_council.production_schedule", all_scenes,
    column_names=["production_id", "scene_id", "scene_title", "shoot_day", "sequence_order",
                  "location_id", "required_cast", "scene_type", "is_cover_scene", "priority",
                  "continuity_tags", "depends_on", "status", "updated_at"],
)

# --- Location Availability ---
all_loc_avail = []
for lid, _, _, _, _, _, _, _, _ in locations_data["prod_001"]:
    for day in range(1, 4):
        avail = 0 if (lid == "harbor_exterior" and day == 3) else 1
        note = "Permit expired: pier closed Day 3" if not avail else ""
        all_loc_avail.append(["prod_001", lid, day, avail, note, NOW])

for pid, total_days in [("prod_002", 160), ("prod_003", 66), ("prod_004", 18), ("prod_005", 15), ("prod_006", 20)]:
    locs = locations_data[pid]
    for lid, name, ltype, cap, fee, lat, lon, curr, notes in locs:
        for day in range(1, total_days + 1):
            avail = 1
            note = ""
            if pid == "prod_002":
                if lid == "loc_p2_dunes_north" and day > 120:
                    avail = 0
                    note = "North dunes permit expired after Day 120"
                elif lid == "loc_p2_deep_desert_basin" and day in (45, 90, 135):
                    avail = 0
                    note = "Deep basin closed for severe sandstorm safety window"
            elif pid == "prod_003":
                if lid == "loc_p3_train_station" and day > 50:
                    avail = 0
                    note = "Train station night permit lapsed after Day 50"
            elif pid == "prod_004":
                if lid == "loc_p4_helipad" and day in (5, 12):
                    avail = 0
                    note = "Helipad unavailable: high wind advisory"
            elif pid == "prod_005":
                if lid == "loc_p5_weathered_pier" and day % 7 == 0:
                    avail = 0
                    note = "Pier closed for weekly commercial freight"
            elif pid == "prod_006":
                if lid == "loc_p6_tower_relay" and day in (8, 16):
                    avail = 0
                    note = "Tower relay closed for maintenance"
            all_loc_avail.append([pid, lid, day, avail, note, NOW])

client.insert(
    "continuity_council.location_availability", all_loc_avail,
    column_names=["production_id", "location_id", "shoot_day", "available", "notes", "updated_at"],
)

# --- Cast Availability ---
all_cast_avail = []
for pid, total_days in [("prod_001", 3), ("prod_002", 160), ("prod_003", 66), ("prod_004", 18), ("prod_005", 15), ("prod_006", 20)]:
    c_list = cast_data[pid]
    for cid, name, rtype, rate in c_list:
        for day in range(1, total_days + 1):
            avail = 1
            reason = ""
            all_cast_avail.append([pid, cid, day, avail, reason, NOW])

client.insert(
    "continuity_council.cast_availability", all_cast_avail,
    column_names=["production_id", "cast_id", "shoot_day", "available", "reason", "updated_at"],
)

print(f"Catalog seeded: 6 productions ({len(productions_rows)} prods, {len(all_locations)} locations, {len(all_cast)} cast, {len(all_scenes)} scenes).")

# ---------------------------------------------------------------------------
# 4. Disruption History (200,000 synthetic rows in 10k batches)
# ---------------------------------------------------------------------------
N_TOTAL_HISTORY = 200_000
BATCH_SIZE = 10_000

TYPE_STRATEGY_MAP = {
    "lead_actor_unavailable": [
        ("shoot_cover_scenes", 0.40, (8000, 28000), (2.0, 5.5), (0.20, 0.45), (0.05, 0.20)),
        ("swap_locations", 0.22, (15000, 42000), (3.0, 7.5), (0.12, 0.32), (0.10, 0.35)),
        ("move_to_later_day", 0.18, (20000, 52000), (5.0, 9.5), (0.15, 0.35), (0.10, 0.30)),
        ("use_stand_in", 0.10, (10000, 26000), (2.0, 4.5), (0.35, 0.65), (0.08, 0.25)),
        ("wait_for_actor", 0.05, (35000, 95000), (8.0, 16.0), (0.03, 0.18), (0.05, 0.20)),
        ("recast_scene", 0.03, (25000, 70000), (6.0, 14.0), (0.50, 0.85), (0.20, 0.50)),
        ("split_scene", 0.02, (12000, 32000), (3.0, 6.5), (0.30, 0.55), (0.10, 0.30)),
    ],
    "location_unavailable": [
        ("swap_locations", 0.45, (14000, 40000), (2.5, 6.5), (0.10, 0.30), (0.12, 0.40)),
        ("move_to_later_day", 0.28, (18000, 48000), (4.5, 9.0), (0.14, 0.34), (0.10, 0.30)),
        ("shoot_cover_scenes", 0.15, (8500, 26000), (2.0, 5.0), (0.22, 0.46), (0.05, 0.20)),
        ("split_scene", 0.08, (11000, 30000), (2.5, 6.0), (0.28, 0.52), (0.08, 0.28)),
        ("wait_for_actor", 0.04, (30000, 85000), (7.0, 15.0), (0.05, 0.20), (0.05, 0.20)),
    ],
    "weather_delay": [
        ("swap_locations", 0.42, (12000, 36000), (2.0, 6.0), (0.12, 0.32), (0.10, 0.30)),
        ("shoot_cover_scenes", 0.30, (7500, 24000), (1.5, 4.5), (0.20, 0.42), (0.05, 0.18)),
        ("move_to_later_day", 0.20, (16000, 44000), (4.0, 8.5), (0.15, 0.35), (0.10, 0.28)),
        ("wait_for_actor", 0.08, (28000, 75000), (6.0, 13.0), (0.04, 0.18), (0.05, 0.20)),
    ],
    "equipment_failure": [
        ("swap_locations", 0.35, (11000, 34000), (2.0, 5.5), (0.10, 0.30), (0.08, 0.28)),
        ("move_to_later_day", 0.30, (17000, 46000), (4.0, 8.5), (0.14, 0.32), (0.10, 0.30)),
        ("shoot_cover_scenes", 0.22, (8000, 25000), (1.8, 4.8), (0.22, 0.45), (0.05, 0.20)),
        ("split_scene", 0.13, (10000, 28000), (2.2, 5.2), (0.25, 0.50), (0.08, 0.25)),
    ],
}

DISRUPTION_TYPES_WEIGHTS = [
    ("lead_actor_unavailable", 0.28),
    ("location_unavailable", 0.28),
    ("weather_delay", 0.22),
    ("equipment_failure", 0.22),
]

TYPE_ROLES = {
    "lead_actor_unavailable": "lead_actor",
    "location_unavailable": "location",
    "weather_delay": "location",
    "equipment_failure": "equipment",
}

SEVERITIES = [("low", 0.30, 0.80), ("medium", 0.45, 1.0), ("high", 0.25, 1.30)]
PRODUCTION_TYPES = [("feature_film", 0.50), ("tv_series", 0.28), ("streaming_series", 0.14), ("commercial", 0.08)]

NOTES_TEMPLATES = {
    "shoot_cover_scenes": [
        "Cover scenes preserved shoot day momentum; principal setups moved to a later day.",
        "B-roll and insert coverage kept the crew active while talent/location cleared.",
        "Second unit picked up cover set work; minimal overtime incurred.",
        "Cover stage work absorbed disruption with excellent crew morale.",
    ],
    "swap_locations": [
        "Interior/exterior swap absorbed the disruption with moderate company move cost.",
        "Location swap required extra transport but avoided a lost shooting day.",
        "Cover set swap approved by AD; continuity verified before move.",
        "Company moved to soundstage; schedule preserved with minimal delay.",
    ],
    "move_to_later_day": [
        "Affected scenes pushed to a later shoot day; minor crew overtime incurred.",
        "Rescheduled to buffer day; required condensed multi-camera setups.",
        "Day push absorbed within production contingency budget.",
        "Moved to final week wrap slate; location rebooked successfully.",
    ],
    "wait_for_actor": [
        "Unit held on standby; idle crew time incurred while waiting for talent.",
        "Production held on location; minor per-diem overruns.",
        "Standby hold resolved in afternoon; partial slate completed.",
    ],
    "recast_scene": [
        "Role recast; pickup coverage completed without breaking continuity.",
        "Recast completed quickly; wardrobe adjustments approved by director.",
    ],
    "split_scene": [
        "Scene split across two days; lighting matched perfectly on soundstage.",
        "Partial coverage completed; remainder scheduled with stand-in inserts.",
    ],
    "use_stand_in": [
        "Photo double covered wide shots; close-ups deferred to talent return.",
        "Stand-in executed blocking rehearsals; main unit ready upon arrival.",
    ],
}

def weighted_choice(pairs):
    r = random.random()
    acc = 0.0
    for value, w in pairs:
        acc += w
        if r <= acc:
            return value
    return pairs[-1][0]

print(f"Generating and inserting {N_TOTAL_HISTORY:,} historical disruption rows in {BATCH_SIZE:,}-row batches...")

total_inserted = 0
batch = []
batch_num = 1
num_batches = N_TOTAL_HISTORY // BATCH_SIZE

for i in range(N_TOTAL_HISTORY):
    dtype = weighted_choice(DISRUPTION_TYPES_WEIGHTS)
    strategy_candidates = TYPE_STRATEGY_MAP[dtype]
    strat_item = weighted_choice([(s, s[1]) for s in strategy_candidates])
    strat_name, _, (cost_lo, cost_hi), (d_lo, d_hi), (cont_lo, cont_hi), (comp_lo, comp_hi) = strat_item

    sev_choice = weighted_choice([(0, 0.30), (1, 0.45), (2, 0.25)])
    severity, _, sev_mult = SEVERITIES[sev_choice]

    cost = int(random.triangular(cost_lo, cost_hi, cost_lo + (cost_hi - cost_lo) * 0.35) * sev_mult)
    delay = round(random.triangular(d_lo, d_hi, d_lo + (d_hi - d_lo) * 0.40) * sev_mult, 1)

    cont = round(random.uniform(cont_lo, cont_hi), 2)
    comp = round(random.uniform(comp_lo, comp_hi), 2)

    cost_norm = (cost - cost_lo * 0.7) / (cost_hi * 1.35 - cost_lo * 0.7)
    delay_norm = (delay - d_lo * 0.7) / (d_hi * 1.35 - d_lo * 0.7)
    success = max(0.05, min(0.98, 1.0 - 0.42 * cost_norm - 0.32 * delay_norm - 0.16 * cont + random.uniform(-0.06, 0.06)))

    created = NOW - timedelta(days=random.uniform(1, 1095), hours=random.uniform(0, 23))

    batch.append([
        f"dis_{uuid.uuid4().hex[:12]}",
        weighted_choice(PRODUCTION_TYPES),
        dtype,
        severity,
        TYPE_ROLES[dtype],
        random.randint(1, 8),
        strat_name,
        cost,
        delay,
        cont,
        comp,
        round(success, 2),
        random.choice(NOTES_TEMPLATES.get(strat_name, ["Resolution executed per production guidelines."])),
        created,
    ])

    if len(batch) >= BATCH_SIZE:
        client.insert(
            "continuity_council.disruption_history", batch,
            column_names=["disruption_id", "production_type", "disruption_type", "severity",
                          "affected_role", "affected_scene_count", "resolution_strategy",
                          "cost_overrun_usd", "schedule_delay_hours", "continuity_risk_score",
                          "compliance_risk_score", "success_score", "notes", "created_at"],
        )
        total_inserted += len(batch)
        print(f"  Batch {batch_num}/{num_batches} inserted ({total_inserted:,} / {N_TOTAL_HISTORY:,} rows)...")
        batch = []
        batch_num += 1

if batch:
    client.insert(
        "continuity_council.disruption_history", batch,
        column_names=["disruption_id", "production_type", "disruption_type", "severity",
                      "affected_role", "affected_scene_count", "resolution_strategy",
                      "cost_overrun_usd", "schedule_delay_hours", "continuity_risk_score",
                      "compliance_risk_score", "success_score", "notes", "created_at"],
    )
    total_inserted += len(batch)

print(f"Finished inserting {total_inserted:,} disruption_history rows.")

# ---------------------------------------------------------------------------
# 5. Re-create & Populate Materialized View
# ---------------------------------------------------------------------------
print("Re-creating strategy_performance_mv with POPULATE...")
client.command("DROP TABLE IF EXISTS continuity_council.strategy_performance_mv")
client.command("""
CREATE MATERIALIZED VIEW continuity_council.strategy_performance_mv
ENGINE = AggregatingMergeTree()
ORDER BY (disruption_type, strategy, severity)
POPULATE
AS SELECT
    disruption_type,
    resolution_strategy AS strategy,
    severity,
    avgState(cost_overrun_usd) AS avg_cost,
    avgState(schedule_delay_hours) AS avg_delay,
    countState() AS sample_size,
    avgState(continuity_risk_score) AS avg_continuity_risk,
    avgState(compliance_risk_score) AS avg_compliance_risk,
    avgState(success_score) AS avg_success_score
FROM continuity_council.disruption_history
GROUP BY disruption_type, resolution_strategy, severity
""")
print("Materialized view populated.")

t_duration = time.perf_counter() - t_start
print(f"\nSeed completed in {t_duration:.2f} seconds.")

# Row counts per table
print("\n=== ClickHouse Table Row Counts ===")
for tbl in [
    "productions", "locations", "cast_members", "rate_cards", "production_schedule",
    "location_availability", "cast_availability", "disruption_history",
]:
    cnt = client.command(f"SELECT count() FROM continuity_council.{tbl}")
    print(f"  continuity_council.{tbl:<25}: {cnt:>10,}")

print("\nSEED COMPLETED SUCCESSFULLY.")
