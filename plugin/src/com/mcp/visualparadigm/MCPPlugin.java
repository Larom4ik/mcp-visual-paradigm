package com.mcp.visualparadigm;

import com.vp.plugin.ApplicationManager;
import com.vp.plugin.VPPlugin;
import com.vp.plugin.VPPluginInfo;

import java.io.File;

/**
 * Main plugin lifecycle entry point for Visual Paradigm.
 */
public class MCPPlugin implements VPPlugin {

    private static VPPluginInfo pluginInfo;

    public static VPPluginInfo getPluginInfo() {
        return pluginInfo;
    }

    @Override
    public void loaded(VPPluginInfo info) {
        pluginInfo = info;
        System.out.println("[MCP Plugin] Loaded: " + (info != null ? info.getPluginId() : "com.mcp.visualparadigm"));

        // Auto-start Live Sync HTTP Server on background thread
        try {
            MCPSyncServer.getInstance().start(MCPSyncServer.DEFAULT_PORT);
            if (ApplicationManager.instance() != null && ApplicationManager.instance().getActionManager() != null) {
                ApplicationManager.instance().getActionManager().queryStatus();
            }
        } catch (Exception e) {
            System.err.println("[MCP Plugin] Failed to start Live Sync server: " + e.getMessage());
            e.printStackTrace();
        }

        // Show welcome notification in VP
        try {
            if (ApplicationManager.instance() != null && ApplicationManager.instance().getViewManager() != null) {
                ApplicationManager.instance().getViewManager().showMessage("MCP Visual Paradigm Live Sync Plugin is active (port " + MCPSyncServer.DEFAULT_PORT + ").");
            }
        } catch (Throwable ignored) {}
    }

    @Override
    public void unloaded() {
        System.out.println("[MCP Plugin] Unloading plugin...");
        try {
            MCPSyncServer.getInstance().stop();
        } catch (Exception e) {
            e.printStackTrace();
        }
        pluginInfo = null;
    }
}
