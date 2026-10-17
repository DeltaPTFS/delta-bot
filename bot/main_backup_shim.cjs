"use strict";

// Preload for the independently hosted JavaScript main bot running under the
// HelpDesk application.  The source checkout itself stays byte-for-byte intact.
// Discord accepts only one command per root name in a single application:
// keep HelpDesk's /format and /skymiles, and expose the main counterparts under
// /main-format and /main-skymiles while emergency mode is enabled.
const { createRequire } = require("node:module");
const path = require("node:path");
const mainRequire = createRequire(path.join(process.cwd(), "package.json"));
const discord = mainRequire("discord.js");
const { ApplicationCommandManager, Client, Events } = discord;


// Keep the source checkout unmodified, but never send a deployment-update
// announcement merely because someone enabled the emergency backup. Release
// notices are coordinated by HelpDesk's final-deployment guard instead.
const fs = require("node:fs");
const Module = require("node:module");
const originalJsLoader = Module._extensions[".js"];
const sourceEntry = path.resolve(process.cwd(), "src/index.js");
const startupNotice = [
  "  for (const guild of readyClient.guilds.cache.values()) {",
  "    await postReplaceableUpdate(guild, { createOnly: true })",
  "      .catch((error) => console.error(",
].join("\n");
Module._extensions[".js"] = function loadBackupModule(module, filename) {
  if (path.resolve(filename) !== sourceEntry) return originalJsLoader(module, filename);
  let source = fs.readFileSync(filename, "utf8");
  if (!source.includes(startupNotice)) {
    throw new Error("Main bot changed its startup notice: review before enabling backup.");
  }
  source = source.replace(
    "  for (const guild of readyClient.guilds.cache.values()) {\n" +
    "    await postReplaceableUpdate(guild, { createOnly: true })\n" +
    "      .catch((error) => console.error(\`Could not post update for \${guild.id}:\`, error));\n" +
    "  }\n",
    "  // HelpDesk backup: never announce a new main-bot release on activation.\n"
  );
  // Optional duplicate-log prevention when HelpDesk already handles server logs.
  if (process.env.MAIN_BACKUP_SKIP_DUPLICATE_LOGS !== "0") {
    source = source.replace(
      "async function sendServerLog(guild, embed, pingLeadership = false) {\n",
      "async function sendServerLog(guild, embed, pingLeadership = false) {\n" +
      "  if (process.env.MAIN_BACKUP_ACTIVE === '1') return;\n"
    );
  }
  module._compile(source, filename);
};

const aliases = Object.freeze({
  "format": "main-format",
  "skymiles": "main-skymiles",
});
const reverseAliases = Object.fromEntries(
  Object.entries(aliases).map(([original, backup]) => [backup, original]),
);

// Main source registers GLOBAL application commands. HelpDesk uses GUILD
// commands, so they coexist without deleting the existing ticket commands.
const originalSet = ApplicationCommandManager.prototype.set;
ApplicationCommandManager.prototype.set = function (commands, ...rest) {
  if (!Array.isArray(commands)) return originalSet.call(this, commands, ...rest);
  const adapted = commands.map((definition) => ({
    ...definition,
    name: aliases[definition.name] || definition.name,
  }));
  return originalSet.call(this, adapted, ...rest);
};

const originalEmit = Client.prototype.emit;
Client.prototype.emit = function (event, ...args) {
  if (event === Events.InteractionCreate && args[0]?.isChatInputCommand?.()) {
    const interaction = args[0];
    const original = reverseAliases[interaction.commandName];
    if (original) {
      Object.defineProperty(interaction, "commandName", {
        configurable: true,
        writable: true,
        value: original,
      });
    }
  }
  return originalEmit.call(this, event, ...args);
};
