# Mode maintenance pour Home Assistant

Planifie des maintenances, suspend les automatisations et affiche une page « Maintenance en cours »
(ou bloque seulement certaines pages) aux utilisateurs concernés. Tout se règle depuis un panneau
dédié dans la barre latérale, avec une **vue administrateur** et une **vue utilisateur**.

## Installation (HACS, mises à jour automatiques)

1. Dans HACS : **⋮ → Dépôts personnalisés**, colle l'adresse de ce dépôt GitHub, catégorie **Intégration**.
2. Installe **Mode maintenance**, puis redémarre Home Assistant.
3. **Paramètres → Appareils et services → Ajouter une intégration → Mode maintenance**.
4. Ouvre le panneau **Maintenance** dans la barre latérale.

Les mises à jour apparaissent ensuite dans HACS à chaque nouvelle *release* du dépôt.

## Le panneau

| Onglet | Visible avec l'autorisation | Contenu |
|---|---|---|
| **Maintenances** | `view` | état en cours et planning ; selon les autorisations : démarrer / terminer, planifier / modifier / supprimer, historique |
| **Paramètres** | `settings` et/ou `templates` | message, préavis, automatisations suspendues, utilisateurs non impactés, notifications push, affichage du bandeau (`settings`) ; modèles (`templates`) |
| **Accès** | `access` | rôles personnalisés et rôle de chaque utilisateur |

## Rôles et autorisations

Chaque utilisateur a un **rôle** ; chaque rôle est un ensemble d'**autorisations** :

| Autorisation | Permet de… |
|---|---|
| `view` | voir l'état et le planning (ajoutée automatiquement dès qu'un rôle a une autre autorisation) |
| `history` | voir l'historique |
| `control` | démarrer, modifier et terminer la maintenance en cours |
| `schedule` | planifier, modifier, dupliquer et supprimer des maintenances |
| `templates` | créer et supprimer des modèles |
| `settings` | modifier les paramètres (message, automatisations, utilisateurs non impactés, notifications, bandeau) |
| `access` | gérer les rôles personnalisés et les affectations |

Trois rôles sont intégrés : **Aucun accès** (rien, le panneau disparaît du menu), **Vue utilisateur** (`view`) et
**Vue administrateur** (tout). Dans l'onglet **Accès** tu peux créer jusqu'à 10 rôles personnalisés (par exemple
« Opérateur » = `control` + `history`) puis les attribuer. Par défaut, les administrateurs de Home Assistant ont la
vue administrateur, les autres la vue utilisateur ; le propriétaire a toujours la vue administrateur.

- Les droits sont **vérifiés côté serveur** pour chaque action, pas seulement masqués dans l'interface.
- **Pas d'escalade** : on ne peut créer, modifier ou attribuer un rôle que s'il ne contient aucune autorisation
  qu'on ne possède pas soi-même.
- Une autorisation `access` donne un grand pouvoir (créer des rôles, changer les accès) : réserve-la.
- Supprimer un rôle remet ses utilisateurs sur « Par défaut ».

> ⚠️ Un rôle avec `settings` ou `schedule` donné à un utilisateur non administrateur de Home Assistant lui permet de
> suspendre des automatisations et de bloquer des pages via ce panneau.

## Règles de fonctionnement

- **Plusieurs maintenances** peuvent être planifiées à l'avance (sans chevauchement). Chacune a ses dates,
  son motif, sa portée et son option « suspendre les automatisations ».
- **Portée** : tout Home Assistant, ou seulement certaines pages (tableau de bord principal, carte,
  `config/devices`, …). Un chemin bloque aussi ses sous-pages.
- **Automatisations** : si aucune n'est sélectionnée, **toutes** sont suspendues. Seules celles qui étaient
  actives sont réactivées à la fin.
- **Utilisateurs non impactés** : si aucun n'est sélectionné, **seul le propriétaire** n'est pas impacté.
- **Notification** : avant le début d'une maintenance, une petite notification (fermable) prévient les
  utilisateurs, avec le motif et les pages concernées.
- Une maintenance démarrée à la main **sans date de fin** est remplacée par la maintenance planifiée suivante
  quand celle-ci démarre.
- **Répétition** : une maintenance peut se répéter chaque jour, semaine ou mois (heure locale conservée malgré
  le changement d'heure). Supprimer l'occurrence suivante arrête la série.
- **Modèles** : enregistre un motif / des pages / une durée comme modèle et réutilise-le (onglet Paramètres).
- **Notifications push** (application mobile…) : avant le début, au début, avant la fin, à la fin. Choisis un service
  précis (`notify.mobile_app_…`) : l'alias générique `notify.notify` n'est pas proposé, car son comportement dépend de
  la plateforme qui l'enregistre (aucun, un seul ou tous les appareils).
- **Historique** des dernières maintenances (qui, quand, comment elles ont fini), visible par les administrateurs.
- **Bandeau** « Mode maintenance actif » pour les utilisateurs non bloqués, avec lien vers le panneau. Deux
  affichages au choix (Paramètres → Notification dans l'interface) : un **bandeau pleine largeur en haut de toute la
  page** (l'interface Home Assistant est repoussée vers le bas) ou une petite carte. Si le texte dépasse la fenêtre, il
  **défile** (désactivable : il passe alors à la ligne, avec un ascenseur s'il est très long). Le même bandeau sert
  aussi au préavis d'une maintenance à venir.
- **Réparations** : alerte si une automatisation sélectionnée n'existe plus.
- L'état et le planning sont conservés après un redémarrage ; ce qui est arrivé à échéance pendant
  l'arrêt est rattrapé au démarrage.

## Entités

- `switch.mode_maintenance` : démarre / arrête une maintenance immédiate.
- `sensor.mode_maintenance_prochaine_maintenance` : début de la prochaine maintenance (horodatage).
- `calendar.mode_maintenance_planning` : maintenances en cours et planifiées (répétitions incluses). Une maintenance
  sans fin est affichée sur 24 h. Utilisable dans le calendrier de HA et comme déclencheur d'automatisation.

## Services (administrateurs)

| Service | Rôle |
|---|---|
| `maintenance_mode.start` | démarre une maintenance (`duration` **ou** `end`, `reason`, `pages`, `pause_automations`) |
| `maintenance_mode.stop` | termine la maintenance en cours |
| `maintenance_mode.schedule` | planifie (`start`, `duration` ou `end`, `repeat`: `none`/`daily`/`weekly`/`monthly`, …) |
| `maintenance_mode.cancel_schedule` | supprime une maintenance planifiée (`window_id`) |

## Évènements

`maintenance_mode_started` et `maintenance_mode_ended` sont émis sur le bus (données : `id`, `start`, `end`, `reason`,
`pages`, `pause_automations`, `repeat`, `started_by` ; `ended_by` à la fin : `manual`, `auto` ou `replaced`).

```yaml
automation:
  - alias: Sauvegarde avant maintenance
    trigger:
      - platform: event
        event_type: maintenance_mode_started
    action:
      - service: backup.create
```

## Limites importantes

- **Le blocage est visuel (navigateur).** Il masque l'interface mais n'est pas une barrière de sécurité :
  un utilisateur techniquement averti peut encore appeler l'API REST ou le websocket avec son jeton.
  Un blocage serveur de l'API REST n'est pas possible depuis une intégration personnalisée : le serveur HTTP de
  Home Assistant démarre avant elles et n'accepte plus de nouveau middleware. Pour un vrai verrouillage, passe par
  un reverse proxy ou désactive temporairement les comptes concernés.
- **« Aucun accès » au panneau** retire son entrée du menu latéral : masquage de l'élément dans la page **et** ajout
  de « maintenance » aux panneaux masqués de la barre latérale de l'utilisateur (préférence native de Home Assistant,
  retirée automatiquement si l'accès est rendu, sauf si l'utilisateur l'avait masqué lui-même). Ça repose sur des
  éléments internes du frontend (best-effort) ; côté serveur, l'accès est refusé dans tous les cas.
- Le bandeau pleine largeur repousse l'interface avec un `transform` CSS : si l'affichage est décalé ou cassé
  chez toi, choisis la petite carte dans les paramètres.
- L'affichage repose sur des éléments internes du frontend de Home Assistant (`ha-card`, `ha-icon`,
  `hass.auth.revoke()` pour la déconnexion). Ils peuvent évoluer d'une version à l'autre.
- Panneau et page de blocage : français et anglais ; messages d'erreur du serveur en français.
- Les icônes (`brand/`) ne s'affichent qu'à partir de Home Assistant 2026.3.

## Publier une nouvelle version

1. Modifie `version` dans `custom_components/maintenance_mode/manifest.json` (ex. `0.3.1`).
2. Commit, puis `git tag v0.3.1 && git push --tags`.
3. Le workflow *Release* crée la release GitHub ; HACS propose la mise à jour.

Pense à remplacer `VOTRE_PSEUDO` dans `manifest.json` par ton nom d'utilisateur GitHub.

## Développement

```bash
pip install -r requirements_test.txt
pytest tests -q
```
