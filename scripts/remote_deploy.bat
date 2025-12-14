@echo off
TITLE Kairn Freebox Deployer
COLOR 0A

echo ========================================================
echo        KAIRN - DEPLOIEMENT CLIQUABLE (FREEBOX)
echo ========================================================
echo.

:: --- CONFIGURATION (A MODIFIER UNE SEULE FOIS) ---
:: Remplacez par votre utilisateur et IP (ex: freebox@192.168.1.30)
SET SSH_TARGET=freebox@192.168.1.195
:: ------------------------------------------------

echo [1/3] Connexion a la Freebox (%SSH_TARGET%)...
echo       (Veuillez taper votre mot de passe SSH si demande)
echo [2/3] Lancement du script de deploiement...
echo       (Veuillez taper votre mot de passe SUDO si demande pour les permissions)

ssh -t %SSH_TARGET% "cd KairnGpx && chmod +x scripts/deploy_freebox_full.sh && ./scripts/deploy_freebox_full.sh"

echo.
echo [3/3] Fin de l'operation.
echo ========================================================
pause
