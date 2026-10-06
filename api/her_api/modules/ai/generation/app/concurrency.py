import asyncio


class ModelConcurrency:
    def __init__(self):
        self.slots = asyncio.Semaphore(2)
        self.chat_slots = asyncio.Semaphore(1)
