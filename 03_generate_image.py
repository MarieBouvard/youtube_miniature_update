import os
import json
import requests
import time
import re
import subprocess
from datetime import datetime
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

os.makedirs("data", exist_ok=True)
os.makedirs("data/archives", exist_ok=True)

# --- Numéro d'archive suivant ---
existing_archives = [f for f in os.listdir("data/archives") if f.lower().endswith(".png")]
next_num = len(existing_archives) + 1
num_str = f"{next_num:04d}"

# --- Construire nom avec auteur + snippet + date ---
author_part = re.sub(r"[^a-zA-Z0-9_-]", "_", author)[:20] or "Anonyme"
snippet_part = re.sub(r"[^a-zA-Z0-9_-]", "_", text[:20]) or "no_text"
date_part = datetime.now().strftime("%Y-%m-%d")

archive_generated = os.path.join(
    "data/archives",
    f"{num_str}_{author_part}_{snippet_part}_{date_part}.png"
)

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

# --- Sauvegarde temporaire de l'image brute ---
last_thumbnail_path = "data/last_thumbnail.png"
with open(last_thumbnail_path, "wb") as f:
    f.write(img_data)

print("✅ Image générée téléchargée")

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
entry["_archive_image"] = f"archives/{os.path.basename(archive_generated)}"
entry["_index"] = next_num
all_selected.append(entry)

with open(selected_comments_path, "w", encoding="utf-8") as f:
    json.dump(all_selected, f, ensure_ascii=False, indent=2)

# --- Composition finale avec miniature.png ---
final_path = None
try:
    base_img = Image.open("data/miniature.png").convert("RGBA")
    gen_img = Image.open(last_thumbnail_path).convert("RGBA")

    # 📌 Nouvelles dimensions et coordonnées
    gen_img = gen_img.resize((872, 557))
    x, y = 32, 85
    base_img.paste(gen_img, (x, y), gen_img)

    # Texte sous l'image (aligné à gauche + retour à la ligne auto)
    draw = ImageDraw.Draw(base_img)
    text_line = f"{author} : {text}"
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 20)
    except Exception:
        font = ImageFont.load_default()

    max_width = 872
    words = text_line.split()
    lines = []
    current_line = ""

    for word in words:
        test_line = current_line + (" " if current_line else "") + word
        bbox = draw.textbbox((0, 0), test_line, font=font)
        w = bbox[2] - bbox[0]
        if w <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)

    text_y = y + 562 + 10
    for line in lines:
        draw.text((x, text_y), line, font=font, fill="white")
        bbox = draw.textbbox((0, 0), line, font=font)
        line_height = bbox[3] - bbox[1]
        text_y += line_height + 5

    # --- Ajouter surminiature.png par-dessus ---
    overlay_path = "data/surminiature.png"
    if os.path.exists(overlay_path):
        overlay = Image.open(overlay_path).convert("RGBA")
        if overlay.size != base_img.size:
            overlay = overlay.resize(base_img.size)
        base_img.alpha_composite(overlay)
        print("✅ surminiature.png ajouté par-dessus")
    else:
        print("⚠️ surminiature.png introuvable, montage sans overlay")

    # Sauvegarde finale (miniature + archive)
    final_path = "data/final_thumbnail.png"
    base_img.save(final_path)
    base_img.save(archive_generated)
    print(f"✅ Montage final composé et archivé : {archive_generated}")

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

print(f"✅ Dernière miniature finale : {final_path}")
print(f"✅ Commentaires agrégés : {selected_comments_path} (total: {len(all_selected)})")
print("🌍 URL directe :", image_url)
