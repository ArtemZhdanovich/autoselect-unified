"""Контракты платформы: DTO, `BackendPort` и реестр Telegram-контракта.

Здесь нет ни aiogram, ни FastAPI, ни SQLAlchemy — только pydantic и stdlib.
Это позволяет переиспользовать пакет и в bot-service, и в backend-service,
и в контрактных тестах.
"""

from shared.contracts.analysis import AnalysisOut, AnalysisUnavailable, BotAnalysisRequest, QuotaExceeded
from shared.contracts.backend_port import BackendPort
from shared.contracts.criteria import SearchCriteria
from shared.contracts.delivery import CompareIn, CompareOut, DeliveryIn, DeliveryOut
from shared.contracts.dialog import (
    DialogFinalizeIn,
    DialogFinalizeOut,
    DialogMessageIn,
    DialogReplyResponse,
    DialogResetOut,
    DialogRestoreOut,
    DialogState,
    DialogUserIn,
    Message,
)
from shared.contracts.listing import (
    FetchResult,
    ListingListOut,
    ListingOut,
    PricePointOut,
    UnifiedListing,
)
from shared.contracts.notifications import NotifySettingsIn, NotifySettingsOut
from shared.contracts.payments import (
    PaymentPrepareIn,
    PaymentPrepareOut,
    PaymentSuccessIn,
    PaymentSuccessOut,
    StarsInvoiceOut,
    StarsInvoiceRequest,
    SubscriptionOut,
    UserSubscriptionOut,
)
from shared.contracts.users import (
    LoginLinkConfirmIn,
    LoginLinkConfirmOut,
    UserOut,
    UserUpsert,
)

__all__ = [
    "AnalysisOut",
    "AnalysisUnavailable",
    "BackendPort",
    "BotAnalysisRequest",
    "CompareIn",
    "CompareOut",
    "DeliveryIn",
    "DeliveryOut",
    "DialogFinalizeIn",
    "DialogFinalizeOut",
    "DialogMessageIn",
    "DialogReplyResponse",
    "DialogResetOut",
    "DialogRestoreOut",
    "DialogState",
    "DialogUserIn",
    "FetchResult",
    "ListingListOut",
    "ListingOut",
    "LoginLinkConfirmIn",
    "LoginLinkConfirmOut",
    "Message",
    "NotifySettingsIn",
    "NotifySettingsOut",
    "PaymentPrepareIn",
    "PaymentPrepareOut",
    "PaymentSuccessIn",
    "PaymentSuccessOut",
    "PricePointOut",
    "QuotaExceeded",
    "SearchCriteria",
    "StarsInvoiceOut",
    "StarsInvoiceRequest",
    "SubscriptionOut",
    "UnifiedListing",
    "UserOut",
    "UserUpsert",
    "UserSubscriptionOut",
]
