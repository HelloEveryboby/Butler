import unittest
import json
import socket
import threading
import time
from skills.pixel_pet.main import EventThrottler

class TestEventThrottler(unittest.TestCase):
    def test_throttling_logic(self):
        # Create throttler and mock sending method to avoid actual socket dependency
        throttler = EventThrottler(interval=0.1) # 100ms

        sent_payloads = []
        import skills.pixel_pet.main
        original_send = skills.pixel_pet.main.send_udp_event
        skills.pixel_pet.main.send_udp_event = lambda p: sent_payloads.append(p)

        try:
            # 1. Non-streaming events should be immediate
            throttler.throttle({"event": "ai_thinking", "message": "thinking"})
            self.assertEqual(len(sent_payloads), 1)
            self.assertEqual(sent_payloads[-1]["event"], "ai_thinking")

            # 2. First streaming event should go through immediately
            throttler.throttle({"event": "ai_streaming", "message": "token1"})
            self.assertEqual(len(sent_payloads), 2)
            self.assertEqual(sent_payloads[-1]["message"], "token1")

            # 3. High frequency streaming events should be buffered/throttled
            throttler.throttle({"event": "ai_streaming", "message": "token2"})
            throttler.throttle({"event": "ai_streaming", "message": "token3"})
            # Should not increase length of sent payloads immediately
            self.assertEqual(len(sent_payloads), 2)

            # Wait for more than 100ms
            time.sleep(0.15)

            # The last pending streaming event ("token3") should have been dispatched by the timer
            self.assertEqual(len(sent_payloads), 3)
            self.assertEqual(sent_payloads[-1]["message"], "token3")

        finally:
            skills.pixel_pet.main.send_udp_event = original_send

class TestPetIPCCommunication(unittest.TestCase):
    def test_udp_payload_parsing(self):
        # We can test parsing payload standard by simulating socket sending
        # Let's bind to a random free UDP port to test the reception mechanism
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]

        payload = {"event": "ai_thinking", "message": "Thinking..."}
        raw_bytes = json.dumps(payload).encode('utf-8')

        # Send to ourselves to make sure socket is fully functional
        sock.sendto(raw_bytes, ('127.0.0.1', port))

        sock.settimeout(1.0)
        data, addr = sock.recvfrom(1024)
        parsed = json.loads(data.decode('utf-8'))

        self.assertEqual(parsed["event"], "ai_thinking")
        self.assertEqual(parsed["message"], "Thinking...")
        sock.close()

if __name__ == "__main__":
    unittest.main()
