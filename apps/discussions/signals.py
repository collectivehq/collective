from __future__ import annotations

from django.dispatch import Signal

discussion_items_soft_deleted = Signal()
discussion_posted = Signal()
discussion_status_changed = Signal()
