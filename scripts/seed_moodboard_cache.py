import base64
import json
import sys
import time
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from services import moodboard_service

# Create a small valid JPEG byte buffer
sample_bytes = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c"
    b"\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c"
    b"\x1c $.',#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x10"
    b"\x00\x10\x01\x01\x11\x00\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
)
b64 = base64.b64encode(sample_bytes).decode("utf-8")

locations = [
    ("loc_001", "Pier 7 Harbor Exterior", "EXTERIOR"),
    ("loc_002", "Downtown Loft Interior", "INTERIOR"),
    ("loc_003", "Stage A Soundstage", "INTERIOR / STAGE"),
    ("Harbor Pier 7 Exterior", "Harbor Pier 7 Exterior", "EXTERIOR"),
    ("Downtown Loft", "Downtown Loft", "INTERIOR"),
    ("Stage A", "Stage A", "INTERIOR"),
]

for loc_id, loc_name, loc_type in locations:
    entry = {
        "location_id": loc_id,
        "location_name": loc_name,
        "image_base64": b64,
        "prompt": (
            f"Cinematic film still, 35mm motion picture photography, Panavision anamorphic lens. "
            f"Wide establishing shot of {loc_name} ({loc_type}). "
            f"Atmosphere: cinematic golden hour with diffused natural daylight. "
            f"Masterful production design, authentic textures, volumetric haze, photorealistic depth of field, 8k resolution. "
            f"No text, no watermarks, no subtitles, no close-up people, no logos."
        ),
        "created_at": time.time(),
        "expires_at": time.time() + 24 * 3600,
    }
    moodboard_service._save_to_cache(loc_id, entry)

print("Pre-populated moodboard cache entries for locations:", [l[0] for l in locations])
