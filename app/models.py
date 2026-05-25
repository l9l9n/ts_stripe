from typing import Optional

import stripe as stripe_lib
from sqlalchemy import String, UniqueConstraint, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import MappedAsDataclass, Mapped, mapped_column

from app.database import Base


class Product(MappedAsDataclass, Base):
    __tablename__ = "products"

    # Обязательные поля
    name: Mapped[str] = mapped_column(String(255))
    price: Mapped[int] = mapped_column()  # в центах
    currency: Mapped[str] = mapped_column(String(10))

    # Поля с default
    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True, default=None)
    stripe_product_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default=None)
    stripe_price_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default=None)

    @staticmethod
    async def get_by_id(session: AsyncSession, product_id: int) -> Optional["Product"]:
        result = await session.execute(
            select(Product).where(Product.id == product_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_all(session: AsyncSession) -> list["Product"]:
        result = await session.execute(select(Product))
        return list(result.scalars().all())

    @staticmethod
    async def create_with_stripe(
        session: AsyncSession,
        name: str,
        price: int,
        currency: str,
        description: Optional[str] = None,
    ) -> "Product":
        """Создаёт продукт в Stripe и сохраняет в БД."""
        # 1. Создаём продукт в Stripe
        stripe_product = stripe_lib.Product.create(
            name=name,
            description=description or "",
        )
        # 2. Создаём цену в Stripe
        stripe_price = stripe_lib.Price.create(
            product=stripe_product.id,
            unit_amount=price,  # уже в центах
            currency=currency,
        )
        # 3. Сохраняем в БД
        product = Product(
            name=name,
            price=price,
            currency=currency,
            description=description,
            stripe_product_id=stripe_product.id,
            stripe_price_id=stripe_price.id,
        )
        session.add(product)
        await session.commit()
        await session.refresh(product)
        return product

    async def sync_to_stripe(self, session: AsyncSession) -> "Product":
        if not self.stripe_product_id or not self.stripe_price_id:
            raise ValueError("Продукт не привязан к Stripe")

        # Обновляем название/описание продукта
        stripe_lib.Product.modify(
            self.stripe_product_id,
            name=self.name,
            description=self.description or "",
        )
        # Цену в Stripe нельзя изменить — создаём новую и архивируем старую
        stripe_lib.Price.modify(self.stripe_price_id, active=False)
        new_price = stripe_lib.Price.create(
            product=self.stripe_product_id,
            unit_amount=self.price,
            currency=self.currency,
        )
        self.stripe_price_id = new_price.id
        await session.commit()
        await session.refresh(self)
        return self


class Payment(MappedAsDataclass, Base):
    __tablename__ = "payments"
    __table_args__ = (UniqueConstraint("session_id", name="uq_payments_session_id"),)

    # Обязательные поля
    session_id: Mapped[str] = mapped_column(String(255), index=True)
    amount: Mapped[int] = mapped_column()
    currency: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(50))

    # Поля с default
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