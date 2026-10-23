"""Comprehensive end-to-end verification of all 4 diagram types and XMI export."""

import os
import sys
import xml.etree.ElementTree as ET

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from mcp_tools.tools import (
    add_actor,
    add_class,
    add_class_attribute,
    add_class_method,
    add_class_relation,
    add_er_column,
    add_er_entity,
    add_er_relation,
    add_package,
    add_state,
    add_state_transition,
    add_uc_relation,
    add_use_case,
    export_xmi,
    get_project_summary,
    init_project,
    move_class_to_package,
    smart_add_relation,
    suggest_relation,
)
from core.state import state

def run_tests():
    print("=== 1. Initialize Project ===")
    print(init_project("EnterpriseSystem"))
    assert state.name == "EnterpriseSystem"

    print("\n=== 2. UML Package Hierarchy Setup ===")
    print(add_package("CoreDomain"))
    print(add_package("Ordering", parent_package="CoreDomain"))
    print(add_package("PaymentSubsystem"))

    print("\n=== 3. UML Class Diagram Setup with Packages ===")
    print(add_class("BaseEntity", package="CoreDomain"))
    print(add_class_attribute("BaseEntity", "id", "UUID", "public"))
    print(add_class_attribute("BaseEntity", "createdAt", "DateTime", "protected"))

    print(add_class("User", package="CoreDomain"))
    print(add_class_attribute("User", "email", "string", "private"))
    print(add_class_attribute("User", "passwordHash", "string", "private"))
    print(add_class_method("User", "authenticate", "bool", [{"name": "password", "type": "string", "direction": "in"}]))

    print(add_class("Customer", package="CoreDomain"))
    print(add_class_attribute("Customer", "loyaltyPoints", "int", "public"))

    print(add_class("Order", package="Ordering"))
    print(add_class_attribute("Order", "total", "float", "public"))
    print(add_class_method("Order", "recalculate", "void", []))

    print(add_class("OrderItem", package="Ordering"))
    print(add_class_attribute("OrderItem", "quantity", "int", "public"))

    print(add_class("IPaymentGateway", element_type="Interface", package="PaymentSubsystem"))
    print(add_class_method("IPaymentGateway", "charge", "bool", [{"name": "amount", "type": "float"}]))

    print(add_class("StripePaymentGateway", package="PaymentSubsystem"))

    print("\n=== 4. Semantic Relationship Decision Engine Testing ===")
    # 4.1 Test suggest_relation
    sugg_comp = suggest_relation("Order", "OrderItem", "Order exclusively owns OrderItems and destroys them together")
    print(sugg_comp)
    assert "Composition" in sugg_comp, "Should recommend Composition for exclusive whole-part"

    sugg_real = suggest_relation("StripePaymentGateway", "IPaymentGateway", "implements payment interface contract")
    print("\n" + sugg_real)
    assert "Realization" in sugg_real, "Should recommend Realization for interface implementation"

    # 4.2 Test smart_add_relation
    print("\n" + smart_add_relation("User", "BaseEntity", "inherits identity and timestamps (is a)"))
    print(smart_add_relation("Customer", "User", "subclass of User"))
    print(smart_add_relation("Customer", "Order", "aggregates orders (customer has orders)"))
    print(smart_add_relation("Order", "OrderItem", "owns exclusively (composition)"))
    print(smart_add_relation("Order", "IPaymentGateway", "uses payment gateway parameter"))
    print(smart_add_relation("StripePaymentGateway", "IPaymentGateway", "implements interface contract"))

    print("\n=== 5. ER Diagram Setup ===")
    print(add_er_entity("users"))
    print(add_er_column("users", "id", "BIGINT", is_pk=True))
    print(add_er_column("users", "email", "VARCHAR(255)"))
    print(add_er_column("users", "created_at", "TIMESTAMP"))

    print(add_er_entity("user_profiles"))
    print(add_er_column("user_profiles", "id", "BIGINT", is_pk=True))
    print(add_er_column("user_profiles", "user_id", "BIGINT", is_fk=True))
    print(add_er_column("user_profiles", "avatar_url", "TEXT"))

    print(add_er_entity("orders"))
    print(add_er_column("orders", "id", "BIGINT", is_pk=True))
    print(add_er_column("orders", "user_id", "BIGINT", is_fk=True))
    print(add_er_column("orders", "status", "VARCHAR(50)"))

    print(add_er_entity("tags"))
    print(add_er_column("tags", "id", "BIGINT", is_pk=True))
    print(add_er_column("tags", "name", "VARCHAR(50)"))

    # ER Relations
    print(add_er_relation("users", "user_profiles", "1:1"))
    print(add_er_relation("users", "orders", "1:N"))
    print(add_er_relation("orders", "tags", "M:N"))

    print("\n=== 4. Use Case Diagram Setup ===")
    print(add_actor("CustomerActor"))
    print(add_actor("AdminActor"))

    print(add_use_case("Login"))
    print(add_use_case("TwoFactorAuth"))
    print(add_use_case("PlaceOrder"))
    print(add_use_case("ApplyDiscountCoupon"))

    # UC Relations
    print(add_uc_relation("CustomerActor", "PlaceOrder", "Association"))
    print(add_uc_relation("CustomerActor", "Login", "Association"))
    print(add_uc_relation("Login", "TwoFactorAuth", "Include"))
    print(add_uc_relation("PlaceOrder", "ApplyDiscountCoupon", "Extend"))

    print("\n=== 5. State Machine Diagram Setup ===")
    print(add_state("InitialState", "Initial"))
    print(add_state("Draft", "State"))
    print(add_state("Paid", "State"))
    print(add_state("Shipped", "State"))
    print(add_state("Completed", "Final"))

    # Transitions
    print(add_state_transition("InitialState", "Draft", "create"))
    print(add_state_transition("Draft", "Paid", "paySuccess"))
    print(add_state_transition("Paid", "Shipped", "dispatchOrder"))
    print(add_state_transition("Shipped", "Completed", "deliveredConfirmation"))

    print("\n=== 6. Project Summary ===")
    print(get_project_summary())

    print("\n=== 7. Export to XMI 2.1 ===")
    output_xmi = os.path.join(os.path.dirname(__file__), "enterprise_system.xmi")
    export_msg = export_xmi(output_xmi)
    print(export_msg)

    print("\n=== 8. XML Structure & Standards Validation ===")
    assert os.path.exists(output_xmi), "XMI file was not created!"
    tree = ET.parse(output_xmi)
    root = tree.getroot()

    XMI_NS = "http://schema.omg.org/spec/XMI/2.1"
    UML_NS = "http://schema.omg.org/spec/UML/2.0"
    UML_DI_NS = UML_NS

    print("Root tag:", root.tag)
    assert root.tag == f"{{{XMI_NS}}}XMI"
    assert root.attrib.get(f"{{{XMI_NS}}}version") == "2.1"

    model = root.find(f"{{{UML_NS}}}Model")
    assert model is not None, "uml:Model not found!"
    assert model.attrib.get(f"{{{XMI_NS}}}id") == "model_1"
    assert model.attrib.get("name") == "EnterpriseSystem"

    # Validate Package Hierarchy & Metamodel Containment
    core_pkg = next(el for el in model.findall("ownedMember") if el.attrib.get("name") == "CoreDomain")
    assert core_pkg.attrib.get(f"{{{XMI_NS}}}type") == "uml:Package"
    print("Top-level Package 'CoreDomain' verified.")

    ordering_pkg = next(el for el in core_pkg.findall("ownedMember") if el.attrib.get("name") == "Ordering")
    assert ordering_pkg.attrib.get(f"{{{XMI_NS}}}type") == "uml:Package"
    print("Nested Package 'Ordering' inside 'CoreDomain' verified.")

    payment_pkg = next(el for el in model.findall("ownedMember") if el.attrib.get("name") == "PaymentSubsystem")
    assert payment_pkg.attrib.get(f"{{{XMI_NS}}}type") == "uml:Package"
    print("Top-level Package 'PaymentSubsystem' verified.")

    # Validate Class inside Package & Generalization
    user_elem = next(el for el in core_pkg.findall("ownedMember") if el.attrib.get("name") == "User")
    assert user_elem.attrib.get(f"{{{XMI_NS}}}type") == "uml:Class"
    user_gen = user_elem.find("generalization")
    assert user_gen is not None
    assert user_gen.attrib.get(f"{{{XMI_NS}}}type") == "uml:Generalization"
    print("Class Generalization verified inside User (contained in CoreDomain).")

    # Validate Visual Package Shapes & Containment
    omg_diagrams = root.findall(f"{{{UML_NS}}}Diagram")
    class_diag = next(d for d in omg_diagrams if d.attrib.get("diagramType") == "ClassDiagram")
    elems = class_diag.find(f"{{{UML_NS}}}Diagram.element")
    assert elems is not None
    diag_elems = elems.findall(f"{{{UML_NS}}}DiagramElement")

    pkg_shapes = [el for el in diag_elems if el.attrib.get("preferredShapeType") == "Package"]
    assert len(pkg_shapes) == 3, f"Expected 3 package shapes, got {len(pkg_shapes)}"
    print(f"Visual Package shapes verified: {len(pkg_shapes)} package containers.")

    user_shape = next(el for el in diag_elems if el.attrib.get("subject") == user_elem.attrib.get(f"{{{XMI_NS}}}id"))
    user_vp = user_shape.find(f"{{{XMI_NS}}}Extension")
    assert user_vp is not None
    parent_ref = user_vp.find("parentDiagramElement")
    assert parent_ref is not None, "User shape must have parentDiagramElement pointing to CoreDomain"
    assert parent_ref.attrib.get("idref") == f"shape_{core_pkg.attrib.get(f'{{{XMI_NS}}}id')}"
    print("Visual parentDiagramElement containment verified: User is visually inside CoreDomain shape.")



    # Validate ER Entities & eAnnotations
    users_table = next(el for el in model.findall("ownedMember") if el.attrib.get("name") == "users")
    table_annot = users_table.find("eAnnotations")
    assert table_annot is not None
    assert table_annot.attrib.get("source") == "Stereotype"
    details = table_annot.find("details")
    assert details is not None and details.attrib.get("key") == "entity"
    print("ER Entity eAnnotation verified.")

    # Validate PK / FK annotations
    id_col = next(el for el in users_table.findall("ownedAttribute") if el.attrib.get("name") == "id")
    pk_annot = id_col.find("eAnnotations")
    assert pk_annot is not None
    pk_keys = [d.attrib.get("key") for d in pk_annot.findall("details")]
    assert "primaryKey" in pk_keys
    print("Column PK eAnnotation verified.")

    # Validate Use Case & Include / Extend
    login_uc = next(el for el in model.findall("ownedMember") if el.attrib.get("name") == "Login")
    assert login_uc.attrib.get(f"{{{XMI_NS}}}type") == "uml:UseCase"
    include_elem = login_uc.find("include")
    assert include_elem is not None
    assert include_elem.attrib.get(f"{{{XMI_NS}}}type") == "uml:Include"
    print("Use Case Include verified.")

    place_order_uc = next(el for el in model.findall("ownedMember") if el.attrib.get("name") == "PlaceOrder")
    extend_elem = place_order_uc.find("extend")
    assert extend_elem is not None
    assert extend_elem.attrib.get(f"{{{XMI_NS}}}type") == "uml:Extend"
    print("Use Case Extend verified.")

    # Validate State Machine
    sm_elem = next(el for el in model.findall("ownedMember") if el.attrib.get(f"{{{XMI_NS}}}type") == "uml:StateMachine")
    region_elem = sm_elem.find("region")
    assert region_elem is not None
    assert region_elem.attrib.get(f"{{{XMI_NS}}}type") == "uml:Region"

    subvertices = region_elem.findall("subvertex")
    assert len(subvertices) == 5
    init_state = next(v for v in subvertices if v.attrib.get("name") == "InitialState")
    assert init_state.attrib.get(f"{{{XMI_NS}}}type") == "uml:Pseudostate"
    assert init_state.attrib.get("kind") == "initial"
    final_state = next(v for v in subvertices if v.attrib.get("name") == "Completed")
    assert final_state.attrib.get(f"{{{XMI_NS}}}type") == "uml:FinalState"

    transitions = region_elem.findall("transition")
    assert len(transitions) == 4
    print("State Machine vertices and transitions verified.")

    # Validate that every model element, shape, and connector has an xmi:id attribute
    required_id_tags = (
        "ownedMember", "ownedAttribute", "ownedOperation", "generalization",
        "include", "extend", "subvertex", "transition", "Diagram", "DiagramElement"
    )
    for elem in root.iter():
        clean_tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if clean_tag in required_id_tags:
            assert f"{{{XMI_NS}}}id" in elem.attrib or "xmi:id" in elem.attrib, f"Element {elem.tag} missing xmi:id! Attribs: {elem.attrib}"

    print("\n>>> ALL VALIDATION CHECKS PASSED PERFECTLY! <<<")

if __name__ == "__main__":
    run_tests()
