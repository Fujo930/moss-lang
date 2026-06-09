import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "theme.js" as Theme

// Chat panel — main interaction surface. Uses ListModel for reliable updates.

Rectangle {
    id: root
    color: Theme.bg0

    property color cBg0: Theme.bg0
    property color cBg1: Theme.bg1
    property color cBg2: Theme.bg2
    property color cBg3: Theme.bg3
    property color cFg1: Theme.fg1
    property color cFg2: Theme.fg2
    property color cFg3: Theme.fg3
    property color cAccent: Theme.accent
    property color cGreen: Theme.green
    property color cRed: Theme.red
    property color cBlue: Theme.blue
    property color cAmber: Theme.amber

    property bool typing: false

    ListModel {
        id: chatModel
    }

    function addMessage(role, content, toolCall) {
        chatModel.append({role: role, content: content, toolCallStr: toolCall ? JSON.stringify(toolCall) : ""})
        // Scroll to bottom after model updates
        Qt.callLater(function() {
            messageList.positionViewAtEnd()
        })
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // Message list
        ListView {
            id: messageList
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: Theme.space_sm
            model: chatModel
            boundsBehavior: Flickable.StopAtBounds

            delegate: Item {
                width: messageList.width
                height: contentColumn.height + Theme.space_sm

                property string msgRole: model.role
                property string msgContent: model.content
                property bool isUser: msgRole === "user"
                property bool isSystem: msgRole === "system"
                property bool isTool: model.toolCallStr !== "" && model.toolCallStr !== undefined

                ColumnLayout {
                    id: contentColumn
                    width: parent.width - Theme.space_lg * 2
                    x: Theme.space_lg
                    spacing: Theme.space_xs

                    Text {
                        text: isUser ? "You" : (isSystem ? "System" : "Corvus")
                        color: isUser ? root.cAccent : (isSystem ? root.cAmber : root.cGreen)
                        font.pixelSize: Theme.font_size_xs
                        font.family: Theme.font_sans
                        font.weight: Font.DemiBold
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: bubbleText.implicitHeight + Theme.space_md * 2
                        radius: Theme.radius_md
                        color: isUser ? Qt.darker(root.cAccent, 7.0) :
                               isSystem ? Qt.darker(root.cAmber, 10.0) : root.cBg2
                        border.color: isUser ? Qt.alpha(root.cAccent, 0.3) :
                                     isSystem ? Qt.alpha(root.cAmber, 0.3) : root.cBg3
                        border.width: 1

                        Text {
                            id: bubbleText
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.margins: Theme.space_md
                            text: msgContent
                            color: root.cFg1
                            font.pixelSize: Theme.font_size_md
                            font.family: Theme.font_sans
                            wrapMode: Text.WordWrap
                        }
                    }

                    // Tool call indicator
                    Rectangle {
                        visible: isTool
                        Layout.fillWidth: true
                        implicitHeight: visible ? toolRow.height + Theme.space_sm * 2 : 0
                        radius: Theme.radius_sm
                        color: Qt.darker(root.cBlue, 12.0)
                        border.color: Qt.alpha(root.cBlue, 0.3)
                        border.width: 1

                        RowLayout {
                            id: toolRow
                            anchors.left: parent.left; anchors.right: parent.right
                            anchors.margins: Theme.space_sm; spacing: Theme.space_sm
                            Text { text: "\uD83D\uDD27"; font.pixelSize: Theme.font_size_sm }
                            Text {
                                text: "Tool used"
                                color: root.cBlue
                                font.pixelSize: Theme.font_size_sm
                                font.family: Theme.font_sans
                                font.weight: Font.DemiBold
                            }
                        }
                    }
                }
            }

            footer: Item {
                width: messageList.width
                height: root.typing ? 40 : 0
                visible: root.typing

                Rectangle {
                    anchors.centerIn: parent
                    width: 60; height: 28; radius: 14
                    color: root.cBg2; border.color: root.cBg3
                    Row {
                        anchors.centerIn: parent; spacing: 4
                        Repeater {
                            model: 3
                            Rectangle { width: 6; height: 6; radius: 3; color: root.cFg2 }
                        }
                    }
                }
            }
        }

        // Input bar
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 56
            color: root.cBg1
            border.color: root.cBg3
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.margins: Theme.space_sm
                spacing: Theme.space_sm

                TextField {
                    id: chatInput
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    placeholderText: "Ask Corvus or give a task..."
                    placeholderTextColor: root.cFg3
                    color: root.cFg1
                    font.pixelSize: Theme.font_size_md
                    font.family: Theme.font_sans
                    verticalAlignment: TextField.AlignVCenter
                    background: Rectangle { color: "transparent"; border.color: root.cBg3; border.width: 1; radius: Theme.radius_md }

                    Keys.onReturnPressed: function(event) {
                        var text = chatInput.text.trim()
                        if (text.length === 0) return
                        root.addMessage("user", text, "")
                        bridge.sendChat(text)
                        chatInput.text = ""
                    }
                }

                Rectangle {
                    width: 36; height: 36; radius: 18
                    color: chatInput.text.trim().length > 0 ? root.cAccent : Qt.darker(root.cAccent, 3.0)
                    Text { anchors.centerIn: parent; text: "\u2192"; color: "white"; font.pixelSize: 18 }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            var text = chatInput.text.trim()
                            if (text.length === 0) return
                            root.addMessage("user", text, "")
                            bridge.sendChat(text)
                            chatInput.text = ""
                        }
                    }
                }
            }
        }
    }
}
