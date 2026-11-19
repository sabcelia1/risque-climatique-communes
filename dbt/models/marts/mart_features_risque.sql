-- Table d'entraînement du modèle (étape 3) : une ligne par commune, année et
-- famille de péril. Cibles : « au moins une reconnaissance » sur 1, 3 ou 5 ans.
-- RÈGLE ANTI-FUITE : les variables n'utilisent que les événements antérieurs à
-- l'année ET déjà reconnus au 1er janvier (voir int_historique_a_date).
-- Le test tests/test_absence_de_fuite.sql le vérifie par un calcul indépendant.
with historique as (
    select * from {{ ref('int_historique_a_date') }}
),

-- Fréquence récente dans le département, à date (signal régional)
departement as (
    select
        code_departement,
        annee,
        famille_peril,
        avg(nb_evt_5ans) / 5.0 as taux_dept_5ans
    from historique
    group by 1, 2, 3
)

select
    h.code_insee,
    h.code_departement,
    h.annee,
    h.famille_peril,

    -- Cibles : au moins une reconnaissance sur 1, 3 ou 5 ans à partir de l'année
    h.nb_evenements,
    case when h.nb_evenements > 0 then 1 else 0 end                as cible,
    case when sum(h.nb_evenements) over (partition by h.code_insee, h.famille_peril order by h.annee
              rows between current row and 2 following) > 0 then 1 else 0 end as cible_3ans,
    case when sum(h.nb_evenements) over (partition by h.code_insee, h.famille_peril order by h.annee
              rows between current row and 4 following) > 0 then 1 else 0 end as cible_5ans,

    -- Historique de la commune, connu au 1er janvier
    h.nb_evt_1an,
    h.nb_evt_5ans,
    h.nb_evt_10ans,
    h.nb_evt_depuis_debut,
    h.nb_evt_autres_perils_10ans,
    h.annee - h.derniere_annee_touchee                             as annees_depuis_derniere,
    d.taux_dept_5ans,

    -- Caractéristiques de la commune
    c.population,
    c.surface_km2,
    c.population / nullif(c.surface_km2, 0)                        as densite_hab_km2,
    c.latitude,
    c.longitude,

    -- Exposition physique : part du territoire par niveau d'exposition aux argiles (BRGM 2019)
    a.part_argile_faible,
    a.part_argile_moyen,
    a.part_argile_fort,

    -- Indicateurs d'usage pour la modélisation
    h.annee <= {{ derniere_annee_evaluable('h.famille_peril') }}   as annee_evaluable,
    h.annee + 2 <= {{ derniere_annee_evaluable('h.famille_peril') }} as annee_evaluable_3ans,
    h.annee + 4 <= {{ derniere_annee_evaluable('h.famille_peril') }} as annee_evaluable_5ans,
    h.annee >= {{ var('annee_debut') + var('annees_historique_min') }} as historique_complet,
    h.annee = {{ var('annee_fin') + 1 }}                           as annee_a_predire
from historique as h
inner join {{ ref('stg_communes') }} as c
  on c.code_insee = h.code_insee
left join {{ ref('exposition_argiles') }} as a
  on a.code_insee = h.code_insee
left join departement as d
  on d.code_departement = h.code_departement
 and d.famille_peril = h.famille_peril
 and d.annee = h.annee
