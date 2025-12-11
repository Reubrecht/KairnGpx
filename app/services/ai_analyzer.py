import google.generativeai as genai
import os
import json
from typing import Dict, Any, Optional

class AiAnalyzer:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            # Try 2.0 Flash Exp first (Fast & New), fallback to 1.5 Flash
            try:
                self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
            except:
                self.model = genai.GenerativeModel('gemini-1.5-flash')
        else:
            self.model = None
            print("WARNING: GEMINI_API_KEY not found. AI features disabled.")

    def analyze_track(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates a title, description, and tags based on GPX metrics.
        Returns a dictionary with keys: 'ai_title', 'ai_description', 'ai_tags'.
        """
        if not self.model:
            return {
                "ai_title": None,
                "ai_description": None,
                "ai_tags": []
            }

        prompt = f"""
        Tu es un expert en analyse de données géographiques et sportives. Analyse les métriques suivantes d'une trace GPX :
        - Distance: {metrics.get('distance_km')} km
        - Dénivelé positif: {metrics.get('elevation_gain')} m
        - Altitude max: {metrics.get('max_altitude')} m
        - Type de parcours: {metrics.get('route_type')}
        - Pente max: {metrics.get('max_slope')}%
        - Effort (km-effort): {metrics.get('km_effort')}
        - Ville/Région (si dispo): {metrics.get('location_city', 'Inconnue')}

        Tâche :
        1. Rédige un titre au format STRICT suivant : "Lieu (Ville ou Massif principal) - Distance km - Dénivelé m". Exemple: "Chamonix - 42km - 2500m".
        2. Rédige une description FACTUELLE et TECHNIQUE (2-3 phrases). Décris le profil, la difficulté objective et le type d'effort sans émotions ni marketing.
        3. Suggère 3 à 5 tags pertinents (ex: "Panoramique", "Vertical", "Roulant", "Technique", "Forêt", etc.).

        Réponds UNIQUEMENT au format JSON strict comme ceci :
        {{
            "title": "...",
            "description": "...",
            "tags": ["...", "..."]
        }}
        """

        try:
            response = self.model.generate_content(prompt)
            # Clean response if necessary (remove markdown ```json ... ```)
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            
            data = json.loads(text)
            
            return {
                "ai_title": data.get("title"),
                "ai_description": data.get("description"),
                "ai_tags": data.get("tags", [])
            }
        except Exception as e:
            print(f"AI Analysis failed: {e}")
            return {
                "ai_title": None,
                "ai_description": None,
                "ai_tags": []
            }
