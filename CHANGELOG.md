# Journal des versions

## v1.1.6 — 3 septembre 2026

- **PDF amélioré** :
  - Montants et dates au format français (`1 234,56 €`, `JJ/MM/AAAA`).
  - Ligne **Date d'émission / Échéance** (échéance = date + 30 j, réglable via
    `delai_paiement_jours`).
  - **Mentions légales** ajoutées : conditions de règlement, pénalités de
    retard + indemnité forfaitaire 40 € ; « TVA non applicable, art. 293 B du
    CGI » automatiquement si la facture est sans TVA.
  - Pied de page : **IBAN / BIC** (formatés) au lieu du RIB brut ;
    numérotation **« Page X / Y »**.
  - Tableau épuré (colonne « TVA % » par ligne retirée, en-tête foncé),
    bloc totaux avec « Net à payer TTC » mis en avant.
  - Nouvelles clés optionnelles dans `MY_INFO` : `iban`, `bic`,
    `tva_intracom`, `delai_paiement_jours`, `mentions_legales`,
    `pied_de_page`, `reference_client`.

## v1.1.5 — 3 septembre 2026

- **Correctif (suite)** : la fenêtre de connexion à la base ne s'affichait
  toujours pas. Toute la séquence de démarrage (test BDD, fenêtre de config,
  init) s'exécute désormais **dans** la boucle d'événements Tk, seul contexte
  où les fenêtres modales fonctionnent de façon fiable. `grab_set` non
  bloquant, plus de `wait_visibility`.
- Traces de démarrage jusqu'à l'intérieur de la fenêtre de config.

## v1.1.4 — 3 septembre 2026

- **Correctif : l'application ne s'ouvrait plus.** Le blocage venait de la
  fenêtre de connexion à la base : elle était « transient » de la fenêtre
  principale masquée, ce qui la rendait invisible sous Windows tout en gelant
  l'application. La fenêtre s'affiche désormais toujours, au premier plan.
- Trace de démarrage complétée jusqu'à l'affichage de cette fenêtre.

## v1.1.3 — 3 septembre 2026

- **Correctif démarrage** : la vérification automatique de mise à jour au
  lancement (ajoutée en 1.0.5) est retirée — c'est elle qui empêchait
  l'application de s'ouvrir. La mise à jour reste accessible via
  *Aide → Vérifier les mises à jour*.
- Build ramené au strict nécessaire : plus de `--icon` ni de ressource de
  version (une ressource PE mal formée peut empêcher le chargement de l'exe),
  retour à Python 3.13.
- `facturation-boot.log` : journal de démarrage étape par étape (à côté de
  l'exe et dans `%TEMP%`) pour localiser tout blocage.

## v1.1.2 — 3 septembre 2026

- La release fournit en plus **`Facturation-debug-<version>.exe`** : même
  application mais avec une fenêtre console qui affiche l'erreur exacte quand
  « rien ne se passe » au démarrage. La fenêtre reste ouverte sur l'erreur.
- Python de compilation ramené à **3.12** (compatible toutes éditions de
  Windows 10/11 ; 3.13 exige Windows 10 1809 minimum).

## v1.1.1 — 3 septembre 2026

- Retour à un **seul fichier `Facturation.exe`** (plus de dossier `_internal`).
  Les garde-fous de la 1.1.0 sont conservés : `psycopg2` embarqué en entier,
  ressource de version Windows, compression UPX désactivée, et surtout le
  **journal d'erreur au démarrage** (`facturation-error.log` à côté de l'exe et
  dans `%TEMP%`) qui explique tout refus de démarrage.
- Mise à jour automatique de nouveau basée sur l'échange d'un `.exe`.

## v1.1.0 — 2 septembre 2026

- **Distribution en dossier** : l'application n'est plus un unique `.exe` mais
  un dossier `Facturation` livré dans une archive `Facturation-<version>.zip`.
  Ce format déclenche beaucoup moins de faux positifs antivirus / Windows
  Defender que l'exécutable « tout-en-un ». Décompressez l'archive et lancez
  `Facturation\Facturation.exe` (gardez le dossier entier).
- **Journal d'erreur au démarrage** : si l'application ne démarre pas, un
  rapport complet est écrit dans `facturation-error.log` (à côté de l'exe et
  dans `%TEMP%`) et une fenêtre d'erreur l'indique. Fini le double-clic qui ne
  fait rien du tout.
- **Mise à jour automatique adaptée** : elle télécharge désormais l'archive
  `.zip` et remplace le dossier complet de l'application, puis redémarre. En
  cas d'échec, un message indique comment mettre à jour à la main.
- **Ressource de version Windows** (éditeur Hytris, description, numéro de
  version) intégrée au binaire, et compression UPX désactivée : deux mesures
  supplémentaires contre les faux positifs antivirus.
- Le pilote PostgreSQL (`psycopg2`) est maintenant embarqué en entier (module,
  extension binaire et DLL `libpq`) : plus de démarrage impossible faute de
  DLL manquante.

## v1.0.9 — 2 septembre 2026

- Configuration de la base par fenêtre : au premier lancement, l'application
  demande hôte / port / base / utilisateur / mot de passe, avec un bouton
  « Tester la connexion ». Plus de fichier à créer à la main.
- Menu **Paramètres → Connexion à la base de données…** pour modifier ces
  informations à tout moment (prises en compte sans redémarrer).
- Config enregistrée dans `%APPDATA%\Facturation\db_config.ini` (Windows) ou
  `~/.config/facturation/db_config.ini`.
- Icône et nom de l'application aux couleurs Hytris ; le titre n'affiche plus
  « (Tkinter) ».

## v1.0.8 — 2 septembre 2026

- Dépôt passé en public : les identifiants de la base de données ne sont plus
  dans le code. Ils se lisent depuis `db_config.ini` (à côté de l'exe) ou les
  variables d'environnement `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` /
  `DB_PASSWORD`. Voir `db_config.ini.example`.
- Message clair au démarrage si la configuration de la base est absente.
- Mise à jour automatique : plus besoin de jeton, le dépôt étant public
  (un jeton reste accepté en option pour la limite de débit de l'API).

## v1.0.7 — 2 septembre 2026

- Mise à jour : le dépôt étant privé, l'updater utilise désormais un jeton
  GitHub en lecture seule, lu depuis `update_token.txt` (à côté de l'exe) ou la
  variable d'environnement `FACT_UPDATE_TOKEN`. Sans jeton : rien ne se passe au
  démarrage, et le menu l'indique.
- Téléchargement des assets via l'API GitHub (fonctionne sur dépôt privé).
- Journal de diagnostic : `%TEMP%\facturation_update.log`.

## v1.0.6 — 2 septembre 2026

- Barre d'état en bas : affiche la version en cours (permet de vérifier qu'une
  mise à jour a bien été appliquée).
- Menu « Aide » : « À propos » remplacé par « Notes de version » (ce journal).
- Bouton « Vérifier les mises à jour » refondu : télécharge et installe
  réellement la nouvelle version puis redémarre (même mécanisme que la mise à
  jour automatique). En version non installée (sources), il l'indique clairement.

## v1.0.5 — 2 septembre 2026

- Mise à jour automatique au démarrage (version .exe Windows) : si une release
  plus récente existe, elle est téléchargée, installée à la place de l'ancienne
  puis l'application redémarre. Silencieux si hors ligne.

## v1.0.4 — 2 septembre 2026

- Workflow de release corrigé : la version est désormais dérivée du tag Git
  (plus de plantage de quoting sur le runner Windows).

## v1.0.3 — 2 septembre 2026

- Empaquetage corrigé : `psycopg2` embarqué dans l'exe, `--paths=src` ajouté,
  `requirements.txt` complété.

## v1.0.2 — 2 septembre 2026

- Les PDF sont rangés dans un sous-dossier au nom du client
  (`data/factures_pdf/<client>/`).
- Colonnes triables (clic sur l'en-tête) dans « Rechercher factures » et
  « Clients ».
- Génération PDF réécrite (Platypus) : pagination automatique, en-têtes répétés,
  plus de chevauchement ni de texte qui déborde des cadres.
- Recherche de factures insensible à la casse ; recherche par téléphone corrigée.
- Nom de fichier PDF et numéro affiché basés sur le numéro de facture.

## v1.0.1

- Version de référence initiale.
