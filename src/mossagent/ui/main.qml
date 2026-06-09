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

    // ── Header ─────────────────────────────────────────────
    header: Rectangle {
        height: 44; color: cBg1; border.color: cBg3; border.width: 1
        RowLayout {
            anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 12
            Rectangle { width: 28; height: 28; radius: 8; color: cAccent
                Text { anchors.centerIn: parent; text: "⟡"; color: "white"; font.pixelSize: 16 } }
            Text { text: "Corvus"; color: cFg1; font.pixelSize: 16; font.weight: Font.DemiBold }
            Text { text: "Moss Agent"; color: cFg2; font.pixelSize: 12 }
            Item { Layout.fillWidth: true }
            // Theme toggle
            Rectangle { width: 32; height: 32; radius: 8; color: cBg2; border.color: cBg3
                Text { anchors.centerIn: parent; text: darkMode ? "☀" : "🌙"; font.pixelSize: 14 }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: darkMode = !darkMode }
            }
        }
    }

    // ── Title bar text (read by bridge) ────────────────────
    property string statusText: "Ready"

    // ── Two-panel body ─────────────────────────────────────
    RowLayout {
        anchors.fill: parent; spacing: 0

        ChatPanel {
            id: chatPanel
            Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumWidth: 300
        }

        Rectangle {
            width: 1; Layout.fillHeight: true; color: cBg3
        }

        ColumnLayout {
            Layout.preferredWidth: 300; Layout.minimumWidth: 200; Layout.fillHeight: true; spacing: 0

            WorkspacePanel {
                id: workspacePanel
                Layout.fillWidth: true; Layout.fillHeight: true; Layout.preferredHeight: parent ? parent.height * 0.55 : 300
            }
            Rectangle { Layout.fillWidth: true; height: 1; color: cBg3 }
            DetailPanel {
                id: detailPanel
                Layout.fillWidth: true; Layout.fillHeight: true; Layout.preferredHeight: parent ? parent.height * 0.45 : 200
            }
        }
    }

    // ── Status bar ─────────────────────────────────────────
    footer: Rectangle {
        height: 28; color: cBg1; border.color: cBg3; border.width: 1
        RowLayout {
            anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 12; spacing: 16
            Text { text: bridge.version.moss; color: cFg3; font.pixelSize: 11; font.family: "Consolas" }
            Text { text: "·"; color: cFg3 }
            Text { text: window.statusText; color: cFg2; font.pixelSize: 11 }
            Item { Layout.fillWidth: true }
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
