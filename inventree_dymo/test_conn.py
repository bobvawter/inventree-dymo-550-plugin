import os
import unittest

from .conn import Conn, LockIntent
from .status import PrinterState

PRINTER_HOST_VAR = 'PRINTER_HOST'
PRINTER_HOST = os.getenv(PRINTER_HOST_VAR)

PRINTER_PORT_VAR = 'PRINTER_PORT'
PRINTER_PORT = os.getenv(PRINTER_PORT_VAR, 9100)


class TestConn(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not PRINTER_HOST:
            raise unittest.SkipTest(f'No {PRINTER_HOST_VAR} environment variable defined')

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

            # The second connection should eventually suceed.
            r2 = c2.wait_until_state(intent=LockIntent.LOCK, until=PrinterState.IDLE)
            self.assertEqual(PrinterState.IDLE, r2.printer_state)


if __name__ == '__main__':
    unittest.main()
