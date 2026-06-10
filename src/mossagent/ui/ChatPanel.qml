import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    color: window.cBg0
    radius: 12
    border.color: window.cBg3
    border.width: 1

    property bool typing: false
    property bool hovered: false

    // ── Hover shadow ──────────────────────────────────────
    Rectangle {
        anchors.fill: parent; anchors.margins: -2; radius: 14; z: -1
        color: window.darkMode ? Qt.rgba(0,0,0,0.2) : Qt.rgba(0,0,0,0.06)
        opacity: root.hovered ? 1.0 : 0.0
        Behavior on opacity { NumberAnimation { duration: 200 } }
    }

    ListModel { id: chatModel }

    function addMessage(role, content, toolCall) {
        chatModel.append({role: role, content: content, toolCallStr: toolCall ? JSON.stringify(toolCall) : ""})
        Qt.callLater(function() { messageList.positionViewAtEnd() })
    }
    MouseArea {
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 64
        hoverEnabled: true
        acceptedButtons: Qt.NoButton
        onEntered: root.hovered = true
        onExited: root.hovered = false
    }

    ColumnLayout {
        anchors.fill: parent; spacing: 0; z: 1

        ListView {
            id: messageList
            Layout.fillWidth: true; Layout.fillHeight: true; clip: true; spacing: 8
            model: chatModel; boundsBehavior: Flickable.StopAtBounds
            topMargin: 16
            bottomMargin: 64

            // ── Empty-state greeting ───────────────────────
            Item {
                id: emptyGreeting
                anchors.fill: parent
                anchors.bottomMargin: 72   // room for input bar
                z: -1
                opacity: chatModel.count === 0 ? 1 : 0
                visible: opacity > 0.01
                Behavior on opacity { NumberAnimation { duration: 300 } }

                Column {
                    anchors.centerIn: parent
                    spacing: 6
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "你好，AI时代"
                        color: window.cFg1
                        font.pixelSize: 28
                        font.weight: Font.Light
                    }
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "Hi, AI Time"
                        color: window.cFg2
                        font.pixelSize: 18
                        font.weight: Font.Light
                    }
                }
            }

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
    // Shadow underlay
    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: chatModel.count === 0 ? parent.height * 0.38 - 2 : 10
        width: Math.min(parent.width - 48, 700); height: 48; radius: 12
        color: window.darkMode ? Qt.rgba(0, 0, 0, 0.35) : Qt.rgba(0, 0, 0, 0.06)
        z: 2

        Behavior on anchors.bottomMargin { NumberAnimation { duration: 350; easing.type: Easing.OutCubic } }
    }

    // Input box
    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        // When empty: sits right below greeting, when chatting: sticks to bottom
        anchors.bottomMargin: chatModel.count === 0 ? parent.height * 0.38 : 12
        width: Math.min(parent.width - 48, 700); height: 48; radius: 12
        color: window.cBg0
        border.color: window.darkMode ? Qt.rgba(139/255, 148/255, 158/255, 0.18) : Qt.rgba(0, 0, 0, 0.10)
        border.width: 1
        z: 2

        Behavior on anchors.bottomMargin { NumberAnimation { duration: 350; easing.type: Easing.OutCubic } }

        RowLayout {
            anchors.fill: parent; anchors.leftMargin: 16; anchors.rightMargin: 8; spacing: 8

            TextField {
                id: chatInput
                Layout.fillWidth: true; Layout.fillHeight: true
                placeholderText: "Ask Corvus or give a task..."
                placeholderTextColor: window.cFg3; color: window.cFg1
                font.pixelSize: 13; verticalAlignment: TextField.AlignVCenter
                background: Rectangle { color: "transparent" }

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

                Canvas {
                    anchors.centerIn: parent; width: 14; height: 12
                    onPaint: {
                        var ctx = getContext("2d")
                        ctx.clearRect(0, 0, width, height)
                        ctx.strokeStyle = "white"; ctx.lineWidth = 2; ctx.lineCap = "round"; ctx.lineJoin = "round"
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
