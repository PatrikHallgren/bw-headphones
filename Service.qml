import QtQuick
import Quickshell
import Quickshell.Io
import "Model.js" as Model

Item {
  id: root

  property var settings: ({})
  property bool daemonReachable: false
  property bool connected: false
  property string address: ""
  property string deviceName: "Px7 S3"
  property int batteryLevel: -1
  property bool charging: false
  property string ancMode: Model.UNKNOWN
  property var capabilities: []
  property bool transportReady: false
  property string audioSource: ""
  property string codec: ""
  property string samplingRate: ""
  property string firmware: ""
  property string lastError: ""
  property string actionStatus: ""
  property string pendingMode: ""
  readonly property string statePath: (Quickshell.env("XDG_STATE_HOME")
    || Quickshell.env("HOME") + "/.local/state") + "/bw-headphones/status.json"
  readonly property string ctlPath: String(setting("ctlPath", "") || "px7s3ctl")
  readonly property bool hasBattery: batteryLevel >= 0
  readonly property bool hasControls: transportReady && capabilities.indexOf("anc") >= 0

  function setting(name, fallback) {
    var value = settings ? settings[name] : undefined
    return value === undefined || value === null ? fallback : value
  }

  function refresh() {
    stateFile.reload()
    if (!refreshProcess.running) refreshProcess.running = true
  }

  function applyRaw(raw) {
    var parsed = Model.parseState(raw)
    if (!parsed.ok) {
      daemonReachable = String(raw || "").trim() !== ""
      lastError = parsed.error
      transportReady = false
      return
    }
    daemonReachable = true
    var state = parsed.state
    connected = state.connected
    address = state.address
    deviceName = state.name
    batteryLevel = state.battery.level
    charging = state.battery.charging
    transportReady = state.transport_ready
    audioSource = state.audio_source
    codec = state.codec
    samplingRate = state.sampling_rate
    firmware = state.firmware
    capabilities = state.capabilities
    lastError = state.last_error
    if (!pendingMode || state.anc_mode === pendingMode) {
      ancMode = state.anc_mode
      pendingMode = ""
    }
  }

  function setAnc(mode) {
    if (!Model.isKnownMode(mode) || !hasControls || commandProcess.running) return
    pendingMode = mode
    ancMode = mode
    actionStatus = "Applying " + Model.modeLabel(mode) + "…"
    commandProcess.command = [ctlPath, "set-anc", mode]
    commandProcess.running = true
    settleTimer.restart()
  }

  function cycleAnc() {
    setAnc(Model.nextMode(ancMode, [Model.ANC_OFF, Model.PASS_THROUGH, Model.ANC]))
  }

  function clearTransient() { actionStatus = "" }

  Timer {
    id: settleTimer
    interval: 4000
    repeat: false
    onTriggered: {
      pendingMode = ""
      refresh()
    }
  }

  Timer {
    id: statusTimer
    interval: 2500
    repeat: false
    onTriggered: root.clearTransient()
  }

  FileView {
    id: stateFile
    path: root.statePath
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: root.applyRaw(text())
    onLoadFailed: {
      root.daemonReachable = false
      root.connected = false
      root.transportReady = false
      root.batteryLevel = -1
      root.lastError = "px7s3d is not running"
    }
  }

  Process {
    id: refreshProcess
    command: [ctlPath, "refresh"]
    running: false
  }

  Process {
    id: commandProcess
    command: []
    running: false
    stderr: StdioCollector { id: commandError; waitForEnd: true }
    onExited: function(exitCode) {
      if (exitCode !== 0) {
        root.pendingMode = ""
        root.actionStatus = Model.elide(commandError.text || "px7s3ctl rejected the command")
      statusTimer.restart()
        root.refresh()
      } else {
        root.actionStatus = "Updated"
        statusTimer.restart()
      }
    }
  }

  Component.onCompleted: refresh()
}
