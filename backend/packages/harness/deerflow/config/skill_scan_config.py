"""Configuration for skill safety scanning."""

from pydantic import BaseModel, Field


class SkillScanConfig(BaseModel):
    """Configure native analyzers and install-time skill content scanning.

    Disabling this setting skips scanner calls during archive installation.
    Other skill write paths still retain their LLM moderation scan.
    """

    enabled: bool = Field(
        default=True,
        description="Whether skill archive installation runs native and LLM security scans; native analyzers remain configurable for other skill write paths.",
    )
