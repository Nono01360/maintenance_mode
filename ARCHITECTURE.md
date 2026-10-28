# Architecture

Vue d'ensemble de l'intégration **Mode maintenance** (0.7). Chaque module Python fait au plus 300 lignes
(`tests/test_architecture.py`).

## Côté serveur (`custom_components/maintenance_mode/`)

| Module | Rôle |
|---|---|
| `__init__.py` | installation / déchargement / suppression de l'intégration, panneau, fichiers statiques |
| `manager.py` | **coordinateur** : assemble les modules ci-dessous, expose les actions (démarrer, arrêter, planifier…) |
| `window.py` | `Window` (une maintenance), répétition (jour d'origine mensuel, heure « murale » malgré le DST), utilitaires purs |
| `validation.py` | contrôles de saisie (motif, fin, chevauchement, répétition, modèles) |
| `access.py` | rôles, autorisations, droits d'affichage d'un utilisateur, vue d'état filtrée pour le panneau |
| `settings.py` | mise à jour des réglages (avec anti-escalade des droits), suppression d'historique |
| `suspension.py` | suspension / réactivation / remise en pause des automatisations (instantané pris au démarrage) |
| `planning.py` | échéances, rattrapage au démarrage, minuterie unique |
| `notifications.py` | textes fr / en et envoi aux services `notify.*` choisis |
| `storage.py` | stockage versionné (format 2), migration depuis les anciens formats, copie de sécurité, mode sûr |
| `errors.py` | erreurs à code stable + catalogue fr / en |
| `limits.py` | tailles maximales des saisies, limiteur d'écritures |
| `websocket_api.py` | API du panneau ; **chaque commande vérifie l'autorisation côté serveur** |
| `services.py` | services `maintenance_mode.*` (administrateurs) |
| `switch.py`, `sensor.py`, `calendar.py`, `entity.py` | entités |
| `diagnostics.py` | diagnostics expurgés |

Le gestionnaire est une classe qui hérite de plusieurs « mixins » : chacun suppose certains attributs du
gestionnaire (documentés dans sa docstring). Le découpage a été fait **sans changer le comportement** ; les tests de
caractérisation (`tests/test_characterization.py`) le prouvent.

### Flux de données

```
panneau (panel.js) ──websocket──▶ websocket_api ──▶ manager ──▶ stockage (écriture groupée / immédiate)
                                                       │
bandeau (overlay.js) ◀── attributs de l'entité ◀───────┤──▶ entités, calendrier, évènements du bus
                     ──get_client (SES droits)──▶ websocket_api
```

- **Écritures** : les transitions de maintenance (démarrage, fin, échéances) sont écrites **tout de suite** ; les
  réglages sont groupés (2 s) et terminés au déchargement et à l'arrêt de Home Assistant.
- **Confidentialité** : les attributs de l'entité (lisibles par tous) ne contiennent ni identifiant d'utilisateur ni
  nom d'automatisation. Un navigateur ne connaît que ses propres droits (`maintenance_mode/get_client`), redemandés
  quand l'empreinte `rights_rev` change.

### Stockage

Fichier `.storage/maintenance_mode.<entry_id>`, **format 2**.

- Migration 1 → 2 (`migrate_data`) : conversion des anciens formats (0.2 : `active`, `start_armed`), identifiants
  d'historique. L'ancien fichier est d'abord copié dans `….backup_v1`.
- Intégrité (`check_data`) : une partie illisible est écartée, le reste est conservé (**mode sûr**) ; l'original est
  copié dans `….unreadable` et une alerte « Réparations » est créée. Un fichier écrit par une version plus récente
  n'est pas utilisé (copie conservée).
- Retour arrière : restaurer `….backup_v1` à la place du fichier principal, avec Home Assistant arrêté.
- À la suppression de l'intégration, le fichier et ses copies sont supprimés.

## Côté navigateur (`www/`)

| Fichier | Rôle |
|---|---|
| `overlay.js` | chargé pour **tous** les utilisateurs : page de blocage, préavis, bandeau ; boucle d'affichage adaptative |
| `panel.js` | panneau de configuration (composant web sans compilation) |

**Frontière d'isolation** : tout ce qui dépend de la structure interne du frontend de Home Assistant (décalage de la
page, entrée de menu, largeur de la barre latérale) est dans le bloc `compat` d'`overlay.js` ; le reste du fichier
n'utilise que son interface réduite. `tests_js/compat_isolation.test.js` interdit tout autre usage de
`shadowRoot`, `ha-sidebar`, `home-assistant-main`… Le **mode compatibilité** (réglage) désactive ce bloc ; le panneau
affiche un diagnostic de ce que l'appareil reconnaît.

## Tests

| Couche | Où |
|---|---|
| Python (banc de test de HA) | `tests/` — `pytest tests` |
| JavaScript (jsdom) | `tests_js/` — `npm test` |
| CI | `.github/workflows/` : lint + sécurité, pytest (HA minimale et dernière, couverture ≥ 85 %), JS, hassfest, HACS |
