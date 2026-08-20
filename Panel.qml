import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Bluetooth
import Quickshell.Services.Pipewire
import qs.Ui
import qs.Commons
import "Model.js" as Model

Panel {
  id: root
  moduleName: "io.github.patrikhallgren.bw-headphones"
  ipcTarget: "io.github.patrikhallgren.bw-headphones"
  manageIpc: false

  Service { id: service; settings: root.settings }
  readonly property var devices: Bluetooth.devices ? Bluetooth.devices.values : []
  readonly property var nodes: Pipewire.nodes ? Pipewire.nodes.values : []
  readonly property string configuredAddress: String(setting("deviceAddress", "") || "").toLowerCase()
  readonly property var headphone: findHeadphone()
  readonly property var audioSink: findSink()
  readonly property bool bluezConnected: !!(headphone && headphone.connected)
  readonly property bool connected: bluezConnected || service.connected
  readonly property bool hideWhenDisconnected: setting("hideWhenDisconnected", true) === true
  readonly property bool shouldShow: !hideWhenDisconnected || connected

  function findHeadphone() {
    var fallback = null
    for (var i = 0; i < devices.length; i++) {
      var d = devices[i]
      if (!d) continue
      var address = String(d.address || "").toLowerCase()
      var label = String(d.deviceName || d.name || "").toLowerCase()
      if (configuredAddress && address === configuredAddress) return d
      if (label.indexOf("px7 s3") >= 0 || label.indexOf("bowers") >= 0) {
        if (d.connected) return d
        fallback = fallback || d
      }
    }
    return fallback
  }

  function findSink() {
    if (!headphone) return null
    var address = String(headphone.address || "").toLowerCase().replace(/[^0-9a-f]/g, "")
    var label = String(headphone.deviceName || headphone.name || "").toLowerCase()
    for (var i = 0; i < nodes.length; i++) {
      var n = nodes[i]
      if (!n || !n.isSink || n.isStream) continue
      var text = [n.name, n.description, n.nickname, n.deviceName, n.mediaName].join(" ").toLowerCase()
      var normalized = text.replace(/[^0-9a-f]/g, "")
      if ((address && normalized.indexOf(address) >= 0) || (label && text.indexOf(label) >= 0)) return n
    }
    return null
  }

  function barBattery() {
    var level = service.batteryLevel >= 0 ? service.batteryLevel : (headphone && headphone.batteryAvailable ? headphone.battery : -1)
    return Model.batteryText(level)
  }

  function barText() {
    if (!connected) return "󰋋"
    return "󰋋 " + barBattery()
  }

  function refresh() { service.refresh() }
  function open() { root.controller.show() }
  function close() { root.controller.hide() }
  function toggle() { root.opened ? root.close() : root.open() }
  function switchPanel(direction) {
    if (root.bar && typeof root.bar.switchPanelFrom === "function") return root.bar.switchPanelFrom(root, direction)
    return false
  }

  IpcHandler {
    target: root.ipcTarget
    function open() { root.open() }
    function close() { root.close() }
    function toggle() { root.toggle() }
    function refresh() { root.refresh(); return "ok" }
    function cycleAnc() { service.cycleAnc(); return "ok" }
  }

  visible: shouldShow
  implicitWidth: shouldShow ? button.implicitWidth : 0
  implicitHeight: shouldShow ? button.implicitHeight : 0

  onOpenedChanged: if (opened) {
    service.refresh()
    Qt.callLater(function() { keyCatcher.forceActiveFocus() })
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: root.barText()
    tooltipText: connected ? "Open B&W Headphones" : "B&W Headphones disconnected"
    onPressed: function(buttonCode) {
      if (buttonCode === Qt.RightButton) service.cycleAnc()
      else root.toggle()
    }
  }

  KeyboardPanel {
    id: popup
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: popup.fittedContentWidth(Style.space(360))
    contentHeight: popup.fittedContentHeight(content.implicitHeight, Style.space(520))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onMoveRequested: function(dx, dy) {
        if (dy !== 0) modeCursor = Math.max(0, Math.min(2, modeCursor + dy))
        else if (dx !== 0 && modeCursor >= 0) service.setAnc(modeForCursor(modeCursor))
      }
      onActivateRequested: service.setAnc(modeForCursor(modeCursor))
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }
      onTextKey: function(t) {
        var key = String(t).toLowerCase()
        if (key === "r") service.refresh()
        else if (key === "o") service.setAnc(Model.ANC_OFF)
        else if (key === "p") service.setAnc(Model.PASS_THROUGH)
        else if (key === "n") service.setAnc(Model.ANC)
      }

      property int modeCursor: 0
      function modeForCursor(index) {
        return [Model.ANC_OFF, Model.PASS_THROUGH, Model.ANC][Math.max(0, Math.min(2, index))]
      }

      ColumnLayout {
        id: content
        width: parent.width
        spacing: Style.space(12)

        PanelHero {
          Layout.fillWidth: true
          title: service.deviceName
          subtitle: root.connected ? "Connected" : "Disconnected"
          icon: "󰋋"
        }

        RowLayout {
          Layout.fillWidth: true
          spacing: Style.space(10)
          Text { text: "Battery"; color: Color.muted; font.pixelSize: Style.font.body; Layout.fillWidth: true }
          Text { text: Model.batteryText(service.batteryLevel); color: Color.foreground; font.pixelSize: Style.font.heading }
          Text { text: service.charging ? "Charging" : ""; color: Color.accent; font.pixelSize: Style.font.caption }
        }

        Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Color.muted }

        Text { text: "NOISE CONTROL"; color: Color.muted; font.pixelSize: Style.font.caption; font.bold: true }

        Repeater {
          model: [Model.ANC_OFF, Model.PASS_THROUGH, Model.ANC]
          delegate: Rectangle {
            required property string modelData
            Layout.fillWidth: true
            implicitHeight: Style.space(38)
            radius: Style.radius(8)
            color: service.ancMode === modelData ? Color.accent : Color.menu.background
            border.color: Color.menu.border
            border.width: 1
            Text {
              anchors.fill: parent
              anchors.leftMargin: Style.space(12)
              verticalAlignment: Text.AlignVCenter
              text: Model.modeLabel(modelData)
              color: service.ancMode === modelData ? Color.background : Color.foreground
              font.pixelSize: Style.font.body
            }
            MouseArea { anchors.fill: parent; onClicked: service.setAnc(modelData) }
          }
        }

        Text {
          Layout.fillWidth: true
          text: {
            var details = []
            if (root.audioSink) details.push(String(root.audioSink.description || root.audioSink.name || "Bluetooth output"))
            if (root.audioSink && root.audioSink.properties) {
              var profile = root.audioSink.properties["bluez5.profile"] || root.audioSink.properties["api.bluez5.profile"] || ""
              if (profile) details.push(String(profile))
            }
            if (service.audioSource) details.push(service.audioSource)
            if (service.codec) details.push(service.codec)
            if (service.samplingRate) details.push(service.samplingRate)
            return details.length ? "Audio: " + details.join(" · ") : "Audio output is managed by Omarchy Audio"
          }
          color: Color.muted
          font.pixelSize: Style.font.caption
          elide: Text.ElideRight
        }
        Text {
          Layout.fillWidth: true
          text: service.actionStatus || (service.lastError || (service.transportReady ? "Vendor controls ready" : "Vendor controls unavailable"))
          color: service.lastError ? Color.urgent : Color.muted
          font.pixelSize: Style.font.caption
          wrapMode: Text.WordWrap
        }
        Text {
          Layout.fillWidth: true
          text: "Tab: Bluetooth / Audio panels   •   r: refresh"
          color: Color.muted
          font.pixelSize: Style.font.caption
          wrapMode: Text.WordWrap
        }
      }
    }
  }
}
