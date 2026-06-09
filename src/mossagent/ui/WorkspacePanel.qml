import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "theme.js" as Theme

// Codex-style workspace panel: file tree + memory viewer.
// Top section: project file tree. Bottom section: Agent memory/context.

Rectangle {
    id: root
    color: parent ? parent.cBg1 : Theme.bg1

    property var fileTree: []
    property var memories: []

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ── Section header: Files ───────────────────────────
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 32
            color: root.cBg2
            border.color: root.cBg3
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: Theme.space_md
                spacing: Theme.space_sm

                Text {
                    text: "📁"
                    font.pixelSize: Theme.font_size_sm
                }
                Text {
                    text: "Workspace"
                    color: root.cFg1
                    font.pixelSize: Theme.font_size_sm
                    font.family: Theme.font_sans
                    font.weight: Font.DemiBold
                }
                Item { Layout.fillWidth: true }
                Text {
                    text: "⟳"
                    color: root.cFg2
                    font.pixelSize: Theme.font_size_sm
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: bridge.refreshWorkspace()
                    }
                }
            }
        }

        // ── File tree ────────────────────────────────────────
        ListView {
            id: fileList
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 100
            clip: true
            model: bridge.fileTree
            spacing: 0

            delegate: Rectangle {
                width: fileList.width
                implicitHeight: 28
                color: mouseArea.containsMouse ? Qt.alpha(root.cBg3, 0.5) : "transparent"

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Theme.space_md
                    anchors.rightMargin: Theme.space_sm
                    spacing: Theme.space_sm

                    Text {
                        text: modelData.isDir ? "📂" : "📄"
                        font.pixelSize: Theme.font_size_sm
                    }
                    Text {
                        text: modelData.name
                        color: root.cFg1
                        font.pixelSize: Theme.font_size_sm
                        font.family: modelData.isDir ? Theme.font_sans : Theme.font_mono
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                }

                MouseArea {
                    id: mouseArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (modelData.isDir) {
                            bridge.toggleDirectory(modelData.path)
                        } else {
                            bridge.openFile(modelData.path)
                        }
                    }
                }
            }
        }

        // ── Section header: Memory ───────────────────────────
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 32
            color: root.cBg2
            border.color: root.cBg3
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: Theme.space_md
                spacing: Theme.space_sm

                Text {
                    text: "🧠"
                    font.pixelSize: Theme.font_size_sm
                }
                Text {
                    text: "Memory"
                    color: root.cFg1
                    font.pixelSize: Theme.font_size_sm
                    font.family: Theme.font_sans
                    font.weight: Font.DemiBold
                }
            }
        }

        // ── Memory list ──────────────────────────────────────
        ListView {
            id: memoryList
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 80
            clip: true
            model: bridge.memories
            spacing: Theme.space_xs

            delegate: Rectangle {
                width: memoryList.width
                implicitHeight: memText.implicitHeight + Theme.space_xs * 2
                color: "transparent"
                border.color: root.cBg3
                border.width: 1
                radius: Theme.radius_sm

                Text {
                    id: memText
                    anchors.fill: parent
                    anchors.margins: Theme.space_xs
                    text: modelData.key + ": " + modelData.value
                    color: root.cFg2
                    font.pixelSize: Theme.font_size_xs
                    font.family: Theme.font_sans
                    wrapMode: Text.WordWrap
                    maximumLineCount: 3
                    elide: Text.ElideRight
                }
            }
        }
    }

    // ── Action buttons (bottom) ──────────────────────────────
    RowLayout {
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: Theme.space_sm
        spacing: Theme.space_sm

        actionButton {
            text: "🔍 Verify"
            accent: root.cGreen
            onClicked: {
                var src = bridge.getActiveSource()
                if (src) bridge.runVerify(src)
            }
        }
        actionButton {
            text: "▶ Run"
            accent: root.cBlue
            onClicked: {
                var src = bridge.getActiveSource()
                if (src) bridge.runExecute(src)
            }
        }
        actionButton {
            text: "✨ Gen"
            accent: root.cAccent
            onClicked: bridge.promptGenerate()
        }
    }

    component actionButton: Rectangle {
        property string text: ""
        property color accent: root.cAccent
        signal clicked()

        implicitWidth: textMetrics.width + Theme.space_md * 2
        implicitHeight: 28
        radius: Theme.radius_sm
        color: Qt.darker(accent, 10.0)
        border.color: Qt.alpha(accent, 0.4)
        border.width: 1

        Text {
            id: textMetrics
            anchors.centerIn: parent
            text: parent.text
            color: parent.accent
            font.pixelSize: Theme.font_size_xs
            font.family: Theme.font_sans
            font.weight: Font.DemiBold
        }

        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: parent.clicked()
        }
    }
}
