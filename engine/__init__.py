"""
Captioneer Engine - Headless Kinetic Typography Renderer

This module provides the deterministic rendering engine that:
- Takes a project state (JSON) as input
- Renders frames at any given timestamp
- Is completely headless (no UI dependencies)
- Is used by both the CLI and Studio API
"""

from .renderer import FrameRenderer, ProjectState
from .motion import MotionSettings, CharProperties, Word
from .layout import LayoutEngine, StyleSettings, CanvasSettings
from .encoder import VideoEncoder

__all__ = [
    'FrameRenderer',
    'ProjectState',
    'MotionSettings',
    'CharProperties',
    'Word',
    'LayoutEngine',
    'StyleSettings',
    'CanvasSettings',
    'VideoEncoder',
]
