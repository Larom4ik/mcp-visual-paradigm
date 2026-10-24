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
    add_note,
    add_package,
    add_state,
    add_state_transition,
    add_uc_relation,
    add_use_case,
    export_xmi,
    get_project_summary,
    init_project,
    move_class_to_package,
    set_system_boundary,
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
    print(add_class("BaseEntity", package="CoreDomain", description="Root entity with UUID identifier and audit timestamps."))
    print(add_class_attribute("BaseEntity", "id", "UUID", "public", description="Primary unique identifier"))
    print(add_class_attribute("BaseEntity", "createdAt", "DateTime", "protected"))

    print(add_class("User", package="CoreDomain", description="Represents a registered user in the enterprise application."))
    print(add_class_attribute("User", "email", "string", "private"))
    print(add_class_attribute("User", "passwordHash", "string", "private"))
    print(add_class_method("User", "authenticate", "bool", [{"name": "password", "type": "string", "direction": "in"}], description="Verify credentials and generate JWT token."))

    print(add_class("Customer", package="CoreDomain"))
    print(add_class_attribute("Customer", "loyaltyPoints", "int", "public"))

    print(add_class("Order", package="Ordering", description="Customer commercial order with financial totals."))
    print(add_class_attribute("Order", "total", "float", "public"))
    print(add_class_method("Order", "recalculate", "void", []))

    print(add_class("OrderItem", package="Ordering"))
    print(add_class_attribute("OrderItem", "quantity", "int", "public"))

    print(add_class("IPaymentGateway", element_type="Interface", package="PaymentSubsystem", description="Contract for processing third-party financial charges."))
    print(add_class_method("IPaymentGateway", "charge", "bool", [{"name": "amount", "type": "float"}]))

    print(add_class("StripePaymentGateway", package="PaymentSubsystem"))

    # Add architectural note connected to Order
    print(add_note("Order state transitions must be strictly audited and idempotent.", target="Order"))

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
    print(add_er_entity("users", description="Stores core authentication and user profile data."))
    print(add_er_column("users", "id", "BIGINT", is_pk=True))
    print(add_er_column("users", "email", "VARCHAR(255)", is_unique=True, is_nullable=False, description="Unique user login email address."))
    print(add_er_column("users", "is_active", "BOOL", is_nullable=False))
    print(add_er_column("users", "created_at", "TIMESTAMP"))

    print(add_er_entity("user_profiles"))
    print(add_er_column("user_profiles", "id", "BIGINT", is_pk=True))
    print(add_er_column("user_profiles", "user_id", "BIGINT", is_fk=True, is_unique=True, is_nullable=False))
    print(add_er_column("user_profiles", "birth_date", "DATE"))
    print(add_er_column("user_profiles", "avatar_url", "TEXT"))

    print(add_er_entity("orders"))
    print(add_er_column("orders", "id", "BIGINT", is_pk=True))
    print(add_er_column("orders", "user_id", "BIGINT", is_fk=True, is_nullable=False))
    print(add_er_column("orders", "total_amount", "NUMERIC(10, 2)", is_nullable=False))
    print(add_er_column("orders", "discount_pct", "FLOAT"))
    print(add_er_column("orders", "status", "VARCHAR(50)"))

    print(add_er_entity("tags"))
    print(add_er_column("tags", "id", "BIGINT", is_pk=True))
    print(add_er_column("tags", "name", "VARCHAR(50)", is_unique=True, is_nullable=False))

    # ER Relations
    print(add_er_relation("users", "user_profiles", "1:1"))
    print(add_er_relation("users", "orders", "1:N"))
    print(add_er_relation("orders", "tags", "M:N"))

    print("\n=== 6. Use Case Diagram Setup with System Boundary ===")
    print(add_actor("CustomerActor", description="Registered end-user purchasing goods."))
    print(add_actor("AdminActor"))

    print(add_use_case("Login", description="Authenticate customer with email and password."))
    print(add_use_case("TwoFactorAuth", description="Verify second factor via SMS or authenticator app."))
    print(add_use_case("PlaceOrder"))
    print(add_use_case("ApplyDiscountCoupon"))

    # System Boundary enclosing use cases
    print(set_system_boundary("E-Commerce Platform", "Login,TwoFactorAuth,PlaceOrder,ApplyDiscountCoupon"))

    # UC Relations
    print(add_uc_relation("CustomerActor", "PlaceOrder", "Association"))
    print(add_uc_relation("CustomerActor", "Login", "Association"))
    print(add_uc_relation("Login", "TwoFactorAuth", "Include"))
    print(add_uc_relation("PlaceOrder", "ApplyDiscountCoupon", "Extend"))

    print("\n=== 7. State Machine Diagram Setup with Guards & Behaviors ===")
    print(add_state("InitialState", "Initial"))
    print(add_state("Draft", "State", entry="init_draft()", exit="validate_items()", description="Order is being edited."))
    print(add_state("Paid", "State", entry="send_receipt()", do="reserve_inventory()", description="Funds captured successfully."))
    print(add_state("Shipped", "State", do="track_carrier()", description="Package is in transit with carrier."))
    print(add_state("Completed", "Final"))

    # Transitions with event triggers and guard conditions
    print(add_state_transition("InitialState", "Draft", "create"))
    print(add_state_transition("Draft", "Paid", "paySuccess", guard="balance >= total"))
    print(add_state_transition("Paid", "Shipped", "dispatchOrder", guard="inStock == true"))
    print(add_state_transition("Shipped", "Completed", "deliveredConfirmation"))

    print("\n=== 8. Project Summary ===")
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
    assert users_table.attrib.get(f"{{{XMI_NS}}}type") == "uml:dbTable", "ER table element must have xmi:type='uml:dbTable'"
    table_annot = users_table.find("eAnnotations")
    assert table_annot is not None
    assert table_annot.attrib.get("source") == "Stereotype"
    details = table_annot.find("details")
    assert details is not None and details.attrib.get("key") == "entity"
    users_ext = users_table.find(f"{{{XMI_NS}}}Extension")
    assert users_ext is not None
    assert users_ext.find("modelType").attrib.get("value") == "DBTable", "ER table modelType must be DBTable"
    assert users_ext.find("documentation").attrib.get("value") == "Stores core authentication and user profile data."
    users_comment = users_table.find("ownedComment")
    assert users_comment is not None and users_comment.attrib.get("body") == "Stores core authentication and user profile data."

    # Validate native Visual Paradigm <childrens> and <dbColumn> elements
    childrens = users_table.find("childrens")
    assert childrens is not None, "ER table must have <childrens> container for VP DBColumn importer"
    db_cols = childrens.findall("dbColumn")
    assert len(db_cols) == 4, f"Expected 4 dbColumn elements in users table, got {len(db_cols)}"
    id_db_col = next(c for c in db_cols if c.attrib.get("name") == "id")
    assert id_db_col.attrib.get("primaryKey") == "true"
    assert id_db_col.attrib.get("type") == "9"
    assert id_db_col.attrib.get("typeName") in ("bigint", "int8")
    assert id_db_col.attrib.get("idGenerator") == "native"

    email_db_col = next(c for c in db_cols if c.attrib.get("name") == "email")
    assert email_db_col.attrib.get("unique") == "true", "email must have unique='true'"
    assert email_db_col.attrib.get("nullable") == "false", "email must have nullable='false'"
    assert email_db_col.attrib.get("type") == "27"
    assert email_db_col.attrib.get("typeName") == "varchar"

    active_db_col = next(c for c in db_cols if c.attrib.get("name") == "is_active")
    assert active_db_col.attrib.get("type") == "3", "BOOL must map to type='3'"
    assert active_db_col.attrib.get("typeName") in ("bool", "bit")
    assert active_db_col.attrib.get("nullable") == "false"

    created_db_col = next(c for c in db_cols if c.attrib.get("name") == "created_at")
    assert created_db_col.attrib.get("type") == "17"
    assert created_db_col.attrib.get("typeName") == "timestamp"

    # Validate orders table: NUMERIC, FLOAT, FK constraints
    orders_table = next(el for el in model.findall("ownedMember") if el.attrib.get("name") == "orders")
    orders_cols = orders_table.find("childrens").findall("dbColumn")
    user_id_col = next(c for c in orders_cols if c.attrib.get("name") == "user_id")
    assert user_id_col.attrib.get("foreignKey") == "true", "orders.user_id must be marked foreignKey='true'"
    assert user_id_col.attrib.get("foreignKeyConstraints"), "orders.user_id must have foreignKeyConstraints"

    total_col = next(c for c in orders_cols if c.attrib.get("name") == "total_amount")
    assert total_col.attrib.get("type") == "11", "NUMERIC must map to type='11'"
    assert total_col.attrib.get("typeName") == "numeric"
    assert total_col.attrib.get("nullable") == "false"

    discount_col = next(c for c in orders_cols if c.attrib.get("name") == "discount_pct")
    assert discount_col.attrib.get("type") == "12", "FLOAT must map to type='12'"
    assert discount_col.attrib.get("typeName") in ("float", "float4")

    # Validate user_profiles table: DATE type
    profiles_table = next(el for el in model.findall("ownedMember") if el.attrib.get("name") == "user_profiles")
    profiles_cols = profiles_table.find("childrens").findall("dbColumn")
    date_col = next(c for c in profiles_cols if c.attrib.get("name") == "birth_date")
    assert date_col.attrib.get("type") == "15", "DATE must map to type='15'"
    assert date_col.attrib.get("typeName") == "date"
    print("ER Entity native types (bigint, varchar, bool, timestamp, numeric, float, date) and unique/fk verified.")

    # Validate ER Foreign Keys (uml:dbForeignKey)
    er_fks = [el for el in model.findall("ownedMember") if el.attrib.get(f"{{{XMI_NS}}}type") == "uml:dbForeignKey"]
    assert len(er_fks) == 3, f"Expected 3 uml:dbForeignKey elements, got {len(er_fks)}"
    for fk in er_fks:
        assert fk.attrib.get("from"), "dbForeignKey must specify 'from' table"
        assert fk.attrib.get("to"), "dbForeignKey must specify 'to' table"
        assert fk.attrib.get("fromMultiplicity") is not None
        assert fk.attrib.get("toMultiplicity") is not None
        assert fk.find("from") is not None and f"{{{XMI_NS}}}idref" in fk.find("from").attrib
        assert fk.find("to") is not None and f"{{{XMI_NS}}}idref" in fk.find("to").attrib
    print("ER Foreign Key metamodel (uml:dbForeignKey with from/to and multiplicities) verified.")

    # Validate PK / FK annotations and column documentation
    id_col = next(el for el in users_table.findall("ownedAttribute") if el.attrib.get("name") == "id")
    pk_annot = id_col.find("eAnnotations")
    assert pk_annot is not None
    pk_keys = [d.attrib.get("key") for d in pk_annot.findall("details")]
    assert "primaryKey" in pk_keys
    email_col = next(el for el in users_table.findall("ownedAttribute") if el.attrib.get("name") == "email")
    email_ext = email_col.find(f"{{{XMI_NS}}}Extension")
    assert email_ext is not None and email_ext.find("documentation").attrib.get("value") == "Unique user login email address."
    email_annot = email_col.find("eAnnotations")
    email_keys = [d.attrib.get("key") for d in email_annot.findall("details")]
    assert "unique" in email_keys, "email ownedAttribute must have 'unique' eAnnotation"
    print("Column PK and UNIQUE eAnnotation and documentation verified.")

    # Validate Use Case & Include / Extend (Capitalized Stereotypes)
    login_uc = next(el for el in model.findall("ownedMember") if el.attrib.get("name") == "Login")
    assert login_uc.attrib.get(f"{{{XMI_NS}}}type") == "uml:UseCase"
    login_ext = login_uc.find(f"{{{XMI_NS}}}Extension")
    assert login_ext is not None and login_ext.find("documentation").attrib.get("value") == "Authenticate customer with email and password."
    include_elem = login_uc.find("include")
    assert include_elem is not None
    assert include_elem.attrib.get(f"{{{XMI_NS}}}type") == "uml:Include"
    assert include_elem.attrib.get("name") == "«Include»", f"Expected «Include», got {include_elem.attrib.get('name')}"
    print("Use Case Include (capitalized «Include») and documentation verified.")

    place_order_uc = next(el for el in model.findall("ownedMember") if el.attrib.get("name") == "PlaceOrder")
    extend_elem = place_order_uc.find("extend")
    assert extend_elem is not None
    assert extend_elem.attrib.get(f"{{{XMI_NS}}}type") == "uml:Extend"
    assert extend_elem.attrib.get("name") == "«Extend»", f"Expected «Extend», got {extend_elem.attrib.get('name')}"
    print("Use Case Extend (capitalized «Extend») verified.")

    # Validate State Machine & Internal Behaviors
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

    draft_vertex = next(v for v in subvertices if v.attrib.get("name") == "Draft")
    draft_entry = draft_vertex.find("entry")
    assert draft_entry is not None and draft_entry.attrib.get("name") == "init_draft()"
    draft_exit = draft_vertex.find("exit")
    assert draft_exit is not None and draft_exit.attrib.get("name") == "validate_items()"
    draft_ext = draft_vertex.find(f"{{{XMI_NS}}}Extension")
    assert draft_ext is not None and draft_ext.find("documentation").attrib.get("value") == "Order is being edited."

    paid_vertex = next(v for v in subvertices if v.attrib.get("name") == "Paid")
    paid_do = paid_vertex.find("doActivity")
    assert paid_do is not None and paid_do.attrib.get("name") == "reserve_inventory()"
    print("State Machine vertices, internal behaviors (entry, do, exit), and documentation verified.")

    transitions = region_elem.findall("transition")
    assert len(transitions) == 4
    # Check guard condition on transition
    guard_tr = next(t for t in transitions if t.find("guard") is not None)
    assert guard_tr is not None
    guard_node = guard_tr.find("guard")
    assert guard_node.attrib.get("name") == "balance >= total"
    print("State Machine transitions and guard conditions verified.")

    # Validate Universal Notes (uml:Comment) & Visual NOTE / Anchor
    owned_comments = model.findall("ownedComment")
    assert len(owned_comments) >= 1
    note_comment = owned_comments[0]
    assert "Order state transitions" in note_comment.attrib.get("body", "")
    print("Metamodel ownedComment (Note) verified.")

    # Check Visual NOTE shape and Anchor connector in ClassDiagram
    note_shapes = [el for el in diag_elems if el.attrib.get("preferredShapeType") == "NOTE"]
    assert len(note_shapes) >= 1
    anchor_conns = [el for el in diag_elems if el.attrib.get("preferredShapeType") == "Anchor"]
    assert len(anchor_conns) >= 1
    print("Visual NOTE shape and Anchor connector in Class Diagram verified.")

    # Check ER Diagram Visual Shapes (DBTable with Peach color, DBForeignKey with no multiplicity text)
    erd_diag = next(d for d in omg_diagrams if d.attrib.get("diagramType") == "ERDiagram")
    erd_props = erd_diag.find(f"{{{XMI_NS}}}Extension").find("properties")
    assert erd_props.find("a_showDBTableColumnsMode").attrib.get("value") == "1", "ERDiagram must have a_showDBTableColumnsMode='1'"
    assert erd_props.find("a_showColumnTypes").attrib.get("value") == "true", "ERDiagram must have a_showColumnTypes='true'"
    assert erd_props.find("a_columnConstraintsDisplayOption").attrib.get("value") == "2", "ERDiagram must have a_columnConstraintsDisplayOption='2'"

    erd_elems = erd_diag.find(f"{{{UML_NS}}}Diagram.element").findall(f"{{{UML_NS}}}DiagramElement")
    table_shapes = [el for el in erd_elems if el.attrib.get("preferredShapeType") == "DBTable"]
    assert len(table_shapes) == 4, f"Expected 4 DBTable shapes, got {len(table_shapes)}"
    for ts in table_shapes:
        ts_props = ts.find(f"{{{XMI_NS}}}Extension").find("properties")
        assert ts_props.find("abackground").attrib.get("value") == "Cr:245,182,122,255", "DBTable must be peach/orange"
        assert ts_props.find("ashowColumnsMode").attrib.get("value") == "0", "DBTable must have ashowColumnsMode='0'"
    erd_conns = [el for el in erd_elems if el.attrib.get("preferredShapeType") == "DBForeignKey"]
    assert len(erd_conns) == 3, f"Expected 3 DBForeignKey connectors, got {len(erd_conns)}"
    for ec in erd_conns:
        ec_props = ec.find(f"{{{XMI_NS}}}Extension").find("properties")
        assert ec_props.find("ashowConnectorName").attrib.get("value") == "0", "DBForeignKey must suppress name caption"
        assert ec_props.find("ashowFromMultiplicity").attrib.get("value") == "false", "DBForeignKey must suppress text multiplicity"
        assert ec_props.find("ashowToMultiplicity").attrib.get("value") == "false", "DBForeignKey must suppress text multiplicity"
        assert ec_props.find("afromPinType").attrib.get("value") == "1", "DBForeignKey must set afromPinType='1'"
        assert ec_props.find("atoPinType").attrib.get("value") == "1", "DBForeignKey must set atoPinType='1'"
    print("Visual ER Diagram native DBTable (peach color) and DBForeignKey (clean Crow's Foot) verified.")

    # Check vpumlChildModels under model Extension for ER data modeling
    model_elem = root.find(f"{{{UML_NS}}}Model")
    model_vp = model_elem.find(f"{{{XMI_NS}}}Extension")
    assert model_vp is not None, "Model must have Visual Paradigm Extension"
    vp_children = model_vp.find("vpumlChildModels")
    assert vp_children is not None, "Model Extension must contain vpumlChildModels"
    vp_tables = [m for m in vp_children.findall("vpumlModel") if m.attrib.get("modelType") == "DBTable"]
    assert len(vp_tables) == 4, f"Expected 4 vpumlModel DBTable elements, got {len(vp_tables)}"
    vp_fks = [m for m in vp_children.findall("vpumlModel") if m.attrib.get("modelType") == "DBForeignKey"]
    assert len(vp_fks) == 3, f"Expected 3 vpumlModel DBForeignKey elements, got {len(vp_fks)}"
    print("Native Visual Paradigm ER metamodel (DBTable, DBColumn, DBForeignKey in vpumlChildModels) verified.")

    # Check Use Case Diagram System Boundary shape
    uc_diag = next(d for d in omg_diagrams if d.attrib.get("diagramType") == "UseCaseDiagram")
    uc_elems = uc_diag.find(f"{{{UML_NS}}}Diagram.element").findall(f"{{{UML_NS}}}DiagramElement")
    system_shapes = [el for el in uc_elems if el.attrib.get("preferredShapeType") == "System"]
    assert len(system_shapes) == 1
    print("Visual System Boundary shape in Use Case Diagram verified.")

    # Check State Machine Visual Shapes (State2, FinalState2, InitialPseudoState, Transition2)
    sm_diag = next(d for d in omg_diagrams if d.attrib.get("diagramType") == "StateDiagram")
    sm_elems = sm_diag.find(f"{{{UML_NS}}}Diagram.element").findall(f"{{{UML_NS}}}DiagramElement")
    sm_state2 = [el for el in sm_elems if el.attrib.get("preferredShapeType") == "State2"]
    assert len(sm_state2) == 3, f"Expected 3 State2 shapes, got {len(sm_state2)}"
    for s2 in sm_state2:
        s2_ext = s2.find(f"{{{XMI_NS}}}Extension")
        s2_props = s2_ext.find("properties")
        assert s2_props.find("ashowActionActivities").attrib.get("value") == "true", "State2 must display action activities"
        assert s2_ext.find("captionSide").attrib.get("value") == "1", "State2 captionSide must be 1 (header compartment anchor)"
        assert s2_ext.find("captionBounds").attrib.get("value").endswith(",15"), "State2 captionBounds height must be 15 (header tab)"

    sm_final = [el for el in sm_elems if el.attrib.get("preferredShapeType") == "FinalState2"]
    assert len(sm_final) == 1, f"Expected 1 FinalState2 shape, got {len(sm_final)}"
    final_ext = sm_final[0].find(f"{{{XMI_NS}}}Extension")
    assert final_ext.find("captionVisible").attrib.get("value") == "false", "FinalState2 caption must be hidden"
    final_props = final_ext.find("properties")
    assert final_props.find("abackground").attrib.get("value") == "Cr:0,0,0,255", "FinalState2 must be solid black"

    sm_init = [el for el in sm_elems if el.attrib.get("preferredShapeType") == "InitialPseudoState"]
    assert len(sm_init) == 1, f"Expected 1 InitialPseudoState shape, got {len(sm_init)}"
    init_ext = sm_init[0].find(f"{{{XMI_NS}}}Extension")
    assert init_ext.find("captionVisible").attrib.get("value") == "false", "InitialPseudoState caption must be hidden"
    init_props = init_ext.find("properties")
    assert init_props.find("abackground").attrib.get("value") == "Cr:0,0,0,255", "InitialPseudoState must be solid black"

    sm_trans = [el for el in sm_elems if el.attrib.get("preferredShapeType") == "Transition2"]
    assert len(sm_trans) == 4, f"Expected 4 Transition2 connectors, got {len(sm_trans)}"
    print("Visual State Machine shapes (State2 with activities in header, solid black Initial/Final, Transition2) verified.")

    # Check that auto-generated role names are suppressed on connectors
    all_connectors = [
        el for d in omg_diagrams for el in d.find(f"{{{UML_NS}}}Diagram.element").findall(f"{{{UML_NS}}}DiagramElement")
        if el.attrib.get("fromDiagramElement") and el.attrib.get("toDiagramElement")
    ]
    for conn in all_connectors:
        ext = conn.find(f"{{{XMI_NS}}}Extension")
        if ext is not None:
            props = ext.find("properties")
            if props is not None:
                from_role = props.find("ashowFromRoleName")
                to_role = props.find("ashowToRoleName")
                if from_role is not None:
                    assert from_role.attrib.get("value") == "false", "Connector must suppress ashowFromRoleName"
                if to_role is not None:
                    assert to_role.attrib.get("value") == "false", "Connector must suppress ashowToRoleName"
    print("Connector role name clutter suppression verified (ashowFromRoleName='false').")

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
