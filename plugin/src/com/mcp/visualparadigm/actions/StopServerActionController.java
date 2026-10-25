package com.mcp.visualparadigm.actions;

import com.mcp.visualparadigm.MCPSyncServer;
import com.vp.plugin.ApplicationManager;
import com.vp.plugin.ViewManager;
import com.vp.plugin.action.VPAction;
import com.vp.plugin.action.VPActionController;

import java.awt.Component;

/**
 * Action controller to stop (disconnect) the MCP Live Sync background server.
 */
public class StopServerActionController implements VPActionController {

    @Override
    public void performAction(VPAction action) {
        ViewManager viewManager = ApplicationManager.instance().getViewManager();
        Component parent = (viewManager != null) ? viewManager.getRootFrame() : null;
        MCPSyncServer server = MCPSyncServer.getInstance();

        if (server.isRunning()) {
            server.stop();
            if (action != null) {
                action.setEnabled(false);
            }
            try {
                VPAction startAction = ApplicationManager.instance().getActionManager().getAction("com.mcp.visualparadigm.actions.StartServerAction");
                if (startAction != null) {
                    startAction.setEnabled(true);
                }
                ApplicationManager.instance().getActionManager().queryStatus();
            } catch (Throwable ignored) {
            }
            if (viewManager != null) {
                viewManager.showMessage("MCP: Live Sync DISCONNECTED. Server stopped.");
                viewManager.showMessageDialog(
                        parent,
                        "Live Sync DISCONNECTED.\nBackground server on port 19842 has been stopped.",
                        "MCP Live Sync: Disconnected",
                        1 // Information Message
                );
            }
        } else {
            if (viewManager != null) {
                viewManager.showMessageDialog(
                        parent,
                        "Live Sync is already STOPPED.",
                        "MCP Live Sync: Disconnected",
                        1 // Information Message
                );
            }
        }
    }

    @Override
    public void update(VPAction action) {
        if (action != null) {
            action.setEnabled(MCPSyncServer.getInstance().isRunning());
            action.setLabel("Disconnect");
            action.setTooltip("Stop MCP Live Sync background server");
        }
    }
}
