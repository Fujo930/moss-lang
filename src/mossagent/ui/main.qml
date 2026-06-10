import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

ApplicationWindow {
    id: window
    width: 1200; height: 760
    minimumWidth: 900; minimumHeight: 500
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
    property bool welcomeDone: bridge.welcomeDone || false
    property bool welcomeClosing: false

    // ── Welcome screen ──────────────────────────────────────
    Rectangle {
        id: welcomeHost
        anchors.fill: parent
        z: 100
        color: "#5b6e7a"
        visible: !welcomeDone

        Timer {
            running: welcomeClosing
            interval: 600
            onTriggered: { window.welcomeDone = true; welcomeHost.visible = false }
        }

        Welcome { anchors.fill: parent }
    }

    // ── Three-panel body ────────────────────────────────────
    Item {
        anchors.fill: parent; anchors.margins: 10
        visible: welcomeDone
        opacity: welcomeDone ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 400 } }

        // LEFT: Session sidebar
        Rectangle {
            id: sidebar
            anchors.top: parent.top; anchors.bottom: parent.bottom
            anchors.left: parent.left; width: 200; radius: 14; color: cBg0
            border.color: cBg3; border.width: 1; clip: true

            ColumnLayout {
                anchors.fill: parent; spacing: 0

                // Sidebar header
                Rectangle { Layout.fillWidth: true; implicitHeight: 46
                    color: cBg0
                    Rectangle { anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right; height: 1; color: cBg3 }
                    RowLayout { anchors.fill: parent; anchors.leftMargin: 14; anchors.rightMargin: 10; spacing: 8
                        Rectangle { width: 24; height: 24; radius: 6; color: cAccent
                            Text { anchors.centerIn: parent; text: "⟡"; color: "white"; font.pixelSize: 13 } }
                        Text { text: "Corvus"; color: cFg1; font.pixelSize: 14; font.weight: Font.DemiBold }
                        Item { Layout.fillWidth: true }
                        Rectangle { width: 26; height: 26; radius: 6; color: cBg2; border.color: cBg3
                            Text { anchors.centerIn: parent; text: "+"; color: cFg2; font.pixelSize: 15 }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: bridge.createSession("New") }
                        }
                    }
                }

                // Session list
                ListView {
                    id: sessionList
                    Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                    model: window.sessionNames; spacing: 2
                    anchors.topMargin: 6; anchors.bottomMargin: 6

                    delegate: Rectangle {
                        width: sessionList.width - 16; x: 8; implicitHeight: 38; radius: 10
                        color: index === window.activeSession ? Qt.alpha(window.cAccent, 0.10) : "transparent"
                        border.color: index === window.activeSession ? Qt.alpha(window.cAccent, 0.25) : "transparent"
                        border.width: 1

                        RowLayout {
                            anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 8; spacing: 8
                            Text { text: "💬"; font.pixelSize: 11 }
                            Text { text: modelData; color: window.cFg1; font.pixelSize: 12
                                font.weight: index === window.activeSession ? Font.DemiBold : Font.Normal
                                elide: Text.ElideRight; Layout.fillWidth: true }
                            Rectangle { visible: sessionList.count > 1; width: 18; height: 18; radius: 4; color: "transparent"
                                Text { anchors.centerIn: parent; text: "✕"; color: window.cFg3; font.pixelSize: 9 }
                                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: bridge.closeSession(index) }
                            }
                        }

                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: bridge.switchSession(index) }
                    }
                }

                // Bottom tools
                ColumnLayout {
                    Layout.fillWidth: true; anchors.bottomMargin: 8
                    // Settings button
                    Rectangle { id: sbtn; property bool h: false
                        Layout.fillWidth: true; implicitHeight: 36; radius: 10
                        color: sbtn.h ? window.cBg2 : "transparent"
                        RowLayout { anchors.fill: parent; anchors.leftMargin: 14; spacing: 8
                            Text { text: "⚙️"; font.pixelSize: 12 }
                            Text { text: "Settings"; color: window.cFg2; font.pixelSize: 12 }
                            Item { Layout.fillWidth: true } }
                        MouseArea { anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onEntered: sbtn.h = true; onExited: sbtn.h = false } }
                    // History button
                    Rectangle { id: hbtn; property bool h: false
                        Layout.fillWidth: true; implicitHeight: 36; radius: 10
                        color: hbtn.h ? window.cBg2 : "transparent"
                        RowLayout { anchors.fill: parent; anchors.leftMargin: 14; spacing: 8
                            Text { text: "🕐"; font.pixelSize: 12 }
                            Text { text: "History"; color: window.cFg2; font.pixelSize: 12 }
                            Item { Layout.fillWidth: true } }
                        MouseArea { anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onEntered: hbtn.h = true; onExited: hbtn.h = false } }
                    // Trash button
                    Rectangle { id: tbtn; property bool h: false
                        Layout.fillWidth: true; implicitHeight: 36; radius: 10
                        color: tbtn.h ? window.cBg2 : "transparent"
                        RowLayout { anchors.fill: parent; anchors.leftMargin: 14; spacing: 8
                            Text { text: "🗑️"; font.pixelSize: 12 }
                            Text { text: "Trash"; color: window.cFg2; font.pixelSize: 12 }
                            Item { Layout.fillWidth: true } }
                        MouseArea { anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onEntered: tbtn.h = true; onExited: tbtn.h = false } }
                }

                // Theme toggle
                Rectangle { Layout.fillWidth: true; implicitHeight: 38; radius: 10; color: "transparent"; width: sidebar.width - 16; anchors.leftMargin: 8
                    RowLayout { anchors.fill: parent; anchors.leftMargin: 12; spacing: 8
                        Text { text: darkMode ? "☀" : "🌙"; font.pixelSize: 13 }
                        Text { text: darkMode ? "Light mode" : "Dark mode"; color: window.cFg2; font.pixelSize: 11 } }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: darkMode = !darkMode }
                }
            }
        }

        Item { width: 10; anchors.top: parent.top; anchors.bottom: parent.bottom }

        // CENTER: Chat
        ChatPanel {
            id: chatPanel
            anchors.top: parent.top; anchors.bottom: parent.bottom
            anchors.left: sidebar.right; anchors.leftMargin: 10
            anchors.right: filePanel.left; anchors.rightMargin: 10
        }

        // RIGHT: File panel
        Rectangle {
            id: filePanel
            anchors.top: parent.top; anchors.bottom: parent.bottom
            anchors.right: parent.right; width: 280; radius: 14; color: cBg0
            border.color: cBg3; border.width: 1; clip: true
            anchors.rightMargin: viewerSlot.viewerVisible ? 430 : 0
            Behavior on anchors.rightMargin { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }

            ListView {
                id: fileList
                anchors.fill: parent; anchors.topMargin: 10; anchors.leftMargin: 10
                anchors.rightMargin: 10; anchors.bottomMargin: 0
                clip: true; boundsBehavior: Flickable.StopAtBounds
                model: bridge.fileTree; spacing: 2

                delegate: Rectangle {
                    width: fileList.width; implicitHeight: 30; radius: 8
                    color: {
                        if (modelData.path === window.selectedPath) return Qt.alpha(window.cAccent, 0.12)
                        if (hovered) return window.cBg2
                        return "transparent"
                    }
                    property bool hovered: false

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 8 + (modelData.depth ? modelData.depth * 14 : 0)
                        anchors.rightMargin: 8
                        spacing: 6

                        // Arrow placeholder — space always reserved for alignment
                        Rectangle {
                            width: 12; height: 12
                            color: "transparent"
                            Text {
                                anchors.centerIn: parent
                                visible: modelData.isDir
                                text: modelData.expanded ? "▼" : "▶"
                                color: window.cFg3
                                font.pixelSize: 8
                            }
                        }
                        Text { text: modelData.isDir ? "📂" : "📄"; font.pixelSize: 11 }
                        Text { text: modelData.name; color: window.cFg1; font.pixelSize: 12; elide: Text.ElideRight; Layout.fillWidth: true }
                    }

                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; hoverEnabled: true
                        onEntered: parent.hovered = true
                        onExited: parent.hovered = false
                        onClicked: {
                            if (modelData.isDir) {
                                bridge.toggleDirectory(modelData.path)
                            } else {
                                window.selectedPath = modelData.path
                                bridge.openFile(modelData.path)
                            }
                        }
                    }
                }
            }
        }

        // Viewer — slides from right
        Rectangle {
            id: viewerSlot
            anchors.top: parent.top; anchors.bottom: parent.bottom
            anchors.right: parent.right; width: 420; color: "transparent"; clip: true

            property bool viewerVisible: bridge.fileViewerPath !== ""
            x: viewerVisible ? 0 : width + 12
            visible: viewerVisible || x < width
            Behavior on x { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }

            Rectangle { anchors.fill: parent; radius: 16; color: cBg0; border.color: cBg3; border.width: 1; clip: true
                Rectangle { anchors.fill: parent; anchors.margins: -2; radius: 18; z: -1
                    color: darkMode ? Qt.rgba(0,0,0,0.35) : Qt.rgba(0,0,0,0.08) }

                Rectangle { id: viewerTitleBar; width: parent.width; height: 44; color: cBg0
                    RowLayout { anchors.fill: parent; anchors.leftMargin: 16; anchors.rightMargin: 8; spacing: 10
                        Text { text: "📄"; font.pixelSize: 14 }
                        Text { text: bridge.fileViewerPath || ""; color: cFg1; font.pixelSize: 13; font.weight: Font.DemiBold; elide: Text.ElideRight; Layout.fillWidth: true }
                        Rectangle { width: 30; height: 30; radius: 8; color: cBg2; border.color: cBg3
                            Text { anchors.centerIn: parent; text: "✕"; color: cFg2; font.pixelSize: 13 }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: bridge.closeFileViewer() } } }
                    Rectangle { anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right; height: 1; color: cBg3 } }

                Flickable { id: viewerFlick; anchors.top: viewerTitleBar.bottom; anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
                    contentWidth: viewerText.implicitWidth; contentHeight: viewerText.implicitHeight; clip: true; boundsBehavior: Flickable.StopAtBounds; flickableDirection: Flickable.VerticalFlick
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AlwaysOn; parent: viewerFlick.parent; anchors.right: viewerFlick.right; anchors.top: viewerFlick.top; anchors.bottom: viewerFlick.bottom; anchors.margins: 4 }
                    Text { id: viewerText; width: viewerFlick.width - 28; x: 16; y: 8; text: bridge.fileViewerContent || ""; color: cFg1; font.pixelSize: 12; font.family: "Consolas"; wrapMode: Text.Wrap }
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
