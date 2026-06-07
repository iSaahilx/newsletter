from __future__ import annotations

from datetime import datetime

from rich.console import Console


console = Console()


def log(message: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    console.print(f"[dim]{timestamp}[/dim] {message}")


def success(message: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    console.print(f"[dim]{timestamp}[/dim] [green]{message}[/green]")


def warn(message: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    console.print(f"[dim]{timestamp}[/dim] [yellow]{message}[/yellow]")
