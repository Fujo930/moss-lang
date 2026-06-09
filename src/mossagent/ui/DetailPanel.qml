import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "theme.js" as Theme

Rectangle {
    id: root
    color: Theme.bg1

    property color cBg1: Theme.bg1
    property color cBg2: Theme.bg2
    property color cBg3: Theme.bg3
    property color cFg1: Theme.fg1
    property color cFg2: Theme.fg2
    property color cFg3: Theme.fg3
    property color cGreen: Theme.green
    property color cRed: Theme.red
    property color cAmber: Theme.amber

    property var gateStates: ({
        check:    { status: "\u2014", color: root.cFg3 },
        trace:    { status: "\u2014", color: root.cFg3 },
        golden:   { status: "\u2014", color: root.cFg3 },
        lock:     { status: "\u2014", color: root.cFg3 },
        selfhost: { status: "\u2014", color: root.cFg3 }
    })

    function updateGate(name, status) {
        if (!gateStates[name]) return
        gateStates[name].status = status
        if (status === "PASS") gateStates[name].color = root.cGreen
        else if (status === "FAIL") gateStates[name].color = root.cRed
        else if (status === "SKIP") gateStates[name].color = root.cAmber
        else gateStates[name].color = root.cFg3
        gateStates = gateStates
    }

    function showResult(result) {
        summaryText.text = result.summary || ""
        summaryOk.text = result.ok ? "\u2705" : "\u274C"
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // Gates header
        Rectangle {
            Layout.fillWidth: true; implicitHeight: 32
            color: root.cBg2; border.color: root.cBg3; border.width: 1
            Text {
                anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: Theme.space_md
                text: "\uD83D\uDEE1 Trust Gates"; color: root.cFg1; font.pixelSize: Theme.font_size_sm; font.family: Theme.font_sans; font.weight: Font.DemiBold
            }
        }

        Column {
            Layout.fillWidth: true; Layout.topMargin: Theme.space_sm
            Layout.leftMargin: Theme.space_md; Layout.rightMargin: Theme.space_md
            spacing: Theme.space_xs

            Repeater {
                model: ["check", "trace", "golden", "lock", "selfhost"]
                delegate: RowLayout {
                    width: parent ? parent.width : 200
                    spacing: Theme.space_sm

                    Rectangle {
                        width: 100; height: 12; radius: 6
                        color: root.cBg2; border.color: root.cBg3
                        Rectangle {
                            width: root.gateStates[modelData].status === "PASS" || root.gateStates[modelData].status === "FAIL" ? 100 : 0
                            height: parent.height; radius: 6
                            color: root.gateStates[modelData].color
                            Behavior on width { NumberAnimation { duration: 300 } }
                        }
                    }
                    Text { text: modelData; color: root.cFg1; font.pixelSize: Theme.font_size_sm; font.family: Theme.font_mono; Layout.preferredWidth: 55 }
                    Text { text: root.gateStates[modelData].status; color: root.gateStates[modelData].color; font.pixelSize: Theme.font_size_sm; font.family: Theme.font_sans; font.weight: Font.DemiBold }
                }
            }
        }

        Item { Layout.preferredHeight: Theme.space_lg }

        // Task header
        Rectangle {
            Layout.fillWidth: true; implicitHeight: 32
            color: root.cBg2; border.color: root.cBg3; border.width: 1
            Text {
                anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: Theme.space_md
                text: "\uD83D\uDCCB Task"; color: root.cFg1; font.pixelSize: Theme.font_size_sm; font.family: Theme.font_sans; font.weight: Font.DemiBold
            }
        }

        ColumnLayout {
            Layout.fillWidth: true; Layout.margins: Theme.space_md; spacing: Theme.space_sm
            RowLayout {
                spacing: Theme.space_sm
                Text { id: summaryOk; text: ""; font.pixelSize: Theme.font_size_lg }
                Text { id: summaryText; text: "No active task"; color: root.cFg2; font.pixelSize: Theme.font_size_sm; font.family: Theme.font_sans; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            }
        }

        Item { Layout.fillHeight: true }

        // Performance header
        Rectangle {
            Layout.fillWidth: true; implicitHeight: 32
            color: root.cBg2; border.color: root.cBg3; border.width: 1
            Text {
                anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: Theme.space_md
                text: "\u26A1 Performance"; color: root.cFg1; font.pixelSize: Theme.font_size_sm; font.family: Theme.font_sans; font.weight: Font.DemiBold
            }
        }

        ColumnLayout {
            Layout.fillWidth: true; Layout.margins: Theme.space_md; spacing: Theme.space_xs
            RowLayout {
                spacing: Theme.space_sm
                Text { text: "Cache hit:"; color: root.cFg2; font.family: Theme.font_sans; font.pixelSize: Theme.font_size_xs }
                Text { text: bridge.stats ? bridge.stats.cache_hit_pct + "%" : "\u2014"; color: root.cGreen; font.family: Theme.font_mono; font.pixelSize: Theme.font_size_xs }
            }
            RowLayout {
                spacing: Theme.space_sm
                Text { text: "Turns:"; color: root.cFg2; font.family: Theme.font_sans; font.pixelSize: Theme.font_size_xs }
                Text { text: bridge.stats ? bridge.stats.turns : "\u2014"; color: root.cFg1; font.family: Theme.font_mono; font.pixelSize: Theme.font_size_xs }
            }
            RowLayout {
                spacing: Theme.space_sm
                Text { text: "Messages:"; color: root.cFg2; font.family: Theme.font_sans; font.pixelSize: Theme.font_size_xs }
                Text { text: bridge.stats ? bridge.stats.messages : "\u2014"; color: root.cFg1; font.family: Theme.font_mono; font.pixelSize: Theme.font_size_xs }
            }
        }

        Item { Layout.preferredHeight: Theme.space_sm }
    }
}
