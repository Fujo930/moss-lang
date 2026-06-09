import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "theme.js" as Theme

Rectangle {
    id: root
    color: Theme.bg1

    property color cBg1: Theme.bg1
    property color cBg2: Theme.bg2
    property color cBg3: Theme.bg3
    property color cFg1: Theme.fg1
    property color cFg2: Theme.fg2
    property color cFg3: Theme.fg3
    property color cAccent: Theme.accent
    property color cGreen: Theme.green
    property color cBlue: Theme.blue

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // Section: Files
        Rectangle {
            Layout.fillWidth: true; implicitHeight: 32
            color: root.cBg2; border.color: root.cBg3; border.width: 1
            RowLayout {
                anchors.fill: parent; anchors.leftMargin: Theme.space_md; spacing: Theme.space_sm
                Text { text: "\uD83D\uDCC1"; font.pixelSize: Theme.font_size_sm }
                Text { text: "Workspace"; color: root.cFg1; font.pixelSize: Theme.font_size_sm; font.family: Theme.font_sans; font.weight: Font.DemiBold }
                Item { Layout.fillWidth: true }
                Text {
                    text: "\u27F3"; color: root.cFg2; font.pixelSize: Theme.font_size_sm
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: bridge.refreshWorkspace() }
                }
            }
        }

        ListView {
            id: fileList
            Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 100
            clip: true; model: bridge.fileTree; spacing: 0
            delegate: Rectangle {
                width: fileList.width; implicitHeight: 28
                color: mouseArea.containsMouse ? Qt.alpha(root.cBg3, 0.5) : "transparent"
                RowLayout {
                    anchors.fill: parent; anchors.leftMargin: Theme.space_md; anchors.rightMargin: Theme.space_sm; spacing: Theme.space_sm
                    Text { text: modelData.isDir ? "\uD83D\uDCC2" : "\uD83D\uDCC4"; font.pixelSize: Theme.font_size_sm }
                    Text { text: modelData.name; color: root.cFg1; font.family: modelData.isDir ? Theme.font_sans : Theme.font_mono; font.pixelSize: Theme.font_size_sm; elide: Text.ElideRight; Layout.fillWidth: true }
                }
                MouseArea {
                    id: mouseArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: { if (modelData.isDir) bridge.toggleDirectory(modelData.path); else bridge.openFile(modelData.path) }
                }
            }
        }

        // Section: Memory
        Rectangle {
            Layout.fillWidth: true; implicitHeight: 32
            color: root.cBg2; border.color: root.cBg3; border.width: 1
            RowLayout {
                anchors.fill: parent; anchors.leftMargin: Theme.space_md; spacing: Theme.space_sm
                Text { text: "\uD83E\uDDE0"; font.pixelSize: Theme.font_size_sm }
                Text { text: "Memory"; color: root.cFg1; font.pixelSize: Theme.font_size_sm; font.family: Theme.font_sans; font.weight: Font.DemiBold }
            }
        }

        ListView {
            id: memoryList
            Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 80
            clip: true; model: bridge.memories; spacing: Theme.space_xs
            delegate: Rectangle {
                width: memoryList.width; implicitHeight: memText.implicitHeight + Theme.space_xs * 2
                color: "transparent"; border.color: root.cBg3; border.width: 1; radius: Theme.radius_sm
                Text {
                    id: memText; anchors.fill: parent; anchors.margins: Theme.space_xs
                    text: modelData.key + ": " + modelData.value
                    color: root.cFg2; font.pixelSize: Theme.font_size_xs; font.family: Theme.font_sans
                    wrapMode: Text.WordWrap; maximumLineCount: 3; elide: Text.ElideRight
                }
            }
        }
    }

    // Action buttons
    RowLayout {
        anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right
        anchors.margins: Theme.space_sm; spacing: Theme.space_sm

        Rectangle {
            implicitWidth: btnText1.implicitWidth + Theme.space_md * 2; implicitHeight: 28; radius: Theme.radius_sm
            color: Qt.darker(root.cGreen, 10.0); border.color: Qt.alpha(root.cGreen, 0.4); border.width: 1
            Text { id: btnText1; anchors.centerIn: parent; text: "\uD83D\uDD0D Verify"; color: root.cGreen; font.pixelSize: Theme.font_size_xs; font.family: Theme.font_sans; font.weight: Font.DemiBold }
            MouseArea {
                anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                onClicked: { var s = bridge.getActiveSource(); if (s) bridge.runVerify(s) }
            }
        }
        Rectangle {
            implicitWidth: btnText2.implicitWidth + Theme.space_md * 2; implicitHeight: 28; radius: Theme.radius_sm
            color: Qt.darker(root.cBlue, 10.0); border.color: Qt.alpha(root.cBlue, 0.4); border.width: 1
            Text { id: btnText2; anchors.centerIn: parent; text: "\u25B6 Run"; color: root.cBlue; font.pixelSize: Theme.font_size_xs; font.family: Theme.font_sans; font.weight: Font.DemiBold }
            MouseArea {
                anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                onClicked: { var s = bridge.getActiveSource(); if (s) bridge.runExecute(s) }
            }
        }
        Rectangle {
            implicitWidth: btnText3.implicitWidth + Theme.space_md * 2; implicitHeight: 28; radius: Theme.radius_sm
            color: Qt.darker(root.cAccent, 10.0); border.color: Qt.alpha(root.cAccent, 0.4); border.width: 1
            Text { id: btnText3; anchors.centerIn: parent; text: "\u2728 Gen"; color: root.cAccent; font.pixelSize: Theme.font_size_xs; font.family: Theme.font_sans; font.weight: Font.DemiBold }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: bridge.promptGenerate() }
        }
    }
}
