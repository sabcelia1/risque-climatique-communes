{# Test générique : aucune combinaison de colonnes ne doit apparaître deux fois. #}
{% test lignes_uniques(model, colonnes) %}
select {{ colonnes | join(', ') }}, count(*) as nb
from {{ model }}
group by {{ colonnes | join(', ') }}
having count(*) > 1
{% endtest %}
