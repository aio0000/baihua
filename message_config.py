import json
import re
import string
from dataclasses import dataclass
from pathlib import Path as path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import discord


message_config_path = path(__file__).with_name("message_config.json")
message_page_size = 25
max_template_length = 2000

default_server_resources = {
    "ticket_category": 0,
    "welcome_channel": 0,
    "open_ticket_role": 0,
    "staff_role": 0,
    "massing_role": 0,
    "posted_role": 0,
    "new_ticket_exempt_roles": [],
    "done_output_channel": 0,
    "posted_output_channel": 0,
    "invs_output_channel": 0,
    "her_output_channel": 0,
    "status_channel": 0,
    "mass_status_channel": 0,
}

server_resource_labels = {
    "ticket_category": ("Ticket category", "category"),
    "welcome_channel": ("Welcome channel", "text"),
    "open_ticket_role": ("Open ticket role", "role"),
    "staff_role": ("Staff role", "role"),
    "massing_role": ("Massing role", "role"),
    "posted_role": ("Posted role", "role"),
    "new_ticket_exempt_roles": ("Ticket-closed bypass roles", "roles"),
    "done_output_channel": ("Done output channel", "text"),
    "posted_output_channel": ("Posted output channel", "text"),
    "invs_output_channel": ("Invites output channel", "text"),
    "her_output_channel": ("Checkpoint output channel", "text"),
    "status_channel": ("Counts status channel", "voice"),
    "mass_status_channel": ("Mass status channel", "voice"),
}

weekdays = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
default_mass_schedule = {
    "timezone": "Asia/Manila",
    "threshold": 20,
    "days": {
        "Monday": ("00:00", "12:00"),
        "Tuesday": None,
        "Wednesday": None,
        "Thursday": ("12:00", "24:00"),
        "Friday": ("00:00", "24:00"),
        "Saturday": ("00:00", "24:00"),
        "Sunday": ("00:00", "24:00"),
    },
}


@dataclass(frozen=True)
class output_message:
    group: str
    label: str
    default: str
    placeholders: tuple[str, ...] = ()


output_messages = {
    "welcome_embed": output_message(
        "Welcome",
        "Welcome embed",
        """_ _
_ _⠀⠀` ꒰ঌ ♱ ໒꒱ ` ⠀ ⠀ 𝔀ū⠀ 𝓵ìn ⠀shop
_ _⠀⠀✿❀。。here to https://discord.com/channels/1517762150058295406/1517962729573322862 
_ _⠀⠀or to https://discord.com/channels/1517762150058295406/1517769906978816201 ⠀<a:ngc002hrtsprkls:1521342163172986881> 
-# _ _ ⠀⠀・・┈・・ always check [__status__](https://discord.com/channels/1517762150058295406/1517762151094161452)
-# _ _ ⠀⠀` /new ` 4 ticket⠀|⠀inquire here!
_ _⠀⠀⠀_ _⠀⠀⠀""",
    ),
    "member_greeting": output_message("Welcome", "Member greeting", "hello, {member}", ("member",)),
    "ticket_intro": output_message("Tickets", "Ticket intro", "_ _ \n _ _ \n_ _ ┈┈┈ ⟢   click 2 start _ _"),
    "ticket_created": output_message(
        "Tickets",
        "Ticket created reply",
        "tckt created ┈ㆍ<:ngc004slvrsun:1518970371385331892> ㆍ┈ {channel}",
        ("channel",),
    ),
    "form_sent": output_message("Confirmations", "Form sent", "form sent!"),
    "proof_sent": output_message("Confirmations", "Proof sent", "*proof sent!*"),
    "sent": output_message("Confirmations", "Sent", "*sent!*"),
    "message_sent": output_message("Confirmations", "Message sent", "*msg sent!*"),
    "done": output_message("Confirmations", "Done", "*done!*"),
    "menu_prompt": output_message("Menus", "Menu prompt", "pick . . ."),
    "proof_continue_prompt": output_message("Menus", "Proof continuation prompt", "continue with the final details:"),
    "proof_deco_embed": output_message(
        "Forms",
        "Decoration proof embed",
        "_ _\n_ _⠀  ⠀  {name} thru ` {plan} ` ︵︵ ． ．୭\n"
        "_ _⠀  ⠀  own'd by {hirer} ⌢⌢⌢⌢ 𓂃✿．．\n"
        "_ _⠀  ⠀  ( ` {description} ` )\n_ _⠀⠀⠀_ _⠀⠀⠀",
        ("name", "plan", "hirer", "description"),
    ),
    "proof_partner_output": output_message(
        "Forms",
        "Partner proof output",
        "_ _ ⠀⠀_ _ ⠀⠀\n"
        "_ _ ⠀⠀[૮꒰](<{link}>)◞ ˕ ◟ ྀི[꒱ა]({proof}) ⠀ ⠀⠀⠀ ⠀⠀` {name} `\n"
        "_ _ ⠀⠀__{total}__ ⠀⠀ ꒰ ᧔ෆ᧓ ꒱ ⠀⠀4⠀⠀[{plan}]({review})\n"
        "_ _ ⠀⠀_ _ ⠀⠀_ _ ⠀⠀",
        ("link", "proof", "name", "total", "plan", "review"),
    ),
    "ad_separator": output_message(
        "Forms",
        "Advertisement separator",
        "ㆍㆍ(⟡✦⟡)ㆍㆍ",
    ),
    "link_separator": output_message(
        "Forms",
        "Link separator",
        "` 𓂃⠀⠀˖⠀𓇬⠀˖⠀⠀𓂃⠀`",
    ),
    "staff_ping": output_message(
        "Forms",
        "Staff role mention",
        "{staff_role}",
        ("staff_role",),
    ),
    "plan_line": output_message("Forms", "Plan suffix", "{plan} plan.", ("plan",)),
    "waitlist_separator": output_message(
        "Forms",
        "Waitlist separator",
        "_ _             ⏔⏔⏔⏔ ୨ ♡ ୧ ⏔⏔⏔⏔",
    ),
    "hire_password_wrong": output_message(
        "Hire flow",
        "Incorrect password",
        "**incorrect!** read thru the [tos](https://docs.google.com/document/d/1IfSQ3ELvnEwl3CThgohrc6Jb1TqFKGhhRjfDyzrmylU/edit?tab=t.0) to continue. \n channel will be deleted in __ 5 seconds. __",
    ),
    "hire_password_correct": output_message(
        "Hire flow",
        "Correct password response",
        "_ _ ⠀ ⠀\n _ _ ⠀ ⠀┈┈┈⠀ ⠀ ⠀ <a:ngc002swrlyspin:1518897992730677339>  \n_ _ ⠀ ⠀",
    ),
    "link_guidance": output_message(
        "Forms",
        "Link form guidance",
        "_ _   \n-# send our https://discord.com/channels/1517762150058295406/1518220013201391646 𓂃，\n-# in your links . . .   ⊹   send ss ꒰ 𐙚 ୭\n_ _  _   _",
    ),
    "mass_instructions": output_message(
        "Ticket workflow",
        "Massing instructions",
        "_ _ ⠀⠀⠀\n_ _ ⠀⠀⠀꒰ 𐙚 ୭，⠀{masser}\n_ _ ⠀⠀⠀code: ⠀⠀[` hrts4u `](https://discord.gg/a9Jj6erDFJ)\n_ _ ⠀⠀⠀5d2p  ┈  ask4ext\n_ _ ⠀⠀⠀_ _ ⠀⠀⠀",
        ("masser",),
    ),
    "proof_deco_spacer": output_message(
        "Forms",
        "Decoration proof spacer",
        "_ _\n_ _\n\n\n\n\n_ _",
    ),
    "proof_deco_art": output_message(
        "Forms",
        "Decoration proof image URL",
        "https://cdn.discordapp.com/attachments/1518247846703403219/1518647237398495334/Tumblr_l_401679934671512-removebg-preview.png?ex=6a3aadf4&is=6a395c74&hm=c7d6545b99d608eea739d30217a123c1d5073847a7980176cead5a6255400db7",
    ),
    "proof_partner_spacer": output_message(
        "Forms",
        "Partner proof spacer",
        "_ _\n_ _\n\n\n\n\n_ _",
    ),
    "proof_partner_art": output_message(
        "Forms",
        "Partner proof image URL",
        "https://cdn.discordapp.com/attachments/1518247846703403219/1518647237398495334/Tumblr_l_401679934671512-removebg-preview.png?ex=6a3aadf4&is=6a395c74&hm=c7d6545b99d608eea739d30217a123c1d5073847a7980176cead5a6255400db7",
    ),
    "missing_item_notice": output_message(
        "Errors",
        "Missing item notice",
        "_ _  \n_ _    ✿❀． `báihuā notice`\n"
        "_ _    <a:ngc002hrtsprkl:1539238587785150598> ┈┈  {item} can't be found!\n_ _  _ _",
        ("item",),
    ),
    "ticket_only_notice": output_message(
        "Errors",
        "Ticket channel required notice",
        "_ _  \n"
        "_ _    ✿❀． `báihuā notice`\n"
        "_ _    <a:ngc002hrtsprkl:1539238587785150598> ┈┈  command must be used \n"
        "_ _                       in a ticket channel!\n"
        "_ _  _ _",
    ),
    "no_masser_notice": output_message(
        "Errors",
        "No masser assigned notice",
        "_ _  \n"
        "_ _    ✿❀． `báihuā notice`\n"
        "_ _    <a:ngc002hrtsprkl:1539238587785150598> ┈┈  no masser found!\n"
        "_ _  _ _",
    ),
    "roles_missing_notice": output_message(
        "Errors",
        "Missing roles notice",
        "_ _  \n"
        "_ _    ✿❀． `báihuā notice`\n"
        "_ _    :ngc002hrtsprkl~1: ┈┈  uh, oh! roles can't be found!\n"
        "_ _  _ _",
    ),
    "masses_closed_notice": output_message(
        "Errors",
        "Masses closed notice",
        "_ _  \n"
        "_ _    ✿❀． `báihuā notice`\n"
        "_ _    <a:ngc002hrtsprkl:1539238587785150598> ┈┈  masses are closed!\n"
        "_ _  _ _",
    ),
    "closed_ticket_dm": output_message(
        "Ticket closing",
        "Masses-closed direct message",
        "_ _\n"
        "_ _        ✿❀  ┈┈┈┈┈┈ \n"
        "_ _        new message from *báihuā*!\n"
        "_ _            𓎢𓎟 ꒰  ୨ <a:ngc002hrtbeats:1523044381270216765> ୧  ꒱ 𓎟𓎡\n"
        "_ _ \n"
        "_ _        ꒱ა  ㆍ ㆍ ㆍ ㆍ  ticket: *closed*\n"
        "-# _ _         xue is currently closed—please \n"
        "-# _ _         check status + sched always!\n"
        "-# _ _         come back next time, thank u!\n"
        " _ _",
    ),
    "closed_ticket_fallback": output_message(
        "Ticket closing",
        "Masses-closed fallback notice",
        "_ _\n"
        "_ _        ✿❀  ┈┈┈┈┈┈ hello, {member}\n"
        "_ _        new message from *báihuā*!\n"
        "_ _            𓎢𓎟 ꒰  ୨ :ngc002hrtbeats: ୧  ꒱ 𓎟𓎡\n"
        "_ _ \n"
        "_ _        ꒱ა  ㆍ ㆍ ㆍ ㆍ  ticket: *closed*\n"
        "-# _ _         xue is currently closed—please \n"
        "-# _ _         check status + sched always!\n"
        "-# _ _         come back next time, thank u!\n"
        " _ _",
        ("member",),
    ),
    "manage_roles_error": output_message(
        "Errors",
        "Manage roles permission error",
        "I lack Manage Roles permission or role hierarchy prevents this.",
    ),
    "embed_send_error": output_message(
        "Errors",
        "Embed send error",
        "Failed to send embed: {error}",
        ("error",),
    ),
    "image_send_error": output_message(
        "Errors",
        "Image send error",
        "failed to send image embed: {error}",
        ("error",),
    ),
    "role_update_error": output_message("Errors", "Role update error", "Role update failed."),
    "wait_for_post": output_message(
        "Ticket workflow",
        "Done command public reply",
        "-# ꒰১ <:ngc004btrwngs:1518970193550774362> ໒꒱   ┈┈   wait 4 your ticket to be posted",
    ),
    "done_output": output_message(
        "Ticket workflow",
        "Done output message",
        "_ _⠀⠀ ⠀_ _⠀⠀ ⠀\n_ _⠀⠀ ⠀{staff_role}  <:ngc004flwrot:1518970225578741842>  {masser}\n_ _⠀⠀ ⠀᧔ෆ᧓，⠀ 𓂃 __{sep}__ **{urg}**\n_ _⠀⠀ ⠀{channel}，꒰꒰❀✿❀\n_ _⠀⠀ ⠀_ _⠀⠀ ⠀",
        ("staff_role", "masser", "sep", "urg", "channel"),
    ),
    "posted_ticket": output_message(
        "Ticket workflow",
        "Posted ticket message",
        "_ _⠀⠀ ⠀_ _⠀⠀ ⠀\n_ _⠀⠀ ⠀୨♡୧． ． ． {masser}\n_ _⠀⠀ ⠀sep time: __ start __， ໒꒱\n_ _⠀⠀ ⠀𓂅，check [invs]({link}) now <a:ngc002flwrsprkle:1521342158974484490>\n_ _⠀⠀ ⠀_ _⠀⠀ ⠀",
        ("masser", "link"),
    ),
    "posted_output": output_message(
        "Ticket workflow",
        "Posted output-channel message",
        "_ _\n_ _     __posted__ 𓂃♡．．\n_ _     𓂅， {masser}\n_ _     {sep} ┈ [`໒꒰՞ ܸ. .ܸ՞꒱ა`]({link})\n_ _   _ _",
        ("masser", "sep", "link"),
    ),
    "over_ticket": output_message(
        "Ticket workflow",
        "Over ticket message",
        "_ _⠀⠀ ⠀_ _⠀⠀\n_ _⠀⠀ ⠀┈┈・・ ・・ {masser}\n_ _⠀⠀ ⠀sep time: __ {sep} __  ． ． ໒ <a:ngc002parfum:1521342143942230046>\n_ _⠀⠀ ⠀𓂅，check [` /invs `]({link}) now\n_ _⠀⠀ ⠀_ _⠀⠀ ⠀",
        ("masser", "sep", "link"),
    ),
    "invs_output": output_message(
        "Ticket workflow",
        "Invite ratio output",
        "_ _⠀⠀ ⠀_ _⠀⠀ ⠀\n_ _⠀⠀ ⠀໒꒱．♡ ⠀ {masser}\n_ _⠀⠀ ⠀（ {invs}i ），𓂃\n_ _⠀⠀ ⠀{sep}h ꒰ ✿❀ ꒱ {portals}p\n_ _⠀⠀ ⠀┈┈ ` {desc} `\n_ _⠀⠀ ⠀",
        ("masser", "invs", "sep", "portals", "desc"),
    ),
    "invs_complete": output_message(
        "Ticket workflow",
        "Invite ticket completion reply",
        "┈┈・・ticket will close soon ． ． ．✿❀꒱ა\n┈┈・・tysm for massing! come back soon <a:ngc002hrtsprkls:1521342163172986881>",
    ),
    "checkpoint_output": output_message(
        "Other",
        "Checkpoint message",
        "_ _\n-# ⠀⠀⠀⠀ {member} says ...  `{confession}` \n_ _",
        ("member", "confession"),
    ),
    "checkpoint_reply": output_message(
        "Other",
        "Checkpoint confirmation",
        "checkpoint done.\n-# your secret is safe with me. . .",
    ),
    "waitlist_output": output_message(
        "Other",
        "Waitlist message",
        "_ _\n_ _  ` ૮ ྀིᴗ͈ . ᴗ͈ ྀིა `         __wait__list #{line}\n_ _  [**{name}**](<{link}>)   ⌢⌢⌢    {hirer}\n_ _  _ _",
        ("line", "name", "link", "hirer"),
    ),
    "run_partner_output": output_message(
        "Runs",
        "Partner run message",
        "_ _ ⠀⠀_ _ ⠀⠀\n"
        "_ _              __ ꒰ ✿❀✿ ꒱ __   [` {name} `](<{link}>)\n"
        "-# _ _                began **{start}** : {plan} for {invites} 。꒱ა。\n"
        "_ _ ⠀⠀_ _ ⠀⠀_ _ ⠀⠀",
        ("name", "link", "start", "plan", "invites"),
    ),
    "run_uploader_output": output_message(
        "Runs",
        "Uploader run message",
        "_ _ ⠀⠀_ _ ⠀⠀\n"
        "_ _              ★☆𓂅．．．[__{name}__](<{link}>)\n"
        "_ _              **{start}**     :     {uploads} ⌢ 𓂃✿\n"
        "_ _ ⠀⠀_ _ ⠀⠀_ _ ⠀⠀",
        ("name", "link", "start", "uploads"),
    ),
    "counts_success": output_message(
        "Counts",
        "Counts success reply",
        "_ _   𓂃✿．．counts + status updated! reminders sent: {amount} <a:ngc002hrtbeats:1523044381270216765>\n_ _   {mass_link}              ୨❀୧             {status_link}",
        ("amount", "mass_link", "status_link"),
    ),
    "w2p_reminder": output_message(
        "Ticket workflow",
        "W2P reminder",
        "_ _ ⠀⠀⠀\n"
        "_ _ ⠀⠀⠀ ໒．．⠀ hello, {masser},\n"
        "_ _ ⠀⠀⠀ ꒰ 𐙚  ┈  reminder to post!\n"
        "_ _ ⠀⠀⠀_ _ ⠀⠀⠀",
        ("masser",),
    ),
    "counts_permission_error": output_message(
        "Counts",
        "Counts permission error",
        "_ _  \n_ _    ✿❀． `báihuā notice`\n_ _    <a:ngc002hrtsprkl:1539238587785150598> ┈┈  I do not have permission to rename the status channel!\n_ _  _ _",
    ),
    "counts_partial_warning": output_message(
        "Counts",
        "Reminder permission warning",
        "-# Reminder checks failed in {history_errors} ticket(s); "
        "reminders could not be sent in {send_errors} ticket(s). "
        "Check the bot's Read Message History and Send Messages permissions.",
        ("history_errors", "send_errors"),
    ),
    "counts_audit_error": output_message(
        "Counts",
        "Audit log error",
        "_ _  \n_ _    ✿❀． `báihuā notice`\n"
        "_ _    <a:ngc002hrtsprkl:1539238587785150598> ┈┈  "
        "View Audit Log permission is needed for reminders!\n_ _  _ _",
    ),
    "counts_update_error": output_message(
        "Counts",
        "Counts update error",
        "_ _  \n_ _    ✿❀． `báihuā notice`\n"
        "_ _    <a:ngc002hrtsprkl:1539238587785150598> ┈┈  "
        "Discord couldn't update the status channels!\n_ _  _ _",
    ),
    "close_much": output_message(
        "Ticket closing",
        "Closed: too many massers",
        "_ _\n"
        "_ _    ꒰꒰❀✿❀．．new báihuā notice! ⠀ 𓂃\n"
        "_ _    ticket has been ┈┈┈┈┈ *closed* \n"
        "_ _    ` too many massers for this server `\n"
        "_ _",
    ),
    "close_over": output_message(
        "Ticket closing",
        "Closed: mass completed",
        "_ _\n"
        "_ _    ꒰꒰❀✿❀．．new báihuā notice! ⠀ 𓂃\n"
        "_ _    ticket has been ┈┈┈┈┈ *closed* \n"
        "_ _    ` mass has been completed, ty! `\n"
        "_ _",
    ),
    "close_oops": output_message(
        "Ticket closing",
        "Closed: no reply to reminders",
        "_ _\n"
        "_ _    ꒰꒰❀✿❀．．new báihuā notice! ⠀ 𓂃\n"
        "_ _    ticket has been ┈┈┈┈┈ *closed* \n"
        "_ _    ` was not replying to reminders `\n"
        "_ _",
    ),
    "setup_start": output_message(
        "Setup",
        "Setup introduction",
        "hello, {user}! what are we customising today? *all changes are for this server alone.*",
        ("user",),
    ),
    "setup_guild_only": output_message(
        "Setup",
        "Setup server-only notice",
        "use `/setup` inside the configured server.",
    ),
    "setup_admin_only": output_message(
        "Setup",
        "Setup administrator-only notice",
        "oops, only a server administrator can customize bot messages!",
    ),
    "setup_owner_only": output_message(
        "Setup",
        "Setup menu owner notice",
        "only the administrator who opened `/setup` can use this menu, sorry!",
    ),
    "setup_group_prompt": output_message(
        "Setup",
        "Setup group selection prompt",
        "choose a message group to customise:",
    ),
    "setup_picker_prompt": output_message(
        "Setup",
        "Setup message selection prompt",
        "please choose a **{group}** message!",
        ("group",),
    ),
    "setup_saved": output_message(
        "Setup",
        "Setup saved confirmation",
        "saved **{label}**! you can continue editing or reset it to its default.",
        ("label",),
    ),
    "setup_reset": output_message(
        "Setup",
        "Setup reset confirmation",
        "reset **{label}** to default!",
        ("label",),
    ),
    "setup_reset_select": output_message(
        "Setup",
        "Setup reset selection error",
        "choose a message before resetting it.",
    ),
    "setup_template_error": output_message(
        "Setup",
        "Setup template validation error",
        "this message could not be saved: {error}",
        ("error",),
    ),
    "setup_save_error": output_message(
        "Setup",
        "Setup save error",
        "could not save the message configuration: {error}",
        ("error",),
    ),
    "setup_reset_error": output_message(
        "Setup",
        "Setup reset error",
        "could not reset the message configuration: {error}",
        ("error",),
    ),
    "spacer": output_message("Dividers", "Divider spacer", "_ _   _ _"),
    "divider_flower": output_message("Dividers", "Flower divider", "_ _                      𓎢𓎟 ꒰ ` ୨❀୧ ` ꒱ 𓎟𓡎"),
    "divider_icon": output_message("Dividers", "Small icon divider", "-# _ _                      ┈┈┈┈┈┈┈┈ `  ໒꒰୨୧꒱ა  `"),
    "divider_image_1": output_message(
        "Dividers",
        "Divider image URL 1",
        "https://cdn.discordapp.com/attachments/1518247846703403219/1518647237398495334/Tumblr_l_401679934671512-removebg-preview.png?ex=6a3aadf4&is=6a395c74&hm=c7d6545b99d608eea739d30217a123c1d5073847a7980176cead5a6255400db7",
    ),
    "divider_image_2": output_message(
        "Dividers",
        "Divider image URL 2",
        "https://cdn.discordapp.com/attachments/1517770077301112943/1523041520461152276/image.png?ex=6a4aaa73&is=6a4958f3&hm=436ea3c917a4e2d84050113ae608c4d5378fdd4c6df48076f800128c305f6d40&",
    ),
    "checkpoint_333": output_message(
        "Dividers",
        "Checkpoint .333",
        "_ _ ⠀⠀ ┈┈ ⠀ [` /done `](https://open.spotify.com/playlist/22Ck6C1WGjd2BzTTU4kv3C?si=dc76186527964382)  ⠀when  ⠀fin \n_ _   _ _",
    ),
    "checkpoint_444": output_message(
        "Dividers",
        "Checkpoint .444",
        "_ _ ⠀⠀ ┈┈ ⠀ [` /done `](https://open.spotify.com/playlist/6MVvRvoT0EsUDZw2FkHkzO?si=87d5dec645944b33)  ⠀when  ⠀fin \n_ _   _ _",
    ),
    "checkpoint_666": output_message(
        "Dividers",
        "Checkpoint .666",
        "_ _ ⠀⠀ ┈┈ ⠀ [` /done `](https://open.spotify.com/playlist/4rWPKO2sfmmKYZ7Jk5RjWS?si=5154819612c041ea)  ⠀when  ⠀fin \n_ _   _ _",
    ),
    "checkpoint_999": output_message(
        "Dividers",
        "Checkpoint .999",
        "_ _ ⠀⠀ ┈┈ ⠀ [` /done `](https://open.spotify.com/playlist/66vBkSNJu494Bg2yG5FTbo?si=2f2dab9916d54272)  ⠀when  ⠀fin \n_ _   _ _",
    ),
}

groups = tuple(dict.fromkeys(message.group for message in output_messages.values()))
message_overrides: dict[str, dict[str, str]] = {}
server_resource_overrides: dict[str, dict[str, int | list[int]]] = {}
mass_schedule_overrides: dict[str, dict[str, object]] = {}


def load_message_overrides() -> None:
    try:
        config = json.loads(message_config_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Invalid message configuration file: {error}") from error

    if not isinstance(config, dict) or not isinstance(config.get("guilds", {}), dict):
        raise RuntimeError("The message configuration file must contain a 'guilds' object.")

    for guild_id, overrides in config.get("guilds", {}).items():
        if not isinstance(overrides, dict):
            raise RuntimeError(f"Message overrides for guild {guild_id} must be an object.")
        for key, value in overrides.items():
            if key not in output_messages or not isinstance(value, str):
                raise RuntimeError(
                    f"Invalid message override '{key}' for guild {guild_id}."
                )
            error = validate_template(key, value)
            if error is not None:
                raise RuntimeError(
                    f"Invalid message override '{key}' for guild {guild_id}: {error}"
                )
        message_overrides[guild_id] = overrides

    resources = config.get("server_resources", {})
    if not isinstance(resources, dict):
        raise RuntimeError("The message configuration 'server_resources' must be an object.")
    for guild_id, overrides in resources.items():
        if not isinstance(overrides, dict):
            raise RuntimeError(f"Server resources for guild {guild_id} must be an object.")
        for key, value in overrides.items():
            default = default_server_resources.get(key)
            valid_scalar = isinstance(default, int) and isinstance(value, int)
            valid_roles = (
                isinstance(default, list)
                and isinstance(value, list)
                and all(isinstance(role_id, int) for role_id in value)
            )
            if not valid_scalar and not valid_roles:
                raise RuntimeError(
                    f"Invalid server resource '{key}' for guild {guild_id}."
                )
        server_resource_overrides[guild_id] = overrides

    schedules = config.get("mass_schedules", {})
    if not isinstance(schedules, dict):
        raise RuntimeError("The message configuration 'mass_schedules' must be an object.")
    for guild_id, schedule in schedules.items():
        if not isinstance(schedule, dict):
            raise RuntimeError(f"Mass schedule for guild {guild_id} must be an object.")
        if set(schedule).difference({"timezone", "threshold", "days"}):
            raise RuntimeError(f"Mass schedule for guild {guild_id} has unknown settings.")
        schedule_days = schedule.get("days", {})
        if not isinstance(schedule_days, dict):
            raise RuntimeError(f"Mass schedule days for guild {guild_id} must be an object.")
        complete_schedule = {
            **default_mass_schedule,
            **schedule,
            "days": {**default_mass_schedule["days"], **schedule_days},
        }
        validate_mass_schedule(complete_schedule)
        mass_schedule_overrides[guild_id] = schedule


def save_message_overrides() -> None:
    payload = json.dumps(
        {
            "guilds": message_overrides,
            "server_resources": server_resource_overrides,
            "mass_schedules": mass_schedule_overrides,
        },
        ensure_ascii=False,
        indent=2,
    )
    temporary_path = message_config_path.with_suffix(".json.tmp")
    temporary_path.write_text(payload + "\n", encoding="utf-8")
    temporary_path.replace(message_config_path)


def get_message(guild_id: int | None, key: str, **values: object) -> str:
    message = output_messages[key]
    template = message_overrides.get(str(guild_id), {}).get(key, message.default)
    try:
        return template.format_map(values)
    except (KeyError, ValueError, IndexError) as error:
        raise ValueError(f"Invalid custom template for '{message.label}': {error}") from error


def validate_template(key: str, template: str) -> str | None:
    message = output_messages[key]
    if len(template) > max_template_length:
        return f"Message text must be {max_template_length} characters or fewer."
    try:
        fields = {
            field_name
            for _, field_name, _, _ in string.Formatter().parse(template)
            if field_name is not None
        }
    except ValueError as error:
        return f"Template syntax error: {error}"

    unsupported_fields = fields.difference(message.placeholders)
    if unsupported_fields:
        return "Unknown placeholder(s): " + ", ".join(sorted(unsupported_fields))

    try:
        template.format_map({field: "example" for field in message.placeholders})
    except (KeyError, ValueError, IndexError) as error:
        return f"Template syntax error: {error}"
    return None


def set_message_override(guild_id: int, key: str, template: str | None) -> None:
    overrides = message_overrides.setdefault(str(guild_id), {})
    if template is None:
        overrides.pop(key, None)
        if not overrides:
            message_overrides.pop(str(guild_id), None)
    else:
        overrides[key] = template
    save_message_overrides()


def get_server_resource(guild_id: int | None, key: str) -> int:
    if key not in default_server_resources:
        raise KeyError(f"Unknown server resource: {key}")
    resource_id = server_resource_overrides.get(str(guild_id), {}).get(
        key, default_server_resources[key]
    )
    if not isinstance(resource_id, int):
        raise TypeError(f"Server resource '{key}' contains multiple role IDs.")
    return resource_id


def get_server_resource_list(guild_id: int | None, key: str) -> list[int]:
    if key not in default_server_resources:
        raise KeyError(f"Unknown server resource: {key}")
    value = server_resource_overrides.get(str(guild_id), {}).get(
        key, default_server_resources[key]
    )
    if not isinstance(value, list):
        raise TypeError(f"Server resource '{key}' does not contain a list of IDs.")
    return value


def current_resource_value(guild_id: int, key: str) -> str:
    value = server_resource_overrides.get(str(guild_id), {}).get(
        key, default_server_resources[key]
    )
    if isinstance(value, list):
        return ", ".join(map(str, value)) or "none"
    if value == 0:
        return "not set"
    return str(value)


def set_server_resource(
    guild_id: int,
    key: str,
    resource_id: int | list[int] | None,
) -> None:
    if key not in default_server_resources:
        raise KeyError(f"Unknown server resource: {key}")
    default = default_server_resources[key]
    if resource_id is not None:
        if isinstance(default, list):
            valid_resource = (
                isinstance(resource_id, list)
                and all(type(role_id) is int and role_id > 0 for role_id in resource_id)
            )
        else:
            valid_resource = type(resource_id) is int and resource_id > 0
        if not valid_resource:
            raise ValueError(f"Invalid value for server resource '{key}'.")

    overrides = server_resource_overrides.setdefault(str(guild_id), {})
    if resource_id is None or resource_id == default_server_resources[key]:
        overrides.pop(key, None)
        if not overrides:
            server_resource_overrides.pop(str(guild_id), None)
    else:
        overrides[key] = resource_id
    save_message_overrides()


def validate_mass_schedule(schedule: dict[str, object]) -> None:
    timezone_name = schedule.get("timezone")
    if not isinstance(timezone_name, str):
        raise ValueError("Timezone must be a valid IANA timezone name.")
    try:
        ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError("Timezone must be a valid IANA timezone name.") from error

    threshold = schedule.get("threshold")
    if type(threshold) is not int or not 0 <= threshold <= 100_000:
        raise ValueError("Ticket threshold must be between 0 and 100000.")

    days = schedule.get("days")
    if not isinstance(days, dict) or set(days) != set(weekdays):
        raise ValueError("Schedule must have an entry for every weekday.")
    for day, hours in days.items():
        if hours is None:
            continue
        if (
            not isinstance(hours, (list, tuple))
            or len(hours) != 2
            or not all(isinstance(value, str) for value in hours)
        ):
            raise ValueError(f"{day} hours must contain an opening and closing time.")
        opening, closing = hours
        time_pattern = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
        close_pattern = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$|^24:00$")
        if not time_pattern.fullmatch(opening) or not close_pattern.fullmatch(closing):
            raise ValueError(f"{day} times must use HH:MM (closing time may be 24:00).")
        if _time_to_minutes(closing) <= _time_to_minutes(opening):
            raise ValueError(f"{day} closing time must be later than its opening time.")


def _time_to_minutes(value: str) -> int:
    hours, minutes = map(int, value.split(":"))
    return hours * 60 + minutes


def get_mass_schedule(guild_id: int | None) -> dict[str, object]:
    schedule = {
        **default_mass_schedule,
        **mass_schedule_overrides.get(str(guild_id), {}),
    }
    schedule["days"] = {
        **default_mass_schedule["days"],
        **mass_schedule_overrides.get(str(guild_id), {}).get("days", {}),
    }
    return schedule


def update_mass_schedule(
    guild_id: int,
    *,
    timezone_name: str | None = None,
    threshold: int | None = None,
    day: str | None = None,
    opening: str | None = None,
    closing: str | None = None,
) -> None:
    schedule = get_mass_schedule(guild_id)
    days = dict(schedule["days"])
    if day is not None:
        if day not in weekdays:
            raise ValueError("Unknown weekday.")
        days[day] = None if not opening and not closing else (opening, closing)
    updated = {
        "timezone": timezone_name if timezone_name is not None else schedule["timezone"],
        "threshold": threshold if threshold is not None else schedule["threshold"],
        "days": days,
    }
    validate_mass_schedule(updated)

    overrides = mass_schedule_overrides.setdefault(str(guild_id), {})
    if timezone_name is not None:
        overrides["timezone"] = timezone_name
    if threshold is not None:
        overrides["threshold"] = threshold
    if day is not None:
        changed_days = dict(overrides.get("days", {}))
        if days[day] == default_mass_schedule["days"][day]:
            changed_days.pop(day, None)
        else:
            changed_days[day] = days[day]
        if changed_days:
            overrides["days"] = changed_days
        else:
            overrides.pop("days", None)
    if not overrides:
        mass_schedule_overrides.pop(str(guild_id), None)
    save_message_overrides()


def reset_mass_schedule(guild_id: int) -> None:
    mass_schedule_overrides.pop(str(guild_id), None)
    save_message_overrides()


async def require_setup_owner(interaction: discord.Interaction, owner_id: int) -> bool:
    if interaction.user.id == owner_id:
        return True
    await interaction.response.send_message(
        get_message(interaction.guild_id, "setup_owner_only"),
        ephemeral=True,
    )
    return False


class template_editor(discord.ui.Modal):
    def __init__(
        self,
        owner_id: int,
        guild_id: int,
        group: str,
        page: int,
        key: str,
    ):
        self.owner_id = owner_id
        self.guild_id = guild_id
        self.group = group
        self.page = page
        self.key = key
        message = output_messages[key]
        super().__init__(title=f"edit: {message.label.lower()[:40]}")
        current = message_overrides.get(str(guild_id), {}).get(key, message.default)
        placeholder_text = (
            "placeholders: " + ", ".join(f"{{{name}}}" for name in message.placeholders)
            if message.placeholders
            else "enter the complete message text"
        )
        self.template = discord.ui.TextInput(
            label="message text",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=max_template_length,
            default=current,
            placeholder=placeholder_text[:100],
        )
        self.add_item(self.template)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        error = validate_template(self.key, self.template.value)
        if error:
            await interaction.response.send_message(
                get_message(self.guild_id, "setup_template_error", error=error),
                ephemeral=True,
            )
            return

        try:
            set_message_override(self.guild_id, self.key, self.template.value)
        except OSError as error:
            await interaction.response.send_message(
                get_message(self.guild_id, "setup_save_error", error=error),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            get_message(
                self.guild_id,
                "setup_saved",
                label=output_messages[self.key].label.lower(),
            ),
            ephemeral=True,
            view=message_picker_view(
                self.owner_id,
                self.guild_id,
                self.group,
                page=self.page,
                selected_key=self.key,
            ),
        )


class message_setup_view(discord.ui.View):
    def __init__(self, owner_id: int, guild_id: int):
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.guild_id = guild_id
        options = [
            discord.SelectOption(label=group.lower()[:100], value=group)
            for group in groups
        ]
        select = discord.ui.Select(
            placeholder="choose a message group to customise",
            options=options,
        )
        select.callback = self.select_group
        self.add_item(select)

    @discord.ui.button(
        label="server settings",
        style=discord.ButtonStyle.primary,
        row=1,
    )
    async def server_settings(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if not await require_setup_owner(interaction, self.owner_id):
            return
        await interaction.response.edit_message(
            content="choose a role or channel to configure:",
            view=server_settings_view(self.owner_id, self.guild_id),
        )

    @discord.ui.button(
        label="massing schedule",
        style=discord.ButtonStyle.primary,
        row=1,
    )
    async def massing_schedule(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if not await require_setup_owner(interaction, self.owner_id):
            return
        await interaction.response.edit_message(
            content=mass_schedule_description(self.guild_id),
            view=mass_schedule_view(self.owner_id, self.guild_id),
        )

    async def select_group(self, interaction: discord.Interaction) -> None:
        if not await require_setup_owner(interaction, self.owner_id):
            return
        group = interaction.data["values"][0]
        await interaction.response.edit_message(
            content=get_message(
                self.guild_id,
                "setup_picker_prompt",
                group=group,
            ),
            view=message_picker_view(self.owner_id, self.guild_id, group),
        )


class server_settings_view(discord.ui.View):
    def __init__(self, owner_id: int, guild_id: int):
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.guild_id = guild_id
        options = [
            discord.SelectOption(
                label=label.lower(),
                value=key,
                description=(
                    f"current setting: {current_resource_value(guild_id, key)}"
                )[:100],
            )
            for key, (label, _) in server_resource_labels.items()
        ]
        select = discord.ui.Select(
            placeholder="choose!",
            options=options,
        )
        select.callback = self.select_resource
        self.add_item(select)

    @discord.ui.button(
        label="back to messages",
        style=discord.ButtonStyle.secondary,
        row=1,
    )
    async def back_to_messages(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if not await require_setup_owner(interaction, self.owner_id):
            return
        await interaction.response.edit_message(
            content=get_message(self.guild_id, "setup_group_prompt"),
            view=message_setup_view(self.owner_id, self.guild_id),
        )

    async def select_resource(self, interaction: discord.Interaction) -> None:
        if not await require_setup_owner(interaction, self.owner_id):
            return
        key = interaction.data["values"][0]
        label, resource_type = server_resource_labels[key]
        guild = interaction.guild
        if resource_type == "roles":
            current_ids = get_server_resource_list(self.guild_id, key)
            current_label = ", ".join(
                role.mention
                if guild and (role := guild.get_role(role_id))
                else f"`{role_id}`"
                for role_id in current_ids
            ) or "none"
        else:
            current_id = get_server_resource(self.guild_id, key)
            if current_id == 0:
                current_label = "not set"
            else:
                current = (
                    guild.get_role(current_id)
                    if guild and resource_type == "role"
                    else guild.get_channel(current_id)
                    if guild
                    else None
                )
                current_label = (
                    current.mention
                    if current is not None
                    else f"`{current_id}` (not found)"
                )
        await interaction.response.edit_message(
            content=(
                f"select the **{label.lower()}**.\n"
                f"current setting: {current_label}.\n"
                "*use reset to clear!*"
            ),
            view=server_resource_target_view(
                self.owner_id,
                self.guild_id,
                key,
            ),
        )


class server_resource_target_view(discord.ui.View):
    def __init__(self, owner_id: int, guild_id: int, key: str):
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.guild_id = guild_id
        self.key = key
        label, resource_type = server_resource_labels[key]

        if resource_type == "role":
            select = discord.ui.RoleSelect(
                placeholder="choose!",
                min_values=1,
                max_values=1,
            )
        elif resource_type == "roles":
            select = discord.ui.RoleSelect(
                placeholder="choose!",
                min_values=1,
                max_values=25,
            )
        else:
            channel_types = {
                "category": [discord.ChannelType.category],
                "text": [discord.ChannelType.text],
                "voice": [discord.ChannelType.voice],
            }[resource_type]
            select = discord.ui.ChannelSelect(
                placeholder="choose!",
                channel_types=channel_types,
                min_values=1,
                max_values=1,
            )
        select.callback = self.save_selection
        self.add_item(select)

    @discord.ui.button(
        label="back to server settings",
        style=discord.ButtonStyle.secondary,
        row=1,
    )
    async def back_to_settings(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if not await require_setup_owner(interaction, self.owner_id):
            return
        await interaction.response.edit_message(
            content="choose a role or channel to configure:",
            view=server_settings_view(self.owner_id, self.guild_id),
        )

    @discord.ui.button(
        label="reset to default",
        style=discord.ButtonStyle.danger,
        row=1,
    )
    async def reset_resource(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if not await require_setup_owner(interaction, self.owner_id):
            return
        try:
            set_server_resource(self.guild_id, self.key, None)
        except OSError as error:
            await interaction.response.send_message(
                f"could not reset this server setting: {error}",
                ephemeral=True,
            )
            return
        label, _ = server_resource_labels[self.key]
        value = default_server_resources[self.key]
        shown_value = ", ".join(map(str, value)) if isinstance(value, list) else value
        reset_message = (
            "no built-in value is set. choose a server resource in `/setup`."
            if value == 0 or value == []
            else f"reset **{label.lower()}** to its built-in default (`{shown_value}`)."
        )
        await interaction.response.edit_message(
            content=reset_message,
            view=server_settings_view(self.owner_id, self.guild_id),
        )

    async def save_selection(self, interaction: discord.Interaction) -> None:
        if not await require_setup_owner(interaction, self.owner_id):
            return
        selected_values = interaction.data["values"]
        try:
            resource_value = (
                [int(value) for value in selected_values]
                if server_resource_labels[self.key][1] == "roles"
                else int(selected_values[0])
            )
            set_server_resource(self.guild_id, self.key, resource_value)
        except (OSError, ValueError) as error:
            await interaction.response.send_message(
                f"could not save this server setting: {error}",
                ephemeral=True,
            )
            return

        label, _ = server_resource_labels[self.key]
        selected_label = (
            ", ".join(f"<@&{value}>" for value in selected_values)
            if server_resource_labels[self.key][1] == "roles"
            else f"`{selected_values[0]}`"
        )
        await interaction.response.edit_message(
            content=(
                f"saved **{label.lower()}** as {selected_label}. "
                "choose another resource or return to message settings."
            ),
            view=server_settings_view(self.owner_id, self.guild_id),
        )


def _display_day_hours(hours: object) -> str:
    if hours is None:
        return "closed"
    opening, closing = hours
    return f"{opening}-{closing}"


def mass_schedule_description(guild_id: int) -> str:
    schedule = get_mass_schedule(guild_id)
    days = schedule["days"]
    day_summary = "\n".join(
        f"**{day}:** {_display_day_hours(days[day])}"
        for day in weekdays
    )
    threshold = schedule["threshold"]
    threshold_text = "disabled" if threshold == 0 else str(threshold)
    return (
        f"**weekly massing hours** (`{schedule['timezone']}`)\n{day_summary}\n\n"
        f"automatically close at **{threshold_text} n2p tickets** "
        f"(0 disables the limit).\n"
        "choose a weekday to edit the hours! use 24:00 to close at midnight, "
        "and leave both time fields blank to mark a day closed ♡"
    )


class mass_schedule_view(discord.ui.View):
    def __init__(self, owner_id: int, guild_id: int):
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.guild_id = guild_id
        days = get_mass_schedule(guild_id)["days"]
        day_select = discord.ui.Select(
            placeholder="choose a weekday to edit",
            options=[
                discord.SelectOption(
                    label=day.lower(),
                    value=day,
                    description=_display_day_hours(days[day])[:100],
                )
                for day in weekdays
            ],
        )
        day_select.callback = self.select_day
        self.add_item(day_select)

    @discord.ui.button(
        label="timezone and ticket limit",
        style=discord.ButtonStyle.primary,
        row=1,
    )
    async def edit_global_schedule(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if not await require_setup_owner(interaction, self.owner_id):
            return
        await interaction.response.send_modal(
            mass_schedule_settings_modal(self.owner_id, self.guild_id)
        )

    @discord.ui.button(
        label="reset schedule",
        style=discord.ButtonStyle.danger,
        row=1,
    )
    async def reset_schedule(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if not await require_setup_owner(interaction, self.owner_id):
            return
        try:
            reset_mass_schedule(self.guild_id)
        except OSError as error:
            await interaction.response.send_message(
                f"could not reset the massing schedule: {error}",
                ephemeral=True,
            )
            return
        await interaction.response.edit_message(
            content=mass_schedule_description(self.guild_id),
            view=mass_schedule_view(self.owner_id, self.guild_id),
        )

    @discord.ui.button(
        label="back to setup",
        style=discord.ButtonStyle.secondary,
        row=1,
    )
    async def back_to_setup(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if not await require_setup_owner(interaction, self.owner_id):
            return
        await interaction.response.edit_message(
            content=get_message(self.guild_id, "setup_group_prompt"),
            view=message_setup_view(self.owner_id, self.guild_id),
        )

    async def select_day(self, interaction: discord.Interaction) -> None:
        if not await require_setup_owner(interaction, self.owner_id):
            return
        day = interaction.data["values"][0]
        await interaction.response.send_modal(
            mass_day_schedule_modal(self.owner_id, self.guild_id, day)
        )


class mass_schedule_settings_modal(discord.ui.Modal):
    def __init__(self, owner_id: int, guild_id: int):
        super().__init__(title="massing schedule settings")
        self.owner_id = owner_id
        self.guild_id = guild_id
        schedule = get_mass_schedule(guild_id)
        self.timezone = discord.ui.TextInput(
            label="timezone (IANA name)",
            default=schedule["timezone"],
            placeholder="e.g. Asia/Manila or America/New_York",
            max_length=100,
        )
        self.threshold = discord.ui.TextInput(
            label="n2p ticket limit (0 disables)",
            default=str(schedule["threshold"]),
            placeholder="20",
            max_length=6,
        )
        self.add_item(self.timezone)
        self.add_item(self.threshold)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not await require_setup_owner(interaction, self.owner_id):
            return
        try:
            threshold = int(self.threshold.value)
            update_mass_schedule(
                self.guild_id,
                timezone_name=self.timezone.value.strip(),
                threshold=threshold,
            )
        except (ValueError, OSError) as error:
            await interaction.response.send_message(
                f"could not save the massing schedule: {error}",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            content=mass_schedule_description(self.guild_id),
            view=mass_schedule_view(self.owner_id, self.guild_id),
            ephemeral=True,
        )


class mass_day_schedule_modal(discord.ui.Modal):
    def __init__(self, owner_id: int, guild_id: int, day: str):
        super().__init__(title=f"edit {day.lower()} hours")
        self.owner_id = owner_id
        self.guild_id = guild_id
        self.day = day
        hours = get_mass_schedule(guild_id)["days"][day]
        opening, closing = hours if hours is not None else ("", "")
        self.opening = discord.ui.TextInput(
            label="opening time (24-hour HH:MM)",
            default=opening,
            required=False,
            placeholder="e.g. 09:00",
            max_length=5,
        )
        self.closing = discord.ui.TextInput(
            label="closing time (HH:MM or 24:00)",
            default=closing,
            required=False,
            placeholder="e.g. 17:00 or 24:00",
            max_length=5,
        )
        self.add_item(self.opening)
        self.add_item(self.closing)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not await require_setup_owner(interaction, self.owner_id):
            return
        opening = self.opening.value.strip()
        closing = self.closing.value.strip()
        if bool(opening) != bool(closing):
            await interaction.response.send_message(
                "enter both times, or leave both blank to mark the day closed.",
                ephemeral=True,
            )
            return
        try:
            update_mass_schedule(
                self.guild_id,
                day=self.day,
                opening=opening,
                closing=closing,
            )
        except (ValueError, OSError) as error:
            await interaction.response.send_message(
                f"could not save {self.day.lower()}'s hours: {error}",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            content=mass_schedule_description(self.guild_id),
            view=mass_schedule_view(self.owner_id, self.guild_id),
            ephemeral=True,
        )


class message_picker_view(discord.ui.View):
    def __init__(
        self,
        owner_id: int,
        guild_id: int,
        group: str,
        page: int = 0,
        selected_key: str | None = None,
    ):
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.guild_id = guild_id
        self.group = group
        self.page = page
        self.selected_key = selected_key
        self.keys = [
            key for key, message in output_messages.items()
            if message.group == group
        ]
        page_count = max(1, (len(self.keys) + message_page_size - 1) // message_page_size)
        self.page = min(page, page_count - 1)

        page_keys = self.keys[
            self.page * message_page_size:(self.page + 1) * message_page_size
        ]
        options = []
        for key in page_keys:
            message = output_messages[key]
            placeholders = ", ".join(f"{{{name}}}" for name in message.placeholders)
            options.append(
                discord.SelectOption(
                    label=message.label.lower()[:100],
                    value=key,
                    description=(f"placeholders: {placeholders}" if placeholders else "no placeholders")[:100],
                    default=key == selected_key,
                )
            )
        select = discord.ui.Select(
            placeholder="what to edit?",
            options=options,
        )
        select.callback = self.select_template
        self.add_item(select)

        back = discord.ui.Button(label="groups", style=discord.ButtonStyle.secondary, row=1)
        back.callback = self.go_back
        self.add_item(back)
        previous = discord.ui.Button(
            label="previous",
            style=discord.ButtonStyle.secondary,
            disabled=self.page == 0,
            row=1,
        )
        previous.callback = self.previous_page
        self.add_item(previous)
        next_page = discord.ui.Button(
            label="next",
            style=discord.ButtonStyle.secondary,
            disabled=self.page >= page_count - 1,
            row=1,
        )
        next_page.callback = self.next_page
        self.add_item(next_page)
        reset = discord.ui.Button(
            label="reset selected",
            style=discord.ButtonStyle.danger,
            disabled=selected_key is None,
            row=1,
        )
        reset.callback = self.reset_template
        self.add_item(reset)

    async def select_template(self, interaction: discord.Interaction) -> None:
        if not await require_setup_owner(interaction, self.owner_id):
            return
        self.selected_key = interaction.data["values"][0]
        await interaction.response.send_modal(
            template_editor(
                self.owner_id,
                self.guild_id,
                self.group,
                self.page,
                self.selected_key,
            )
        )

    async def go_back(self, interaction: discord.Interaction) -> None:
        if not await require_setup_owner(interaction, self.owner_id):
            return
        await interaction.response.edit_message(
            content=get_message(self.guild_id, "setup_group_prompt"),
            view=message_setup_view(self.owner_id, self.guild_id),
        )

    async def previous_page(self, interaction: discord.Interaction) -> None:
        if not await require_setup_owner(interaction, self.owner_id):
            return
        await interaction.response.edit_message(
            content=get_message(
                self.guild_id,
                "setup_picker_prompt",
                group=self.group.lower(),
            ),
            view=message_picker_view(
                self.owner_id,
                self.guild_id,
                self.group,
                page=self.page - 1,
                selected_key=self.selected_key,
            ),
        )

    async def next_page(self, interaction: discord.Interaction) -> None:
        if not await require_setup_owner(interaction, self.owner_id):
            return
        await interaction.response.edit_message(
            content=get_message(
                self.guild_id,
                "setup_picker_prompt",
                group=self.group.lower(),
            ),
            view=message_picker_view(
                self.owner_id,
                self.guild_id,
                self.group,
                page=self.page + 1,
                selected_key=self.selected_key,
            ),
        )

    async def reset_template(self, interaction: discord.Interaction) -> None:
        if not await require_setup_owner(interaction, self.owner_id):
            return
        if self.selected_key is None:
            await interaction.response.send_message(
                get_message(self.guild_id, "setup_reset_select"),
                ephemeral=True,
            )
            return
        try:
            set_message_override(self.guild_id, self.selected_key, None)
        except OSError as error:
            await interaction.response.send_message(
                get_message(self.guild_id, "setup_reset_error", error=error),
                ephemeral=True,
            )
            return
        await interaction.response.edit_message(
            content=get_message(
                self.guild_id,
                "setup_reset",
                label=output_messages[self.selected_key].label.lower(),
            ),
            view=message_picker_view(
                self.owner_id,
                self.guild_id,
                self.group,
                page=self.page,
            ),
        )


load_message_overrides()
