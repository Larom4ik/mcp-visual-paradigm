package com.mcp.visualparadigm.actions;

import com.vp.plugin.ApplicationManager;
import com.vp.plugin.ViewManager;
import com.vp.plugin.action.VPAction;
import com.vp.plugin.action.VPActionController;

import javax.swing.JFileChooser;
import javax.swing.filechooser.FileNameExtensionFilter;
import java.awt.Component;
import java.io.File;

/**
 * Action controller for the "Import MCP Diagram (XMI)" menu and toolbar button.
 */
public class ImportXMIActionController implements VPActionController {

    private static File lastDirectory = null;

    @Override
    public void performAction(VPAction action) {
        ViewManager viewManager = ApplicationManager.instance().getViewManager();
        Component parent = (viewManager != null) ? viewManager.getRootFrame() : null;

        JFileChooser chooser = new JFileChooser();
        chooser.setDialogTitle("Select MCP-generated XMI 2.1 File");
        chooser.setFileFilter(new FileNameExtensionFilter("XMI Files (*.xmi, *.xml)", "xmi", "xml"));

        if (lastDirectory != null && lastDirectory.exists()) {
            chooser.setCurrentDirectory(lastDirectory);
        } else {
            // Default to working directory or user home
            chooser.setCurrentDirectory(new File(System.getProperty("user.dir")));
        }

        int result = chooser.showOpenDialog(parent);
        if (result == JFileChooser.APPROVE_OPTION) {
            File selectedFile = chooser.getSelectedFile();
            lastDirectory = selectedFile.getParentFile();

            try {
                if (ApplicationManager.instance().getModelConvertionManager() != null) {
                    ApplicationManager.instance().getModelConvertionManager().importXMI(selectedFile);
                    if (viewManager != null) {
                        viewManager.showMessage("Successfully imported diagram: " + selectedFile.getName());
                    }
                }
            } catch (Throwable ex) {
                ex.printStackTrace();
                if (viewManager != null) {
                    viewManager.showMessageDialog(parent, "Failed to import XMI: " + ex.getMessage(), "MCP Import Error", 0);
                }
            }
        }
    }

    @Override
    public void update(VPAction action) {
        if (action != null) {
            action.setEnabled(true);
        }
    }
}
