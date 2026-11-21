# Recettes

Quatre usages courants, à copier dans `configuration.yaml` (ou dans l'éditeur YAML des automatisations et des scripts).

> **Ce qui est vérifié et ce qui ne l'est pas.** Un test automatique relit chaque bloc YAML de ce fichier : la syntaxe,
> les services `maintenance_mode.*` (ils existent et les champs utilisés sont déclarés dans `services.yaml`) et les
> évènements `maintenance_mode_*`. Les recettes n'ont **pas** été exécutées sur un vrai Home Assistant : remplace les
> identifiants d'exemple (`calendar.travail`, `assist_satellite.salon`…) par les tiens et essaie-les d'abord en
> dehors d'une vraie maintenance.

Les exemples utilisent la syntaxe `triggers:` / `actions:` / `action:` (Home Assistant 2024.10 et plus ; la version
minimale de l'intégration est 2025.1).

## 1. Sauvegarde avant la maintenance

Un **hook** « avant le début » exécute un script de sauvegarde. Avec la politique d'échec *annuler le démarrage*, la
maintenance ne commence pas si la sauvegarde échoue : rien n'est suspendu.

```yaml
script:
  sauvegarde_avant_maintenance:
    alias: Sauvegarde avant maintenance
    sequence:
      - action: backup.create
```

Dans **Maintenance → Paramètres → Hooks** (administrateur) : ajouter un hook, moment *Avant le début*,
entité `script.sauvegarde_avant_maintenance`, délai max **120 s** (limite 120 s par hook), politique
*En cas d'échec : annuler le démarrage*. Une sauvegarde plus longue que ce délai est comptée comme un échec : dans ce
cas, déclenche-la en avance (par une automatisation à heure fixe) plutôt que par un hook.

Sans hook, la même chose par automatisation (la sauvegarde démarre en même temps que la maintenance, sans pouvoir
l'annuler) :

```yaml
automation:
  - alias: Sauvegarde au début de la maintenance
    triggers:
      - trigger: event
        event_type: maintenance_mode_started
    actions:
      - action: backup.create
```

## 2. Planifier une maintenance quand une mise à jour est disponible

Dès qu'une mise à jour de Home Assistant apparaît, une maintenance d'une heure est planifiée à 3 h du matin le
lendemain, avec le motif de la mise à jour. `schedule` refuse un chevauchement : si une maintenance est déjà prévue
à ce moment, le service échoue et l'automatisation s'arrête sans rien casser.

```yaml
automation:
  - alias: Maintenance pour la mise à jour de Home Assistant
    triggers:
      - trigger: state
        entity_id: update.home_assistant_core_update
        to: "on"
    actions:
      - action: maintenance_mode.schedule
        data:
          start: "{{ (today_at('03:00') + timedelta(days=1)).isoformat() }}"
          duration: "01:00:00"
          reason: "Mise à jour de Home Assistant"
          pause_automations: true
```

## 3. Annonces vocales

Une annonce au début et à la fin d'une maintenance. Les données de l'évènement donnent le motif (`reason`) et, à la fin,
la cause (`ended_by` : `manual`, `auto`, `replaced`, `max_duration`).

```yaml
automation:
  - alias: Annonce de début de maintenance
    triggers:
      - trigger: event
        event_type: maintenance_mode_started
    actions:
      - action: assist_satellite.announce
        target:
          entity_id: assist_satellite.salon
        data:
          message: >-
            Maintenance en cours.
            {% if trigger.event.data.reason %}Motif : {{ trigger.event.data.reason }}.{% endif %}

  - alias: Annonce de fin de maintenance
    triggers:
      - trigger: event
        event_type: maintenance_mode_ended
    conditions:
      - condition: template
        value_template: "{{ trigger.event.data.ended_by != 'replaced' }}"
    actions:
      - action: assist_satellite.announce
        target:
          entity_id: assist_satellite.salon
        data:
          message: "La maintenance est terminée."
```

Tes annonces tournent pendant la maintenance : si tu suspends **toutes** les automatisations (aucune sélectionnée),
celles-ci sont suspendues aussi. Choisis donc des automatisations précises dans *Paramètres → Automatisations
suspendues*, ou protège ces annonces dans *Protections*.

## 4. Démarrer une maintenance depuis un agenda

Un évènement de ton agenda (ici `calendar.travail`) démarre la maintenance à son début et la termine à sa fin ; le titre
de l'évènement devient le motif. Ça ne fonctionne que pour les évènements **avec heures** (un évènement « toute la
journée » n'a pas d'heure de fin exploitable).

```yaml
automation:
  - alias: Maintenance depuis l'agenda
    triggers:
      - trigger: calendar
        event: start
        entity_id: calendar.travail
    actions:
      - action: maintenance_mode.start
        data:
          end: "{{ trigger.calendar_event.end }}"
          reason: "{{ trigger.calendar_event.summary }}"
          pause_automations: true
```

Pour être prévenu avant le début, utilise une seconde automatisation avec le même déclencheur et
`offset: "-0:15:00"` (annonce, notification…). Le réglage *Préavis* de l'intégration, lui, ne concerne que les
maintenances **planifiées** dans l'intégration, pas celles lancées par cette automatisation.
