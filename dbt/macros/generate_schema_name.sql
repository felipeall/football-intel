{# Models land in the schema they name (`staging`, `marts`), not `<target>_<schema>`. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ custom_schema_name | trim if custom_schema_name else target.schema }}
{%- endmacro %}
