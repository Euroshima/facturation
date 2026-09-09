# Journal des versions

## v1.7.2 — 9 septembre 2026

Audit complet des lenteurs restantes. Avec une base distante, chaque
aller-retour réseau coûte environ 100 ms : la rapidité d'une action dépend donc
surtout du **nombre de requêtes** qu'elle envoie. Elles ont été réduites partout.

- **Création et modification de facture** : les lignes d'articles partaient une
  par une (23 lignes = 23 allers-retours). Elles sont maintenant envoyées
  ensemble — de ~1,5 s à ~0,07 s pour une facture de 23 lignes.
- **Reconnaissance du client** : les trois recherches successives (e-mail, puis
  téléphone, puis identité) sont fusionnées en une seule requête, à priorité
  identique.
- **Ouvrir, régénérer ou envoyer une facture** : 4 requêtes → 2 (facture et
  client lus ensemble, et le chemin du PDF n'est réécrit que s'il a changé).
- **Démarrage** : le test de connexion réutilise la connexion de
  l'application au lieu d'en ouvrir une jetable (~0,5 s économisées), et la
  création des tables se fait en un seul envoi (6 requêtes → 3).
- **Onglets** : chaque onglet n'interroge la base qu'en devenant visible. Au
  lancement, seul « Créer / Éditer facture » est chargé, au lieu des quatre.

## v1.7.1 — 9 septembre 2026

- **Correctif de lenteur : l'application ouvrait une connexion neuve à la base
  à chaque action.** Avec la base sur un serveur distant, établir une connexion
  (réseau + chiffrement + authentification) coûte environ 450 ms, contre 60 ms
  pour la requête elle-même. La connexion est désormais réutilisée d'une action
  à l'autre, et rouverte automatiquement si le serveur l'a coupée ou si les
  paramètres de connexion changent.
- **Marquage des paiements groupé** : marquer plusieurs factures payées se fait
  en un seul aller-retour au lieu d'un par facture.
- Effet mesuré sur l'onglet Paiements : marquer une facture passe de ~1,5 s à
  ~0,35 s ; en marquer cinq, de ~4,5 s à ~0,38 s (le temps ne dépend plus du
  nombre de factures sélectionnées). Toute l'application en profite :
  recherches, listes et chargement de facture sont environ 3 fois plus rapides.

## v1.7.0 — 9 septembre 2026

- **Les listes s'affichent toutes seules.** Les onglets Rechercher et Clients
  chargent leur contenu à l'ouverture, sans avoir à cliquer « Rechercher », et
  la touche Entrée lance la recherche depuis le champ de saisie.
- **Correctif : impossible d'effacer un champ client.** Vider l'e-mail ou
  l'adresse dans « Modifier client » n'avait aucun effet, l'ancienne valeur
  revenait silencieusement. L'édition écrit désormais la fiche telle quelle.
  (La complétion automatique lors de la création d'une facture, elle, continue
  de ne jamais effacer une information existante.)
- **Suppression de factures et de clients.** Bouton « Supprimer » dans les
  onglets Rechercher et Clients, avec confirmation. Un client encore rattaché
  à des factures ne peut pas être supprimé ; le PDF d'une facture supprimée
  reste sur le disque.
- **Votre société n'est plus enregistrée comme cliente.** Elle était recréée
  dans la liste des clients à chaque démarrage et polluait la recherche. Si
  elle s'y trouve déjà, vous pouvez maintenant la supprimer.
- **« Garder le client après création »** (coché par défaut) : le bloc client
  reste rempli après avoir généré une facture, pour en enchaîner plusieurs sur
  le même client.
- **Relance depuis l'onglet Paiements.** Bouton « Relancer par e-mail » avec un
  modèle dédié, distinct de l'envoi de facture, et un nouveau champ `{retard}`
  (jours de retard). Les deux modèles s'éditent dans Paramètres → Modèle
  d'e-mail.

## v1.6.0 — 9 septembre 2026

- **Sélection du client directement depuis l'onglet Création.** Un champ
  « Rechercher un client » a été ajouté en haut du bloc Client : tape un nom,
  un prénom, une entreprise (ou un e-mail / téléphone), une liste de
  suggestions s'affiche, et le choix remplit d'un coup l'adresse, l'e-mail et
  le téléphone. Plus besoin de passer par l'onglet Clients.
- Navigation au clavier : flèche Bas pour entrer dans la liste, Entrée pour
  valider, Échap pour fermer.

## v1.5.0 — 9 septembre 2026

- **Nouvel onglet « Paiements »** : suivi des factures réglées ou non.
  Les impayées sont listées en premier, de la plus ancienne à la plus
  récente, avec leur échéance et leur retard en jours. Les factures dont
  l'échéance est dépassée s'affichent en rouge.
- **Marquage rapide** : bouton « Marquer payée » (ou double-clic sur la
  ligne) qui enregistre la date du jour. La sélection multiple permet de
  régler plusieurs factures d'un coup. « Marquer non payée » corrige une
  erreur, et la case « Afficher aussi les payées » permet de les retrouver.
- Total des impayés (nombre de factures et montant) affiché en bas de
  l'onglet.
- La colonne `paid_at` est ajoutée automatiquement à la base existante au
  premier lancement ; les factures déjà enregistrées apparaissent comme non
  payées.

## v1.4.0 — 9 septembre 2026

- **Nouveau bouton « Générer PDF, Enregistrer & Envoyer par e-mail »** dans
  l'onglet Création. En un clic : la facture est enregistrée en base, le PDF
  est généré, puis la fenêtre d'envoi s'ouvre avec l'e-mail du client, le
  sujet et le message pré-remplis, PDF déjà en pièce jointe.
- Le contexte du modèle d'e-mail (facture, client, total, échéance…) est
  désormais partagé entre les onglets Création et Recherche.

## v1.3.1 — 3 septembre 2026

- **Correctif « Security validation failure » (la vraie cause).** Le script de
  mise à jour héritait des variables internes de PyInstaller
  (`_PYI_ARCHIVE_FILE`, `_PYI_PARENT_PROCESS_LEVEL`, `_MEIPASS2`…) et les
  transmettait à l'exe relancé. Celui-ci se croyait alors processus *enfant*
  d'un bootloader parent inexistant et refusait de démarrer.
  L'environnement est maintenant nettoyé avant le lancement du script, et le
  script les efface également de son côté.

## v1.3.0 — 3 septembre 2026

- Version de test de la bascule d'exe corrigée en 1.2.9 (aucun changement de
  code).

## v1.2.9 — 3 septembre 2026

- **Correctif « Security validation failure » après mise à jour.** Le script
  renommait l'ancien `.exe` en `.exe.old` — Windows l'autorise même si le
  programme tourne encore, mais le bootloader PyInstaller ne retrouve alors
  plus son image et refuse de démarrer.
  Le script **ne renomme plus rien** : il attend que le fichier soit
  réellement déverrouillé (test d'ouverture, ~2 min max) puis l'écrase
  directement.
- Nettoyage automatique au lancement des reliquats
  (`Facturation.update.exe`, `Facturation.exe.old`).

## v1.2.8 — 3 septembre 2026

- Version de test de la mise à jour automatique (aucun changement de code par
  rapport à la 1.2.7).

## v1.2.7 — 3 septembre 2026

- **Mise à jour : remplacement de l'exe plus robuste.**
  - On **renomme** l'ancien exe de côté avant de le supprimer : le renommage
    réussit souvent là où la suppression échoue sur un fichier encore
    verrouillé (bootloader one-file, antivirus, OneDrive).
  - Les boucles d'attente sont **bornées** (≈60 s pour la fermeture, ≈90 s
    pour la libération) : plus de script qui tourne indéfiniment.
  - Le script s'exécute désormais **sans fenêtre console** (`CREATE_NO_WINDOW`)
    et survit à la fermeture de l'application.
  - Journal détaillé : `%TEMP%\facturation_update_bat.log` (état de OLD/NEW,
    nombre d'essais, action finale).

## v1.2.6 — 3 septembre 2026

- Version de test du signalement de mise à jour (aucun changement fonctionnel
  par rapport à la 1.2.5).

## v1.2.5 — 3 septembre 2026

- **Signalement des mises à jour** (sans blocage) : au lancement, une
  vérification en arrière-plan ; si une version plus récente existe :
  - petit pop-up « La version X est disponible — l'installer maintenant ? » ;
  - indicateur permanent « ⬆ Mise à jour vX disponible » en bas à droite,
    cliquable pour lancer l'installation.
  Rien ne se télécharge ni ne se remplace tant que l'utilisateur n'a pas
  cliqué. Silencieux si hors ligne.

## v1.2.4 — 3 septembre 2026

- Le fichier de la release s'appelle désormais simplement **`Facturation.exe`**
  (et `Facturation-debug.exe`), sans le numéro de version dans le nom. La
  version est portée par le tag/titre de la release et affichée dans
  l'application. Un nom fixe évite qu'un fichier « mente » après une mise à
  jour (qui remplace le contenu, pas le nom).
- L'updater ignore explicitement la variante `-debug` et privilégie
  `Facturation.exe`.

## v1.2.3 — 3 septembre 2026

- Nettoyage : suppression de l'échafaudage de traçage du démarrage
  (`_trace`, `core/debuglog.py`, `facturation-boot.log`). Le garde-fou reste :
  toute erreur au démarrage est toujours écrite dans `facturation-error.log`
  et affichée. `Facturation-debug-<version>.exe` (console) reste fourni pour
  voir un éventuel plantage.

## v1.2.2 — 3 septembre 2026

- **Modèle d'e-mail personnalisable** : Paramètres → *Modèle d'e-mail…* pour
  écrire une fois le sujet et le corps, réutilisés à chaque envoi. Champs
  substituables : `{facture}`, `{societe}`, `{client}`, `{total}`, `{date}`,
  `{echeance}` (un champ inconnu est laissé tel quel, jamais d'erreur). Le
  texte reste modifiable au cas par cas avant l'envoi. Bouton
  « Réinitialiser » pour revenir au modèle par défaut.

## v1.2.1 — 3 septembre 2026

- **Correctif mise à jour manuelle** : le script de remplacement laissait
  `Facturation.update.exe` à côté sans remplacer l'ancien exe. Causes :
  `timeout` ne fonctionne pas quand le script tourne sans console, et l'exe
  reste verrouillé quelques secondes après la fermeture. Le script temporise
  maintenant avec `ping`, réessaie (suppression puis renommage de l'ancien)
  jusqu'à ~80 s, puis relance la bonne version. Trace dans
  `%TEMP%\facturation_update_bat.log`.

## v1.2.0 — 3 septembre 2026

- **Paramètres → Mon entreprise…** : nom, adresse, SIRET, TVA intracom, IBAN,
  BIC, délai de paiement, mentions légales, pied de page… éditables dans
  l'application (stockés dans `%APPDATA%\Facturation\facturation.ini`).
  Plus besoin de recompiler pour changer l'adresse ou l'IBAN sur les factures.
- **Envoi de la facture par e-mail** (onglet Rechercher → *Envoyer par
  e-mail*) :
  - envoi direct via **SMTP** (Paramètres → *E-mail (SMTP)…* : serveur, port,
    identifiants, sécurité starttls/ssl ; bouton « Envoyer un test ») avec le
    PDF en pièce jointe ;
  - ou **« Ouvrir dans ma messagerie »** (mailto pré-rempli) si le SMTP n'est
    pas configuré.
  Le PDF est régénéré à la volée avant l'envoi.
- Journal de démarrage (`facturation-boot.log`) **désactivé par défaut** :
  activable via un fichier `debug.txt` à côté de l'exe ou la variable
  `FACT_DEBUG=1`. Plus de fichier qui traîne en usage normal.

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
