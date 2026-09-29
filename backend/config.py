"""Central config — secrets from env, never hardcoded in prod."""
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENV = os.getenv("CLINIVA_ENV", "demo")

RX_SECRET = os.getenv("CLINIVA_RX_SECRET", "cliniva-hackathon-demo-secret-change-in-prod")
if ENV == "prod" and RX_SECRET.startswith("cliniva-hackathon"):
    raise RuntimeError("CLINIVA_RX_SECRET must be set in prod")

VERIFY_BASE = os.getenv("CLINIVA_VERIFY_BASE", "http://127.0.0.1:8000/verify-page")
HINDSIGHT_URL = os.getenv("HINDSIGHT_URL", "")
DATA_RESIDENCY = os.getenv("CLINIVA_REGION", "ap-south-1 (Mumbai-target)")
ABDM_MODE = os.getenv("ABDM_MODE", "mock")  # mock | sandbox | prod
ABDM_SANDBOX = os.getenv("ABDM_SANDBOX", "https://sandbox.abdm.gov.in")
SMS_PROVIDER = os.getenv("SMS_PROVIDER", "mock")  # mock | twilio
