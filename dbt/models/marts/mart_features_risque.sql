-- Table d'entraînement du modèle (étape 3) : une ligne par commune, année et
-- famille de péril. La cible est « au moins une reconnaissance cette année ».
-- RÈGLE ANTI-FUITE : toutes les variables explicatives n'utilisent que les années
-- STRICTEMENT antérieures à l'année de la ligne (fenêtres terminant à « 1 preceding »).
-- Le test tests/test_absence_de_fuite.sql le vérifie par un calcul indépendant.
{% set par_commune = "partition by code_insee, famille_peril order by annee" %}

with grille as (
    select * from {{ ref('int_grille_commune_annee') }}
),

historique as (
    select
        *,
        coalesce(sum(nb_evenements) over ({{ par_commune }}
            rows between 1 preceding and 1 preceding), 0)          as nb_evt_1an,
        coalesce(sum(nb_evenements) over ({{ par_commune }}
            rows between 5 preceding and 1 preceding), 0)          as nb_evt_5ans,
        coalesce(sum(nb_evenements) over ({{ par_commune }}
            rows between 10 preceding and 1 preceding), 0)         as nb_evt_10ans,
        coalesce(sum(nb_evenements) over ({{ par_commune }}
            rows between unbounded preceding and 1 preceding), 0)  as nb_evt_depuis_debut,
        coalesce(sum(nb_evenements_autres_perils) over ({{ par_commune }}
            rows between 10 preceding and 1 preceding), 0)         as nb_evt_autres_perils_10ans,
        max(case when nb_evenements > 0 then annee end) over ({{ par_commune }}
            rows between unbounded preceding and 1 preceding)      as derniere_annee_touchee
    from grille
),

-- Part des communes du département touchées l'année précédente (signal régional)
departement as (
    select
        code_departement,
        annee,
        famille_peril,
        avg(case when nb_evenements > 0 then 1.0 else 0.0 end) as taux_communes_touchees
    from grille
    group by 1, 2, 3
)

select
    h.code_insee,
    h.code_departement,
    h.annee,
    h.famille_peril,

    -- Cible
    h.nb_evenements,
    case when h.nb_evenements > 0 then 1 else 0 end                as cible,

    -- Historique de la commune (années < annee)
    h.nb_evt_1an,
    h.nb_evt_5ans,
    h.nb_evt_10ans,
    h.nb_evt_depuis_debut,
    h.nb_evt_autres_perils_10ans,
    h.annee - h.derniere_annee_touchee                             as annees_depuis_derniere,

    -- Contexte départemental (année précédente)
    d.taux_communes_touchees                                       as taux_dept_annee_prec,

    -- Caractéristiques de la commune
    c.population,
    c.surface_km2,
    c.population / nullif(c.surface_km2, 0)                        as densite_hab_km2,
    c.latitude,
    c.longitude,

    -- Indicateurs d'usage pour la modélisation
    h.annee <= {{ derniere_annee_evaluable('h.famille_peril') }}   as annee_evaluable,
    h.annee >= {{ var('annee_debut') + var('annees_historique_min') }} as historique_complet
from historique as h
inner join {{ ref('stg_communes') }} as c
  on c.code_insee = h.code_insee
left join departement as d
  on d.code_departement = h.code_departement
 and d.famille_peril = h.famille_peril
 and d.annee = h.annee - 1
