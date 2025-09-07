import json
import random
import os
import re
import time

# Charger les commentaires
with open("data/comments.json", "r", encoding="utf-8") as f:
    comments = json.load(f)

# Aucun commentaire valide
if not comments:
    print("ℹ️ Aucun commentaire valide trouvé → pas de changement.")
    with open("no_selection.flag", "w") as f:
        f.write("no selection")
    raise SystemExit(0)

# Trouver le max de likes
max_likes = max(c["likes"] for c in comments)
candidates = [c for c in comments if c["likes"] == max_likes]

# En cas d’égalité → tirage au sort
selected = random.choice(candidates)

# Nettoyer l’auteur pour nom de fichier (utile si tu veux l’afficher)
author = selected.get("author", "Anonyme")
author_safe = re.sub(r"[^a-zA-Z0-9_-]", "_", author)

os.makedirs("data", exist_ok=True)

# Sauvegarde uniquement dans selected_comment.json
with open("data/selected_comment.json", "w", encoding="utf-8") as f:
    json.dump(selected, f, ensure_ascii=False, indent=2)

# --- Logs détaillés ---
print("====================================")
print("🏆 Nouveau commentaire choisi :")
print(f"👤 Auteur : {selected['author']}")
print(f"💬 Texte  : {selected['text']}")
print(f"👍 Likes  : {selected['likes']}")
if "publishedAt" in selected:
    try:
        ts = time.strptime(selected["publishedAt"], "%Y-%m-%dT%H:%M:%SZ")
        print(f"🕒 Publié le : {time.strftime('%Y-%m-%d %H:%M:%S', ts)}")
    except Exception:
        print(f"🕒 Publié le : {selected['publishedAt']}")
print("====================================")
