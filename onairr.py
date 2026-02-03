import os, requests
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, jsonify, request
import xml.etree.ElementTree as ET

load_dotenv()

app = Flask(__name__)

class PlexAPI:
    def __init__(self, base_url, token):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.session = requests.Session()

    def get_server_info(self):
        try:
            url = f"{self.base_url}/identity"
            params = {'X-Plex-Token': self.token}
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()

            root = ET.fromstring(response.content)
            return root.get('machineIdentifier', '')
        except Exception as e:
            print(f"Error getting server info: {e}")
            return ''
    
    def get_sessions(self):
        try:
            url = f"{self.base_url}/status/sessions"
            params = {'X-Plex-Token': self.token}
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            sessions = []
            
            for video in root.findall('.//Video') + root.findall('.//Track'):
                session = self._parse_session(video)
                if session:
                    sessions.append(session)
            
            return sessions
        
        except requests.exceptions.RequestException as e:
            print(f"Error fetching sessions: {e}")
            return []
        except ET.ParseError as e:
            print(f"Error parsing XML: {e}")
            return []
        
    def _get_cast(self, element):
        actors = []
        for role in element.findall('.//Role'):
            actor_name = role.get('tag', '')
            if actor_name:
                actors.append({
                    'name': actor_name
                })
        return actors
    
    def _get_directors(self, element):
        directors = []
        for director in element.findall('.//Director'):
            director_name = director.get('tag', '')
            if director_name:
                directors.append(director_name)
        return directors
    
    def _parse_session(self, element):
        try:
            session = {
                'sessionKey': element.get('sessionKey', ''),
                'title': element.get('title', 'Unknown'),
                'type': element.get('type', 'unknown'),
                'year': element.get('year', ''),
                'rating': element.get('contentRating', ''),
                'summary': element.get('summary', ''),
                'thumb': element.get('grandparentThumb') if element.get('type') == 'episode' else element.get('thumb', ''),
                'art': element.get('art', ''),
                'actors': self._get_cast(element)[:3],
                'directors': self._get_directors(element)[:1],
                'ratingKey': element.get('ratingKey' ,''),
                'grandparentRatingKey': element.get('grandparentRatingKey', ''),
                'parentRatingKey': element.get('parentRatingKey', ''),
                'slug': element.get('slug', ''),
                'grandparentSlug': element.get('grandparentSlug', ''),
                'parentSlug': element.get('parentSlug', ''),
            }
            
            if element.get('type') == 'episode':
                session['show_title'] = element.get('grandparentTitle', '')
                session['season'] = element.get('parentIndex', '')
                session['episode'] = element.get('index', '')
            
            if element.get('type') == 'track':
                session['artist'] = element.get('grandparentTitle', '')
                session['album'] = element.get('parentTitle', '')
            
            return session
        
        except (ValueError, AttributeError) as e:
            print(f"Error parsing session: {e}")
            return None

plex_token = os.getenv('PLEX_TOKEN')
plex_url = os.getenv('PLEX_URL', 'http://localhost:32400')
links_bool = os.getenv('ENABLE_LINKS')

if not plex_token:
    print("Warning: PLEX_TOKEN not found in environment variables")
    plex_api = None
else:
    plex_api = PlexAPI(plex_url, plex_token)

@app.route('/')
def index():
    return render_template('index.html', links_bool=links_bool)

@app.route('/api/sessions')
def api_sessions():
    if not plex_api:
        return jsonify({'error': 'Plex API not configured'}), 500
    
    sessions = plex_api.get_sessions()

    return jsonify({
        'sessions': sessions,
        'count': len(sessions),
        'last_updated': datetime.now().isoformat()
    })

@app.route('/api/artwork/<path:thumb_path>')
def get_artwork(thumb_path):
    if not plex_api:
        return '', 404
    
    try:
        artwork_url = f"{plex_api.base_url}/{thumb_path}?X-Plex-Token={plex_api.token}"
        response = requests.get(artwork_url, timeout=30)
        return response.content, response.status_code, {'Content-Type': response.headers.get('Content-Type', 'image/jpeg')}
    except:
        return '', 404

@app.route('/api/open-in-plex', methods=['POST'])
def open_in_plex():
    if not plex_api:
        return jsonify({'error': 'Plex API not configured'}), 500
    
    try:
        data = request.get_json()
        session_type = data.get('type')
        rating_key = data.get('ratingKey')
        grandparent_key = data.get('grandparentRatingKey')
        parent_key = data.get('parentRatingKey')
        is_mobile = data.get('isMobile', False)
        user_agent = data.get('userAgent', '')
        slug = data.get('slug', '')
        grandparent_slug = data.get('grandparentSlug', '')
        parent_slug = data.get('parentSlug', '')
        
        if session_type == 'episode':
            target_key = grandparent_key if grandparent_key else rating_key
            target_slug = grandparent_slug if grandparent_slug else slug
            url_type = 'show'
        elif session_type == 'track':
            target_key = parent_key if parent_key else rating_key
            target_slug = parent_slug if parent_slug else slug
            url_type = 'album'
        else:
            target_key = rating_key
            target_slug = slug
            url_type = 'movie'
        
        if not target_key:
            return jsonify({'error': 'Invalid session data'}), 400
        
        machine_id = plex_api.get_server_info()
        if not machine_id:
            return jsonify({'error': 'Could not get server info'}), 500
        
        web_fallback = f"https://app.plex.tv/desktop/#!/server/{machine_id}/details?key=/library/metadata/{target_key}"

        if is_mobile:
            is_android = 'android' in user_agent.lower()

            if is_android and target_slug and url_type in ['movie', 'show']:
                android_url = f"https://watch.plex.tv/{url_type}/{target_slug}"
                return jsonify({
                    'url': android_url,
                    'platform': 'android'
                })
            else:
                encoded_key = f"%2Flibrary%2Fmetadata%2F{target_key}&metadataType=1"
                ios_url = f"plex://preplay/?metadataKey={encoded_key}&server={machine_id}"
                return jsonify({
                    'url': ios_url,
                    'platform': 'ios'
                })
        else:
            return jsonify({'url': web_fallback})
        
    except Exception as e:
        print(f"Error generating Plex URL: {e}")
        return jsonify({'error': 'Failed to generate URL'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=2477)