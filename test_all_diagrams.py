"""Comprehensive end-to-end verification of all 4 diagram types and XMI export."""

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
    get_project_summary,
    init_project,
)
from core.state import state

def run_tests():
    print("=== 1. Initialize Project ===")
    print(init_project("EnterpriseSystem"))
    assert state.name == "EnterpriseSystem"

    print("\n=== 2. UML Class Diagram Setup ===")
    print(add_class("BaseEntity"))
    print(add_class_attribute("BaseEntity", "id", "UUID", "public"))
    print(add_class_attribute("BaseEntity", "createdAt", "DateTime", "protected"))

    print(add_class("User"))
    print(add_class_attribute("User", "email", "string", "private"))
    print(add_class_attribute("User", "passwordHash", "string", "private"))
    print(add_class_method("User", "authenticate", "bool", [{"name": "password", "type": "string", "direction": "in"}]))

    print(add_class("Customer"))
    print(add_class_attribute("Customer", "loyaltyPoints", "int", "public"))

    print(add_class("Order"))
    print(add_class_attribute("Order", "total", "float", "public"))
    print(add_class_method("Order", "recalculate", "void", []))

    print(add_class("OrderItem"))
    print(add_class_attribute("OrderItem", "quantity", "int", "public"))

    print(add_class("IPaymentGateway"))
    print(add_class_method("IPaymentGateway", "charge", "bool", [{"name": "amount", "type": "float"}]))

    print(add_class("StripePaymentGateway"))

    # Relations
    print(add_class_relation("User", "BaseEntity", "Generalization"))
    print(add_class_relation("Customer", "User", "Generalization"))
    print(add_class_relation("Customer", "Order", "Aggregation"))
    print(add_class_relation("Order", "OrderItem", "Composition"))
    print(add_class_relation("Order", "IPaymentGateway", "Dependency"))
    print(add_class_relation("StripePaymentGateway", "IPaymentGateway", "Realization"))

    print("\n=== 3. ER Diagram Setup ===")
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

    print("Root tag:", root.tag)
    assert root.tag == f"{{{XMI_NS}}}XMI"
    assert root.attrib.get(f"{{{XMI_NS}}}version") == "2.1"

    model = root.find(f"{{{UML_NS}}}Model")
    assert model is not None, "uml:Model not found!"
    assert model.attrib.get(f"{{{XMI_NS}}}id") == "model_1"
    assert model.attrib.get("name") == "EnterpriseSystem"

    # Validate Class Diagram
    user_elem = next(el for el in model.findall("ownedMember") if el.attrib.get("name") == "User")
    assert user_elem.attrib.get(f"{{{XMI_NS}}}type") == "uml:Class"
    user_gen = user_elem.find("generalization")
    assert user_gen is not None
    assert user_gen.attrib.get(f"{{{XMI_NS}}}type") == "uml:Generalization"
    print("Class Generalization verified inside User.")

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
