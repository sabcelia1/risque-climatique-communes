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
    -- Année à partir de laquelle l'événement est CONNU (au 1er janvier suivant l'arrêté)
    cast(extract(year from coalesce(date_arrete, date_debut)) as {{ dbt.type_int() }}) + 1
                                                          as annee_connue,
    duree_suspecte
from {{ ref('stg_catnat') }}
where not evenement_repete
  and commune_actuelle
  and annee between {{ var('annee_debut') }} and {{ var('annee_fin') }}
