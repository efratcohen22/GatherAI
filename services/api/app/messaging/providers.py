"""Messaging abstraction. Only the simulator exists today; nothing leaves this application."""
from dataclasses import dataclass
from typing import Protocol


@dataclass
class DeliveryResult:
    status: str
    provider_message_id: str | None = None


class MessagingProvider(Protocol):
    def send_message(self, to: str | None, content: str) -> DeliveryResult: ...
    def receive_message(self, payload: dict) -> dict: ...
    def get_delivery_status(self, provider_message_id: str) -> str: ...


class SimulatorMessagingProvider:
    def send_message(self, to: str | None, content: str) -> DeliveryResult:
        return DeliveryResult(status="simulated_delivered")

    def receive_message(self, payload: dict) -> dict:
        return payload

    def get_delivery_status(self, provider_message_id: str) -> str:
        return "simulated_delivered"


class WhatsAppBusinessProvider:
    """Placeholder for the official Meta WhatsApp Business Platform (phase 3, needs authorization)."""

    def send_message(self, to: str | None, content: str) -> DeliveryResult:
        raise NotImplementedError("WhatsApp Business is not connected")

    def receive_message(self, payload: dict) -> dict:
        raise NotImplementedError("WhatsApp Business is not connected")

    def get_delivery_status(self, provider_message_id: str) -> str:
        raise NotImplementedError("WhatsApp Business is not connected")


def get_provider() -> MessagingProvider:
    return SimulatorMessagingProvider()
