import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "theme.js" as Theme

// Reasonix-style detail panel: Trust gate visualization, task steps, cache stats.
// Shows real-time gate status during verify/generate operations.

Rectangle {
    id: root
    color: parent ? parent.cBg1 : Theme.bg1

    property var gateStates: ({
        check:    { status: "—", color: root.cFg3 },
        trace:    { status: "—", color: root.cFg3 },
        golden:   { status: "—", color: root.cFg3 },
        lock:     { status: "—", color: root.cFg3 },
        selfhost: { status: "—", color: root.cFg3 }
    })

    function updateGate(name, status) {
        if (!gateStates[name]) return
        gateStates[name].status = status
        if (status === "PASS") gateStates[name].color = root.cGreen
        else if (status === "FAIL") gateStates[name].color = root.cRed
        else if (status === "SKIP") gateStates[name].color = root.cAmber
        else gateStates[name].color = root.cFg3
        gateStates = gateStates  // trigger binding
    }

    function showResult(result) {
        summaryText.text = result.summary || ""
        summaryOk.color = result.ok ? root.cGreen : root.cRed
        summaryOk.text = result.ok ? "✅" : "❌"
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ── Section: Gates ──────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 32
            color: root.cBg2
            border.color: root.cBg3
            border.width: 1

            Text {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.leftMargin: Theme.space_md
                text: "🛡 Trust Gates"
                color: root.cFg1
                font.pixelSize: Theme.font_size_sm
                font.family: Theme.font_sans
                font.weight: Font.DemiBold
            }
        }

        Column {
            Layout.fillWidth: true
            Layout.topMargin: Theme.space_sm
            Layout.leftMargin: Theme.space_md
            Layout.rightMargin: Theme.space_md
            spacing: Theme.space_xs

            Repeater {
                model: ["check", "trace", "golden", "lock", "selfhost"]

                delegate: RowLayout {
                    width: parent ? parent.width : 200
                    spacing: Theme.space_sm

                    // Progress bar background
                    Rectangle {
                        width: 100; height: 12; radius: 6
                        color: root.cBg2
                        border.color: root.cBg3

                        // Fill bar
                        Rectangle {
                            width: {
                                var s = root.gateStates[modelData].status
                                if (s === "PASS" || s === "FAIL") return 100
                                if (s === "RUNNING") return 40
                                return 0
                            }
                            height: parent.height
                            radius: 6
                            color: root.gateStates[modelData].color
                            Behavior on width { NumberAnimation { duration: 300 } }
                            Behavior on color { ColorAnimation { duration: 200 } }
                        }
                    }

                    Text {
                        text: modelData
                        color: root.cFg1
                        font.pixelSize: Theme.font_size_sm
                        font.family: Theme.font_mono
                        Layout.preferredWidth: 55
                    }

                    Text {
                        text: root.gateStates[modelData].status
                        color: root.gateStates[modelData].color
                        font.pixelSize: Theme.font_size_sm
                        font.family: Theme.font_sans
                        font.weight: Font.DemiBold
                    }
                }
            }
        }

        // ── Spacer ──────────────────────────────────────────
        Item { Layout.preferredHeight: Theme.space_lg }

        // ── Section: Task progress ──────────────────────────
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 32
            color: root.cBg2
            border.color: root.cBg3
            border.width: 1

            Text {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.leftMargin: Theme.space_md
                text: "📋 Task"
                color: root.cFg1
                font.pixelSize: Theme.font_size_sm
                font.family: Theme.font_sans
                font.weight: Font.DemiBold
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.margins: Theme.space_md
            spacing: Theme.space_sm

            RowLayout {
                spacing: Theme.space_sm
                Text {
                    id: summaryOk
                    text: ""
                    font.pixelSize: Theme.font_size_lg
                }
                Text {
                    id: summaryText
                    text: "No active task"
                    color: root.cFg2
                    font.pixelSize: Theme.font_size_sm
                    font.family: Theme.font_sans
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
            }
        }

        // ── Spacer ──────────────────────────────────────────
        Item { Layout.fillHeight: true }

        // ── Section: Cache stats ────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 32
            color: root.cBg2
            border.color: root.cBg3
            border.width: 1

            Text {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.leftMargin: Theme.space_md
                text: "⚡ Performance"
                color: root.cFg1
                font.pixelSize: Theme.font_size_sm
                font.family: Theme.font_sans
                font.weight: Font.DemiBold
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.margins: Theme.space_md
            spacing: Theme.space_xs

            RowLayout {
                spacing: Theme.space_sm
                Text { text: "Cache hit:"; color: root.cFg2; font.family: Theme.font_sans; font.size: Theme.font_size_xs }
                Text { text: bridge.stats ? bridge.stats.cache_hit_pct + "%" : "—"; color: root.cGreen; font.family: Theme.font_mono; font.size: Theme.font_size_xs }
            }
            RowLayout {
                spacing: Theme.space_sm
                Text { text: "Turns:"; color: root.cFg2; font.family: Theme.font_sans; font.size: Theme.font_size_xs }
                Text { text: bridge.stats ? bridge.stats.turns : "—"; color: root.cFg1; font.family: Theme.font_mono; font.size: Theme.font_size_xs }
            }
            RowLayout {
                spacing: Theme.space_sm
                Text { text: "Messages:"; color: root.cFg2; font.family: Theme.font_sans; font.size: Theme.font_size_xs }
                Text { text: bridge.stats ? bridge.stats.messages : "—"; color: root.cFg1; font.family: Theme.font_mono; font.size: Theme.font_size_xs }
            }
        }

        Item { Layout.preferredHeight: Theme.space_sm }
    }
}
