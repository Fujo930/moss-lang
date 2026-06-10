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
        width: 420
        height: 300
        radius: 20
        color: Qt.rgba(1, 1, 1, 0.10)
        border.color: Qt.rgba(1, 1, 1, 0.18)
        border.width: 1
        opacity: 0; z: 2
        Behavior on opacity { NumberAnimation { duration: 400 } }

        // ── Dropdown overlay — drawn ABOVE everything inside the card ──
        Rectangle {
            id: providerDropdown
            anchors.left: parent.left; anchors.leftMargin: 28
            anchors.right: parent.right; anchors.rightMargin: 28
            y: 108  // below the select button
            height: dropHost.overlay ? Math.min(5 * 44 + 12, providerList.providerKeys.length * 44 + 12) : 0
            radius: 14; clip: true
            color: "#f0f0f0"
            border.color: Qt.rgba(0,0,0,0.10); border.width: 1
            visible: height > 0
            z: 100

            Behavior on height { NumberAnimation { duration: 200 } }

            ListView {
                id: dropdownList
                anchors.fill: parent; anchors.margins: 6
                model: providerList.providerKeys
                spacing: 2
                clip: true

                delegate: Rectangle {
                    width: dropdownList.width - 8; x: 4; implicitHeight: 42; radius: 10
                    color: mouseArea.containsMouse ? Qt.rgba(124/255, 58/255, 237/255, 0.08) : "transparent"
                    RowLayout { anchors.fill: parent; anchors.leftMargin: 14; anchors.rightMargin: 14; spacing: 10
                        Text { text: providerList.providers[modelData].name; color: "#1f2328"; font.pixelSize: 13; Layout.fillWidth: true }
                        Text { text: providerList.providers[modelData].model; color: "#656d76"; font.pixelSize: 10 }
                    }
                    MouseArea { id: mouseArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: { providerList.selectedKey = modelData; dropHost.overlay = false }
                    }
                }
            }
        }

        ColumnLayout {
            width: parent.width - 56
            x: 28; y: 28
            spacing: 14

            Text { text: "Choose your AI provider"; color: "white"; font.pixelSize: 15; font.weight: Font.DemiBold }

            // ── Select button ──────────────────────────────
            Item {
                id: dropHost
                Layout.fillWidth: true
                Layout.preferredHeight: 44
                property bool overlay: false

                Rectangle {
                    anchors.fill: parent; radius: 12
                    color: Qt.rgba(1,1,1,0.12)
                    border.color: Qt.rgba(1,1,1,0.25); border.width: 1

                    RowLayout {
                        anchors.fill: parent; anchors.leftMargin: 16; anchors.rightMargin: 10
                        Text { text: providerList.providers[providerList.selectedKey].name; color: "white"; font.pixelSize: 14; Layout.fillWidth: true }
                        Canvas { width: 14; height: 10
                            onPaint: { var ctx = getContext("2d"); ctx.strokeStyle = Qt.rgba(1,1,1,0.5); ctx.lineWidth = 2; ctx.lineCap = "round"; ctx.lineJoin = "round"; ctx.beginPath(); ctx.moveTo(width*0.2, height*0.25); ctx.lineTo(width*0.5, height*0.75); ctx.lineTo(width*0.8, height*0.25); ctx.stroke() }
                        }
                    }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { dropHost.overlay = !dropHost.overlay } }
                }
            }

            // ── Provider data (invisible) ──────────────────
            Item {
                id: providerList
                visible: false
                property var providers: ({
                    "openai":    { name: "OpenAI — GPT-5.5",              baseUrl: "https://api.openai.com/v1",            model: "gpt-5.5" },
                    "anthropic": { name: "Anthropic — Claude Fable 5",    baseUrl: "https://api.anthropic.com/v1",         model: "claude-fable-5" },
                    "google":    { name: "Google — Gemini 3.5 Flash",     baseUrl: "https://generativelanguage.googleapis.com/v1beta/openai", model: "gemini-3.5-flash" },
                    "mistral":   { name: "Mistral — Medium 3.5",          baseUrl: "https://api.mistral.ai/v1",            model: "mistral-medium-3.5" },
                    "xai":       { name: "xAI — Grok 4.3",               baseUrl: "https://api.x.ai/v1",                  model: "grok-4.3" },
                    "deepseek":  { name: "DeepSeek — V4 Pro",             baseUrl: "https://api.deepseek.com/v1",          model: "deepseek-v4-pro" },
                    "glm":       { name: "GLM (Z.ai) — GLM-5.1",          baseUrl: "https://open.bigmodel.cn/api/paas/v4", model: "glm-5.1" },
                    "kimi":      { name: "Kimi (Moonshot) — K2.6",        baseUrl: "https://api.moonshot.cn/v1",           model: "kimi-k2.6" },
                    "qwen":      { name: "Qwen (Alibaba) — Qwen3.7-Max",  baseUrl: "https://dashscope-intl.aliyuncs.com/compatible-mode/v1", model: "qwen3.7-max" },
                })
                property var providerKeys: ["openai","anthropic","google","mistral","xai","deepseek","glm","kimi","qwen"]
                property string selectedKey: "openai"
            }

            // ── API Key input ──────────────────────────────
            ColumnLayout { spacing: 6
                Text { text: "API Key"; color: Qt.rgba(1,1,1,0.6); font.pixelSize: 11 }
                TextField {
                    id: apiKeyInput
                    Layout.fillWidth: true; implicitHeight: 40
                    echoMode: TextInput.Password
                    placeholderText: "sk-..."
                    placeholderTextColor: Qt.rgba(1,1,1,0.25)
                    color: "white"; font.pixelSize: 13
                    background: Rectangle { radius: 10; color: Qt.rgba(1,1,1,0.08); border.color: apiError.visible ? Qt.rgba(1,0,0,0.5) : Qt.rgba(1,1,1,0.20); border.width: 1 }
                    onTextChanged: { apiError.visible = false }
                }
                Text { id: apiError; text: "请输入API key"; color: "#ff6b6b"; font.pixelSize: 11; visible: false }
            }

            // ── Action buttons ─────────────────────────────
            ColumnLayout { spacing: 8
                Rectangle { Layout.fillWidth: true; implicitHeight: 48; radius: 12; color: "white"
                    Text {
                        anchors.centerIn: parent
                        text: testingConnection ? "Testing..." : "Go to the future"
                        color: "#5b6e7a"; font.pixelSize: 14; font.weight: Font.DemiBold
                    }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !testingConnection
                        onClicked: {
                            if (apiKeyInput.text.trim() === "") { apiError.visible = true; return }
                            apiError.visible = false
                            testStatus.text = ""
                            testStatus.color = Qt.rgba(1,1,1,0.5)
                            testingConnection = true
                            var p = providerList.providers[providerList.selectedKey]
                            bridge.testApiConnection(apiKeyInput.text, p.baseUrl, p.model)
                        }
                    }
                }

                // Test result / spinner
                Text {
                    id: testStatus
                    text: ""
                    color: "#ff6b6b"; font.pixelSize: 11
                    Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter
                }

                Text { text: "Skip — local model"; color: Qt.rgba(1,1,1,0.35); font.pixelSize: 11; horizontalAlignment: Text.AlignHCenter
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                        onClicked: { bridge.saveConfig("","",""); finishAnim.start() } }
                }
            }
        }
    }

    property bool testingConnection: false

    // Listen for API test results from bridge
    Connections {
        target: bridge
        function onProgressChanged(msg) {
            try {
                var result = JSON.parse(msg)
                if (result.action === "apiTest") {
                    welcome.testingConnection = false
                    if (result.ok) {
                        testStatus.text = "✅ " + result.message
                        testStatus.color = "#3fb950"
                        // Success — save config and go
                        var p = providerList.providers[providerList.selectedKey]
                        bridge.saveConfig(apiKeyInput.text, p.baseUrl, p.model)
                        finishAnim.start()
                    } else {
                        testStatus.text = "❌ " + result.message
                        testStatus.color = "#ff6b6b"
                    }
                }
            } catch(e) {}
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
