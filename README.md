# baihua's code

## run the bot

1. install python 3.10 or newer and `discord.py`:

   ```sh
   python -m pip install -U discord.py
   ```

2. create a discord application and bot through [discord's developer portal](https://discord.com/developers/home), invite it to your server,
   and enable the **Server Members Intent** and **Message Content Intent** in the developer portal.

3. set the variables `BOT_TOKEN`, `GUILD_ID`, and `HIRE_PASSWORD`.
   `GUILD_ID` is the numeric ID of the server where the slash commands should
   appear. keep the bot token private; never put it in source code or commit it.

   on macOS/Linux, set them in the same terminal you use to start the bot:

   ```sh
   export BOT_TOKEN="paste-your-private-bot-token"
   export GUILD_ID="your-server-id"
   export HIRE_PASSWORD="choose-a-private-password"
   python main.py
   ```

   in Windows PowerShell, use `$env:BOT_TOKEN="..."`, `$env:GUILD_ID="..."`,
   and `$env:HIRE_PASSWORD="..."`, then run `python main.py` in that same
   window.

4. invite the bot with the permissions required by the commands, including
   manage channels, manage roles, view audit log, read message
   history, and send messages. channel and role selections are configured in
   `/setup`; `GUILD_ID` remains the server where the bot syncs its slash commands.

5. start the bot with `python main.py`. in the configured server, run `/setup`
   as an administrator to customize its output messages.

## Customize messages with `/setup`

`/setup` is available to server administrators. select a message group, choose a
message, edit the complete text in the popup, and submit. The editor lists the
supported placeholders for messages that contain changing values. Keep a
placeholder such as `{channel}` or `{masser}` in the text if you want that value
to appear; unknown placeholders are rejected before saving. Choose **Reset
selected** to restore a message's built-in default.

choose **server settings** in `/setup` to select the ticket category, welcome,
status, and workflow output channels, plus the open-ticket, staff, massing, and
posted roles. It also lets you choose the roles allowed to open tickets while
massing is closed. All server resource defaults are unset, so configure the
resources your server uses before enabling the matching commands. These
selections are stored per server in `message_config.json` and remain editable
after a restart. Use **reset to default** to clear a selection.

choose **massing schedule** in `/setup` to set open and closed hours for each
weekday, select the IANA timezone, and adjust the N2P ticket limit that
automatically closes massing. Use a limit of `0` to disable the ticket limit.
Daily hours use 24-hour `HH:MM`; use `24:00` as a closing time for midnight,
or leave both times blank to mark that weekday closed. To set hours that cross
midnight, split them between the two weekdays. **reset schedule** restores the
built-in schedule.

changes are saved per server in `message_config.json` beside `main.py` and
survive bot restarts. That generated file is ignored by Git so local message
customizations and server-specific text are not committed by accident. Back it
up if you want to keep your customizations.

the editor covers the bot's user-facing text responses (including `/setup`
prompts and errors), message templates, embed descriptions, and divider/image
URL messages. server-specific channel and role IDs are selected through the
server settings panel rather than edited as text. the bot token and
`GUILD_ID` are environment configuration; `GUILD_ID` determines where slash
commands are registered and must be changed in the environment before startup
if the bot is moved to another server. Slash-command names, form labels,
select-menu/button labels, and thumbnail URLs remain source configuration.

the `/runs` command opens a menu for partner and uploader run announcements.
Their message templates can be customized in `/setup` under **runs**. `/lay`
sends the supplied text as a Discord Components V2 layout. both commands
require a member with the configured staff role.

the `/acc`, `/done`, `/posted`, `/over`, `/invs`, and `/close` workflow
commands are limited to channels inside the configured ticket category.
`/done`, `/posted`, `/over`, and `/invs` also require the ticket topic to
contain an assigned masser ID; `/acc` writes that ID when assigning a masser.
`/new` is blocked while massing is closed except for members with a configured
bypass role. `/close` deletes the ticket and then DMs the assigned masser the
selected closure notice; if the topic has no masser, choose one with the
command's optional `masser` parameter.

some things may need to be edited directly through the code itself, so 
should there be issues, especially through `setup`, please contact
[@lunaemisa](https://discord.com/users/861086733361479720) on discord or join [the portal](https://discord.gg/2KPqm4dwA2)
