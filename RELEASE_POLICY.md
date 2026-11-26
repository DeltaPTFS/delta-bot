# Delta HelpDesk release announcements

HelpDesk announcements are **release events**, not GitHub push notifications.

1. During development and multi-commit updates, keep `announce_on_final_deployment` set to `false` in `bot/deployment_notes.json`. Changes and redeploys are silent.
2. When the update is complete, set `BOT_VERSION` in `bot/config.py` to the final version, write the release notes, and keep `release_version` in the JSON equal to `BOT_VERSION`.
3. **Only in the final release commit**, set `announce_on_final_deployment` to `true`. Allow that finished commit to deploy.
4. After the bot starts, it waits `RELEASE_ANNOUNCEMENT_DELAY_SECONDS` (default **180 seconds**), then checks the latest release flag and existing messages in `#server-logs`. A message is sent only if the release is finalized and that version was not previously announced.
5. The founder receives one DM **only after the final release announcement is posted**. Reconnects and intermediate commits do not generate update DMs.

When beginning the next update, change the version and release notes in your working commits but leave the release flag `false` until the final commit. Repeated pushes of an already-announced version do not generate additional posts.

**Permissions:** The bot needs **View Channel, Read Message History, and Send Messages** in `#server-logs`. If history cannot be checked, the release announcement is intentionally suppressed to avoid duplicates. All official release notices are sent exclusively to channel `1539005101941850274`; the bot does not fall back to a different channel.

Previously sent duplicate announcements are not deleted by this release policy. Deployment ID is retained in the one official version announcement for debugging.


## Website releases

The regular Delta bot checks `https://roblox-delta-web.vercel.app/release-info` every five minutes. Only a successful production deployment with a valid Git commit SHA qualifies. The notifier checks recent channel history before sending and ignores already-announced commits. Website and HelpDesk updates use the same channel. Vercel preview builds and ordinary Git pushes are not announced. The bot must be online with View Channel, Read Message History and Send Messages permissions. A website deployment that is superseded between polling cycles may not receive its own notice.
