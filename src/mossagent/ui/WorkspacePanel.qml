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

            ColumnLayout {
                anchors.fill: parent; spacing: 0

                // Header
                Rectangle {
                    Layout.fillWidth: true; implicitHeight: 36; radius: 12
                    color: "transparent"

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
                    Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                    model: bridge.fileTree; spacing: 2
                    anchors.leftMargin: 6; anchors.rightMargin: 6

                    delegate: Rectangle {
                        width: fileList.width - 12; implicitHeight: 30; radius: 8
                        color: mouseArea.containsMouse ? window.cBg2 : "transparent"

                        RowLayout {
                            anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 8; spacing: 6
                            Text {
                                text: modelData.isDir ? "📂" : "📄"; font.pixelSize: 11
                            }
                            Text {
                                text: modelData.name; color: window.cFg1; font.pixelSize: 12
                                font.family: modelData.isDir ? "" : "Consolas"
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

        // ── Memory card ─────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true; implicitHeight: 120; radius: 12
            color: window.cBg0; border.color: window.cBg3; border.width: 1

            ColumnLayout {
                anchors.fill: parent; spacing: 0

                Rectangle {
                    Layout.fillWidth: true; implicitHeight: 36; radius: 12
                    color: "transparent"
                    RowLayout {
                        anchors.fill: parent; anchors.leftMargin: 12; spacing: 6
                        Text { text: "🧠"; font.pixelSize: 12 }
                        Text { text: "Memory"; color: window.cFg1; font.pixelSize: 13; font.weight: Font.DemiBold }
                    }
                }

                ListView {
                    id: memoryList
                    Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                    model: bridge.memories; spacing: 4
                    anchors.leftMargin: 12; anchors.rightMargin: 12

                    delegate: Rectangle {
                        width: memoryList.width - 24; implicitHeight: memText.implicitHeight + 12; radius: 8
                        color: window.cBg2

                        Text {
                            id: memText
                            anchors.fill: parent; anchors.margins: 6
                            text: modelData.key + ": " + modelData.value
                            color: window.cFg2; font.pixelSize: 11; wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight
                        }
                    }
                }
            }
        }

        // ── Action buttons row ──────────────────────────────
        RowLayout {
            Layout.fillWidth: true; spacing: 6

            Rectangle {
                Layout.fillWidth: true; implicitHeight: 30; radius: 10
                color: window.cGreen; opacity: 0.12
                border.color: Qt.rgba(26/255, 127/255, 55/255, 0.2); border.width: 1
                Text { anchors.centerIn: parent; text: "🔍 Verify"; color: window.cGreen; font.pixelSize: 11; font.weight: Font.DemiBold }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { var s = bridge.getActiveSource(); if (s) bridge.runVerify(s) } }
            }
            Rectangle {
                Layout.fillWidth: true; implicitHeight: 30; radius: 10
                color: window.cBlue; opacity: 0.12
                border.color: Qt.rgba(9/255, 105/255, 218/255, 0.2); border.width: 1
                Text { anchors.centerIn: parent; text: "▶ Run"; color: window.cBlue; font.pixelSize: 11; font.weight: Font.DemiBold }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { var s = bridge.getActiveSource(); if (s) bridge.runExecute(s) } }
            }
            Rectangle {
                Layout.fillWidth: true; implicitHeight: 30; radius: 10
                color: window.cAccent; opacity: 0.12
                border.color: Qt.rgba(124/255, 58/255, 237/255, 0.2); border.width: 1
                Text { anchors.centerIn: parent; text: "✨ Gen"; color: window.cAccent; font.pixelSize: 11; font.weight: Font.DemiBold }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: bridge.promptGenerate() }
            }
        }
    }
}
