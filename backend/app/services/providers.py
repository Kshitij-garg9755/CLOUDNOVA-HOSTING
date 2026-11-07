import hashlib
import logging
from decimal import Decimal, InvalidOperation
from urllib.parse import quote, urlparse

import httpx

from app.core.config import settings

logger=logging.getLogger(__name__)

class DemoDomainProvider:
    """Deterministic demo lookup. Never represents registrar availability."""
    def search(self, domain:str)->dict:
        name=domain.lower().strip().lstrip("@");available=int(hashlib.sha256(name.encode()).hexdigest(),16)%3!=0
        return {"domain":name,"available":available,"price":899 if name.endswith(".com") else 599,"mode":"DEMO","message":"Mock result only; verify with a registrar."}
class DemoHostingProvider:
    mode="DEMO"
    def provision(self,account:str,plan:str)->dict:return {"status":"demo_pending","provider_ref":None,"mode":self.mode}
    def suspend(self,ref:str)->dict:return {"status":"suspended","mode":self.mode}
    def activate(self,ref:str)->dict:return {"status":"active","mode":self.mode}
    def cancel(self,ref:str)->dict:return {"status":"cancelled","mode":self.mode}
    def status(self,ref:str)->dict:return {"status":"demo_pending","mode":self.mode,"resources":{}}
class PaymentService:
    def create_upi_gateway_order(self,amount:int,receipt:str,customer:dict|None=None)->dict:
        if not settings.upi_gateway_configured:
            raise ValueError("UPI Gateway credentials are not configured")
        return self._create_upi_gateway_order(amount,receipt,customer or {})

    def create_order(self,amount:int,receipt:str,customer:dict|None=None)->dict:
        if settings.upi_gateway_configured:
            return self._create_upi_gateway_order(amount,receipt,customer or {})
        if settings.razorpay_key_id and settings.razorpay_key_secret:
            import razorpay
            client=razorpay.Client(auth=(settings.razorpay_key_id,settings.razorpay_key_secret))
            return {**client.order.create({"amount":amount,"currency":"INR","receipt":receipt}),"mode":"razorpay_test"}
        if not settings.payment_demo_mode: raise ValueError("Razorpay credentials are not configured")
        return {"id":"demo_"+receipt,"amount":amount,"currency":"INR","status":"created","mode":"DEMO"}

    def _headers(self)->dict[str,str]:
        return {"X-Api-Key":settings.upi_gateway_api_key,"X-Api-Secret":settings.upi_gateway_api_secret}

    def _create_upi_gateway_order(self,amount:int,receipt:str,customer:dict)->dict:
        if settings.environment.lower()=="production" and not settings.upi_gateway_url.startswith("https://"):
            raise ValueError("The UPI Gateway must use an HTTPS URL in production")

        payload={
            "amount":str((Decimal(amount)/100).quantize(Decimal("0.01"))),
            "client_order_id":receipt,
            "redirect_url":settings.upi_gateway_return_url,
            "customer_name":customer.get("name"),
            "customer_email":customer.get("email"),
            "customer_mobile":customer.get("phone"),
            "note":"CloudNova hosting plan",
        }
        try:
            response=httpx.post(
                settings.upi_gateway_url.rstrip("/")+"/api/v1/orders",
                headers=self._headers(),json=payload,timeout=20,
            )
            response.raise_for_status()
            body=response.json()
            data=body.get("data") if body.get("success") is True else None
            payment_url=data.get("payment_url") if isinstance(data,dict) else None
            remote_id=data.get("order_id") if isinstance(data,dict) else None
            if not payment_url or not remote_id:
                raise ValueError("The UPI Gateway returned an incomplete payment order")
            configured_url=urlparse(settings.upi_gateway_url)
            checkout_url=urlparse(payment_url)
            if checkout_url.netloc!=configured_url.netloc or checkout_url.scheme not in {"http","https"}:
                raise ValueError("The UPI Gateway returned an unsafe checkout URL")
            if settings.environment.lower()=="production" and checkout_url.scheme!="https":
                raise ValueError("The UPI Gateway returned a non-HTTPS checkout URL")
            return {
                "id":remote_id,
                "amount":amount,
                "currency":"INR",
                "status":data.get("status","pending"),
                "payment_url":payment_url,
                "mode":"upi_gateway",
            }
        except httpx.HTTPStatusError as exc:
            logger.warning("UPI gateway create-order request failed with HTTP %s",exc.response.status_code)
            if exc.response.status_code in (401,403):
                raise ValueError("UPI Gateway credentials are invalid or the merchant account is inactive") from exc
            raise ValueError("The UPI Gateway could not create a payment order") from exc
        except (httpx.RequestError,ValueError) as exc:
            if isinstance(exc,ValueError): raise
            logger.warning("UPI gateway create-order request failed (%s)",type(exc).__name__)
            raise ValueError("The UPI Gateway is unavailable; no payment order was created") from exc
        except (KeyError,TypeError):
            raise ValueError("The UPI Gateway returned an invalid response")

    def get_upi_gateway_order(self,remote_id:str)->dict:
        try:
            response=httpx.get(
                settings.upi_gateway_url.rstrip("/")+"/api/v1/orders/"+quote(remote_id,safe=""),
                headers=self._headers(),timeout=15,
            )
            response.raise_for_status()
            body=response.json()
            data=body.get("data") if body.get("success") is True else None
            if not isinstance(data,dict): raise ValueError("The UPI Gateway returned an invalid order")
            payment_url=data.get("payment_url")
            if payment_url:
                configured_url=urlparse(settings.upi_gateway_url)
                checkout_url=urlparse(payment_url)
                if checkout_url.netloc!=configured_url.netloc or checkout_url.scheme not in {"http","https"}:
                    raise ValueError("The UPI Gateway returned an unsafe checkout URL")
                if settings.environment.lower()=="production" and checkout_url.scheme!="https":
                    raise ValueError("The UPI Gateway returned a non-HTTPS checkout URL")
            return data
        except httpx.HTTPStatusError as exc:
            logger.warning("UPI gateway status request failed with HTTP %s",exc.response.status_code)
            if exc.response.status_code in (401,403):
                raise ValueError("UPI Gateway credentials are invalid or the merchant account is inactive") from exc
            raise ValueError("Could not verify payment status with the UPI Gateway") from exc
        except httpx.RequestError as exc:
            logger.warning("UPI gateway status request failed (%s)",type(exc).__name__)
            raise ValueError("The UPI Gateway is unavailable; payment status was not changed") from exc

    @staticmethod
    def is_matching_paid_order(order,remote_order:dict)->bool:
        if (remote_order.get("client_order_id")!=order.id
                or remote_order.get("status")!="paid"
                or remote_order.get("currency")!="INR"):
            return False
        try:
            paid_amount=Decimal(str(remote_order["amount"]))
            expected_amount=Decimal(str(order.amount))
            if not paid_amount.is_finite() or not expected_amount.is_finite():
                return False
            paid_amount=paid_amount.quantize(Decimal("0.01"))
            expected_amount=expected_amount.quantize(Decimal("0.01"))
        except (KeyError,InvalidOperation,TypeError,ValueError):
            return False
        return paid_amount==expected_amount
