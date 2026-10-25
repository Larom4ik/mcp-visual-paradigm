"""XMI 2.1 Builder with OMG Diagram Interchange and Visual Paradigm Native Data Binding.

Features:
1. Exact matching IDs: DiagramElement.subject == ownedMember.xmi:id.
2. Native Visual Paradigm Model Structure: All elements in <uml:Model> are <ownedMember xmi:type="...">.
3. Recursive Nested Packages: Packages inside Packages, Classes inside Packages with dynamic bounding box calculation.
4. Smart Specialized Layout Engines:
   - HierarchicalClassLayout (Layered DAG for inheritance hierarchies and package containment).
   - UseCaseTierLayout (3-tier columnar architecture: Actors -> Core Use Cases -> Sub-cases/Secondary Actors).
   - ERDClusterLayout (Topological order by Foreign-Key dependencies).
   - StateMachineFlowLayout (Horizontal pipeline flow with loopback offsets).
5. Clean Diagram Rendering: Pure OMG <uml:Diagram> and <uml:DiagramElement> with Visual Paradigm extensions.
"""

import math
import os
import re
import uuid
import xml.etree.ElementTree as ET
from typing import Optional
from core.models import (
    BaseNode,
    ClassNode,
    EntityNode,
    MethodModel,
    NoteNode,
    PackageNode,
    RelationModel,
    SystemBoundaryNode,
    UseCaseNode,
)
from core.state import ProjectState
from exporters.layout_engine import (
    BoundingBoxCalculator,
    ERDClusterLayout,
    HierarchicalClassLayout,
    NodePlacement,
    StateMachineFlowLayout,
    UseCaseTierLayout,
    WaypointRoutingEngine,
)

XMI_NS = "http://schema.omg.org/spec/XMI/2.1"
UML_NS = "http://schema.omg.org/spec/UML/2.0"


def sanitize_id(raw_str: str) -> str:
    """Ensure an ID is a valid XML NCName."""
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", raw_str)
    if not cleaned or cleaned[0].isdigit():
        return f"_{cleaned}"
    return cleaned


def create_uuid_id(prefix: str = "xmi") -> str:
    """Generate a valid XML ID with given prefix."""
    return f"{prefix}_{uuid.uuid4().hex}"


class XMIBuilder:
    """Generates standard UML 2.x XMI 2.1 with verified Data Binding and Smart Diagram Interchange."""

    def __init__(self, state: ProjectState) -> None:
        self.state = state
        self.root: Optional[ET.Element] = None
        self.model: Optional[ET.Element] = None
        self.known_primitive_ids: dict[str, str] = {}

    def _get_or_create_type_id(self, type_name: str) -> Optional[str]:
        cleaned = (type_name or "").strip()
        if not cleaned or cleaned.lower() in ("void", "none"):
            return None

        cls = self.state.find_class(cleaned)
        if cls:
            return cls.id

        ent = self.state.find_entity(cleaned)
        if ent:
            return ent.id

        norm_key = cleaned.lower()
        if norm_key not in self.known_primitive_ids:
            pt_id = f"{sanitize_id(norm_key)}_id"
            self.known_primitive_ids[norm_key] = pt_id
            if self.model is not None:
                ET.SubElement(
                    self.model,
                    "ownedMember",
                    {
                        f"{{{XMI_NS}}}type": "uml:DataType",
                        f"{{{XMI_NS}}}id": pt_id,
                        "name": cleaned,
                        "visibility": "public",
                    },
                )
        return self.known_primitive_ids[norm_key]

    def _append_multiplicity(self, parent: ET.Element, mult_str: str, prefix_id: str) -> None:
        mult_clean = (mult_str or "").strip()
        if not mult_clean:
            return
        if ".." in mult_clean:
            parts = mult_clean.split("..", 1)
            low = parts[0].strip()
            high = parts[1].strip()
        elif mult_clean == "*":
            low = "0"
            high = "*"
        else:
            low = "0" if mult_clean == "0" else "1"
            high = mult_clean

        ET.SubElement(
            parent,
            "lowerValue",
            {
                f"{{{XMI_NS}}}type": "uml:LiteralString",
                f"{{{XMI_NS}}}id": f"{prefix_id}_multiplicity_lowerValue",
                "value": str(low),
            },
        )
        if high != "1" or low == "0":
            ET.SubElement(
                parent,
                "upperValue",
                {
                    f"{{{XMI_NS}}}type": "uml:LiteralString",
                    f"{{{XMI_NS}}}id": f"{prefix_id}_multiplicity_upperValue",
                    "value": str(high),
                },
            )

    def _map_sql_type_to_vp(self, type_str: str) -> tuple[int, str, int]:
        """Map SQL data type string to (vp_type_int, type_name, length).

        Supports all native Visual Paradigm ERD types from the standard palette:
        bigint, binary, bit, blob, char, clob, date, decimal, double, float,
        integer, numeric, real, smallint, time, timestamp, tinyint, varbinary, varchar.

        Also retains key DBMS / PostgreSQL types (int8, int4, int2, bool, uuid) as requested.
        Superfluous types (money, timestamptz, timetz, interval) are normalized.
        """
        import re
        t_upper = (type_str or "VARCHAR").upper().strip()
        length = 0
        match = re.search(r'\((\d+)(?:,\s*\d+)?\)', t_upper)
        if match:
            try:
                length = int(match.group(1))
            except ValueError:
                length = 0

        # 1. Integer / Serial types
        if "BIGINT" in t_upper or "BIGSERIAL" in t_upper or "SERIAL8" in t_upper:
            return 9, "bigint", length or 19
        elif "INT8" in t_upper:
            return 9, "int8", length or 19
        elif "TINYINT" in t_upper:
            return 8, "tinyint", length or 3
        elif "SMALLINT" in t_upper:
            return 8, "smallint", length or 5
        elif "INT2" in t_upper:
            return 8, "int2", length or 5
        elif "INT4" in t_upper:
            return 9, "int4", length or 10
        elif re.search(r'\b(INTEGER|INT)\b', t_upper):
            return 9, "integer", length or 10
        elif any(k in t_upper for k in ("SERIAL", "SERIAL4")):
            return 9, "serial4", length or 10

        # 2. Floating-point & Fixed-point types
        elif "DOUBLE" in t_upper:
            return 13, "double", 0
        elif "FLOAT8" in t_upper:
            return 13, "float8", 0
        elif "REAL" in t_upper:
            return 12, "real", 0
        elif "FLOAT4" in t_upper:
            return 12, "float4", 0
        elif "FLOAT" in t_upper:
            return 12, "float", 0
        elif "NUMERIC" in t_upper:
            return 11, "numeric", length or 10
        elif any(k in t_upper for k in ("DECIMAL", "DEC", "MONEY")):
            return 11, "decimal", length or 10

        # 3. String & Character types
        elif "VARCHAR" in t_upper or "VARYING" in t_upper or "INTERVAL" in t_upper:
            return 27, "varchar", length or 255
        elif "CHAR" in t_upper or "BPCHAR" in t_upper:
            return 27, "char", length or 1
        elif "CLOB" in t_upper:
            return 27, "clob", 0
        elif any(k in t_upper for k in ("TEXT", "STRING", "JSONB", "JSON")):
            return 27, "clob", 0

        # 4. Date & Time types (timestamptz -> timestamp, timetz -> time)
        elif "TIMESTAMP" in t_upper or "DATETIME" in t_upper:
            return 17, "timestamp", 0
        elif "TIME" in t_upper:
            return 16, "time", 0
        elif "DATE" in t_upper:
            return 15, "date", 0

        # 5. Boolean & Bit
        elif "BIT" in t_upper:
            return 3, "bit", length or 1
        elif any(k in t_upper for k in ("BOOL", "BOOLEAN")):
            return 3, "bool", 0

        # 6. Binary / Large Objects
        elif "BLOB" in t_upper:
            return 25, "blob", 0
        elif "VARBINARY" in t_upper:
            return 25, "varbinary", length or 255
        elif "BINARY" in t_upper:
            return 25, "binary", length or 1
        elif "BYTEA" in t_upper:
            return 25, "bytea", length or 0

        # 7. Identifiers & Structured types
        elif "UUID" in t_upper:
            return 28, "uuid", 0

        # Default fallback
        else:
            clean_type = re.sub(r'\(.*?\)', '', t_upper).lower().strip() or "varchar"
            return 27, clean_type, length or 255

    # ---------------------------------------------------------
    # Metamodel Builders (ownedMember tags, public visibility, full VP metadata)
    # ---------------------------------------------------------

    def _emit_class_element(
        self,
        parent_elem: ET.Element,
        cls: ClassNode,
        generalizations_by_source: dict[str, list[tuple[str, str]]],
    ) -> ET.Element:
        """Emit a single UML Class or Interface classifier into the specified parent element."""
        class_elem = ET.SubElement(
            parent_elem,
            "ownedMember",
            {
                f"{{{XMI_NS}}}type": "uml:Class",
                f"{{{XMI_NS}}}id": cls.id,
                "name": cls.name,
                "visibility": "public",
                "isAbstract": "true" if cls.is_abstract else "false",
                "isActive": "false",
                "isLeaf": "false",
            },
        )

        if cls.element_type == "Interface":
            annot = ET.SubElement(
                class_elem,
                "eAnnotations",
                {f"{{{XMI_NS}}}id": create_uuid_id("annot"), "source": "Stereotype"},
            )
            ET.SubElement(annot, "details", {f"{{{XMI_NS}}}id": create_uuid_id("det"), "key": "interface", "value": "true"})

        cls_vp_ext = ET.SubElement(class_elem, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
        ET.SubElement(cls_vp_ext, "isRoot", {f"{{{XMI_NS}}}value": "false"})
        ET.SubElement(cls_vp_ext, "modelType", {"value": cls.element_type})
        ET.SubElement(cls_vp_ext, "businessModel", {f"{{{XMI_NS}}}value": "false"})
        ET.SubElement(cls_vp_ext, "qualityScore", {"value": "-1"})
        if getattr(cls, "description", ""):
            ET.SubElement(
                class_elem,
                "ownedComment",
                {
                    f"{{{XMI_NS}}}type": "uml:Comment",
                    f"{{{XMI_NS}}}id": f"{cls.id}_comment",
                    "body": cls.description,
                },
            )
            ET.SubElement(cls_vp_ext, "documentation", {"value": cls.description})

        # Attributes STRICTLY inside class
        for attr in cls.attributes:
            attr_dict = {
                f"{{{XMI_NS}}}type": "uml:Property",
                f"{{{XMI_NS}}}id": attr.id,
                "name": attr.name,
                "visibility": attr.visibility or "public",
                "aggregation": "none",
                "isDerived": "false",
                "isDerivedUnion": "false",
                "isID": "false",
                "isLeaf": "false",
                "isReadOnly": "false",
                "isStatic": "false",
            }
            type_id = self._get_or_create_type_id(attr.type)
            if type_id:
                attr_dict["type"] = type_id

            prop_elem = ET.SubElement(class_elem, "ownedAttribute", attr_dict)
            attr_vp_ext = ET.SubElement(prop_elem, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
            ET.SubElement(attr_vp_ext, "attribute")
            ET.SubElement(attr_vp_ext, "isAbstract", {f"{{{XMI_NS}}}value": "false"})
            ET.SubElement(attr_vp_ext, "isVisble", {f"{{{XMI_NS}}}value": "true"})
            ET.SubElement(attr_vp_ext, "qualityScore", {"value": "-1"})
            if getattr(attr, "description", ""):
                ET.SubElement(
                    prop_elem,
                    "ownedComment",
                    {
                        f"{{{XMI_NS}}}type": "uml:Comment",
                        f"{{{XMI_NS}}}id": f"{attr.id}_comment",
                        "body": attr.description,
                    },
                )
                ET.SubElement(attr_vp_ext, "documentation", {"value": attr.description})

            if attr.multiplicity:
                self._append_multiplicity(prop_elem, attr.multiplicity, attr.id)

        # Methods STRICTLY inside class
        for method in cls.methods:
            op_elem = ET.SubElement(
                class_elem,
                "ownedOperation",
                {
                    f"{{{XMI_NS}}}type": "uml:Operation",
                    f"{{{XMI_NS}}}id": method.id,
                    "name": method.name,
                    "visibility": "public",
                    "isAbstract": "false",
                    "isLeaf": "false",
                    "isOrdered": "false",
                    "isQuery": "false",
                    "isStatic": "false",
                    "isUnique": "true",
                },
            )
            ret_type_id = self._get_or_create_type_id(method.return_type)
            if ret_type_id:
                ET.SubElement(
                    op_elem,
                    "ownedParameter",
                    {
                        f"{{{XMI_NS}}}type": "uml:Parameter",
                        f"{{{XMI_NS}}}id": f"{method.id}_return",
                        "kind": "return",
                        "type": ret_type_id,
                    },
                )
            for param in method.params:
                p_dict = {
                    f"{{{XMI_NS}}}type": "uml:Parameter",
                    f"{{{XMI_NS}}}id": param.id,
                    "name": param.name,
                    "kind": param.direction or "in",
                }
                p_type_id = self._get_or_create_type_id(param.type)
                if p_type_id:
                    p_dict["type"] = p_type_id
                ET.SubElement(op_elem, "ownedParameter", p_dict)

            op_vp_ext = ET.SubElement(op_elem, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
            ET.SubElement(op_vp_ext, "returnTypeDocumentation", {f"{{{XMI_NS}}}value": ""})
            props = ET.SubElement(op_vp_ext, "properties")
            ET.SubElement(props, "property", {"name": "visible", "type": "boolean", "value": "true"})
            ET.SubElement(props, "property", {"name": "qualityScore", "type": "int", "value": "-1"})
            ET.SubElement(op_vp_ext, "qualityScore", {"value": "-1"})
            if getattr(method, "description", ""):
                ET.SubElement(
                    op_elem,
                    "ownedComment",
                    {
                        f"{{{XMI_NS}}}type": "uml:Comment",
                        f"{{{XMI_NS}}}id": f"{method.id}_comment",
                        "body": method.description,
                    },
                )
                ET.SubElement(op_vp_ext, "documentation", {"value": method.description})

        # Generalizations inside class
        if cls.id in generalizations_by_source:
            for rel_id, parent_id in generalizations_by_source[cls.id]:
                gen_elem = ET.SubElement(
                    class_elem,
                    "generalization",
                    {
                        f"{{{XMI_NS}}}type": "uml:Generalization",
                        f"{{{XMI_NS}}}id": rel_id,
                        "general": parent_id,
                    },
                )
                gen_vp = ET.SubElement(gen_elem, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
                ET.SubElement(gen_vp, "qualityScore", {"value": "-1"})

        return class_elem

    def _emit_package_element(
        self,
        parent_elem: ET.Element,
        pkg: PackageNode,
        generalizations_by_source: dict[str, list[tuple[str, str]]],
    ) -> ET.Element:
        """Emit a Package and recursively nest child packages and member classes."""
        pkg_elem = ET.SubElement(
            parent_elem,
            "ownedMember",
            {
                f"{{{XMI_NS}}}type": "uml:Package",
                f"{{{XMI_NS}}}id": pkg.id,
                "name": pkg.name,
                "visibility": "public",
                "isAbstract": "false",
                "isLeaf": "false",
            },
        )
        pkg_vp_ext = ET.SubElement(pkg_elem, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
        ET.SubElement(pkg_vp_ext, "isRoot", {f"{{{XMI_NS}}}value": "false"})
        ET.SubElement(pkg_vp_ext, "modelType", {"value": "Package"})
        ET.SubElement(pkg_vp_ext, "businessModel", {f"{{{XMI_NS}}}value": "false"})
        ET.SubElement(pkg_vp_ext, "qualityScore", {"value": "-1"})
        if getattr(pkg, "description", ""):
            ET.SubElement(
                pkg_elem,
                "ownedComment",
                {
                    f"{{{XMI_NS}}}type": "uml:Comment",
                    f"{{{XMI_NS}}}id": f"{pkg.id}_comment",
                    "body": pkg.description,
                },
            )
            ET.SubElement(pkg_vp_ext, "documentation", {"value": pkg.description})

        # 1. Nested sub-packages
        for sub_id in pkg.child_package_ids:
            if sub_id in self.state.packages:
                sub_pkg = self.state.packages[sub_id]
                self._emit_package_element(pkg_elem, sub_pkg, generalizations_by_source)

        # 2. Member classes inside this package
        for cid in pkg.class_ids:
            if cid in self.state.classes:
                cls_obj = self.state.classes[cid]
                self._emit_class_element(pkg_elem, cls_obj, generalizations_by_source)

        return pkg_elem

    def _build_class_metamodel(self) -> None:
        assert self.model is not None

        generalizations_by_source: dict[str, list[tuple[str, str]]] = {}
        top_level_relations: list[RelationModel] = []

        for rel in self.state.class_relations:
            if rel.type == "Generalization":
                generalizations_by_source.setdefault(rel.source_id, []).append((rel.id, rel.target_id))
            else:
                top_level_relations.append(rel)

        # 1. Emit Packages hierarchy (starting from root packages that have no parent_package_id)
        root_packages = [p for p in self.state.packages.values() if not p.parent_package_id]
        for pkg in root_packages:
            self._emit_package_element(self.model, pkg, generalizations_by_source)

        # 2. Emit Top-Level Classes (classes not assigned to any package)
        for cls in self.state.classes.values():
            if not cls.package_id:
                self._emit_class_element(self.model, cls, generalizations_by_source)

        # 3. Top-level class relations (Association, Composition, Dependency, Realization)
        for rel in top_level_relations:
            src = self.state.find_class(rel.source_id)
            tgt = self.state.find_class(rel.target_id)
            if not src or not tgt:
                continue

            if rel.type == "Dependency":
                dep_elem = ET.SubElement(
                    self.model,
                    "ownedMember",
                    {
                        f"{{{XMI_NS}}}type": "uml:Dependency",
                        f"{{{XMI_NS}}}id": rel.id,
                        "name": rel.name or f"{src.name}_depends_on_{tgt.name}",
                        "visibility": "public",
                        "client": src.id,
                        "supplier": tgt.id,
                    },
                )
                dep_vp = ET.SubElement(dep_elem, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
                ET.SubElement(dep_vp, "qualityScore", {"value": "-1"})
            elif rel.type == "Realization":
                real_elem = ET.SubElement(
                    self.model,
                    "ownedMember",
                    {
                        f"{{{XMI_NS}}}type": "uml:Realization",
                        f"{{{XMI_NS}}}id": rel.id,
                        "name": rel.name or f"{src.name}_realizes_{tgt.name}",
                        "visibility": "public",
                        "client": src.id,
                        "supplier": tgt.id,
                        "realizingClassifier": tgt.id,
                    },
                )
                real_vp = ET.SubElement(real_elem, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
                ET.SubElement(real_vp, "qualityScore", {"value": "-1"})
            else:
                end_src_id = f"{rel.id}_end_src"
                end_tgt_id = f"{rel.id}_end_tgt"

                assoc_elem = ET.SubElement(
                    self.model,
                    "ownedMember",
                    {
                        f"{{{XMI_NS}}}type": "uml:Association",
                        f"{{{XMI_NS}}}id": rel.id,
                        "name": rel.name or f"{src.name}_{tgt.name}_{rel.type}",
                        "visibility": "public",
                        "isAbstract": "false",
                        "isDerived": "false",
                        "isLeaf": "false",
                    },
                )
                ET.SubElement(assoc_elem, "memberEnd", {f"{{{XMI_NS}}}idref": end_src_id})
                src_end_attrs = {
                    f"{{{XMI_NS}}}type": "uml:Property",
                    f"{{{XMI_NS}}}id": end_src_id,
                    "name": src.name.lower(),
                    "visibility": "public",
                    "type": src.id,
                    "association": rel.id,
                    "aggregation": "none",
                    "isDerived": "false",
                    "isDerivedUnion": "false",
                    "isLeaf": "false",
                    "isNavigable": "true",
                    "isReadOnly": "false",
                    "isStatic": "false",
                }
                if rel.type == "Composition":
                    src_end_attrs["aggregation"] = "composite"
                elif rel.type == "Aggregation":
                    src_end_attrs["aggregation"] = "shared"

                src_end = ET.SubElement(assoc_elem, "ownedEnd", src_end_attrs)
                src_end_vp = ET.SubElement(src_end, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
                ET.SubElement(src_end_vp, "associationEnd")
                ET.SubElement(src_end_vp, "qualityScore", {"value": "-1"})
                if rel.source_multiplicity:
                    self._append_multiplicity(src_end, rel.source_multiplicity, end_src_id)

                ET.SubElement(assoc_elem, "memberEnd", {f"{{{XMI_NS}}}idref": end_tgt_id})
                tgt_end_attrs = {
                    f"{{{XMI_NS}}}type": "uml:Property",
                    f"{{{XMI_NS}}}id": end_tgt_id,
                    "name": tgt.name.lower(),
                    "visibility": "public",
                    "type": tgt.id,
                    "association": rel.id,
                    "aggregation": "none",
                    "isDerived": "false",
                    "isDerivedUnion": "false",
                    "isLeaf": "false",
                    "isNavigable": "true",
                    "isReadOnly": "false",
                    "isStatic": "false",
                }
                tgt_end = ET.SubElement(assoc_elem, "ownedEnd", tgt_end_attrs)
                tgt_end_vp = ET.SubElement(tgt_end, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
                ET.SubElement(tgt_end_vp, "associationEnd")
                ET.SubElement(tgt_end_vp, "qualityScore", {"value": "-1"})
                if rel.target_multiplicity:
                    self._append_multiplicity(tgt_end, rel.target_multiplicity, end_tgt_id)

                assoc_vp = ET.SubElement(assoc_elem, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
                ET.SubElement(assoc_vp, "qualityScore", {"value": "-1"})

    def _build_er_metamodel(self) -> None:
        assert self.model is not None

        for ent in self.state.entities.values():
            ent_elem = ET.SubElement(
                self.model,
                "ownedMember",
                {
                    f"{{{XMI_NS}}}type": "uml:dbTable",
                    f"{{{XMI_NS}}}id": ent.id,
                    "name": ent.name,
                    "visibility": "public",
                    "isAbstract": "false",
                    "isActive": "false",
                    "isLeaf": "false",
                    "syncType": "1",
                    "type": "0",
                    "ormSyncState": "1",
                },
            )

            e_annot = ET.SubElement(
                ent_elem,
                "eAnnotations",
                {f"{{{XMI_NS}}}id": create_uuid_id("annot"), "source": "Stereotype"},
            )
            ET.SubElement(e_annot, "details", {f"{{{XMI_NS}}}id": create_uuid_id("det"), "key": "entity", "value": "true"})
            ET.SubElement(e_annot, "details", {f"{{{XMI_NS}}}id": create_uuid_id("det"), "key": "modelType", "value": "DBTable"})

            ent_vp_ext = ET.SubElement(ent_elem, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
            ET.SubElement(ent_vp_ext, "isRoot", {f"{{{XMI_NS}}}value": "false"})
            ET.SubElement(ent_vp_ext, "modelType", {"value": "DBTable"})
            ET.SubElement(ent_vp_ext, "businessModel", {f"{{{XMI_NS}}}value": "false"})
            ET.SubElement(ent_vp_ext, "qualityScore", {"value": "-1"})
            if getattr(ent, "description", ""):
                ET.SubElement(
                    ent_elem,
                    "ownedComment",
                    {
                        f"{{{XMI_NS}}}type": "uml:Comment",
                        f"{{{XMI_NS}}}id": f"{ent.id}_comment",
                        "body": ent.description,
                    },
                )
                ET.SubElement(ent_vp_ext, "documentation", {"value": ent.description})

            # 1. Native VP children container for DBTable importer (v/dqn/ai.class)
            childrens_elem = ET.SubElement(ent_elem, "childrens")
            matching_fks = [
                rel.id for rel in self.state.er_relations
                if rel.target_id == ent.id or rel.source_id == ent.id
            ]
            for col in ent.columns:
                col_type_int, col_type_name, col_len = self._map_sql_type_to_vp(col.type)
                if col.length:
                    col_len = col.length

                col_nullable_str = str(col.is_nullable).lower()
                col_unique_str = str(getattr(col, "is_unique", False)).lower()
                col_pk_str = str(col.is_primary_key).lower()
                col_fk_str = str(col.is_foreign_key).lower()

                col_elem_attrs = {
                    f"{{{XMI_NS}}}type": "uml:dbColumn",
                    f"{{{XMI_NS}}}id": col.id,
                    "name": col.name,
                    "type": str(col_type_int),
                    "typeName": col_type_name,
                    "length": str(col_len),
                    "scale": "0",
                    "nullable": col_nullable_str,
                    "unique": col_unique_str,
                    "primaryKey": col_pk_str,
                    "foreignKey": col_fk_str,
                    "syncType": "1",
                }
                if col.is_foreign_key and matching_fks:
                    col_elem_attrs["foreignKeyConstraints"] = matching_fks[0]
                if col.is_primary_key:
                    col_elem_attrs["idGenerator"] = "native"
                if getattr(col, "default_value", None):
                    col_elem_attrs["defaultValue"] = str(col.default_value)

                col_elem = ET.SubElement(childrens_elem, "dbColumn", col_elem_attrs)
                col_vp = ET.SubElement(col_elem, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
                ET.SubElement(col_vp, "modelType", {"value": "DBColumn"})
                ET.SubElement(col_vp, "nullable", {"value": col_nullable_str})
                ET.SubElement(col_vp, "unique", {"value": col_unique_str})
                ET.SubElement(col_vp, "primaryKey", {"value": col_pk_str})
                ET.SubElement(col_vp, "foreignKey", {"value": col_fk_str})
                if col.is_foreign_key and matching_fks:
                    ET.SubElement(col_vp, "foreignKeyConstraints", {"value": matching_fks[0]})
                if getattr(col, "description", ""):
                    ET.SubElement(col_vp, "documentation", {"value": col.description})

            # 2. Standard UML ownedAttribute elements for backward compatibility and test assertions
            for col in ent.columns:
                col_attrs = {
                    f"{{{XMI_NS}}}type": "uml:Property",
                    f"{{{XMI_NS}}}id": f"{col.id}_attr",
                    "name": col.name,
                    "visibility": "public",
                    "aggregation": "none",
                    "isDerived": "false",
                    "isDerivedUnion": "false",
                    "isID": "false",
                    "isLeaf": "false",
                    "isReadOnly": "false",
                    "isStatic": "false",
                }
                col_type_id = self._get_or_create_type_id(col.type)
                if col_type_id:
                    col_attrs["type"] = col_type_id

                prop_elem = ET.SubElement(ent_elem, "ownedAttribute", col_attrs)
                col_vp_ext = ET.SubElement(prop_elem, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
                ET.SubElement(col_vp_ext, "attribute")
                ET.SubElement(col_vp_ext, "modelType", {"value": "DBColumn"})
                ET.SubElement(col_vp_ext, "isVisble", {f"{{{XMI_NS}}}value": "true"})
                ET.SubElement(col_vp_ext, "isVisible", {f"{{{XMI_NS}}}value": "true"})
                ET.SubElement(col_vp_ext, "qualityScore", {"value": "-1"})
                if getattr(col, "description", ""):
                    ET.SubElement(
                        prop_elem,
                        "ownedComment",
                        {
                            f"{{{XMI_NS}}}type": "uml:Comment",
                            f"{{{XMI_NS}}}id": f"{col.id}_comment",
                            "body": col.description,
                        },
                    )
                    ET.SubElement(col_vp_ext, "documentation", {"value": col.description})

                col_annot = ET.SubElement(
                    prop_elem,
                    "eAnnotations",
                    {f"{{{XMI_NS}}}id": create_uuid_id("annot"), "source": "Stereotype"},
                )
                ET.SubElement(col_annot, "details", {f"{{{XMI_NS}}}id": create_uuid_id("det"), "key": "column", "value": "true"})
                ET.SubElement(col_annot, "details", {f"{{{XMI_NS}}}id": create_uuid_id("det"), "key": "modelType", "value": "DBColumn"})
                if col.is_primary_key:
                    ET.SubElement(col_annot, "details", {f"{{{XMI_NS}}}id": create_uuid_id("det"), "key": "primaryKey", "value": "true"})
                    ET.SubElement(col_annot, "details", {f"{{{XMI_NS}}}id": create_uuid_id("det"), "key": "stereotype", "value": "PK"})
                if col.is_foreign_key:
                    ET.SubElement(col_annot, "details", {f"{{{XMI_NS}}}id": create_uuid_id("det"), "key": "foreignKey", "value": "true"})
                    ET.SubElement(col_annot, "details", {f"{{{XMI_NS}}}id": create_uuid_id("det"), "key": "stereotype", "value": "FK"})
                if getattr(col, "is_unique", False):
                    ET.SubElement(col_annot, "details", {f"{{{XMI_NS}}}id": create_uuid_id("det"), "key": "unique", "value": "true"})
                    ET.SubElement(col_annot, "details", {f"{{{XMI_NS}}}id": create_uuid_id("det"), "key": "uniqueConstraint", "value": "true"})
                    if not col.is_primary_key:
                        ET.SubElement(col_annot, "details", {f"{{{XMI_NS}}}id": create_uuid_id("det"), "key": "stereotype", "value": "U"})
                if not col.is_nullable:
                    ET.SubElement(col_annot, "details", {f"{{{XMI_NS}}}id": create_uuid_id("det"), "key": "nullable", "value": "false"})
                if col.length:
                    ET.SubElement(col_annot, "details", {f"{{{XMI_NS}}}id": create_uuid_id("det"), "key": "length", "value": str(col.length)})

        for rel in self.state.er_relations:
            src = self.state.find_entity(rel.source_id)
            tgt = self.state.find_entity(rel.target_id)
            if not src or not tgt:
                continue

            from_mult = "1"
            to_mult = "0..*"
            if rel.type == "1:1":
                from_mult = "1"
                to_mult = "1"
            elif rel.type == "1:N":
                from_mult = "1"
                to_mult = "0..*"
            elif rel.type in ("N:1", "M:1"):
                from_mult = "0..*"
                to_mult = "1"
            elif rel.type in ("M:N", "N:M"):
                from_mult = "0..*"
                to_mult = "0..*"

            fk_elem = ET.SubElement(
                self.model,
                "ownedMember",
                {
                    f"{{{XMI_NS}}}type": "uml:dbForeignKey",
                    f"{{{XMI_NS}}}id": rel.id,
                    "name": "",
                    "from": rel.source_id,
                    "to": rel.target_id,
                    "fromMultiplicity": from_mult,
                    "toMultiplicity": to_mult,
                    "identifying": "false",
                    "syncType": "1",
                    "visibility": "public",
                    "isAbstract": "false",
                    "isDerived": "false",
                    "isLeaf": "false",
                },
            )
            ET.SubElement(fk_elem, "from", {f"{{{XMI_NS}}}idref": rel.source_id})
            ET.SubElement(fk_elem, "to", {f"{{{XMI_NS}}}idref": rel.target_id})

            fk_vp = ET.SubElement(fk_elem, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
            ET.SubElement(fk_vp, "modelType", {"value": "DBForeignKey"})
            ET.SubElement(fk_vp, "from", {"value": rel.source_id})
            ET.SubElement(fk_vp, "to", {"value": rel.target_id})
            ET.SubElement(fk_vp, "fromMultiplicity", {"value": from_mult})
            ET.SubElement(fk_vp, "toMultiplicity", {"value": to_mult})
            ET.SubElement(fk_vp, "identifying", {"value": "false"})
            ET.SubElement(fk_vp, "syncType", {"value": "1"})
            ET.SubElement(fk_vp, "qualityScore", {"value": "-1"})
            if getattr(rel, "description", ""):
                ET.SubElement(
                    fk_elem,
                    "ownedComment",
                    {
                        f"{{{XMI_NS}}}type": "uml:Comment",
                        f"{{{XMI_NS}}}id": f"{rel.id}_comment",
                        "body": rel.description,
                    },
                )
                ET.SubElement(fk_vp, "documentation", {"value": rel.description})

        # Visual Paradigm native ER data structures in model Extension
        if self.state.entities:
            model_vp_ext = self.model.find(f"{{{XMI_NS}}}Extension")
            if model_vp_ext is None:
                model_vp_ext = ET.SubElement(self.model, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})

            vp_child_models = model_vp_ext.find("vpumlChildModels")
            if vp_child_models is None:
                vp_child_models = ET.SubElement(model_vp_ext, "vpumlChildModels")

            for ent in self.state.entities.values():
                tbl_model = ET.SubElement(vp_child_models, "vpumlModel", {"id": ent.id, "modelType": "DBTable"})
                t_props = ET.SubElement(tbl_model, "properties")
                ET.SubElement(t_props, "property", {"name": "name", "type": "string", "value": ent.name})
                ET.SubElement(t_props, "property", {"name": "modelType", "type": "string", "value": "DBTable"})
                ET.SubElement(t_props, "property", {"name": "type", "type": "int", "value": "0"})
                ET.SubElement(t_props, "property", {"name": "syncType", "type": "int", "value": "1"})
                ET.SubElement(t_props, "property", {"name": "dataModel", "type": "int", "value": "2"})
                ET.SubElement(t_props, "property", {"name": "ormSyncState", "type": "int", "value": "1"})
                ET.SubElement(t_props, "property", {"name": "qualityScore", "type": "int", "value": "-1"})
                if getattr(ent, "description", ""):
                    ET.SubElement(t_props, "property", {"name": "documentation", "type": "htmlString", "value": ent.description})

                t_child_refs = ET.SubElement(tbl_model, "vpumlChildModelRefs")
                t_child_models = ET.SubElement(tbl_model, "vpumlChildModels")

                for col in ent.columns:
                    ET.SubElement(t_child_refs, "modelRef", {"value": col.id})

                    col_type_int, col_type_name, col_len = self._map_sql_type_to_vp(col.type)
                    if col.length:
                        col_len = col.length

                    col_model = ET.SubElement(t_child_models, "vpumlModel", {"id": col.id, "modelType": "DBColumn"})
                    c_props = ET.SubElement(col_model, "properties")
                    ET.SubElement(c_props, "property", {"name": "name", "type": "string", "value": col.name})
                    ET.SubElement(c_props, "property", {"name": "modelType", "type": "string", "value": "DBColumn"})
                    ET.SubElement(c_props, "property", {"name": "type", "type": "int", "value": str(col_type_int)})
                    ET.SubElement(c_props, "property", {"name": "typeName", "type": "string", "value": col_type_name})
                    ET.SubElement(c_props, "property", {"name": "length", "type": "int", "value": str(col_len)})
                    ET.SubElement(c_props, "property", {"name": "scale", "type": "int", "value": "0"})
                    ET.SubElement(c_props, "property", {"name": "nullable", "type": "boolean", "value": str(col.is_nullable).lower()})
                    ET.SubElement(c_props, "property", {"name": "unique", "type": "boolean", "value": str(getattr(col, "is_unique", False)).lower()})
                    ET.SubElement(c_props, "property", {"name": "primaryKey", "type": "boolean", "value": str(col.is_primary_key).lower()})
                    ET.SubElement(c_props, "property", {"name": "foreignKey", "type": "boolean", "value": str(col.is_foreign_key).lower()})
                    if col.is_foreign_key and matching_fks:
                        ET.SubElement(c_props, "property", {"name": "foreignKeyConstraints", "type": "modelRefs", "value": matching_fks[0]})
                    ET.SubElement(c_props, "property", {"name": "index", "type": "boolean", "value": "false"})
                    ET.SubElement(c_props, "property", {"name": "syncType", "type": "int", "value": "1"})
                    ET.SubElement(c_props, "property", {"name": "generated", "type": "int", "value": "0"})
                    ET.SubElement(c_props, "property", {"name": "syncToAttribute", "type": "int", "value": "0"})
                    if col.is_primary_key:
                        ET.SubElement(c_props, "property", {"name": "idGenerator", "type": "stringSelection", "value": "native"})
                    if getattr(col, "description", ""):
                        ET.SubElement(c_props, "property", {"name": "documentation", "type": "htmlString", "value": col.description})

            for rel in self.state.er_relations:
                src = self.state.find_entity(rel.source_id)
                tgt = self.state.find_entity(rel.target_id)
                if not src or not tgt:
                    continue

                from_mult = "1"
                to_mult = "0..*"
                if rel.type == "1:1":
                    from_mult = "1"
                    to_mult = "1"
                elif rel.type == "1:N":
                    from_mult = "1"
                    to_mult = "0..*"
                elif rel.type in ("N:1", "M:1"):
                    from_mult = "0..*"
                    to_mult = "1"
                elif rel.type in ("M:N", "N:M"):
                    from_mult = "0..*"
                    to_mult = "0..*"

                fk_model = ET.SubElement(vp_child_models, "vpumlModel", {"id": rel.id, "modelType": "DBForeignKey"})
                fk_props = ET.SubElement(fk_model, "properties")
                ET.SubElement(fk_props, "property", {"name": "name", "type": "string", "value": ""})
                ET.SubElement(fk_props, "property", {"name": "modelType", "type": "string", "value": "DBForeignKey"})
                ET.SubElement(fk_props, "property", {"name": "from", "type": "fromTo", "modelRef": rel.source_id})
                ET.SubElement(fk_props, "property", {"name": "to", "type": "fromTo", "modelRef": rel.target_id})
                ET.SubElement(fk_props, "property", {"name": "identifying", "type": "boolean", "value": "false"})
                ET.SubElement(fk_props, "property", {"name": "subtype", "type": "boolean", "value": "false"})
                ET.SubElement(fk_props, "property", {"name": "syncType", "type": "int", "value": "1"})
                ET.SubElement(fk_props, "property", {"name": "fromMultiplicity", "type": "stringSelection", "value": from_mult})
                ET.SubElement(fk_props, "property", {"name": "toMultiplicity", "type": "stringSelection", "value": to_mult})
                ET.SubElement(fk_props, "property", {"name": "syncToAssociation", "type": "int", "value": "0"})
                ET.SubElement(fk_props, "property", {"name": "dataModel", "type": "int", "value": "2"})
                ET.SubElement(fk_props, "property", {"name": "foreignKeyRelationshipPattern", "type": "string", "value": "{association_name}"})
                if getattr(rel, "description", ""):
                    ET.SubElement(fk_props, "property", {"name": "documentation", "type": "htmlString", "value": rel.description})

    def _build_uc_metamodel(self) -> None:
        assert self.model is not None

        for actor in self.state.actors.values():
            act_elem = ET.SubElement(
                self.model,
                "ownedMember",
                {
                    f"{{{XMI_NS}}}type": "uml:Actor",
                    f"{{{XMI_NS}}}id": actor.id,
                    "name": actor.name,
                    "visibility": "public",
                    "isAbstract": "false",
                    "isLeaf": "false",
                },
            )
            act_vp_ext = ET.SubElement(act_elem, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
            ET.SubElement(act_vp_ext, "isRoot", {f"{{{XMI_NS}}}value": "false"})
            ET.SubElement(act_vp_ext, "modelType", {"value": "Actor"})
            ET.SubElement(act_vp_ext, "businessModel", {f"{{{XMI_NS}}}value": "false"})
            ET.SubElement(act_vp_ext, "qualityScore", {"value": "-1"})
            if getattr(actor, "description", ""):
                ET.SubElement(
                    act_elem,
                    "ownedComment",
                    {
                        f"{{{XMI_NS}}}type": "uml:Comment",
                        f"{{{XMI_NS}}}id": f"{actor.id}_comment",
                        "body": actor.description,
                    },
                )
                ET.SubElement(act_vp_ext, "documentation", {"value": actor.description})

        # System Boundary container (if defined)
        if self.state.system_boundary:
            sb = self.state.system_boundary
            sb_elem = ET.SubElement(
                self.model,
                "ownedMember",
                {
                    f"{{{XMI_NS}}}type": "uml:Component",
                    f"{{{XMI_NS}}}id": sb.id,
                    "name": sb.name,
                    "visibility": "public",
                    "isAbstract": "false",
                    "isLeaf": "false",
                },
            )
            sb_vp_ext = ET.SubElement(sb_elem, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
            ET.SubElement(sb_vp_ext, "modelType", {"value": "System"})
            ET.SubElement(sb_vp_ext, "qualityScore", {"value": "-1"})

        includes_by_source: dict[str, list[tuple[str, str]]] = {}
        extends_by_source: dict[str, list[tuple[str, str]]] = {}
        uc_associations: list[RelationModel] = []

        for rel in self.state.uc_relations:
            if rel.type == "Include":
                includes_by_source.setdefault(rel.source_id, []).append((rel.id, rel.target_id))
            elif rel.type == "Extend":
                extends_by_source.setdefault(rel.source_id, []).append((rel.id, rel.target_id))
            else:
                uc_associations.append(rel)

        for uc in self.state.use_cases.values():
            uc_elem = ET.SubElement(
                self.model,
                "ownedMember",
                {
                    f"{{{XMI_NS}}}type": "uml:UseCase",
                    f"{{{XMI_NS}}}id": uc.id,
                    "name": uc.name,
                    "visibility": "public",
                    "isAbstract": "false",
                    "isLeaf": "false",
                },
            )
            uc_vp_ext = ET.SubElement(uc_elem, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
            ET.SubElement(uc_vp_ext, "isRoot", {f"{{{XMI_NS}}}value": "false"})
            ET.SubElement(uc_vp_ext, "modelType", {"value": "UseCase"})
            ET.SubElement(uc_vp_ext, "businessModel", {f"{{{XMI_NS}}}value": "false"})
            ET.SubElement(uc_vp_ext, "qualityScore", {"value": "-1"})
            if getattr(uc, "description", ""):
                ET.SubElement(
                    uc_elem,
                    "ownedComment",
                    {
                        f"{{{XMI_NS}}}type": "uml:Comment",
                        f"{{{XMI_NS}}}id": f"{uc.id}_comment",
                        "body": uc.description,
                    },
                )
                ET.SubElement(uc_vp_ext, "documentation", {"value": uc.description})

            if uc.id in includes_by_source:
                for rel_id, target_id in includes_by_source[uc.id]:
                    inc_elem = ET.SubElement(
                        uc_elem,
                        "include",
                        {
                            f"{{{XMI_NS}}}type": "uml:Include",
                            f"{{{XMI_NS}}}id": rel_id,
                            "addition": target_id,
                            "name": "«Include»",
                        },
                    )
                    inc_vp = ET.SubElement(inc_elem, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
                    ET.SubElement(inc_vp, "qualityScore", {"value": "-1"})

            if uc.id in extends_by_source:
                for rel_id, target_id in extends_by_source[uc.id]:
                    ext_elem = ET.SubElement(
                        uc_elem,
                        "extend",
                        {
                            f"{{{XMI_NS}}}type": "uml:Extend",
                            f"{{{XMI_NS}}}id": rel_id,
                            "extendedCase": target_id,
                            "name": "«Extend»",
                        },
                    )
                    ext_vp = ET.SubElement(ext_elem, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
                    ET.SubElement(ext_vp, "qualityScore", {"value": "-1"})

        for rel in uc_associations:
            src = self.state.find_uc_node(rel.source_id)
            tgt = self.state.find_uc_node(rel.target_id)
            if not src or not tgt:
                continue

            end_src_id = f"{rel.id}_end_src"
            end_tgt_id = f"{rel.id}_end_tgt"

            # In UML Use Case diagrams, associations connecting Actors with Use Cases are clean lines without default title or role text
            clean_assoc_name = rel.name if (rel.name and not rel.name.endswith("_Association")) else ""
            assoc_elem = ET.SubElement(
                self.model,
                "ownedMember",
                {
                    f"{{{XMI_NS}}}type": "uml:Association",
                    f"{{{XMI_NS}}}id": rel.id,
                    "name": clean_assoc_name,
                    "visibility": "public",
                    "isAbstract": "false",
                    "isDerived": "false",
                    "isLeaf": "false",
                },
            )
            ET.SubElement(assoc_elem, "memberEnd", {f"{{{XMI_NS}}}idref": end_src_id})
            src_end = ET.SubElement(
                assoc_elem,
                "ownedEnd",
                {
                    f"{{{XMI_NS}}}type": "uml:Property",
                    f"{{{XMI_NS}}}id": end_src_id,
                    "name": "",
                    "visibility": "public",
                    "type": src.id,
                    "association": rel.id,
                    "aggregation": "none",
                    "isDerived": "false",
                    "isDerivedUnion": "false",
                    "isLeaf": "false",
                    "isNavigable": "true",
                    "isReadOnly": "false",
                    "isStatic": "false",
                },
            )
            src_end_vp = ET.SubElement(src_end, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
            ET.SubElement(src_end_vp, "associationEnd")
            ET.SubElement(src_end_vp, "qualityScore", {"value": "-1"})

            ET.SubElement(assoc_elem, "memberEnd", {f"{{{XMI_NS}}}idref": end_tgt_id})
            tgt_end = ET.SubElement(
                assoc_elem,
                "ownedEnd",
                {
                    f"{{{XMI_NS}}}type": "uml:Property",
                    f"{{{XMI_NS}}}id": end_tgt_id,
                    "name": "",
                    "visibility": "public",
                    "type": tgt.id,
                    "association": rel.id,
                    "aggregation": "none",
                    "isDerived": "false",
                    "isDerivedUnion": "false",
                    "isLeaf": "false",
                    "isNavigable": "true",
                    "isReadOnly": "false",
                    "isStatic": "false",
                },
            )
            tgt_end_vp = ET.SubElement(tgt_end, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
            ET.SubElement(tgt_end_vp, "associationEnd")
            ET.SubElement(tgt_end_vp, "qualityScore", {"value": "-1"})

            assoc_vp = ET.SubElement(assoc_elem, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
            ET.SubElement(assoc_vp, "qualityScore", {"value": "-1"})

    def _build_sm_metamodel(self) -> None:
        assert self.model is not None

        if not self.state.states and not self.state.transitions:
            return

        sm_elem = ET.SubElement(
            self.model,
            "ownedMember",
            {
                f"{{{XMI_NS}}}type": "uml:StateMachine",
                f"{{{XMI_NS}}}id": create_uuid_id("sm"),
                "name": f"{self.state.name}_StateMachine",
            },
        )

        region_elem = ET.SubElement(
            sm_elem,
            "region",
            {
                f"{{{XMI_NS}}}type": "uml:Region",
                f"{{{XMI_NS}}}id": create_uuid_id("region"),
                "name": "DefaultRegion",
            },
        )

        for st in self.state.states.values():
            if st.type == "Initial":
                subv = ET.SubElement(
                    region_elem,
                    "subvertex",
                    {
                        f"{{{XMI_NS}}}type": "uml:Pseudostate",
                        f"{{{XMI_NS}}}id": st.id,
                        "name": st.name,
                        "kind": "initial",
                    },
                )
                st_ext = ET.SubElement(subv, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
                ET.SubElement(st_ext, "modelType", {"value": "Pseudostate"})
                if getattr(st, "description", ""):
                    ET.SubElement(
                        subv,
                        "ownedComment",
                        {
                            f"{{{XMI_NS}}}type": "uml:Comment",
                            f"{{{XMI_NS}}}id": f"{st.id}_comment",
                            "body": st.description,
                        },
                    )
                    ET.SubElement(st_ext, "documentation", {"value": st.description})
            elif st.type == "Final":
                subv = ET.SubElement(
                    region_elem,
                    "subvertex",
                    {
                        f"{{{XMI_NS}}}type": "uml:FinalState",
                        f"{{{XMI_NS}}}id": st.id,
                        "name": st.name,
                    },
                )
                st_ext = ET.SubElement(subv, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
                ET.SubElement(st_ext, "modelType", {"value": "FinalState"})
                if getattr(st, "description", ""):
                    ET.SubElement(
                        subv,
                        "ownedComment",
                        {
                            f"{{{XMI_NS}}}type": "uml:Comment",
                            f"{{{XMI_NS}}}id": f"{st.id}_comment",
                            "body": st.description,
                        },
                    )
                    ET.SubElement(st_ext, "documentation", {"value": st.description})
            else:
                subv = ET.SubElement(
                    region_elem,
                    "subvertex",
                    {
                        f"{{{XMI_NS}}}type": "uml:State",
                        f"{{{XMI_NS}}}id": st.id,
                        "name": st.name,
                    },
                )
                if getattr(st, "entry_action", ""):
                    ET.SubElement(
                        subv,
                        "entry",
                        {
                            f"{{{XMI_NS}}}type": "uml:Activity",
                            f"{{{XMI_NS}}}id": f"{st.id}_entry",
                            "name": st.entry_action,
                        },
                    )
                if getattr(st, "do_activity", ""):
                    ET.SubElement(
                        subv,
                        "doActivity",
                        {
                            f"{{{XMI_NS}}}type": "uml:Activity",
                            f"{{{XMI_NS}}}id": f"{st.id}_do",
                            "name": st.do_activity,
                        },
                    )
                if getattr(st, "exit_action", ""):
                    ET.SubElement(
                        subv,
                        "exit",
                        {
                            f"{{{XMI_NS}}}type": "uml:Activity",
                            f"{{{XMI_NS}}}id": f"{st.id}_exit",
                            "name": st.exit_action,
                        },
                    )
                st_ext = ET.SubElement(subv, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
                ET.SubElement(st_ext, "modelType", {"value": "State"})
                if getattr(st, "description", ""):
                    ET.SubElement(
                        subv,
                        "ownedComment",
                        {
                            f"{{{XMI_NS}}}type": "uml:Comment",
                            f"{{{XMI_NS}}}id": f"{st.id}_comment",
                            "body": st.description,
                        },
                    )
                    ET.SubElement(st_ext, "documentation", {"value": st.description})

        for tr in self.state.transitions:
            lbl = tr.trigger_event
            if tr.guard_condition:
                guard_fmt = tr.guard_condition if tr.guard_condition.startswith("[") else f"[{tr.guard_condition}]"
                lbl = f"{lbl} {guard_fmt}".strip() if lbl else guard_fmt

            tr_attrs = {
                f"{{{XMI_NS}}}type": "uml:Transition",
                f"{{{XMI_NS}}}id": tr.id,
                "source": tr.source_id,
                "target": tr.target_id,
            }
            if lbl:
                tr_attrs["name"] = lbl
            tr_elem = ET.SubElement(region_elem, "transition", tr_attrs)

            if tr.guard_condition:
                guard_elem = ET.SubElement(
                    tr_elem,
                    "guard",
                    {
                        f"{{{XMI_NS}}}type": "uml:Constraint",
                        f"{{{XMI_NS}}}id": f"{tr.id}_guard",
                        "name": tr.guard_condition,
                    },
                )
                ET.SubElement(
                    guard_elem,
                    "specification",
                    {
                        f"{{{XMI_NS}}}type": "uml:OpaqueExpression",
                        f"{{{XMI_NS}}}id": f"{tr.id}_guard_spec",
                        "body": tr.guard_condition,
                    },
                )

            if tr.trigger_event:
                ET.SubElement(
                    tr_elem,
                    "trigger",
                    {
                        f"{{{XMI_NS}}}type": "uml:Trigger",
                        f"{{{XMI_NS}}}id": create_uuid_id("trigger"),
                        "name": tr.trigger_event,
                    },
                )

    # ---------------------------------------------------------
    # Visual Layout Engine (OMG <uml:Diagram> and <uml:DiagramElement>)
    # ---------------------------------------------------------

    def _add_shape_element(
        self,
        omg_elements: ET.Element,
        p: NodePlacement,
        node: BaseNode,
        shape_type: str,
        creator_diag_type: str,
        caption_side: int = 12,
    ) -> None:
        """Add fully-styled OMG DiagramElement with Visual Paradigm data binding."""
        az_order = "2"
        bg_color = "Cr:122,207,245,255"
        fill_color = "Cr:122,207,245,255"
        fill_trans = "0"
        line_color = "Cr:0,0,0,255"
        line_weight = "1.0"
        caption_vis = "true"

        if shape_type == "Package":
            effective_caption_side = 12
            caption_bounds = f"0,20,{p.width},{max(20, p.height - 20)}"
            align = "1"
        elif shape_type == "Actor":
            effective_caption_side = 1
            caption_bounds = f"0,{p.height},{p.width},18"
            align = "4"
        elif shape_type == "UseCase":
            effective_caption_side = 12
            caption_bounds = f"0,0,{p.width},{p.height}"
            align = "4"
        elif shape_type == "System":
            effective_caption_side = 12
            caption_bounds = f"15,10,{max(20, p.width - 30)},28"
            align = "1"
            az_order = "1"
            bg_color = "Cr:240,247,255,255"
            fill_color = "Cr:240,247,255,255"
            fill_trans = "0"
            line_color = "Cr:70,130,220,255"
            line_weight = "2.0"
        elif shape_type == "NOTE":
            effective_caption_side = 12
            caption_bounds = f"0,0,{p.width},{p.height}"
            caption_vis = "true"
            align = "9"
            az_order = "4"
            bg_color = "Cr:255,255,200,255"
            fill_color = "Cr:255,255,200,255"
            fill_trans = "0"
            line_color = "Cr:180,180,100,255"
            line_weight = "1.0"
        elif shape_type == "InitialPseudoState":
            effective_caption_side = 1
            caption_bounds = "0,0,0,0"
            caption_vis = "false"
            align = "4"
            az_order = "3"
            bg_color = "Cr:0,0,0,255"
            fill_color = "Cr:0,0,0,255"
            line_color = "Cr:0,0,0,255"
        elif shape_type == "FinalState2":
            effective_caption_side = 1
            caption_bounds = "0,0,0,0"
            caption_vis = "false"
            align = "4"
            az_order = "3"
            bg_color = "Cr:0,0,0,255"
            fill_color = "Cr:0,0,0,255"
            line_color = "Cr:0,0,0,255"
        elif shape_type == "State2":
            effective_caption_side = 1
            caption_bounds = f"0,0,{p.width},15"
            caption_vis = "true"
            align = "4"
            az_order = "2"
            bg_color = "Cr:122,207,245,255"
            fill_color = "Cr:122,207,245,255"
        elif shape_type == "DBTable":
            effective_caption_side = 12
            caption_bounds = f"0,0,{p.width},15"
            caption_vis = "true"
            align = "4"
            az_order = "2"
            bg_color = "Cr:245,182,122,255"
            fill_color = "Cr:245,182,122,255"
            fill_trans = "0"
            line_color = "Cr:0,0,0,255"
            line_weight = "1.0"
        else:
            effective_caption_side = caption_side
            caption_bounds = f"0,0,{p.width},16"
            caption_vis = "true"
            align = "9"

        omg_elem = ET.SubElement(
            omg_elements,
            f"{{{UML_NS}}}DiagramElement",
            {
                f"{{{XMI_NS}}}id": p.shape_id,
                "geometry": p.geometry_str,
                "preferredShapeType": shape_type,
                "subject": p.node_id,
            },
        )
        shape_vp = ET.SubElement(omg_elem, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
        ET.SubElement(shape_vp, "captionBounds", {"value": caption_bounds})
        ET.SubElement(shape_vp, "captionInternalWidth", {"value": "-2147483648"})
        ET.SubElement(shape_vp, "captionInternalHeight", {"value": "-2147483648"})
        ET.SubElement(shape_vp, "captionVisible", {"value": caption_vis})
        ET.SubElement(shape_vp, "captionSide", {"value": str(effective_caption_side)})

        props = ET.SubElement(shape_vp, "properties")
        ET.SubElement(props, "azOrder", {"value": az_order})
        ET.SubElement(props, "abackground", {"value": bg_color})
        ET.SubElement(props, "aforeground", {"value": "Cr:0,0,0,255"})
        ET.SubElement(props, "acreatorDiagramType", {"value": creator_diag_type})
        ET.SubElement(props, "aselectable", {"value": "true"})
        ET.SubElement(props, "amodelElementNameAlignment", {"value": align})

        if shape_type == "Package":
            ET.SubElement(props, "ashowPackageNameStyle", {"value": "2"})
        elif shape_type == "System":
            ET.SubElement(props, "captionAlignment", {"value": "0"})
            ET.SubElement(props, "ashowCaption", {"value": "true"})
        elif shape_type == "Actor":
            ET.SubElement(props, "arequestResetCaption", {"value": "true"})
        elif shape_type == "State2":
            ET.SubElement(props, "ashowActionActivities", {"value": "true"})
            ET.SubElement(props, "ashowInternalTransitions", {"value": "true"})
        elif shape_type == "DBTable":
            ET.SubElement(props, "acolSortType", {"value": "0"})
            ET.SubElement(props, "ashowColumnStereotypes", {"value": "0"})
            ET.SubElement(props, "ashowColumnsMode", {"value": "0"})
            ET.SubElement(props, "apresentationOption", {"value": "4"})

        ET.SubElement(props, "ashowAttributeType", {"value": "1"})
        ET.SubElement(props, "ashowOperationType", {"value": "1"})
        ET.SubElement(props, "ashowReceptionType", {"value": "1"})
        ET.SubElement(props, "ashowEmptyCompartments", {"value": "0"})
        ET.SubElement(props, "ashowOperationSignature", {"value": "true"})
        ET.SubElement(props, "ashowInitialAttributeValue", {"value": "true"})

        # If shape is inside a parent package or system boundary, establish visual containment
        if p.parent_shape_id:
            ET.SubElement(shape_vp, "parentDiagramElement", {"idref": p.parent_shape_id})

        ET.SubElement(omg_elem, "elementFill", {"color1": fill_color, "color2": "", "style": "1", "transparency": fill_trans, "type": "1"})
        font_bold = "true" if shape_type == "System" else "false"
        font_size = "12" if shape_type == "System" else "11"
        font_style = "1" if shape_type == "System" else "0"
        ET.SubElement(omg_elem, "elementFont", {"bold": font_bold, "color": "Cr:0,0,0,255", "italic": "false", "name": "Dialog", "size": font_size, "style": font_style})
        ET.SubElement(omg_elem, "elementLine", {"color": line_color, "style": "1", "transparency": "0", "weight": line_weight})
        ET.SubElement(omg_elem, "CompartmentFont", {"value": "none"})

    def _add_connector_element(
        self,
        omg_elements: ET.Element,
        rel_id: str,
        rel_type: str,
        rel_name: str,
        src_p: NodePlacement,
        tgt_p: NodePlacement,
        creator_diag_type: str,
        src_mult: str = "",
        tgt_mult: str = "",
        is_transition: bool = False,
        is_uc_stereotype: bool = False,
    ) -> None:
        """Add fully-styled OMG DiagramElement connector with Visual Paradigm data binding."""
        wp1, wp2 = WaypointRoutingEngine.calculate_waypoints(src_p, tgt_p)
        mid_x = (wp1[0] + wp2[0]) // 2
        mid_y = (wp1[1] + wp2[1]) // 2

        # In Visual Paradigm, StateMachine transitions must use Transition2, and ERD must use DBForeignKey
        if is_transition or rel_type in ("Transition", "Transition2"):
            effective_shape_type = "Transition2"
        elif creator_diag_type == "ERDiagram" or rel_type in ("DBForeignKey", "DBRelationship"):
            effective_shape_type = "DBForeignKey"
        else:
            effective_shape_type = rel_type

        # Check if relation name was an auto-generated title or default
        is_auto_name = any(
            rel_name.endswith(suffix)
            for suffix in ("_Association", "_Composition", "_Aggregation", "_Generalization", "_Realization", "_Dependency")
        ) or rel_name in ("Association", "Composition", "Aggregation", "Generalization", "Realization", "Dependency", "")

        if creator_diag_type == "UseCaseDiagram" and not is_uc_stereotype and rel_type not in ("Include", "Extend"):
            # UML 2.5: Actor-to-UseCase associations are clean lines without default title or role text
            show_name_val = "0"
            caption_vis = "false"
        elif rel_type in ("Include", "Extend") or is_uc_stereotype:
            show_name_val = "2"
            caption_vis = "true"
        elif effective_shape_type == "DBForeignKey" or creator_diag_type == "ERDiagram":
            show_name_val = "0"
            caption_vis = "true"
        elif is_transition or effective_shape_type == "Transition2":
            show_name_val = "2" if rel_name else "0"
            caption_vis = "true" if rel_name else "false"
        elif rel_type == "Anchor":
            show_name_val = "0"
            caption_vis = "false"
        elif not is_auto_name:
            show_name_val = "2"
            caption_vis = "true"
        else:
            show_name_val = "0"
            caption_vis = "false"

        omg_conn = ET.SubElement(
            omg_elements,
            f"{{{UML_NS}}}DiagramElement",
            {
                f"{{{XMI_NS}}}id": f"conn_{rel_id}",
                "fromDiagramElement": src_p.shape_id,
                "toDiagramElement": tgt_p.shape_id,
                "geometry": f"{wp1[0]},{wp1[1]};{wp2[0]},{wp2[1]};",
                "preferredShapeType": effective_shape_type,
                "subject": rel_id,
            },
        )
        conn_vp = ET.SubElement(omg_conn, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
        if creator_diag_type == "UseCaseDiagram" and not is_uc_stereotype and rel_type not in ("Include", "Extend"):
            c_bounds_w = "0"
            c_bounds_h = "0"
            caption_vis = "false"
        else:
            c_bounds_w = "20" if effective_shape_type == "DBForeignKey" else "60"
            c_bounds_h = "0" if effective_shape_type == "DBForeignKey" else "16"
        ET.SubElement(conn_vp, "captionBounds", {"value": f"{mid_x},{mid_y},{c_bounds_w},{c_bounds_h}"})
        ET.SubElement(conn_vp, "captionInternalWidth", {"value": "-2147483648"})
        ET.SubElement(conn_vp, "captionInternalHeight", {"value": "-2147483648"})
        ET.SubElement(conn_vp, "captionVisible", {"value": caption_vis})
        ET.SubElement(conn_vp, "captionSide", {"value": "1"})

        if (src_mult or tgt_mult) and creator_diag_type != "ERDiagram":
            ET.SubElement(conn_vp, "roleA", {"multiplicity": f"{wp1[0]},{wp1[1]},30,16"})
            ET.SubElement(conn_vp, "roleB", {"multiplicity": f"{wp2[0]},{wp2[1]},30,16"})

        c_props = ET.SubElement(conn_vp, "properties")
        ET.SubElement(c_props, "azOrder", {"value": "10"})
        ET.SubElement(c_props, "abackground", {"value": "Cr:255,255,255,255"})
        ET.SubElement(c_props, "aforeground", {"value": "Cr:0,0,0,255"})
        ET.SubElement(c_props, "acreatorDiagramType", {"value": creator_diag_type})
        ET.SubElement(c_props, "aselectable", {"value": "true"})
        ET.SubElement(c_props, "aconnectorStyle", {"value": "3"})
        ET.SubElement(c_props, "aconnectorLineJumps", {"value": "4"})
        ET.SubElement(c_props, "aconnectorLabelOrientation", {"value": "4"})
        ET.SubElement(c_props, "ashowConnectorName", {"value": show_name_val})

        # CRITICAL: Always suppress auto-generated role names (+customer, +order) to eliminate clutter
        ET.SubElement(c_props, "ashowFromRoleName", {"value": "false"})
        ET.SubElement(c_props, "ashowToRoleName", {"value": "false"})

        if (src_mult or tgt_mult) and creator_diag_type != "ERDiagram":
            ET.SubElement(c_props, "amultiplicityARectangle", {"value": f"Re:{wp1[0]}.0,{wp1[1]}.0,30.0,16.0"})
            ET.SubElement(c_props, "amultiplicityBRectangle", {"value": f"Re:{wp2[0]}.0,{wp2[1]}.0,30.0,16.0"})
            ET.SubElement(c_props, "ahasMultiplicityAShape", {"value": "true"})
            ET.SubElement(c_props, "ahasMultiplicityBShape", {"value": "true"})
            ET.SubElement(c_props, "ashowFromMultiplicity", {"value": "true" if src_mult else "false"})
            ET.SubElement(c_props, "ashowToMultiplicity", {"value": "true" if tgt_mult else "false"})
        else:
            ET.SubElement(c_props, "ashowFromMultiplicity", {"value": "false"})
            ET.SubElement(c_props, "ashowToMultiplicity", {"value": "false"})

        if effective_shape_type == "DBForeignKey":
            ET.SubElement(c_props, "afromPinType", {"value": "1"})
            ET.SubElement(c_props, "atoPinType", {"value": "1"})
            ET.SubElement(c_props, "auseFromShapeCenter", {"value": "true"})
            ET.SubElement(c_props, "auseToShapeCenter", {"value": "true"})
            ET.SubElement(c_props, "afromConnectType", {"value": "0"})
            ET.SubElement(c_props, "atoConnectType", {"value": "0"})
            ET.SubElement(c_props, "arequestRebuild", {"value": "false"})
            ET.SubElement(c_props, "arequestResetLabels", {"value": "false"})
            ET.SubElement(c_props, "apaintThroughLabel", {"value": "2"})

        line_style = "2" if rel_type in ("Include", "Extend", "Dependency", "Realization", "Anchor") else "1"
        line_color = "Cr:120,120,120,255" if rel_type == "Anchor" else "Cr:0,0,0,255"
        ET.SubElement(omg_conn, "elementFont", {"bold": "false", "color": "Cr:0,0,0,255", "italic": "false", "name": "Dialog", "size": "11", "style": "0"})
        ET.SubElement(omg_conn, "elementLine", {"color": line_color, "style": line_style, "transparency": "0", "weight": "1.0"})

    def _render_notes_for_diagram(
        self,
        omg_elements: ET.Element,
        target_node_ids: set[str],
        placements: dict[str, NodePlacement],
        creator_diag_type: str,
    ) -> None:
        """Render relevant Notes and their connecting Anchor lines on the diagram canvas."""
        relevant_notes = [
            n for n in self.state.notes.values()
            if (n.target_id and n.target_id in target_node_ids) or (not n.target_id and creator_diag_type == "ClassDiagram")
        ]
        for note in relevant_notes:
            tgt_p = placements.get(note.target_id) if note.target_id else None
            if tgt_p:
                nx = tgt_p.x + tgt_p.width + 50
                ny = tgt_p.y
            else:
                max_x = max((p.x + p.width for p in placements.values()), default=60)
                nx = max_x + 60
                ny = 60
            nw = 200
            nh = max(60, min(140, 24 + len(note.text) // 2))

            note_p = NodePlacement(
                node_id=note.id,
                shape_id=f"shape_{note.id}",
                x=nx,
                y=ny,
                width=nw,
                height=nh,
            )
            self._add_shape_element(
                omg_elements,
                note_p,
                note,
                shape_type="NOTE",
                creator_diag_type=creator_diag_type,
                caption_side=12,
            )

            if tgt_p:
                self._add_connector_element(
                    omg_elements,
                    rel_id=f"anchor_{note.id}",
                    rel_type="Anchor",
                    rel_name="",
                    src_p=note_p,
                    tgt_p=tgt_p,
                    creator_diag_type=creator_diag_type,
                )

    def _create_diagram(self, diag_id: str, name: str, diag_type: str) -> tuple[ET.Element, ET.Element]:
        """Create standard OMG <uml:Diagram> with Visual Paradigm diagram-level properties."""
        omg_diag = ET.SubElement(
            self.root,
            f"{{{UML_NS}}}Diagram",
            {
                f"{{{XMI_NS}}}id": diag_id,
                "name": name,
                "diagramType": diag_type,
                "toolName": "Visual Paradigm",
                "documentation": "",
            },
        )
        diag_ext = ET.SubElement(omg_diag, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
        diag_props = ET.SubElement(diag_ext, "properties")
        ET.SubElement(diag_props, "ashowShapeStereotypeIconName", {"value": "true"})
        ET.SubElement(diag_props, "ashowAllocatedFrom", {"value": "true"})
        ET.SubElement(diag_props, "ashowAllocatedTo", {"value": "true"})
        ET.SubElement(diag_props, "afilterByViewpointLegend", {"value": "true"})
        ET.SubElement(diag_props, "ashowPackageNameStyle", {"value": "0"})
        ET.SubElement(diag_props, "ashowConnectorName", {"value": "0"})
        ET.SubElement(diag_props, "aeditable", {"value": "true"})
        ET.SubElement(diag_props, "adiagramBackground", {"value": "Cr:255,255,255,255"})
        ET.SubElement(diag_props, "aconnectorStyle", {"value": "1"})
        ET.SubElement(diag_props, "aconnectorLineJumps", {"value": "0"})
        ET.SubElement(diag_props, "ashowClassEmptyCompartments", {"value": "2"})
        ET.SubElement(diag_props, "ashowAttributesType", {"value": "1"})
        ET.SubElement(diag_props, "ashowOperationsParameters", {"value": "1"})
        ET.SubElement(diag_props, "ashowOperationsReturnType", {"value": "1"})
        ET.SubElement(diag_props, "ashowAssociationNavigationArrows", {"value": "3"})
        ET.SubElement(diag_props, "ashowStereotypes", {"value": "true"})
        ET.SubElement(diag_props, "aclassFitSizeWhenShowHideMember", {"value": "true"})

        if diag_type == "ERDiagram":
            ET.SubElement(diag_props, "a_showDBTableColumnsMode", {"value": "1"})
            ET.SubElement(diag_props, "a_showColumnStereotypes", {"value": "true"})
            ET.SubElement(diag_props, "a_showColumnTypes", {"value": "true"})
            ET.SubElement(diag_props, "a_showColumnUserType", {"value": "false"})
            ET.SubElement(diag_props, "a_showColumnDefaultValue", {"value": "false"})
            ET.SubElement(diag_props, "a_columnConstraintsDisplayOption", {"value": "2"})
            ET.SubElement(diag_props, "a_showExtraColumnProperties", {"value": "true"})
            ET.SubElement(diag_props, "a_pointForeignKeyEndToColumn", {"value": "false"})
            ET.SubElement(diag_props, "a_alignColumnProperties", {"value": "true"})
            ET.SubElement(diag_props, "adataModel", {"value": "2"})
            ET.SubElement(diag_props, "aForeignKeyArrowHeadSize", {"value": "3"})

        omg_elements = ET.SubElement(omg_diag, f"{{{UML_NS}}}Diagram.element")
        return omg_diag, omg_elements

    def _build_visual_layers(self) -> None:
        """Inject OMG <uml:Diagram> and <uml:DiagramElement> using Smart Layout Engines."""
        assert self.root is not None

        # Diagram 1: Class Diagram with Hierarchical DAG & Nested Package Layout
        if self.state.classes or self.state.packages:
            class_layout = HierarchicalClassLayout(start_x=60, start_y=60, gap_x=60, gap_y=100)
            class_placements = class_layout.layout(self.state)
            class_title = getattr(self.state, "diagram_names", {}).get("ClassDiagram", "Class Diagram")
            _, omg_elements = self._create_diagram("omg_diag_class_1", class_title, "ClassDiagram")

            # 1. Add Package shapes
            for pid, pkg in self.state.packages.items():
                if pid in class_placements:
                    p = class_placements[pid]
                    self._add_shape_element(
                        omg_elements,
                        p,
                        pkg,
                        shape_type="Package",
                        creator_diag_type="ClassDiagram",
                        caption_side=12,
                    )

            # 2. Add Class shapes
            for cid, cls_node in self.state.classes.items():
                if cid in class_placements:
                    p = class_placements[cid]
                    shape_type = "Interface" if cls_node.element_type == "Interface" else "Class"
                    self._add_shape_element(
                        omg_elements,
                        p,
                        cls_node,
                        shape_type=shape_type,
                        creator_diag_type="ClassDiagram",
                        caption_side=12,
                    )

            # 3. Add Connectors
            for rel in self.state.class_relations:
                if rel.source_id in class_placements and rel.target_id in class_placements:
                    src_p = class_placements[rel.source_id]
                    tgt_p = class_placements[rel.target_id]
                    self._add_connector_element(
                        omg_elements,
                        rel_id=rel.id,
                        rel_type=rel.type,
                        rel_name=rel.name or rel.type,
                        src_p=src_p,
                        tgt_p=tgt_p,
                        creator_diag_type="ClassDiagram",
                        src_mult=rel.source_multiplicity,
                        tgt_mult=rel.target_multiplicity,
                    )

            # 4. Render Notes for Class Diagram
            self._render_notes_for_diagram(
                omg_elements,
                set(self.state.classes.keys()) | set(self.state.packages.keys()),
                class_placements,
                "ClassDiagram",
            )

        # Diagram 2: ER Diagram with FK Dependency Directed Layout
        if self.state.entities:
            erd_layout = ERDClusterLayout(start_x=60, start_y=60, gap_x=90, gap_y=110)
            er_placements = erd_layout.layout(self.state)
            erd_title = getattr(self.state, "diagram_names", {}).get("ERDiagram", "Entity Relationship Diagram")
            _, omg_elements = self._create_diagram("omg_diag_erd_1", erd_title, "ERDiagram")

            for p in er_placements.values():
                ent_node = self.state.entities[p.node_id]
                self._add_shape_element(
                    omg_elements,
                    p,
                    ent_node,
                    shape_type="DBTable",
                    creator_diag_type="ERDiagram",
                    caption_side=12,
                )

            for rel in self.state.er_relations:
                if rel.source_id in er_placements and rel.target_id in er_placements:
                    src_p = er_placements[rel.source_id]
                    tgt_p = er_placements[rel.target_id]
                    self._add_connector_element(
                        omg_elements,
                        rel_id=rel.id,
                        rel_type="DBForeignKey",
                        rel_name="",
                        src_p=src_p,
                        tgt_p=tgt_p,
                        creator_diag_type="ERDiagram",
                        src_mult="",
                        tgt_mult="",
                    )

            # Render Notes for ER Diagram
            self._render_notes_for_diagram(
                omg_elements,
                set(self.state.entities.keys()),
                er_placements,
                "ERDiagram",
            )

        # Diagram 3: Use Case Diagram with 3-Tier Columnar Layout and System Boundary
        if self.state.actors or self.state.use_cases:
            uc_layout = UseCaseTierLayout(col1_x=80, col2_x=340, start_y=60)
            uc_placements = uc_layout.layout(self.state)
            uc_title = getattr(self.state, "diagram_names", {}).get("UseCaseDiagram", "Use Case Diagram")
            _, omg_elements = self._create_diagram("omg_diag_uc_1", uc_title, "UseCaseDiagram")

            # 1. System Boundary shape (if defined)
            if self.state.system_boundary and self.state.use_cases:
                sb = self.state.system_boundary
                target_ucs = [uc_placements[uid] for uid in sb.use_case_ids if uid in uc_placements]
                if not target_ucs:
                    target_ucs = [p for p in uc_placements.values() if p.node_id in self.state.use_cases]
                if target_ucs:
                    pad_x = 45
                    pad_y = 55
                    sb_min_x = min(p.x for p in target_ucs) - pad_x
                    sb_min_y = min(p.y for p in target_ucs) - pad_y
                    sb_max_x = max(p.x + p.width for p in target_ucs) + pad_x
                    sb_max_y = max(p.y + p.height for p in target_ucs) + pad_y
                    sb_w = sb_max_x - sb_min_x
                    sb_h = sb_max_y - sb_min_y

                    sb_placement = NodePlacement(
                        node_id=sb.id,
                        shape_id=f"shape_{sb.id}",
                        x=sb_min_x,
                        y=sb_min_y,
                        width=sb_w,
                        height=sb_h,
                    )
                    self._add_shape_element(
                        omg_elements,
                        sb_placement,
                        sb,
                        shape_type="System",
                        creator_diag_type="UseCaseDiagram",
                        caption_side=12,
                    )
                    for p in target_ucs:
                        p.parent_shape_id = sb_placement.shape_id

            # 2. Actors and Use Cases
            for p in uc_placements.values():
                is_actor = p.node_id in self.state.actors
                shape_type = "Actor" if is_actor else "UseCase"
                caption_side = 1 if is_actor else 12
                uc_node = self.state.actors[p.node_id] if is_actor else self.state.use_cases[p.node_id]
                self._add_shape_element(
                    omg_elements,
                    p,
                    uc_node,
                    shape_type=shape_type,
                    creator_diag_type="UseCaseDiagram",
                    caption_side=caption_side,
                )

            # 3. Connectors (Include, Extend, Association)
            for rel in self.state.uc_relations:
                if rel.source_id in uc_placements and rel.target_id in uc_placements:
                    src_p = uc_placements[rel.source_id]
                    tgt_p = uc_placements[rel.target_id]
                    rel_lbl = "«Include»" if rel.type == "Include" else ("«Extend»" if rel.type == "Extend" else "")
                    self._add_connector_element(
                        omg_elements,
                        rel_id=rel.id,
                        rel_type=rel.type,
                        rel_name=rel_lbl,
                        src_p=src_p,
                        tgt_p=tgt_p,
                        creator_diag_type="UseCaseDiagram",
                        is_uc_stereotype=(rel.type in ("Include", "Extend")),
                    )

            # 4. Render Notes for Use Case Diagram
            self._render_notes_for_diagram(
                omg_elements,
                set(self.state.actors.keys()) | set(self.state.use_cases.keys()),
                uc_placements,
                "UseCaseDiagram",
            )

        # Diagram 4: State Machine Diagram with Horizontal Flow Pipeline Layout
        if self.state.states:
            sm_layout = StateMachineFlowLayout(start_x=60, start_y=150, gap_x=160)
            sm_placements = sm_layout.layout(self.state)
            sm_title = getattr(self.state, "diagram_names", {}).get("StateDiagram", "State Machine Diagram")
            _, omg_elements = self._create_diagram("omg_diag_sm_1", sm_title, "StateDiagram")

            for p in sm_placements.values():
                st_obj = self.state.states[p.node_id]
                if st_obj.type == "Initial":
                    shape_type = "InitialPseudoState"
                elif st_obj.type == "Final":
                    shape_type = "FinalState2"
                else:
                    shape_type = "State2"

                self._add_shape_element(
                    omg_elements,
                    p,
                    st_obj,
                    shape_type=shape_type,
                    creator_diag_type="StateDiagram",
                    caption_side=12 if shape_type == "State2" else 1,
                )

            for tr in self.state.transitions:
                if tr.source_id in sm_placements and tr.target_id in sm_placements:
                    src_p = sm_placements[tr.source_id]
                    tgt_p = sm_placements[tr.target_id]
                    lbl = tr.trigger_event
                    if tr.guard_condition:
                        guard_fmt = tr.guard_condition if tr.guard_condition.startswith("[") else f"[{tr.guard_condition}]"
                        lbl = f"{lbl} {guard_fmt}".strip() if lbl else guard_fmt

                    self._add_connector_element(
                        omg_elements,
                        rel_id=tr.id,
                        rel_type="Transition2",
                        rel_name=lbl,
                        src_p=src_p,
                        tgt_p=tgt_p,
                        creator_diag_type="StateDiagram",
                        is_transition=True,
                    )

            # Render Notes for State Machine Diagram
            self._render_notes_for_diagram(
                omg_elements,
                set(self.state.states.keys()),
                sm_placements,
                "StateDiagram",
            )

    def build_tree(self) -> ET.ElementTree:
        """Construct full XML ElementTree with Metamodel and Visual Layout."""
        ET.register_namespace("xmi", XMI_NS)
        ET.register_namespace("uml", UML_NS)

        self.root = ET.Element(
            f"{{{XMI_NS}}}XMI",
            {
                f"{{{XMI_NS}}}version": "2.1",
            },
        )

        doc_elem = ET.SubElement(
            self.root,
            f"{{{XMI_NS}}}Documentation",
            {
                "exporter": "Visual Paradigm",
                "exporterVersion": "7.0.2",
            },
        )
        doc_ext = ET.SubElement(doc_elem, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
        ET.SubElement(doc_ext, "nickname", {"exportedFromDifferentName": "false"})

        root_ext = ET.SubElement(self.root, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
        proj_props = ET.SubElement(root_ext, "projectProperties")
        ET.SubElement(proj_props, "projectProperty", {"name": "author", "value": "Architect"})

        self.model = ET.SubElement(
            self.root,
            f"{{{UML_NS}}}Model",
            {
                f"{{{XMI_NS}}}id": "model_1",
                "name": self.state.name or "ProjectModel",
                "visibility": "public",
            },
        )

        # 1. Logical Metamodel (pure native ownedMember elements with packages)
        self._build_class_metamodel()
        self._build_er_metamodel()
        self._build_uc_metamodel()
        self._build_sm_metamodel()

        # 1b. Emit Universal Notes (UML Comments)
        for note in self.state.notes.values():
            note_attrs = {
                f"{{{XMI_NS}}}type": "uml:Comment",
                f"{{{XMI_NS}}}id": note.id,
                "body": note.text,
            }
            if note.target_id:
                note_attrs["annotatedElement"] = note.target_id
            c_elem = ET.SubElement(self.model, "ownedComment", note_attrs)
            c_ext = ET.SubElement(c_elem, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
            ET.SubElement(c_ext, "type", {"value": "NOTE"})
            ET.SubElement(c_ext, "qualityScore", {"value": "-1"})

        # 1c. Emit vpumlModel for Anchor connectors under projectProperties
        for note in self.state.notes.values():
            if note.target_id:
                anc_model = ET.SubElement(proj_props, "vpumlModel", {"id": f"anchor_{note.id}", "modelType": "Anchor"})
                a_props = ET.SubElement(anc_model, "properties")
                ET.SubElement(a_props, "property", {"name": "modelType", "type": "string", "value": "Anchor"})
                ET.SubElement(a_props, "property", {"name": "from", "type": "fromTo", "modelRef": note.id})
                ET.SubElement(a_props, "property", {"name": "to", "type": "fromTo", "modelRef": note.target_id})

        # 2. Visual Layout Layer (pure native OMG <uml:Diagram> and <uml:DiagramElement>)
        self._build_visual_layers()

        ET.indent(self.root, space="\t")
        return ET.ElementTree(self.root)

    def export(self, filepath: str) -> str:
        """Serialize ElementTree to the specified file."""
        tree = self.build_tree()
        abs_path = os.path.abspath(filepath)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        tree.write(abs_path, encoding="utf-8", xml_declaration=True)
        return abs_path


def export_to_xmi(state: ProjectState, filepath: str) -> str:
    """Helper function to build and export XMI from ProjectState."""
    builder = XMIBuilder(state)
    return builder.export(filepath)
