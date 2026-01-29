"""
Motion Engine - Animation state calculations

This module provides pure functions for computing animation properties
at any given timestamp. All parameters are configurable via MotionSettings.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class CharProperties:
    """Animation properties for a single character at a point in time."""
    opacity: float = 0.0
    blur: float = 20.0
    scale: float = 0.96
    y_offset: float = 6.0
    visible: bool = False


@dataclass
class MotionSettings:
    """Configurable motion parameters."""
    max_words_on_screen: int = 3
    entry_blur_start: float = 20.0
    entry_duration: float = 0.28
    char_stagger: float = 0.025
    entry_scale: float = 0.96
    y_drift: float = 6.0
    entry_opacity_start: float = 0.1


def ease_out_cubic(t: float) -> float:
    """Smooth deceleration - fog clearing into focus."""
    return 1 - pow(1 - t, 3)


def compute_char_state(
    current_time: float,
    char_entry_start: float,
    char_focus_time: float,
    settings: MotionSettings
) -> CharProperties:
    """
    Compute animation properties for a character at current_time.
    
    Entry-only animation model:
    - Characters animate from blur → focus
    - No exit animation (hard cut on group change)
    """
    if current_time < char_entry_start:
        return CharProperties(visible=False)
    
    if char_entry_start <= current_time < char_focus_time:
        progress = (current_time - char_entry_start) / settings.entry_duration
        progress = min(1.0, max(0.0, progress))
        e = ease_out_cubic(progress)
        
        opacity = settings.entry_opacity_start + (1.0 - settings.entry_opacity_start) * e
        blur = settings.entry_blur_start * (1.0 - e)
        scale = settings.entry_scale + (1.0 - settings.entry_scale) * e
        y_offset = settings.y_drift * (1.0 - e)
        
        return CharProperties(
            opacity=opacity,
            blur=blur,
            scale=scale,
            y_offset=y_offset,
            visible=True
        )
    
    # Fully visible (hold state)
    return CharProperties(
        opacity=1.0,
        blur=0.0,
        scale=1.0,
        y_offset=0.0,
        visible=True
    )


@dataclass
class Word:
    """A single word with timing information."""
    id: str
    text: str
    start: float
    end: float


@dataclass
class DisplayGroup:
    """A group of words displayed together."""
    word_ids: List[str]
    start_time: float
    end_time: float


def compute_display_groups(
    words: List[Word],
    settings: MotionSettings
) -> List[DisplayGroup]:
    """
    Compute display groups based on word timing and max words setting.
    
    Words accumulate 1→2→3 (or max_words), then hard-cut to new group.
    """
    if not words:
        return []
    
    groups = []
    current_word_ids = []
    current_group_start = None
    
    for word in words:
        word_entry_start = word.start - settings.entry_duration
        
        if len(current_word_ids) >= settings.max_words_on_screen:
            # Close current group and start new one
            if current_word_ids:
                groups.append(DisplayGroup(
                    word_ids=current_word_ids.copy(),
                    start_time=current_group_start,
                    end_time=word_entry_start
                ))
            current_word_ids = [word.id]
            current_group_start = word_entry_start
        else:
            if not current_word_ids:
                current_group_start = word_entry_start
            current_word_ids.append(word.id)
    
    # Close final group
    if current_word_ids:
        last_word = words[-1]
        groups.append(DisplayGroup(
            word_ids=current_word_ids,
            start_time=current_group_start,
            end_time=last_word.end + 1.0
        ))
    
    return groups


@dataclass(frozen=True)
class Character:
    """A single character with animation timing."""
    char: str
    word_id: str
    char_index: int
    entry_start: float
    focus_time: float


def decompose_group_to_characters(
    words: List[Word],
    group: DisplayGroup,
    settings: MotionSettings
) -> List[Character]:
    """
    Convert a display group into individual characters with timing.
    """
    word_lookup = {w.id: w for w in words}
    characters = []
    
    for word_id in group.word_ids:
        word = word_lookup.get(word_id)
        if not word:
            continue
        
        for char_idx, char in enumerate(word.text):
            stagger_offset = char_idx * settings.char_stagger
            entry_start = word.start - settings.entry_duration + stagger_offset
            focus_time = word.start + stagger_offset
            
            characters.append(Character(
                char=char,
                word_id=word_id,
                char_index=char_idx,
                entry_start=entry_start,
                focus_time=focus_time
            ))
    
    return characters
