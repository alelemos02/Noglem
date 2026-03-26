from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ISAFirstLetter(Enum):
    """ISA 5.1 First Letter - Measured/Initiating Variable."""
    A = "Analysis"
    B = "Burner/Combustion"
    C = "Conductivity"  # User's choice
    D = "Density/Specific Gravity"
    E = "Voltage"
    F = "Flow Rate"
    G = "Gaging/Position"
    H = "Hand/Manual"
    I = "Current"
    J = "Power"
    K = "Time/Schedule"
    L = "Level"
    M = "Moisture/Humidity"
    N = "User's Choice"
    O = "User's Choice"
    P = "Pressure/Vacuum"
    Q = "Quantity"
    R = "Radiation"
    S = "Speed/Frequency"
    T = "Temperature"
    U = "Multivariable"
    V = "Vibration"
    W = "Weight/Force"
    X = "Unclassified"
    Y = "Event/State"
    Z = "Position/Dimension"


class ISASucceedingLetter(Enum):
    """ISA 5.1 Succeeding Letters - Readout/Output Function."""
    A = "Alarm"
    B = "User's Choice"
    C = "Controller"
    D = "Differential"
    E = "Sensor/Primary Element"
    G = "Glass/Gauge/Viewing"
    H = "High"
    HH = "High-High"
    I = "Indicator"
    K = "Control Station"
    L = "Low"
    LL = "Low-Low"
    N = "User's Choice"
    O = "Orifice"
    P = "Point/Test Connection"
    Q = "Totalize/Integrate"
    R = "Record"
    S = "Switch"
    T = "Transmitter"
    U = "Multifunction"
    V = "Valve/Damper/Louver"
    W = "Well"
    X = "Unclassified"
    Y = "Relay/Compute/Convert"
    Z = "Driver/Actuator/Final Element"


# Complete ISA type descriptions for common instrument types
ISA_TYPE_DESCRIPTIONS = {
    # Pressure
    "PI": "Pressure Indicator",
    "PIT": "Pressure Indicating Transmitter",
    "PT": "Pressure Transmitter",
    "PIC": "Pressure Indicating Controller",
    "PSV": "Pressure Safety Valve",
    "PSE": "Pressure Safety Element",
    "PDI": "Pressure Differential Indicator",
    "PDIT": "Pressure Differential Indicating Transmitter",
    "PDT": "Pressure Differential Transmitter",
    "PS": "Pressure Switch",
    "PSH": "Pressure Switch High",
    "PSL": "Pressure Switch Low",
    "PSHH": "Pressure Switch High-High",
    "PSLL": "Pressure Switch Low-Low",
    "PAH": "Pressure Alarm High",
    "PAL": "Pressure Alarm Low",
    "PAHH": "Pressure Alarm High-High",
    "PALL": "Pressure Alarm Low-Low",
    "PV": "Pressure Valve",
    "PCV": "Pressure Control Valve",
    "PY": "Pressure Relay/Compute",
    "PE": "Pressure Element",
    "PG": "Pressure Gauge",
    # Temperature
    "TI": "Temperature Indicator",
    "TIT": "Temperature Indicating Transmitter",
    "TT": "Temperature Transmitter",
    "TE": "Temperature Element",
    "TIC": "Temperature Indicating Controller",
    "TCV": "Temperature Control Valve",
    "TS": "Temperature Switch",
    "TSH": "Temperature Switch High",
    "TSL": "Temperature Switch Low",
    "TSHH": "Temperature Switch High-High",
    "TSLL": "Temperature Switch Low-Low",
    "TAH": "Temperature Alarm High",
    "TAL": "Temperature Alarm Low",
    "TAHH": "Temperature Alarm High-High",
    "TALL": "Temperature Alarm Low-Low",
    "TSV": "Temperature Safety Valve",
    "TW": "Temperature Well (Thermowell)",
    "TV": "Temperature Valve",
    "TY": "Temperature Relay/Compute",
    "TR": "Temperature Recorder",
    "TG": "Temperature Gauge",
    # Flow
    "FI": "Flow Indicator",
    "FIT": "Flow Indicating Transmitter",
    "FT": "Flow Transmitter",
    "FE": "Flow Element",
    "FIC": "Flow Indicating Controller",
    "FCV": "Flow Control Valve",
    "FQ": "Flow Totalizer",
    "FQI": "Flow Quantity Indicator",
    "FQIT": "Flow Quantity Indicating Transmitter",
    "FS": "Flow Switch",
    "FSH": "Flow Switch High",
    "FSL": "Flow Switch Low",
    "FAH": "Flow Alarm High",
    "FAL": "Flow Alarm Low",
    "FV": "Flow Valve",
    "FY": "Flow Relay/Compute",
    "FO": "Flow Orifice",
    "FR": "Flow Recorder",
    "FC": "Flow Controller",
    "FG": "Flow Gauge",
    # Level
    "LI": "Level Indicator",
    "LIT": "Level Indicating Transmitter",
    "LT": "Level Transmitter",
    "LG": "Level Gauge/Glass",
    "LIC": "Level Indicating Controller",
    "LCV": "Level Control Valve",
    "LS": "Level Switch",
    "LSH": "Level Switch High",
    "LSL": "Level Switch Low",
    "LSHH": "Level Switch High-High",
    "LSLL": "Level Switch Low-Low",
    "LAH": "Level Alarm High",
    "LAL": "Level Alarm Low",
    "LAHH": "Level Alarm High-High",
    "LALL": "Level Alarm Low-Low",
    "LV": "Level Valve",
    "LY": "Level Relay/Compute",
    "LR": "Level Recorder",
    # Analysis
    "AI": "Analysis Indicator",
    "AIT": "Analysis Indicating Transmitter",
    "AT": "Analysis Transmitter",
    "AE": "Analysis Element",
    "AIC": "Analysis Indicating Controller",
    "AS": "Analysis Switch",
    "AY": "Analysis Relay/Compute",
    "AR": "Analysis Recorder",
    # Valve/On-Off
    "XV": "On-Off Valve (Unclassified)",
    # Hand / Manual
    "HS": "Hand Switch",
    "HSA": "Hand Switch Alarm",
    "HSS": "Hand Switch Safety",
    "HIC": "Hand Indicating Controller",
    "HOA": "Hand-Off-Auto Switch",
    "HC": "Hand Controller",
    "HV": "Hand Valve",
    "HCV": "Hand Control Valve",
    "SDV": "Shutdown Valve",
    "BDV": "Blowdown Valve",
    "SV": "Solenoid Valve",
    "ZA": "Position Alarm",
    "ZS": "Position Switch",
    "ZT": "Valve Position Transmitter",
    "ZI": "Valve Position Indicator",
    # Motor/Pump accessories
    "XCM": "Motor Control (Start/Stop)",
    "HCM": "Motor Hand Control",
    "ITM": "Motor Current Transmitter",
    "IIM": "Motor Current Indicator",
    "IE": "Current Element",
    "II": "Current Indicator",
    "ML": "Motor Light",
    "YAM": "Motor Alarm Relay",
    "RIM": "Motor Speed Indicator",
    "SIS": "Safety Instrumented System",
    # Speed
    "SI": "Speed Indicator",
    "SIT": "Speed Indicating Transmitter",
    "ST": "Speed Transmitter",
    "SIC": "Speed Indicating Controller",
    "SS": "Speed Switch",
    "SSH": "Speed Switch High",
    "SSL": "Speed Switch Low",
    "SC": "Speed Controller",
    "SLA": "Speed Low Alarm",
    "SAL": "Speed Alarm Low",
    # Weight
    "WE": "Weight Element",
    "WIT": "Weight Indicating Transmitter",
    "WI": "Weight Indicator",
    "WT": "Weight Transmitter",
    # Vibration
    "VI": "Vibration Indicator",
    "VT": "Vibration Transmitter",
    "VS": "Vibration Switch",
    "VSH": "Vibration Switch High",
    # Event/State/Relay
    "YS": "Event Switch",
    "YV": "Event Valve (Solenoid)",
    "YI": "Event Indicator",
    # Misc
    "PW": "Pump (non-ISA, project-specific)",
    "MW": "Motor (non-ISA, project-specific)",
}

# --- DYNAMIC RULES FOR 'Z' (SAFETY/SYSTEM) MODIFIERS ---
_z_variants = {}
for base_isa, desc in ISA_TYPE_DESCRIPTIONS.items():
    if len(base_isa) >= 2 and base_isa[1] != 'Z':
        z_isa = base_isa[0] + 'Z' + base_isa[1:]
        if z_isa not in ISA_TYPE_DESCRIPTIONS:
            _z_variants[z_isa] = f"{desc} (Safety/SIS)"

ISA_TYPE_DESCRIPTIONS.update(_z_variants)
# -----------------------------------------------------

# Set of all valid ISA type prefixes (sorted by length desc for greedy matching)
ISA_VALID_TYPES = sorted(ISA_TYPE_DESCRIPTIONS.keys(), key=len, reverse=True)


@dataclass
class Position:
    """Bounding box position from PDF extraction."""
    x0: float
    top: float
    x1: float
    bottom: float

    @property
    def center_x(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def center_y(self) -> float:
        return (self.top + self.bottom) / 2

    def distance_to(self, other: "Position") -> float:
        dx = self.center_x - other.center_x
        dy = self.center_y - other.center_y
        return (dx * dx + dy * dy) ** 0.5


@dataclass
class ExtractedWord:
    """A word extracted from PDF with its position."""
    text: str
    position: Position
    page_index: int
    merged: bool = False


@dataclass
class Instrument:
    """An instrument detected in a P&ID."""
    tag: str
    isa_type: str
    isa_description: str
    position: Optional[Position] = None
    page_index: int = 0
    sheet_name: str = ""

    # Parsed components
    area: str = ""
    tag_number: str = ""
    qualifier: str = ""

    # Associations
    equipment_ref: str = ""
    loop_id: str = ""
    furnished_by_package: bool = False
    line_number: str = ""
    service: str = ""

    # Hierarchy
    parent_tag: str = ""
    children_tags: list = field(default_factory=list)

    # Symbology Classification
    symbol: str = "circle"
    is_physical: bool = True
    classification: str = "Instrumento de Campo"

    # Metadata
    confidence: float = 1.0
    notes: list = field(default_factory=list)
    source: str = "primary"


@dataclass
class Equipment:
    """An equipment item detected in a P&ID."""
    tag: str
    position: Optional[Position] = None
    page_index: int = 0
    description: str = ""
    associated_instruments: list = field(default_factory=list)


@dataclass
class Loop:
    """An instrument loop grouping related instruments."""
    loop_id: str
    instruments: list = field(default_factory=list)
    is_complete: bool = False
    missing: list = field(default_factory=list)


@dataclass
class LineNumber:
    """A process line number extracted from a P&ID."""
    full_tag: str
    diameter: str = ""
    spec_class: str = ""
    line_id: str = ""
    service_code: str = ""
    position: Optional[Position] = None
    page_index: int = 0


@dataclass
class DrawingNote:
    """A note extracted from the P&ID drawing."""
    number: int
    text: str
    affects_instruments: bool = False
    affected_types: list = field(default_factory=list)


@dataclass
class DrawingMetadata:
    """Metadata extracted from the title block."""
    document_number: str = ""
    revision: str = ""
    title: str = ""
    area: str = ""
    project: str = ""
    sheet_number: str = ""
    total_sheets: str = ""
    date: str = ""
    scale: str = ""
    drawn_by: str = ""
    checked_by: str = ""


@dataclass
class ExtractionResult:
    """Complete result of processing one or more P&ID sheets."""
    metadata: list = field(default_factory=list)
    instruments: list = field(default_factory=list)
    equipment: list = field(default_factory=list)
    loops: list = field(default_factory=list)
    line_numbers: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    errors: list = field(default_factory=list)
