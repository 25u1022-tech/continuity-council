import base64
import io
import json
import sys
import time
from pathlib import Path
from PIL import Image, ImageDraw

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from services import moodboard_service

def create_cinematic_sample_image(location_name: str, location_type: str) -> bytes:
    """Create a high-quality 1280x720 16:9 cinematic frame with atmospheric gradients."""
    width, height = 1280, 720
    img = Image.new("RGB", (width, height), color=(15, 18, 24))
    draw = ImageDraw.Draw(img)

    # Cinematic gradient: deep blue twilight to amber sunset or studio tones
    is_ext = "exterior" in location_type.lower() or "harbor" in location_name.lower()
    for y in range(height):
        ratio = y / height
        if is_ext:
            # Golden hour harbor: deep navy sky -> golden amber horizon -> deep water
            if ratio < 0.6:
                t = ratio / 0.6
                r = int(20 * (1 - t) + 180 * t)
                g = int(35 * (1 - t) + 110 * t)
                b = int(70 * (1 - t) + 50 * t)
            else:
                t = (ratio - 0.6) / 0.4
                r = int(180 * (1 - t) + 15 * t)
                g = int(110 * (1 - t) + 25 * t)
                b = int(50 * (1 - t) + 40 * t)
        else:
            # Rich interior / Stage: warm amber practical lights -> charcoal shadows
            t = ratio
            r = int(35 * (1 - t) + 18 * t)
            g = int(28 * (1 - t) + 20 * t)
            b = int(22 * (1 - t) + 26 * t)

        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Anamorphic 2.39:1 letterbox subtle guides
    bar_height = 40
    draw.rectangle([(0, 0), (width, bar_height)], fill=(5, 6, 8))
    draw.rectangle([(0, height - bar_height), (width, height)], fill=(5, 6, 8))

    # Subtle vignette overlay
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()

locations = [
    ("loc_001", "Pier 7 Harbor Exterior", "EXTERIOR"),
    ("loc_002", "Downtown Loft Interior", "INTERIOR"),
    ("loc_003", "Stage A Soundstage", "INTERIOR / STAGE"),
    ("harbor_exterior", "Harbor Pier 7 Exterior", "EXTERIOR"),
    ("loft_interior", "Downtown Loft Interior", "INTERIOR"),
    ("stage_a", "Stage A: Interrogation Set", "INTERIOR / STAGE"),
    ("Harbor Pier 7 Exterior", "Harbor Pier 7 Exterior", "EXTERIOR"),
    ("Downtown Loft", "Downtown Loft", "INTERIOR"),
    ("Stage A", "Stage A", "INTERIOR"),
]

# 1. Purge old stale cache
moodboard_service.purge_cache()

# 2. Seed fresh normalized entries
for loc_id, loc_name, loc_type in locations:
    img_bytes = create_cinematic_sample_image(loc_name, loc_type)
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    entry = {
        "location_id": loc_id,
        "location_name": loc_name,
        "image_base64": b64,
        "mime": "image/jpeg",
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

print("Pre-populated fresh normalized moodboard cache entries for locations:", [l[0] for l in locations])
