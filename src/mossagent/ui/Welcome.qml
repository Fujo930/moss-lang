import QtQuick

// Full-window welcome.  Apple-style: "Hello" floats up, then dissolves.
// Multilingual greeting lives in ChatPanel's empty state, not here.

Rectangle {
    id: welcome
    anchors.fill: parent
    color: "#5b6e7a"

    // ── Background doodles ────────────────────────────────────
    Canvas {
        anchors.fill: parent
        property int frame: 0

        Timer { interval: 600; running: welcome.visible; repeat: true
            onTriggered: { frame++; requestPaint() } }

        onPaint: {
            var ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)
            var w = width, h = height
            var seed = 42  // deterministic "random"

            function rand() {
                seed = (seed * 16807) % 2147483647
                return (seed - 1) / 2147483646
            }

            // ── Scatter circles ──────────────────────────
            for (var i = 0; i < 18; i++) {
                var cx = rand() * w, cy = rand() * h
                var r = 4 + rand() * 22
                ctx.globalAlpha = 0.02 + rand() * 0.04
                ctx.strokeStyle = "white"
                ctx.lineWidth = 0.5 + rand() * 1.0
                ctx.beginPath()
                if (rand() > 0.5) {
                    ctx.arc(cx, cy, r, 0, Math.PI * 2)     // full circle
                } else {
                    ctx.arc(cx, cy, r, rand() * Math.PI, rand() * Math.PI + 2.5)  // partial arc
                }
                ctx.stroke()
            }

            // ── Thin wandering lines ─────────────────────
            for (var j = 0; j < 5; j++) {
                var x0 = rand() * w, y0 = rand() * h
                ctx.globalAlpha = 0.03 + rand() * 0.04
                ctx.strokeStyle = "white"
                ctx.lineWidth = 0.5
                ctx.beginPath()
                ctx.moveTo(x0, y0)
                for (var k = 0; k < 5; k++) {
                    x0 += (rand() - 0.5) * 160
                    y0 += (rand() - 0.5) * 120
                    ctx.lineTo(x0, y0)
                }
                ctx.stroke()
            }

            // ── Constellation dots + connectors ──────────
            var dots = []
            for (var d = 0; d < 11; d++) {
                dots.push({x: rand() * w * 0.85 + w * 0.07, y: rand() * h * 0.8 + h * 0.1})
            }
            for (var di = 0; di < dots.length; di++) {
                ctx.globalAlpha = 0.10 + rand() * 0.08
                ctx.fillStyle = "white"
                ctx.beginPath()
                ctx.arc(dots[di].x, dots[di].y, 1.5 + rand() * 2.5, 0, Math.PI * 2)
                ctx.fill()

                // Connect some nearby pairs
                for (var dj = di + 1; dj < dots.length; dj++) {
                    var dx = dots[di].x - dots[dj].x
                    var dy = dots[di].y - dots[dj].y
                    var dist = Math.sqrt(dx * dx + dy * dy)
                    if (dist < 160 && rand() > 0.6) {
                        ctx.globalAlpha = 0.02 + rand() * 0.03
                        ctx.strokeStyle = "white"
                        ctx.lineWidth = 0.4
                        ctx.beginPath()
                        ctx.moveTo(dots[di].x, dots[di].y)
                        ctx.lineTo(dots[dj].x, dots[dj].y)
                        ctx.stroke()
                    }
                }
            }

            // ── Gentle fade pulse on frame ───────────────
            // (doodles breathe subtly)
            ctx.globalAlpha = 1.0
        }
    }

    // ── Greeting ────────────────────────────────────────────
    Column {
        anchors.centerIn: parent
        spacing: 18

        Text {
            id: helloLine
            anchors.horizontalCenter: parent.horizontalCenter
            text: "Hello"
            color: "white"
            font.pixelSize: 64
            font.weight: Font.Thin
            font.letterSpacing: -1
            opacity: 0
            y: 30
        }

        Text {
            id: subtitleLine
            anchors.horizontalCenter: parent.horizontalCenter
            text: "Welcome to Corvus"
            color: Qt.rgba(1, 1, 1, 0.55)
            font.pixelSize: 16
            font.weight: Font.Light
            opacity: 0
            y: 12
        }
    }

    // ── Bottom tagline ──────────────────────────────────────
    Text {
        id: tagLine
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom; anchors.bottomMargin: 32
        text: "Moss Agent · AI Time"
        color: Qt.rgba(1, 1, 1, 0.25)
        font.pixelSize: 12
        font.weight: Font.Light
        opacity: 0
    }

    // ── Animations ──────────────────────────────────────────

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

    NumberAnimation {
        id: dissolve
        target: welcome; property: "opacity"
        to: 0; duration: 500; easing.type: Easing.InCubic
        onFinished: { window.welcomeDone = true }
    }

    Timer { interval: 300; running: true; repeat: false
        onTriggered: { helloAnim.start(); subtitleAnim.start(); tagAnim.start() }
    }

    Timer { interval: 4500; running: welcome.visible; repeat: false
        onTriggered: { if (!window.welcomeDone) dissolve.start() }
    }

    MouseArea { anchors.fill: parent
        onClicked: { if (!window.welcomeDone) dissolve.start() }
    }
}
