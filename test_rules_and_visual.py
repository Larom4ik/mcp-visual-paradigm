"""Unit and integration tests for Rules Engine, Visual Layout, and XMI Export."""

import os
import xml.etree.ElementTree as ET
from mcp_tools.tools import (
    add_actor,
    add_class,
    add_class_attribute,
    add_class_method,
    add_class_relation,
    add_er_column,
    add_er_entity,
    add_er_relation,
    add_state,
    add_state_transition,
    add_uc_relation,
    add_use_case,
    export_xmi,
    init_project,
)
from core.state import state

def run_tests():
    print("=== TEST 1: Rules Engine (Self-Correction Feedback) ===")
    init_project("TestRulesProject")

    # 1.1 Interface private attribute rule
    add_class("IService", element_type="Interface")
    res_err_attr = add_class_attribute("IService", "secretKey", "string", "private")
    print("Interface private attr response:", res_err_attr)
    assert res_err_attr.startswith("ERROR:"), "Should reject private attribute in Interface"

    # 1.2 Cyclic inheritance detection
    add_class("ClassA")
    add_class("ClassB")
    add_class("ClassC")
    add_class_relation("ClassA", "ClassB", "Generalization")
    add_class_relation("ClassB", "ClassC", "Generalization")
    res_cycle = add_class_relation("ClassC", "ClassA", "Generalization")
    print("Cyclic inheritance response:", res_cycle)
    assert res_cycle.startswith("ERROR:"), "Should detect cyclic inheritance loop"

    # 1.3 ERD 1:N missing FK rule
    add_er_entity("authors")
    add_er_column("authors", "id", "INT", is_pk=True)
    add_er_entity("books")
    add_er_column("books", "id", "INT", is_pk=True)
    add_er_column("books", "title", "VARCHAR", length=150)
    # Attempt 1:N without FK
    res_fk_err = add_er_relation("authors", "books", "1:N")
    print("ERD 1:N missing FK response:", res_fk_err)
    assert res_fk_err.startswith("ERROR:"), "Should require target entity to have FK"

    # Now add FK and retry
    add_er_column("books", "author_id", "INT", is_fk=True)
    res_fk_ok = add_er_relation("authors", "books", "1:N")
    print("ERD 1:N with FK response:", res_fk_ok)
    assert not res_fk_ok.startswith("ERROR:"), "Should succeed after adding FK"

    # 1.4 Use Case Include rule: only between Use Cases, not Actors
    add_actor("Member")
    add_use_case("BorrowBook")
    res_uc_err = add_uc_relation("Member", "BorrowBook", "Include")
    print("Include with Actor response:", res_uc_err)
    assert res_uc_err.startswith("ERROR:"), "Include cannot have an Actor as source"

    # Valid Include
    add_use_case("CheckCardValid")
    res_uc_ok = add_uc_relation("BorrowBook", "CheckCardValid", "Include")
    print("Include between UseCases response:", res_uc_ok)
    assert not res_uc_ok.startswith("ERROR:")

    print("\n=== TEST 2: Visual Layout Engine Export ===")
    add_state("InitialVertex", "Initial")
    add_state("BookReserved", "State")
    add_state("Completed", "Final")
    add_state_transition("InitialVertex", "BookReserved", "reserve")
    add_state_transition("BookReserved", "Completed", "returnBook")

    output_path = os.path.join(os.path.dirname(__file__), "visual_layout_output.xmi")
    export_res = export_xmi(output_path)
    print("Export response:", export_res)
    assert not export_res.startswith("ERROR:")
    assert os.path.exists(output_path)

    print("\n=== TEST 3: Validating Visual Layer XML ===")
    tree = ET.parse(output_path)
    root = tree.getroot()

    XMI_NS = "http://schema.omg.org/spec/XMI/2.1"
    UML_NS = "http://schema.omg.org/spec/UML/2.0"

    # 3.1 Check Visual Paradigm Extension (<xmi:Extension extender="Visual Paradigm"><projectProperties>)
    vp_extensions = [e for e in root.findall(f"{{{XMI_NS}}}Extension") if e.attrib.get("extender") == "Visual Paradigm"]
    assert len(vp_extensions) >= 1, "Visual Paradigm Extension must be present"

    proj_props = None
    for ext in vp_extensions:
        p = ext.find("projectProperties")
        if p is not None:
            proj_props = p
            break
    assert proj_props is not None, "<projectProperties> must be present in root VP Extension"

    # 3.2 Check Model Elements (<ownedMember>)
    model = root.find(f"{{{UML_NS}}}Model")
    assert model is not None, "<uml:Model> must be present"
    owned_members = model.findall("ownedMember")
    print(f"Found {len(owned_members)} ownedMember elements in <uml:Model>.")
    assert len(owned_members) >= 5, "Model must contain classes, interfaces, and state machine"

    # 3.3 Check OMG Diagram Layer (<uml:Diagram>) with VP Extensions
    omg_diagrams = root.findall(f"{{{UML_NS}}}Diagram")
    print(f"\nFound {len(omg_diagrams)} standard OMG <uml:Diagram> elements:")
    for od in omg_diagrams:
        d_type = od.attrib.get("diagramType")
        d_ext = od.find(f"{{{XMI_NS}}}Extension")
        assert d_ext is not None, "Diagram must have Visual Paradigm Extension"
        d_props = d_ext.find("properties")
        assert d_props is not None, "Diagram must have VP properties"
        assert d_props.find("ashowClassEmptyCompartments") is not None

        elems = od.find(f"{{{UML_NS}}}Diagram.element")
        assert elems is not None
        diag_elems = elems.findall(f"{{{UML_NS}}}DiagramElement")
        print(f"  - OMG Diagram: type='{d_type}', diagramElements={len(diag_elems)}")
        assert len(diag_elems) > 0

        # Validate shapes and connectors
        for de in diag_elems:
            geom = de.attrib.get("geometry")
            pref_type = de.attrib.get("preferredShapeType")
            subj = de.attrib.get("subject")
            assert geom, "DiagramElement must have geometry"
            assert pref_type, "DiagramElement must have preferredShapeType"
            assert subj, "DiagramElement must have subject bound to model element"
            de_ext = de.find(f"{{{XMI_NS}}}Extension")
            assert de_ext is not None, "DiagramElement must have VP extension"
            assert de_ext.find("captionBounds") is not None, "DiagramElement must have captionBounds"

    print("\n>>> ALL TESTS PASSED WITH 100% SUCCESS! <<<")

if __name__ == "__main__":
    run_tests()
