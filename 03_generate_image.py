import os
import json
import requests
import time
import re
from PIL import Image, ImageDraw, ImageFont

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
if not REPLICATE_API_TOKEN:
    raise SystemExit("❌ Manque le secret REPLICATE_API_TOKEN")

# Charger le commentaire sélectionné
with open("data/selected_comment.json", "r", encoding="utf-8") as f:
    comment = json.load(f)

text = comment.get("text", "")
author = comment.get("author", "Anonyme")

author_safe = re.sub(r"[^a-zA-Z0-9_-]", "_", author)
snippet = text[:14] if text else "no_text"
snippet_safe = re.sub(r"[^a-zA-Z0-9_-]", "_", snippet)

os.makedirs("data", exist_ok=True)
os.makedirs("data/archives", exist_ok=True)

# --- Numéro global basé sur le nombre d'archives existantes ---
existing_archives = [f for f in os.listdir("data/archives") if f.lower().endswith(".png")]
global_index = len(existing_archives) + 1
archive_filename = f"{global_index:04d}_{author_safe}_{snippet_safe}.png"
archive_path = os.path.join("data/archives", archive_filename)

# --- Génération de l'image via Replicate ---
prompt = f"Une image photoréaliste représentant : {text}, haute qualité, style photographie réaliste, détails précis, lumière naturelle"
negative_prompt = "dessin, peinture, cartoon, illustration, animé, art stylisé, lowres, 3D render"

print("🎨 Prompt envoyé à Replicate :", prompt)

url = "https://api.replicate.com/v1/predictions"
headers = {
    "Authorization": f"Token {REPLICATE_API_TOKEN}",
    "Content-Type": "application/json"
}
payload = {
    "version": "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
    "input": {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "width": 1280,
        "height": 720
    }
}

response = requests.post(url, headers=headers, json=payload)
if response.status_code not in [200, 201]:
    print("❌ Erreur API Replicate :", response.text)
    raise SystemExit(1)

prediction = response.json()
prediction_url = prediction["urls"]["get"]

while prediction["status"] not in ["succeeded", "failed"]:
    time.sleep(3)
    prediction = requests.get(prediction_url, headers=headers).json()

if prediction["status"] != "succeeded":
    raise SystemExit("❌ La génération a échoué.")

image_url = prediction["output"][0]
img_data = requests.get(image_url).content

# --- Sauvegardes finales ---
with open(archive_path, "wb") as f:
    f.write(img_data)

last_thumbnail_path = "data/last_thumbnail.png"
with open(last_thumbnail_path, "wb") as f:
    f.write(img_data)

# Fichier agrégé de tous les commentaires sélectionnés
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
entry["_archive_image"] = f"archives/{archive_filename}"
entry["_index"] = global_index
all_selected.append(entry)

with open(selected_comments_path, "w", encoding="utf-8") as f:
    json.dump(all_selected, f, ensure_ascii=False, indent=2)

# --- Composition finale avec miniature.png + cadre IA + texte en bas à droite ---
final_path = None
try:
    base_img = Image.open("data/miniature.png").convert("RGBA")
    gen_img = Image.open(last_thumbnail_path).convert("RGBA")
    gen_img = gen_img.resize((785, 502))
    x, y = 458, 150
    base_img.paste(gen_img, (x, y), gen_img)

    # Charger le dernier commentaire sélectionné
    last_entry = all_selected[-1] if all_selected else comment
    author_text = last_entry.get("author", "Anonyme")
    comment_text = last_entry.get("text", "")

    draw = ImageDraw.Draw(base_img)
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = ImageFont.load_default()

    display_text = f"{author_text} : {comment_text}"

    # Retour à la ligne automatique
    max_width = gen_img.width - 40
    words = display_text.split()
    lines, line = [], ""
    for word in words:
        test_line = line + (" " if line else "") + word
        w, _ = draw.textsize(test_line, font=font)
        if w <= max_width:
            line = test_line
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)

    # Calcul dimensions du bloc texte
    line_heights = [draw.textsize(l, font=font)[1] for l in lines]
    text_height = sum(line_heights) + 10
    text_width = max(draw.textsize(l, font=font)[0] for l in lines) + 20

    # Position : sous le cadre IA, en bas à droite
    margin_bottom = 20
    margin_right = 20
    pos_x = x + gen_img.width - text_width - margin_right
    pos_y = y + gen_img.height + 10  # juste sous le cadre

    # Fond noir semi-transparent
    overlay = Image.new("RGBA", (text_width, text_height), (0, 0, 0, 150))
    base_img.paste(overlay, (pos_x, pos_y), overlay)

    # Dessiner le texte en blanc
    for i, l in enumerate(lines):
        draw.text((pos_x + 10, pos_y + 5 + i * 22), l, font=font, fill=(255, 255, 255, 255))

    final_path = "data/final_thumbnail.png"
    base_img.save(final_path)
    print(f"✅ Image finale composée avec commentaire en bas à droite : {final_path}")

except Exception as e:
    print("⚠️ Impossible de composer avec miniature.png :", e)

# ✅ Mise à jour de l'horodatage uniquement si une image finale existe
if final_path and os.path.exists(final_path):
    now_ts = int(time.time())
    last_update_path = "data/last_update.json"
    last_update = {"timestamp": now_ts}
    with open(last_update_path, "w", encoding="utf-8") as f:
        json.dump(last_update, f)
    print(f"🕒 Horodatage mis à jour : {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now_ts))}")
else:
    print("⚠️ Horodatage NON mis à jour (pas de final_thumbnail générée).")

print(f"✅ Image archivée : {archive_path}")
print(f"✅ Dernière miniature brute : {last_thumbnail_path}")
print(f"✅ Commentaires agrégés : {selected_comments_path} (total: {len(all_selected)})")
print("🌍 URL directe :", image_url)
