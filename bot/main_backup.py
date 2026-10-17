"""Opt-in, separately supervised Delta main-bot fallback for HelpDesk.

The production HelpDesk implementation stays in main.py.  This module starts an
unmodified, pinned checkout of deltaptfs-bot with a small command-name shim when
authorized staff explicitly activate the fallback.  No bot tokens are stored.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from pathlib import Path

import discord
from discord import app_commands

from config import ADMIN_ROLE_ID, GUILD_ID

log = logging.getLogger("delta-helpdesk.main-backup")

SOURCE_URL = "https://github.com/DeltaPTFS/deltaptfs-bot.git"
# Audited main-branch revision when this fallback was built. Never execute an
# unreviewed moving branch with the HelpDesk application's Discord token.
SOURCE_COMMIT = "d7460e39a21af422803b484b4ec7352ad52335cf"
BACKUP_DIR = Path(os.getenv("MAIN_BACKUP_DIR", str(Path(__file__).resolve().parent / ".main_backup")))
MODE_FILE = BACKUP_DIR / "mode.json"
SOURCE_DIR = BACKUP_DIR / "deltaptfs-bot"
READY_MESSAGE = "Commands are registered."


async def run_checked(*arguments: str, cwd: Path | None = None, timeout: int = 180) -> str:
    """Run a fixed-argument executable; never invoke a shell or echo secrets."""
    try:
        process = await asyncio.create_subprocess_exec(
            *arguments, cwd=str(cwd) if cwd else None,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Required program is unavailable: {arguments[0]}") from exc
    try:
        out, _ = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except asyncio.TimeoutError as exc:
        process.kill()
        await process.wait()
        raise RuntimeError(f"{arguments[0]} timed out after {timeout} seconds.") from exc
    decoded = out.decode("utf-8", errors="replace")
    if process.returncode:
        raise RuntimeError(f"{arguments[0]} failed (exit {process.returncode}): {decoded[-700:]}")
    return decoded


class MainBackup:
    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.process: asyncio.subprocess.Process | None = None
        self._lock = asyncio.Lock()
        self._stdout_task: asyncio.Task | None = None
        self._watch_task: asyncio.Task | None = None
        self._ready: asyncio.Event | None = None
        self._start_error = ""
        self._enabled = self._load_enabled()

    def _load_enabled(self) -> bool:
        try:
            data = json.loads(MODE_FILE.read_text(encoding="utf-8"))
            return data.get("enabled") is True
        except (OSError, ValueError, TypeError):
            return os.getenv("MAIN_BACKUP_ENABLED", "0") == "1"

    def _save_enabled(self, enabled: bool) -> None:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        tmp = MODE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps({"enabled": enabled}) + "\n", encoding="utf-8")
        tmp.replace(MODE_FILE)
        self._enabled = enabled

    async def prepare(self) -> None:
        """Fetch the exact upstream source and install its Node dependencies."""
        commit = os.getenv("MAIN_BACKUP_COMMIT", SOURCE_COMMIT).lower().strip()
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise RuntimeError("MAIN_BACKUP_COMMIT must be a full 40-character Git SHA.")
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        await run_checked("node", "--version", timeout=15)
        await run_checked("npm", "--version", timeout=15)
        if not (SOURCE_DIR / ".git").exists():
            SOURCE_DIR.mkdir(parents=True, exist_ok=True)
            await run_checked("git", "init", cwd=SOURCE_DIR, timeout=30)
            await run_checked("git", "remote", "add", "origin", SOURCE_URL, cwd=SOURCE_DIR, timeout=30)
        installed = SOURCE_DIR / ".delta-main-installed"
        if installed.exists() and installed.read_text(encoding="utf-8").strip() == commit:
            return
        await run_checked("git", "fetch", "--depth", "1", "origin", commit, cwd=SOURCE_DIR, timeout=120)
        await run_checked("git", "checkout", "--force", "FETCH_HEAD", cwd=SOURCE_DIR, timeout=30)
        await run_checked("npm", "install", "--omit=dev", "--ignore-scripts",
                          "--no-audit", "--no-fund", cwd=SOURCE_DIR, timeout=240)
        installed.write_text(commit + "\n", encoding="utf-8")

    async def _read_output(self, process: asyncio.subprocess.Process) -> None:
        assert process.stdout is not None
        async for raw in process.stdout:
            message = raw.decode("utf-8", errors="replace").rstrip()
            if READY_MESSAGE in message:
                if self._ready is not None:
                    self._ready.set()
            if "Discord command registration failed:" in message:
                self._start_error = "Discord rejected the main bot command registration."
                if self._ready is not None:
                    self._ready.set()
            # Source stdout must never contain the token. Keep diagnostic logs
            # private and avoid echoing unexpected upstream output unfiltered.
            log.debug("Main fallback runtime output received (%d characters)", len(message))
        if self._ready is not None:
            self._ready.set()

    async def _launch(self) -> None:
        await self.prepare()
        env = os.environ.copy()
        env["PORT"] = os.getenv("MAIN_BACKUP_PORT", "0")
        env["GUILD_ID"] = str(GUILD_ID)
        env["MAIN_BACKUP_ACTIVE"] = "1"
        shim = Path(__file__).resolve().with_name("main_backup_shim.cjs")
        self._ready = asyncio.Event()
        self._start_error = ""
        try:
            self.process = await asyncio.create_subprocess_exec(
                "node", "--require", str(shim), "src/index.js",
                cwd=str(SOURCE_DIR), env=env,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            )
            self._stdout_task = asyncio.create_task(self._read_output(self.process))
            await asyncio.wait_for(self._ready.wait(), timeout=90)
            if self._start_error or self.process.returncode is not None:
                raise RuntimeError(self._start_error or "Main bot process stopped during startup.")
        except Exception:
            await self._terminate()
            raise

    async def _terminate(self) -> None:
        process = self.process
        self.process = None
        if process is not None and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=12)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
        if self._stdout_task:
            await asyncio.gather(self._stdout_task, return_exceptions=True)
            self._stdout_task = None

    async def enable(self) -> str:
        async with self._lock:
            if self.process is not None and self.process.returncode is None:
                return "The Delta main-bot backup is already running on HelpDesk."
            try:
                await self._launch()
            except Exception as exc:
                log.warning("Main backup activation failed: %s", type(exc).__name__)
                return f"Backup could not start: {str(exc)[:450]}"
            self._save_enabled(True)
            if self._watch_task is None or self._watch_task.done():
                self._watch_task = asyncio.create_task(self._watch())
            return ("Delta main-bot backup is enabled on HelpDesk. Existing ticket "
                    "commands remain available. Use /delta main disable to stop it.")

    async def _watch(self) -> None:
        """Restart a crashed backup, but never turn it on unless opted in."""
        retry_delay = 15
        while self._enabled:
            process = self.process
            if process is not None:
                await process.wait()
            if not self._enabled:
                break
            log.warning("Main fallback stopped unexpectedly; retrying in %d seconds.", retry_delay)
            await asyncio.sleep(retry_delay)
            if not self._enabled:
                break
            async with self._lock:
                if self._enabled and (self.process is None or self.process.returncode is not None):
                    try:
                        await self._launch()
                        retry_delay = 15
                    except Exception:
                        log.exception("Could not restart main fallback")
                        retry_delay = min(retry_delay * 2, 300)

    async def disable(self) -> str:
        # Disable first so the process watcher does not restart the child.
        self._save_enabled(False)
        if self._watch_task is not None:
            self._watch_task.cancel()
        async with self._lock:
            await self._terminate()
            # The HelpDesk sync intentionally owns no global commands.  The
            # main bot registered globals; syncing the empty global command
            # tree removes them without affecting HelpDesk's guild commands.
            try:
                await self.bot.tree.sync()
            except discord.HTTPException:
                log.exception("Main backup stopped, but could not remove global commands")
                return ("Backup process disabled, but Discord did not clear its global "
                        "slash commands. Retry /delta main disable.")
        return "Delta main-bot backup disabled. HelpDesk ticket commands are unchanged."

    def status(self) -> str:
        if self.process is not None and self.process.returncode is None:
            return "Enabled — Delta main-bot backup is running on HelpDesk."
        if self._enabled:
            return "Enabled — backup is currently restarting or unavailable."
        return "Disabled — HelpDesk is running independently."

    async def restore_on_start(self) -> None:
        if self._enabled:
            async def resume() -> None:
                result = await self.enable()
                log.info("Saved main backup setting restored: %s", result.split(".")[0])
            asyncio.create_task(resume())


def register_commands(tree: app_commands.CommandTree, backup: MainBackup) -> None:
    """Expose /delta main enable, /delta main disable, and /delta main status."""
    delta = app_commands.Group(name="delta", description="Delta Air Lines operations")
    main = app_commands.Group(name="main", description="Emergency main-bot backup controls")

    async def authorized(interaction: discord.Interaction) -> bool:
        if interaction.guild_id != GUILD_ID or not isinstance(interaction.user, discord.Member):
            return False
        member = interaction.user
        return (member.guild_permissions.administrator
                or any(role.id == ADMIN_ROLE_ID for role in member.roles))

    @main.command(name="enable", description="Activate the main Delta bot on HelpDesk")
    @app_commands.check(authorized)
    async def enable(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        await interaction.followup.send(await backup.enable(), ephemeral=True)

    @main.command(name="disable", description="Stop the main Delta backup and keep HelpDesk running")
    @app_commands.check(authorized)
    async def disable(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        await interaction.followup.send(await backup.disable(), ephemeral=True)

    @main.command(name="status", description="Check if the emergency Delta backup is active")
    @app_commands.check(authorized)
    async def status(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(backup.status(), ephemeral=True)

    @delta.error
    async def group_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        if interaction.response.is_done():
            await interaction.followup.send("You need Delta administrative access to use this.", ephemeral=True)
        else:
            await interaction.response.send_message("You need Delta administrative access to use this.", ephemeral=True)

    delta.add_command(main)
    tree.add_command(delta)
