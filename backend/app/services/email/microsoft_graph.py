import msal
import httpx
import logging
from datetime import datetime
from typing import Optional, Dict
from app.config import settings

logger = logging.getLogger(__name__)


class MicrosoftGraphService:
    AUTHORITY = f"https://login.microsoftonline.com/{settings.MICROSOFT_TENANT_ID}"
    GRAPH_BASE = "https://graph.microsoft.com/v1.0"
    SCOPES = settings.MICROSOFT_SCOPES

    def __init__(self):
        self.app = msal.ConfidentialClientApplication(
            client_id=settings.MICROSOFT_CLIENT_ID,
            client_credential=settings.MICROSOFT_CLIENT_SECRET,
            authority=self.AUTHORITY,
        )

    def get_auth_url(self, state: str = "") -> str:
        return self.app.get_authorization_request_url(
            scopes=self.SCOPES,
            redirect_uri=settings.MICROSOFT_REDIRECT_URI,
            state=state,
        )

    def exchange_code(self, code: str) -> Dict:
        result = self.app.acquire_token_by_authorization_code(
            code=code,
            scopes=self.SCOPES,
            redirect_uri=settings.MICROSOFT_REDIRECT_URI,
        )
        if "error" in result:
            raise Exception(
                f"Token exchange failed: {result.get('error_description', result['error'])}"
            )
        return result

    def refresh_access_token(self, refresh_token: str) -> Dict:
        result = self.app.acquire_token_by_refresh_token(
            refresh_token=refresh_token,
            scopes=self.SCOPES,
        )
        if "error" in result:
            raise Exception(
                f"Token refresh failed: {result.get('error_description', result['error'])}"
            )
        return result

    async def get_user_profile(self, access_token: str) -> Dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.GRAPH_BASE}/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            return response.json()

    async def get_messages(
        self,
        access_token: str,
        since_date: datetime,
        next_link: Optional[str] = None,
        top: int = 50,
    ) -> Dict:
        if next_link:
            url = next_link
        else:
            date_filter = since_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            url = (
                f"{self.GRAPH_BASE}/me/messages"
                f"?$filter=receivedDateTime ge {date_filter}"
                f"&$orderby=receivedDateTime desc"
                f"&$top={top}"
                f"&$select=id,subject,from,toRecipients,receivedDateTime,body,bodyPreview"
            )

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            data = response.json()
            return {
                "value": data.get("value", []),
                "next_link": data.get("@odata.nextLink"),
            }


_graph_service = None


def get_graph_service() -> MicrosoftGraphService:
    global _graph_service
    if _graph_service is None:
        _graph_service = MicrosoftGraphService()
    return _graph_service
