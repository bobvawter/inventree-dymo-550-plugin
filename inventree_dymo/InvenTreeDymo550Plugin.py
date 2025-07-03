import logging
import math
import socket
import time

from django.db import models
from django.db.models.query import QuerySet
from django.utils.translation import gettext_lazy as _
from plugin import InvenTreePlugin
from plugin.machine.machine_types import LabelPrinterBaseDriver, LabelPrinterMachine
from report.models import LabelTemplate
from rest_framework import serializers

from .version import DYMO_PLUGIN_VERSION

logger = logging.getLogger('inventree')


class InvenTreeDymo550Plugin(InvenTreePlugin):
    AUTHOR = "bobvawter"
    DESCRIPTION = "InvenTree Dymo 550 plugin"
    # Machine driver registry is only available in InvenTree 0.14.0 and later
    # Machine driver interface was fixed with 0.16.0 to work inside of inventree workers
    MIN_VERSION = "0.16.0"
    NAME = "InvenTreeDymo550Plugin"
    SLUG = "inventree-dymo-550-plugin"
    TITLE = "InvenTree Dymo 550 Plugin"
    VERSION = DYMO_PLUGIN_VERSION


SPEED_GRAPHICS = 'graphics'
SPEED_TEXT = 'text'
SPEED_TURBO = 'turbo'

class Dymo550LabelPrinterDriver(LabelPrinterBaseDriver):
    """Label printer driver for Dymo 550 printers."""

    DESCRIPTION = "Dymo 550 driver"
    SLUG = "dymo-550-driver"
    NAME = "Dymo 550 Driver"

    class PrintingOptionsSerializer(LabelPrinterBaseDriver.PrintingOptionsSerializer):
        speed = serializers.ChoiceField(
            choices=[(SPEED_GRAPHICS, _('Graphics')), (SPEED_TEXT, _('Text')), (SPEED_TURBO, _("Turbo"))],
            default=SPEED_GRAPHICS,
            label=_('Print Speed'),
            help_text=_('Trade print quality for speed')
        )

    def __init__(self, *args, **kwargs):
        self.print_socket: socket.socket | None = None
        self.MACHINE_SETTINGS = {
            'SERVER': {
                'name': _('Server'),
                'description': _('IP/Hostname of the Dymo print server'),
                'default': 'localhost',
                'required': True,
            },
            'PORT': {
                'name': _('Port'),
                'description': _('Port number of the Dymo print server'),
                'validator': int,
                'default': 9100,
                'required': True,
            },
        }

        super().__init__(*args, **kwargs)

    def get_printing_options_serializer(self, request, *args, **kwargs):
        return self.PrintingOptionsSerializer(*args, **kwargs)

    def print_labels(self, machine: LabelPrinterMachine, label: LabelTemplate, items: QuerySet[models.Model], **kwargs):
        """Print labels using a Dymo label printer."""
        printing_options = kwargs.get('printing_options', {})
        logger.debug("print_labels running")

        self.open_socket(machine.get_setting('SERVER', 'D'), machine.get_setting('PORT', 'D'))
        try:
            self.wait_for_unlocked()
            self.wait_for_lock()
            self.start_job(speed=printing_options.get('speed', SPEED_GRAPHICS))

            index = 1
            for item in items:
                png = self.render_to_png(label, item, dpi=300).rotate(90, expand=1)

                for _copies in range(printing_options.get('copies', 1)):
                    self.send_label(index, png)
                    index = index + 1

            # Advance to tear-off position
            self.send_command("E")

            # End job.
            self.send_command("Q")

        except Exception as e:
            logger.error(e, exc_info=True)
            raise e

        finally:
            if self.print_socket is not None:
                self.print_socket.close()

    def open_socket(self, ip_addr: str, port: int):
        self.print_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.print_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.print_socket.connect((ip_addr, port))
        logger.debug("socket connected")

    def wait_for_idle(self):
        while True:
            self.send_command("A", 0)  # Non-locking status request
            status = self.print_socket.recv(32)
            logger.debug("status: %s", status.hex())
            if status[0] == 0:
                return
            logger.debug("waiting for idle")
            time.sleep(0.5)

    def wait_for_lock(self):
        while True:
            self.send_command("A", 1)  # Locking status request
            status = self.print_socket.recv(32)
            logger.debug("status: %s", status.hex())
            if status[0] == 0:
                err_code = (status[26] << 24) | (status[25] << 16) | (status[24] << 8) | (status[23])
                if err_code != 0:
                    raise Exception(f"printer reports error code {err_code}")
                # Have the lock, make sure the media is ready.
                if status[10] == 6 or status[10] == 7 or status[10] == 8:
                    return
                raise Exception(f"unexpected media state {status[10]}")
            logger.debug("waiting to lock")
            time.sleep(0.5)

    def wait_for_unlocked(self):
        while True:
            self.send_command("A", 0)  # Non-locking status request
            status = self.print_socket.recv(32)
            logger.debug("status: %s", status.hex())
            if status[0] == 5:
                return
            logger.debug("waiting for unlocked state")
            time.sleep(0.5)

    def send_command(self, cmd: str, *more: int):
        """ A utility method to send an escape command """
        out = bytearray([0x1b, ord(cmd)]) + bytearray(more)
        logger.debug(out.hex())
        self.print_socket.sendall(out)

    def start_job(self, speed: str = SPEED_GRAPHICS):
        self.send_command("s", 1, 0, 0, 0)  # start job 1 (little-endian order)
        self.send_command("e")  # use default density
        self.send_command("i" if speed == SPEED_GRAPHICS else "h")  # Graphics or text mode
        self.send_command("T", 0x20 if speed == SPEED_TURBO else 0x10)  # High- or normal-speed
        self.send_command("L", 0, 0)  # use chip-based media length

    def send_label(self, index, png):
        width, height = png.size
        bytes_per_line = math.ceil(width / 8)
        dot_height = bytes_per_line * 8

        # Convert to B&W, then rotate into column-major order.
        data = png.convert('L').point(lambda x: 0 if x > 200 else 1, mode='1').tobytes()
        data = [data[y * bytes_per_line:(y + 1) * bytes_per_line] for y in range(height)]
        data = bytearray(b''.join(data))

        # We've swapped the dimensions.
        height, width = png.size
        logger.debug("data is %d bytes long width=%d height=%d, bytes_per_line=%d, dot_height=%d",
                     len(data), width, height, bytes_per_line, dot_height)

        # Start of label.
        self.send_command("n", index & 0xFF, (index >> 8) & 0xFF)

        # Send label data header.
        self.send_command(
            "D",
            1,  # bits per pixel, always 1
            2,  # align to bottom of label, always 2
            width & 0xFF,
            (width >> 8) & 0xFF,
            (width >> 16) & 0xFF,
            (width >> 24) & 0xFF,
            dot_height & 0xFF,
            (dot_height >> 8) & 0xFF,
            (dot_height >> 16) & 0xFF,
            (dot_height >> 24) & 0xFF
        )

        self.print_socket.sendall(data)

        # Feed to start of next label.
        self.send_command("G")
