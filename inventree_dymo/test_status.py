import unittest

from status import MediaState, PSUState, PrintHeadState, PrintHeadVoltage, PrinterState, StatusReport

SAMPLE = bytes([
    0x05,  # Status
    0x01, 0x02, 0x03, 0x04,  # Job ID
    0x05, 0x06,  # Label Index
    0x00,  # Reserved
    0x01,  # Print head status
    0x64,  # Density
    0x08,  # Media status
    ord('a'), ord('b'), ord('c'), 0, 0, 0, 0, 0, 0, 0, 0, 0,  # Media SKU
    0x11, 0x12, 0x13, 0x14,  # Printer error code
    0x09, 0x10,  # Remaining label count
    0x01,  # Power supply status (bits 0-3)
    0x01,  # Print head voltage (bits 0-3)
    0  # Reserved
])


class TestStatus(unittest.TestCase):
    def test_decode_sample(self):
        r = StatusReport(SAMPLE)
        self.assertEqual(PrinterState.UNLOCKED, r.printer_state)
        self.assertEqual(0x04030201, r.print_job_id)
        self.assertEqual(0x0605, r.label_index)
        self.assertEqual(PrintHeadState.PRINT_HEAD_OVERHEAT, r.print_head_state)
        self.assertEqual(100, r.density)
        self.assertEqual(MediaState.LEVEL_OK, r.media_state)
        self.assertEqual("abc", r.label_sku)
        self.assertEqual(0x14131211, r.error_id)
        self.assertEqual(0x1009, r.remaining_label_count)
        self.assertEqual(PSUState.PRESENT, r.psu_state)
        self.assertEqual(PrintHeadVoltage.OK, r.print_head_voltage)
        print(r)

    def test_wrong_length(self):
        try:
            StatusReport(bytes([0, 1, 2]))
            self.fail("expecting exception")
        except Exception:
            pass


if __name__ == '__main__':
    unittest.main()
