import requests
from typing import Optional, Generator
import time
import json
from importlib.metadata import version

class _Recall:
    def __init__(self, client: "IGPT"):
        self._client = client

    # ASK
    def ask(self, user: Optional[str] = None, **kwargs) -> dict:
        """
        Generate response based on input and context

        The 'user' parameter is required—either include it in 'params', or set it as default on IGPTClient initialization.

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
        return self._client._stream_request(url, payload) if payload.get("stream") else self._client._post(url, payload)
    
    # SEARCH
    def search(self, user: Optional[str] = None, **kwargs) -> dict:
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
        return self._client._post(url, payload)

class _Datasources:
    def __init__(self, client: "IGPT"):
        self._client = client

    # LIST DATASOURCES
    def list(self, user: Optional[str] = None, **kwargs) -> dict:
        """
        List user datasources and their indexing status

        The 'user' parameter is required—either include it in 'params', or set it as default on IGPTClient initialization.

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
        return self._client._post(url, payload)
    
    # DISCONNECT DATASOURCE
    def disconnect(self, user: Optional[str] = None, **kwargs) -> dict:
        """
        Disconnect datasource and remove index data

        The 'user' parameter is required—either include it in 'params', or set it as default on IGPTClient initialization.

        Parameters
        ----------
        user : (str)
            A unique identifier representing your end-user.
        id : (str)
            datasource id to disconnect.
                
        """
        
        payload = {}
        payload["user"] = user or self._client.user or None
        if kwargs:
            payload.update(kwargs)
        
        url = f"{self._client.base_url}/datasources/disconnect/"
        return self._client._post(url, payload)

class _Connectors:
    def __init__(self, client: "IGPT"):
        self._client = client
    
    # AUTHORIZE CONNECTOR
    def authorize(self, user: Optional[str] = None, **kwargs) -> dict:
        """
        Authorize, connect and start indexing a new datasource

        The 'user' parameter is required—either include it in 'params', or set it as default on IGPTClient initialization.

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
        return self._client._post(url, payload)

class IGPT:
    """
    iGPT API client class.

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
    def _post(self, url: str, payload: dict):
        delay = self.backoff_base
        for attempt in range(self.max_retries):
            try:
                resp = requests.post(url, json=payload, headers=self.headers, timeout=(60, 600)) # connect_timeout 60 seconds, read_timeout 10 minutes
                if resp.status_code == 200:
                    try:
                        return resp.json()
                    except Exception:
                        return {"error": "invalid_json_response"}
                elif resp.status_code == 429 or 500 <= resp.status_code < 600: # Server-side error (429 - Too Many Requests) - retry
                    pass
                else:
                    return {"error": resp.reason} # Client-side error - don't retry
            except requests.exceptions.RequestException: # Network error or timeout - retry
                pass

            if attempt < self.max_retries - 1: # Sleep before next retry, except after the last attempt
                time.sleep(delay)
                delay *= self.backoff_factor  # Exponential backoff
        
        return {"error": "network_error"}
    

    def _stream_request(self, url: str, payload: dict) -> Generator[dict, None, None]:
        delay = self.backoff_base
        for attempt in range(self.max_retries):
            try:
                with requests.post(url, json=payload, stream=True, headers=self.headers, timeout=(60, 600)) as resp:
                    if resp.status_code == 200:
                        for chunk in resp.iter_lines():
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
                    elif resp.status_code == 429 or 500 <= resp.status_code < 600:
                        pass
                    else:
                        yield {"error": resp.reason}
                        return
            except requests.exceptions.RequestException:
                pass

            if attempt < self.max_retries - 1:
                time.sleep(delay)
                delay *= self.backoff_factor
            else:  
                yield {"error": "network_error"}
