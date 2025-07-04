import logging
import socket

from django.db import models
from django.db.models.query import QuerySet
from django.utils.translation import gettext_lazy as _
from plugin import InvenTreePlugin
from plugin.machine.machine_types import LabelPrinterBaseDriver, LabelPrinterMachine
from report.models import LabelTemplate
from rest_framework import serializers

from .conn import Conn, LockIntent, Speed
from .status import PrinterState, StatusReport, StatusReportError
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


class Dymo550LabelPrinterDriver(LabelPrinterBaseDriver):
    """Label printer driver for Dymo 550 printers."""

    DESCRIPTION = "Dymo 550 driver"
    SLUG = "dymo-550-driver"
    NAME = "Dymo 550 Driver"

    class PrintingOptionsSerializer(LabelPrinterBaseDriver.PrintingOptionsSerializer):
        speed = serializers.ChoiceField(
            choices=[(Speed.GRAPHICS, _('Graphics')), (Speed.TEXT, _('Text')), (Speed.TURBO, _("Turbo"))],
            default=Speed.GRAPHICS,
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

    def get_printing_options_serializer(self, _, *args, **kwargs):
        return self.PrintingOptionsSerializer(*args, **kwargs)

    def init_machine(self, machine: LabelPrinterMachine):
        self.restart_machine(machine)

    def restart_machine(self, machine: LabelPrinterMachine):
        try:
            with Conn(machine.get_setting('SERVER', 'D'), machine.get_setting('PORT', 'D')) as c:
                self.set_status_from_report(machine, c.status_report())
        except Exception as e:
            machine.set_status(LabelPrinterMachine.MACHINE_STATUS.DISCONNECTED)
            machine.handle_error(e)

    def update_machine(self, _, machine: LabelPrinterMachine):
        self.restart_machine(machine)

    def print_labels(self, machine: LabelPrinterMachine, label: LabelTemplate, items: QuerySet[models.Model], **kwargs):
        """Print labels using a Dymo label printer."""
        printing_options = kwargs.get('printing_options', {})
        speed = Speed(printing_options.get('speed', Speed.GRAPHICS))
        ip = machine.get_setting('SERVER', 'D')
        port = machine.get_setting('PORT', 'D')

        try:
            with Conn(ip, port) as c:
                # Acquire the lock on the printer. This will block if another
                # print job is underway.
                report = c.wait_until_state(PrinterState.IDLE, intent=LockIntent.LOCK)

                if not report.can_print:
                    raise StatusReportError("printer requires attention", report)

                machine.set_status(LabelPrinterMachine.MACHINE_STATUS.PRINTING)

                # Send start commands to the printer.
                c.start_job(speed)

                # Spool each image to the printer.
                index = 1
                for item in items:
                    png = self.render_to_png(label, item, dpi=Conn.DPI)

                    for _copies in range(printing_options.get('copies', 1)):
                        c.send_label(index, png)
                        index = index + 1

                # Advance to tear-off position.
                c.send_command("E")

                # End job.
                c.send_command("Q")
                machine.set_status(LabelPrinterMachine.MACHINE_STATUS.CONNECTED)
        except StatusReportError as e:
            self.set_status_from_report(machine, e.status)
            machine.handle_error(e)

        except Exception as e:
            machine.set_status(LabelPrinterMachine.MACHINE_STATUS.DISCONNECTED)
            machine.handle_error(e)

    def set_status_from_report(self, machine: LabelPrinterMachine, report: StatusReport):
        if not report.can_print:
            machine.set_status(LabelPrinterMachine.MACHINE_STATUS.NO_MEDIA)
        else:
            machine.set_status(LabelPrinterMachine.MACHINE_STATUS.CONNECTED)
