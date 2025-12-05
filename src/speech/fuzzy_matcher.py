"""Fuzzy wake word matching using Levenshtein distance via rapidfuzz.

This module provides fuzzy matching for wake word detection in speech recognition
systems. It uses Levenshtein distance (edit distance) on word-level windows to
match trigger phrases even when they are transcribed with slight variations.

The implementation uses word boundaries to prevent partial-word matches and
leverages rapidfuzz for high-performance distance calculations with pre-built
ARM wheels for Raspberry Pi compatibility.

The implementation is thread-safe and stateless, making it suitable for use in
concurrent audio processing callbacks.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import re

try:
    from rapidfuzz.distance import Levenshtein

    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False


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

    This class uses word-boundary matching to prevent partial-word false positives
    (e.g., matching "hey robot" inside "they robotic"). It operates on word-level
    windows rather than character-level sliding windows for better accuracy.

    All configuration is passed to __init__ and stored as immutable attributes,
    making this class stateless and safe for concurrent use from multiple threads.

    Example:
        >>> matcher = FuzzyWakeWordMatcher(threshold=2)
        >>> alternatives = [
        ...     {"transcript": "hey robotic turn on lights", "confidence": 0.9},
        ...     {"transcript": "hey robot turn on lights", "confidence": 0.95},
        ...     {"transcript": "hey robbed turn on lights", "confidence": 0.75}
        ... ]
        >>> match = matcher.match_trigger("hey robot", "hey robotic turn on lights", alternatives)
        >>> if match:
        ...     # Returns the 0.95 confidence match ("hey robot") even though primary was checked first
        ...     print(f"Matched '{match.matched_phrase}' (confidence: {match.confidence})")
        ...     print(f"Command: {match.command_text}")
    """

    def __init__(self, threshold: int = 2):
        """Initialize the fuzzy matcher.

        Args:
            threshold: Maximum Levenshtein distance for a match (0-5)

        Raises:
            ImportError: If rapidfuzz is not installed
        """
        if not RAPIDFUZZ_AVAILABLE:
            raise ImportError(
                "rapidfuzz is required for fuzzy matching. "
                "Install with: pip install rapidfuzz"
            )

        self.threshold = max(0, min(5, threshold))  # Clamp to valid range

    def match_trigger(
        self,
        trigger_phrase: str,
        transcript: str,
        alternatives: Optional[List[Dict[str, Any]]] = None,
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
        if alternatives and len(alternatives) > 1:
            # Sort alternatives by confidence (descending) to check highest confidence first
            # Skip index 0 (primary transcript already checked) and create tuples of (original_index, alt)
            alternatives_with_indices = [
                (idx, alt) for idx, alt in enumerate(alternatives[1:], start=1)
            ]

            # Sort by confidence descending
            sorted_alternatives = sorted(
                alternatives_with_indices,
                key=lambda x: x[1].get("confidence", 0.0),
                reverse=True,
            )

            for original_idx, alt in sorted_alternatives[
                :4
            ]:  # Check top 4 alternatives
                alt_text = alt.get("transcript", "")
                alt_confidence = alt.get("confidence", 0.0)

                if (
                    not alt_text or alt_confidence < 0.5
                ):  # Skip low-confidence alternatives
                    continue

                match = self._match_single_transcript(
                    normalized_trigger,
                    alt_text,
                    confidence=alt_confidence,
                    alt_index=original_idx,
                )
                if match:
                    return match

        return None

    def _match_single_transcript(
        self,
        normalized_trigger: str,
        transcript: str,
        confidence: float,
        alt_index: int,
    ) -> Optional[TriggerMatch]:
        """Match trigger against a single transcript using word-boundary windows.

        This approach splits text into words and matches against N-word windows,
        preventing partial-word matches and simplifying command extraction.

        Args:
            normalized_trigger: Pre-normalized trigger phrase
            transcript: Raw transcript text
            confidence: STT confidence for this transcript
            alt_index: Index of this alternative (0 = primary)

        Returns:
            TriggerMatch if found, None otherwise
        """
        normalized_transcript = self._normalize_text(transcript)

        # Split into words
        trigger_words = normalized_trigger.split()
        transcript_words = normalized_transcript.split()

        if not trigger_words or not transcript_words:
            return None

        # Track best match
        best_distance = self.threshold + 1
        best_position = -1
        best_word_count = len(trigger_words)

        # Try N-word windows where N is around the trigger word count
        # Range: trigger_word_count - 1 to trigger_word_count + 1
        # This allows for word insertions/deletions while staying focused
        for num_words in range(max(1, len(trigger_words) - 1), len(trigger_words) + 2):
            for i in range(len(transcript_words) - num_words + 1):
                # Get window of words
                window_words = transcript_words[i : i + num_words]
                window_text = " ".join(window_words)

                # Calculate Levenshtein distance using rapidfuzz
                distance = Levenshtein.distance(normalized_trigger, window_text)

                # Update if better match found
                if distance < best_distance:
                    best_distance = distance
                    best_position = i
                    best_word_count = num_words

        # Check if we found a match within threshold
        if best_distance > self.threshold or best_position == -1:
            return None

        # Extract the matched words from normalized transcript
        matched_words = transcript_words[
            best_position : best_position + best_word_count
        ]

        # Map back to original transcript to get:
        # 1. The actual matched phrase (with original casing/punctuation)
        # 2. The command text (everything after the match)
        match_start, match_end = self._find_word_positions_in_original(
            transcript, matched_words, best_position
        )

        # Extract command text (everything after the matched trigger)
        command_text = transcript[match_end:].strip()

        # Get the actual matched phrase from original transcript
        matched_phrase = transcript[match_start:match_end].strip()

        return TriggerMatch(
            matched=True,
            distance=best_distance,
            confidence=confidence,
            matched_phrase=matched_phrase,
            match_start_pos=match_start,
            match_end_pos=match_end,
            command_text=command_text,
            alternative_index=alt_index,
        )

    def _find_word_positions_in_original(
        self, original_text: str, matched_words: List[str], word_position: int
    ) -> tuple:
        """Find character positions in original text for matched words.

        This maps word positions from normalized text back to character positions
        in the original text by reconstructing the word boundaries.

        Args:
            original_text: Original unnormalized text
            matched_words: List of matched words from normalized text
            word_position: Starting word index in the normalized word list

        Returns:
            Tuple of (start_char_pos, end_char_pos) in original text
        """
        # Normalize the original text to get word boundaries
        normalized = self._normalize_text(original_text)
        all_words = normalized.split()

        # Find the position of these words in the normalized text
        # Build the text up to and including the matched words
        if word_position < len(all_words):
            # Text before the match
            words_before = all_words[:word_position]
            text_before_match = " ".join(words_before)

            # The matched text
            matched_text = " ".join(matched_words)

            # Find where this appears in the original (case-insensitive search)
            original_lower = original_text.lower()

            # Search for the matched text after the "before" text
            search_start = 0
            if words_before:
                # Find where the "before" text ends
                before_idx = original_lower.find(text_before_match.lower())
                if before_idx != -1:
                    search_start = before_idx + len(text_before_match)

            # Find the matched text starting from search_start
            match_idx = original_lower.find(matched_text.lower(), search_start)

            if match_idx != -1:
                # Found it! Return the positions
                match_start = match_idx
                match_end = match_idx + len(matched_text)
                return match_start, match_end

        # Fallback: use simple search
        # This handles edge cases where word boundaries don't align perfectly
        normalized_lower = self._normalize_text(original_text).lower()
        matched_text = " ".join(matched_words)

        idx = normalized_lower.find(matched_text)
        if idx != -1:
            # Approximate position in original
            # Count how many characters we need to skip
            return idx, idx + len(matched_text)

        # Last resort: return beginning
        return 0, len(" ".join(matched_words))

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
