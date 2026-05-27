import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.models import Payment, Product
from app.schemas import (
    CheckoutRequest, CheckoutResponse,
    PaymentResponse, WebhookResponse,
    ProductCreate, ProductResponse, ProductUpdate,
)

stripe.api_key = settings.stripe_secret_key

router = APIRouter()


# --- Products ---

@router.post("/products/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(body: ProductCreate, db: AsyncSession = Depends(get_session)):
    """Создаёт продукт в нашей БД и синхронизирует со Stripe."""
    try:
        product = await Product.create_with_stripe(
            session=db,
            name=body.name,
            price=body.price_in_cents,
            currency=body.currency,
            description=body.description,
        )
    except stripe.StripeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return ProductResponse.from_product(product)


@router.get("/products/", response_model=list[ProductResponse])
async def list_products(db: AsyncSession = Depends(get_session)):
    """Список всех продуктов из БД."""
    products = await Product.get_all(db)
    return [ProductResponse.from_product(p) for p in products]


@router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int, db: AsyncSession = Depends(get_session)):
    product = await Product.get_by_id(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductResponse.from_product(product)


@router.patch("/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    body: ProductUpdate,
    db: AsyncSession = Depends(get_session),
):
    """Обновляет продукт в БД и синхронизирует со Stripe."""
    product = await Product.get_by_id(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    if body.name is not None:
        product.name = body.name
    if body.price is not None:
        product.price = body.price_in_cents
    if body.description is not None:
        product.description = body.description

    try:
        await product.sync_to_stripe(db)
    except stripe.StripeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return ProductResponse.from_product(product)


# --- Sync from Stripe ---

@router.post("/products/sync-from-stripe/")
async def sync_products_from_stripe(db: AsyncSession = Depends(get_session)):
    """
    Тянет все активные продукты из Stripe и синхронизирует с БД.
    Новые → создаёт, существующие → обновляет, без цены → пропускает.
    """
    try:
        result = await Product.sync_from_stripe(db)
    except stripe.StripeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return result


# --- Checkout ---

@router.post("/checkout/", response_model=CheckoutResponse)
async def create_checkout_session(
    body: CheckoutRequest,
    db: AsyncSession = Depends(get_session),
):
    """Создаёт Stripe Checkout сессию для конкретного продукта."""
    product = await Product.get_by_id(db, body.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if not product.stripe_price_id:
        raise HTTPException(status_code=400, detail="Product not synced with Stripe")

    try:
        session = stripe.checkout.Session.create(
            line_items=[{
                "price": product.stripe_price_id,
                "quantity": 1,
            }],
            metadata={
                "user_id": "42",
                "product_id": str(product.id),
            },
            mode="payment",
            success_url=settings.base_url + "/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=settings.base_url + "/cancel",
            customer_email=body.email,
        )
    except stripe.StripeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return CheckoutResponse(checkout_url=session.url)


# --- Webhook ---

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


# --- Success / Cancel ---

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