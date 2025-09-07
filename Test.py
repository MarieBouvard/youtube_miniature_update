import os
import requests
from PIL import Image, ImageDraw, ImageFont
import subprocess
import time

# --- Paramètres ---
PROMPT = "Une amulette dans une voiture dans un parc au coucher de soleil"
AUTHOR = "Cyril"
#MODEL = "black-forest-labs/flux-schnell"
MODEL = "qwen/qwen-image"

# --- Auth ---
token = os.getenv("REPLICATE_API_TOKEN")
if not token:
    raise SystemExit("❌ Manque le secret REPLICATE_API_TOKEN")

# --- Préparation dossiers ---
os.makedirs("data/archives", exist_ok=True)

# --- Numéro d'archive suivant ---
existing = [f for f in os.listdir("data/archives") if f.endswith("_final.png")]
next_num = len(existing) + 1
num_str = f"{next_num:04d}"

def commit_and_push(msg):
    """Force commit & push"""
    try:
        subprocess.run(["git", "config", "--global", "user.name", "github-actions[bot]"], check=True)
        subprocess.run(["git", "config", "--global", "user.email", "github-actions[bot]@users.noreply.github.com"], check=True)
        subprocess.run(["git", "add", "-A"], check=True)
        subprocess.run(["git", "commit", "--allow-empty", "-m", msg], check=True)
        subprocess.run(["git", "push"], check=True)
        print("✅ Poussé dans le repo :", msg)
    except Exception as e:
        print(f"⚠️ Erreur lors du push : {e}")

# --- Génération image brute ---
print(f"⏳ Génération avec Replicate ({MODEL}) : {PROMPT}")

url = "https://api.replicate.com/v1/predictions"
headers = {"Authorization": f"Token {token}", "Content-Type": "application/json"}
payload = {
    "version": MODEL,
    "input": {"prompt": PROMPT, "width": 1280, "height": 720}
}

response = requests.post(url, headers=headers, json=payload)
if response.status_code not in [200, 201]:
    raise SystemExit(f"❌ Erreur API Replicate : {response.text}")

prediction = response.json()
prediction_url = prediction["urls"]["get"]

while prediction["status"] not in ["succeeded", "failed"]:
    time.sleep(2)
    prediction = requests.get(prediction_url, headers=headers).json()

if prediction["status"] != "succeeded":
    raise SystemExit("❌ La génération a échoué")

image_url = prediction["output"][0]

# --- Sauvegarde brute ---
gen_path = f"data/archives/{num_str}_generated.png"
r = requests.get(image_url, stream=True)
r.raise_for_status()
with open(gen_path, "wb") as f:
    for chunk in r.iter_content(chunk_size=8192):
        f.write(chunk)
print(f"✅ Image brute sauvegardée : {gen_path}")

# --- Push immédiat de l'image brute ---
commit_and_push(f"🖼️ Image brute {num_str} (flux-schnell)")

# --- Montage final ---
miniature_path = "data/miniature.png"
if not os.path.exists(miniature_path):
    raise SystemExit(f"❌ {miniature_path} introuvable")

base = Image.open(miniature_path).convert("RGBA")
gen = Image.open(gen_path).convert("RGBA").resize((785, 502))

x, y = 458, 150
base.paste(gen, (x, y), gen)

# Texte sous l’image
draw = ImageDraw.Draw(base)
text_line = f"{AUTHOR} : {PROMPT}"
if len(text_line) > 70:
    text_line = text_line[:67] + "..."

try:
    font = ImageFont.truetype("DejaVuSans-Bold.ttf", 18)
except Exception:
    font = ImageFont.load_default()

text_y = y + 502 + 10
bbox = draw.textbbox((0, 0), text_line, font=font)
text_w = bbox[2] - bbox[0]
text_x = x + 785 - text_w
draw.text((text_x, text_y), text_line, font=font, fill="white")

# Sauvegardes finales
final_path = "data/final_thumbnail.png"
archive_final = f"data/archives/{num_str}_final.png"
base.save(final_path)
base.save(archive_final)

print(f"✅ Miniature finale sauvegardée : {final_path}")
print(f"💾 Miniature archivée : {archive_final}")

# --- Push final ---
commit_and_push(f"🖼️ Miniature finale {num_str} (flux-schnell)")
