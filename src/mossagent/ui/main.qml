import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "theme.js" as Theme

ApplicationWindow {
    id: window
    width: 1200
    height: 760
    minimumWidth: 800
    minimumHeight: 500
    visible: true
    title: "Corvus — Moss Agent"

    // ── Color scheme ────────────────────────────────────────
    property bool darkMode: true
    property color cBg0:     darkMode ? Theme.bg0     : Theme.light_bg0
    property color cBg1:     darkMode ? Theme.bg1     : Theme.light_bg1
    property color cBg2:     darkMode ? Theme.bg2     : Theme.light_bg2
    property color cBg3:     darkMode ? Theme.bg3     : Theme.light_bg3
    property color cFg1:     darkMode ? Theme.fg1     : Theme.light_fg1
    property color cFg2:     darkMode ? Theme.fg2     : Theme.light_fg2
    property color cFg3:     darkMode ? Theme.fg3     : Theme.light_fg3
    property color cAccent:  Theme.accent
    property color cGreen:   Theme.green
    property color cRed:     Theme.red
    property color cAmber:   Theme.amber
    property color cBlue:    Theme.blue

    color: cBg0

    // ── Header bar (Claude-style minimal top bar) ──────────
    header: Rectangle {
        height: 44
        color: cBg1
        border.color: cBg3
        border.width: 1

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: Theme.space_md
            anchors.rightMargin: Theme.space_md

            // Logo area
            Rectangle {
                width: 28; height: 28; radius: 8
                color: cAccent
                Text {
                    anchors.centerIn: parent
                    text: "⟡"
                    color: "white"
                    font.pixelSize: 16
                    font.family: Theme.font_sans
                }
            }

            Text {
                text: "Corvus"
                color: cFg1
                font.pixelSize: Theme.font_size_lg
                font.family: Theme.font_sans
                font.weight: Font.DemiBold
            }

            Text {
                text: "Moss Agent · " + bridge.version.moss
                color: cFg2
                font.pixelSize: Theme.font_size_sm
                font.family: Theme.font_sans
            }

            Item { Layout.fillWidth: true }

            // Quick actions
            RowLayout {
                spacing: Theme.space_sm
                
                // Dark/light toggle
                Rectangle {
                    width: 32; height: 32; radius: 8
                    color: darkMode ? cBg2 : cBg2
                    border.color: cBg3
                    Text {
                        anchors.centerIn: parent
                        text: darkMode ? "☀" : "🌙"
                        font.pixelSize: 14
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: darkMode = !darkMode
                    }
                }
            }
        }
    }

    // ── Three-panel body ────────────────────────────────────
    RowLayout {
        anchors.fill: parent
        spacing: 0

        // LEFT: Workspace panel (Codex-style file tree + memory)
        WorkspacePanel {
            id: workspacePanel
            Layout.preferredWidth: Theme.sidebar_w
            Layout.minimumWidth: Theme.min_panel
            Layout.fillHeight: true
        }

        // Divider
        Rectangle {
            width: 1
            Layout.fillHeight: true
            color: cBg3
        }

        // CENTER: Chat panel (Claude-style message bubbles)
        ChatPanel {
            id: chatPanel
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumWidth: 300
        }

        // Divider
        Rectangle {
            width: 1
            Layout.fillHeight: true
            color: cBg3
        }

        // RIGHT: Detail panel (Reasonix-style gate visualization)
        DetailPanel {
            id: detailPanel
            Layout.preferredWidth: Theme.detail_w
            Layout.minimumWidth: Theme.min_panel
            Layout.fillHeight: true
        }
    }

    // ── Status bar (bottom) ─────────────────────────────────
    footer: Rectangle {
        height: 28
        color: cBg1
        border.color: cBg3
        border.width: 1

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: Theme.space_md
            anchors.rightMargin: Theme.space_md
            spacing: Theme.space_lg

            Text {
                text: bridge.version.moss
                color: cFg3
                font.pixelSize: Theme.font_size_xs
                font.family: Theme.font_mono
            }
            Text {
                text: "·"
                color: cFg3
            }
            Text {
                id: statusText
                text: "Ready"
                color: cFg2
                font.pixelSize: Theme.font_size_xs
                font.family: Theme.font_sans
            }
            Item { Layout.fillWidth: true }
            Text {
                text: bridge.stats ? bridge.stats.cache_hit : ""
                color: cFg3
                font.pixelSize: Theme.font_size_xs
                font.family: Theme.font_mono
            }
        }
    }

    // ── Python bridge signals ──────────────────────────────
    Connections {
        target: bridge

        function onMessageAdded(msg) {
            chatPanel.addMessage(msg.role, msg.content, msg.toolCall)
        }
        function onGateUpdated(gate) {
            detailPanel.updateGate(gate.name, gate.status)
        }
        function onProgressChanged(msg) {
            statusText.text = msg
        }
        function onTaskComplete(result) {
            detailPanel.showResult(result)
            statusText.text = "Task complete"
        }
    }

    Component.onCompleted: {
        bridge.onUIReady()
    }
}
