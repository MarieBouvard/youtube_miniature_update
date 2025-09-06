import os, sys, time, random
import google.auth.transport.requests
import google.oauth2.credentials
import googleapiclient.discovery
from PIL import Image  # pip install pillow
import requests

CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID")
CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN")
VIDEO_ID = os.getenv("YOUTUBE_VIDEO_ID")

if not all([CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN, VIDEO_ID]):
    sys.exit("❌ Manque un secret GitHub")

SRC_THUMB = "data/final_thumbnail.png"
if not os.path.exists(SRC_THUMB):
    sys.exit(f"❌ Miniature introuvable : {SRC_THUMB}")

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def make_jpeg_variation(src_path: str) -> str:
    """Recode en JPEG avec un quality aléatoire + métadonnée pour changer les octets."""
    tmp_path = "data/final_thumbnail_tmp_upload.jpg"
    img = Image.open(src_path).convert("RGB")
    # S'assure du 16:9 (optionnel) : si besoin, redimensionne en 1280x720
    img = img.resize((1280, 720), Image.LANCZOS)
    quality = random.randint(88, 96)
    img.save(tmp_path, format="JPEG", quality=quality, optimize=True)
    return tmp_path

def main():
    creds = google.oauth2.credentials.Credentials(
        None,
        refresh_token=REFRESH_TOKEN,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES
    )
    req = google.auth.transport.requests.Request()
    creds.refresh(req)

    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=creds)

    # 1) Re-encode en JPEG pour forcer un nouveau hash
    upload_path = make_jpeg_variation(SRC_THUMB)

    # 2) Upload
    resp = youtube.thumbnails().set(
        videoId=VIDEO_ID,
        media_body=upload_path
    ).execute()
    print("✅ Miniature mise à jour :", resp)

    # 3) Vérification : URLs anti-cache
    ts = int(time.time())
    sizes = ["default", "mqdefault", "hqdefault", "sddefault", "maxresdefault"]
    print("🔗 Vérifie les vignettes (anti-cache) :")
    for s in sizes:
        url = f"https://i.ytimg.com/vi/{VIDEO_ID}/{s}.jpg?nocache={ts}"
        print(f" - {s}: {url}")

    # 4) (Optionnel) Ping l'image pour voir la nouvelle taille
    test_url = f"https://i.ytimg.com/vi/{VIDEO_ID}/maxresdefault.jpg?nocache={ts}"
    try:
        r = requests.get(test_url, timeout=10)
        print(f"🧪 Fetch maxresdefault: HTTP {r.status_code}, {len(r.content)} octets")
    except Exception as e:
        print("⚠️ Test fetch impossible :", e)

if __name__ == "__main__":
    main()
