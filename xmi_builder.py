"""XMI 2.1 Builder for Visual Paradigm compatibility.

Generates standard OMG UML 2.x / XMI 2.1 XML files from diagram state,
ready for direct import into Visual Paradigm (Project > Import > XMI...).
"""

import math
import os
import re
import uuid
import xml.etree.ElementTree as ET
from typing import Optional
from models import DiagramState, RelationModel

# Standard OMG Namespaces for UML 2.0 / XMI 2.1
XMI_NS = "http://schema.omg.org/spec/XMI/2.1"
UML_NS = "http://schema.omg.org/spec/UML/2.0"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"


def sanitize_id(raw_str: str) -> str:
    """Ensure an ID is valid XML NCName and starts with an underscore or letter."""
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", raw_str)
    if not cleaned or cleaned[0].isdigit():
        return f"_{cleaned}"
    return cleaned


def append_multiplicity(parent: ET.Element, mult_str: str, prefix_id: str) -> None:
    """Add lowerValue and upperValue XML tags to an ownedEnd if multiplicity is specified."""
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


def generate_xmi(state: DiagramState, filepath: str) -> str:
    """Build XMI 2.1 XML structure from DiagramState and write to filepath.

    Args:
        state: DiagramState holding classes and relations.
        filepath: Destination file path for .xmi file.

    Returns:
        Absolute path to the created XMI file.
    """
    ET.register_namespace("xmi", XMI_NS)
    ET.register_namespace("uml", UML_NS)
    ET.register_namespace("xsi", XSI_NS)

    root = ET.Element(
        f"{{{XMI_NS}}}XMI",
        {
            f"{{{XMI_NS}}}version": "2.1",
        },
    )

    doc_elem = ET.SubElement(
        root,
        f"{{{XMI_NS}}}Documentation",
        {
            "exporter": "Visual Paradigm",
            "exporterVersion": "7.0.2",
        },
    )
    doc_ext = ET.SubElement(doc_elem, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
    ET.SubElement(doc_ext, "nickname", {"exportedFromDifferentName": "false"})

    root_ext = ET.SubElement(root, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
    proj_props = ET.SubElement(root_ext, "projectProperties")
    ET.SubElement(proj_props, "projectProperty", {"name": "author", "value": "Architect"})

    model_id = f"_{uuid.uuid4().hex}"
    model_elem = ET.SubElement(
        root,
        f"{{{UML_NS}}}Model",
        {
            f"{{{XMI_NS}}}type": "uml:Model",
            f"{{{XMI_NS}}}id": model_id,
            "name": state.name or "ArchitectureModel",
            "visibility": "public",
        },
    )

    known_primitive_ids: dict[str, str] = {}

    def get_or_create_type_id(type_name: str) -> Optional[str]:
        cleaned = (type_name or "").strip()
        if not cleaned or cleaned.lower() in ("void", "none", ""):
            return None

        cls_match = state.find_class(cleaned)
        if cls_match:
            return cls_match.id

        norm_key = cleaned.lower()
        if norm_key not in known_primitive_ids:
            pt_id = f"{sanitize_id(norm_key)}_id"
            known_primitive_ids[norm_key] = pt_id
            ET.SubElement(
                model_elem,
                "ownedMember",
                {
                    f"{{{XMI_NS}}}type": "uml:DataType",
                    f"{{{XMI_NS}}}id": pt_id,
                    "name": cleaned,
                    "visibility": "public",
                },
            )
        return known_primitive_ids[norm_key]

    for cls in state.classes.values():
        for attr in cls.attributes:
            get_or_create_type_id(attr.type)
        for meth in cls.methods:
            get_or_create_type_id(meth.return_type)
            for param in meth.params:
                get_or_create_type_id(param.get("type", "string"))

    generalizations_by_source: dict[str, list[RelationModel]] = {}
    other_relations: list[RelationModel] = []

    for rel in state.relations:
        if rel.relation_type == "Generalization":
            generalizations_by_source.setdefault(rel.source_id, []).append(rel)
        else:
            other_relations.append(rel)

    # Build Class Elements as ownedMember
    for cls in state.classes.values():
        class_elem = ET.SubElement(
            model_elem,
            "ownedMember",
            {
                f"{{{XMI_NS}}}type": "uml:Class",
                f"{{{XMI_NS}}}id": cls.id,
                "name": cls.name,
                "visibility": "public",
                "isAbstract": "false",
                "isActive": "false",
                "isLeaf": "false",
            },
        )

        cls_vp_ext = ET.SubElement(class_elem, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
        ET.SubElement(cls_vp_ext, "isRoot", {f"{{{XMI_NS}}}value": "false"})
        ET.SubElement(cls_vp_ext, "modelType", {"value": "Class"})
        ET.SubElement(cls_vp_ext, "businessModel", {f"{{{XMI_NS}}}value": "false"})
        ET.SubElement(cls_vp_ext, "qualityScore", {"value": "-1"})

        # Generalizations
        if cls.id in generalizations_by_source:
            for gen_rel in generalizations_by_source[cls.id]:
                gen_elem = ET.SubElement(
                    class_elem,
                    "generalization",
                    {
                        f"{{{XMI_NS}}}type": "uml:Generalization",
                        f"{{{XMI_NS}}}id": gen_rel.id,
                        "general": gen_rel.target_id,
                    },
                )
                gen_vp = ET.SubElement(gen_elem, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
                ET.SubElement(gen_vp, "qualityScore", {"value": "-1"})

        # Attributes
        for attr in cls.attributes:
            attr_id = f"_attr_{sanitize_id(cls.name)}_{sanitize_id(attr.name)}_{uuid.uuid4().hex[:8]}"
            attr_attrs = {
                f"{{{XMI_NS}}}type": "uml:Property",
                f"{{{XMI_NS}}}id": attr_id,
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
            type_id = get_or_create_type_id(attr.type)
            if type_id:
                attr_attrs["type"] = type_id

            prop_elem = ET.SubElement(class_elem, "ownedAttribute", attr_attrs)
            attr_vp_ext = ET.SubElement(prop_elem, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
            ET.SubElement(attr_vp_ext, "attribute")
            ET.SubElement(attr_vp_ext, "isAbstract", {f"{{{XMI_NS}}}value": "false"})
            ET.SubElement(attr_vp_ext, "isVisble", {f"{{{XMI_NS}}}value": "true"})
            ET.SubElement(attr_vp_ext, "qualityScore", {"value": "-1"})

        # Methods / Operations
        for method in cls.methods:
            method_id = f"_op_{sanitize_id(cls.name)}_{sanitize_id(method.name)}_{uuid.uuid4().hex[:8]}"
            op_elem = ET.SubElement(
                class_elem,
                "ownedOperation",
                {
                    f"{{{XMI_NS}}}type": "uml:Operation",
                    f"{{{XMI_NS}}}id": method_id,
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

            ret_type_id = get_or_create_type_id(method.return_type)
            if ret_type_id:
                ET.SubElement(
                    op_elem,
                    "ownedParameter",
                    {
                        f"{{{XMI_NS}}}type": "uml:Parameter",
                        f"{{{XMI_NS}}}id": f"_param_ret_{method_id}",
                        "kind": "return",
                        "type": ret_type_id,
                    },
                )

            for p_idx, param in enumerate(method.params):
                p_name = param.get("name", f"param{p_idx + 1}")
                p_type = param.get("type", "string")
                p_id = f"_param_{sanitize_id(p_name)}_{method_id}_{p_idx}"
                p_attrs = {
                    f"{{{XMI_NS}}}type": "uml:Parameter",
                    f"{{{XMI_NS}}}id": p_id,
                    "name": p_name,
                    "kind": "in",
                }
                p_type_id = get_or_create_type_id(p_type)
                if p_type_id:
                    p_attrs["type"] = p_type_id

                ET.SubElement(op_elem, "ownedParameter", p_attrs)

            op_vp_ext = ET.SubElement(op_elem, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
            ET.SubElement(op_vp_ext, "returnTypeDocumentation", {f"{{{XMI_NS}}}value": ""})
            props = ET.SubElement(op_vp_ext, "properties")
            ET.SubElement(props, "property", {"name": "visible", "type": "boolean", "value": "true"})
            ET.SubElement(props, "property", {"name": "qualityScore", "type": "int", "value": "-1"})
            ET.SubElement(op_vp_ext, "qualityScore", {"value": "-1"})

    # Build Relationships as ownedMember
    for rel in other_relations:
        src_cls = state.find_class(rel.source_id)
        tgt_cls = state.find_class(rel.target_id)
        if not src_cls or not tgt_cls:
            continue

        if rel.relation_type == "Dependency":
            dep_elem = ET.SubElement(
                model_elem,
                "ownedMember",
                {
                    f"{{{XMI_NS}}}type": "uml:Dependency",
                    f"{{{XMI_NS}}}id": rel.id,
                    "name": f"{src_cls.name}_depends_on_{tgt_cls.name}",
                    "visibility": "public",
                    "client": rel.source_id,
                    "supplier": rel.target_id,
                },
            )
            dep_vp = ET.SubElement(dep_elem, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
            ET.SubElement(dep_vp, "qualityScore", {"value": "-1"})
        else:
            end_src_id = f"_end_src_{rel.id}"
            end_tgt_id = f"_end_tgt_{rel.id}"

            assoc_elem = ET.SubElement(
                model_elem,
                "ownedMember",
                {
                    f"{{{XMI_NS}}}type": "uml:Association",
                    f"{{{XMI_NS}}}id": rel.id,
                    "name": f"{src_cls.name}_{tgt_cls.name}_{rel.relation_type}",
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
                "name": src_cls.name.lower(),
                "visibility": "public",
                "type": rel.source_id,
                "association": rel.id,
                "aggregation": "none",
                "isDerived": "false",
                "isDerivedUnion": "false",
                "isLeaf": "false",
                "isNavigable": "true",
                "isReadOnly": "false",
                "isStatic": "false",
            }
            if rel.relation_type == "Aggregation":
                src_end_attrs["aggregation"] = "shared"
            elif rel.relation_type == "Composition":
                src_end_attrs["aggregation"] = "composite"

            src_end = ET.SubElement(assoc_elem, "ownedEnd", src_end_attrs)
            src_end_vp = ET.SubElement(src_end, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
            ET.SubElement(src_end_vp, "associationEnd")
            ET.SubElement(src_end_vp, "qualityScore", {"value": "-1"})
            append_multiplicity(src_end, rel.source_multiplicity, end_src_id)

            ET.SubElement(assoc_elem, "memberEnd", {f"{{{XMI_NS}}}idref": end_tgt_id})
            tgt_end_attrs = {
                f"{{{XMI_NS}}}type": "uml:Property",
                f"{{{XMI_NS}}}id": end_tgt_id,
                "name": tgt_cls.name.lower(),
                "visibility": "public",
                "type": rel.target_id,
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
            append_multiplicity(tgt_end, rel.target_multiplicity, end_tgt_id)

            assoc_vp = ET.SubElement(assoc_elem, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
            ET.SubElement(assoc_vp, "qualityScore", {"value": "-1"})

    # Build Visual Layer (OMG Diagram)
    if state.classes:
        omg_diag = ET.SubElement(
            root,
            f"{{{UML_NS}}}Diagram",
            {
                f"{{{XMI_NS}}}id": "omg_diag_class_1",
                "name": state.name or "Class Diagram",
                "diagramType": "ClassDiagram",
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

        placements: dict[str, tuple[int, int, int, int, str]] = {}
        cols = max(3, int(math.ceil(math.sqrt(len(state.classes)))))
        for i, cls in enumerate(state.classes.values()):
            col = i % cols
            row = i // cols
            x = 50 + col * 250
            y = 50 + row * 160
            w = 160
            h = max(80, 40 + 18 * len(cls.attributes) + 18 * len(cls.methods))
            shape_id = f"shape_{cls.id}"
            placements[cls.id] = (x, y, w, h, shape_id)

            omg_elem = ET.SubElement(
                omg_elements,
                f"{{{UML_NS}}}DiagramElement",
                {
                    f"{{{XMI_NS}}}id": shape_id,
                    "geometry": f"{x},{y},{w},{h}",
                    "preferredShapeType": "Class",
                    "subject": cls.id,
                },
            )
            shape_vp = ET.SubElement(omg_elem, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
            ET.SubElement(shape_vp, "captionBounds", {"value": f"0,0,{w},16"})
            ET.SubElement(shape_vp, "captionInternalWidth", {"value": "-2147483648"})
            ET.SubElement(shape_vp, "captionInternalHeight", {"value": "-2147483648"})
            ET.SubElement(shape_vp, "captionVisible", {"value": "true"})
            ET.SubElement(shape_vp, "captionSide", {"value": "12"})

            props = ET.SubElement(shape_vp, "properties")
            ET.SubElement(props, "azOrder", {"value": "2"})
            ET.SubElement(props, "abackground", {"value": "Cr:122,207,245,255"})
            ET.SubElement(props, "aforeground", {"value": "Cr:0,0,0,255"})
            ET.SubElement(props, "acreatorDiagramType", {"value": "ClassDiagram"})
            ET.SubElement(props, "aselectable", {"value": "true"})
            ET.SubElement(props, "amodelElementNameAlignment", {"value": "9"})
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

        for rel in state.relations:
            if rel.source_id in placements and rel.target_id in placements:
                src_x, src_y, src_w, src_h, src_sid = placements[rel.source_id]
                tgt_x, tgt_y, tgt_w, tgt_h, tgt_sid = placements[rel.target_id]
                wp1_x = src_x + src_w if tgt_x > src_x else src_x
                wp1_y = src_y + src_h // 2
                wp2_x = tgt_x if tgt_x > src_x else tgt_x + tgt_w
                wp2_y = tgt_y + tgt_h // 2
                mid_x = (wp1_x + wp2_x) // 2
                mid_y = (wp1_y + wp2_y) // 2

                omg_conn = ET.SubElement(
                    omg_elements,
                    f"{{{UML_NS}}}DiagramElement",
                    {
                        f"{{{XMI_NS}}}id": f"conn_{rel.id}",
                        "fromDiagramElement": src_sid,
                        "toDiagramElement": tgt_sid,
                        "geometry": f"{wp1_x},{wp1_y};{wp2_x},{wp2_y};",
                        "preferredShapeType": rel.relation_type,
                        "subject": rel.id,
                    },
                )
                conn_vp = ET.SubElement(omg_conn, f"{{{XMI_NS}}}Extension", {"extender": "Visual Paradigm"})
                ET.SubElement(conn_vp, "captionBounds", {"value": f"{mid_x},{mid_y},50,16"})
                ET.SubElement(conn_vp, "captionInternalWidth", {"value": "-2147483648"})
                ET.SubElement(conn_vp, "captionInternalHeight", {"value": "-2147483648"})
                ET.SubElement(conn_vp, "captionVisible", {"value": "true"})
                ET.SubElement(conn_vp, "captionSide", {"value": "1"})

                if rel.source_multiplicity or rel.target_multiplicity:
                    ET.SubElement(conn_vp, "roleA", {"multiplicity": f"{wp1_x},{wp1_y},30,16"})
                    ET.SubElement(conn_vp, "roleB", {"multiplicity": f"{wp2_x},{wp2_y},30,16"})

                c_props = ET.SubElement(conn_vp, "properties")
                ET.SubElement(c_props, "azOrder", {"value": "10"})
                ET.SubElement(c_props, "abackground", {"value": "Cr:255,255,255,255"})
                ET.SubElement(c_props, "aforeground", {"value": "Cr:0,0,0,255"})
                ET.SubElement(c_props, "acreatorDiagramType", {"value": "ClassDiagram"})
                ET.SubElement(c_props, "aselectable", {"value": "true"})
                ET.SubElement(c_props, "aconnectorStyle", {"value": "3"})
                ET.SubElement(c_props, "aconnectorLineJumps", {"value": "4"})
                ET.SubElement(c_props, "aconnectorLabelOrientation", {"value": "4"})
                ET.SubElement(c_props, "ashowConnectorName", {"value": "2"})

                if rel.source_multiplicity or rel.target_multiplicity:
                    ET.SubElement(c_props, "amultiplicityARectangle", {"value": f"Re:{wp1_x}.0,{wp1_y}.0,30.0,16.0"})
                    ET.SubElement(c_props, "amultiplicityBRectangle", {"value": f"Re:{wp2_x}.0,{wp2_y}.0,30.0,16.0"})
                    ET.SubElement(c_props, "ahasMultiplicityAShape", {"value": "true"})
                    ET.SubElement(c_props, "ahasMultiplicityBShape", {"value": "true"})
                    ET.SubElement(c_props, "ashowFromRoleName", {"value": "true"})
                    ET.SubElement(c_props, "ashowToRoleName", {"value": "true"})
                    ET.SubElement(c_props, "ashowFromMultiplicity", {"value": "true"})
                    ET.SubElement(c_props, "ashowToMultiplicity", {"value": "true"})

                ET.SubElement(omg_conn, "elementFont", {"bold": "false", "color": "Cr:0,0,0,255", "italic": "false", "name": "Dialog", "size": "11", "style": "0"})
                ET.SubElement(omg_conn, "elementLine", {"color": "Cr:0,0,0,255", "style": "1", "transparency": "0", "weight": "1.0"})

    ET.indent(root, space="\t")

    abs_filepath = os.path.abspath(filepath)
    os.makedirs(os.path.dirname(abs_filepath), exist_ok=True)

    tree = ET.ElementTree(root)
    tree.write(abs_filepath, encoding="utf-8", xml_declaration=True)
    return abs_filepath
