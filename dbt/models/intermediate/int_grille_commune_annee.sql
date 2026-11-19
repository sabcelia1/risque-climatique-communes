-- Grille complète commune x année x famille modélisée, avec des zéros les années
-- sans reconnaissance : indispensable pour que « 5 lignes précédentes » signifie
-- bien « 5 années précédentes » dans les fenêtres glissantes.
-- La grille va jusqu'à annee_fin + 1 : c'est l'année à prédire (cible inconnue).
with annees as (
    {{ serie_annees(var('annee_debut'), var('annee_fin') + 1) }}
),

familles as (
    {% for famille in var('derniere_annee_evaluable') %}
    select '{{ famille }}' as famille_peril {% if not loop.last %}union all{% endif %}
    {% endfor %}
),

comptes as (
    select code_insee, annee, famille_peril, count(*) as nb_evenements
    from {{ ref('int_evenements') }}
    group by 1, 2, 3
),

comptes_tous_perils as (
    select code_insee, annee, count(*) as nb_evenements_tous_perils
    from {{ ref('int_evenements') }}
    group by 1, 2
)

select
    c.code_insee,
    c.code_departement,
    a.annee,
    f.famille_peril,
    coalesce(n.nb_evenements, 0)                              as nb_evenements,
    coalesce(t.nb_evenements_tous_perils, 0)
      - coalesce(n.nb_evenements, 0)                          as nb_evenements_autres_perils
from {{ ref('stg_communes') }} as c
cross join annees as a
cross join familles as f
left join comptes as n
  on n.code_insee = c.code_insee and n.annee = a.annee and n.famille_peril = f.famille_peril
left join comptes_tous_perils as t
  on t.code_insee = c.code_insee and t.annee = a.annee
