package com.mcp.visualparadigm.actions;

import com.mcp.visualparadigm.MCPSyncServer;
import com.vp.plugin.ApplicationManager;
import com.vp.plugin.ViewManager;
import com.vp.plugin.action.VPAction;
import com.vp.plugin.action.VPActionController;

import java.awt.Component;

/**
 * Action controller to toggle or inspect the Live Sync background server.
 */
public class ToggleServerActionController implements VPActionController {

    @Override
    public void performAction(VPAction action) {
        ViewManager viewManager = ApplicationManager.instance().getViewManager();
        Component parent = (viewManager != null) ? viewManager.getRootFrame() : null;
        MCPSyncServer server = MCPSyncServer.getInstance();

        if (server.isRunning()) {
            server.stop();
            if (viewManager != null) {
                viewManager.showMessage("MCP Live Sync Server has been stopped.");
            }
        } else {
            try {
                server.start(MCPSyncServer.DEFAULT_PORT);
                if (viewManager != null) {
                    viewManager.showMessage("MCP Live Sync Server started on http://127.0.0.1:" + server.getPort());
                }
            } catch (Exception e) {
                if (viewManager != null) {
                    viewManager.showMessageDialog(parent, "Failed to start Live Sync Server: " + e.getMessage(), "MCP Server Error", 0);
                }
            }
        }
        update(action);
    }

    @Override
    public void update(VPAction action) {
        if (action != null) {
            boolean running = MCPSyncServer.getInstance().isRunning();
            action.setEnabled(true);
            action.setLabel(running ? "Stop MCP Live Sync Server" : "Start MCP Live Sync Server");
            action.setTooltip(running
                    ? "Live Sync is ACTIVE on port 19842. Click to stop."
                    : "Live Sync is STOPPED. Click to start.");
        }
    }
}
