{# Understat escapes names as HTML ("O&#039;Shea"); undo the entities it uses. #}
{% macro html_unescape(expression) -%}
    replace(replace(replace(replace(replace(
        {{ expression }}, '&#039;', ''''), '&quot;', '"'), '&lt;', '<'), '&gt;', '>'), '&amp;', '&')
{%- endmacro %}
