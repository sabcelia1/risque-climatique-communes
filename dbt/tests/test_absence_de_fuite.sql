-- Contrôle anti-fuite : on recalcule indépendamment (jointure, sans fenêtre glissante)
-- le nombre d'événements des 5 années précédentes. Toute différence signale qu'une
-- variable utilise l'année courante ou une année future. Le test échoue s'il
-- renvoie au moins une ligne.
with grille as (
    select code_insee, famille_peril, annee, nb_evenements
    from {{ ref('int_grille_commune_annee') }}
),

recalcul as (
    select
        m.code_insee,
        m.famille_peril,
        m.annee,
        m.nb_evt_5ans,
        m.nb_evt_depuis_debut,
        coalesce(sum(g.nb_evenements), 0) as attendu_5ans
    from {{ ref('mart_features_risque') }} as m
    left join grille as g
      on g.code_insee = m.code_insee
     and g.famille_peril = m.famille_peril
     and g.annee between m.annee - 5 and m.annee - 1
    group by 1, 2, 3, 4, 5
)

select *, 'nb_evt_5ans incorrect' as probleme
from recalcul
where nb_evt_5ans != attendu_5ans
union all
select *, 'historique non nul la première année' as probleme
from recalcul
where annee = {{ var('annee_debut') }} and nb_evt_depuis_debut != 0
