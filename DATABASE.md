# Documentation — Base de données `cisat_db`

## 1. Informations générales

| Élément | Valeur |
|---|---|
| SGBD | PostgreSQL 18 |
| Nom de la base | `cisat_db` |
| Hôte / Port | `localhost` / `5432` |
| Utilisateur | `postgres` |
| Encodage client | UTF-8 |
| Schéma principal | `public` |

**Extensions installées**

| Extension | Rôle |
|---|---|
| `plpgsql` | Langage procédural natif PostgreSQL (triggers, fonctions) |
| `unaccent` | Recherche insensible aux accents (utile pour noms d'indicateurs / pays) |

> La base est gérée **hors Django** (`managed = False` dans les modèles). Le schéma est créé via SQL natif ; Django n'opère que les migrations techniques (extensions, auth, sessions).

---

## 2. Vue d'ensemble du schéma

La base se compose de **deux groupes de tables** :

### 2.1 Tables métier (5)

| Table | Rôle | Lignes |
|---|---|---:|
| [`pays`](#table-pays) | Référentiel des pays | 1 |
| [`utilisateur`](#table-utilisateur) | Comptes collecteurs / administrateurs | 1 |
| [`indicateur`](#table-indicateur) | Catalogue des indicateurs CISAT & BASICSET | 515 |
| [`metadonnee_indicateur`](#table-metadonnee_indicateur) | Métadonnées détaillées d'un indicateur (1-1) | 515 |
| [`donnee_collectee`](#table-donnee_collectee) | Valeurs saisies par pays / année / indicateur | 3 |

### 2.2 Tables techniques Django (10)

Gérées automatiquement par le framework, à ne pas modifier manuellement :

`auth_group`, `auth_group_permissions`, `auth_permission`, `auth_user`, `auth_user_groups`, `auth_user_user_permissions`, `django_admin_log`, `django_content_type`, `django_migrations`, `django_session`.

---

## 3. Diagramme relationnel (texte)

```
            ┌──────────┐
            │   pays   │◄────────────┐
            └────┬─────┘             │
                 │                   │
                 │ pays_id           │ pays_id
                 ▼                   │
         ┌──────────────┐            │
         │ utilisateur  │            │
         └──────┬───────┘            │
                │                    │
                │ utilisateur_id     │
                │ valide_par         │
                ▼                    │
       ┌────────────────────┐        │
       │  donnee_collectee  │────────┘
       └─────────┬──────────┘
                 │ indicateur_id
                 ▼
            ┌────────────┐           ┌──────────────────────────┐
            │ indicateur │◄──────────│  metadonnee_indicateur   │ (1-1)
            └────────────┘           └──────────────────────────┘
```

---

## 4. Détail des tables métier

### Table `pays`

Référentiel des pays participants.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | `integer` | PK, auto | Identifiant interne |
| `code_iso` | `character(3)` | NOT NULL, UNIQUE | Code ISO 3166-1 alpha-3 (ex. `CIV`, `FRA`) |
| `nom` | `varchar(100)` | NOT NULL | Nom officiel du pays |
| `region` | `varchar(100)` | NULL | Région géographique (Afrique de l'Ouest, etc.) |
| `actif` | `boolean` | défaut `true` | Pays activé pour la collecte |

**Index** : PK sur `id`, UNIQUE sur `code_iso`.
**Référencé par** : `utilisateur.pays_id`, `donnee_collectee.pays_id`.

---

### Table `utilisateur`

Comptes des utilisateurs métier (distincts de `auth_user` qui gère l'admin Django).

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | `integer` | PK, auto | Identifiant |
| `nom` | `varchar(100)` | NOT NULL | Nom de famille |
| `prenom` | `varchar(100)` | NOT NULL | Prénom |
| `email` | `varchar(150)` | NOT NULL, UNIQUE | Identifiant de connexion |
| `mot_de_passe_hash` | `varchar(255)` | NOT NULL | Hash du mot de passe |
| `institution` | `varchar(200)` | NULL | Organisme de rattachement |
| `pays_id` | `integer` | FK → `pays(id)` | Pays affecté |
| `role` | `varchar(20)` | NOT NULL, CHECK ∈ {`collecteur`, `admin`} | Profil applicatif |
| `actif` | `boolean` | défaut `true` | Compte activé |
| `cree_le` | `timestamp` | défaut `now()` | Date de création |
| `derniere_connexion` | `timestamp` | NULL | Dernière connexion |

**Contrainte CHECK** : `role IN ('collecteur', 'admin')`.
**Référencé par** : `donnee_collectee.utilisateur_id` (saisie), `donnee_collectee.valide_par` (validation).

---

### Table `indicateur`

Catalogue des **515 indicateurs** issus des référentiels CISAT (climatique) et BASICSET (environnemental). C'est la table la plus large : elle agrège les métadonnées descriptives et les références aux cadres internationaux.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | `integer` | PK, auto | Identifiant |
| `source` | `varchar(10)` | NOT NULL, CHECK ∈ {`CISAT`, `BASICSET`} | Référentiel d'origine |
| `code` | `varchar(60)` | UNIQUE, NULL | Code court (ex. `CISAT-1-A-01`) |
| `numero_cisat` | `smallint` | NULL | Numéro CISAT |
| `zone_cisat` | `varchar(50)` | NULL | Zone thématique CISAT |
| `sujet` | `text` | NULL | Sujet de l'indicateur |
| `composante_basicset` | `varchar(200)` | NULL | Composante BASICSET |
| `sous_composante` | `text` | NULL | Sous-composante |
| `nom` | `text` | NOT NULL | Libellé complet de l'indicateur |
| `statistique` | `text` | NULL | Statistique mesurée |
| `theme` | `varchar(100)` | NULL | Thème |
| `etage` | `smallint` | défaut `1`, CHECK ∈ {1, 2, 3} | Niveau hiérarchique |
| `unite_mesure` | `varchar(150)` | NULL | Unité (kg, %, °C, etc.) |
| `accord_paris` | `varchar(100)` | NULL | Article Accord de Paris associé |
| `pawp_katowice` | `text` | NULL | Référence PAWP Katowice |
| `ref_fdes` | `varchar(200)` | NULL | Référence FDES |
| `ref_odd` | `varchar(200)` | NULL | Référence ODD (Objectifs de Développement Durable) |
| `ref_sendai` | `varchar(200)` | NULL | Référence Cadre de Sendai |
| `ref_unece` | `varchar(300)` | NULL | Référence UNECE |
| `ref_methodo` | `varchar(300)` | NULL | Référence méthodologique |
| `sources_nat` | `text` | NULL | Sources nationales suggérées |
| `institution_focale` | `text` | NULL | Institution focale |
| `agregations` | `text` | NULL | Agrégations possibles |
| `actif` | `boolean` | défaut `true` | Indicateur en cours d'usage |

**Index** : `idx_ind_source` (source), `idx_ind_zone` (zone_cisat), `idx_ind_comp` (composante_basicset), `idx_ind_etage` (etage).
**Référencé par** : `metadonnee_indicateur.indicateur_id` (ON DELETE CASCADE), `donnee_collectee.indicateur_id`.

---

### Table `metadonnee_indicateur`

Métadonnées complémentaires en relation **1-1** avec `indicateur`. Permet d'isoler les contenus longs sans alourdir les requêtes sur le catalogue.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | `integer` | PK, auto | Identifiant |
| `indicateur_id` | `integer` | NOT NULL, UNIQUE, FK → `indicateur(id)` ON DELETE CASCADE | Indicateur associé |
| `definition` | `text` | NULL | Définition complète |
| `pertinence` | `text` | NULL | Pertinence / justification |
| `type_source_donnee` | `text` | NULL | Type de source (enquête, registre, etc.) |
| `frequence_maj` | `text` | NULL | Fréquence de mise à jour |
| `categorie_mesure` | `varchar(150)` | NULL | Catégorie de mesure |
| `methode_calcul` | `text` | NULL | Formule / méthode de calcul |
| `agregations_potentielles` | `text` | NULL | Possibilités d'agrégation |
| `cree_le` | `timestamp` | défaut `now()` | Création |
| `modifie_le` | `timestamp` | défaut `now()`, auto-MAJ | Dernière modification |

**Trigger** : `trg_meta_modifie_le` (BEFORE UPDATE) → met à jour `modifie_le`.

---

### Table `donnee_collectee`

Table de **faits** : valeurs saisies par les collecteurs pour un triplet (indicateur, pays, année). Coeur opérationnel de l'application.

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | `integer` | PK, auto | Identifiant |
| `indicateur_id` | `integer` | NOT NULL, FK → `indicateur(id)` | Indicateur mesuré |
| `pays_id` | `integer` | NOT NULL, FK → `pays(id)` | Pays concerné |
| `utilisateur_id` | `integer` | NOT NULL, FK → `utilisateur(id)` | Auteur de la saisie |
| `annee_reference` | `smallint` | NOT NULL, CHECK 1990 ≤ x ≤ 2100 | Année de référence |
| `valeur_numerique` | `numeric(20,4)` | NULL | Valeur quantitative |
| `valeur_texte` | `text` | NULL | Valeur qualitative |
| `unite_saisie` | `varchar(150)` | NULL | Unité effectivement saisie |
| `source_donnee` | `text` | NULL | Source de la donnée |
| `methode_collecte` | `varchar(300)` | NULL | Méthode de collecte |
| `commentaire` | `text` | NULL | Note libre du collecteur |
| `statut` | `varchar(20)` | NOT NULL, défaut `brouillon`, CHECK ∈ {`brouillon`, `soumis`, `valide`, `rejete`} | État du workflow |
| `valide_par` | `integer` | FK → `utilisateur(id)`, NULL | Administrateur validant |
| `valide_le` | `timestamp` | NULL | Date de validation |
| `motif_rejet` | `text` | NULL | Raison du rejet le cas échéant |
| `cree_le` | `timestamp` | défaut `now()` | Création |
| `modifie_le` | `timestamp` | défaut `now()`, auto-MAJ | Dernière modification |

**Contrainte UNIQUE** : `(indicateur_id, pays_id, annee_reference)` — une seule valeur par triplet.
**Index** : `idx_dc_indicateur`, `idx_dc_pays`, `idx_dc_annee`, `idx_dc_statut`.
**Trigger** : `trg_donnee_modifie_le` (BEFORE UPDATE) → met à jour `modifie_le`.

---

## 5. Fonctions et triggers

### Fonction `update_modifie_le()`

```sql
CREATE OR REPLACE FUNCTION public.update_modifie_le()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.modifie_le = NOW();
    RETURN NEW;
END;
$$;
```

Utilisée par les triggers `BEFORE UPDATE` sur :

- `metadonnee_indicateur` → `trg_meta_modifie_le`
- `donnee_collectee` → `trg_donnee_modifie_le`

---

## 6. Workflow de validation des données

```
[brouillon] ──soumission──► [soumis] ──admin valide──► [valide]
                               │
                               └──admin rejette──► [rejete]
                                                     (motif_rejet renseigné)
```

- Lors d'une validation : `valide_par` et `valide_le` sont renseignés.
- Lors d'un rejet : `motif_rejet` doit être renseigné par l'administrateur.

---

## 7. Règles d'intégrité clés

1. **Unicité de saisie** : impossible d'avoir deux valeurs pour le même (indicateur, pays, année).
2. **Suppression d'un indicateur** : `CASCADE` sur `metadonnee_indicateur`, mais bloquée si des `donnee_collectee` y font référence (RESTRICT implicite).
3. **Suppression d'un utilisateur** : bloquée s'il a saisi ou validé des données.
4. **Année plausible** : bornée entre 1990 et 2100.
5. **Rôles** : seulement `collecteur` ou `admin`.
6. **Sources d'indicateurs** : seulement `CISAT` ou `BASICSET`.

---

## 8. Volumétrie actuelle (snapshot au 2026-05-20)

| Table | Lignes |
|---|---:|
| `pays` | 1 |
| `utilisateur` | 1 |
| `indicateur` | 515 |
| `metadonnee_indicateur` | 515 |
| `donnee_collectee` | 3 |

La base est encore en phase d'amorçage : catalogue d'indicateurs déjà chargé, collecte à démarrer.
