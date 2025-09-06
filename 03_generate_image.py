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

# --- Numéro global basé sur les archives ---
existing_archives = [f for f in os.listdir("data/archives") if f.lower().endswith(".png")]
global_index = len(existing_archives) + 1

# --- Prompt ---
prompt = (
    f"{text}. "
    "High quality, realistic, detailed, coherent with the description, 8k, sharp focus"
)
negative_prompt = (
    "low quality, blurry, deformed, distorted, text, watermark, bad anatomy, extra limbs, cropped, "
    "lowres, jpeg artifacts, worst quality, ugly, cartoonish, disfigured"
)

headers = {
    "Authorization": f"Token {REPLICATE_API_TOKEN}",
    "Content-Type": "application/json"
}
url = "https://api.replicate.com/v1/predictions"

def generate_sdxl_image():
    payload = {
        "version": "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
        "input": {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": 1280,
            "height": 720,
            "guidance_scale": 9,
            "num_inference_steps": 50
        }
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code not in (200, 201):
        print("❌ Erreur API SDXL:", response.text)
        return None

    prediction = response.json()
    prediction_url = prediction["urls"]["get"]

    while prediction["status"] not in ["succeeded", "failed"]:
        time.sleep(3)
        prediction = requests.get(prediction_url, headers=headers).json()

    if prediction["status"] != "succeeded":
        print("❌ Génération SDXL a échoué")
        return None

    image_url = prediction["output"][0]
    img_data = requests.get(image_url).content

    archive_filename = f"{global_index:04d}_{author_safe}_{snippet_safe}_SDXL.png"
    archive_path = os.path.join("data/archives", archive_filename)

    with open(archive_path, "wb") as f:
        f.write(img_data)

    print(f"✅ Image SDXL sauvegardée :", archive_path)
    return archive_path

# --- Génération SDXL ---
generated_path = generate_sdxl_image()

# --- Composer une miniature ---
final_path = None
if generated_path:
    try:
        base_img = Image.open("data/miniature.png").convert("RGBA")
        gen_img = Image.open(generated_path).convert("RGBA")
        gen_img = gen_img.resize((785, 502))

        # Position du cadre
        x, y = 458, 150
        base_img.paste(gen_img, (x, y), gen_img)

        draw = ImageDraw.Draw(base_img)
        try:
            font = ImageFont.truetype("arial.ttf", 28)
        except:
            font = ImageFont.load_default()

        text_color = (255, 255, 255, 255)
        text_start_y = y + gen_img.height + 20
        margin_right = 40

        # Auteur aligné à droite
        author_text = f"Auteur: {author}"
        aw, ah = draw.textsize(author_text, font=font)
        draw.text((x + gen_img.width - aw - margin_right, text_start_y), author_text, font=font, fill=text_color)

        # Commentaire aligné à droite avec retour dynamique
        max_width = gen_img.width - 2 * margin_right
        words = text.split()
        wrapped_lines = []
        line = ""
        for word in words:
            test_line = line + (" " if line else "") + word
            lw, _ = draw.textsize(test_line, font=font)
            if lw <= max_width:
                line = test_line
            else:
                wrapped_lines.append(line)
                line = word
        if line:
            wrapped_lines.append(line)

        for j, line in enumerate(wrapped_lines):
            lw, lh = draw.textsize(line, font=font)
            draw.text(
                (x + gen_img.width - lw - margin_right, text_start_y + 40 + j * lh),
                line,
                font=font,
                fill=text_color
            )

        final_path = "data/final_thumbnail.png"
        base_img.save(final_path)
        print(f"✅ Miniature finale composée avec texte SDXL : {final_path}")
    except Exception as e:
        print("⚠️ Impossible de composer la miniature :", e)

# --- Sauvegarder dans selected_comments.json ---
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
entry["_generated_image"] = generated_path
entry["_index"] = global_index
all_selected.append(entry)

with open(selected_comments_path, "w", encoding="utf-8") as f:
    json.dump(all_selected, f, ensure_ascii=False, indent=2)

print(f"✅ Commentaires agrégés : {selected_comments_path} (total: {len(all_selected)})")

# --- Mise à jour de l'horodatage ---
if final_path and os.path.exists(final_path):
    now_ts = int(time.time())
    last_update_path = "data/last_update.json"
    last_update = {"timestamp": now_ts}
    with open(last_update_path, "w", encoding="utf-8") as f:
        json.dump(last_update, f)
    print(f"🕒 Horodatage mis à jour : {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now_ts))}")

print("🎉 Terminé. Image générée :", generated_path)
