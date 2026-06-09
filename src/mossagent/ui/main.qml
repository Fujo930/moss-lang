import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

ApplicationWindow {
    id: window
    width: 1200; height: 760
    minimumWidth: 800; minimumHeight: 500
    visible: true
    title: "Corvus — Moss Agent"

    // ── Global font ────────────────────────────────────────
    font.family: "Segoe UI"

    // ── Theme ──────────────────────────────────────────────
    property bool darkMode: false

    property color cBg0:     darkMode ? "#0d1117" : "#ffffff"
    property color cBg1:     darkMode ? "#161b22" : "#f6f8fa"
    property color cBg2:     darkMode ? "#21262d" : "#eaeef2"
    property color cBg3:     darkMode ? "#30363d" : "#d0d7de"
    property color cFg1:     darkMode ? "#e6edf3" : "#1f2328"
    property color cFg2:     darkMode ? "#8b949e" : "#656d76"
    property color cFg3:     darkMode ? "#484f58" : "#8c959f"
    property color cAccent:  "#7c3aed"
    property color cGreen:   darkMode ? "#3fb950" : "#1a7f37"
    property color cRed:     darkMode ? "#f85149" : "#cf222e"
    property color cAmber:   darkMode ? "#d29922" : "#9a6700"
    property color cBlue:    darkMode ? "#58a6ff" : "#0969da"

    color: cBg0

    // ── Title bar text (read by bridge) ────────────────────
    property string statusText: "Ready"

    // ── Two-panel body: Chat (left) + Files (right) ─────────
    RowLayout {
        anchors.fill: parent; spacing: 0

        ChatPanel {
            id: chatPanel
            Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumWidth: 300
        }

        Rectangle {
            width: 1; Layout.fillHeight: true; color: cBg3
        }

        WorkspacePanel {
            id: workspacePanel
            Layout.preferredWidth: 280; Layout.minimumWidth: 200; Layout.fillHeight: true
        }
    }

    // ── Python bridge signals ──────────────────────────────
    Connections {
        target: bridge

        function onMessageAdded(role, content, toolCall) {
            chatPanel.addMessage(role, content, toolCall)
        }
        function onGateUpdated(name, status) {
            detailPanel.updateGate(name, status)
        }
        function onProgressChanged(msg) {
            window.statusText = msg
            try {
                var result = JSON.parse(msg)
                if (result.summary) detailPanel.showResult(result)
            } catch(e) {}
        }
    }

    Component.onCompleted: {
        bridge.onUIReady()
    }
}
