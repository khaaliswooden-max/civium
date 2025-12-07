"""Pro-Ticket API routes."""

from services.ticket.routes.tickets import router as tickets_router
from services.ticket.routes.triage import router as triage_router
from services.ticket.routes.sla import router as sla_router

__all__ = [
    "tickets_router",
    "triage_router",
    "sla_router",
]

