{# CASE SQL donnant la dernière année évaluable selon la famille de péril. #}
{% macro derniere_annee_evaluable(colonne_famille) %}
  case {{ colonne_famille }}
  {%- for famille, annee in var('derniere_annee_evaluable').items() %}
    when '{{ famille }}' then {{ annee }}
  {%- endfor %}
  end
{% endmacro %}
