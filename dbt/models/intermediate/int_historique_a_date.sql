-- Historique de chaque commune TEL QU'IL ÉTAIT CONNU au 1er janvier de l'année :
-- un événement n'est compté que s'il est antérieur à l'année ET si son arrêté a
-- été signé avant cette date. Au 1er janvier, aucune sécheresse de l'année
-- précédente n'est encore reconnue (délai médian : 533 jours) : sans cette règle,
-- le modèle apprendrait avec des informations qu'il n'aura jamais en conditions réelles.
select
    g.code_insee,
    g.code_departement,
    g.annee,
    g.famille_peril,
    g.nb_evenements,
    sum(case when e.famille_peril = g.famille_peril and e.annee = g.annee - 1 then 1 else 0 end)
        as nb_evt_1an,
    sum(case when e.famille_peril = g.famille_peril and e.annee >= g.annee - 5 then 1 else 0 end)
        as nb_evt_5ans,
    sum(case when e.famille_peril = g.famille_peril and e.annee >= g.annee - 10 then 1 else 0 end)
        as nb_evt_10ans,
    sum(case when e.famille_peril = g.famille_peril then 1 else 0 end)
        as nb_evt_depuis_debut,
    sum(case when e.famille_peril != g.famille_peril and e.annee >= g.annee - 10 then 1 else 0 end)
        as nb_evt_autres_perils_10ans,
    max(case when e.famille_peril = g.famille_peril then e.annee end)
        as derniere_annee_touchee
from {{ ref('int_grille_commune_annee') }} as g
left join {{ ref('int_evenements') }} as e
  on e.code_insee = g.code_insee
 and e.annee < g.annee
 and e.annee_connue <= g.annee
group by 1, 2, 3, 4, 5
