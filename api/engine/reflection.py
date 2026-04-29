"""Instruction-fidelity audit helpers."""

from __future__ import annotations


def audit_instruction_fidelity(user_input: str, output_text: str) -> dict:
    """Return a lightweight audit record for future reflection workflows."""
    return {
        "user_input_chars": len(user_input or ""),
        "output_chars": len(output_text or ""),
        "has_output": bool((output_text or "").strip()),
    }
