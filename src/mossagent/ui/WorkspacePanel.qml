import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    color: "transparent"

    property string selectedPath: ""

    ColumnLayout {
        anchors.fill: parent; anchors.margins: 10; spacing: 8; z: 1

        // ── Clear selection when viewer closes ──────────────
        Connections {
            target: bridge
            function onProgressChanged(msg) {
                if (bridge.fileViewerPath === "") {
                    root.selectedPath = ""
                }
            }
        }

        // ── Files card ──────────────────────────────────────
        Rectangle {
            id: filesCard
            property bool cardHovered: false
            Layout.fillWidth: true; Layout.fillHeight: true; radius: 12
            color: window.cBg0; border.color: window.cBg3; border.width: 1

            Rectangle {
                anchors.fill: parent; anchors.margins: -2; radius: 14; z: -1
                color: window.darkMode ? Qt.rgba(0,0,0,0.2) : Qt.rgba(0,0,0,0.06)
                opacity: filesCard.cardHovered ? 1.0 : 0.0
                Behavior on opacity { NumberAnimation { duration: 200 } }
            }

            Column {
                anchors.fill: parent

                Rectangle {
                    width: parent.width; height: 36; color: "transparent"
                    RowLayout {
                        anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 12; spacing: 6
                        Text { text: "📁"; font.pixelSize: 12 }
                        Text { text: "Files"; color: window.cFg1; font.pixelSize: 13; font.weight: Font.DemiBold }
                        Item { Layout.fillWidth: true }
                        Text {
                            text: "⟳"; color: window.cFg2; font.pixelSize: 14
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: bridge.refreshWorkspace() }
                        }
                    }
                }

                ListView {
                    id: fileList
                    width: parent.width; height: parent.height - 36; clip: true
                    model: bridge.fileTree; spacing: 1

                    delegate: Rectangle {
                        width: fileList.width - (modelData.depth ? modelData.depth * 16 : 0)
                        x: modelData.depth ? modelData.depth * 16 : 0
                        implicitHeight: 30; radius: 8
                        color: modelData.path === root.selectedPath ? Qt.alpha(window.cAccent, 0.12) : "transparent"

                        RowLayout {
                            anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 8; spacing: 6
                            Text { text: modelData.isDir ? "📂" : "📄"; font.pixelSize: 11 }
                            Text {
                                text: modelData.name; color: window.cFg1; font.pixelSize: 12
                                elide: Text.ElideRight; Layout.fillWidth: true
                            }
                        }

                        MouseArea {
                            anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                root.selectedPath = modelData.path
                                if (modelData.isDir) bridge.toggleDirectory(modelData.path)
                                else bridge.openFile(modelData.path)
                            }
                        }
                    }
                }
            }

            MouseArea {
                anchors.fill: parent; z: 2; hoverEnabled: true; acceptedButtons: Qt.NoButton
                onEntered: filesCard.cardHovered = true
                onExited: filesCard.cardHovered = false
            }
        }

        // ── Settings ────────────────────────────────────────
        Rectangle {
            id: settingsCard; property bool cardHovered: false
            Layout.fillWidth: true; implicitHeight: 44; radius: 12
            color: window.cBg0; border.color: window.cBg3; border.width: 1
            Rectangle { anchors.fill: parent; anchors.margins: -2; radius: 14; z: -1
                color: window.darkMode ? Qt.rgba(0,0,0,0.2) : Qt.rgba(0,0,0,0.06)
                opacity: settingsCard.cardHovered ? 1.0 : 0.0; Behavior on opacity { NumberAnimation { duration: 200 } } }
            RowLayout { anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 12; spacing: 8
                Text { text: "⚙️"; font.pixelSize: 12 }
                Text { text: "Settings"; color: window.cFg1; font.pixelSize: 13 }
                Item { Layout.fillWidth: true } }
            MouseArea { anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                onEntered: settingsCard.cardHovered = true; onExited: settingsCard.cardHovered = false }
        }

        // ── History ─────────────────────────────────────────
        Rectangle {
            id: historyCard; property bool cardHovered: false
            Layout.fillWidth: true; implicitHeight: 44; radius: 12
            color: window.cBg0; border.color: window.cBg3; border.width: 1
            Rectangle { anchors.fill: parent; anchors.margins: -2; radius: 14; z: -1
                color: window.darkMode ? Qt.rgba(0,0,0,0.2) : Qt.rgba(0,0,0,0.06)
                opacity: historyCard.cardHovered ? 1.0 : 0.0; Behavior on opacity { NumberAnimation { duration: 200 } } }
            RowLayout { anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 12; spacing: 8
                Text { text: "🕐"; font.pixelSize: 12 }
                Text { text: "History"; color: window.cFg1; font.pixelSize: 13 }
                Item { Layout.fillWidth: true } }
            MouseArea { anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                onEntered: historyCard.cardHovered = true; onExited: historyCard.cardHovered = false }
        }

        // ── Trash ───────────────────────────────────────────
        Rectangle {
            id: trashCard; property bool cardHovered: false
            Layout.fillWidth: true; implicitHeight: 44; radius: 12
            color: window.cBg0; border.color: window.cBg3; border.width: 1
            Rectangle { anchors.fill: parent; anchors.margins: -2; radius: 14; z: -1
                color: window.darkMode ? Qt.rgba(0,0,0,0.2) : Qt.rgba(0,0,0,0.06)
                opacity: trashCard.cardHovered ? 1.0 : 0.0; Behavior on opacity { NumberAnimation { duration: 200 } } }
            RowLayout { anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 12; spacing: 8
                Text { text: "🗑️"; font.pixelSize: 12 }
                Text { text: "Trash"; color: window.cFg1; font.pixelSize: 13 }
                Item { Layout.fillWidth: true } }
            MouseArea { anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                onEntered: trashCard.cardHovered = true; onExited: trashCard.cardHovered = false }
        }
    }
}
