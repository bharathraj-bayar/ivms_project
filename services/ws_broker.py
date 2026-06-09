import asyncio
import json
import os
import logging
from datetime import datetime, timezone
import redis.asyncio as aioredis

class WebSocketBroker:
    """Redis-backed pub/sub broker to stream vehicle-specific channels and batch messages."""
    def __init__(self):
        self.redis_url = os.getenv('REDIS_URL', f"redis://{os.getenv('REDIS_HOST','localhost')}:{os.getenv('REDIS_PORT',6379)}/0")
        self.client = None
        self.logger = logging.getLogger(__name__)
        self.running = False

    async def connect(self):
        if not self.client:
            self.client = aioredis.from_url(self.redis_url, decode_responses=True)

    async def listen_and_publish(self, callback, batch_ms: int = 200, max_batch: int = 100):
        """
        Subscribe to patterns and call `callback(messages)` periodically with a batch list.
        `callback` should be an async callable that takes list[str] messages.
        """
        await self.connect()
        pubsub = self.client.pubsub(ignore_subscribe_messages=True)
        # subscribe to generic and per-vehicle channels
        await pubsub.psubscribe('live_updates*')
        self.running = True

        batch = []
        last_flush = asyncio.get_event_loop().time()

        try:
            while self.running:
                msg = await pubsub.get_message(timeout=0.1)
                if msg and 'data' in msg and msg['data']:
                    data = msg['data']
                    if isinstance(data, bytes):
                        try:
                            data = data.decode('utf-8')
                        except Exception:
                            data = str(data)
                    batch.append(data)

                now = asyncio.get_event_loop().time()
                if batch and (len(batch) >= max_batch or (now - last_flush) * 1000 >= batch_ms):
                    try:
                        await callback(batch)
                    except Exception as e:
                        self.logger.exception(f"ws_broker callback error: {e}")
                    batch = []
                    last_flush = now

                await asyncio.sleep(0)
        finally:
            try:
                await pubsub.close()
            except Exception:
                pass

    async def publish(self, channel: str, message: str):
        await self.connect()
        await self.client.publish(channel, message)

ws_broker = WebSocketBroker()
