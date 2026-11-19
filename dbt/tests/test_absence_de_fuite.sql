-- Contrôle anti-fuite, par un calcul INDÉPENDANT de celui du modèle :
-- le modèle part de chaque ligne et regarde en arrière (jointure) ; ce test part
-- de chaque événement et le projette en avant, sur les 5 années où il doit être
-- compté, à condition que son arrêté soit déjà signé. Toute différence signale
-- une variable qui utilise l'année courante, le futur, ou un arrêté pas encore pris.
-- Le test échoue s'il renvoie au moins une ligne.
with decalages as (
    {{ serie_annees(1, 5) }}
),

attendu as (
    select
        e.code_insee,
        e.famille_peril,
        e.annee + d.annee as annee,
        count(*) as nb_attendu
    from {{ ref('int_evenements') }} as e
    cross join decalages as d
    where e.annee + d.annee >= e.annee_connue
    group by 1, 2, 3
),

comparaison as (
    select
        m.code_insee,
        m.famille_peril,
        m.annee,
        m.nb_evt_5ans,
        coalesce(a.nb_attendu, 0) as nb_attendu,
        m.nb_evt_depuis_debut
    from {{ ref('mart_features_risque') }} as m
    left join attendu as a
      on a.code_insee = m.code_insee
     and a.famille_peril = m.famille_peril
     and a.annee = m.annee
)

select *, 'nb_evt_5ans incorrect' as probleme
from comparaison
where nb_evt_5ans != nb_attendu
union all
select *, 'historique non nul la première année' as probleme
from comparaison
where annee = {{ var('annee_debut') }} and nb_evt_depuis_debut != 0
