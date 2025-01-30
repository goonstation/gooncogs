from redbot.core.bot import Red

class aobject(object):
    """Inheriting this class allows you to define an async __init__.

    So you can create objects by doing something like `await MyClass(params)`
    """
    async def __new__(cls, *a, **kw):
        instance = super().__new__(cls)
        await instance.__init__(*a, **kw)
        return instance

    async def __init__(self):
        pass

class ResponseStatusError(Exception):
    pass

class ResponseValidationError(Exception):
    pass

class GoonhubRequest(aobject):
    async def __init__(self, bot: Red, session):
        self.session = session
        tokens = await bot.get_shared_api_tokens('goonhub')
        self.api_url = tokens['api_url']
        self.api_key = tokens['api_key']

    def headers(self):
        return {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }
    
    async def run(self, method, path, params = {}, data = {}) -> dict:
        url = f"{self.api_url}/{path}"
        async with self.session.request(method, url, headers = self.headers(), params = params, json = data) as res:
            json = await res.json()
            if res.status >= 500:
                message = f"Error code {res.status} occured when querying the API"
                if json is not None and "message" in json: message += f": {json['message']}"
                raise ResponseStatusError(message)
            if json is None:
                raise ResponseValidationError(f"Invalid response from API")
            return json

    async def get(self, path, params = {}) -> dict:
        return await self.run('GET', path, params = params)
    
    async def post(self, path, params = {}, data = {}) -> dict:
        return await self.run('POST', path, params = params, data = data)
    
    async def put(self, path, params = {}, data = {}) -> dict:
        return await self.run('PUT', path, params = params, data = data)
    
    async def delete(self, path, params = {}) -> dict:
        return await self.run('DELETE', path, params = params)
