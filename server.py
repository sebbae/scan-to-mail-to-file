import asyncio
import logging
import os
import re
from datetime import datetime
from email import message_from_bytes
from email.header import decode_header

from aiosmtpd.controller import Controller

OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/output")
MAX_SIZE = 50 * 1024 * 1024  # 50 MB

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)


def decode_str(value):
    if value is None:
        return ""
    parts = decode_header(value)
    return "".join(
        part.decode(enc or "utf-8") if isinstance(part, bytes) else part
        for part, enc in parts
    )


def safe_name(name, max_len=200):
    name = re.sub(r"[^\w\.\-@]", "_", name)
    return name[:max_len] or "unnamed"


def recipient_dir(to_header):
    addr = decode_str(to_header)
    # extract the address from "Name <addr>" or bare "addr"
    m = re.search(r"<([^>]+)>", addr)
    addr = m.group(1) if m else addr.strip()
    return safe_name(addr)


class AttachmentHandler:
    async def handle_DATA(self, server, session, envelope):
        msg = message_from_bytes(envelope.content)
        to_dir = recipient_dir(msg.get("To", "unknown"))
        out_dir = os.path.join(OUTPUT_DIR, to_dir)
        os.makedirs(out_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        saved = 0

        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            disposition = part.get("Content-Disposition", "")
            if "attachment" not in disposition and "inline" not in disposition:
                continue

            raw_filename = part.get_filename() or f"attachment.bin"
            filename = f"{timestamp}_{safe_name(decode_str(raw_filename))}"
            path = os.path.join(out_dir, filename)

            payload = part.get_payload(decode=True)
            if payload is None:
                continue

            with open(path, "wb") as f:
                f.write(payload)

            log.info("saved %s", path)
            saved += 1

        if saved == 0:
            log.info("message from %s had no attachments", envelope.mail_from)

        return "250 OK"


async def main():
    handler = AttachmentHandler()
    controller = Controller(
        handler,
        hostname="0.0.0.0",
        port=25,
        data_size_limit=MAX_SIZE,
    )
    controller.start()
    log.info("SMTP server listening on port 25, writing to %s", OUTPUT_DIR)
    try:
        await asyncio.Event().wait()
    finally:
        controller.stop()


if __name__ == "__main__":
    asyncio.run(main())
