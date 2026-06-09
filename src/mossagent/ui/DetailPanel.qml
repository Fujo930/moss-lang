import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Detail panel — Trust gates, task result, cache stats. Cards, reads from window.

Rectangle {
    id: root
    color: window.cBg1

    property var gateStates: ({
        check:    { status: "—", color: window.cFg3 },
        trace:    { status: "—", color: window.cFg3 },
        golden:   { status: "—", color: window.cFg3 },
        lock:     { status: "—", color: window.cFg3 },
        selfhost: { status: "—", color: window.cFg3 }
    })

    function updateGate(name, status) {
        if (!gateStates[name]) return
        gateStates[name].status = status
        if (status === "PASS") gateStates[name].color = window.cGreen
        else if (status === "FAIL") gateStates[name].color = window.cRed
        else if (status === "SKIP") gateStates[name].color = window.cAmber
        else gateStates[name].color = window.cFg3
        gateStates = gateStates
    }

    function showResult(result) {
        taskSummary.text = result.summary || ""
        taskIcon.text = result.ok ? "✅" : "❌"
    }

    ColumnLayout {
        anchors.fill: parent; anchors.margins: 10; spacing: 8

        // ── Trust Gates card ────────────────────────────────
        Rectangle {
            Layout.fillWidth: true; implicitHeight: 180; radius: 12
            color: window.cBg0; border.color: window.cBg3; border.width: 1

            ColumnLayout {
                anchors.fill: parent; spacing: 0

                Rectangle {
                    Layout.fillWidth: true; implicitHeight: 36; radius: 12; color: "transparent"
                    RowLayout {
                        anchors.fill: parent; anchors.leftMargin: 12; spacing: 6
                        Text { text: "🛡"; font.pixelSize: 12 }
                        Text { text: "Trust Gates"; color: window.cFg1; font.pixelSize: 13; font.weight: Font.DemiBold }
                    }
                }

                Column {
                    Layout.fillWidth: true; Layout.leftMargin: 12; Layout.rightMargin: 12; spacing: 4
                    Repeater {
                        model: ["check", "trace", "golden", "lock", "selfhost"]
                        delegate: RowLayout {
                            width: parent ? parent.width - 24 : 200; spacing: 8

                            Rectangle {
                                width: 80; height: 8; radius: 4
                                color: window.cBg2; border.color: window.cBg3
                                Rectangle {
                                    width: root.gateStates[modelData].status === "PASS" || root.gateStates[modelData].status === "FAIL" ? 80 : 0
                                    height: 8; radius: 4
                                    color: root.gateStates[modelData].color
                                    Behavior on width { NumberAnimation { duration: 300 } }
                                }
                            }
                            Text { text: modelData; color: window.cFg1; font.pixelSize: 12; Layout.preferredWidth: 50 }
                            Text { text: root.gateStates[modelData].status; color: root.gateStates[modelData].color; font.pixelSize: 12; font.weight: Font.DemiBold }
                        }
                    }
                }
            }
        }

        // ── Task card ───────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true; implicitHeight: 72; radius: 12
            color: window.cBg0; border.color: window.cBg3; border.width: 1

            ColumnLayout {
                anchors.fill: parent; spacing: 0

                Rectangle {
                    Layout.fillWidth: true; implicitHeight: 36; radius: 12; color: "transparent"
                    RowLayout {
                        anchors.fill: parent; anchors.leftMargin: 12; spacing: 6
                        Text { text: "📋"; font.pixelSize: 12 }
                        Text { text: "Task"; color: window.cFg1; font.pixelSize: 13; font.weight: Font.DemiBold }
                    }
                }

                RowLayout {
                    Layout.leftMargin: 12; Layout.rightMargin: 12; spacing: 6
                    Text { id: taskIcon; text: ""; font.pixelSize: 16 }
                    Text { id: taskSummary; text: "No active task"; color: window.cFg2; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                }
            }
        }

        // ── Performance card ────────────────────────────────
        Rectangle {
            Layout.fillWidth: true; implicitHeight: 100; radius: 12
            color: window.cBg0; border.color: window.cBg3; border.width: 1

            ColumnLayout {
                anchors.fill: parent; spacing: 0

                Rectangle {
                    Layout.fillWidth: true; implicitHeight: 36; radius: 12; color: "transparent"
                    RowLayout {
                        anchors.fill: parent; anchors.leftMargin: 12; spacing: 6
                        Text { text: "⚡"; font.pixelSize: 12 }
                        Text { text: "Performance"; color: window.cFg1; font.pixelSize: 13; font.weight: Font.DemiBold }
                    }
                }

                Column {
                    Layout.leftMargin: 12; Layout.rightMargin: 12; spacing: 3
                    RowLayout { spacing: 4
                        Text { text: "Cache hit:"; color: window.cFg2; font.pixelSize: 11 }
                        Text { text: bridge.stats && bridge.stats.estimated_cache_hit_pct ? bridge.stats.estimated_cache_hit_pct + "%" : "—"; color: window.cGreen; font.pixelSize: 11 }
                    }
                    RowLayout { spacing: 4
                        Text { text: "Turns:"; color: window.cFg2; font.pixelSize: 11 }
                        Text { text: bridge.stats && bridge.stats.turns ? bridge.stats.turns : "—"; color: window.cFg1; font.pixelSize: 11 }
                    }
                }
            }
        }

        Item { Layout.fillHeight: true }
    }
}
