{# Liste d'années (une ligne par année) : la syntaxe diffère selon la base. #}
{% macro serie_annees(debut, fin) %}
  {{ return(adapter.dispatch('serie_annees')(debut, fin)) }}
{% endmacro %}

{% macro bigquery__serie_annees(debut, fin) %}
  select annee from unnest(generate_array({{ debut }}, {{ fin }})) as annee
{% endmacro %}

{% macro default__serie_annees(debut, fin) %}
  select cast(generate_series as {{ dbt.type_int() }}) as annee
  from generate_series({{ debut }}, {{ fin }})
{% endmacro %}
