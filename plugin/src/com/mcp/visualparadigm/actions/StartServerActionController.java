package com.mcp.visualparadigm.actions;

import com.mcp.visualparadigm.MCPSyncServer;
import com.vp.plugin.ApplicationManager;
import com.vp.plugin.ViewManager;
import com.vp.plugin.action.VPAction;
import com.vp.plugin.action.VPActionController;

import java.awt.Component;

/**
 * Action controller to start (connect) the MCP Live Sync background server.
 */
public class StartServerActionController implements VPActionController {

    @Override
    public void performAction(VPAction action) {
        ViewManager viewManager = ApplicationManager.instance().getViewManager();
        Component parent = (viewManager != null) ? viewManager.getRootFrame() : null;
        MCPSyncServer server = MCPSyncServer.getInstance();

        if (server.isRunning()) {
            if (viewManager != null) {
                viewManager.showMessageDialog(
                        parent,
                        "Live Sync is ALREADY CONNECTED and listening on http://127.0.0.1:" + server.getPort() + "\nReady to receive diagrams from AI Agent.",
                        "MCP Live Sync: Connected",
                        1 // Information Message
                );
            }
        } else {
            try {
                server.start(MCPSyncServer.DEFAULT_PORT);
                if (viewManager != null) {
                    viewManager.showMessage("MCP: Live Sync CONNECTED on http://127.0.0.1:" + server.getPort());
                    viewManager.showMessageDialog(
                            parent,
                            "Live Sync CONNECTED successfully on http://127.0.0.1:" + server.getPort() + "\nAI Agents can now instantly draw and inspect diagrams.",
                            "MCP Live Sync: Connected",
                            1 // Information Message
                    );
                }
            } catch (Exception e) {
                if (viewManager != null) {
                    viewManager.showMessageDialog(
                            parent,
                            "Failed to start Live Sync Server: " + e.getMessage(),
                            "MCP Server Error",
                            0 // Error Message
                    );
                }
            }
        }
    }

    @Override
    public void update(VPAction action) {
        if (action != null) {
            action.setEnabled(true);
            action.setLabel("Connect");
            action.setTooltip("Start MCP Live Sync server (127.0.0.1:19842) for instant AI diagram rendering");
        }
    }
}
