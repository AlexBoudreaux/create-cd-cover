import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os

# Set up your Spotify API credentials
os.environ['SPOTIPY_CLIENT_ID'] = 'c6f396797011483d851763702a41a68a'
os.environ['SPOTIPY_CLIENT_SECRET'] = 'fecdb4cae1714758a2ef45914beb63bb'
os.environ['SPOTIPY_REDIRECT_URI'] = 'http://localhost:8888/callback'

# Set up the Spotify client with the correct scope
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(scope='user-follow-read'))

def get_saved_artists():
    artists = []
    offset = 0
    limit = 50

    while True:
        results = sp.current_user_followed_artists(limit=limit)
        items = results['artists']['items']
        
        if not items:
            break

        for item in items:
            artist = {
                'name': item['name'],
                'image_url': item['images'][0]['url'] if item['images'] else None
            }
            artists.append(artist)
            print(f"Artist: {artist['name']}, Image URL: {artist['image_url']}")

        if results['artists']['next'] is None:
            break
        
        offset = results['artists']['cursors']['after']

    return artists

if __name__ == "__main__":
    saved_artists = get_saved_artists()
    print(f"Total saved artists: {len(saved_artists)}")