# Installation de PostgreSQL & PostGIS sur Windows

Ce guide vous accompagne pour installer une base de données robuste directement sur votre machine, sans Docker.

## 1. Télécharger et Installer PostgreSQL
1.  Allez sur la page de téléchargement officielle : [EnterpriseDB PostgreSQL Installer](https://www.enterprisedb.com/downloads/postgres-postgresql-downloads).
2.  Téléchargez la version **16.x** pour Windows x86-64.
3.  Lancez l'installateur (`postgresql-16.x-windows-x64.exe`).
4.  **Important pendant l'installation** :
    *   Laissez les composants par défaut cochés.
    *   **Mot de passe** : Choisissez `postgres` (simple pour le dev local) ou notez-le bien.
    *   **Port** : Laissez `5432`.
    *   **Locale** : Laissez par défaut.
5.  À la fin, l'installateur vous demandera "Launch Stack Builder at exit?". **COCHEZ OUI** et cliquez sur Finish.

## 2. Installer PostGIS (via Stack Builder)
Le "Stack Builder" va se lancer (sinon, cherchez "Stack Builder" dans le menu Démarrer).
1.  Sélectionnez votre installation PostgreSQL 16 dans la liste déroulante et faites `Next`.
2.  Dépliez la branche **Spatial Extensions**.
3.  Cochez **PostGIS 3.x Bundle for PostgreSQL 16** (la version la plus récente).
4.  Faites `Next` jusqu'à ce que l'installation de PostGIS démarre.
5.  Pendant l'installation de PostGIS : 
    *   Acceptez les composants par défaut.
    *   Dites "Yes" pour créer la base spatiale template si demandé.
    *   Acceptez toutes les variables d'environnement (GDAL_DATA, etc.).

## 3. Créer la base de données Kairn
Utilisons **pgAdmin 4** (installé avec PostgreSQL) pour créer votre base.
1.  Lancez **pgAdmin 4** (Menu Démarrer).
2.  Dans la colonne de gauche, double-cliquez sur "Servers" > "PostgreSQL 16" (entrez votre mot de passe).
3.  Faites un clic droit sur **Databases** > **Create** > **Database...**.
4.  **Database**: `kairn`.
5.  Cliquez sur **Save**.

## 4. Activer PostGIS
Maintenant, on active l'extension spatiale sur votre nouvelle base.
1.  Dépliez votre nouvelle base `kairn` dans la colonne de gauche.
2.  Faites un clic droit sur `kairn` > **Query Tool**.
3.  Tapez la commande suivante et cliquez sur le bouton "Play" (▶️) :
    ```sql
    CREATE EXTENSION postgis;
    ```
4.  Vous devriez voir "CREATE EXTENSION" dans les messages.

## 5. C'est prêt !
Prévenez-moi quand vous avez terminé ces étapes. Je mettrai ensuite à jour votre fichier `local.env` pour connecter l'application.
