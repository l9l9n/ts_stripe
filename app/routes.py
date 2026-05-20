import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.models import Payment
from app.schemas import CheckoutRequest, CheckoutResponse, PaymentResponse, WebhookResponse

stripe.api_key = settings.stripe_secret_key

router = APIRouter()


@router.post("/checkout/", response_model=CheckoutResponse)
async def create_checkout_session(body: CheckoutRequest):
    try:
        session = stripe.checkout.Session.create(
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": "Test Product"},
                    "unit_amount": body.price * 100,  # Stripe принимает центы
                },
                "quantity": 1,
            }],
            metadata={
                "user_id": "42",
                "email": body.email,
                "request_id": "req_test_001",
            },
            mode="payment",
            success_url=settings.base_url + "/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=settings.base_url + "/cancel",
            customer_email=body.email,
        )
        return CheckoutResponse(checkout_url=session.url)
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/webhook/", response_model=WebhookResponse)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Invalid signature"},
        )

    if event["type"] == "checkout.session.completed":
        stripe_session = event["data"]["object"]
        await Payment.create_from_stripe(db, stripe_session)

    return WebhookResponse(status="ok")


@router.get("/success", response_model=PaymentResponse)
async def success(session_id: str, db: AsyncSession = Depends(get_session)):
    payment = await Payment.get_by_session_id(db, session_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return PaymentResponse(
        message="Оплата прошла успешно!",
        session_id=payment.session_id,
        email=payment.email,
        amount_usd=payment.amount / 100,
        status=payment.status,
    )


@router.get("/cancel")
async def cancel():
    return {"message": "Оплата отменена."}