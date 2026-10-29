"""Comprehensive automated tests for Activity and Deployment diagrams in mcp-visual-paradigm."""

import os
import xml.etree.ElementTree as ET
from core.state import state
from mcp_tools.tools import (
    init_project,
    add_activity_partition,
    add_activity_node,
    add_control_flow,
    add_deployment_node,
    add_artifact,
    add_communication_path,
    add_deployment_link,
    build_activity_diagram,
    build_deployment_diagram,
    batch_build_diagrams,
    get_project_summary,
    export_xmi,
)


def test_granular_tools():
    print("[TEST 1] Testing granular Activity & Deployment tools...")
    init_project("TestGranularProject")

    # Activity diagram elements
    res = add_activity_partition("Customer")
    assert "Created Activity Partition" in res, f"Partition failed: {res}"

    res = add_activity_node("Start", type="Initial", partition="Customer")
    assert "Created Activity [Initial]" in res, f"Initial node failed: {res}"

    res = add_activity_node("Place Order", type="Action", partition="Customer")
    assert "Created Activity [Action]" in res, f"Action node failed: {res}"

    res = add_activity_node("Payment Decision", type="Decision")
    assert "Created Activity [Decision]" in res, f"Decision node failed: {res}"

    res = add_control_flow("Start", "Place Order")
    assert "Created ControlFlow" in res, f"Flow failed: {res}"

    res = add_control_flow("Place Order", "Payment Decision", guard="[items valid]")
    assert "Created ControlFlow" in res and "guard: [items valid]" in res, f"Flow with guard failed: {res}"

    # Deployment diagram elements
    res = add_deployment_node("Client PC", node_type="Device")
    assert "Created Deployment [Device]" in res, f"Device node failed: {res}"

    res = add_deployment_node("App Server", node_type="Node")
    assert "Created Deployment [Node]" in res, f"Node failed: {res}"

    res = add_deployment_node("Docker Container", node_type="ExecutionEnvironment", parent_node="App Server")
    assert "Created Deployment [ExecutionEnvironment]" in res, f"Nested EE failed: {res}"

    res = add_artifact("web-app.jar", deployed_on_node="Docker Container")
    assert "Created Artifact" in res, f"Artifact failed: {res}"

    res = add_communication_path("Client PC", "App Server", protocol="HTTPS (Port 443)")
    assert "Created CommunicationPath" in res, f"Comm path failed: {res}"

    res = add_deployment_link("web-app.jar", "Docker Container")
    assert "Created Deployment" in res, f"Deployment link failed: {res}"

    # Project summary
    summary = get_project_summary()
    assert "Activity Diagram" in summary, "Summary missing Activity Diagram"
    assert "Deployment Diagram" in summary, "Summary missing Deployment Diagram"
    assert "web-app.jar" in summary, "Summary missing artifact"
    assert "HTTPS (Port 443)" in summary, "Summary missing protocol"

    print(" -> Granular tools passed!")


def test_activity_builder():
    print("[TEST 2] Testing build_activity_diagram...")
    spec = {
        "project_name": "ECommerceActivity",
        "activity_partitions": [
            {"name": "Shopper"},
            {"name": "OrderService"},
            {"name": "PaymentGateway"},
        ],
        "activity_nodes": [
            {"name": "StartCheckout", "type": "Initial", "partition": "Shopper"},
            {"name": "FillCart", "type": "Action", "partition": "Shopper"},
            {"name": "VerifyStock", "type": "Action", "partition": "OrderService"},
            {"name": "CheckStockDecision", "type": "Decision", "partition": "OrderService"},
            {"name": "ProcessPayment", "type": "Action", "partition": "PaymentGateway"},
            {"name": "NotifyOutOfStock", "type": "Action", "partition": "OrderService"},
            {"name": "ForkDelivery", "type": "Fork", "partition": "OrderService"},
            {"name": "SendReceipt", "type": "Action", "partition": "OrderService"},
            {"name": "ShipPackage", "type": "Action", "partition": "OrderService"},
            {"name": "JoinDelivery", "type": "Join", "partition": "OrderService"},
            {"name": "CheckoutFinal", "type": "Final", "partition": "Shopper"},
        ],
        "control_flows": [
            {"source": "StartCheckout", "target": "FillCart"},
            {"source": "FillCart", "target": "VerifyStock"},
            {"source": "VerifyStock", "target": "CheckStockDecision"},
            {"source": "CheckStockDecision", "target": "ProcessPayment", "guard": "[in stock]"},
            {"source": "CheckStockDecision", "target": "NotifyOutOfStock", "guard": "[out of stock]"},
            {"source": "ProcessPayment", "target": "ForkDelivery"},
            {"source": "ForkDelivery", "target": "SendReceipt"},
            {"source": "ForkDelivery", "target": "ShipPackage"},
            {"source": "SendReceipt", "target": "JoinDelivery"},
            {"source": "ShipPackage", "target": "JoinDelivery"},
            {"source": "JoinDelivery", "target": "CheckoutFinal"},
        ],
    }

    out_file = "test_activity_out.xmi"
    res = build_activity_diagram(spec, append=False, filepath=out_file)
    assert "SUCCESS" in res or "exported" in res.lower(), f"Build failed: {res}"
    assert os.path.exists(out_file), "Output file does not exist"

    # Parse and validate XMI
    tree = ET.parse(out_file)
    root = tree.getroot()

    # Verify Activity metamodel
    activities = root.findall(".//ownedMember[@xmi:type='uml:Activity']", namespaces={"xmi": "http://schema.omg.org/spec/XMI/2.1"})
    assert len(activities) >= 1, "No uml:Activity ownedMember found"
    act = activities[0]

    # Verify nodes
    nodes = act.findall("node")
    assert len(nodes) >= 10, f"Expected >=10 nodes in Activity, got {len(nodes)}"

    # Verify partitions / groups
    groups = act.findall("group")
    assert len(groups) == 3, f"Expected 3 groups/swimlanes, got {len(groups)}"

    # Verify visual diagram
    vp_diagrams = [e for e in root.iter() if e.tag.endswith("Diagram") and e.attrib.get("diagramType") == "ActivityDiagram"]
    assert len(vp_diagrams) >= 1, "No ActivityDiagram visual layer found"
    diag = vp_diagrams[0]
    elements = [e for e in diag.iter() if e.tag.endswith("DiagramElement")]
    assert len(elements) >= 10, f"Expected >=10 visual elements in ActivityDiagram, got {len(elements)}"

    print(f" -> build_activity_diagram passed! Found {len(nodes)} nodes, {len(groups)} swimlanes, {len(elements)} visual elements.")


def test_deployment_builder():
    print("[TEST 3] Testing build_deployment_diagram...")
    spec = {
        "project_name": "CloudDeployment",
        "deployment_nodes": [
            {"name": "Client Workstation", "type": "Device"},
            {"name": "API Gateway", "type": "ExecutionEnvironment"},
            {"name": "Backend Application Server", "type": "Node"},
            {"name": "Primary Database Server", "type": "Node"},
        ],
        "artifacts": [
            {"name": "web_portal_bundle.js", "deployed_on": "Client Workstation"},
            {"name": "gateway_proxy.conf", "deployed_on": "API Gateway"},
            {"name": "backend_app.jar", "deployed_on": "Backend Application Server"},
            {"name": "enterprise_db.sql", "deployed_on": "Primary Database Server"},
        ],
        "communication_paths": [
            {"source": "Client Workstation", "target": "API Gateway", "protocol": "HTTPS (Port 443)"},
            {"source": "API Gateway", "target": "Backend Application Server", "protocol": "gRPC (Port 50051)"},
            {"source": "Backend Application Server", "target": "Primary Database Server", "protocol": "TCP/IP (Port 5432)"},
        ],
        "deployment_links": [
            {"artifact": "backend_app.jar", "node": "Backend Application Server"},
        ]
    }

    out_file = "test_deployment_out.xmi"
    res = build_deployment_diagram(spec, append=False, filepath=out_file)
    assert "SUCCESS" in res or "exported" in res.lower(), f"Build failed: {res}"
    assert os.path.exists(out_file), "Output file does not exist"

    # Parse and validate XMI
    tree = ET.parse(out_file)
    root = tree.getroot()

    # Verify Deployment elements in metamodel
    dep_nodes = root.findall(".//ownedMember[@xmi:type='uml:Node']", namespaces={"xmi": "http://schema.omg.org/spec/XMI/2.1"})
    devices = root.findall(".//ownedMember[@xmi:type='uml:Device']", namespaces={"xmi": "http://schema.omg.org/spec/XMI/2.1"})
    ee_nodes = root.findall(".//ownedMember[@xmi:type='uml:ExecutionEnvironment']", namespaces={"xmi": "http://schema.omg.org/spec/XMI/2.1"})
    artifacts = root.findall(".//ownedMember[@xmi:type='uml:Artifact']", namespaces={"xmi": "http://schema.omg.org/spec/XMI/2.1"})

    assert len(dep_nodes) == 2, f"Expected 2 Nodes, got {len(dep_nodes)}"
    assert len(devices) == 1, f"Expected 1 Device, got {len(devices)}"
    assert len(ee_nodes) == 1, f"Expected 1 ExecutionEnvironment, got {len(ee_nodes)}"
    assert len(artifacts) == 4, f"Expected 4 Artifacts, got {len(artifacts)}"

    # Verify visual diagram
    vp_diagrams = [e for e in root.iter() if e.tag.endswith("Diagram") and e.attrib.get("diagramType") == "DeploymentDiagram"]
    assert len(vp_diagrams) >= 1, "No DeploymentDiagram visual layer found"
    diag = vp_diagrams[0]
    elements = [e for e in diag.iter() if e.tag.endswith("DiagramElement")]

    assert len(elements) >= 7, f"Expected >=7 visual elements, got {len(elements)}"

    print(f" -> build_deployment_diagram passed! Found {len(dep_nodes) + len(devices) + len(ee_nodes)} nodes, {len(artifacts)} artifacts, {len(elements)} visual elements.")


def test_batch_build_all_six_diagrams():
    print("[TEST 4] Testing batch_build_diagrams with all 6 diagram types...")
    spec = {
        "project_name": "FullArchitectureSuite",
        # 1. Class
        "packages": [{"name": "CoreDomain"}],
        "classes": [
            {
                "name": "Order",
                "package": "CoreDomain",
                "attributes": [{"name": "id", "type": "UUID"}, {"name": "total", "type": "Decimal"}],
                "methods": [{"name": "calculateTotal", "params": [], "return_type": "Decimal"}],
            },
            {
                "name": "OrderItem",
                "package": "CoreDomain",
                "attributes": [{"name": "quantity", "type": "int"}, {"name": "price", "type": "Decimal"}],
            }
        ],
        "class_relations": [
            {"source": "Order", "target": "OrderItem", "type": "Composition", "source_multiplicity": "1", "target_multiplicity": "1..*"}
        ],
        # 2. ERD
        "entities": [
            {
                "name": "orders",
                "columns": [
                    {"name": "id", "type": "UUID", "is_pk": True},
                    {"name": "status", "type": "VARCHAR", "length": 50, "is_nullable": False},
                ]
            },
            {
                "name": "order_items",
                "columns": [
                    {"name": "id", "type": "UUID", "is_pk": True},
                    {"name": "order_id", "type": "UUID", "is_fk": True, "is_nullable": False},
                ]
            }
        ],
        "er_relations": [
            {"source": "order_items", "target": "orders", "type": "N:1"}
        ],
        # 3. Use Case
        "actors": [{"name": "Customer"}, {"name": "Admin"}],
        "use_cases": [{"name": "Checkout"}, {"name": "ViewAuditLog"}],
        "system_boundary": {"name": "StorePlatform", "use_cases": ["Checkout", "ViewAuditLog"]},
        "uc_relations": [
            {"source": "Customer", "target": "Checkout", "type": "Association"},
            {"source": "Admin", "target": "ViewAuditLog", "type": "Association"}
        ],
        # 4. State Machine
        "states": [
            {"name": "InitState", "type": "Initial"},
            {"name": "Pending", "type": "State", "entry": "log()"},
            {"name": "Completed", "type": "Final"},
        ],
        "transitions": [
            {"source": "InitState", "target": "Pending"},
            {"source": "Pending", "target": "Completed", "trigger": "pay()", "guard": "ok"},
        ],
        # 5. Activity
        "activity_partitions": [{"name": "Operations"}],
        "activity_nodes": [
            {"name": "StartOp", "type": "Initial", "partition": "Operations"},
            {"name": "ExecuteTask", "type": "Action", "partition": "Operations"},
            {"name": "EndOp", "type": "Final", "partition": "Operations"},
        ],
        "control_flows": [
            {"source": "StartOp", "target": "ExecuteTask"},
            {"source": "ExecuteTask", "target": "EndOp"},
        ],
        # 6. Deployment
        "deployment_nodes": [
            {"name": "EdgeServer", "type": "Node"},
            {"name": "DatabaseCluster", "type": "Node"},
        ],
        "artifacts": [
            {"name": "service.bin", "deployed_on": "EdgeServer"},
        ],
        "communication_paths": [
            {"source": "EdgeServer", "target": "DatabaseCluster", "protocol": "PostgreSQL (5432)"},
        ],
    }

    out_file = "test_full_suite_out.xmi"
    res = batch_build_diagrams(spec, append=False, filepath=out_file)
    assert "SUCCESS" in res or "exported" in res.lower(), f"Batch build failed: {res}"

    tree = ET.parse(out_file)
    root = tree.getroot()

    # Verify all 6 diagrams exist in visual extensions
    expected_diagram_types = [
        "ClassDiagram",
        "ERDiagram",
        "UseCaseDiagram",
        "StateDiagram",
        "ActivityDiagram",
        "DeploymentDiagram",
    ]

    for dt in expected_diagram_types:
        diag = [e for e in root.iter() if e.tag.endswith("Diagram") and e.attrib.get("diagramType") == dt]
        assert len(diag) >= 1, f"Missing diagram type {dt} in visual extension!"
        elements = [e for e in diag[0].iter() if e.tag.endswith("DiagramElement")]
        print(f"   [OK] Diagram {dt}: {len(elements)} visual elements rendered.")

    print(" -> All 6 diagrams successfully verified in batch build!")


if __name__ == "__main__":
    test_granular_tools()
    test_activity_builder()
    test_deployment_builder()
    test_batch_build_all_six_diagrams()
    print("\nALL ACTIVITY & DEPLOYMENT TESTS PASSED SUCCESSFULLY!")
