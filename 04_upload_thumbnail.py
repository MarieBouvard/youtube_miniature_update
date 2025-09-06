import os
import sys
import time
import requests
import google.auth.transport.requests
import google.oauth2.credentials
import googleapiclient.discovery

# Récupération des secrets (variables d’environnement injectées par GitHub)
CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID")
CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN")
VIDEO_ID = os.getenv("YOUTUBE_VIDEO_ID")

if not all([CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN, VIDEO_ID]):
    sys.exit("❌ Manque un secret GitHub (YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN, YOUTUBE_VIDEO_ID)")

# Fichier miniature attendu
THUMBNAIL_PATH = "data/final_thumbnail.png"
if not os.path.exists(THUMBNAIL_PATH):
    sys.exit(f"❌ Miniature introuvable : {THUMBNAIL_PATH}")

# Scope OK pour thumbnails.set
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def main():
    # Credentials à partir du refresh token
    creds = google.oauth2.credentials.Credentials(
        None,
        refresh_token=REFRESH_TOKEN,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES
    )

    # Rafraîchir l'access_token
    request = google.auth.transport.requests.Request()
    creds.refresh(request)

    # Client YouTube API
    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=creds)

    # Upload de la miniature
    req = youtube.thumbnails().set(
        videoId=VIDEO_ID,
        media_body=THUMBNAIL_PATH
    )
    resp = req.execute()
    print("✅ Miniature mise à jour :", resp)

    # URLs anti-cache pour vérification visuelle
    ts = int(time.time())
    sizes = ["default", "mqdefault", "hqdefault", "sddefault", "maxresdefault"]
    print("🔗 Vérifie les vignettes (anti-cache) :")
    for s in sizes:
        url = f"https://i.ytimg.com/vi/{VIDEO_ID}/{s}.jpg?nocache={ts}"
        print(f" - {s}: {url}")

    # (Optionnel) Tester une récupération pour voir si le CDN sert la nouvelle image
    try:
        test_url = f"https://i.ytimg.com/vi/{VIDEO_ID}/maxresdefault.jpg?nocache={ts}"
        r = requests.get(test_url, timeout=10)
        print(f"🧪 Test fetch maxresdefault: HTTP {r.status_code}, {len(r.content)} octets")
    except Exception as e:
        print("⚠️ Impossible de tester le fetch de l’image :", e)

if __name__ == "__main__":
    main()
