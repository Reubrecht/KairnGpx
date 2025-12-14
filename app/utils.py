import hashlib
import unicodedata
import re
from geopy.geocoders import Nominatim
import markdown

def slugify(text: str) -> str:
    """
    Generate a slug from the given text.
    """
    # Normalized + remove accents
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    text = re.sub(r'[^\w\s-]', '', text).lower()
    return re.sub(r'[-\s]+', '-', text).strip('-')

def calculate_file_hash(file_content: bytes) -> str:
    """
    Calculate SHA256 hash of file content.
    """
    return hashlib.sha256(file_content).hexdigest()

def get_location_info(lat: float, lon: float):
    """
    Reverse geocode coordinates to get city, region, country.
    """
    geolocator = Nominatim(user_agent="kairn_trail_app_v1")
    try:
        location = geolocator.reverse(f"{lat}, {lon}", language="fr", timeout=5)
        if location and location.raw.get('address'):
            address = location.raw['address']
            city = address.get('city') or address.get('town') or address.get('village') or address.get('hamlet') or "Unknown"
            region = address.get('state') or address.get('region') or address.get('county') or "Unknown"
            country = address.get('country') or "Unknown"
            return city, region, country
    except Exception as e:
        print(f"Geocoding error: {e}")
    return "Unknown", "Unknown", "Unknown"

def markdown_filter(text):
    if text:
        return markdown.markdown(text)
    return ""
