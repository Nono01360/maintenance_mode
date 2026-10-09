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

| Onglet | Qui | Contenu |
|---|---|---|
| **Maintenances** | tous (en lecture pour la vue utilisateur) | état en cours, maintenances planifiées ; la vue administrateur peut démarrer, planifier, modifier, supprimer |
| **Paramètres** | vue administrateur | message affiché, préavis de la notification, automatisations suspendues, utilisateurs non impactés |
| **Accès** | vue administrateur | choisit pour chaque utilisateur : *par défaut*, *aucun accès*, *vue utilisateur* ou *vue administrateur* |

Les droits sont **vérifiés côté serveur** : un utilisateur sans la vue administrateur ne peut rien modifier,
même en appelant l'API directement. Par défaut, les administrateurs de Home Assistant ont la vue
administrateur et les autres la vue utilisateur. Le propriétaire a toujours la vue administrateur.

> ⚠️ Donner la vue administrateur à un utilisateur non administrateur de Home Assistant lui permet de
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
- **Notifications push** (application mobile…) : avant le début, au début, avant la fin, à la fin.
- **Historique** des dernières maintenances (qui, quand, comment elles ont fini), visible par les administrateurs.
- **Bandeau** « Mode maintenance actif » pour les utilisateurs non bloqués, avec lien vers le panneau.
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
- **« Aucun accès » au panneau** retire son entrée du menu latéral côté navigateur (best-effort) ; côté serveur,
  l'accès est refusé dans tous les cas.
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
