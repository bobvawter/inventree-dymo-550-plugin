import os
import unittest

import qrcode
import qrcode.image.svg
from PIL import Image

from .conn import Conn, LockIntent
from .status import PrinterState

PRINTER_CONSUME_VAR = 'PRINTER_CONSUME'
PRINTER_CONSUME = os.getenv(PRINTER_CONSUME_VAR, False)

PRINTER_HOST_VAR = 'PRINTER_HOST'
PRINTER_HOST = os.getenv(PRINTER_HOST_VAR)

PRINTER_PORT_VAR = 'PRINTER_PORT'
PRINTER_PORT = os.getenv(PRINTER_PORT_VAR, 9100)


class TestConn(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not PRINTER_HOST:
            raise unittest.SkipTest(f'No {PRINTER_HOST_VAR} environment variable defined')
        if not PRINTER_PORT:
            raise unittest.SkipTest(f'No {PRINTER_PORT_VAR} environment variable defined')

    def test_already_locked(self):
        with Conn(PRINTER_HOST, PRINTER_PORT) as c, Conn(PRINTER_HOST, PRINTER_PORT) as c2:
            # Acquire a lock on the printer.
            r = c.wait_until_state(intent=LockIntent.LOCK, until=PrinterState.IDLE)
            self.assertEqual(PrinterState.IDLE, r.printer_state)

            # Dial another connection that attempts to lock. We should see a
            # sentinel busy report.
            r2 = c2.status_report(intent=LockIntent.LOCK)
            self.assertEqual(PrinterState.BUSY, r2.printer_state)

            # Close the blocking connection.
            c.close()

            # The second connection should eventually succeed.
            r2 = c2.wait_until_state(intent=LockIntent.LOCK, until=PrinterState.IDLE)
            self.assertEqual(PrinterState.IDLE, r2.printer_state)

    def test_print(self):
        if not PRINTER_CONSUME:
            self.skipTest(f'No {PRINTER_CONSUME_VAR} environment variable defined')

        # Create a 1" x 1" label using the printer's fixed 300 DPI.
        img = qrcode.make("Hello World!")
        width, height = img.size
        aspect_ratio = width / height
        img = img.resize((int(Conn.DPI * aspect_ratio), Conn.DPI), Image.Resampling.LANCZOS)

        with Conn(PRINTER_HOST, PRINTER_PORT) as c:
            c.wait_until_state(intent=LockIntent.LOCK, until=PrinterState.IDLE)
            c.start_job()
            c.send_label(1, img)
            c.send_command("E")
            c.send_command("Q")


if __name__ == '__main__':
    unittest.main()
