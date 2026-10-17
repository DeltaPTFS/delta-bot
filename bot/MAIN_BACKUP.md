# Emergency main-bot backup inside HelpDesk

The HelpDesk application has a manual, **disabled-by-default** standby for the
DeltaPTFS/deltaptfs-bot code. Its ticket handlers, DMs, support formats and
existing application commands stay in Python and are not replaced.

## Discord commands (Delta administrators only)

- **/delta main enable**: Prepare the pinned copy of \`deltaptfs-bot\` and run
  its Node.js entry point under the HelpDesk application's Discord token.
- **/delta main disable**: Stop that Node.js process and clear its globally
  registered commands; leave HelpDesk's guild commands untouched.
- **/delta main status**: See whether the fallback is running, restarting or off.

Only members with Administrator permission or the configured founder/admin role
may use these controls. Commands only operate in the main Delta guild. The
fallback does **not** automatically switch on based on the main bot's online
status. Enable it intentionally when the primary Delta bot is unavailable.

## Runtime

The backup downloads a **pinned, reviewed Git commit** of the public
\`DeltaPTFS/deltaptfs-bot\` repository into \`bot/.main_backup/deltaptfs-bot\` and
installs its npm dependencies. This is a full local checkout of the original
main-bot source, not a hand-rewritten Python approximation. The upstream GitHub
repository is never modified. Its source is cached locally after the first
activation; a new SHA is only used after deliberately updating
\`MAIN_BACKUP_COMMIT\` and reviewing that revision.

Host prerequisites:

1. Install **Git, Node.js 20+ and npm** on the same host as HelpDesk. Ensure
   the service may reach GitHub and npm during the initial download.
2. Ensure HelpDesk's application has the necessary Discord permissions and
   gateway intents for the Delta main bot features.
3. Configure the Delta main bot's integration environment variables **on the
   HelpDesk host** where needed: \`DATABASE_URL\`, Roblox OAuth configuration,
   Google Sheets webhook, website API secrets, guild IDs, etc. The code does
   not copy secrets from the other bot's hosting environment.
4. Configure a separate publicly accessible callback/proxy if you need
   browser-based OAuth or inbound website sync to fail over. By default the
   Node sidecar binds an internal ephemeral \`PORT=0\`, preventing a port
   collision with the HelpDesk health server. **HTTP endpoints are not
   automatically transferred.**
5. Start HelpDesk as usual. Use the new Discord controls to activate or
   deactivate the standby. Test it in a maintenance window first.

Environment options:

| Setting | Default | Purpose |
| --- | --- | --- |
| \`MAIN_BACKUP_DIR\` | \`bot/.main_backup\` | Local checkout and toggle state |
| \`MAIN_BACKUP_COMMIT\` | pinned tested source revision | Reviewed main-bot commit to use |
| \`MAIN_BACKUP_PORT\` | \`0\` | Port for optional Node HTTP requests |
| \`MAIN_BACKUP_ENABLED\` | \`0\` | Restore-on-start fallback if no state file is present |
| \`MAIN_BACKUP_SKIP_DUPLICATE_LOGS\` | active (anything except \`0\`) | Skip main-bot server logs while HelpDesk is already logging |

The \`/delta main\` switch writes its last choice to
\`bot/.main_backup/mode.json\`, which is not committed to Git. Hosts with
ephemeral filesystems will lose that switch across redeploys; use persistent
storage or set \`MAIN_BACKUP_ENABLED\` at the host if restore-on-start is
required. A running sidecar is restarted automatically after a crash while
the switch is enabled; a disabled sidecar does not run.

## Command-name collisions

Both source bots include commands named \`/format\` and \`/skymiles\`. Discord
does not allow two different definitions of the same application command in one
scope. The fallback exposes the main-bot versions as **/main-format** and
**/main-skymiles**, while the original HelpDesk commands keep their names.
The source code remains unchanged; \`main_backup_shim.cjs\` adapts the backup
commands and dispatch at runtime. Main commands are globally registered; the
HelpDesk commands are registered in the Delta guild. Global commands may take
time to appear in Discord after activation.

## Safety and release policy

- Leave the original \`deltaptfs-bot\` offline while the backup is active to
  avoid duplicate processing of joins, roles, logging and event actions.
  HelpDesk's own ticket-related activity remains live. There can still be
  overlap between main-bot and HelpDesk event handlers; verify in staging.
- Main-bot startup notices are intentionally suppressed in fallback mode.
  This preserves HelpDesk's rule that finalized updates are announced only
  after the **last** deployment. Main-bot routine server logs are suppressed
  by default to avoid duplicating HelpDesk's server logs.
- The Node sidecar uses the HelpDesk **Discord application token** supplied
  through the host's environment. It never reads or copies the primary bot's
  token or checks a token into Git.
- Disabling removes the standby's global commands. HelpDesk's support/ticket
  guild commands are not removed. The main bot's databases, OAuth callbacks
  and external services must be tested separately before claiming full
  disaster-recovery coverage.
