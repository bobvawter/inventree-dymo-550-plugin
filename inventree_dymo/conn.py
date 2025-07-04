import enum
import logging
import math
import socket
import time
from typing import Optional

from PIL.Image import Image

from .status import PrinterState, StatusReport, StatusReportError

logger = logging.getLogger('inventree')


class LockIntent(enum.Enum):
    NONE = 0
    """ General polling with no expectation to hold a lock. """
    LOCK = 1
    """ Acquire lock for printing. """
    STATUS = 2
    """ Used while locked to query status between printing labels. """


class Speed(enum.StrEnum):
    GRAPHICS = 'graphics'
    TEXT = 'text'
    TURBO = 'turbo'


class Conn:
    """ A Conn represents a network connection to the printer. """

    DPI = 300
    """ DPI is fixed at 300 in both directions for the 550 series. """

    DEFAULT_TIMEOUT = 30
    POLL_INTERVAL = 0.5

    def __init__(self, ip_addr: str, port: int):
        self.ip_addr = ip_addr
        self.port = port
        self.print_socket: Optional[socket.socket] = None

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def _dial(self) -> None:
        self.print_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Prioritize latency over throughput.
        self.print_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        # No individual label data transfer should take longer than this.
        self.print_socket.settimeout(Conn.DEFAULT_TIMEOUT)
        self.print_socket.connect((self.ip_addr, self.port))
        logger.debug("socket connected")

    def close(self) -> None:
        """
        close releases all resources associated with the connection. It is safe
        to call this method multiple times.
        """
        if self.print_socket is not None:
            self.print_socket.close()
            self.print_socket = None

    def send_command(self, cmd: str, *more: int) -> None:
        """
        send_commands writes an escape charactor, a single-character command,
        and an optional number of bytes.
        """
        if self.print_socket is None:
            self._dial()
        out = bytearray([0x1b, ord(cmd)]) + bytearray(more)
        self.print_socket.sendall(out)

    def status_report(self, intent: LockIntent = LockIntent.NONE) -> StatusReport:
        """
        status_report retrieves the printer's current state. This method is also
        used to acquire the lock on the print interface to be able to send a
        print job.
        """
        try:
            self.send_command("A", intent.value)
            status_bytes = bytearray()
            while len(status_bytes) < StatusReport.LENGTH:
                status_bytes += self.print_socket.recv(StatusReport.LENGTH - len(status_bytes))
        except ConnectionResetError:
            # The printer will drop the connection if another print job is
            # running. We'll close our connection, with the expectation that
            # we're being called in a loop, and return a fake status report.
            self.close()
            status_bytes = bytearray(StatusReport.LENGTH)
            status_bytes[0] = PrinterState.BUSY.value

        ret = StatusReport(status_bytes)
        logger.debug("printer status: %s", ret)
        return ret

    def start_job(self, speed: Speed = Speed.GRAPHICS) -> None:
        """
        start_job sends the necessary initialization strings to the printer.

        :param speed: Controls print quality. Not all printer models support :py:attr:`Conn.DPI`.
        """
        self.send_command("s", 1, 0, 0, 0)  # start job 1 (little-endian order)
        self.send_command("e")  # use default density
        self.send_command("i" if speed == Speed.GRAPHICS else "h")  # Graphics or text mode
        self.send_command("T", 0x20 if speed == Speed.TURBO else 0x10)  # High- or normal-speed
        self.send_command("L", 0, 0)  # use chip-based media length

    def send_label(self, index: int, img: Image) -> None:
        """
        :param index: A counter to use with status reporting.
        :param img: The label image as intended to be read (i.e. landscape
        aspect ratio). It is imperative that the image has been rasterized at
        Conn.DPI resolution.
        """

        # Rotate to portait orientation for the printer.
        img = img.rotate(270, expand=1)
        # Convert to B&W.
        data = img.convert('L').point(lambda x: 0 if x > 200 else 1, mode='1').tobytes()

        # We've swapped the dimensions.
        width, height = img.size
        # Pad the label height to byte-align the data
        dot_height = math.ceil(width / 8) * 8

        # Start of label.
        self.send_command("n", index & 0xFF, (index >> 8) & 0xFF)

        # Send label data header.
        self.send_command(
            "D",
            1,  # bits per pixel, always 1
            2,  # align to bottom of label, always 2
            height & 0xFF,
            (height >> 8) & 0xFF,
            (height >> 16) & 0xFF,
            (height >> 24) & 0xFF,
            dot_height & 0xFF,
            (dot_height >> 8) & 0xFF,
            (dot_height >> 16) & 0xFF,
            (dot_height >> 24) & 0xFF
        )

        self.print_socket.sendall(data)

        # Feed to start of next label.
        self.send_command("G")

    def wait_until_state(self,
                         until: PrinterState,
                         deadline: float | None = None,
                         intent: LockIntent = LockIntent.NONE,
                         ) -> StatusReport:
        """
        wait_until_state loops until the printer is in the required state before
        returning. A StatusReportError will be raised if the printer has not
        reached the desired state before the deadline.
        """
        if deadline is None:
            deadline = time.time() + Conn.DEFAULT_TIMEOUT
        while True:
            report = self.status_report(intent)
            if report.printer_state == until:
                return report
            time.sleep(Conn.POLL_INTERVAL)
            if time.time() >= deadline:
                raise StatusReportError("deadline exceeded waiting for printer", report)
