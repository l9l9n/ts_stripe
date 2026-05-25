from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict


# --- Product ---

class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    price: int = Field(..., gt=0, description="Цена в центах (например 2000 = $20.00)")
    currency: str = Field(default="usd", max_length=10)
    description: Optional[str] = Field(default=None, max_length=1000)


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    price: int
    currency: str
    description: Optional[str]
    stripe_product_id: Optional[str]
    stripe_price_id: Optional[str]


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    price: Optional[int] = Field(default=None, gt=0)
    description: Optional[str] = Field(default=None, max_length=1000)


# --- Checkout ---

class CheckoutRequest(BaseModel):
    email: EmailStr
    product_id: int = Field(..., description="ID продукта из нашей БД")


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