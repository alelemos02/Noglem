"""Optional LLM-based validation using Claude API for tag disambiguation."""

import json
import logging
from typing import List, Optional

from app.services.pid.models.instrument import ExtractionResult, Instrument

logger = logging.getLogger(__name__)


def validate_with_llm(
    result: ExtractionResult,
    api_key: Optional[str] = None,
    model: str = "claude-sonnet-4-20250514",
) -> None:
    """Use Claude API to validate and disambiguate detected instruments.

    This is an optional post-processing step that:
    1. Reviews low-confidence detections
    2. Suggests corrections for ambiguous tags
    3. Validates ISA type assignments semantically

    Requires the ANTHROPIC_API_KEY environment variable or api_key parameter.
    """
    try:
        import anthropic
    except ImportError:
        logger.error(
            "anthropic package not installed. "
            "Install with: pip install anthropic"
        )
        return

    import os
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        logger.error(
            "ANTHROPIC_API_KEY not set. "
            "Set the environment variable or pass api_key parameter."
        )
        return

    client = anthropic.Anthropic(api_key=key)

    # Collect instruments needing review
    to_review = [
        inst for inst in result.instruments
        if inst.confidence < 0.7
    ]

    if not to_review:
        logger.info("LLM validation: no low-confidence tags to review")
        return

    logger.info(f"LLM validation: reviewing {len(to_review)} low-confidence tags")

    # Process in batches of 20
    batch_size = 20
    for i in range(0, len(to_review), batch_size):
        batch = to_review[i:i + batch_size]
        _review_batch(client, model, batch, result)


def _review_batch(
    client,
    model: str,
    instruments: List[Instrument],
    result: ExtractionResult,
) -> None:
    """Send a batch of instruments to Claude for review."""
    tags_data = []
    for inst in instruments:
        tags_data.append({
            "tag": inst.tag,
            "isa_type": inst.isa_type,
            "isa_description": inst.isa_description,
            "confidence": inst.confidence,
            "equipment_ref": inst.equipment_ref,
            "page": inst.page_index + 1,
        })

    prompt = f"""You are an instrumentation engineer reviewing P&ID instrument tags.

Review these detected instrument tags and identify any that seem incorrect or ambiguous.
For each tag, respond with:
- "valid": true/false
- "suggestion": corrected tag if invalid, or empty string
- "reason": brief explanation

Tags to review:
{json.dumps(tags_data, indent=2)}

Respond with a JSON array of objects, one per tag, in the same order.
Each object should have: "tag", "valid", "suggestion", "reason"

Only respond with the JSON array, no other text."""

    try:
        response = client.messages.create(
            model=model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = response.content[0].text.strip()

        # Handle potential markdown code block wrapping
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1])

        reviews = json.loads(response_text)

        for review, inst in zip(reviews, instruments):
            if not review.get("valid", True):
                suggestion = review.get("suggestion", "")
                reason = review.get("reason", "")
                result.warnings.append(
                    f"LLM REVIEW: {inst.tag} may be incorrect. "
                    f"Suggestion: {suggestion}. Reason: {reason}"
                )
                logger.info(
                    f"LLM flagged {inst.tag}: {reason} "
                    f"(suggestion: {suggestion})"
                )

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse LLM response: {e}")
    except Exception as e:
        logger.error(f"LLM validation error: {e}")
