"""meet-mom: client-meeting minutes from a live Google Meet call.

Reuses the verified two-channel audio routing from ``interview_eval`` (host =
channel 0, client side = channel 1, via a BlackHole Aggregate Device) to capture
both sides of a call, build a speaker-labeled transcript, and generate a polished
Minutes of Meeting (GPT-4o) that can be saved, copied, and drafted as an email.

See ``docs/MEETING_MOM_PLAN.md`` for the design.
"""

__all__ = ["__version__"]
__version__ = "0.1.0"
