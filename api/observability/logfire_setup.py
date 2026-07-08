"""Pydantic Logfire observability setup.

Instruments:
- pydantic-ai agents (LLM calls, tokens, latency, prompts/responses)
- FastAPI (HTTP requests, response times, status codes)
- httpx (outbound calls to OpenAI, Pinecone, etc.)
- Python stdlib logging (forwards all log lines to Logfire)

Call `setup_logfire(app)` once at startup, before any routes are registered.
"""

from __future__ import annotations

import logging
import warnings

logger = logging.getLogger(__name__)


def _silence_otel_export_errors() -> None:
    """Silence the OpenTelemetry 401 spam when the Logfire token is invalid.

    When the token is bad, the OTLP exporter retries every few seconds forever
    and floods stderr. We drop those specific error messages — they're not
    actionable and the underlying Logfire: 401 warning is already shown once.
    """
    for name in (
        "opentelemetry.exporter.otlp.proto.http.trace_exporter",
        "opentelemetry.exporter.otlp.proto.http.metric_exporter",
    ):
        logging.getLogger(name).setLevel(logging.CRITICAL)


def setup_logfire(app=None) -> bool:
    """Configure Logfire. Returns True if successfully enabled, False if skipped."""
    from api import config

    token = config.LOGFIRE_TOKEN
    if not token:
        logger.info("Logfire: LOGFIRE_TOKEN not set — observability disabled")
        return False

    try:
        import logfire
        import requests

        # Validate the token BEFORE configuring Logfire, so we can fail fast
        # and avoid the OTEL exporter spamming 401 errors on retry loops.
        try:
            r = requests.get(
                "https://logfire-api.pydantic.dev/v1/info",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5,
            )
            if r.status_code == 401:
                logger.warning(
                    "Logfire: token is invalid (401 from Logfire API). "
                    "Generate a new write token at https://logfire.pydantic.dev "
                    "and update LOGFIRE_TOKEN in .env. Observability disabled."
                )
                return False
            if r.status_code >= 400 and r.status_code != 404:
                # 404 is ok — the /info endpoint may not exist but token shape is valid
                logger.warning(
                    "Logfire: token validation returned %d — observability disabled",
                    r.status_code,
                )
                return False
        except Exception as exc:
            logger.warning("Logfire: token validation network error: %s", exc)
            return False

        # Suppress harmless warnings
        warnings.filterwarnings(
            "ignore",
            message="Logfire API returned status code 401",
            category=UserWarning,
        )

        logfire.configure(
            token=token,
            service_name="smartshop-api",
            service_version="2.0",
            send_to_logfire=True,
            inspect_arguments=False,
        )

        logfire.instrument_pydantic_ai()
        logfire.instrument_httpx(
            capture_request_body=False,
            capture_response_body=False,
        )
        if app is not None:
            logfire.instrument_fastapi(app, capture_headers=False)
        logfire.install_auto_tracing(
            modules=["api"],
            min_duration=0.0,
            check_imported_modules="ignore",
        )

        logger.info("Logfire: observability enabled (service=smartshop-api)")
        return True

    except ImportError as exc:
        logger.warning("Logfire: missing package — %s", exc)
        return False
    except Exception as exc:
        logger.warning("Logfire: setup failed: %s", exc)
        # Still silence the OTEL spam if setup partially succeeded
        _silence_otel_export_errors()
        return False
