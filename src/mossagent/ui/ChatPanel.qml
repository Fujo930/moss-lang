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

            // ── Welcome canvas ─────────────────────────────
            Canvas {
                id: welcomeCanvas
                anchors.fill: parent
                visible: chatModel.count === 0

                property var languages: [
                    "Bonjour, l'ère de l'IA",
                    "Hallo, KI-Zeitalter",
                    "こんにちは、AI時代",
                    "안녕, AI 시대",
                    "Hola, era de la IA",
                    "Olá, era da IA",
                    "Ciao, era dell'IA",
                    "Привет, эпоха ИИ",
                    "مرحباً، عصر الذكاء",
                    "Hallå, AI-eran",
                    "Hej, AI-tidsalder",
                    "नमस्ते, AI युग",
                    "שלום, עידן ה-AI",
                    "Salut, ère de l'IA",
                    "สวัสดี, ยุค AI",
                    "Ahoj, éro AI",
                    "Γεια, εποχή AI",
                    "Merhaba, YZ çağı",
                    "Xin chào, kỷ nguyên AI",
                    "Hei, AI-aikakausi"
                ]

                // Organic scatter offsets — balanced but not geometric
                property var scatterX: [
                     -0.72,  0.65, -0.45,  0.55, -0.85,
                      0.38, -0.58,  0.78, -0.28,  0.82,
                     -0.62,  0.42, -0.35,  0.70, -0.75,
                      0.48, -0.52,  0.60, -0.68,  0.32
                ]
                property var scatterY: [
                     -0.55, -0.48,  0.50, -0.35,  0.28,
                     -0.62,  0.38, -0.30,  0.58,  0.10,
                      0.42, -0.08, -0.45,  0.45, -0.15,
                      0.35, -0.38, -0.52,  0.20,  0.55
                ]

                property int tick: 0
                property real titleOpac: 0.0

                Timer {
                    interval: 50
                    running: welcomeCanvas.visible
                    repeat: true
                    onTriggered: {
                        welcomeCanvas.tick++
                        if (welcomeCanvas.tick >= 4 && welcomeCanvas.titleOpac < 1.0)
                            welcomeCanvas.titleOpac = Math.min(1.0, welcomeCanvas.titleOpac + 0.06)
                        welcomeCanvas.requestPaint()
                    }
                }

                onVisibleChanged: { if (!visible) { tick = 0; titleOpac = 0.0 } }

                onPaint: {
                    var ctx = getContext("2d")
                    ctx.clearRect(0, 0, width, height)

                    var cx = width / 2, cy = height / 2
                    var rad = Math.min(width, height) * 0.20
                    var count = languages.length, now = tick

                    // Languages — each fades in over ~10 ticks (500ms)
                    for (var i = 0; i < count; i++) {
                        var start = i * 2
                        if (now < start) continue
                        var fade = Math.min(1.0, (now - start) / 6.0)
                        var opac = 0.50 * fade

                        var x = cx + scatterX[i] * rad * 0.75
                        var y = cy + scatterY[i] * rad * 0.65

                        ctx.globalAlpha = opac
                        ctx.fillStyle = window.darkMode ? "#8b949e" : "#656d76"
                        ctx.font = "300 11px 'Segoe UI'"
                        ctx.textAlign = "center"
                        ctx.fillText(languages[i], x, y)
                    }

                    ctx.globalAlpha = titleOpac
                    ctx.fillStyle = window.darkMode ? "#e6edf3" : "#1f2328"
                    ctx.font = "300 28px 'Segoe UI'"
                    ctx.textAlign = "center"
                    ctx.fillText("你好，AI时代", cx, cy - 6)

                    ctx.fillStyle = window.darkMode ? "#8b949e" : "#656d76"
                    ctx.font = "300 20px 'Segoe UI'"
                    ctx.fillText("Hi, AI Time", cx, cy + 24)
                    ctx.globalAlpha = 1.0
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
        anchors.bottomMargin: 10
        width: Math.min(parent.width - 48, 700); height: 48; radius: 12
        color: window.darkMode ? Qt.rgba(0, 0, 0, 0.35) : Qt.rgba(0, 0, 0, 0.06)
        z: 2
    }

    // Input box
    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 12
        width: Math.min(parent.width - 48, 700); height: 48; radius: 12
        color: window.cBg0
        border.color: window.darkMode ? Qt.rgba(139/255, 148/255, 158/255, 0.18) : Qt.rgba(0, 0, 0, 0.10)
        border.width: 1
        z: 2

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
