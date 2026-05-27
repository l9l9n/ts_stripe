from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict


# --- Product ---

class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    price: float = Field(..., gt=0, description="Цена в долларах (например 20.00 = $20.00)")
    currency: str = Field(default="usd", max_length=10)
    description: Optional[str] = Field(default=None, max_length=1000)

    @property
    def price_in_cents(self) -> int:
        return round(self.price * 100)


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    price_usd: float
    currency: str
    description: Optional[str]
    stripe_product_id: Optional[str]
    stripe_price_id: Optional[str]

    @classmethod
    def from_product(cls, product) -> "ProductResponse":
        return cls(
            id=product.id,
            name=product.name,
            price_usd=product.price / 100,
            currency=product.currency,
            description=product.description,
            stripe_product_id=product.stripe_product_id,
            stripe_price_id=product.stripe_price_id,
        )


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    price: Optional[float] = Field(default=None, gt=0, description="Цена в долларах")
    description: Optional[str] = Field(default=None, max_length=1000)

    @property
    def price_in_cents(self) -> Optional[int]:
        return round(self.price * 100) if self.price is not None else None


# --- Checkout ---

class CartItem(BaseModel):
    product_id: int = Field(..., description="ID продукта из нашей БД")
    quantity: int = Field(default=1, ge=1, le=99, description="Количество")


class CheckoutRequest(BaseModel):
    email: EmailStr
    items: list[CartItem] = Field(..., min_length=1, description="Список продуктов")


class CheckoutResponse(BaseModel):
    checkout_url: str


# --- Payment ---

class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    message: str
    session_id: str
    email: Optional[str]
    amount_usd: float
    status: str


class WebhookResponse(BaseModel):
    status: str