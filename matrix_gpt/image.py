import asyncio
import base64
import io

from PIL import Image


async def process_image(source_bytes: bytes, resize_px: int):
    loop = asyncio.get_event_loop()
    image = await loop.run_in_executor(None, Image.open, io.BytesIO(source_bytes))
    width, height = image.size

    if min(width, height) > resize_px:
        if width < height:
            new_width = resize_px
            new_height = int((height / width) * new_width)
        else:
            new_height = resize_px
            new_width = int((width / height) * new_height)
        image = await loop.run_in_executor(None, image.resize, (new_width, new_height))

    byte_arr = io.BytesIO()
    await loop.run_in_executor(None, image.save, byte_arr, 'PNG')
    image_bytes = byte_arr.getvalue()
    return base64.b64encode(image_bytes).decode('utf-8')
