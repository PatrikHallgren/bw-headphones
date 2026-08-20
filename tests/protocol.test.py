import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "helper"))
from bw_headphones import decode_frame, encode_request, command, retry, ProtocolError


class ProtocolTests(unittest.TestCase):
    def test_request_without_payload(self):
        self.assertEqual(encode_request(3, 1), bytes.fromhex("040b120103"))

    def test_request_with_integer_payload(self):
        packet = encode_request(3, 2, 1)
        self.assertEqual(packet, bytes.fromhex("070b920203010001"))

    def test_decode_notification(self):
        decoded = decode_frame(bytes.fromhex("0d120103"))
        self.assertEqual(decoded["kind"], "notification")
        self.assertEqual(decoded["namespace"], 3)
        self.assertEqual(decoded["command_id"], 1)

    def test_decode_response_with_payload(self):
        # 0x920c response, command 0x01/namespace 0x03, error 0,
        # MessagePack integer 2.
        decoded = decode_frame(bytes.fromhex("0c9201030000010002"))
        self.assertEqual(decoded["kind"], "response")
        self.assertEqual(decoded["payload"], 2)

    def test_command_mapping(self):
        self.assertEqual(command("off"), (3, 2, 0))
        self.assertEqual(command("pass-through"), (3, 2, 2))

    def test_retry_recovers_from_a_transient_timeout(self):
        calls = []

        def flaky():
            calls.append(True)
            if len(calls) < 3:
                raise TimeoutError("GATT timeout")
            return "ok"

        self.assertEqual(retry(flaky, attempts=3, delay=0, sleep=lambda _delay: None), "ok")
        self.assertEqual(len(calls), 3)

    def test_retry_preserves_the_final_transport_error(self):
        with self.assertRaises(ConnectionError):
            retry(lambda: (_ for _ in ()).throw(ConnectionError("disconnected")), attempts=2, delay=0, sleep=lambda _delay: None)

    def test_malformed_frame_is_rejected(self):
        with self.assertRaises(ProtocolError):
            decode_frame(bytes.fromhex("0c920103000001"))


if __name__ == "__main__":
    unittest.main()
