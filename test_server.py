"""End-to-end test script for mcp-visual-paradigm tools and XMI generation."""

import os
import xml.etree.ElementTree as ET
from server import (
    add_attribute,
    add_class,
    add_method,
    add_relationship,
    export_xmi,
    get_diagram_summary,
    init_diagram,
    state,
)

def run_tests():
    print("=== 1. Testing init_diagram ===")
    res = init_diagram("ECommerceArchitecture")
    print(res)
    assert state.name == "ECommerceArchitecture"
    assert len(state.classes) == 0

    print("\n=== 2. Testing add_class ===")
    res_user = add_class("User")
    print(res_user)
    res_customer = add_class("Customer")
    print(res_customer)
    res_order = add_class("Order")
    print(res_order)
    res_item = add_class("OrderItem")
    print(res_item)
    res_service = add_class("PaymentService")
    print(res_service)
    assert len(state.classes) == 5

    print("\n=== 3. Testing add_attribute ===")
    print(add_attribute("User", "id", "UUID", "public"))
    print(add_attribute("User", "email", "string", "private"))
    print(add_attribute("User", "passwordHash", "string", "private"))
    print(add_attribute("Customer", "shippingAddress", "string", "public"))
    print(add_attribute("Order", "totalAmount", "float", "public"))
    print(add_attribute("Order", "status", "string", "public"))
    print(add_attribute("OrderItem", "quantity", "int", "public"))
    print(add_attribute("OrderItem", "unitPrice", "float", "public"))

    print("\n=== 4. Testing add_method ===")
    print(add_method(
        "User",
        "verifyPassword",
        "bool",
        [{"name": "rawPassword", "type": "string"}]
    ))
    print(add_method(
        "Order",
        "calculateTotal",
        "float",
        []
    ))
    print(add_method(
        "Order",
        "addItem",
        "void",
        [{"name": "item", "type": "OrderItem"}, {"name": "qty", "type": "int"}]
    ))
    print(add_method(
        "PaymentService",
        "processPayment",
        "bool",
        [{"name": "order", "type": "Order"}, {"name": "amount", "type": "float"}]
    ))

    print("\n=== 5. Testing add_relationship ===")
    # Generalization: Customer is-a User
    print(add_relationship("Customer", "User", "Generalization"))
    # Composition: Order is composed of OrderItems (1 -> 1..*)
    print(add_relationship("Order", "OrderItem", "Composition", "1", "1..*"))
    # Aggregation: Customer has Orders (1 -> 0..*)
    print(add_relationship("Customer", "Order", "Aggregation", "1", "0..*"))
    # Association: User to Order (1 -> *)
    print(add_relationship("User", "Order", "Association", "1", "*"))
    # Dependency: Order depends on PaymentService
    print(add_relationship("Order", "PaymentService", "Dependency"))

    print("\n=== 6. Diagram Summary ===")
    summary = get_diagram_summary()
    print(summary)

    print("\n=== 7. Testing export_xmi ===")
    test_file = os.path.join(os.path.dirname(__file__), "test_model.xmi")
    export_res = export_xmi(test_file)
    print(export_res)

    print("\n=== 8. Validating Generated XMI XML ===")
    assert os.path.exists(test_file), "XMI file was not created!"
    tree = ET.parse(test_file)
    root = tree.getroot()

    XMI_NS = "http://schema.omg.org/spec/XMI/2.1"
    UML_NS = "http://schema.omg.org/spec/UML/2.0"

    print("Root tag:", root.tag)
    assert root.tag == f"{{{XMI_NS}}}XMI"
    assert root.attrib.get(f"{{{XMI_NS}}}version") == "2.1"

    model = root.find(f"{{{UML_NS}}}Model")
    assert model is not None, "uml:Model element not found!"
    assert model.attrib.get("name") == "ECommerceArchitecture"
    assert f"{{{XMI_NS}}}id" in model.attrib

    classes = [el for el in model.findall("ownedMember") if el.attrib.get(f"{{{XMI_NS}}}type") == "uml:Class"]
    print(f"Found {len(classes)} classes in XMI")
    assert len(classes) == 5

    customer_elem = next(c for c in classes if c.attrib.get("name") == "Customer")
    gen_elem = customer_elem.find("generalization")
    assert gen_elem is not None, "Customer should have generalization tag"
    print("Generalization found in Customer pointing to:", gen_elem.attrib.get("general"))

    associations = [el for el in model.findall("ownedMember") if el.attrib.get(f"{{{XMI_NS}}}type") == "uml:Association"]
    print(f"Found {len(associations)} associations in XMI")
    assert len(associations) == 3  # Composition, Aggregation, Association

    dependencies = [el for el in model.findall("ownedMember") if el.attrib.get(f"{{{XMI_NS}}}type") == "uml:Dependency"]
    print(f"Found {len(dependencies)} dependencies in XMI")
    assert len(dependencies) == 1

    primitives = [el for el in model.findall("ownedMember") if el.attrib.get(f"{{{XMI_NS}}}type") == "uml:DataType"]
    print(f"Found {len(primitives)} primitive/data types registered in XMI")

    # Verify that UML model and diagram elements have an xmi:id attribute
    required_id_tags = (
        "ownedMember", "ownedAttribute", "ownedOperation", "generalization",
        "ownedParameter", "lowerValue", "upperValue", "Diagram", "DiagramElement"
    )
    for elem in root.iter():
        clean_tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if clean_tag in required_id_tags:
            assert f"{{{XMI_NS}}}id" in elem.attrib, f"Element {elem.tag} missing xmi:id! Attribs: {elem.attrib}"

    print("\n>>> ALL TESTS PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    run_tests()
