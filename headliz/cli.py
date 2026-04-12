import asyncio
import typer
from typing import List, Optional
from rich.console import Console
from rich.logging import RichHandler
import logging

from headliz.logger import setup_logger
from headliz.civitai.service import upload_to_civitai
from headliz.civitai.models import UploadToCivitaiRequest
from headliz.civitai.browser import BrowserManager

from headliz.pinterest.service import upload_to_pinterest
from headliz.pinterest.models import UploadToPinterestRequest
from headliz.pinterest.browser import PinterestBrowserManager

app = typer.Typer(help="Headliz: Browser-automated uploads for Civitai and Pinterest.")
civitai_app = typer.Typer(help="Civitai upload commands.")
pinterest_app = typer.Typer(help="Pinterest upload commands.")

app.add_typer(civitai_app, name="civitai")
app.add_typer(pinterest_app, name="pinterest")

console = Console()

# Configure logging to use Rich
logging.basicConfig(
    level="INFO",
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)]
)

@civitai_app.command("upload")
def civitai_upload(
    image_base64: str = typer.Option(..., help="Base64-encoded image data"),
    title: str = typer.Option(..., help="Title of the image post"),
    description: str = typer.Option("", help="Description of the image post"),
    tags: Optional[List[str]] = typer.Option(None, "--tag", help="Tags for the image (can be specified multiple times)"),
):
    """Upload an image to Civitai."""
    async def run_upload():
        browser_manager = BrowserManager()
        request = UploadToCivitaiRequest(
            image_base64=image_base64,
            title=title,
            description=description,
            tags=tags or []
        )
        try:
            response = await upload_to_civitai(request, browser_manager)
            if response.success:
                console.print(f"[bold green]Success![/bold green] Post URL: {response.post_url}")
            else:
                console.print(f"[bold red]Failed:[/bold red] {response.message}")
        finally:
            await browser_manager.close()

    asyncio.run(run_upload())

@pinterest_app.command("upload")
def pinterest_upload(
    image_base64: str = typer.Option(..., help="Base64-encoded image data"),
    title: str = typer.Option(..., help="Title of the pin"),
    description: str = typer.Option("", help="Description of the pin"),
    tags: Optional[List[str]] = typer.Option(None, "--tag", help="Tags for the pin (can be specified multiple times)"),
    board_name: str = typer.Option("", help="Name of the board to pin to"),
):
    """Upload an image to Pinterest."""
    async def run_upload():
        browser_manager = PinterestBrowserManager()
        request = UploadToPinterestRequest(
            image_base64=image_base64,
            title=title,
            description=description,
            tags=tags or [],
            board_name=board_name
        )
        try:
            response = await upload_to_pinterest(request, browser_manager)
            if response.success:
                console.print(f"[bold green]Success![/bold green] Pin URL: {response.pin_url}")
            else:
                console.print(f"[bold red]Failed:[/bold red] {response.message}")
        finally:
            await browser_manager.close()

    asyncio.run(run_upload())

if __name__ == "__main__":
    app()
