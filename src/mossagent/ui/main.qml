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
    font.family: "Segoe UI"

    property bool darkMode: false
    property color cBg0: darkMode ? "#0d1117" : "#ffffff"
    property color cBg1: darkMode ? "#161b22" : "#f6f8fa"
    property color cBg2: darkMode ? "#21262d" : "#eaeef2"
    property color cBg3: darkMode ? "#30363d" : "#d0d7de"
    property color cFg1: darkMode ? "#e6edf3" : "#1f2328"
    property color cFg2: darkMode ? "#8b949e" : "#656d76"
    property color cFg3: darkMode ? "#484f58" : "#8c959f"
    property color cAccent: "#7c3aed"
    property color cGreen:  darkMode ? "#3fb950" : "#1a7f37"
    property color cRed:    darkMode ? "#f85149" : "#cf222e"
    property color cAmber:  darkMode ? "#d29922" : "#9a6700"
    property color cBlue:   darkMode ? "#58a6ff" : "#0969da"
    color: cBg0

    property string statusText: "Ready"
    property int activeSession: bridge.activeSession || 0
    property var sessionNames: bridge.sessionNames || ["Default"]

    // ── Tab bar ────────────────────────────────────────────
    Item {
        id: tabBar
        anchors.top: parent.top; anchors.left: parent.left
        anchors.right: parent.right
        height: 44

        RowLayout {
            anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 12; spacing: 6

            // Session tabs
            ListView {
                id: tabList
                Layout.fillWidth: true; Layout.fillHeight: true
                orientation: ListView.Horizontal; clip: true
                model: window.sessionNames
                spacing: 4
                interactive: false

                delegate: Rectangle {
                    width: tabLabel.implicitWidth + 32; height: 32; radius: 10
                    color: index === window.activeSession ? Qt.alpha(window.cAccent, 0.12) : "transparent"
                    border.color: index === window.activeSession ? window.cAccent : "transparent"
                    border.width: 1

                    RowLayout {
                        anchors.centerIn: parent; spacing: 6
                        Text {
                            id: tabLabel
                            text: modelData; color: window.cFg1; font.pixelSize: 12
                            font.weight: index === window.activeSession ? Font.DemiBold : Font.Normal
                        }
                        Rectangle {
                            visible: tabList.count > 1
                            width: 16; height: 16; radius: 4
                            color: "transparent"
                            Text { anchors.centerIn: parent; text: "✕"; color: window.cFg3; font.pixelSize: 10 }
                            MouseArea {
                                anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                onClicked: bridge.closeSession(index)
                            }
                        }
                    }

                    MouseArea {
                        anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                        onClicked: bridge.switchSession(index)
                    }
                }
            }

            // New session button
            Rectangle {
                width: 28; height: 28; radius: 8; color: "transparent"; border.color: window.cBg3
                Text { anchors.centerIn: parent; text: "+"; color: window.cFg2; font.pixelSize: 16 }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: bridge.createSession("Session " + (tabList.count + 1)) }
            }

            Item { Layout.preferredWidth: 16 }

            // Theme toggle
            Rectangle {
                width: 28; height: 28; radius: 8; color: window.cBg2; border.color: window.cBg3
                Text { anchors.centerIn: parent; text: darkMode ? "☀" : "🌙"; font.pixelSize: 14 }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: darkMode = !darkMode }
            }
        }
    }

    // ── Main body ──────────────────────────────────────────
    Item {
        anchors.top: tabBar.bottom; anchors.bottom: parent.bottom
        anchors.left: parent.left; anchors.right: parent.right
        anchors.margins: 12

        ChatPanel {
            id: chatPanel
            anchors.top: parent.top; anchors.bottom: parent.bottom
            anchors.left: parent.left
            anchors.right: filePanel.left; anchors.rightMargin: 12
        }

        Rectangle {
            id: filePanel
            anchors.top: parent.top; anchors.bottom: parent.bottom
            anchors.right: parent.right
            anchors.rightMargin: viewerSlot.viewerVisible ? 432 : 0
            width: 280; radius: 14; color: window.cBg0
            border.color: window.cBg3; border.width: 1
            clip: true

            Behavior on anchors.rightMargin { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }

            Rectangle {
                anchors.fill: parent; anchors.margins: -2; radius: 16; z: -1
                color: window.darkMode ? Qt.rgba(0,0,0,0.2) : Qt.rgba(0,0,0,0.06)
            }

            ColumnLayout {
                anchors.fill: parent; spacing: 0; anchors.margins: 10

                // File tree — fills vertical space
                ListView {
                    id: fileList
                    Layout.fillWidth: true; Layout.fillHeight: true
                    clip: true; model: bridge.fileTree; spacing: 1

                    delegate: Rectangle {
                        width: fileList.width; implicitHeight: 30; radius: 8
                        x: modelData.depth ? modelData.depth * 14 : 0
                        color: modelData.path === window.selectedPath ? Qt.alpha(window.cAccent, 0.12) : "transparent"

                        RowLayout {
                            anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 8; spacing: 6
                            Text { text: modelData.isDir ? "📂" : "📄"; font.pixelSize: 11 }
                            Text { text: modelData.name; color: window.cFg1; font.pixelSize: 12; elide: Text.ElideRight; Layout.fillWidth: true }
                        }

                        MouseArea {
                            anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                window.selectedPath = modelData.path
                                if (modelData.isDir) bridge.toggleDirectory(modelData.path)
                                else bridge.openFile(modelData.path)
                            }
                        }
                    }
                }

                // Settings card
                Rectangle { id: mc1; property bool ch: false
                    Layout.fillWidth: true; implicitHeight: 44; radius: 12
                    color: window.cBg0; border.color: window.cBg3; border.width: 1
                    Rectangle { anchors.fill: parent; anchors.margins: -2; radius: 14; z: -1
                        color: window.darkMode ? Qt.rgba(0,0,0,0.2) : Qt.rgba(0,0,0,0.06)
                        opacity: mc1.ch ? 1.0 : 0.0; Behavior on opacity { NumberAnimation { duration: 200 } } }
                    RowLayout { anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 12; spacing: 8
                        Text { text: "⚙️"; font.pixelSize: 12 }
                        Text { text: "Settings"; color: window.cFg1; font.pixelSize: 13 }
                        Item { Layout.fillWidth: true } }
                    MouseArea { anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onEntered: mc1.ch = true; onExited: mc1.ch = false } }
                // History card
                Rectangle { id: mc2; property bool ch: false
                    Layout.fillWidth: true; implicitHeight: 44; radius: 12
                    color: window.cBg0; border.color: window.cBg3; border.width: 1
                    Rectangle { anchors.fill: parent; anchors.margins: -2; radius: 14; z: -1
                        color: window.darkMode ? Qt.rgba(0,0,0,0.2) : Qt.rgba(0,0,0,0.06)
                        opacity: mc2.ch ? 1.0 : 0.0; Behavior on opacity { NumberAnimation { duration: 200 } } }
                    RowLayout { anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 12; spacing: 8
                        Text { text: "🕐"; font.pixelSize: 12 }
                        Text { text: "History"; color: window.cFg1; font.pixelSize: 13 }
                        Item { Layout.fillWidth: true } }
                    MouseArea { anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onEntered: mc2.ch = true; onExited: mc2.ch = false } }
                // Trash card
                Rectangle { id: mc3; property bool ch: false
                    Layout.fillWidth: true; implicitHeight: 44; radius: 12
                    color: window.cBg0; border.color: window.cBg3; border.width: 1
                    Rectangle { anchors.fill: parent; anchors.margins: -2; radius: 14; z: -1
                        color: window.darkMode ? Qt.rgba(0,0,0,0.2) : Qt.rgba(0,0,0,0.06)
                        opacity: mc3.ch ? 1.0 : 0.0; Behavior on opacity { NumberAnimation { duration: 200 } } }
                    RowLayout { anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 12; spacing: 8
                        Text { text: "🗑️"; font.pixelSize: 12 }
                        Text { text: "Trash"; color: window.cFg1; font.pixelSize: 13 }
                        Item { Layout.fillWidth: true } }
                    MouseArea { anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onEntered: mc3.ch = true; onExited: mc3.ch = false } }
            }
        }

        // Viewer
        Rectangle {
            id: viewerSlot
            anchors.top: parent.top; anchors.bottom: parent.bottom
            anchors.right: parent.right; width: 420; color: "transparent"; clip: true

            property bool viewerVisible: bridge.fileViewerPath !== ""
            x: viewerVisible ? 0 : width + 12
            visible: viewerVisible || x < width
            Behavior on x { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }

            Rectangle {
                anchors.fill: parent; radius: 16; color: window.cBg0
                border.color: window.cBg3; border.width: 1; clip: true

                Rectangle {
                    anchors.fill: parent; anchors.margins: -2; radius: 18; z: -1
                    color: window.darkMode ? Qt.rgba(0,0,0,0.35) : Qt.rgba(0,0,0,0.08)
                }

                Rectangle {
                    id: viewerTitleBar; width: parent.width; height: 44; color: window.cBg0
                    RowLayout {
                        anchors.fill: parent; anchors.leftMargin: 16; anchors.rightMargin: 8; spacing: 10
                        Text { text: "📄"; font.pixelSize: 14 }
                        Text { text: bridge.fileViewerPath || ""; color: window.cFg1; font.pixelSize: 13; font.weight: Font.DemiBold; elide: Text.ElideRight; Layout.fillWidth: true }
                        Rectangle { width: 30; height: 30; radius: 8; color: window.cBg2; border.color: window.cBg3
                            Text { anchors.centerIn: parent; text: "✕"; color: window.cFg2; font.pixelSize: 13 }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: bridge.closeFileViewer() }
                        }
                    }
                    Rectangle { anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right; height: 1; color: window.cBg3 }
                }

                Flickable {
                    id: viewerFlick
                    anchors.top: viewerTitleBar.bottom; anchors.left: parent.left
                    anchors.right: parent.right; anchors.bottom: parent.bottom
                    contentWidth: viewerText.implicitWidth; contentHeight: viewerText.implicitHeight
                    clip: true; boundsBehavior: Flickable.StopAtBounds; flickableDirection: Flickable.VerticalFlick

                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AlwaysOn; parent: viewerFlick.parent
                        anchors.right: viewerFlick.right; anchors.top: viewerFlick.top; anchors.bottom: viewerFlick.bottom; anchors.margins: 4 }

                    Text { id: viewerText; width: viewerFlick.width - 28; x: 16; y: 8
                        text: bridge.fileViewerContent || ""; color: window.cFg1; font.pixelSize: 12; font.family: "Consolas"; wrapMode: Text.Wrap }
                }
            }
        }
    }

    property string selectedPath: ""

    Connections { target: bridge
        function onMessageAdded(role, content, toolCall) { chatPanel.addMessage(role, content, toolCall) }
        function onProgressChanged(msg) { window.statusText = msg }
    }

    Component.onCompleted: { bridge.onUIReady() }
}
