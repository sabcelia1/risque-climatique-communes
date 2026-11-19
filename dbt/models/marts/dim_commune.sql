-- Dimension commune, enrichie d'un résumé de l'historique CatNat (usage descriptif :
-- ces totaux couvrent toute la période et ne doivent PAS servir de variables au modèle).
with resume as (
    select
        code_insee,
        count(*)                                                    as nb_evenements_total,
        sum(case when famille_peril = 'secheresse' then 1 else 0 end) as nb_secheresses,
        sum(case when famille_peril = 'inondation' then 1 else 0 end) as nb_inondations,
        max(annee)                                                  as derniere_annee_touchee
    from {{ ref('int_evenements') }}
    group by 1
)

select
    c.*,
    c.population / nullif(c.surface_km2, 0)       as densite_hab_km2,
    coalesce(r.nb_evenements_total, 0)            as nb_evenements_total,
    coalesce(r.nb_secheresses, 0)                 as nb_secheresses,
    coalesce(r.nb_inondations, 0)                 as nb_inondations,
    r.derniere_annee_touchee
from {{ ref('stg_communes') }} as c
left join resume as r
  on r.code_insee = c.code_insee
