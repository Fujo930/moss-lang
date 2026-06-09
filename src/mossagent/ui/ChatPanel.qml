import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "theme.js" as Theme

// Claude-style chat panel with message bubbles, typing indicator, and tool call cards.

Rectangle {
    id: root
    color: Theme.bg0

    // Self-contained color properties
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
    property color cAmber: Theme.amber
    property color cBlue: Theme.blue

    property var messages: []
    property bool typing: false

    function addMessage(role, content, toolCall) {
        messages.push({role: role, content: content, toolCall: toolCall || null, time: new Date()})
        messages = messages
        messageList.positionViewAtEnd()
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        ListView {
            id: messageList
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: Theme.space_sm
            model: root.messages
            boundsBehavior: Flickable.StopAtBounds

            delegate: Item {
                width: messageList.width
                height: contentColumn.height + Theme.space_sm

                ColumnLayout {
                    id: contentColumn
                    width: parent.width - Theme.space_lg * 2
                    x: Theme.space_lg
                    spacing: Theme.space_xs

                    Text {
                        text: modelData.role === "user" ? "You" : 
                              modelData.role === "system" ? "System" : "Corvus"
                        color: modelData.role === "user" ? root.cAccent :
                               modelData.role === "system" ? root.cAmber : root.cGreen
                        font.pixelSize: Theme.font_size_xs
                        font.family: Theme.font_sans
                        font.weight: Font.DemiBold
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: messageText.implicitHeight + Theme.space_md * 2
                        radius: Theme.radius_md
                        color: modelData.role === "user" ? Qt.darker(root.cAccent, 7.0) :
                               modelData.role === "system" ? Qt.darker(root.cAmber, 10.0) :
                               root.cBg2
                        border.color: modelData.role === "user" ? Qt.alpha(root.cAccent, 0.3) :
                                     modelData.role === "system" ? Qt.alpha(root.cAmber, 0.3) :
                                     root.cBg3
                        border.width: 1

                        Text {
                            id: messageText
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.margins: Theme.space_md
                            text: modelData.content
                            color: root.cFg1
                            font.pixelSize: Theme.font_size_md
                            font.family: Theme.font_sans
                            wrapMode: Text.WordWrap
                        }
                    }

                    // Tool call card
                    Rectangle {
                        visible: modelData.toolCall !== null && modelData.toolCall !== undefined
                        Layout.fillWidth: true
                        implicitHeight: visible ? toolCallContent.height + Theme.space_sm * 2 : 0
                        radius: Theme.radius_sm
                        color: Qt.darker(root.cBlue, 12.0)
                        border.color: Qt.alpha(root.cBlue, 0.3)
                        border.width: 1

                        ColumnLayout {
                            id: toolCallContent
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.margins: Theme.space_sm
                            spacing: Theme.space_xs

                            RowLayout {
                                spacing: Theme.space_sm
                                Text { text: "\uD83D\uDD27"; font.pixelSize: Theme.font_size_sm }
                                Text {
                                    text: modelData.toolCall ? modelData.toolCall.tool || "tool" : ""
                                    color: root.cBlue
                                    font.pixelSize: Theme.font_size_sm
                                    font.family: Theme.font_mono
                                    font.weight: Font.DemiBold
                                }
                                Text {
                                    text: modelData.toolCall && modelData.toolCall.ok !== undefined ? 
                                          (modelData.toolCall.ok ? "\u2705" : "\u274C") : ""
                                    font.pixelSize: Theme.font_size_sm
                                }
                            }

                            Text {
                                visible: modelData.toolCall && modelData.toolCall.output
                                text: modelData.toolCall ? (modelData.toolCall.output || "").substring(0, 200) : ""
                                color: root.cFg2
                                font.pixelSize: Theme.font_size_xs
                                font.family: Theme.font_mono
                                wrapMode: Text.WordWrap
                                maximumLineCount: 3
                                elide: Text.ElideRight
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
                    color: root.cBg2
                    border.color: root.cBg3

                    Row {
                        anchors.centerIn: parent
                        spacing: 4
                        Repeater {
                            model: 3
                            Rectangle {
                                width: 6; height: 6; radius: 3
                                color: root.cFg2
                            }
                        }
                    }
                }
            }
        }

        // Input area
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

                TextArea {
                    id: chatInput
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    placeholderText: "Ask Corvus or give a task..."
                    placeholderTextColor: root.cFg3
                    color: root.cFg1
                    font.pixelSize: Theme.font_size_md
                    font.family: Theme.font_sans
                    background: Rectangle { color: "transparent" }
                    wrapMode: TextArea.Wrap

                    Keys.onReturnPressed: {
                        if (event.modifiers & Qt.ShiftModifier) return
                        var text = chatInput.text.trim()
                        if (text.length > 0) {
                            root.addMessage("user", text, null)
                            bridge.sendChat(text)
                            chatInput.text = ""
                        }
                    }
                }

                Rectangle {
                    width: 36; height: 36; radius: 18
                    color: root.cAccent
                    opacity: chatInput.text.trim().length > 0 ? 1.0 : 0.4
                    Text { anchors.centerIn: parent; text: "\u2192"; color: "white"; font.pixelSize: 18 }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            var text = chatInput.text.trim()
                            if (text.length > 0) {
                                root.addMessage("user", text, null)
                                bridge.sendChat(text)
                                chatInput.text = ""
                            }
                        }
                    }
                }
            }
        }
    }
}
