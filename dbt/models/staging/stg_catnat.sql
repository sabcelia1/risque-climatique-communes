-- Reconnaissances CatNat, typées et renommées. Aucune ligne n'est retirée ici :
-- les filtres métier sont faits dans int_evenements.
select
    cast(code_insee as {{ dbt.type_string() }})      as code_insee,
    cast(libelle_peril as {{ dbt.type_string() }})   as libelle_peril,
    cast(famille_peril as {{ dbt.type_string() }})   as famille_peril,
    cast(date_debut as date)                         as date_debut,
    cast(date_fin as date)                           as date_fin,
    cast(date_arrete as date)                        as date_arrete,
    cast(date_jo as date)                            as date_jo,
    cast(annee as {{ dbt.type_int() }})              as annee,
    cast(commune_actuelle as boolean)                as commune_actuelle,
    cast(evenement_repete as boolean)                as evenement_repete,
    cast(duree_suspecte as boolean)                  as duree_suspecte
from {{ source('raw', 'catnat') }}
