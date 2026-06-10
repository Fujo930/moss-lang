import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Welcome flow:
//   Phase 1: Doodle bg + "Hello" / "Welcome to Corvus" float up
//   Phase 2: Greeting slides up → API config card appears beneath
//   Phase 3: User enters key/model → confirm → greeting slides back
//   Phase 4: Card dissolves → welcomes fades out → main app shown
//
// Background doodles: canvas with a breathing cycle — circles expand
// from center outward then vanish and restart.  Constant subtle motion.

Rectangle {
    id: welcome
    anchors.fill: parent
    color: "#5b6e7a"

    // ── Breathing doodle background ──────────────────────────
    Canvas {
        id: doodleCanvas
        anchors.fill: parent

        property int frame: 0
        // breathingCycle: 0→1 (expand), then 1→0 (contract), repeat
        property real breathingCycle: 0.0
        property int cycleDir: 1

        Timer {
            interval: 50
            running: welcome.visible
            repeat: true
            onTriggered: {
                doodleCanvas.frame++
                // Breathe: oscillate between 0.0 and 1.0
                doodleCanvas.breathingCycle += 0.012 * doodleCanvas.cycleDir
                if (doodleCanvas.breathingCycle >= 1.0) { doodleCanvas.breathingCycle = 1.0; doodleCanvas.cycleDir = -1 }
                if (doodleCanvas.breathingCycle <= 0.0) { doodleCanvas.breathingCycle = 0.0; doodleCanvas.cycleDir = 1 }
                doodleCanvas.requestPaint()
            }
        }

        onPaint: {
            var ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)
            var w = width, h = height
            var seed = 42
            function rand() { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646 }

            var pulse = breathingCycle   // 0→1→0
            var centerMass = 0.4 + pulse * 0.6  // dots move outward with pulse

            // ── Scatter circles ──────────────────────────
            for (var i = 0; i < 22; i++) {
                var cx = (w * 0.5) + (rand() - 0.5) * w * centerMass * 1.2
                var cy = (h * 0.5) + (rand() - 0.5) * h * centerMass * 1.1
                var r = 4 + rand() * 26
                ctx.globalAlpha = (0.02 + rand() * 0.04) * (0.5 + pulse * 0.5)
                ctx.strokeStyle = "white"
                ctx.lineWidth = 0.5 + rand() * 1.0
                ctx.beginPath()
                if (rand() > 0.5) ctx.arc(cx, cy, r, 0, Math.PI * 2)
                else ctx.arc(cx, cy, r, rand() * Math.PI, rand() * Math.PI + 2.5)
                ctx.stroke()
            }

            // ── Wandering lines ──────────────────────────
            for (var j = 0; j < 5; j++) {
                var x0 = (w * 0.5) + (rand() - 0.5) * w * centerMass * 1.1
                var y0 = (h * 0.5) + (rand() - 0.5) * h * centerMass
                ctx.globalAlpha = (0.03 + rand() * 0.04) * (0.5 + pulse * 0.5)
                ctx.strokeStyle = "white"; ctx.lineWidth = 0.5
                ctx.beginPath(); ctx.moveTo(x0, y0)
                for (var k = 0; k < 5; k++) { x0 += (rand()-0.5)*160; y0 += (rand()-0.5)*120; ctx.lineTo(x0, y0) }
                ctx.stroke()
            }

            // ── Constellation dots ───────────────────────
            var dots = []
            for (var d = 0; d < 11; d++) {
                dots.push({x: (w*0.5)+(rand()-0.5)*w*centerMass*1.5, y: (h*0.5)+(rand()-0.5)*h*centerMass*1.3})
            }
            for (var di = 0; di < dots.length; di++) {
                ctx.globalAlpha = (0.10 + rand()*0.08) * (0.5 + pulse*0.5)
                ctx.fillStyle = "white"
                ctx.beginPath(); ctx.arc(dots[di].x, dots[di].y, 1.5+rand()*2.5, 0, Math.PI*2); ctx.fill()
                for (var dj = di+1; dj < dots.length; dj++) {
                    var dx = dots[di].x - dots[dj].x, dy = dots[di].y - dots[dj].y
                    if (Math.sqrt(dx*dx+dy*dy) < 160 && rand() > 0.6) {
                        ctx.globalAlpha = (0.02+rand()*0.03) * (0.5+pulse*0.5)
                        ctx.strokeStyle = "white"; ctx.lineWidth = 0.4
                        ctx.beginPath(); ctx.moveTo(dots[di].x, dots[di].y); ctx.lineTo(dots[dj].x, dots[dj].y); ctx.stroke()
                    }
                }
            }
            ctx.globalAlpha = 1.0
        }
    }

    // ── Greeting — centered initially, slides up ──────────────
    Item {
        id: greetingBlock
        anchors.horizontalCenter: parent.horizontalCenter
        width: 600; height: 120
        z: 2
        Component.onCompleted: { y = (welcome.height - 120) / 2 }

        Column {
            anchors.centerIn: parent; spacing: 18
            Text {
                id: helloLine
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Hello"; color: "white"
                font.pixelSize: 64; font.weight: Font.Thin; font.letterSpacing: -1
                opacity: 0; y: 30
            }
            Text {
                id: subtitleLine
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Welcome to Corvus"; color: Qt.rgba(1,1,1,0.55)
                font.pixelSize: 16; font.weight: Font.Light
                opacity: 0; y: 12
            }
        }
    }

    // ── API config card ───────────────────────────────────────
    Rectangle {
        id: configCard
        anchors.centerIn: parent
        width: 460
        height: 620
        radius: 20; clip: true
        color: Qt.rgba(1, 1, 1, 0.10)
        border.color: Qt.rgba(1, 1, 1, 0.18)
        border.width: 1
        opacity: 0; z: 2
        Behavior on opacity { NumberAnimation { duration: 400 } }

        property bool customVisible: false

        ColumnLayout {
            id: innerLayout
            width: parent.width - 56
            x: 28; y: 28
            spacing: 16

                Text {
                    text: "Choose your AI provider"
                    color: "white"; font.pixelSize: 16; font.weight: Font.DemiBold
                    Layout.fillWidth: true
                }

                // ── Provider list ──────────────────────────
                Column {
                    id: providerList
                    Layout.fillWidth: true
                    spacing: 8

                    // Selection state
                    property string selectedKey: ""

                    function select(key) {
                        selectedKey = key
                        var p = providers[key]
                        if (p) {
                            apiKeyInput.text = ""
                            apiKeyInput.placeholderText = "sk-...  (required)"
                        }
                    }

                    property var providers: ({
                        "deepseek":  { name: "DeepSeek",            baseUrl: "https://api.deepseek.com/v1",          model: "deepseek-chat" },
                        "openai":    { name: "OpenAI",              baseUrl: "https://api.openai.com/v1",            model: "gpt-4o" },
                        "anthropic": { name: "Anthropic (Claude)",  baseUrl: "https://api.anthropic.com/v1",         model: "claude-sonnet-4-20250514" },
                        "google":    { name: "Google (Gemini)",     baseUrl: "https://generativelanguage.googleapis.com/v1beta/openai", model: "gemini-2.0-flash" },
                        "groq":      { name: "Groq",                baseUrl: "https://api.groq.com/openai/v1",       model: "mixtral-8x7b-32768" },
                        "together":  { name: "Together AI",         baseUrl: "https://api.together.xyz/v1",          model: "mistralai/Mixtral-8x7B-Instruct-v0.1" },
                        "fireworks": { name: "Fireworks AI",        baseUrl: "https://api.fireworks.ai/inference/v1", model: "accounts/fireworks/models/llama-v3p1-70b-instruct" },
                        "cerebras":  { name: "Cerebras",            baseUrl: "https://api.cerebras.ai/v1",           model: "llama3.1-70b" },
                        "xai":       { name: "xAI (Grok)",          baseUrl: "https://api.x.ai/v1",                  model: "grok-beta" },
                        "mistral":   { name: "Mistral",             baseUrl: "https://api.mistral.ai/v1",            model: "mistral-large-latest" },
                        "cohere":    { name: "Cohere",              baseUrl: "https://api.cohere.ai/v1",             model: "command-r-plus" },
                        "perplexity":{ name: "Perplexity",          baseUrl: "https://api.perplexity.ai",            model: "llama-3.1-sonar-large-128k-online" },
                    })

                    Repeater {
                        model: ["deepseek","openai","anthropic","google","groq","together","fireworks","cerebras","xai","mistral","cohere","perplexity"]
                        delegate: Rectangle {
                            width: parent.width; implicitHeight: 44; radius: 12
                            color: providerList.selectedKey === modelData
                                   ? Qt.rgba(1,1,1,0.15)
                                   : Qt.rgba(1,1,1,0.05)
                            border.color: providerList.selectedKey === modelData
                                          ? Qt.rgba(1,1,1,0.30)
                                          : Qt.rgba(1,1,1,0.08)
                            border.width: 1

                            RowLayout {
                                anchors.fill: parent; anchors.leftMargin: 14; anchors.rightMargin: 14; spacing: 10
                                Rectangle {
                                    width: 18; height: 18; radius: 9
                                    border.color: providerList.selectedKey === modelData ? "white" : Qt.rgba(1,1,1,0.3)
                                    border.width: 2
                                    Rectangle {
                                        anchors.centerIn: parent; width: 8; height: 8; radius: 4
                                        color: "white"
                                        visible: providerList.selectedKey === modelData
                                    }
                                }
                                Text {
                                    text: providerList.providers[modelData].name
                                    color: "white"; font.pixelSize: 13
                                    Layout.fillWidth: true
                                }
                                Text {
                                    text: providerList.providers[modelData].model
                                    color: Qt.rgba(1,1,1,0.35); font.pixelSize: 10
                                }
                            }

                            MouseArea {
                                anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                onClicked: providerList.select(modelData)
                            }
                        }
                    }
                }

                // ── API Key input (always visible after provider selection) ──
                ColumnLayout {
                    visible: providerList.selectedKey !== "" || customVisible
                    spacing: 6
                    Text { text: "API Key"; color: Qt.rgba(1,1,1,0.6); font.pixelSize: 11 }
                    TextField {
                        id: apiKeyInput
                        Layout.fillWidth: true; implicitHeight: 40
                        echoMode: TextInput.Password
                        placeholderText: "sk-..."
                        placeholderTextColor: Qt.rgba(1,1,1,0.25)
                        color: "white"; font.pixelSize: 13
                        background: Rectangle { radius: 10; color: Qt.rgba(1,1,1,0.08); border.color: Qt.rgba(1,1,1,0.20); border.width: 1 }
                    }
                }

                // ── Custom provider toggle ──────────────────
                Rectangle {
                    Layout.fillWidth: true; implicitHeight: 36; radius: 10
                    color: customVisible ? Qt.rgba(1,1,1,0.10) : "transparent"
                    border.color: Qt.rgba(1,1,1,0.15); border.width: 1

                    RowLayout {
                        anchors.centerIn: parent; spacing: 6
                        Text { text: customVisible ? "▲  Hide custom" : "▼  Other provider..."; color: Qt.rgba(1,1,1,0.4); font.pixelSize: 11 }
                    }

                    MouseArea {
                        anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            customVisible = !customVisible
                            if (customVisible) providerList.selectedKey = ""
                        }
                    }
                }

                // ── Custom fields ──────────────────────────
                ColumnLayout {
                    id: customBlock
                    visible: customVisible
                    spacing: 10

                    RowLayout { spacing: 10
                        ColumnLayout { Layout.fillWidth: true; spacing: 6
                            Text { text: "Base URL"; color: Qt.rgba(1,1,1,0.6); font.pixelSize: 11 }
                            TextField {
                                id: baseUrlInput; Layout.fillWidth: true; implicitHeight: 40
                                text: "https://api.deepseek.com/v1"
                                placeholderTextColor: Qt.rgba(1,1,1,0.25); color: "white"; font.pixelSize: 13
                                background: Rectangle { radius: 10; color: Qt.rgba(1,1,1,0.08); border.color: Qt.rgba(1,1,1,0.20); border.width: 1 }
                            }
                        }
                        ColumnLayout { Layout.preferredWidth: 140; spacing: 6
                            Text { text: "Model"; color: Qt.rgba(1,1,1,0.6); font.pixelSize: 11 }
                            TextField {
                                id: modelInput; Layout.fillWidth: true; implicitHeight: 40
                                text: "deepseek-chat"
                                placeholderTextColor: Qt.rgba(1,1,1,0.25); color: "white"; font.pixelSize: 13
                                background: Rectangle { radius: 10; color: Qt.rgba(1,1,1,0.08); border.color: Qt.rgba(1,1,1,0.20); border.width: 1 }
                            }
                        }
                    }
                }

                // ── Action buttons ──────────────────────────
                Item {
                    Layout.fillWidth: true; implicitHeight: 44

                    RowLayout {
                        anchors.fill: parent; spacing: 10

                        Rectangle {
                            Layout.fillWidth: true; implicitHeight: 44; radius: 12
                            color: "white"
                            opacity: (providerList.selectedKey !== "" && apiKeyInput.text.trim() !== "") ? 1.0 : 0.4
                            Text { anchors.centerIn: parent; text: "Connect"; color: "#5b6e7a"; font.pixelSize: 14; font.weight: Font.DemiBold }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (providerList.selectedKey === "" && !customVisible) return
                                    var p = providerList.providers[providerList.selectedKey]
                                    var url = customVisible ? baseUrlInput.text : (p ? p.baseUrl : "")
                                    var model = customVisible ? modelInput.text : (p ? p.model : "")
                                    bridge.saveConfig(apiKeyInput.text, url, model)
                                    finishAnim.start()
                                }
                            }
                        }

                        Text {
                            text: "Skip"; color: Qt.rgba(1,1,1,0.35)
                            font.pixelSize: 12; Layout.fillWidth: true
                            horizontalAlignment: Text.AlignHCenter
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                onClicked: { bridge.saveConfig("", "", ""); finishAnim.start() }
                            }
                        }
                    }
                }
            }
        }

    // ── Bottom tagline ──────────────────────────────────────
    Text {
        id: tagLine
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom; anchors.bottomMargin: 32
        text: "Moss Agent · AI Time"; color: Qt.rgba(1,1,1,0.25)
        font.pixelSize: 12; font.weight: Font.Light; opacity: 0
    }

    // ── Animations ──────────────────────────────────────────

    // Phase 1: Hello + subtitle float up
    ParallelAnimation {
        id: helloAnim
        NumberAnimation { target: helloLine; property: "opacity"; to: 1; duration: 800; easing.type: Easing.OutCubic }
        NumberAnimation { target: helloLine; property: "y"; to: 0; duration: 900; easing.type: Easing.OutCubic }
    }
    SequentialAnimation {
        id: subtitleAnim
        PauseAnimation { duration: 500 }
        ParallelAnimation {
            NumberAnimation { target: subtitleLine; property: "opacity"; to: 1; duration: 600; easing.type: Easing.OutCubic }
            NumberAnimation { target: subtitleLine; property: "y"; to: 0; duration: 650; easing.type: Easing.OutCubic }
        }
    }
    SequentialAnimation {
        id: tagAnim
        PauseAnimation { duration: 700 }
        NumberAnimation { target: tagLine; property: "opacity"; to: 1; duration: 500; easing.type: Easing.OutCubic }
    }

    // Phase 2: Greeting slides up out of view, config card fades in
    SequentialAnimation {
        id: configReveal
        PauseAnimation { duration: 2200 }
        NumberAnimation { target: greetingBlock; property: "y"; to: -140; duration: 500; easing.type: Easing.InCubic }
        PropertyAction { target: configCard; property: "opacity"; value: 1 }
    }

    // Phase 3: Greeting slides back, config card fades, welcome ends
    SequentialAnimation {
        id: finishAnim
        PropertyAction { target: configCard; property: "opacity"; value: 0 }
        PauseAnimation { duration: 200 }
        PropertyAction { target: window; property: "welcomeClosing"; value: true }
    }

    Timer { interval: 300; running: true; repeat: false
        onTriggered: { helloAnim.start(); subtitleAnim.start(); tagAnim.start(); configReveal.start() }
    }
}
