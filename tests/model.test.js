import "../Model.js"

function assertEquals(actual, expected) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(`Expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`)
  }
}

const Model = globalThis.BwHeadphonesModel

Deno.test("parses a connected status", () => {
  const parsed = Model.parseState(JSON.stringify({
    schema_version: 1,
    connected: true,
    address: "AA:BB:CC:DD:EE:FF",
    name: "Px7 S3",
    battery: { level: 73, charging: true },
    anc_mode: "anc",
    capabilities: ["anc"],
    transport_ready: true
  }))
  assertEquals(parsed.ok, true)
  assertEquals(parsed.state.battery.level, 73)
  assertEquals(parsed.state.anc_mode, Model.ANC)
})

Deno.test("rejects malformed and newer state", () => {
  assertEquals(Model.parseState("not json").ok, false)
  assertEquals(Model.parseState(JSON.stringify({ schema_version: 2 })).ok, false)
})

Deno.test("cycles the stable ANC order", () => {
  assertEquals(Model.nextMode(Model.ANC_OFF), Model.PASS_THROUGH)
  assertEquals(Model.nextMode(Model.PASS_THROUGH), Model.ANC)
  assertEquals(Model.nextMode(Model.ANC), Model.ANC_OFF)
})

Deno.test("formats battery and clamps values", () => {
  assertEquals(Model.batteryText(-1), "--")
  assertEquals(Model.batteryText(101), "100%")
  assertEquals(Model.clampLevel(130), 100)
  assertEquals(Model.clampLevel(-4), 0)
})
