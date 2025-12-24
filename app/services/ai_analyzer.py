import google.generativeai as genai
import os
import json
from typing import Dict, Any, Optional

class AiAnalyzer:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            # Allow model override via env var, default to 2.0 Flash (More stable quotas)
            model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
            try:
                self.model = genai.GenerativeModel(model_name)
            except:
                print(f"Failed to load {model_name}, falling back to gemini-2.0-flash")
                self.model = genai.GenerativeModel('gemini-2.0-flash')
        else:
            self.model = None
            print("WARNING: GEMINI_API_KEY not found. AI features disabled.")

    def analyze_track(self, metrics: Dict[str, Any], metadata: Dict[str, Any] = None, user_title: str = None, user_description: str = None, is_race: bool = False, scenery_rating: int = None, water_count: int = None, user_tags: list = None) -> Dict[str, Any]:
        """
        Generates structured analysis including title, description, tags, technicity, and exposure.
        Returns a dictionary with keys: 'ai_title', 'ai_description', 'ai_tags', 'ai_technicity', 'ai_exposure', 'ai_surface', 'ai_path_type'.
        """
        if not self.model:
            return {
                "ai_title": None,
                "ai_description": None,
                "ai_tags": [],
                "ai_technicity": None,
                "ai_exposure": None
            }

        # Build context from metrics
        context_str = f"""
        - Distance: {metrics.get('distance_km')} km
        - Dénivelé positif: {metrics.get('elevation_gain')} m
        - Altitude max: {metrics.get('max_altitude')} m
        - Altitude min: {metrics.get('min_altitude')} m
        - Type de parcours: {metrics.get('route_type')}
        - Pente max: {metrics.get('max_slope')}%
        - Pente moyenne montée: {metrics.get('avg_slope_uphill')}%
        - Effort (km-effort): {metrics.get('km_effort')}
        - Ville/Région (si dispo): {metrics.get('location_city', 'Inconnue')}
        - Coordonnée Départ: {metrics.get('start_coords', 'Inconnu')}
        """

        # Add GPX metadata if available
        if metadata:
            name = metadata.get('name', '')
            desc = metadata.get('description', '')
            if name:
                context_str += f"\n        - Nom original du fichier GPX: {name}"
            if desc:
                context_str += f"\n        - Description originale GPX: {desc}"

        # Add User Input Context
        if user_title:
             context_str += f"\n        - Titre fourni par l'utilisateur : {user_title}"
        
        if user_description:
             context_str += f"\n        - Description fournie par l'utilisateur : {user_description}"
             
        if scenery_rating:
             context_str += f"\n        - Note Paysage (ISOLÉE - NE PAS répéter dans la description) : {scenery_rating}/5"
             
        if water_count is not None:
             context_str += f"\n        - Points d'eau (ISOLÉ - NE PAS répéter dans la description) : {water_count}"
             
        if user_tags:
             tags_str = ", ".join(user_tags)
             context_str += f"\n        - Tags/Ambiance (cochés par l'utilisateur) : {tags_str}"
        
        if is_race:
             context_str += f"\n        - CONTEXTE : C'est une COURSE OFFICIELLE (Compétition)."

        prompt = f"""
        Tu es un expert en analyse de traces GPS pour les sports outdoor (Trail, Rando, VTT).
        Analyse les données suivantes pour extraire des caractéristiques techniques précises et générer du contenu SEO.
        
        Données techniques :
        {context_str}

        Tes instructions :
        1. **TITRE (SEO)** : Titre optimisé (Massif/Lieu - Nom - Distance/D+). Priorité au titre utilisateur s'il existe.
        2. **DESCRIPTION** : 
           - Résumé professionnel et inspirant (2-4 phrases). 
           - **INTERDIT** : Ne mentionne PAS le nombre de points d'eau, la note de paysage (ex: "5/5"), ou le score de technicité chiffré dans le texte, car ces données sont affichées ailleurs.
           - Parle du type de terrain, de l'ambiance, de la difficulté ressentie, et des points de vue notables (sommets, lacs, etc. déduits de la géolocalisation ou du contexte).
        3. **TECHNICITÉ** : Estime une note de 1 à 5 (1=Facile/Piste, 5=Très Technique/Alpin/Grimpe).
        4. **EXPOSITION** : Détermine l'exposition majoritaire : "Ensoleillé" (Adret/Sud/Découvert), "Ombragé" (Ubac/Nord/Forêt), ou "Mixte".
        5. **TAGS** : Sélectionne 3-5 tags pertinents (ex: Sommet, Lac, Crête, Forêt, Roulant, Technique, Aérien...).
        6. **SURFACE** : Estime la composition en % (ex: {{"trail": 80, "asphalt": 20}}) à partir du contexte (ville vs montagne).
        7. **TYPE DE SENTIER** : Estime le type en % (ex: {{"single_track": 70, "road": 30}}).

        Réponds UNIQUEMENT au format JSON strict :
        {{
            "title": "...",
            "description": "...",
            "tags": ["...", "..."],
            "technicity_score": 3,
            "exposure": "Mixte",
            "surface_composition": {{ "trail": 80, "asphalt": 20 }},
            "path_type": {{ "single_track": 70, "wide_path": 30 }}
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
                "ai_tags": data.get("tags", []),
                "ai_technicity": data.get("technicity_score"),
                "ai_exposure": data.get("exposure"),
                "ai_surface": data.get("surface_composition"),
                "ai_path_type": data.get("path_type")
            }
        except Exception as e:
            print(f"AI Analysis failed: {e}")
            return {
                "ai_title": None,
                "ai_description": None,
                "ai_tags": [],
                "ai_technicity": None,
                "ai_exposure": None
            }

    def normalize_event(self, name: str, region: str = None, website: str = None, description: str = None) -> Dict[str, Any]:
        """
        Standardizes event nomenclature using Gemini.
        Returns:
        {
            "normalized_name": "UTMB Mont-Blanc", 
            "slug": "utmb-mont-blanc",
            "region": "Chamonix, France",
            "circuit": "UTMB World Series",
            "description": "..."
        }
        """
        if not self.model:
             return {}
             
        prompt = f"""
        Tu es un expert en gestion de courses de trail et d'événements sportifs. Ton rôle est de normaliser les données d'un événement pour qu'elles suivent une nomenclature propre, standardisée et professionnelle (Type UTMB).
        
        Données brutes reçues :
        - Nom : {name}
        - Région : {region}
        - Site Web : {website}
        - Description : {description}
        
        Instructions de normalisation :
        1. **Nom** : Doit être le nom officiel court et propre. Ex: "Marathon du Mont-Blanc" (pas "42km du mont blanc"). En cas d'acronyme célèbre (UTMB, GRP), utilise le format "Acronyme Nom-Complet" (ex: "UTMB Mont-Blanc") ou juste le nom officiel s'il est très connu.
        2. **Slug** : Format url-friendly (kebab-case). Ex: "utmb-mont-blanc".
        3. **Région** : Format "Ville Principale (Département/Pays)". Ex: "Chamonix (74)".
        4. **Circuit** : Si l'événement fait partie d'un circuit connu (UTMB World Series, Golden Trail Series, Spartanguill), indique-le. Sinon null.
        5. **Description** : Rédige une description courte (2 phrases), pro et marketing, en français.
        
        Réponds UNIQUEMENT au format JSON strict :
        {{
            "normalized_name": "...",
            "slug": "...",
            "region": "...",
            "circuit": "...",
            "description": "..."
        }}
        """
        
        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            return json.loads(text)
        except Exception as e:
            print(f"AI Normalization failed: {e}")
            return {}
