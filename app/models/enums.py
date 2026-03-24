import enum


class PlanLayer(str, enum.Enum):
    CONTEXT = "CONTEXT"
    SETUP = "SETUP"
    CONFIRMATION = "CONFIRMATION"
    ENTRY = "ENTRY"
    RISK = "RISK"
    MANAGEMENT = "MANAGEMENT"
    BEHAVIORAL = "BEHAVIORAL"


class RuleType(str, enum.Enum):
    REQUIRED = "REQUIRED"
    OPTIONAL = "OPTIONAL"
    ADVISORY = "ADVISORY"


class IdeaState(str, enum.Enum):
    WATCHING = "WATCHING"
    SETUP_VALID = "SETUP_VALID"
    CONFIRMED = "CONFIRMED"
    ENTRY_PERMITTED = "ENTRY_PERMITTED"
    IN_TRADE = "IN_TRADE"
    MANAGED = "MANAGED"
    CLOSED = "CLOSED"
    INVALIDATED = "INVALIDATED"


class Direction(str, enum.Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class SetupGrade(str, enum.Enum):
    A = "A"
    B = "B"
    C = "C"


class TradeState(str, enum.Enum):
    OPEN = "OPEN"
    PARTIAL = "PARTIAL"
    RUNNER = "RUNNER"
    CLOSED = "CLOSED"


class JournalStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    COMPLETED = "COMPLETED"


class AIStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AssetClass(str, enum.Enum):
    FX = "FX"
    STOCKS = "STOCKS"
    INDICES = "INDICES"
    FUTURES = "FUTURES"
    CRYPTO = "CRYPTO"


class InterpretationStatus(str, enum.Enum):
    # Phase 1 (data-source classification) — current values
    OHLC_COMPUTABLE = "OHLC_COMPUTABLE"
    OHLC_APPROXIMATE = "OHLC_APPROXIMATE"
    LIVE_ONLY = "LIVE_ONLY"
    # Legacy aliases kept for backward-compat with stored JSONB data
    TESTABLE = "TESTABLE"
    APPROXIMATED = "APPROXIMATED"
    NOT_TESTABLE = "NOT_TESTABLE"


class ValidationRunStatus(str, enum.Enum):
    PENDING = "PENDING"
    COMPILING = "COMPILING"
    REPLAYING = "REPLAYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ValidationMode(str, enum.Enum):
    INTERPRETABILITY = "INTERPRETABILITY"
    REPLAY = "REPLAY"
