import os
from pathlib import Path

VERSION = "4.8.2"
SCORING_MODEL_VERSION = "1.0"
DEFAULT_ENGINEERING_THRESHOLD = 160
COS_MANDATORY_GATE = 12
MAX_UPLOAD_BYTES = 16 * 1024 * 1024
ALLOWED_EXTENSIONS = {".docx", ".pdf"}
WEIGHTS = {"urgency": .25, "operational": .25, "customer_fleet": .15, "financial": .15, "breadth": .10, "readiness": .10}
LABELS = {"urgency":"Urgency","operational":"Operational","customer_fleet":"Customer / Fleet","financial":"Financial","breadth":"Breadth","readiness":"Readiness"}
LIFECYCLE_PHASE_LABELS = {
    "Phase 1": "Phase 1",
    "Phase 2": "Phase 2",
    "Phase 3": "Phase 3",
    "Phase 4": "Phase 4",
    "Phase 5": "Phase 5",
    "Phase 6": "Phase 6",
    "Phase 7": "Phase 7",
}
DEFAULT_LIFECYCLE_PHASE = "Phase 3"


class BaseConfig:
    """Environment-independent application defaults."""

    MAX_CONTENT_LENGTH = MAX_UPLOAD_BYTES
    UPLOAD_FOLDER = Path(__file__).resolve().parent / "uploads"
    CTI_DATABASE = None
    DEBUG = False
    TESTING = False


class DevelopmentConfig(BaseConfig):
    DEBUG = False
    SECRET_KEY = os.environ.get("CTI_SECRET_KEY", "cti-v482-development-only")


class TestingConfig(BaseConfig):
    TESTING = True
    SECRET_KEY = os.environ.get("CTI_SECRET_KEY", "cti-v482-test-only")


class ProductionConfig(BaseConfig):
    DEBUG = False

    @property
    def SECRET_KEY(self):
        secret = os.environ.get("CTI_SECRET_KEY")
        if not secret:
            raise RuntimeError("CTI_SECRET_KEY must be set outside development/testing")
        return secret


CONFIGURATIONS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def configuration_name():
    return os.environ.get("CTI_ENV", "development").strip().lower()


def apply_environment_overrides(config):
    database = os.environ.get("CTI_DATABASE")
    upload_folder = os.environ.get("CTI_UPLOAD_FOLDER")
    if database:
        config["CTI_DATABASE"] = database
    if upload_folder:
        config["UPLOAD_FOLDER"] = Path(upload_folder)
