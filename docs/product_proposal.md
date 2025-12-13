# Proposition d'Améliorations "Trail Running & UX"

Pour augmenter l'adhésion et rendre **Kairn** incontournable pour les traileurs, voici une série de fonctionnalités axées sur l'usage réel (terrain, préparation, communauté) et "l'effet WoW" visuel.

## 1. L'Expérience Visuelle "Premium" (Effet WoW)
L'objectif est de dépasser la simple carte 2D.

*   **Prévisualisation 3D Immersive (Flyover)** :
    *   Intégrer une vue 3D (via Mapbox GL ou Cesium) permettant de "survoler" la trace.
    *   *User Value* : Mieux se rendre compte de la verticalité et de la technicité (très difficile à lire sur une carte 2D).
*   **Profil Altimétrique Interactif Avancé** :
    *   Coloriser la pente (vert < 10%, jaune < 20%, rouge > 20%, noir > 30%).
    *   Ajouter des repères visuels : "Sommet", "Ravito", "Passage technique".

## 2. Outils de Préparation Intelligents (AI & Data)
Le traileur passe beaucoup de temps à *préparer* sa sortie. Simplifions-lui la vie.

*   **Calculateur de Temps Prévisionnel (Pacing)** :
    *   L'utilisateur entre son niveau (ex: Cote ITRA ou temps sur 10km).
    *   L'algorithme estime son temps total et ses temps de passage aux points clés en fonction du D+/D-.
*   **Assistant Matériel (AI)** :
    *   En fonction de la longueur, du D+, de l'altitude max et de la saison, suggérer une "Checklist Matos" (ex: "Frontale obligatoire : passage de nuit probable", "Bâtons conseillés : pente moyenne 18%").
*   **Météo Localisée** :
    *   Afficher la météo non pas à la ville la plus proche, mais au **départ** et au **sommet** (vent, température ressentie).

## 3. Engagement Communautaire (Social)
Transformer une base de données en lieu de vie.

*   **Le concept de "Kairn" (Cairn Virtuel)** :
    *   Permettre aux utilisateurs de laisser des "Kairns" sur la carte (photos, alertes danger, points d'eau vérifiés).
    *   *Gamification* : "Constructeur de Kairns" (badge pour ceux qui documentent les sentiers).
*   **Comparaison "Trace Réelle vs Officielle"** :
    *   Si l'utilisateur upload sa propre trace d'une course, superposer automatiquement avec la trace officielle et analyser les écarts ("Jardinage" au km 12, Raccourci involontaire, etc.).

## 4. UX & Accessibilité (Simplicité)
*   **Export Montre Simplifié** :
    *   Un bouton "Envoyer vers Garmin/Suunto" direct (via API ou fichier simplifié).
*   **Filtres "Sensations"** :
    *   Au lieu de chercher juste par Km/D+, chercher par "Envie" : "Roulant & Rapide", "Technique & Aérien", "Sortie Longue Zen".
*   **Mode "Déconnecté" (App Mobile)** :
    *   (Futur) Préchargement des cartes pour l'utilisation sur le terrain sans réseau.

## 5. Idée Phare : "Le Carnet de Reconnaissance"
Une fonctionnalité unique pour les compétiteurs.
*   Permettre de découper une course en **tronçons** (ex: "Montée du Semnoz").
*   L'utilisateur peut ajouter des notes textuelles/vocales sur chaque tronçon ("Attention racine", "Relancer ici").
*   Générer un PDF/Roadbook imprimable ou consultable sur mobile.

---

### Priorités Suggérées (MVP)
1.  **Profil Altimétrique Colorisé** (Facile à implémenter, fort impact visuel).
2.  **Calculateur de Temps** (Apporte une vraie valeur ajoutée par rapport à une simple map).
3.  **Checklist Matériel AI** (Utilise votre infrastructure Gemini existante).
