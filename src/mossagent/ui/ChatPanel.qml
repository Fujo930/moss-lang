import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Chat panel — main surface. Input bar floats above the bottom.

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
            bottomMargin: 64  // space for floating input bar

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
    }

    // ── Floating input bar ──────────────────────────────────
    // Shadow layer
    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 10
        width: Math.min(parent.width - 48, 700)
        height: 48
        radius: 12
        color: window.darkMode ? Qt.rgba(0, 0, 0, 0.35) : Qt.rgba(0, 0, 0, 0.06)
    }

    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 12
        width: Math.min(parent.width - 48, 700)
        height: 48
        radius: 12
        color: window.cBg0
        border.color: window.darkMode ? Qt.rgba(139/255, 148/255, 158/255, 0.18) : Qt.rgba(0, 0, 0, 0.10)
        border.width: 1

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 16; anchors.rightMargin: 8
            spacing: 8

            TextField {
                id: chatInput
                Layout.fillWidth: true; Layout.fillHeight: true
                placeholderText: "Ask Corvus or give a task..."
                placeholderTextColor: window.cFg3; color: window.cFg1
                font.pixelSize: 13; verticalAlignment: TextField.AlignVCenter
                background: null

                Keys.onReturnPressed: function(event) {
                    var text = chatInput.text.trim()
                    if (text.length === 0) return
                    root.addMessage("user", text, "")
                    bridge.sendChat(text)
                    chatInput.text = ""
                }
            }

            Rectangle {
                width: 32; height: 32; radius: 8
                color: chatInput.text.trim().length > 0 ? window.cAccent : Qt.darker(window.cAccent, 3.0)

                // Chevron arrow — pure geometry, no font dependency
                Canvas {
                    anchors.centerIn: parent
                    width: 14; height: 12
                    onPaint: {
                        var ctx = getContext("2d")
                        ctx.clearRect(0, 0, width, height)
                        ctx.strokeStyle = "white"
                        ctx.lineWidth = 2
                        ctx.lineCap = "round"
                        ctx.lineJoin = "round"
                        ctx.beginPath()
                        ctx.moveTo(width * 0.3, height * 0.1)
                        ctx.lineTo(width * 0.85, height * 0.5)
                        ctx.lineTo(width * 0.3, height * 0.9)
                        ctx.stroke()
                    }
                }

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
