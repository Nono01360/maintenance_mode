# Mode maintenance — feuille de route vers la 1.0

> Objectif : une **1.0 très qualitative**. La qualité n'est pas une phase finale : chaque version
> doit respecter les mêmes engagements (section 1) et les mêmes règles de conduite (section 2).
> Les tailles sont relatives (**S** petite, **M** moyenne, **L** grosse). Aucune date n'est promise :
> une version sort quand ses critères de sortie sont atteints.

---

## 0. Point de départ (0.6.1)

**Déjà en place** : panneau (maintenances, paramètres, accès), rôles et autorisations vérifiés côté serveur,
maintenances multiples et répétées, modèles, historique avec suppression, notifications push, calendrier,
services et évènements, bandeau pleine largeur avec défilement, masquage du menu, suspension réappliquée
après redémarrage, initiateur non public, alertes de réparation, diagnostics, français / anglais.

**Dettes connues (à traiter, pas à cacher)**

| Dette | Conséquence |
|---|---|
| `manager.py` ≈ 900 lignes, `panel.js` ≈ 1 150, `overlay.js` ≈ 800 | difficile à relire et à faire évoluer sans régression |
| Stockage sans migration versionnée | tout nouveau champ est risqué |
| Astuces sur la structure interne du frontend (décalage de page, menu) | déjà cassées 3 fois, validées seulement par essais manuels |
| Tests JavaScript hors dépôt, aucun test sur un vrai Home Assistant | les bugs d'affichage ne sont vus que par l'utilisateur |
| Attributs d'entité publics : `exempt_users`, `panel_hidden_for`, `disabled_automations` | fuite d'information mineure |
| Boucle d'affichage toutes les secondes pour tous les utilisateurs | consommation inutile, surtout sur mobile |
| Messages d'erreur du serveur en français seulement | incohérent avec un panneau bilingue |
| Désinstaller l'intégration pendant une maintenance laisse les automatisations coupées | piège réel |
| L'abonnement du panneau reste attaché à l'ancienne instance après un rechargement | mises à jour qui s'arrêtent |
| Fuseau horaire du formulaire = celui du navigateur | décalage possible des dates |

---

## 1. Ce que « très qualitatif » veut dire (10 engagements mesurables)

| # | Engagement | Critère de sortie de la 1.0 |
|---|---|---|
| 1 | **Fiabilité** : ne jamais laisser la maison dans un état incohérent | scénarios de panne testés (arrêt brutal à chaque étape d'une bascule, redémarrage, rechargement, désinstallation, horloge qui recule, changement d'heure) : zéro état incohérent |
| 2 | **Sécurité et confidentialité** | matrice « commande × rôle » testée automatiquement ; aucune donnée personnelle dans les attributs publics ; tout texte saisi échappé ; toutes les saisies bornées |
| 3 | **Résilience aux évolutions de Home Assistant** | CI sur la version minimale **et** la dernière ; tout code dépendant de la structure interne du frontend isolé dans un seul module avec mode dégradé ; veille hebdomadaire sur les versions bêta |
| 4 | **Performance et sobriété** | budgets chiffrés tenus (voir 0.12) ; aucune opération bloquante dans la boucle d'évènements ; stockage borné |
| 5 | **Accessibilité** | WCAG 2.1 AA visé : clavier, lecteur d'écran, contrastes en clair et sombre, animations réduites ; audit automatisé sans erreur critique |
| 6 | **Expérience utilisateur** | première configuration guidée ; aucune action destructive sans confirmation ; annulation possible quand c'est peu coûteux ; messages d'erreur compréhensibles |
| 7 | **Observabilité** | journaux exploitables, diagnostics, capteurs de santé, entrées dans le Journal de HA, alertes de réparation actionnables |
| 8 | **Tests** | tests unitaires, d'intégration, de migration, de chaos, de charge, JavaScript et de bout en bout sur un vrai Home Assistant, tous en CI |
| 9 | **Maintenabilité** | modules courts et typés, architecture documentée, contribution facilitée |
| 10 | **Documentation, support, distribution** | guides complets, FAQ, dépannage, journal des modifications, canal bêta, licence, modèles de tickets |

> Cadre de référence : l'**Integration Quality Scale** de Home Assistant (Bronze → Argent → Or → Platine, suivi dans un
> fichier `quality_scale.yaml`). Les niveaux officiels ne concernent que les intégrations du cœur : on l'utilise ici comme
> **auto-évaluation** (cible : Argent puis Or) ; le palier Platine (typage strict de bout en bout…) reste un objectif
> à discuter.

---

## 2. Règles de conduite (valables pour chaque version)

1. **Aucune nouvelle astuce sur le DOM de Home Assistant** hors du module d'isolation (`compat`). Préférer les API documentées (cartes, réparations, évènements, services).
2. **Toute action passe par le serveur**, avec contrôle de l'autorisation et validation de la saisie.
3. **Toute donnée enregistrée est versionnée et migrée**, avec test de migration depuis chaque ancien format.
4. **Toute fonction livre** : test automatique, documentation, traductions fr / en, ligne dans le journal des modifications.
5. **Toute opération est rejouable** (idempotente) : démarrer, terminer, réappliquer, notifier.
6. **L'échec d'un élément secondaire ne bloque jamais l'essentiel** (notification, hook, journal), sauf politique explicite choisie par l'utilisateur.
7. **Rien d'irréversible sans confirmation**, et rien de caché : ce que le système va faire est visible avant (aperçu).
8. **Pas de télémétrie.** Aucune donnée ne quitte l'installation.
9. **Un bug corrigé = un test de non-régression** ajouté.
10. **Pas de fonction livrée sans essai réel** sur l'installation de référence.

---

## 3. Vue d'ensemble

| Version | Thème | Contenu clé |
|---|---|---|
| **0.6.2** | Correctifs rapides | fuseau, répétition mensuelle, désinstallation propre, abonnement du panneau, boucle d'affichage, tests JS en CI |
| **0.7** | Fondations | découpage, stockage versionné, confidentialité complète, mode compatibilité, banc de test de bout en bout, CI en matrice |
| **0.8** | Sûreté | exclusions, étiquettes et zones, aperçu, durée maximale, plages interdites, confirmations renforcées |
| **0.9** | Fiabilité et opérations | bascule transactionnelle, réparation réparable, hooks, suspension par lots, bilan de fin, capteurs de santé |
| **0.10** | Intégration à Home Assistant | carte de tableau de bord, actions de notification, gravité, `binary_sensor`, entités `notify`, blueprints |
| **0.11** | Apparence et suivi | historique enrichi, catégories, page de blocage, assistant de première configuration, export / import, finitions |
| **0.12** | Qualité transversale (gel des fonctions) | accessibilité, performance, langues, sécurité, documentation, distribution |
| **1.0-rc** | Stabilisation | corrections uniquement, période d'essai |
| **1.0** | Version de référence | tous les critères de la section 1 |

**Dépendances principales** : 0.7 avant tout le reste (découpage + migration + banc de test) ; 0.8 « aperçu » avant
« étiquettes » ; 0.9 « bascule transactionnelle » avant « hooks » ; 0.10 « carte » et « actions de notification »
après les droits confidentiels de 0.7.

---

## 4. Détail par version

### 0.6.2 — Correctifs rapides

| ID | Élément | Type | Taille | Risque | Critère d'acceptation |
|---|---|---|---|---|---|
| 6.2.1 | **Fuseau horaire** : le formulaire interprète et affiche les dates dans le fuseau de Home Assistant (le fuseau est affiché à côté du champ) | 🔧 | S | faible | une maintenance saisie à 03:00 démarre à 03:00 heure de HA, navigateur dans un autre fuseau ; test autour du changement d'heure |
| 6.2.2 | **Répétition mensuelle** : mémoriser le jour d'origine | 🔧 | S | faible | 31 janvier → 28 février → 31 mars ; jamais de dérive |
| 6.2.3 | **Boucle d'affichage** : erreurs isolées par étape, fréquence adaptée (rapide si actif, lente sinon, suspendue quand l'onglet est masqué) | 🔧 | S | faible | une erreur dans une étape n'arrête pas les autres ; charge mesurée divisée par au moins 5 au repos |
| 6.2.4 | **Désinstallation propre** : terminer la maintenance (réactiver les automatisations), supprimer panneau, stockage et alertes | 🔧 | S | moyen | désinstaller pendant une maintenance laisse toutes les automatisations dans leur état d'origine |
| 6.2.5 | **Abonnement du panneau** : survit au rechargement de l'intégration et aux reconnexions | 🔧 | S | moyen | recharger l'intégration avec le panneau ouvert : il continue de se mettre à jour |
| 6.2.6 | **Écritures disque groupées** : sauvegarde différée pour les changements fréquents, immédiate pour les transitions critiques | 🧱 | S | faible | pas plus d'une écriture par rafale de changements ; aucune perte à l'arrêt |
| 6.2.7 | **Tests JavaScript dans le dépôt** et dans la CI | 🧱 | M | faible | les suites actuelles tournent en CI |
| 6.2.8 | **Dépôt** : licence, topics, CI verte sur HA 2026.2, section « Dépannage » du README | 🔧 | S | nul | les vérifications HACS passent |

**Sortie** : tous les critères ci-dessus ; essai réel du fuseau et de la désinstallation.

### 0.7 — Fondations (aucune fonction visible)

| ID | Élément | Type | Taille | Risque | Critère d'acceptation |
|---|---|---|---|---|---|
| 7.1 | **Découpage de `manager.py`** : planification, suspension, droits, notifications, historique, modèles, réparations ; le gestionnaire ne fait plus que coordonner | 🧱 | L | moyen | aucun module > 300 lignes ; **comportement identique** prouvé par des tests de caractérisation écrits *avant* le découpage |
| 7.2 | **Stockage versionné** : migrations testées depuis chaque format (0.2 → 0.6), copie de sauvegarde avant migration, vérification d'intégrité au chargement, retour arrière documenté | 🧱 | M | moyen | chaque ancien format migre sans perte ; données corrompues → démarrage en mode sûr + alerte, jamais de plantage |
| 7.3 | **Types** : structures typées, vérification de types en CI sur le nouveau code | 🧱 | M | faible | zéro erreur de typage sur les modules découpés |
| 7.4 | **Confidentialité complète** : chaque navigateur demande au serveur *ses propres* droits ; suppression des attributs publics sensibles | 🔧 | M | moyen | aucun identifiant d'utilisateur ni nom d'automatisation dans les attributs lisibles par tous |
| 7.5 | **Mode compatibilité** : un réglage désactive tous les procédés touchant à la structure interne du frontend ; **module d'isolation unique** ; diagnostic dans le panneau (structure reconnue ? décalage appliqué ? menu masqué ?) | ✨ | M | faible | avec le mode activé, aucune modification du DOM de HA ; avec une structure inconnue, repli automatique et message clair |
| 7.6 | **Banc de bout en bout** : un vrai Home Assistant en conteneur + navigateur automatisé ; scénarios : bandeau (position, défilement), masquage du menu, panneau selon le rôle, blocage ; captures de référence | 🧱 | L | moyen | les 3 bugs d'affichage déjà rencontrés sont reproduits par un test qui échoue sans le correctif |
| 7.7 | **Veille « canari »** : même banc, chaque semaine, sur les versions bêta de HA (non bloquant) | 🧱 | S | nul | une régression frontend est détectée avant la sortie de HA |
| 7.8 | **CI en matrice** : version minimale et dernière de HA, Python 3.12 / 3.13, couverture, analyse statique, hassfest, HACS, analyse de sécurité du code, mises à jour automatiques des actions épinglées | 🧱 | M | nul | tout est vert ; couverture ≥ 85 % sur le cœur |
| 7.9 | **Erreurs traduites** : codes d'erreur stables côté serveur, traduits fr / en côté panneau | 🔧 | M | faible | plus aucun message en dur côté serveur visible par l'utilisateur |
| 7.10 | **Limites et validation** : tailles maximales sur toutes les saisies, limitation douce des écritures | 🔧 | S | faible | une saisie hors limites est refusée proprement |
| 7.11 | **Documents d'architecture** : `ARCHITECTURE.md`, `quality_scale.yaml` (auto-évaluation) | 🧱 | S | nul | à jour |

**Sortie** : suite de tests complète verte avant *et* après le découpage ; migration essayée sur ta vraie configuration (avec sauvegarde) ; banc de bout en bout fonctionnel.

### 0.8 — Sûreté

| ID | Élément | Taille | Risque | Critère d'acceptation |
|---|---|---|---|---|
| 8.1 | **Exclusions** (liste et par étiquette) : jamais suspendues, **même si elles sont sélectionnées** ; affichage d'un avertissement dans le formulaire | M | faible | test : une automatisation exclue et sélectionnée reste active |
| 8.2 | **Étiquettes et zones** comme sélecteurs : somme des sélecteurs moins les exclusions, résolue au démarrage de la maintenance (instantané) | M | moyen | comportement documenté ; une automatisation créée pendant la maintenance n'est pas suspendue |
| 8.3 | **Aperçu avant démarrage** : suspendues / protégées / ignorées, utilisateurs bloqués, pages, notifications et hooks prévus ; **mode test à blanc** sans aucun effet | M | faible | l'aperçu est identique à ce qui se passe réellement (test comparant les deux) |
| 8.4 | **Durée maximale** (par défaut, par modèle, par maintenance) avec **rappel préalable** puis arrêt automatique et notification | M | faible | une maintenance sans fin se termine à la durée maximale ; le rappel part avant |
| 8.5 | **Plages interdites** : jours et heures où l'on ne planifie ni ne démarre ; refus expliqué ; dérogation explicite du propriétaire | S | faible | refus testé, dérogation journalisée |
| 8.6 | **Confirmation renforcée** pour les actions larges (« tout suspendre » avec beaucoup d'automatisations) | S | faible | seuil configurable, texte explicite |
| 8.7 | **Annuler pendant quelques secondes** après une suppression (maintenance, modèle) | S | faible | annulation restaure à l'identique |

**Sortie** : essai sur tes vraies automatisations ; aucun cas où une automatisation protégée est suspendue.

### 0.9 — Fiabilité et opérations

| ID | Élément | Taille | Risque | Critère d'acceptation |
|---|---|---|---|---|
| 9.1 | **Bascule transactionnelle** : marqueur « bascule en cours », reprise au démarrage d'une opération interrompue | M | moyen | **tests de chaos** : arrêt brutal simulé à chaque étape, état final toujours cohérent |
| 9.2 | **Réconciliation et réparation réparable** : écarts détectés (entité disparue, réapplication impossible…), alerte avec bouton « Réparer » | M | moyen | chaque type d'écart a une alerte et une réparation testées |
| 9.3 | **Suspension par lots** avec délais d'attente et reprise partielle, progression visible | M | moyen | 200 automatisations suspendues sans bloquer la boucle d'évènements |
| 9.4 | **Hooks avant / après** (scripts et scènes) : ordre garanti, délai maximum, politique d'échec (continuer ou annuler), résultat dans l'historique, protection contre les boucles | L | moyen | échec, délai dépassé et boucle testés |
| 9.5 | **Bilan de fin** : entités devenues indisponibles, erreurs du journal limitées, durée réelle | M | faible | affiché dans l'historique |
| 9.6 | **Journal de Home Assistant** : « Maintenance démarrée / terminée » avec auteur et motif | S | faible | visible dans la page Journal |
| 9.7 | **Capteurs de santé** : dernière réapplication, nombre suspendu, dernier hook en échec, `binary_sensor` « problème » | S | faible | exposés et documentés |
| 9.8 | **Tests de temps** : changement d'heure, horloge qui recule, fuseau modifié, redémarrage à la seconde de la fin | M | faible | suite dédiée en CI |
| 9.9 | **Recettes documentées** : sauvegarde avant, mises à jour, annonces vocales, import d'agenda | S | nul | testées à la main |

**Sortie** : un vrai redémarrage de Home Assistant pendant une maintenance, essayé sur ton installation, avec et sans arrêt propre.

### 0.10 — Intégration à Home Assistant

| ID | Élément | Taille | Risque | Critère d'acceptation |
|---|---|---|---|---|
| 10.1 | **Carte de tableau de bord** (configuration YAML) : état, prochaine maintenance, boutons selon les droits via nos commandes serveur ; variante « mur » lisible de loin | L | moyen | un utilisateur sans droit ne voit pas les boutons **et** le serveur refuse ses appels |
| 10.2 | **`binary_sensor`** et recette de supervision externe (Uptime Kuma, `mqtt_statestream`) | S | faible | documenté avec exemple |
| 10.3 | **Actions dans les notifications** (prolonger, terminer) : identité vérifiée via l'utilisateur de l'évènement, identifiant unique et expirant contre le rejeu, droit vérifié, trace dans l'historique | L | **élevé** | tests de sécurité : rejeu, droit insuffisant, appareil d'un autre utilisateur ; essai sur iOS et Android |
| 10.4 | **Entités `notify` modernes**, textes personnalisables avec variables (fr / en), « préviens-moi à la fin » | M | faible | aperçu du texte avant enregistrement |
| 10.5 | **Niveaux de gravité** : information (rien n'est bloqué), avertissement, bloquant ; couleurs et comportement distincts | M | moyen | chaque niveau testé sur la page de blocage et le bandeau |
| 10.6 | **Service `extend`**, déclencheurs d'appareil, blueprints livrés | S | faible | utilisables depuis l'éditeur d'automatisations |

**Sortie** : essai de la carte sur la tablette, des actions sur le téléphone ; audit de sécurité dédié aux actions de notification.

### 0.11 — Apparence et suivi

| ID | Élément | Taille | Risque | Critère d'acceptation |
|---|---|---|---|---|
| 11.1 | **Assistant de première configuration** : protections, notifications, rôles, aperçu, test à blanc | M | faible | une installation neuve est utilisable en moins de 5 minutes sans lire la documentation |
| 11.2 | **Historique enrichi** : durée réelle contre prévue, notes, recherche, export CSV et JSON, disponibilité sur 30 jours | M | faible | exports vérifiés |
| 11.3 | **Catégories colorées** avec réglages par défaut, fusionnées avec les modèles | M | faible | filtres dans la liste et l'historique |
| 11.4 | **Page de blocage** : messages par langue et par rôle, compte à rebours visuel, thèmes limités, aperçu du rendu, journal de progression | M | faible | aperçu fidèle ; contenu nettoyé |
| 11.5 | **Export / import de configuration** et **journal d'audit** des réglages sensibles | M | faible | import refuse un fichier invalide ou plus récent |
| 11.6 | **Finitions d'ergonomie** : validation en ligne, avertissement avant de quitter avec des modifications non enregistrées, états vides soignés, indicateurs de chargement, aide contextuelle avec liens vers la documentation | M | faible | revue complète des écrans sur ordinateur, tablette et téléphone |

**Sortie** : revue de tous les écrans sur trois formats et deux thèmes ; essai de l'assistant sur une installation vierge.

### 0.12 — Qualité transversale (**gel des fonctions** : plus de nouveauté)

| ID | Élément | Critère d'acceptation |
|---|---|---|
| 12.1 | **Accessibilité** : audit automatisé + audit manuel (clavier seul, lecteur d'écran), contrastes en clair et sombre, animations réduites, zones tactiles | zéro erreur critique ; parcours complet au clavier |
| 12.2 | **Performance** : budgets chiffrés — suspension de 200 automatisations sans bloquer, page de blocage réactive avec 1 000 entités, charge de la boucle d'affichage mesurée, stockage borné (historique, notifications mémorisées) | budgets tenus en CI |
| 12.3 | **Langues** : textes extraits en fichiers de traduction, test de complétude en CI, pluriels et formats corrects, guide pour proposer d'autres langues | fr / en complets ; ajout d'une langue sans toucher au code |
| 12.4 | **Sécurité** : revue complète, matrice « commande × rôle » automatisée, tests d'injection de HTML, tests de saisies aberrantes, politique de signalement (`SECURITY.md`) | aucune faille connue ouverte |
| 12.5 | **Documentation** : README, guides (installation, premiers pas, rôles, exclusions, hooks, carte), FAQ, dépannage, captures et courtes vidéos, `CONTRIBUTING.md`, `CHANGELOG.md`, modèles de tickets demandant les diagnostics | relue par une personne extérieure |
| 12.6 | **Distribution** : icônes, topics, licence, notes de version automatiques, canal bêta (pré-versions), vérifications HACS complètes, option de soumission à la liste officielle | tout vert |
| 12.7 | **Compatibilité et dépréciations** : liste des changements incompatibles, guide de migration, politique de versions | publié |

### 1.0-rc — Stabilisation

Corrections uniquement. Période d'essai d'au moins deux semaines sur ton installation, plus quelques volontaires si possible.
Chaque bug trouvé reçoit un test de non-régression. Aucune nouvelle fonction.

### 1.0 — Critères de sortie (liste de contrôle)

- [ ] Aucun bug bloquant ou majeur ouvert
- [ ] CI entièrement verte (version minimale et dernière de HA, bout en bout, migrations, chaos, charge)
- [ ] Migration testée depuis toutes les versions publiées
- [ ] Audit d'accessibilité sans critique ; audit de sécurité fait
- [ ] Documentation complète, relue
- [ ] Au moins deux semaines sans bug bloquant sur l'installation de référence
- [ ] `quality_scale.yaml` à jour (cible Or en auto-évaluation)
- [ ] Journal des modifications, licence, notes de version publiés

---

## 5. Stratégie de tests (couches)

| Couche | Ce qu'elle protège | Où |
|---|---|---|
| Unitaires (Python) | logique pure : calendrier, répétition, droits, migrations | CI |
| Intégration (banc de test de HA) | entités, services, websocket, stockage, réparations | CI |
| JavaScript (faux navigateur) | logique du panneau et du bandeau | CI |
| **Bout en bout (vrai HA + vrai navigateur)** | affichage réel, menu, défilement, rôles | CI (min et dernière), canari hebdomadaire (bêta) |
| Migration | anciens formats de stockage | CI |
| Chaos | arrêt brutal pendant une bascule | CI |
| Charge | 200 automatisations, 1 000 entités, 50 maintenances, 50 utilisateurs | CI planifiée |
| Accessibilité | clavier, contrastes, rôles ARIA | CI + audit manuel |
| Sécurité | droits, injections, rejeu, saisies aberrantes | CI + revue |
| Essai réel | ce qu'aucun test ne voit | à chaque version, sur ton installation |

---

## 6. Registre des risques

| Risque | Probabilité | Impact | Parade |
|---|---|---|---|
| Une mise à jour de HA casse l'affichage (décalage, menu) | élevée | moyen | module d'isolation, mode compatibilité, banc de bout en bout, veille bêta |
| Régression lors du découpage du code | moyenne | élevé | tests de caractérisation écrits avant, livraison seule |
| Migration de stockage qui perd des données | faible | élevé | sauvegarde avant migration, tests depuis chaque format, mode sûr |
| Faille dans les actions de notification | moyenne | élevé | identité vérifiée, identifiants expirants, tests de sécurité dédiés |
| Arrêt brutal pendant une bascule | moyenne | moyen | bascule transactionnelle, tests de chaos |
| Dérive de périmètre (trop de fonctions) | élevée | moyen | gel des fonctions en 0.12, liste « après 1.0 » |
| Dépendances de test lourdes (banc de bout en bout) | moyenne | faible | conteneur et navigateur automatisé en CI, version épinglée |
| Je ne peux pas essayer sur un vrai HA | certaine | moyen | essais réels obligatoires à chaque version (règle 10) |

---

## 7. Politique de versions et de publication

- **Numérotation sémantique** : `0.x` jusqu'à la 1.0 ; ensuite `MAJEUR.MINEUR.CORRECTIF`. Un changement incompatible = version majeure.
- **Canaux** : stable (releases), bêta (pré-versions visibles dans HACS pour les volontaires).
- **Liste de contrôle de publication** : tests verts, migration testée, essai réel fait, traductions complètes, journal des modifications, notes de version, étiquette `vX.Y.Z` identique au manifeste.
- **Dépréciations** : annoncées une version à l'avance, avec guide de migration.
- **Compatibilité** : la version minimale de Home Assistant supportée est publiée dans le README et `hacs.json` ; son relèvement est une décision explicite, annoncée.

---

## 8. Décisions à prendre

1. **Licence** (MIT, Apache 2.0, GPL v3…).
2. **Version minimale de HA** supportée (aujourd'hui 2025.1) : la relever simplifie le code mais exclut des utilisateurs.
3. **Langues** à ajouter après fr / en.
4. **Liste officielle de HACS** : viser la soumission ou rester en dépôt personnalisé ?
5. **Ordre 0.9 / 0.10** : carte avant hooks si l'usage tablette prime.
6. **Banc de bout en bout** : accepter la dépendance à un conteneur et un navigateur automatisé en CI (recommandé).
7. **Ambition de l'auto-évaluation** : Argent, Or ou Platine.
8. **Aucune télémétrie** (recommandé) : à confirmer.

---

## 9. Après la 1.0 et écarté

**Après la 1.0** : commandes vocales Assist, chronologie visuelle (glisser-déposer), import d'agenda natif, détection de
conflits avec les calendriers, redémarrage planifié sécurisé, messages enrichis (liens, images), notification persistante
avec compte à rebours, marquage des automatisations suspendues, annonces vocales natives.

**Écarté** : code PIN (valeur faible), reprise « en douceur » des automatisations (problème largement théorique), mode
lecture seule et pastille sur le menu (trop fragiles), créneau suggéré (trop complexe pour l'intérêt), blocage serveur de
l'API REST (impossible depuis une intégration personnalisée).
