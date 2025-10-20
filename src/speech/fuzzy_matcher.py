"""Fuzzy wake word matching using Levenshtein distance.

This module provides fuzzy matching for wake word detection in speech recognition
systems. It uses Levenshtein distance (edit distance) to match trigger phrases
even when they are transcribed with slight variations.

The implementation is thread-safe and stateless, making it suitable for use in
concurrent audio processing callbacks.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import re

try:
    import Levenshtein
    LEVENSHTEIN_AVAILABLE = True
except ImportError:
    LEVENSHTEIN_AVAILABLE = False


@dataclass
class TriggerMatch:
    """Result of a successful trigger phrase match.

    Attributes:
        matched: Whether a match was found
        distance: Levenshtein distance of the match
        confidence: STT confidence score (0.0-1.0)
        matched_phrase: The actual phrase that matched (e.g., "hey robotic")
        match_start_pos: Character position where match starts in transcript
        match_end_pos: Character position where match ends in transcript
        command_text: Text following the matched trigger
        alternative_index: Which alternative matched (0 = primary)
        trigger_type: Type of trigger (set by caller: "say", "completion", "command")
    """
    matched: bool
    distance: int
    confidence: float
    matched_phrase: str
    match_start_pos: int
    match_end_pos: int
    command_text: str
    alternative_index: int
    trigger_type: str = ""


class FuzzyWakeWordMatcher:
    """Thread-safe fuzzy wake word matcher using Levenshtein distance.

    This class is stateless and safe for concurrent use from multiple threads.
    All configuration is passed to __init__ and stored as immutable attributes.

    Example:
        >>> matcher = FuzzyWakeWordMatcher(threshold=2)
        >>> alternatives = [
        ...     {"transcript": "hey robotic turn on lights", "confidence": 0.9}
        ... ]
        >>> match = matcher.match_trigger("hey robot", "hey robotic turn on lights", alternatives)
        >>> if match:
        ...     print(f"Matched with distance {match.distance}: {match.command_text}")
    """

    def __init__(self, threshold: int = 2):
        """Initialize the fuzzy matcher.

        Args:
            threshold: Maximum Levenshtein distance for a match (0-5)

        Raises:
            ImportError: If python-Levenshtein is not installed
        """
        if not LEVENSHTEIN_AVAILABLE:
            raise ImportError(
                "python-Levenshtein is required for fuzzy matching. "
                "Install with: pip install python-Levenshtein"
            )

        self.threshold = max(0, min(5, threshold))  # Clamp to valid range

    def match_trigger(
        self,
        trigger_phrase: str,
        transcript: str,
        alternatives: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[TriggerMatch]:
        """Match a trigger phrase against transcript and alternatives.

        This method is thread-safe and can be called concurrently.

        Args:
            trigger_phrase: The configured wake word/trigger phrase
            transcript: The primary transcribed text
            alternatives: List of alternative transcriptions with confidence scores
                         Format: [{"transcript": "text", "confidence": 0.95}, ...]

        Returns:
            TriggerMatch object if a match is found, None otherwise
        """
        if not trigger_phrase or not transcript:
            return None

        # Normalize trigger phrase (done once, cached effectively by Python)
        normalized_trigger = self._normalize_text(trigger_phrase)

        # Try primary transcript first
        match = self._match_single_transcript(
            normalized_trigger, transcript, confidence=1.0, alt_index=0
        )
        if match:
            return match

        # Try alternatives if provided
        if alternatives:
            for idx, alt in enumerate(alternatives[1:], start=1):  # Skip first (already checked)
                if idx >= 5:  # Hardcoded limit for MVP
                    break

                alt_text = alt.get("transcript", "")
                alt_confidence = alt.get("confidence", 0.0)

                if not alt_text or alt_confidence < 0.5:  # Skip low-confidence alternatives
                    continue

                match = self._match_single_transcript(
                    normalized_trigger, alt_text, confidence=alt_confidence, alt_index=idx
                )
                if match:
                    return match

        return None

    def _match_single_transcript(
        self,
        normalized_trigger: str,
        transcript: str,
        confidence: float,
        alt_index: int
    ) -> Optional[TriggerMatch]:
        """Match trigger against a single transcript using sliding window.

        Args:
            normalized_trigger: Pre-normalized trigger phrase
            transcript: Raw transcript text
            confidence: STT confidence for this transcript
            alt_index: Index of this alternative (0 = primary)

        Returns:
            TriggerMatch if found, None otherwise
        """
        normalized_transcript = self._normalize_text(transcript)

        # Use simple sliding window based on character count
        # Window size = trigger length ± 20% to allow for length variations
        trigger_len = len(normalized_trigger)
        min_window = max(1, int(trigger_len * 0.8))
        max_window = int(trigger_len * 1.2)

        best_match = None
        best_distance = self.threshold + 1

        # Try different window sizes
        for window_size in range(min_window, max_window + 1):
            # Slide window across transcript
            for i in range(len(normalized_transcript) - window_size + 1):
                candidate = normalized_transcript[i:i + window_size]
                distance = Levenshtein.distance(normalized_trigger, candidate)

                if distance <= self.threshold and distance < best_distance:
                    # Found a better match
                    best_distance = distance

                    # Find original position in unnormalized transcript
                    # This is approximate but works well in practice
                    match_start, match_end = self._find_original_position(
                        transcript, i, i + window_size
                    )

                    # Extract command text (everything after the match)
                    command_text = transcript[match_end:].strip()

                    best_match = TriggerMatch(
                        matched=True,
                        distance=distance,
                        confidence=confidence,
                        matched_phrase=transcript[match_start:match_end],
                        match_start_pos=match_start,
                        match_end_pos=match_end,
                        command_text=command_text,
                        alternative_index=alt_index
                    )

                    # Early exit if we found exact match
                    if distance == 0:
                        return best_match

        return best_match

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison.

        Normalization steps:
        1. Convert to lowercase
        2. Remove most punctuation (keep apostrophes for contractions)
        3. Collapse multiple spaces to single space
        4. Strip leading/trailing whitespace

        Args:
            text: Raw text to normalize

        Returns:
            Normalized text
        """
        # Lowercase
        text = text.lower()

        # Remove punctuation except apostrophes (for contractions like "can't")
        text = re.sub(r"[^\w\s']", " ", text)

        # Collapse multiple spaces
        text = re.sub(r"\s+", " ", text)

        # Strip whitespace
        text = text.strip()

        return text

    def _find_original_position(
        self,
        original_text: str,
        norm_start: int,
        norm_end: int
    ) -> tuple:
        """Find position in original text corresponding to normalized text position.

        This is approximate but works well for extracting command text.

        Args:
            original_text: Original unnormalized text
            norm_start: Start position in normalized text
            norm_end: End position in normalized text

        Returns:
            Tuple of (start_pos, end_pos) in original text
        """
        # Simple heuristic: normalize character by character and track positions
        norm_chars_seen = 0
        start_pos = 0
        end_pos = len(original_text)

        for i, char in enumerate(original_text):
            # Check if this character would be kept in normalization
            normalized_char = self._normalize_text(char)

            if normalized_char:
                if norm_chars_seen == norm_start:
                    start_pos = i
                if norm_chars_seen == norm_end:
                    end_pos = i
                    break
                norm_chars_seen += len(normalized_char)

        return start_pos, end_pos
