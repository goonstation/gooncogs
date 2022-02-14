import asyncio
import urllib
from collections import OrderedDict
import struct
import discord
from redbot.core import commands, Config, checks
import discord.errors
from redbot.core.bot import Red
from typing import *
import re
import time
from redbot.core.utils.chat_formatting import pagify, box


class WorldTopic(commands.Cog):
    RESPONSE_HEADER_LENGTH = 5
    MAGIC_STRING = 0x06
    MAGIC_STRING = 0x06
    MAGIC_FLOAT = 0x2A
    MAGIC_NULL = 0x00
    MAX_RECEIVE_TRIES = 10

    def __init__(self, bot: Red):
        self.bot = bot

    async def send(self, addr_port: Tuple[str, int], msg: str, timeout: int = 5) -> str:
        future = self._send(addr_port, msg)
        return await asyncio.wait_for(future, timeout=timeout)

    async def _send(self, addr_port: Tuple[str, int], msg: str) -> str:
        addr, port = addr_port

        packet = bytearray(b"\x00" * 8)
        if not msg or msg[0] != "?":
            packet += b"?"
        packet += msg.encode("utf8")
        packet += b"\x00"

        packet[1] = 0x83
        length = len(packet) - 4
        length_bytes = length.to_bytes(length=2, byteorder="big")
        packet[2] = int(length_bytes[0])
        packet[3] = int(length_bytes[1])

        reader, writer = await asyncio.open_connection(addr, port)

        writer.write(bytes(packet))
        await writer.drain()

        response = b""
        target_length = 0
        failures_left = self.MAX_RECEIVE_TRIES
        while len(response) < 4 or len(response) < target_length:
            new_bytes = await reader.read(0xFFFF)
            if not new_bytes:
                failures_left -= 1
                if failures_left < 0:
                    raise TimeoutError("Maximum receive tries exceeded.")
            response += new_bytes
            if not target_length and len(response) >= 4:
                target_length = int.from_bytes(response[2:4], byteorder="big") + 4

        writer.close()
        await writer.wait_closed()

        response_type_magic = response[4]

        header_length = self.RESPONSE_HEADER_LENGTH
        if response_type_magic == 0x04:  # no idea
            response_type_magic = self.MAGIC_STRING
            header_length = 17

        if response_type_magic == self.MAGIC_STRING:
            return response[header_length:].strip(b"\x00").decode("utf8")
        elif response_type_magic == self.MAGIC_FLOAT:
            return struct.unpack("f", response[header_length:])[0]
        elif response_type_magic == self.MAGIC_NULL:
            return None
        else:
            raise ValueError(
                f"Unknown response type {hex(response_type_magic)}. Full hex dump: '{response.hex()}'."
            )

    def params_to_dict(self, params: str):
        result = OrderedDict()
        for pair in params.split("&"):
            key, *rest = pair.split("=")
            value = urllib.parse.unquote_plus(rest[0]) if rest else None
            result[key] = value
        return result

    def iterable_to_params(self, iterable):
        if (
            isinstance(iterable, str)
            or isinstance(iterable, int)
            or isinstance(iterable, float)
        ):
            return iterable
        result_parts = []
        for key in iterable:
            value = None
            if not isinstance(key, int):
                try:
                    value = iterable[key]
                except (KeyError, IndexError, TypeError):
                    pass
            part = urllib.parse.quote_plus(str(key))
            if value is not None:
                part += "=" + urllib.parse.quote_plus(str(value))
            result_parts.append(part)
        return "&".join(result_parts)

    @commands.command()
    @checks.is_owner()
    async def test_world_topic(
        self, ctx: commands.Context, addr_port: str, message: str
    ):
        addr, port = re.match(r"(.*):([0-9]+)", addr_port).groups()
        port = int(port)
        start_time = time.time()
        try:
            response = await self.send((addr, port), message)
        except (asyncio.exceptions.TimeoutError, TimeoutError) as e:
            await ctx.send("Request timed out.")
            return
        except ConnectionRefusedError:
            await ctx.send("Connection refused.")
            return
        elapsed = time.time() - start_time
        response_message = []
        if isinstance(response, str):
            dict_response = self.params_to_dict(response)
            if len(dict_response) > 1:
                response_message.append("")
            if len(dict_response) > 1 or next(iter(dict_response.values())) is not None:
                for k, v in dict_response.items():
                    response_message.append(f"{k}: {v}")
            else:
                response_message = [response]
        else:
            response_message = [str(response)]
        response_message = "\n".join(response_message)
        response_message = f"Time: {elapsed * 1000:.2f}ms\nResponse: {response_message}"
        for page in pagify(response_message):
            await ctx.send(box(page))
