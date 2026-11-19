-- Faits : un événement reconnu distinct par ligne, avec les attributs de la commune
-- utiles aux analyses et à l'assistant en langage naturel (étape 4).
select
    e.code_insee,
    c.nom_commune,
    c.code_departement,
    c.nom_departement,
    c.nom_region,
    e.famille_peril,
    e.libelle_peril,
    e.annee,
    e.date_debut,
    e.date_fin,
    e.date_arrete,
    e.delai_reconnaissance_jours,
    e.duree_suspecte
from {{ ref('int_evenements') }} as e
inner join {{ ref('stg_communes') }} as c
  on c.code_insee = e.code_insee
