import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load env from backend/.env or root .env
root_dir = Path(__file__).resolve().parent.parent
backend_env = root_dir / "backend" / ".env"
root_env = root_dir / ".env"

if backend_env.exists():
    load_dotenv(backend_env)
elif root_env.exists():
    load_dotenv(root_env)

api_key = os.getenv("GEMINI_API_KEY", "").strip()
if not api_key:
    print("ERROR: GEMINI_API_KEY is not set or empty in environment / .env file.")
    sys.exit(1)

from google import genai
from google.genai import types
from google.genai.errors import APIError

client = genai.Client(api_key=api_key)

candidate_models = [
    "gemini-2.5-flash-image",
    "gemini-2.0-flash-exp-image-generation",
    "gemini-2.0-flash-preview-image-generation",
]

prompt = "Cinematic film still of an old warehouse at sunset, 35mm film photograph."

print("=" * 80)
print("DIAGNOSING MOODBOARD IMAGE GENERATION MODELS")
print(f"API Key present: {api_key[:6]}...{api_key[-4:]} (len: {len(api_key)})")
print("=" * 80)

results = []

for model_name in candidate_models:
    print(f"\n---> Testing model: {model_name}")
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
            ),
        )

        has_image = False
        img_bytes_len = 0
        mime_type = None

        if response and getattr(response, "candidates", None):
            for cand in response.candidates:
                content = getattr(cand, "content", None)
                parts = getattr(content, "parts", None) if content else []
                for part in parts:
                    inline_data = getattr(part, "inline_data", None)
                    if inline_data and getattr(inline_data, "data", None):
                        raw_data = inline_data.data
                        img_bytes_len = len(raw_data) if raw_data else 0
                        mime_type = getattr(inline_data, "mime_type", "unknown")
                        if img_bytes_len > 0:
                            has_image = True
                            break
                if has_image:
                    break

        if has_image:
            print(f"SUCCESS! Model {model_name} returned image ({img_bytes_len} bytes, mime: {mime_type})")
            results.append({
                "model": model_name,
                "status": "SUCCESS",
                "bytes": img_bytes_len,
                "mime": mime_type,
                "error": None,
            })
        else:
            print(f"FAILED (No image bytes in response candidates). Response: {response}")
            results.append({
                "model": model_name,
                "status": "FAILED_NO_IMAGE",
                "bytes": 0,
                "mime": None,
                "error": "No inline image data in candidates",
            })

    except APIError as ae:
        code = getattr(ae, "code", "UNKNOWN_CODE")
        msg = getattr(ae, "message", str(ae))
        print(f"APIError: code={code} message={msg}")
        results.append({
            "model": model_name,
            "status": "API_ERROR",
            "code": code,
            "message": msg,
            "error": f"APIError {code}: {msg}",
        })
    except Exception as exc:
        print(f"Exception ({type(exc).__name__}): {exc}")
        results.append({
            "model": model_name,
            "status": "EXCEPTION",
            "type": type(exc).__name__,
            "message": str(exc),
            "error": f"{type(exc).__name__}: {exc}",
        })

print("\n" + "=" * 80)
print("DIAGNOSIS SUMMARY TABLE")
print("=" * 80)
print(f"{'Model':<45} | {'Status':<15} | {'Details'}")
print("-" * 80)
for r in results:
    details = r.get("error") or f"{r.get('bytes')} bytes ({r.get('mime')})"
    print(f"{r['model']:<45} | {r['status']:<15} | {details}")
print("=" * 80)
