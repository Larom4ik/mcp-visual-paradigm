package com.mcp.visualparadigm;

import com.vp.plugin.ApplicationManager;
import com.vp.plugin.ExportDiagramAsImageOption;
import com.vp.plugin.diagram.IDiagramUIModel;
import com.vp.plugin.model.IProject;

import javax.swing.SwingUtilities;
import java.io.*;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;

/**
 * Pure Java standard socket HTTP server.
 * Uses only java.base (java.net.ServerSocket) to ensure 100% compatibility across
 * all Visual Paradigm versions (16.x - 18.x) and all JDK/modular runtimes without
 * depending on jdk.httpserver module.
 */
public class MCPSyncServer {

    public static final int DEFAULT_PORT = 19842;
    private static MCPSyncServer instance;

    private ServerSocket serverSocket;
    private Thread serverThread;
    private volatile boolean running = false;
    private int port = DEFAULT_PORT;

    private MCPSyncServer() {}

    public static synchronized MCPSyncServer getInstance() {
        if (instance == null) {
            instance = new MCPSyncServer();
        }
        return instance;
    }

    public synchronized boolean isRunning() {
        return running;
    }

    public synchronized int getPort() {
        return port;
    }

    public synchronized void start(int serverPort) throws IOException {
        if (running) {
            return;
        }
        this.port = serverPort;
        serverSocket = new ServerSocket();
        serverSocket.setReuseAddress(true);
        serverSocket.bind(new InetSocketAddress("127.0.0.1", port));
        running = true;

        serverThread = new Thread(this::listenLoop, "MCP-LiveSync-Worker");
        serverThread.setDaemon(true);
        serverThread.start();

        System.out.println("[MCP Plugin] Pure Socket Live Sync Server listening on http://127.0.0.1:" + port);
    }

    public synchronized void stop() {
        if (!running) {
            return;
        }
        running = false;
        try {
            if (serverSocket != null && !serverSocket.isClosed()) {
                serverSocket.close();
            }
        } catch (Exception ignored) {}
        serverSocket = null;
        serverThread = null;
        System.out.println("[MCP Plugin] Live Sync Server stopped.");
    }

    private void listenLoop() {
        while (running && serverSocket != null && !serverSocket.isClosed()) {
            try {
                Socket client = serverSocket.accept();
                new Thread(() -> handleClient(client), "MCP-Client-Handler").start();
            } catch (IOException e) {
                if (!running) {
                    break;
                }
            }
        }
    }

    private void handleClient(Socket socket) {
        try (socket;
             InputStream in = socket.getInputStream();
             OutputStream out = socket.getOutputStream();
             BufferedReader reader = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8))) {

            String requestLine = reader.readLine();
            if (requestLine == null || requestLine.trim().isEmpty()) {
                return;
            }

            String[] parts = requestLine.split(" ");
            if (parts.length < 2) {
                return;
            }
            String method = parts[0].toUpperCase();
            String uri = parts[1];

            // Read HTTP headers
            Map<String, String> headers = new HashMap<>();
            String headerLine;
            int contentLength = 0;
            while ((headerLine = reader.readLine()) != null && !headerLine.isEmpty()) {
                int colon = headerLine.indexOf(":");
                if (colon > 0) {
                    String key = headerLine.substring(0, colon).trim().toLowerCase();
                    String val = headerLine.substring(colon + 1).trim();
                    headers.put(key, val);
                    if ("content-length".equals(key)) {
                        try {
                            contentLength = Integer.parseInt(val);
                        } catch (Exception ignored) {}
                    }
                }
            }

            // Read body if present
            String body = "";
            if (contentLength > 0) {
                char[] bodyChars = new char[contentLength];
                int read = 0;
                while (read < contentLength) {
                    int r = reader.read(bodyChars, read, contentLength - read);
                    if (r == -1) break;
                    read += r;
                }
                body = new String(bodyChars, 0, read);
            }

            // Route requests
            if ("OPTIONS".equals(method)) {
                sendResponse(out, 204, "OK", "text/plain", "");
                return;
            }

            String path = uri;
            String query = "";
            int qIdx = uri.indexOf("?");
            if (qIdx >= 0) {
                path = uri.substring(0, qIdx);
                query = uri.substring(qIdx + 1);
            }

            if ("/health".equals(path) || "/status".equals(path)) {
                handleHealth(out);
            } else if ("/import".equals(path)) {
                handleImport(out, query, body);
            } else if ("/export_image".equals(path)) {
                handleExportImage(out, query, body);
            } else {
                sendResponse(out, 404, "Not Found", "application/json", "{\"error\":\"Unknown endpoint\"}");
            }

        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    private void handleHealth(OutputStream out) throws IOException {
        String projectName = "No Project";
        try {
            if (ApplicationManager.instance() != null && ApplicationManager.instance().getProjectManager() != null) {
                IProject project = ApplicationManager.instance().getProjectManager().getProject();
                if (project != null && project.getName() != null) {
                    projectName = project.getName();
                }
            }
        } catch (Throwable ignored) {}

        String json = String.format("{\"status\":\"ok\",\"app\":\"Visual Paradigm\",\"project\":\"%s\"}", projectName);
        sendResponse(out, 200, "OK", "application/json", json);
    }

    private void handleImport(OutputStream out, String query, String body) throws IOException {
        Map<String, String> params = parseQueryParams(query);
        String filePath = params.get("file");

        if (filePath == null || filePath.trim().isEmpty()) {
            if (body != null && !body.trim().isEmpty()) {
                if (body.contains("\"file\"")) {
                    int start = body.indexOf("\"file\"");
                    int colon = body.indexOf(":", start);
                    int q1 = body.indexOf("\"", colon + 1);
                    int q2 = body.indexOf("\"", q1 + 1);
                    if (q1 > 0 && q2 > q1) {
                        filePath = body.substring(q1 + 1, q2);
                    }
                } else {
                    filePath = body.trim();
                }
            }
        }

        if (filePath == null || filePath.trim().isEmpty()) {
            sendResponse(out, 400, "Bad Request", "application/json", "{\"success\":false,\"error\":\"Missing 'file' parameter\"}");
            return;
        }

        final File targetFile = new File(filePath);
        if (!targetFile.exists()) {
            sendResponse(out, 404, "Not Found", "application/json", String.format("{\"success\":false,\"error\":\"File not found: %s\"}", filePath));
            return;
        }

        // Trigger import asynchronously on Swing Event Dispatch Thread (EDT)
        SwingUtilities.invokeLater(() -> {
            try {
                System.out.println("[MCP Plugin] Importing XMI: " + targetFile.getAbsolutePath());
                if (ApplicationManager.instance() != null && ApplicationManager.instance().getModelConvertionManager() != null) {
                    ApplicationManager.instance().getModelConvertionManager().importXMI(targetFile);

                    // Auto-open imported diagram in active editor tab
                    try {
                        if (ApplicationManager.instance().getProjectManager() != null &&
                                ApplicationManager.instance().getDiagramManager() != null) {
                            IProject proj = ApplicationManager.instance().getProjectManager().getProject();
                            if (proj != null) {
                                IDiagramUIModel[] diags = proj.toDiagramArray();
                                if (diags != null && diags.length > 0) {
                                    IDiagramUIModel latest = diags[diags.length - 1];
                                    ApplicationManager.instance().getDiagramManager().openDiagram(latest);
                                }
                            }
                        }
                    } catch (Throwable t) {
                        System.err.println("[MCP Plugin] Notice: Could not auto-open diagram: " + t.getMessage());
                    }

                    if (ApplicationManager.instance().getViewManager() != null) {
                        ApplicationManager.instance().getViewManager().showMessage("MCP: Successfully imported and opened " + targetFile.getName());
                    }
                }
            } catch (Throwable ex) {
                ex.printStackTrace();
                if (ApplicationManager.instance() != null && ApplicationManager.instance().getViewManager() != null) {
                    ApplicationManager.instance().getViewManager().showMessage("MCP Import Error: " + ex.getMessage());
                }
            }
        });

        String json = String.format("{\"success\":true,\"message\":\"Import initiated for %s\"}", targetFile.getName());
        sendResponse(out, 200, "OK", "application/json", json);
    }

    private void handleExportImage(OutputStream out, String query, String body) throws IOException {
        Map<String, String> params = parseQueryParams(query);
        String diagramName = params.get("diagram");
        String filePath = params.get("file");

        if (filePath == null || filePath.trim().isEmpty()) {
            if (body != null && !body.trim().isEmpty()) {
                if (body.contains("\"file\"")) {
                    int start = body.indexOf("\"file\"");
                    int colon = body.indexOf(":", start);
                    int q1 = body.indexOf("\"", colon + 1);
                    int q2 = body.indexOf("\"", q1 + 1);
                    if (q1 > 0 && q2 > q1) {
                        filePath = body.substring(q1 + 1, q2);
                    }
                }
                if (body.contains("\"diagram\"")) {
                    int start = body.indexOf("\"diagram\"");
                    int colon = body.indexOf(":", start);
                    int q1 = body.indexOf("\"", colon + 1);
                    int q2 = body.indexOf("\"", q1 + 1);
                    if (q1 > 0 && q2 > q1) {
                        diagramName = body.substring(q1 + 1, q2);
                    }
                }
            }
        }

        if (filePath == null || filePath.trim().isEmpty()) {
            filePath = System.getProperty("java.io.tmpdir") + File.separator + "vp_diagram_" + System.currentTimeMillis() + ".png";
        }

        final File targetFile = new File(filePath);
        if (targetFile.getParentFile() != null && !targetFile.getParentFile().exists()) {
            targetFile.getParentFile().mkdirs();
        }

        final String reqDiagramName = diagramName;
        final boolean[] success = new boolean[]{false};
        final String[] errorMsg = new String[]{null};
        final String[] exportedDiagramName = new String[]{""};

        Runnable exportTask = () -> {
            try {
                if (ApplicationManager.instance() == null) {
                    errorMsg[0] = "ApplicationManager instance is null";
                    return;
                }

                IDiagramUIModel targetDiagram = null;
                if (reqDiagramName != null && !reqDiagramName.trim().isEmpty()) {
                    if (ApplicationManager.instance().getProjectManager() != null &&
                            ApplicationManager.instance().getProjectManager().getProject() != null) {
                        IDiagramUIModel[] allDiagrams = ApplicationManager.instance().getProjectManager().getProject().toDiagramArray();
                        if (allDiagrams != null) {
                            for (IDiagramUIModel d : allDiagrams) {
                                if (reqDiagramName.equalsIgnoreCase(d.getName())) {
                                    targetDiagram = d;
                                    break;
                                }
                            }
                        }
                    }
                }

                if (targetDiagram == null && ApplicationManager.instance().getDiagramManager() != null) {
                    targetDiagram = ApplicationManager.instance().getDiagramManager().getActiveDiagram();
                }

                if (targetDiagram == null && ApplicationManager.instance().getDiagramManager() != null) {
                    IDiagramUIModel[] opened = ApplicationManager.instance().getDiagramManager().getOpenedDiagrams();
                    if (opened != null && opened.length > 0) {
                        targetDiagram = opened[0];
                    }
                }

                if (targetDiagram == null && ApplicationManager.instance().getProjectManager() != null &&
                        ApplicationManager.instance().getProjectManager().getProject() != null) {
                    IDiagramUIModel[] all = ApplicationManager.instance().getProjectManager().getProject().toDiagramArray();
                    if (all != null && all.length > 0) {
                        targetDiagram = all[all.length - 1];
                        if (ApplicationManager.instance().getDiagramManager() != null) {
                            ApplicationManager.instance().getDiagramManager().openDiagram(targetDiagram);
                        }
                    }
                }

                if (targetDiagram == null) {
                    errorMsg[0] = "No active or opened diagram found in Visual Paradigm. Please open a diagram or import an XMI.";
                    return;
                }

                exportedDiagramName[0] = targetDiagram.getName();
                ExportDiagramAsImageOption option = new ExportDiagramAsImageOption(ExportDiagramAsImageOption.IMAGE_TYPE_PNG);
                ApplicationManager.instance().getModelConvertionManager().exportDiagramAsImage(targetDiagram, targetFile, option);
                success[0] = true;

                if (ApplicationManager.instance().getViewManager() != null) {
                    ApplicationManager.instance().getViewManager().showMessage("MCP: Exported diagram image to " + targetFile.getName());
                }
            } catch (Throwable ex) {
                ex.printStackTrace();
                errorMsg[0] = ex.getMessage();
            }
        };

        try {
            if (SwingUtilities.isEventDispatchThread()) {
                exportTask.run();
            } else {
                SwingUtilities.invokeAndWait(exportTask);
            }
        } catch (Exception ex) {
            errorMsg[0] = ex.getMessage();
        }

        if (success[0]) {
            String json = String.format("{\"success\":true,\"diagram\":\"%s\",\"image_path\":\"%s\"}",
                    exportedDiagramName[0].replace("\\", "\\\\").replace("\"", "\\\""),
                    targetFile.getAbsolutePath().replace("\\", "\\\\").replace("\"", "\\\""));
            sendResponse(out, 200, "OK", "application/json", json);
        } else {
            String json = String.format("{\"success\":false,\"error\":\"%s\"}",
                    (errorMsg[0] != null ? errorMsg[0] : "Export failed").replace("\\", "\\\\").replace("\"", "\\\""));
            sendResponse(out, 200, "OK", "application/json", json);
        }
    }

    private static void sendResponse(OutputStream out, int code, String statusText, String contentType, String content) throws IOException {
        byte[] bytes = content.getBytes(StandardCharsets.UTF_8);
        String header = "HTTP/1.1 " + code + " " + statusText + "\r\n" +
                "Content-Type: " + contentType + "; charset=UTF-8\r\n" +
                "Content-Length: " + bytes.length + "\r\n" +
                "Connection: close\r\n" +
                "Access-Control-Allow-Origin: *\r\n" +
                "Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n" +
                "Access-Control-Allow-Headers: Content-Type\r\n" +
                "\r\n";
        out.write(header.getBytes(StandardCharsets.UTF_8));
        out.write(bytes);
        out.flush();
    }

    private static Map<String, String> parseQueryParams(String query) {
        Map<String, String> map = new HashMap<>();
        if (query == null || query.trim().isEmpty()) {
            return map;
        }
        String[] pairs = query.split("&");
        for (String pair : pairs) {
            int idx = pair.indexOf("=");
            if (idx > 0) {
                try {
                    String key = URLDecoder.decode(pair.substring(0, idx), StandardCharsets.UTF_8.name());
                    String val = (idx < pair.length() - 1)
                            ? URLDecoder.decode(pair.substring(idx + 1), StandardCharsets.UTF_8.name())
                            : "";
                    map.put(key, val);
                } catch (Exception ignored) {}
            }
        }
        return map;
    }
}
