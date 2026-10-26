"""Unit test verifying all 19 native Visual Paradigm ERD data types and retained DBMS types."""

import xml.etree.ElementTree as ET
from exporters.xmi_builder import XMIBuilder
from core.state import ProjectState
from core.models import EntityNode, ColumnModel

XMI_NS = "http://schema.omg.org/spec/XMI/2.1"


def test_erd_data_types():
    state = ProjectState()
    builder = XMIBuilder(state)

    # 1. Test all 19 standard Visual Paradigm ERD types from screenshots
    vp_native_types = [
        ("bigint", "bigint", 9),
        ("binary", "binary", 25),
        ("bit", "bit", 3),
        ("blob", "blob", 25),
        ("char", "char", 27),
        ("clob", "clob", 27),
        ("date", "date", 15),
        ("decimal", "decimal", 11),
        ("double", "double", 13),
        ("float", "float", 12),
        ("integer", "integer", 9),
        ("numeric", "numeric", 11),
        ("real", "real", 12),
        ("smallint", "smallint", 8),
        ("time", "time", 16),
        ("timestamp", "timestamp", 17),
        ("tinyint", "tinyint", 8),
        ("varbinary", "varbinary", 25),
        ("varchar", "varchar", 27),
    ]

    for type_input, expected_name, expected_type_int in vp_native_types:
        type_int, type_name, length = builder._map_sql_type_to_vp(type_input)
        assert type_name == expected_name, f"Input '{type_input}': expected typeName '{expected_name}', got '{type_name}'"
        assert type_int == expected_type_int, f"Input '{type_input}': expected type_int {expected_type_int}, got {type_int}"

    # 2. Test retained DBMS / PostgreSQL types requested by user
    retained_types = [
        ("int8", "int8", 9),
        ("int4", "int4", 9),
        ("int2", "int2", 8),
        ("text", "text", 27),
        ("bool", "bool", 3),
        ("boolean", "bool", 3),
        ("uuid", "uuid", 28),
        ("float4", "float4", 12),
        ("float8", "float8", 13),
        ("bytea", "bytea", 25),
        ("timestamptz", "timestamp with time zone", 17),
        ("timestamp with time zone", "timestamp with time zone", 17),
    ]

    for type_input, expected_name, expected_type_int in retained_types:
        type_int, type_name, length = builder._map_sql_type_to_vp(type_input)
        assert type_name == expected_name, f"Input '{type_input}': expected typeName '{expected_name}', got '{type_name}'"
        assert type_int == expected_type_int, f"Input '{type_input}': expected type_int {expected_type_int}, got {type_int}"

    # 3. Test that normalized types map cleanly
    normalized_types = [
        ("money", "decimal", 11),
        ("timetz", "time", 16),
        ("interval", "varchar", 27),
    ]

    for type_input, expected_name, expected_type_int in normalized_types:
        type_int, type_name, length = builder._map_sql_type_to_vp(type_input)
        assert type_name == expected_name, f"Input '{type_input}' should be normalized to '{expected_name}', got '{type_name}'"
        assert type_int == expected_type_int

    print("All 19 VP ERD types + retained DBMS types + normalized types passed successfully!")


if __name__ == "__main__":
    test_erd_data_types()
