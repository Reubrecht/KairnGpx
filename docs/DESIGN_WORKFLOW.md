# Workflow Design : De PNG vers SVG (Vectorisation)

Ce guide décrit le workflow idéal pour moderniser l'interface de **Kairn** en passant d'assets matriciels (PNG/JPG) à des assets vectoriels (SVG), plus propres, légers et manipulables via CSS.

## 🛠️ Choix de l'Outil

### Recommandation : **Penpot** (ou Figma)
Nous recommandons **Penpot** pour ce projet car :
1.  **Open Source & Gratuit** : Alignement avec la philosophie du projet.
2.  **Standards Web** : Penpot utilise le SVG comme format natif, ce qui garantit un code exporté très propre.
3.  **Accessibilité** : Navigateur web, pas d'installation.

> *Note : Figma est tout aussi capable, mais l'export SVG nécessite souvent un nettoyage supplémentaire.*

---

## 🚀 Le Workflow "Clean UI"

### Étape 1 : Import & Calque de Référence
Ne tentez pas de "convertir" automatiquement le PNG. Pour un résultat "propre", il faut redessiner.
1.  Créez un file sur Penpot/Figma.
2.  Importez votre PNG (ex: `logo.png`) et verrouillez le calque avec une opacité de 50%.
3.  C'est votre guide visuel.

### Étape 2 : Redessiner (Vectorisation Manuelle)
Utilisez les outils vectoriels (Plume, Formes géométriques simples) pour reconstruire l'image par dessus.
-   **Pourquoi ?** L'auto-trace crée des milliers de points inutiles. Le dessin manuel garantit des courbes mathématiques parfaites et un poids de fichier minuscule (ex: 2ko vs 50ko).
-   Utilisez des **nombres entiers** pour les dimensions et positionnements (Pixel Perfect) pour éviter le flou sur les écrans bord-à-bord.

### Étape 3 : Convention de Couleurs
Pour que l'icône/logo soit coloriage via TailwindCSS :
-   Définissez la couleur de remplissage (fill) ou de contour (stroke) sur **Noir (#000000)** dans l'outil de design.
-   Lors de l'export, ou dans le code, nous remplacerons ce noir par `currentColor`.

### Étape 4 : Export & Optimisation
1.  Exportez en **SVG**.
2.  **OBLIGATOIRE** : Passez le SVG dans [SVGOMG](https://jakearchibald.github.io/svgomg/) (ou utilisez CLI `svgo`).
    -   Activez *"Remove dimensions"* (width/height).
    -   Activez *"Prefer viewBox"*.
    -   Cela rend le SVG responsive par défaut.

### Étape 5 : Intégration dans Kairn

#### Méthode A : Inline (Pour les logos/icônes uniques)
Copiez le code `<svg>...</svg>` directement dans le template Jinja2.
```html
<!-- Exemple Logo avec Tailwind -->
<svg class="h-10 w-auto text-brand-600 fill-current" viewBox="...">
    <!-- ... path vectoriel ... -->
</svg>
```
*Avantage* : Vous contrôlez la couleur avec `text-red-500`, `text-blue-600` directement en CSS.

#### Méthode B : Templates Partiels (Pour réutilisation)
Créez `app/templates/components/icons/logo.html` contenant le SVG.
```jinja
{% include "components/icons/logo.html" %}
```

---

## ✅ Avantages de cette transition
1.  **Netteté Infinie** : Parfait sur mobile rétina et écran 4K.
2.  **Poids Plume** : Un logo SVG bien dessiné pèse souvent < 1KB (contre 20-50KB pour un PNG).
3.  **Themable** : Dark mode automatique (le SVG change de couleur avec le texte).
4.  **Animation** : Possible d'animer les tracés avec CSS.
