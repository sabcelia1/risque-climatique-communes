-- Événements reconnus distincts (commune x péril x dates), communes actuelles,
-- années de la période d'étude. Les répétitions d'un même événement (arrêtés
-- rectificatifs) et les codes de communes disparues sont écartés.
select
    code_insee,
    famille_peril,
    libelle_peril,
    annee,
    date_debut,
    date_fin,
    date_arrete,
    {{ dbt.datediff('date_debut', 'date_arrete', 'day') }} as delai_reconnaissance_jours,
    duree_suspecte
from {{ ref('stg_catnat') }}
where not evenement_repete
  and commune_actuelle
  and annee between {{ var('annee_debut') }} and {{ var('annee_fin') }}
