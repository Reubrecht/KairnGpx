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
        Generates a title, description, and tags based on GPX metrics, metadata, and user input.
        Returns a dictionary with keys: 'ai_title', 'ai_description', 'ai_tags'.
        """
        if not self.model:
            return {
                "ai_title": None,
                "ai_description": None,
                "ai_tags": []
            }

        # Build context from metrics
        context_str = f"""
        - Distance: {metrics.get('distance_km')} km
        - Dénivelé positif: {metrics.get('elevation_gain')} m
        - Altitude max: {metrics.get('max_altitude')} m
        - Type de parcours: {metrics.get('route_type')}
        - Pente max: {metrics.get('max_slope')}%
        - Effort (km-effort): {metrics.get('km_effort')}
        - Ville/Région (si dispo): {metrics.get('location_city', 'Inconnue')}
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
             context_str += f"\n        - Note Paysage (donnée utilisateur) : {scenery_rating}/5"
             
        if water_count is not None:
             context_str += f"\n        - Points d'eau (donnée utilisateur) : {water_count}"
             
        if user_tags:
             tags_str = ", ".join(user_tags)
             context_str += f"\n        - Tags/Ambiance (cochés par l'utilisateur) : {tags_str}"
        
        if is_race:
             context_str += f"\n        - CONTEXTE : C'est une COURSE OFFICIELLE (Compétition)."

        prompt = f"""
        Tu es un expert en référencement (SEO) et en analyse de données pour le trail running et les sports outdoor (Randonnée, VTT, Cyclisme, Alpinisme, Ski de Rando). 
        Ton but est de maximiser la visibilité et l'attractivité de la trace GPX analysée pour une communauté de passionnés.
        
        Données techniques :
        {context_str}

        Tes instructions :
        1. **TITRE (SEO)** : Génère un titre optimisé pour la recherche (5-8 mots max).
           - Format souhaité : "Massif/Lieu - Nom de l'itinéraire - Distance/D+ " ou "Activité - Lieu - Point fort".
           - **IMPORTANT** : Base-toi prioritairement sur le "Titre fourni par l'utilisateur" ou le "Nom original du fichier GPX". Améliore-le pour le SEO (ajoute le lieu s'il manque), mais NE L'INVENTE PAS totalement si l'utilisateur a été précis.
           - Si c'est une COURSE OFFICIELLE : Le titre DOIT inclure le nom de la course, l'année (si dispo) et la distance. Ex: "Marathon du Mont-Blanc 2025 - 42km".
           - Mentionne obligatoirement le massif ou la ville principale.

        2. **DESCRIPTION (Contenu)** : Rédige une description de 2 à 4 phrases.
           - Ton ton doit être professionnel, technique mais inspirant.
           - Si c'est une COURSE OFFICIELLE : Mentionne que c'est un parcours de compétition, parle de l'exigence et de l'ambiance typique de cette course.
           - **IMPORTANT** : Si une "Description fournie par l'utilisateur" est présente, UTILISE-LA COMME SOURCE PRINCIPALE. Reformule-la pour qu'elle soit plus pro, corrige les fautes, mais conserve le sens et les détails donnés par l'utilisateur.
           - Intègre les informations fournies (Note Paysage, Points d'eau, Tags utilisateur) dans le récit si pertinent (ex: "Très beau parcours panoramique avec 2 points d'eau...").
           - Si pas de description utilisateur, base-toi sur la description originale GPX ou génère-en une standard.
           - Mentionne le type de terrain (ex: technique, roulant) et les points d'intérêts.

        3. **TAGS (Catégorisation)** : Sélectionne STRICTEMENT 3 à 5 tags parmi cette liste fermée :
           ["Roulant", "Technique", "Vertical", "Aérien", "Boucle", "Aller-Retour", "Sommet", "Lac", "Forêt", "Crête", "Skyrunning", "Ultra", "Off-Road", "Sentier", "Piste"]
           - **IMPORTANT** : Si l'utilisateur a déjà coché des tags ("Tags/Ambiance"), essaie de sélectionner les équivalents dans la liste fermée ci-dessus s'ils sont pertinents.

        Réponds UNIQUEMENT au format JSON strict (sans markdown autour si possible, juste le json) :
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
