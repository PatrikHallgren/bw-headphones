//! Small, dependency-free checks for the Px7 S3 command envelope.
//!
//! The running bridge is Python/PyGObject so it can use the system BlueZ
//! bindings on Omarchy. Keeping these invariants in a tiny Rust crate gives
//! contributors a fast, toolchain-independent protocol test target too.

pub const ANC_MODES: [&str; 3] = ["off", "anc", "pass-through"];

pub fn anc_value(mode: &str) -> Option<u8> {
    ANC_MODES.iter().position(|candidate| *candidate == mode).map(|value| value as u8)
}

pub fn encode_request(namespace: u8, command: u8, payload: Option<u8>) -> Vec<u8> {
    let mut body = vec![0x0b, if payload.is_some() { 0x92 } else { 0x12 }, command, namespace];
    if let Some(value) = payload {
        body.extend_from_slice(&[1, 0, value]);
    }
    let mut packet = vec![body.len() as u8];
    packet.extend(body);
    packet
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn maps_only_the_three_safe_anc_modes() {
        assert_eq!(anc_value("off"), Some(0));
        assert_eq!(anc_value("anc"), Some(1));
        assert_eq!(anc_value("pass-through"), Some(2));
        assert_eq!(anc_value("dfu"), None);
    }

    #[test]
    fn frames_get_and_set_requests() {
        assert_eq!(encode_request(3, 1, None), vec![4, 0x0b, 0x12, 1, 3]);
        assert_eq!(encode_request(3, 2, Some(1)), vec![7, 0x0b, 0x92, 2, 3, 1, 0, 1]);
    }
}
