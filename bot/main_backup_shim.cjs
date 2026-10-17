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
