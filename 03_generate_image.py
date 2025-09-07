import os
import json
import requests
import time
import re
import subprocess
from PIL import Image, ImageDraw, ImageFont

# --- Paramètres ---
MODEL = "qwen/qwen-image"   # 👉 modèle à éditer facilement ici
PROMPT_PREFIX = "Une image photoréaliste représentant : "

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
if not REPLICATE_API_TOKEN:
    raise SystemExit("❌ Manque le secret REPLICATE_API_TOKEN")

# --- Fonction commit & push ---
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

# --- Charger le commentaire sélectionné ---
with open("data/selected_comment.json", "r", encoding="utf-8") as f:
    comment = json.load(f)

text = comment.get("text", "")
author = comment.get("author", "Anonyme")

author_safe = re.sub(r"[^a-zA-Z0-9_-]", "_", author)
snippet = text[:14] if text else "no_text"
snippet_safe = re.sub(r"[^a-zA-Z0-9_-]", "_", snippet)

os.makedirs("data", exist_ok=True)
os.makedirs("data/archives", exist_ok=True)

# --- Numéro d'archive suivant ---
existing_archives = [f for f in os.listdir("data/archives") if f.endswith("_generated.png")]
next_num = len(existing_archives) + 1
num_str = f"{next_num:04d}"
archive_generated = os.path.join("data/archives", f"{num_str}_generated.png")

# --- Prompt ---
prompt = f"{PROMPT_PREFIX}{text}, haute qualité, style photographie réaliste, détails précis, lumière naturelle"
print("🎨 Prompt envoyé à Replicate :", prompt)

# --- Appel API Replicate ---
url = "https://api.replicate.com/v1/predictions"
headers = {
    "Authorization": f"Token {REPLICATE_API_TOKEN}",
    "Content-Type": "application/json"
}
payload = {
    "version": MODEL,
    "input": {"prompt": prompt, "width": 1280, "height": 720}
}

response = requests.post(url, headers=headers, json=payload)
if response.status_code not in [200, 201]:
    print("❌ Erreur API Replicate :", response.text)
    raise SystemExit(1)

prediction = response.json()
prediction_url = prediction["urls"]["get"]

while prediction["status"] not in ["succeeded", "failed"]:
    time.sleep(2)
    prediction = requests.get(prediction_url, headers=headers).json()

if prediction["status"] != "succeeded":
    raise SystemExit("❌ La génération a échoué.")

image_url = prediction["output"][0]
img_data = requests.get(image_url).content

# --- Sauvegarde brute ---
with open(archive_generated, "wb") as f:
    f.write(img_data)
last_thumbnail_path = "data/last_thumbnail.png"
with open(last_thumbnail_path, "wb") as f:
    f.write(img_data)

print(f"✅ Image brute archivée : {archive_generated}")

# --- Commit immédiat pour l’image brute ---
commit_and_push(f"🖼️ Image brute {num_str} (qwen)")

# --- Mise à jour selected_comments.json ---
selected_comments_path = "data/selected_comments.json"
if os.path.exists(selected_comments_path):
    try:
        with open(selected_comments_path, "r", encoding="utf-8") as f:
            all_selected = json.load(f)
        if not isinstance(all_selected, list):
            all_selected = []
    except Exception:
        all_selected = []
else:
    all_selected = []

entry = dict(comment)
entry["_archive_image"] = f"archives/{num_str}_generated.png"
entry["_index"] = next_num
all_selected.append(entry)

with open(selected_comments_path, "w", encoding="utf-8") as f:
    json.dump(all_selected, f, ensure_ascii=False, indent=2)

# --- Composition finale avec miniature.png ---
final_path = None
try:
    base_img = Image.open("data/miniature.png").convert("RGBA")
    gen_img = Image.open(last_thumbnail_path).convert("RGBA")
    gen_img = gen_img.resize((785, 502))
    x, y = 458, 150
    base_img.paste(gen_img, (x, y), gen_img)

    # Texte sous l'image
    draw = ImageDraw.Draw(base_img)
    text_line = f"{author} : {text}"
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

    # Sauvegarde finale
    final_path = "data/final_thumbnail.png"
    base_img.save(final_path)
    print(f"✅ Image finale composée : {final_path}")
except Exception as e:
    print("⚠️ Impossible de composer avec miniature.png :", e)

# ✅ Mise à jour horodatage
if final_path and os.path.exists(final_path):
    now_ts = int(time.time())
    last_update_path = "data/last_update.json"
    last_update = {"timestamp": now_ts}
    with open(last_update_path, "w", encoding="utf-8") as f:
        json.dump(last_update, f)
    print(f"🕒 Horodatage mis à jour : {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now_ts))}")
else:
    print("⚠️ Horodatage NON mis à jour (pas de final_thumbnail générée).")

# --- Commit final avec la miniature ---
if final_path and os.path.exists(final_path):
    commit_and_push(f"🖼️ Miniature finale {num_str} (qwen)")

print(f"✅ Dernière miniature brute : {last_thumbnail_path}")
print(f"✅ Commentaires agrégés : {selected_comments_path} (total: {len(all_selected)})")
print("🌍 URL directe :", image_url)
