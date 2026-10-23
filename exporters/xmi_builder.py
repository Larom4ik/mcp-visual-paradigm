"""XMI 2.1 Builder with OMG Diagram Interchange and Visual Paradigm Native Data Binding.

Ensures:
1. Exact matching IDs: DiagramElement.subject == ownedMember.xmi:id.
2. Native Visual Paradigm Model Structure: All elements in <uml:Model> are <ownedMember xmi:type="..."> (Class, DataType, Association, Dependency, Realization, Actor, UseCase, StateMachine).
3. Strict encapsulation: <ownedAttribute> and <ownedOperation> are placed strictly inside <ownedMember xmi:type="uml:Class">.
4. Clean Diagram Rendering: Diagrams are rendered purely via OMG <uml:Diagram> with Visual Paradigm extensions. No freehand drawing shapes.
5. ERD stereotypes: entities have <details key="entity" value="true"/> and columns have <details key="column" value="true"/>.
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
    RelationModel,
    UseCaseNode,
)
from core.state import ProjectState

XMI_NS = "http://schema.omg.org/spec/XMI/2.1"
UML_NS = "http://schema.omg.org/spec/UML/2.0"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"


def sanitize_id(raw_str: str) -> str:
    """Ensure an ID is a valid XML NCName."""
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", raw_str)
    if not cleaned or cleaned[0].isdigit():
        return f"_{cleaned}"
    return cleaned


def create_uuid_id(prefix: str = "xmi") -> str:
    """Generate a valid XML ID with given prefix."""
    return f"{prefix}_{uuid.uuid4().hex}"


class NodePlacement:
    """Calculated layout coordinates and dimensions for a diagram shape."""

    def __init__(self, node_id: str, shape_id: str, x: int, y: int, width: int = 160, height: int = 90):
        self.node_id = node_id
        self.shape_id = shape_id
        self.x = x
        self.y = y
        self.width = width
        self.height = height

    @property
    def center_x(self) -> int:
        return self.x + self.width // 2

    @property
    def center_y(self) -> int:
        return self.y + self.height // 2

    @property
    def geometry_str(self) -> str:
        return f"{self.x},{self.y},{self.width},{self.height}"


class GridAutoLayout:
    """Calculates non-overlapping grid positions and edge connection waypoints for diagram elements."""

    def __init__(self, start_x: int = 50, start_y: int = 50, gap_x: int = 250, gap_y: int = 160):
        self.start_x = start_x
        self.start_y = start_y
        self.gap_x = gap_x
        self.gap_y = gap_y

    def layout_nodes(self, nodes: list[BaseNode]) -> dict[str, NodePlacement]:
        """Compute grid coordinates for a list of nodes with dynamic dimension calculation."""
        placements: dict[str, NodePlacement] = {}
        if not nodes:
            return placements

        cols = max(3, int(math.ceil(math.sqrt(len(nodes)))))
        for i, node in enumerate(nodes):
            col = i % cols
            row = i // cols
            x = self.start_x + col * self.gap_x
            y = self.start_y + row * self.gap_y

            # Dynamically size the shape so attributes and methods are fully visible
            attr_count = len(getattr(node, "attributes", [])) + len(getattr(node, "columns", []))
            method_count = len(getattr(node, "methods", []))
            calc_height = max(80, 40 + 18 * attr_count + 18 * method_count)
            calc_width = 160

            shape_id = f"shape_{node.id}"
            placements[node.id] = NodePlacement(
                node_id=node.id,
                shape_id=shape_id,
                x=x,
                y=y,
                width=calc_width,
                height=calc_height,
            )
        return placements

    @staticmethod
    def calculate_waypoints(src: NodePlacement, tgt: NodePlacement) -> tuple[tuple[int, int], tuple[int, int]]:
        """Calculate start and end boundary connection points between two shapes."""
        # Source boundary connection point
        if tgt.center_x > src.center_x + (src.width // 4):
            wp1_x = src.x + src.width
            wp1_y = src.center_y
        elif tgt.center_x < src.center_x - (src.width // 4):
            wp1_x = src.x
            wp1_y = src.center_y
        else:
            wp1_x = src.center_x
            wp1_y = (src.y + src.height) if tgt.center_y >= src.center_y else src.y

        # Target boundary connection point
        if src.center_x < tgt.center_x - (tgt.width // 4):
            wp2_x = tgt.x
            wp2_y = tgt.center_y
        elif src.center_x > tgt.center_x + (tgt.width // 4):
            wp2_x = tgt.x + tgt.width
            wp2_y = tgt.center_y
        else:
            wp2_x = tgt.center_x
            wp2_y = tgt.y if src.center_y <= tgt.center_y else (tgt.y + tgt.height)

        return (wp1_x, wp1_y), (wp2_x, wp2_y)


class XMIBuilder:
    """Generates standard UML 2.x XMI 2.1 with verified Data Binding and Diagram Interchange."""

    def __init__(self, state: ProjectState) -> None:
        self.state = state
        self.root: Optional[ET.Element] = None
        self.model: Optional[ET.Element] = None
        self.known_primitive_ids: dict[str, str] = {}
        self.layout_engine = GridAutoLayout(start_x=50, start_y=50, gap_x=250, gap_y=160)

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

    # ---------------------------------------------------------
    # Metamodel Builders (ownedMember tags, public visibility, full VP metadata)
    # ---------------------------------------------------------

    def _build_class_metamodel(self) -> None:
        assert self.model is not None

        generalizations_by_source: dict[str, list[tuple[str, str]]] = {}
        top_level_relations: list[RelationModel] = []

        for rel in self.state.class_relations:
            if rel.type == "Generalization":
                generalizations_by_source.setdefault(rel.source_id, []).append((rel.id, rel.target_id))
            else:
                top_level_relations.append(rel)

        for cls in self.state.classes.values():
            class_elem = ET.SubElement(
                self.model,
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

            # Generalization STRICTLY inside child class with exact rel.id match
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

        # Top-level class relations (Association, Composition, Dependency, Realization)
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
                    f"{{{XMI_NS}}}type": "uml:Class",
                    f"{{{XMI_NS}}}id": ent.id,
                    "name": ent.name,
                    "visibility": "public",
                    "isAbstract": "false",
                    "isActive": "false",
                    "isLeaf": "false",
                },
            )

            # VP Stereotype: entity
            e_annot = ET.SubElement(
                ent_elem,
                "eAnnotations",
                {f"{{{XMI_NS}}}id": create_uuid_id("annot"), "source": "Stereotype"},
            )
            ET.SubElement(e_annot, "details", {f"{{{XMI_NS}}}id": create_uuid_id("det"), "key": "entity", "value": "true"})

            ent_vp_ext = ET.SubElement(ent_elem, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
            ET.SubElement(ent_vp_ext, "isRoot", {f"{{{XMI_NS}}}value": "false"})
            ET.SubElement(ent_vp_ext, "modelType", {"value": "Class"})
            ET.SubElement(ent_vp_ext, "businessModel", {f"{{{XMI_NS}}}value": "false"})
            ET.SubElement(ent_vp_ext, "qualityScore", {"value": "-1"})

            # Columns STRICTLY inside entity class
            for col in ent.columns:
                col_attrs = {
                    f"{{{XMI_NS}}}type": "uml:Property",
                    f"{{{XMI_NS}}}id": col.id,
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
                ET.SubElement(col_vp_ext, "isVisble", {f"{{{XMI_NS}}}value": "true"})
                ET.SubElement(col_vp_ext, "qualityScore", {"value": "-1"})

                # Annotations for column, primaryKey, foreignKey
                col_annot = ET.SubElement(
                    prop_elem,
                    "eAnnotations",
                    {f"{{{XMI_NS}}}id": create_uuid_id("annot"), "source": "Stereotype"},
                )
                ET.SubElement(col_annot, "details", {f"{{{XMI_NS}}}id": create_uuid_id("det"), "key": "column", "value": "true"})
                if col.is_primary_key:
                    ET.SubElement(col_annot, "details", {f"{{{XMI_NS}}}id": create_uuid_id("det"), "key": "primaryKey", "value": "true"})
                    ET.SubElement(col_annot, "details", {f"{{{XMI_NS}}}id": create_uuid_id("det"), "key": "stereotype", "value": "PK"})
                if col.is_foreign_key:
                    ET.SubElement(col_annot, "details", {f"{{{XMI_NS}}}id": create_uuid_id("det"), "key": "foreignKey", "value": "true"})
                    ET.SubElement(col_annot, "details", {f"{{{XMI_NS}}}id": create_uuid_id("det"), "key": "stereotype", "value": "FK"})
                if not col.is_nullable:
                    ET.SubElement(col_annot, "details", {f"{{{XMI_NS}}}id": create_uuid_id("det"), "key": "nullable", "value": "false"})
                if col.length:
                    ET.SubElement(col_annot, "details", {f"{{{XMI_NS}}}id": create_uuid_id("det"), "key": "length", "value": str(col.length)})

        for rel in self.state.er_relations:
            src = self.state.find_entity(rel.source_id)
            tgt = self.state.find_entity(rel.target_id)
            if not src or not tgt:
                continue

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
            src_end = ET.SubElement(
                assoc_elem,
                "ownedEnd",
                {
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
                },
            )
            tgt_end_vp = ET.SubElement(tgt_end, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
            ET.SubElement(tgt_end_vp, "associationEnd")
            ET.SubElement(tgt_end_vp, "qualityScore", {"value": "-1"})

            if rel.type == "1:1":
                self._append_multiplicity(src_end, "1", end_src_id)
                self._append_multiplicity(tgt_end, "1", end_tgt_id)
            elif rel.type == "1:N":
                self._append_multiplicity(src_end, "1", end_src_id)
                self._append_multiplicity(tgt_end, "*", end_tgt_id)
            elif rel.type == "M:N":
                self._append_multiplicity(src_end, "*", end_src_id)
                self._append_multiplicity(tgt_end, "*", end_tgt_id)

            assoc_vp = ET.SubElement(assoc_elem, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
            ET.SubElement(assoc_vp, "qualityScore", {"value": "-1"})

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

            if uc.id in includes_by_source:
                for rel_id, target_id in includes_by_source[uc.id]:
                    inc_elem = ET.SubElement(
                        uc_elem,
                        "include",
                        {
                            f"{{{XMI_NS}}}type": "uml:Include",
                            f"{{{XMI_NS}}}id": rel_id,
                            "addition": target_id,
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

            assoc_elem = ET.SubElement(
                self.model,
                "ownedMember",
                {
                    f"{{{XMI_NS}}}type": "uml:Association",
                    f"{{{XMI_NS}}}id": rel.id,
                    "name": rel.name or f"{src.name}_{tgt.name}_Association",
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
                st_ext = ET.SubElement(subv, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
                ET.SubElement(st_ext, "modelType", {"value": "State"})

        for tr in self.state.transitions:
            tr_attrs = {
                f"{{{XMI_NS}}}type": "uml:Transition",
                f"{{{XMI_NS}}}id": tr.id,
                "source": tr.source_id,
                "target": tr.target_id,
            }
            if tr.trigger_event:
                tr_attrs["name"] = tr.trigger_event
            tr_elem = ET.SubElement(region_elem, "transition", tr_attrs)
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
        if shape_type == "Actor":
            effective_caption_side = 1
            caption_bounds = f"0,{p.height},{p.width},18"
            align = "4"
        elif shape_type == "UseCase":
            effective_caption_side = 12
            caption_bounds = f"0,0,{p.width},{p.height}"
            align = "4"
        else:
            effective_caption_side = caption_side
            caption_bounds = f"0,0,{p.width},16"
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
        ET.SubElement(shape_vp, "captionVisible", {"value": "true"})
        ET.SubElement(shape_vp, "captionSide", {"value": str(effective_caption_side)})

        props = ET.SubElement(shape_vp, "properties")
        ET.SubElement(props, "azOrder", {"value": "2"})
        ET.SubElement(props, "abackground", {"value": "Cr:122,207,245,255"})
        ET.SubElement(props, "aforeground", {"value": "Cr:0,0,0,255"})
        ET.SubElement(props, "acreatorDiagramType", {"value": creator_diag_type})
        ET.SubElement(props, "aselectable", {"value": "true"})
        ET.SubElement(props, "amodelElementNameAlignment", {"value": align})
        if shape_type == "Actor":
            ET.SubElement(props, "arequestResetCaption", {"value": "true"})
        ET.SubElement(props, "ashowAttributeType", {"value": "1"})
        ET.SubElement(props, "ashowOperationType", {"value": "1"})
        ET.SubElement(props, "ashowReceptionType", {"value": "1"})
        ET.SubElement(props, "ashowEmptyCompartments", {"value": "0"})
        ET.SubElement(props, "ashowOperationSignature", {"value": "true"})
        ET.SubElement(props, "ashowInitialAttributeValue", {"value": "true"})

        ET.SubElement(omg_elem, "elementFill", {"color1": "Cr:122,207,245,255", "color2": "", "style": "1", "transparency": "0", "type": "1"})
        ET.SubElement(omg_elem, "elementFont", {"bold": "false", "color": "Cr:0,0,0,255", "italic": "false", "name": "Dialog", "size": "11", "style": "0"})
        ET.SubElement(omg_elem, "elementLine", {"color": "Cr:0,0,0,255", "style": "1", "transparency": "0", "weight": "1.0"})
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
    ) -> None:
        """Add fully-styled OMG DiagramElement connector with Visual Paradigm data binding."""
        wp1, wp2 = GridAutoLayout.calculate_waypoints(src_p, tgt_p)
        mid_x = (wp1[0] + wp2[0]) // 2
        mid_y = (wp1[1] + wp2[1]) // 2

        omg_conn = ET.SubElement(
            omg_elements,
            f"{{{UML_NS}}}DiagramElement",
            {
                f"{{{XMI_NS}}}id": f"conn_{rel_id}",
                "fromDiagramElement": src_p.shape_id,
                "toDiagramElement": tgt_p.shape_id,
                "geometry": f"{wp1[0]},{wp1[1]};{wp2[0]},{wp2[1]};",
                "preferredShapeType": rel_type,
                "subject": rel_id,
            },
        )
        conn_vp = ET.SubElement(omg_conn, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
        ET.SubElement(conn_vp, "captionBounds", {"value": f"{mid_x},{mid_y},50,16"})
        ET.SubElement(conn_vp, "captionInternalWidth", {"value": "-2147483648"})
        ET.SubElement(conn_vp, "captionInternalHeight", {"value": "-2147483648"})
        ET.SubElement(conn_vp, "captionVisible", {"value": "true"})
        ET.SubElement(conn_vp, "captionSide", {"value": "1"})

        if src_mult or tgt_mult:
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
        ET.SubElement(c_props, "ashowConnectorName", {"value": "2"})

        if src_mult or tgt_mult:
            ET.SubElement(c_props, "amultiplicityARectangle", {"value": f"Re:{wp1[0]}.0,{wp1[1]}.0,30.0,16.0"})
            ET.SubElement(c_props, "amultiplicityBRectangle", {"value": f"Re:{wp2[0]}.0,{wp2[1]}.0,30.0,16.0"})
            ET.SubElement(c_props, "ahasMultiplicityAShape", {"value": "true"})
            ET.SubElement(c_props, "ahasMultiplicityBShape", {"value": "true"})
            ET.SubElement(c_props, "ashowFromRoleName", {"value": "true"})
            ET.SubElement(c_props, "ashowToRoleName", {"value": "true"})
            ET.SubElement(c_props, "ashowFromMultiplicity", {"value": "true"})
            ET.SubElement(c_props, "ashowToMultiplicity", {"value": "true"})

        ET.SubElement(omg_conn, "elementFont", {"bold": "false", "color": "Cr:0,0,0,255", "italic": "false", "name": "Dialog", "size": "11", "style": "0"})
        ET.SubElement(omg_conn, "elementLine", {"color": "Cr:0,0,0,255", "style": "1", "transparency": "0", "weight": "1.0"})

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

        omg_elements = ET.SubElement(omg_diag, f"{{{UML_NS}}}Diagram.element")
        return omg_diag, omg_elements

    def _build_visual_layers(self) -> None:
        """Inject OMG <uml:Diagram> and <uml:DiagramElement> for all active diagrams."""
        assert self.root is not None

        # Diagram 1: Class Diagram
        if self.state.classes:
            class_nodes: list[BaseNode] = list(self.state.classes.values())
            class_placements = self.layout_engine.layout_nodes(class_nodes)
            _, omg_elements = self._create_diagram("omg_diag_class_1", "Class Diagram", "ClassDiagram")

            for p in class_placements.values():
                cls_node = self.state.classes[p.node_id]
                shape_type = "Interface" if cls_node.element_type == "Interface" else "Class"
                self._add_shape_element(
                    omg_elements,
                    p,
                    cls_node,
                    shape_type=shape_type,
                    creator_diag_type="ClassDiagram",
                    caption_side=12,
                )

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

        # Diagram 2: ER Diagram
        if self.state.entities:
            er_nodes: list[BaseNode] = list(self.state.entities.values())
            er_placements = self.layout_engine.layout_nodes(er_nodes)
            _, omg_elements = self._create_diagram("omg_diag_erd_1", "Entity Relationship Diagram", "ERDiagram")

            for p in er_placements.values():
                ent_node = self.state.entities[p.node_id]
                self._add_shape_element(
                    omg_elements,
                    p,
                    ent_node,
                    shape_type="Class",
                    creator_diag_type="ERDiagram",
                    caption_side=12,
                )

            for rel in self.state.er_relations:
                if rel.source_id in er_placements and rel.target_id in er_placements:
                    src_p = er_placements[rel.source_id]
                    tgt_p = er_placements[rel.target_id]
                    src_mult = "1" if rel.type in ("1:1", "1:N") else "*"
                    tgt_mult = "1" if rel.type == "1:1" else "*"
                    self._add_connector_element(
                        omg_elements,
                        rel_id=rel.id,
                        rel_type="Association",
                        rel_name=rel.name or rel.type,
                        src_p=src_p,
                        tgt_p=tgt_p,
                        creator_diag_type="ERDiagram",
                        src_mult=src_mult,
                        tgt_mult=tgt_mult,
                    )

        # Diagram 3: Use Case Diagram
        if self.state.actors or self.state.use_cases:
            uc_nodes: list[BaseNode] = list(self.state.actors.values()) + list(self.state.use_cases.values())
            uc_placements = self.layout_engine.layout_nodes(uc_nodes)
            _, omg_elements = self._create_diagram("omg_diag_uc_1", "Use Case Diagram", "UseCaseDiagram")

            for p in uc_placements.values():
                is_actor = p.node_id in self.state.actors
                shape_type = "Actor" if is_actor else "UseCase"
                caption_side = 7 if is_actor else 12
                uc_node = self.state.actors[p.node_id] if is_actor else self.state.use_cases[p.node_id]
                self._add_shape_element(
                    omg_elements,
                    p,
                    uc_node,
                    shape_type=shape_type,
                    creator_diag_type="UseCaseDiagram",
                    caption_side=caption_side,
                )

            for rel in self.state.uc_relations:
                if rel.source_id in uc_placements and rel.target_id in uc_placements:
                    src_p = uc_placements[rel.source_id]
                    tgt_p = uc_placements[rel.target_id]
                    self._add_connector_element(
                        omg_elements,
                        rel_id=rel.id,
                        rel_type=rel.type,
                        rel_name=rel.name or rel.type,
                        src_p=src_p,
                        tgt_p=tgt_p,
                        creator_diag_type="UseCaseDiagram",
                    )

        # Diagram 4: State Machine Diagram
        if self.state.states:
            sm_nodes: list[BaseNode] = list(self.state.states.values())
            sm_placements = self.layout_engine.layout_nodes(sm_nodes)
            _, omg_elements = self._create_diagram("omg_diag_sm_1", "State Machine Diagram", "StateDiagram")

            for p in sm_placements.values():
                st_obj = self.state.states[p.node_id]
                shape_type = "State" if st_obj.type == "State" else ("InitialPseudoState" if st_obj.type == "Initial" else "FinalState")
                self._add_shape_element(
                    omg_elements,
                    p,
                    st_obj,
                    shape_type=shape_type,
                    creator_diag_type="StateDiagram",
                    caption_side=12,
                )

            for tr in self.state.transitions:
                if tr.source_id in sm_placements and tr.target_id in sm_placements:
                    src_p = sm_placements[tr.source_id]
                    tgt_p = sm_placements[tr.target_id]
                    self._add_connector_element(
                        omg_elements,
                        rel_id=tr.id,
                        rel_type="Transition",
                        rel_name=tr.trigger_event or "Transition",
                        src_p=src_p,
                        tgt_p=tgt_p,
                        creator_diag_type="StateDiagram",
                    )

    def build_tree(self) -> ET.ElementTree:
        """Construct full XML ElementTree with Metamodel and Visual Layout."""
        ET.register_namespace("xmi", XMI_NS)
        ET.register_namespace("uml", UML_NS)
        ET.register_namespace("xsi", XSI_NS)

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

        # 1. Logical Metamodel (pure native ownedMember elements)
        self._build_class_metamodel()
        self._build_er_metamodel()
        self._build_uc_metamodel()
        self._build_sm_metamodel()

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
