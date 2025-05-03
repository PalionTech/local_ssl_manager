"""
User interface components for interactive domain selection.

This module provides an interactive terminal interface for selecting
domains from a list, with support for both curses-based and fallback
text-based interfaces.
"""

import platform
from datetime import datetime
from typing import List, Optional, Tuple

# Import rich for text-based UI fallback
from rich.console import Console
from rich.prompt import Prompt

# Try to import curses, but it might not be available on all platforms
try:
    import curses

    CURSES_AVAILABLE = True
except ImportError:
    CURSES_AVAILABLE = False


def show_domain_selector(domains: List[Tuple[str, datetime]]) -> Optional[str]:
    """
    Display an interactive domain selector.

    Args:
        domains: List of tuples containing domain names and creation dates

    Returns:
        Selected domain name, or None if selection was cancelled
    """
    if not domains:
        print("No domains found.")
        return None

    # Use curses-based selector if available, text-based otherwise
    if CURSES_AVAILABLE and platform.system() != "Windows":
        return _curses_selector(domains)
    else:
        return _text_selector(domains)


def _curses_selector(domains: List[Tuple[str, datetime]]) -> Optional[str]:
    """
    Display a curses-based domain selector.

    Args:
        domains: List of tuples containing domain names and creation dates

    Returns:
        Selected domain name, or None if selection was cancelled
    """

    def _selector_main(stdscr):
        # Initialize curses
        curses.curs_set(0)  # Hide cursor
        curses.start_color()
        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)  # Selected item

        current_row = 0

        while True:
            stdscr.clear()
            height, width = stdscr.getmaxyx()

            # Display header
            header = "Select a Domain (↑/↓: Navigate, Enter: Select, q: Cancel)"
            stdscr.addstr(0, 0, header, curses.A_BOLD)

            # Display domains
            for idx, (domain, created_at) in enumerate(domains):
                # Calculate indentation based on domain hierarchy
                indent = domain.count(".") * 2
                date_str = created_at.strftime("%Y-%m-%d %H:%M")
                display_str = f"{' ' * indent}{domain} (created: {date_str})"

                # Check if this row is currently selected
                if idx == current_row:
                    stdscr.attron(curses.color_pair(1))
                    stdscr.addstr(idx + 2, 0, display_str.ljust(width - 1))
                    stdscr.attroff(curses.color_pair(1))
                else:
                    stdscr.addstr(idx + 2, 0, display_str)

            # Handle keyboard input
            key = stdscr.getch()

            if key == curses.KEY_UP and current_row > 0:
                current_row -= 1
            elif key == curses.KEY_DOWN and current_row < len(domains) - 1:
                current_row += 1
            elif key == ord("\n"):  # Enter key
                return domains[current_row][0]
            elif key == ord("q"):  # q key to quit
                return None

            stdscr.refresh()

    try:
        return curses.wrapper(_selector_main)
    except Exception as e:
        # Fallback to text-based selector if curses encounters an error
        print(f"Error with curses interface: {e}")
        return _text_selector(domains)


def _text_selector(domains: List[Tuple[str, datetime]]) -> Optional[str]:
    """
    Display a text-based domain selector using Rich.

    Args:
        domains: List of tuples containing domain names and creation dates

    Returns:
        Selected domain name, or None if selection was cancelled
    """
    console = Console()

    console.print("[bold]Select a domain:[/bold]")

    for i, (domain, created_at) in enumerate(domains, 1):
        # Add indentation based on domain hierarchy
        indent = "  " * domain.count(".")
        date_str = created_at.strftime("%Y-%m-%d %H:%M")
        console.print(f"{i}. {indent}{domain} [dim](created: {date_str})[/dim]")

    console.print("\nEnter the number of the domain to select, or 'q' to cancel.")

    while True:
        choice = Prompt.ask("Domain number")

        if choice.lower() == "q":
            return None

        try:
            index = int(choice) - 1
            if 0 <= index < len(domains):
                return domains[index][0]
            else:
                console.print(
                    f"[red]Please enter a number between 1 and {len(domains)}[/red]"
                )
        except ValueError:
            console.print("[red]Please enter a valid number[/red]")
