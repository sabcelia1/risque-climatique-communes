select
    cast(code_insee as {{ dbt.type_string() }})        as code_insee,
    cast(nom_commune as {{ dbt.type_string() }})       as nom_commune,
    cast(code_departement as {{ dbt.type_string() }})  as code_departement,
    cast(nom_departement as {{ dbt.type_string() }})   as nom_departement,
    cast(code_region as {{ dbt.type_string() }})       as code_region,
    cast(nom_region as {{ dbt.type_string() }})        as nom_region,
    cast(population as {{ dbt.type_int() }})           as population,
    cast(surface_ha as {{ dbt.type_float() }}) / 100   as surface_km2,
    cast(longitude as {{ dbt.type_float() }})          as longitude,
    cast(latitude as {{ dbt.type_float() }})           as latitude
from {{ source('raw', 'communes') }}
