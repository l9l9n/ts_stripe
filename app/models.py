from dataclasses import field
from typing import Optional

from sqlalchemy import String, UniqueConstraint, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import MappedAsDataclass, Mapped, mapped_column

from app.database import Base


class Payment(MappedAsDataclass, Base):
    __tablename__ = "payments"
    __table_args__ = (UniqueConstraint("session_id", name="uq_payments_session_id"),)


    session_id: Mapped[str] = mapped_column(String(255), index=True)
    amount: Mapped[int] = mapped_column()
    currency: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(50))

 
    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default=None)
    user_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, default=None)
    request_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, default=None)

    @staticmethod
    async def get_by_session_id(session: AsyncSession, session_id: str) -> Optional["Payment"]:
        result = await session.execute(
            select(Payment).where(Payment.session_id == session_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_from_stripe(session: AsyncSession, stripe_session) -> Optional["Payment"]:
        existing = await Payment.get_by_session_id(session, stripe_session["id"])
        if existing:
            return existing

        metadata = stripe_session["metadata"] if "metadata" in stripe_session else {}

        payment = Payment(
            session_id=stripe_session["id"],
            email=stripe_session["customer_email"] if "customer_email" in stripe_session else None,
            amount=stripe_session["amount_total"],
            currency=stripe_session["currency"],
            status=stripe_session["payment_status"],
            user_id=metadata["user_id"] if "user_id" in metadata else None,
            request_id=metadata["request_id"] if "request_id" in metadata else None,
        )
        session.add(payment)
        await session.commit()
        await session.refresh(payment)
        return payment