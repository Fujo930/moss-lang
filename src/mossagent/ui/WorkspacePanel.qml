import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Workspace — card-style file browser + memory. Reads all colors from window.

Rectangle {
    id: root
    color: window.cBg1

    ColumnLayout {
        anchors.fill: parent; anchors.margins: 10; spacing: 8

        // ── Files card ──────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true; Layout.fillHeight: true
            radius: 12; color: window.cBg0; border.color: window.cBg3; border.width: 1

            Column {
                anchors.fill: parent

                // Header
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
                    model: bridge.fileTree; spacing: 2

                    delegate: Rectangle {
                        width: fileList.width - 12; x: 6; implicitHeight: 30; radius: 8
                        color: mouseArea.containsMouse ? window.cBg2 : "transparent"

                        RowLayout {
                            anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 8; spacing: 6
                            Text { text: modelData.isDir ? "📂" : "📄"; font.pixelSize: 11 }
                            Text {
                                text: modelData.name; color: window.cFg1; font.pixelSize: 12
                                elide: Text.ElideRight; Layout.fillWidth: true
                            }
                        }

                        MouseArea {
                            id: mouseArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (modelData.isDir) bridge.toggleDirectory(modelData.path)
                                else bridge.openFile(modelData.path)
                            }
                        }
                    }
                }
            }
        }

        // ── Settings card ──────────────────────────────────
        Rectangle {
            Layout.fillWidth: true; implicitHeight: 44; radius: 12
            color: window.cBg0; border.color: window.cBg3; border.width: 1

            RowLayout {
                anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 12; spacing: 8
                Text { text: "⚙️"; font.pixelSize: 12 }
                Text { text: "Settings"; color: window.cFg1; font.pixelSize: 13 }
                Item { Layout.fillWidth: true }
            }
        }

        // ── History card ────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true; implicitHeight: 44; radius: 12
            color: window.cBg0; border.color: window.cBg3; border.width: 1

            RowLayout {
                anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 12; spacing: 8
                Text { text: "🕐"; font.pixelSize: 12 }
                Text { text: "History"; color: window.cFg1; font.pixelSize: 13 }
                Item { Layout.fillWidth: true }
            }
        }

        // ── Trash card ──────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true; implicitHeight: 44; radius: 12
            color: window.cBg0; border.color: window.cBg3; border.width: 1

            RowLayout {
                anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 12; spacing: 8
                Text { text: "🗑️"; font.pixelSize: 12 }
                Text { text: "Trash"; color: window.cFg1; font.pixelSize: 13 }
                Item { Layout.fillWidth: true }
            }
        }
    }
}
