var ANC_OFF = "off"
var ANC = "anc"
var PASS_THROUGH = "pass-through"
var UNKNOWN = "unknown"

function emptyState() {
  return {
    schema_version: 1,
    connected: false,
    address: "",
    name: "Px7 S3",
    battery: { level: -1, charging: false },
    anc_mode: UNKNOWN,
    capabilities: [],
    transport_ready: false,
    audio_source: "",
    codec: "",
    sampling_rate: "",
    firmware: "",
    last_error: ""
  }
}

function intOr(value, fallback) {
  var n = parseInt(value, 10)
  return isFinite(n) ? n : fallback
}

function parseState(raw) {
  var state = emptyState()
  var text = String(raw || "").trim()
  if (!text) return { ok: false, state: state, error: "Status file is empty" }
  var parsed
  try { parsed = JSON.parse(text) } catch (e) {
    return { ok: false, state: state, error: "Status file is not valid JSON" }
  }
  if (!parsed || typeof parsed !== "object")
    return { ok: false, state: state, error: "Status file is not an object" }
  if (intOr(parsed.schema_version, 0) > 1)
    return { ok: false, state: state, error: "Status file uses a newer schema" }

  state.connected = parsed.connected === true
  state.address = String(parsed.address || "")
  state.name = String(parsed.name || "Px7 S3")
  state.anc_mode = [ANC_OFF, ANC, PASS_THROUGH].indexOf(String(parsed.anc_mode || "")) >= 0
    ? String(parsed.anc_mode) : UNKNOWN
  state.capabilities = Array.isArray(parsed.capabilities) ? parsed.capabilities.slice() : []
  state.transport_ready = parsed.transport_ready === true
  state.audio_source = String(parsed.audio_source || "")
  state.codec = String(parsed.codec || "")
  state.sampling_rate = String(parsed.sampling_rate || "")
  state.firmware = String(parsed.firmware || "")
  state.last_error = String(parsed.last_error || "")
  var battery = parsed.battery && typeof parsed.battery === "object" ? parsed.battery : {}
  state.battery = {
    level: intOr(battery.level, -1),
    charging: battery.charging === true
  }
  return { ok: true, state: state, error: "" }
}

function modeLabel(mode) {
  if (mode === ANC_OFF) return "Off"
  if (mode === ANC) return "Noise cancelling"
  if (mode === PASS_THROUGH) return "Pass-through"
  return "Unavailable"
}

function modeGlyph(mode) {
  if (mode === ANC) return "󰂳"
  if (mode === PASS_THROUGH) return "󰂽"
  return "󰂲"
}

function batteryText(level) {
  return level < 0 ? "--" : String(Math.max(0, Math.min(100, level))) + "%"
}

function clampLevel(level) {
  return Math.max(0, Math.min(100, intOr(level, 0)))
}

function isKnownMode(mode) {
  return [ANC_OFF, ANC, PASS_THROUGH].indexOf(String(mode)) >= 0
}

function nextMode(mode, available) {
  var modes = Array.isArray(available) && available.length ? available : [ANC_OFF, PASS_THROUGH, ANC]
  var index = modes.indexOf(mode)
  return modes[(index < 0 ? 0 : index + 1) % modes.length]
}

function elide(text, max) {
  var value = String(text || "").replace(/\s+/g, " ").trim()
  var limit = max || 120
  return value.length > limit ? value.substring(0, limit - 1) + "…" : value
}

var api = {
  ANC_OFF: ANC_OFF,
  ANC: ANC,
  PASS_THROUGH: PASS_THROUGH,
  UNKNOWN: UNKNOWN,
  emptyState: emptyState,
  parseState: parseState,
  modeLabel: modeLabel,
  modeGlyph: modeGlyph,
  batteryText: batteryText,
  clampLevel: clampLevel,
  isKnownMode: isKnownMode,
  nextMode: nextMode,
  elide: elide
}

if (typeof globalThis !== "undefined") globalThis.BwHeadphonesModel = api
if (typeof module !== "undefined") module.exports = api
