-- Ajout de la colonne notification_preferences à la table users
-- À exécuter sur votre base de données PostgreSQL

ALTER TABLE users 
ADD COLUMN notification_preferences JSON 
DEFAULT '{"newsletter": true, "messages": true, "tracks": true}';
