import aiohttp
from typing import Optional, AsyncGenerator
import asyncio
import json
from importlib.metadata import version

class _Recall:
    def __init__(self, client: "IGPTAsync"):
        self._client = client

    # ASK
    async def ask(self, user: Optional[str] = None, **kwargs) -> dict:
        """
        Generate response based on input and context

        The 'user' parameter is required—either include it in 'params', or set it as default on IGPTAsyncClient initialization.

        Parameters
        ----------
        user : (str)
            a unique identifier representing your end-user
        input : (str)
            the question to ask 
        stream : (bool, optional)
            if True, stream response, defaults to False
        quality : (Optional[str], optional)
            context engineering quality, defaults to None
        output_format : (Optional[str], optional)
            output format: text (default), json or {"schema":{}}
        """

        payload = {}
        payload["user"] = user or self._client.user or None
        if kwargs:
            payload.update(kwargs)
        
        url = f"{self._client.base_url}/recall/ask/"
        return self._client._stream_request(url, payload) if payload.get("stream") else await self._client._post(url, payload)
    
    # SEARCH
    async def search(self, user: Optional[str] = None, **kwargs) -> dict:
        """
        Search connected datasources

        The 'user' parameter is required—either include it in 'params', or set it as default on IGPTClient initialization.

        Parameters
        ----------
        user : (str)
            A unique identifier representing your end-user.
        query : (str)
            The search query to execute.  
        date_from : (str)
            Filter by start date.  
        date_to : (str)
            Filter by end date.
        max_results : (int)  
            Limit number for results.
        """
        
        payload = {}
        payload["user"] = user or self._client.user or None
        if kwargs:
            payload.update(kwargs)
        
        url = f"{self._client.base_url}/recall/search/"
        return await self._client._post(url, payload)

class _Datasources:
    def __init__(self, client: "IGPTAsync"):
        self._client = client

    # LIST DATASOURCES
    async def list(self, user: Optional[str] = None, **kwargs) -> dict:
        """
        List user datasources and their indexing status

        The 'user' parameter is required—either include it in 'params', or set it as default on IGPTAsyncClient initialization.

        Parameters
        ----------
        user : (str)
            A unique identifier representing your end-user.
        """
        
        payload = {}
        payload["user"] = user or self._client.user or None
        if kwargs:
            payload.update(kwargs)
        
        url = f"{self._client.base_url}/datasources/list/"
        return await self._client._post(url, payload)
    
    # DISCONNECT DATASOURCE
    async def disconnect(self, user: Optional[str] = None, **kwargs) -> dict:
        """
        Disconnect datasource and remove index data

        The 'user' parameter is required—either include it in 'params', or set it as default on IGPTAsyncClient initialization.

        Parameters
        ----------
        user : (str)
            a unique identifier representing your end-user.
        id : (str)
            datasource id to disconnect.
                
        """
        payload = {}
        payload["user"] = user or self._client.user or None
        if kwargs:
            payload.update(kwargs)
        
        url = f"{self._client.base_url}/datasources/disconnect/"
        return await self._client._post(url, payload)

class _Connectors:
    def __init__(self, client: "IGPTAsync"):
        self._client = client

    # AUTHORIZE CONNECTOR
    async def authorize(self, user: Optional[str] = None, **kwargs) -> dict:
        """
        Authorize, connect and start indexing a new datasource

        The 'user' parameter is required—either include it in 'params', or set it as default on IGPTAsyncClient initialization.

        Parameters
        ----------
        user : (str)
            a unique identifier representing your end-user.
        service : (str)
            the service provider.  
        scope : (str)
            space delimated services.  
        redirect_uri : (Optional[str], optional)
            redirect after successful authorization flow.  
        state : (Optional[str], optional)
            any value that your application uses to maintain state.
        """
        
        payload = {}
        payload["user"] = user or self._client.user or None
        if kwargs:
            payload.update(kwargs)
        
        url = f"{self._client.base_url}/connectors/authorize/"
        return await self._client._post(url, payload)

class IGPTAsync:
    """
    Async iGPT API client class.

    The user parameter is required for all API requests. You can provide a default user when initializing the client, or specify the user as part of each method call.

    Attributes:
        api_key (str): API key for authenticating requests.
        user (Optional[str]): A unique identifier representing your end-user (must be provided either at initialization or per request).
    """
    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.igpt.ai/v1", user: Optional[str] = None, max_retries: int = 3, backoff_factor: int = 2, backoff_base: int = 100): 
        self.user = user or None
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.max_retries = max(1, max_retries) if isinstance(max_retries, int) else 3
        self.backoff_factor = max(2, backoff_factor) if isinstance(backoff_factor, int) else 2
        backoff_base_ms = max(100, backoff_base) if isinstance(backoff_base, int) else 100
        self.backoff_base = backoff_base_ms / 1000.0 # 0.1 seconds
        self._version = version("igptai")
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "X-Client": f"igpt-python/{self._version}"
        }
        self.recall = _Recall(self)
        self.datasources = _Datasources(self)
        self.connectors = _Connectors(self)

    # internals
    async def _post(self, url: str, payload: dict):        
        delay = self.backoff_base
        timeout = aiohttp.ClientTimeout(
            total=None,
            connect=60,      # connect timeout (sec)
            sock_read=600,   # read timeout (sec) = 10 min
        )
        async with aiohttp.ClientSession(headers=self.headers, timeout=timeout) as session:
            for attempt in range(self.max_retries):
                try:
                    async with session.post(url, json=payload) as resp:
                        if resp.status == 200:
                            try:
                                return await resp.json()
                            except Exception:
                                return {"error": "invalid_json_response"}
                        elif resp.status == 429 or 500 <= resp.status < 600: # Server-side error (429 - Too Many Requests) - retry
                            pass
                        else:
                            return {"error": resp.reason} # Client-side error - don't retry
                except (aiohttp.ClientError, asyncio.TimeoutError):
                    pass
                
                if attempt < self.max_retries - 1: # Sleep before next retry, except after the last attempt
                    await asyncio.sleep(delay)
                    delay *= self.backoff_factor # Exponential backoff

        return {"error": "network_error"}
                    

    async def _stream_request(self, url: str, payload: dict) -> AsyncGenerator[dict, None]:
        delay = self.backoff_base
        timeout = aiohttp.ClientTimeout(
            total=None,
            connect=60,    # connect timeout (sec)
            sock_read=600, # read timeout (sec): max idle time between chunks
        )
        async with aiohttp.ClientSession(headers=self.headers, timeout=timeout) as session:
            for attempt in range(self.max_retries):
                try:
                    async with session.post(url, json=payload) as resp:
                        if resp.status == 200:
                            async for chunk in resp.content:
                                if chunk:
                                    chunk_str = chunk.decode()
                                    if chunk_str.startswith("data:"):
                                        json_str = chunk_str[len("data:"):].strip()
                                    else:
                                        json_str = chunk_str
                                        
                                    if not json_str:
                                        continue
                                    
                                    try:
                                        yield json.loads(json_str)
                                    except json.JSONDecodeError:
                                        continue
                            return
                        elif resp.status == 429 or 500 <= resp.status < 600:
                            pass
                        else:
                            yield {"error": resp.reason}
                            return
                except (aiohttp.ClientError, asyncio.TimeoutError):
                    pass

                if attempt < self.max_retries - 1:
                    await asyncio.sleep(delay)
                    delay *= self.backoff_factor
                
            yield {"error": "network_error"}