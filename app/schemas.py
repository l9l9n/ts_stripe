from pydantic import BaseModel, EmailStr, Field, ConfigDict


class CheckoutRequest(BaseModel):
    email: EmailStr
    price: int = Field(..., gt=0, description="Сумма в USD (целое число, например 20 = $20.00)")


class CheckoutResponse(BaseModel):
    checkout_url: str


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    message: str
    session_id: str
    email: str | None
    amount_usd: float
    status: str


class WebhookResponse(BaseModel):
    status: str