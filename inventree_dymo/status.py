from enum import Enum


class MediaState(Enum):
    UNKNOWN = 0
    BAY_OPEN = 1
    NOT_PRESENT = 2
    NOT_INSERTED_CORRECTLY = 3
    LEVEL_UNKNOWN = 4
    LEVEL_EMPTY = 5
    LEVEL_CRITICAL = 6
    LEVEL_LOW = 7
    LEVEL_OK = 8
    JAMMED = 9
    COUNTERFEIT = 10

    @classmethod
    def _missing_(cls, value):
        return cls.UNKNOWN

    @property
    def can_print(self) -> bool:
        match self:
            case MediaState.LEVEL_OK | MediaState.LEVEL_LOW | MediaState.LEVEL_CRITICAL:
                return True
            case _:
                return False


class PrintHeadState(Enum):
    PRINT_HEAD_OK = 0
    PRINT_HEAD_OVERHEAT = 1
    PRINT_HEAD_UNKNOWN = 4096

    @classmethod
    def _missing_(cls, value):
        return cls.PRINT_HEAD_UNKNOWN


class PrintHeadVoltage(Enum):
    UNKNOWN = 0
    OK = 1
    LOW = 2
    CRITICAL = 3
    TOO_LOW = 4

    @classmethod
    def _missing_(cls, value):
        return cls.UNKNOWN


class PrinterState(Enum):
    """
    PrinterState indicates whether a network connection holds the printer
    interface lock or if the printer is able to grant a new lock.
    """
    IDLE = 0
    PRINTING = 1
    ERROR = 2
    CANCEL = 3

    BUSY = 4
    """ The printer may be waking up from standby or servicing another job. """

    UNLOCKED = 5
    """ The printer will now accept lock requests. """

    UNKNOWN = 4096

    @classmethod
    def _missing_(cls, value):
        return cls.UNKNOWN


class PSUState(Enum):
    UNKNOWN = 0
    PRESENT = 1

    @classmethod
    def _missing_(cls, value):
        return cls.UNKNOWN


class StatusReport:
    """ A StatusReport is a 32-byte value returned by an ESC A command. """

    LENGTH = 32

    def __init__(self, data: bytes):
        if (len(data)) != StatusReport.LENGTH:
            raise Exception(f"exactly {StatusReport.LENGTH} bytes required, received {len(data)}")
        self.data = data

    def __str__(self) -> str:
        return "\n".join([
            f"State: {self.printer_state}",
            f"Media: {self.media_state}",
            f"Label SKU: {self.label_sku}",
            f"Remaining Label Count: {self.remaining_label_count}",
            f"Job ID: {self.print_job_id}",
            f"Label Index: {self.label_index}",
            f"Error ID: {self.error_id}",
            f"Density: {self.density}",
            f"Head: {self.print_head_state}",
            f"Voltage: {self.print_head_voltage}",
            f"PSU: {self.psu_state}",
        ])

    @property
    def can_print(self) -> bool:
        return self.media_state.can_print and self.remaining_label_count > 0

    @property
    def density(self) -> int:
        return self.data[9]

    @property
    def error_id(self) -> int:
        return int.from_bytes(self.data[23:27], byteorder='little')

    @property
    def label_index(self) -> int:
        return int.from_bytes(self.data[5:7], byteorder='little')

    @property
    def label_sku(self) -> str:
        # Data appears to be a null-terminated string.
        chars = self.data[11:23]
        idx = chars.find(0)
        if idx != -1:
            chars = chars[:idx]
        return chars.decode("utf-8")

    @property
    def media_state(self) -> MediaState:
        return MediaState(self.data[10])

    @property
    def print_job_id(self) -> int:
        return int.from_bytes(self.data[1:5], byteorder='little')

    @property
    def print_head_state(self) -> PrintHeadState:
        return PrintHeadState(self.data[8])

    @property
    def print_head_voltage(self) -> PrintHeadVoltage:
        return PrintHeadVoltage(self.data[30] & 0x0F)  # Low nibble

    @property
    def printer_state(self) -> PrinterState:
        return PrinterState(self.data[0])

    @property
    def psu_state(self) -> PSUState:
        return PSUState(self.data[29] & 0x0F)  # Low nibble

    @property
    def remaining_label_count(self) -> int:
        return int.from_bytes(self.data[27:29], byteorder='little')


class StatusReportError(Exception):
    def __init__(self, msg: str, status: StatusReport = None):
        if status is not None:
            msg += "\n" + str(status)
        super().__init__(msg)
        self.status: StatusReport | None = status
