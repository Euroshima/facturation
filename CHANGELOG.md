# Journal des versions

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
