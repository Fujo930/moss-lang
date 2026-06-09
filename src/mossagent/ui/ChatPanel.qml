import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Chat panel — main surface. Reads all colors from window.

Rectangle {
    id: root
    color: window.cBg0

    property bool typing: false

    ListModel { id: chatModel }

    function addMessage(role, content, toolCall) {
        chatModel.append({role: role, content: content, toolCallStr: toolCall ? JSON.stringify(toolCall) : ""})
        Qt.callLater(function() { messageList.positionViewAtEnd() })
    }

    ColumnLayout {
        anchors.fill: parent; spacing: 0

        ListView {
            id: messageList
            Layout.fillWidth: true; Layout.fillHeight: true; clip: true; spacing: 8
            model: chatModel; boundsBehavior: Flickable.StopAtBounds

            delegate: Item {
                width: messageList.width
                height: contentColumn.height + 8

                ColumnLayout {
                    id: contentColumn
                    width: parent.width - 48; x: 24; spacing: 4

                    Text {
                        text: model.role === "user" ? "You" : (model.role === "system" ? "System" : "Corvus")
                        color: model.role === "user" ? window.cAccent : (model.role === "system" ? window.cAmber : window.cGreen)
                        font.pixelSize: 11; font.weight: Font.DemiBold
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: bubbleText.implicitHeight + 24
                        radius: 10
                        color: model.role === "user" ? Qt.rgba(124/255, 58/255, 237/255, 0.08) :
                               model.role === "system" ? Qt.rgba(210/255, 153/255, 34/255, 0.08) : window.cBg2
                        border.color: model.role === "user" ? Qt.rgba(124/255, 58/255, 237/255, 0.2) :
                                     model.role === "system" ? Qt.rgba(210/255, 153/255, 34/255, 0.2) : window.cBg3
                        border.width: 1

                        Text {
                            id: bubbleText
                            anchors.fill: parent; anchors.margins: 12
                            text: model.content; color: window.cFg1
                            font.pixelSize: 13; wrapMode: Text.WordWrap
                        }
                    }
                }
            }
        }

        // Input bar
        Rectangle {
            Layout.fillWidth: true; implicitHeight: 56
            color: window.cBg1; border.color: window.cBg3; border.width: 1

            RowLayout {
                anchors.fill: parent; anchors.margins: 8; spacing: 8

                TextField {
                    id: chatInput
                    Layout.fillWidth: true; Layout.fillHeight: true
                    placeholderText: "Ask Corvus or give a task..."
                    placeholderTextColor: window.cFg3; color: window.cFg1
                    font.pixelSize: 13; verticalAlignment: TextField.AlignVCenter
                    background: Rectangle {
                        color: window.cBg0; border.color: window.cBg3; border.width: 1; radius: 10
                    }

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
                    color: chatInput.text.trim().length > 0 ? window.cAccent : window.cBg3
                    Text { anchors.centerIn: parent; text: "→"; color: "white"; font.pixelSize: 18 }
                    MouseArea {
                        anchors.fill: parent; cursorShape: Qt.PointingHandCursor
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
