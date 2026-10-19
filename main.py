import os
import discord
import asyncio
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo as zone_info
from discord.ext import commands
from discord import app_commands
from message_config import (
    message_setup_view,
    get_message,
    get_server_resource,
    get_server_resource_list,
    get_mass_schedule,
)


def output(interaction: discord.Interaction, key: str, **values: object) -> str:
    return get_message(interaction.guild_id, key, **values)


def server_resource(interaction: discord.Interaction, key: str) -> int:
    return get_server_resource(interaction.guild_id, key)


def has_server_role(key: str):
    async def predicate(interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member):
            return False
        role_id = server_resource(interaction, key)
        return any(role.id == role_id for role in interaction.user.roles)

    return app_commands.check(predicate)


async def require_ticket_channel(interaction: discord.Interaction) -> bool:
    if (
        isinstance(interaction.channel, discord.TextChannel)
        and interaction.channel.category_id
        == server_resource(interaction, "ticket_category")
    ):
        return True
    await interaction.response.send_message(
        get_message(interaction.guild_id, "ticket_only_notice"),
        ephemeral=True,
    )
    return False


def ticket_masser_id(channel: discord.TextChannel) -> int | None:
    topic = channel.topic or ""
    match = re.search(
        r"(?:baihua-)?masser:\s*(?:<@!?(\d+)>|(\d+))|\|\s*(\d+)",
        topic,
        re.IGNORECASE,
    )
    if match is None:
        return None
    return int(next(group for group in match.groups() if group is not None))


async def require_assigned_masser(interaction: discord.Interaction) -> bool:
    channel = interaction.channel
    if (
        isinstance(channel, discord.TextChannel)
        and ticket_masser_id(channel) is not None
    ):
        return True
    await interaction.response.send_message(
        get_message(interaction.guild_id, "no_masser_notice"),
        ephemeral=True,
    )
    return False


async def send_missing_item_notice(
    interaction: discord.Interaction,
    item: str,
) -> None:
    notice = output(interaction, "missing_item_notice", item=item)
    if interaction.response.is_done():
        await interaction.edit_original_response(content=notice)
    else:
        await interaction.response.send_message(notice, ephemeral=True)


def count_n2p_channels(category: discord.CategoryChannel) -> int:
    return sum(
        isinstance(channel, discord.TextChannel)
        and any(term in channel.name.lower() for term in ("urg", "ovd"))
        for channel in category.channels
    )


def get_mass_status(n2p_count: int, guild_id: int) -> str:
    schedule = get_mass_schedule(guild_id)
    local_now = datetime.now(zone_info(schedule["timezone"]))
    daily_hours = schedule["days"][local_now.strftime("%A")]
    scheduled_open = False
    if daily_hours is not None:
        opening_hour, opening_minute = map(int, daily_hours[0].split(":"))
        closing_hour, closing_minute = map(int, daily_hours[1].split(":"))
        minute_of_day = local_now.hour * 60 + local_now.minute
        scheduled_open = (
            opening_hour * 60 + opening_minute
            <= minute_of_day
            < closing_hour * 60 + closing_minute
        )
    threshold = schedule["threshold"]
    threshold_reached = threshold > 0 and n2p_count >= threshold
    return "open" if scheduled_open and not threshold_reached else "closed"


async def send_w2p_reminders(
    guild: discord.Guild,
    channels: list[discord.TextChannel],
) -> tuple[int, int, int]:
    w2p_channels = {
        channel.id: channel
        for channel in channels
        if "w2p" in channel.name.lower()
    }
    if not w2p_channels:
        return 0, 0, 0

    rename_times: dict[int, datetime] = {}
    async for entry in guild.audit_logs(
        limit=None,
        action=discord.AuditLogAction.channel_update,
    ):
        channel_id = getattr(entry.target, "id", None)
        if channel_id not in w2p_channels or channel_id in rename_times:
            continue

        before_name = getattr(entry.before, "name", None)
        after_name = getattr(entry.after, "name", None)
        if (
            before_name is not None
            and after_name is not None
            and before_name != after_name
            and "w2p" in after_name.lower()
        ):
            rename_times[channel_id] = entry.created_at

        if len(rename_times) == len(w2p_channels):
            break

    sent = 0
    history_errors = 0
    send_errors = 0
    now = discord.utils.utcnow()
    for channel_id, channel in w2p_channels.items():
        renamed_at = rename_times.get(channel_id)
        if renamed_at is None or now - renamed_at < timedelta(days=3):
            continue

        try:
            latest_message = None
            async for message in channel.history(limit=1):
                latest_message = message
                break
        except discord.HTTPException:
            history_errors += 1
            continue

        match = re.search(r"\|\s*(\d+)", channel.topic or "")
        if match is None:
            continue

        reminder = get_message(
            guild.id,
            "w2p_reminder",
            masser=f"<@{match.group(1)}>",
        )
        if latest_message is not None and latest_message.created_at > renamed_at:
            continue

        try:
            await channel.send(reminder)
            sent += 1
        except discord.HTTPException:
            send_errors += 1

    return sent, history_errors, send_errors


class bot_client(commands.Bot):
    def __init__(self, command_prefix, intents):
        super().__init__(command_prefix=command_prefix, intents=intents)
    async def on_ready(self):
        await self.change_presence(
            status=discord.Status.online,
            activity=discord.Game(name="with potions in wū lín discord shop")
        )
        print(f'Logged on as {self.user}!')
        
        try:
            synced = await self.tree.sync(guild=guild_id)
            print(f'Synced {len(synced)} command to guild {guild_id.id}.')

        except Exception as e:
            print(f'Failed to sync commands: {e}')

    async def on_member_join(self, member):
        channel_id = get_server_resource(member.guild.id, "welcome_channel")
        channel = self.get_channel(channel_id) if channel_id else None
        if not isinstance(channel, discord.TextChannel):
            print(
                f"Welcome channel is not configured for server {member.guild.id}; "
                f"skipping greeting for member {member.id}."
            )
            return
        welcome = discord.Embed(
            description=get_message(member.guild.id, "welcome_embed"),
            color=0x242429,
        )
        welcome.set_thumbnail(
            url="https://media.discordapp.net/attachments/1518247846703403219/1522555766983098368/IMG_4504.png?ex=6a48e60e&is=6a47948e&hm=02aafd84473bd7110909be79b535a90ac17e0080890fa038cb71d40d85aec209&=&format=webp&quality=lossless&width=1000&height=1000"
        )
        await channel.send(
            get_message(member.guild.id, "member_greeting", member=member.mention),
            embed=welcome,
        )

    
    async def on_message(self, message):
        if message.author == self.user:
            return 
        guild_id = message.guild.id if message.guild else None
        
        # dividers

        if message.content == ".div":
            try:
                await message.delete()
            except discord.Forbidden:
                pass
            await message.channel.send(get_message(guild_id, "spacer"))
            await message.channel.send(get_message(guild_id, "divider_flower"))
            await message.channel.send(get_message(guild_id, "spacer"))
            return
        
        if message.content == ",div":
            try:
                await message.delete()
            except discord.Forbidden:
                pass
            await message.channel.send(get_message(guild_id, "spacer"))
            await message.channel.send(get_message(guild_id, "divider_image_1"))
            await message.channel.send(get_message(guild_id, "spacer"))
            return

        if message.content == ";div":
            try:
                await message.delete()
            except discord.Forbidden:
                pass
            await message.channel.send(get_message(guild_id, "spacer"))
            await message.channel.send(get_message(guild_id, "divider_icon"))
            await message.channel.send(get_message(guild_id, "spacer"))
            return

        if message.content == "'div":
            try:
                await message.delete()
            except discord.Forbidden:
                pass
            await message.channel.send(get_message(guild_id, "spacer"))
            await message.channel.send(get_message(guild_id, "divider_image_2"))
            await message.channel.send(get_message(guild_id, "spacer"))
            return
        
        # checkpoints

        if message.content == ".333":
            try:
                await message.delete()
            except discord.Forbidden:
                pass
            await message.channel.send(get_message(guild_id, "spacer"))
            await message.channel.send(get_message(guild_id, "checkpoint_333"))
            await message.channel.send(get_message(guild_id, "spacer"))
            return
        
        if message.content == ".444":
            try:
                await message.delete()
            except discord.Forbidden:
                pass
            await message.channel.send(get_message(guild_id, "spacer"))
            await message.channel.send(get_message(guild_id, "checkpoint_444"))
            await message.channel.send(get_message(guild_id, "spacer"))
            return
        
        if message.content == ".666":
            try:
                await message.delete()
            except discord.Forbidden:
                pass
            await message.channel.send(get_message(guild_id, "spacer"))
            await message.channel.send(get_message(guild_id, "checkpoint_666"))
            await message.channel.send(get_message(guild_id, "spacer"))
            return
        
        if message.content == ".999":
            try:
                await message.delete()
            except discord.Forbidden:
                pass
            await message.channel.send(get_message(guild_id, "spacer"))
            await message.channel.send(get_message(guild_id, "checkpoint_999"))
            await message.channel.send(get_message(guild_id, "spacer"))
            return
        


intents = discord.Intents.default()
intents.message_content = True
intents.members = True
client = bot_client(command_prefix='%', intents=intents)
bot_token = os.getenv("BOT_TOKEN")
if not bot_token:
    raise RuntimeError("BOT_TOKEN environment variable is required. Do not hardcode bot tokens in source files.")

guild_id_raw = os.getenv("GUILD_ID")
if not guild_id_raw:
    raise RuntimeError("GUILD_ID environment variable is required.")
guild_id = discord.Object(id=int(guild_id_raw))

hire_password = os.getenv("HIRE_PASSWORD")
if not hire_password:
    raise RuntimeError("HIRE_PASSWORD environment variable is required.")


# pre-determined messages 


# buttons, select menus, and modals.


class mass_form(discord.ui.Modal, title="massing w. xue . . ."):
    mass_link = discord.ui.TextInput(
        label="✿❀꒱ა． ． ． link",
        style=discord.TextStyle.short,
        required=True,
        placeholder="https://discord.gg/orchids"
    )
    mass_ad = discord.ui.TextInput(
        label="𓂅． ． ． ad",
        style=discord.TextStyle.paragraph,
        required=True,
        placeholder="come join . . orchids!"
    )
    mass_name = discord.ui.TextInput(
        label="✿❀꒱ა． ． ． name",
        style=discord.TextStyle.short,
        required=True,
        placeholder="orchids"
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await interaction.channel.edit(name='┈ㆍmassㆍ' + (self.mass_name.value))
        await interaction.channel.send(
            output(
                interaction,
                "staff_ping",
                staff_role=f"<@&{server_resource(interaction, 'staff_role')}>",
            )
        )
        await interaction.channel.send(output(interaction, "ad_separator"))
        admsg = await interaction.channel.send(self.mass_ad.value)
        await interaction.channel.send(output(interaction, "link_separator"))
        linkmsg = await interaction.channel.send(self.mass_link.value)
        await interaction.edit_original_response(content=output(interaction, "form_sent"))
        await admsg.pin()
        await linkmsg.pin()


class continue_hire_view(discord.ui.View):
    @discord.ui.button(label=" ✿❀꒱ა． ． ．click", style=discord.ButtonStyle.gray)
    async def continue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(hire_form())


class hire_password_form(discord.ui.Modal, title=". . . what's the password?"):
    password = discord.ui.TextInput(
        label="┈┈┈  ໒꒰୨୧꒱ა",
        style=discord.TextStyle.short,
        required=True,
        placeholder="read thru https://hrts444u.carrd.co",
        min_length=1,
    )

    async def on_submit(self, interaction: discord.Interaction):
        if self.password.value != hire_password:
            await interaction.response.send_message(
                output(interaction, "hire_password_wrong"), ephemeral=True
            )
            await asyncio.sleep(5)
            try:
                await interaction.channel.delete(reason='incorrect password entered.')
            except Exception as e:
                print(f'Failed to delete channel after wrong password: {e}')
            return

        await interaction.response.send_message(
            output(interaction, "hire_password_correct"),
            ephemeral=True,
            view=continue_hire_view()
        )


class hire_form(discord.ui.Modal, title="hiring xue?"):
    hire_ad = discord.ui.TextInput(
        label="𓂅． ． ． ad",
        style=discord.TextStyle.paragraph,
        required=True,
        placeholder="come join . . wu lin!"
    )
    hire_plan = discord.ui.TextInput(
        label="check .. 🖋﹚order！ for plans.",
        style=discord.TextStyle.paragraph,
        required=True,
        placeholder="AU4UM, ETH3R."
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await interaction.channel.edit(name='┈ㆍhire')
        await interaction.channel.send(
            output(
                interaction,
                "staff_ping",
                staff_role=f"<@&{server_resource(interaction, 'staff_role')}>",
            )
        )
        await interaction.channel.send(output(interaction, "ad_separator"))
        await interaction.channel.send(self.hire_ad.value)
        await interaction.channel.send(
            output(interaction, "plan_line", plan=self.hire_plan.value)
        )
        await interaction.edit_original_response(content=output(interaction, "form_sent"))


class link_form(discord.ui.Modal, title="linking w. xue . . ."):
    link_ad = discord.ui.TextInput(
        label="✿❀꒱ა． ． ． ad",
        style=discord.TextStyle.paragraph,
        required=True,
        placeholder="mass here @ the candy shop!"
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await interaction.channel.edit(name='┈ㆍlink')
        await interaction.channel.send(
            output(
                interaction,
                "staff_ping",
                staff_role=f"<@&{server_resource(interaction, 'staff_role')}>",
            )
        )
        await interaction.channel.send(output(interaction, "link_separator"))
        await interaction.channel.send(self.link_ad.value)
        await interaction.channel.send(output(interaction, "link_guidance"))
        await interaction.edit_original_response(content=output(interaction, "form_sent"))
  

class ticket_menu(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        placeholder="໒꒱．what　 are　 you　 doing　 here　 ...　 ?",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label="┈┈・꒰୨୧꒱，mass", description=". . .", value="mass"),
            discord.SelectOption(label="┈┈・hire。꒱ა", description="have xue work for you", value="hire"),
            discord.SelectOption(label="┈┈・꒰୨୧꒱，link", description=". . .", value="link"),
        ],
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        if select.values[0] == "mass":
            guild = interaction.guild
            category = (
                guild.get_channel(get_server_resource(guild.id, "ticket_category"))
                if guild
                else None
            )
            if not isinstance(category, discord.CategoryChannel):
                await interaction.response.send_message(
                    get_message(
                        interaction.guild_id,
                        "missing_item_notice",
                        item="ticket category",
                    ),
                    ephemeral=True,
                )
                return
            if get_mass_status(count_n2p_channels(category), guild.id) == "closed":
                await interaction.response.send_message(
                    get_message(interaction.guild_id, "masses_closed_notice"),
                    ephemeral=True,
                )
                return
            await interaction.response.send_modal(mass_form())

        if select.values[0] == "hire":
            await interaction.response.send_modal(hire_password_form())

        if select.values[0] == "link":
            await interaction.response.send_modal(link_form())

class proof_deco_1(discord.ui.Modal, title="┈┈  new deco proof !"):
    pd_ad = discord.ui.TextInput(
        label="✿❀。。 ad",
        style=discord.TextStyle.short,
        required=True,
        placeholder="come join orchids <3"
    )
    pd_plan = discord.ui.TextInput(
        label="𓂅，plan",
        style=discord.TextStyle.short,
        required=True,
        placeholder="CY4NIDE"
    )
    pd_hirer = discord.ui.TextInput(
        label="✿❀。。employer",
        style=discord.TextStyle.short,
        required=True,
        placeholder="user id / 861086733361479720"
    )
    pd_name = discord.ui.TextInput(
        label="𓂅，name",
        style=discord.TextStyle.short,
        required=True,
        placeholder="orchids"
    )
    pd_desc = discord.ui.TextInput(
        label="✿❀。。description",
        style=discord.TextStyle.paragraph,
        required=True,
        placeholder="cute, maxi, aes"
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(
            description=output(
                interaction,
                "proof_deco_embed",
                name=self.pd_name.value,
                plan=self.pd_plan.value,
                hirer=self.pd_hirer.value,
                description=self.pd_desc.value,
            ),
            color=0x242429,
        )
        await interaction.channel.send(output(interaction, "proof_deco_spacer"))
        await interaction.channel.send(self.pd_ad.value)
        await interaction.channel.send(embed=embed)
        await interaction.channel.send(output(interaction, "spacer"))
        await interaction.channel.send(output(interaction, "proof_deco_art"))
        await interaction.channel.send(output(interaction, "spacer"))
        await interaction.edit_original_response(content=output(interaction, "proof_sent"))



class proof_partner_links(discord.ui.Modal, title="┈┈  new prtnr proof !"):
    ppl_link = discord.ui.TextInput(
        label="✿❀。。 link",
        style=discord.TextStyle.short,
        required=True,
        placeholder="https://discord.gg/St7YmwsBYB"
    )
    ppl_proof = discord.ui.TextInput(
        label="𓂅，proof",
        style=discord.TextStyle.short,
        required=True,
        placeholder="img link ^___^"
    )
    ppl_review = discord.ui.TextInput(
        label="✿❀。。rvw",
        style=discord.TextStyle.paragraph,
        required=True,
        placeholder="img link, pls!"
    )

    async def on_submit(self, interaction: discord.Interaction):
        view = proof_continue_view(
            ppl_link=self.ppl_link.value,
            ppl_proof=self.ppl_proof.value,
            ppl_rvw=self.ppl_review.value,
        )
        await interaction.response.send_message(
            output(interaction, "proof_continue_prompt"),
            ephemeral=True,
            view=view,
        )


class proof_continue_view(discord.ui.View):
    def __init__(self, ppl_link: str, ppl_proof: str, ppl_rvw: str):
        super().__init__(timeout=None)
        self.ppl_link = ppl_link
        self.ppl_proof = ppl_proof
        self.ppl_rvw = ppl_rvw

    @discord.ui.button(label="໒♡．next!", style=discord.ButtonStyle.gray)
    async def continue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            proof_partner_info(
                ppl_link=self.ppl_link,
                ppl_proof=self.ppl_proof,
                ppl_rvw=self.ppl_rvw,
            )
        )


class proof_partner_info(discord.ui.Modal, title="┈┈⠀⠀new⠀prtnr⠀proof⠀!"):
    def __init__(self, ppl_link: str, ppl_proof: str, ppl_rvw: str):
        super().__init__(title="┈┈⠀⠀new⠀prtnr⠀proof⠀!")
        self.ppl_link = ppl_link
        self.ppl_proof = ppl_proof
        self.ppl_rvw = ppl_rvw

    ppi_total = discord.ui.TextInput(
        label="✿❀。。total",
        style=discord.TextStyle.short,
        required=True,
        placeholder="350/350i"
    )
    ppi_name = discord.ui.TextInput(
        label="𓂅，name",
        style=discord.TextStyle.short,
        required=True,
        placeholder="orchids"
    )
    ppi_plan = discord.ui.TextInput(
        label="✿❀。。plan",
        style=discord.TextStyle.short,
        required=True,
        placeholder="AURUM"
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        message = output(
            interaction,
            "proof_partner_output",
            link=self.ppl_link,
            proof=self.ppl_proof,
            name=self.ppi_name.value,
            total=self.ppi_total.value,
            plan=self.ppi_plan.value,
            review=self.ppl_rvw,
        )
        await interaction.channel.send(output(interaction, "proof_partner_spacer"))
        await interaction.channel.send(message)
        await interaction.channel.send(output(interaction, "spacer"))
        await interaction.channel.send(output(interaction, "proof_partner_art"))
        await interaction.channel.send(output(interaction, "spacer"))
        await interaction.edit_original_response(content=output(interaction, "proof_sent"))


class proof_menu(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.select(
        placeholder="໒꒱．paid   completed!",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label="┈┈・꒰୨୧꒱，deco", description=". . .", value="deco"),
            discord.SelectOption(label="┈┈・pm。꒱ა", description=". . .", value="pm"),
        ],
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        if select.values[0] == "deco":
            await interaction.response.send_modal(proof_deco_1())

        if select.values[0] == "pm":
            await interaction.response.send_modal(proof_partner_links())


class run_partner_modal(discord.ui.Modal, title="┈┈⠀⠀new⠀upld⠀wait⠀!"):
    start = discord.ui.TextInput(
        label="✿❀。。start",
        style=discord.TextStyle.short,
        placeholder="what day is it?",
    )
    name = discord.ui.TextInput(
        label="𓂅，name",
        style=discord.TextStyle.short,
        placeholder="orchids",
    )
    link = discord.ui.TextInput(
        label="✿❀。。link",
        style=discord.TextStyle.short,
        placeholder="https://discord.gg/...",
    )
    plan = discord.ui.TextInput(
        label="𓂅，plan",
        style=discord.TextStyle.short,
        placeholder="C4RB0N, AURUM",
    )
    invites = discord.ui.TextInput(
        label="✿❀。。invs",
        style=discord.TextStyle.short,
        placeholder="000/350i",
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not isinstance(interaction.channel, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message(
                output(interaction, "ticket_only_notice"),
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True)
        message = output(
            interaction,
            "run_partner_output",
            name=self.name.value,
            link=self.link.value,
            start=self.start.value,
            plan=self.plan.value,
            invites=self.invites.value,
        )
        await interaction.channel.send("_ _\n_ _\n\n\n\n_ _")
        await interaction.channel.send(message)
        await interaction.channel.send(output(interaction, "spacer"))
        await interaction.channel.send(output(interaction, "divider_image_2"))
        await interaction.channel.send(output(interaction, "spacer"))
        await interaction.edit_original_response(content=output(interaction, "sent"))


class run_uploader_modal(discord.ui.Modal, title="┈┈⠀⠀new⠀upld⠀wait⠀!"):
    start = discord.ui.TextInput(
        label="✿❀。。start",
        style=discord.TextStyle.short,
        placeholder="what day is it?",
    )
    name = discord.ui.TextInput(
        label="𓂅，name",
        style=discord.TextStyle.short,
        placeholder="orchids",
    )
    link = discord.ui.TextInput(
        label="✿❀。。link",
        style=discord.TextStyle.short,
        placeholder="https://discord.gg/...",
    )
    uploads = discord.ui.TextInput(
        label="𓂅，upld",
        style=discord.TextStyle.short,
        placeholder="000/250u",
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not isinstance(interaction.channel, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message(
                output(interaction, "ticket_only_notice"),
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True)
        message = output(
            interaction,
            "run_uploader_output",
            name=self.name.value,
            link=self.link.value,
            start=self.start.value,
            uploads=self.uploads.value,
        )
        await interaction.channel.send("_ _\n_ _\n\n\n\n_ _")
        await interaction.channel.send(message)
        await interaction.channel.send(output(interaction, "spacer"))
        await interaction.channel.send(output(interaction, "divider_image_2"))
        await interaction.channel.send(output(interaction, "spacer"))
        await interaction.edit_original_response(content=output(interaction, "sent"))


class runs_menu(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        select = discord.ui.Select(
            placeholder="໒꒱．on   going   jobs!",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label="┈┈・꒰୨୧꒱，upldr",
                    description=". . .",
                    value="upldr",
                ),
                discord.SelectOption(
                    label="┈┈・prtnr。꒱ა",
                    description=". . .",
                    value="prtnr",
                ),
            ],
        )
        select.callback = self.select_run_type
        self.add_item(select)

    async def select_run_type(self, interaction: discord.Interaction) -> None:
        if interaction.data["values"][0] == "prtnr":
            await interaction.response.send_modal(run_partner_modal())
        else:
            await interaction.response.send_modal(run_uploader_modal())



# messages and embeds


@client.tree.command(
    name="lay",
    description="send a components v2 text layout",
    guild=guild_id,
)
@app_commands.describe(body="text to show in the layout")
@has_server_role("staff_role")
async def send_layout(interaction: discord.Interaction, body: str) -> None:
    if not isinstance(interaction.channel, (discord.TextChannel, discord.Thread)):
        await interaction.response.send_message(
            output(interaction, "ticket_only_notice"),
            ephemeral=True,
        )
        return
    layout = discord.ui.LayoutView(timeout=None)
    layout.add_item(
        discord.ui.Container(
            discord.ui.TextDisplay(content=body),
        )
    )
    await interaction.response.defer(ephemeral=True)
    try:
        await interaction.channel.send(view=layout)
    except discord.HTTPException as error:
        print(f"Could not send layout in channel {interaction.channel.id}: {error}")
        await interaction.edit_original_response(
            content=output(interaction, "image_send_error", error=error),
        )
        return
    await interaction.edit_original_response(content=output(interaction, "sent"))


@client.tree.command(name="embed",
                     description="໒✿꒱．send an embed",
                     guild=guild_id)
@app_commands.describe(body=" . .", 
                       image=". . .", 
                       thumbnail=". . .")
@has_server_role("staff_role") # staff role
async def send_embed(interaction: discord.Interaction, body: str, image: str = None, thumbnail: str = None):
    emb = discord.Embed(description=body, color=0x242429)
    if thumbnail:
        emb.set_thumbnail(url=thumbnail)
    if image:
        emb.set_image(url=image)
    try:
        await interaction.channel.send(embed=emb)
        await interaction.response.send_message(output(interaction, "sent"), ephemeral=True)
    except Exception as e:
        # fallback to deferred followup if immediate response fails
        try:
            await interaction.response.defer(ephemeral=True)
            await interaction.edit_original_response(
                content=output(interaction, "embed_send_error", error=str(e)),
            )
        except Exception:
            pass


@client.tree.command(name="say", 
                     description="what do you want me to say?", 
                     guild=guild_id)
@has_server_role("staff_role") # staff role
async def say(interaction: discord.Interaction, message: str):
    await interaction.channel.send(message)
    await interaction.response.send_message(output(interaction, "message_sent"), ephemeral=True)


@client.tree.command(name="img",
                     description="꒰✿。embedded img...",
                     guild=guild_id)
@has_server_role("staff_role") # staff role
@app_commands.describe(image_url="img link", body=". . .")
async def embed_image(interaction: discord.Interaction, image_url: str, body: str = None):
    """send an embedded img"""
    emb = discord.Embed(color=0x242429)
    if body:
        emb.description = body
    emb.set_image(url=image_url)
    try:
        await interaction.channel.send(embed=emb)
        await interaction.response.send_message(output(interaction, "sent"), ephemeral=True)
    except Exception as e:
        try:
            await interaction.response.defer(ephemeral=True)
            await interaction.edit_original_response(
                content=output(interaction, "image_send_error", error=str(e)),
            )
        except Exception:
            pass


@client.tree.command(name="new", 
                     description="໒♡꒱．open a ticket", 
                     guild=guild_id)
async def new(interaction: discord.Interaction):
    guild = interaction.guild
    if guild is None:
        await send_missing_item_notice(interaction, "server")
        return
    category = guild.get_channel(server_resource(interaction, "ticket_category"))
    if not isinstance(category, discord.CategoryChannel):
        await send_missing_item_notice(interaction, "ticket category")
        return

    member = interaction.user
    if not isinstance(member, discord.Member):
        await send_missing_item_notice(interaction, "server membership")
        return

    exempt_role_ids = get_server_resource_list(
        interaction.guild_id,
        "new_ticket_exempt_roles",
    )
    if (
        get_mass_status(count_n2p_channels(category), guild.id) == "closed"
        and not any(role.id in exempt_role_ids for role in member.roles)
    ):
        await interaction.response.send_message(
            output(interaction, "masses_closed_notice"),
            ephemeral=True,
        )
        try:
            await member.send(output(interaction, "closed_ticket_dm"))
        except discord.HTTPException as error:
            print(f"Could not DM closed-ticket notice to member {member.id}: {error}")
            try:
                welcome_channel = guild.get_channel(
                    server_resource(interaction, "welcome_channel")
                )
                if not isinstance(welcome_channel, discord.TextChannel):
                    print("The configured welcome channel is not a text channel.")
                    return
                await welcome_channel.send(
                    output(
                        interaction,
                        "closed_ticket_fallback",
                        member=member.mention,
                    )
                )
            except discord.HTTPException as fallback_error:
                print(
                    "Could not send closed-ticket fallback notice: "
                    f"{fallback_error}"
                )
        return

    role = guild.get_role(server_resource(interaction, "open_ticket_role"))
    channel = await guild.create_text_channel(f'tckt', category=category)
    await channel.set_permissions(member, read_messages=True, send_messages=True)
    if role:
        try:
            await member.add_roles(role)
        except discord.Forbidden:
            pass
    
    await interaction.response.send_message(
        output(interaction, "ticket_created", channel=channel.mention),
        ephemeral=True,
    )
    ticket_prompt = discord.Embed(
        colour=0x242429,
        description=output(interaction, "ticket_intro"),
    )
    ticket_prompt.set_thumbnail(
        url="https://cdn.discordapp.com/attachments/1518247846703403219/1518672339745636552/IMG_4148-removebg-preview.png?ex=6a3ac555&is=6a3973d5&hm=3f8035bfd8dce9f3f8b7603cb58ca0a424ee5dbc1d5c95a182f28fc6218bb0b2"
    )
    await channel.send(
        interaction.user.mention,
        embed=ticket_prompt,
        view=ticket_menu(),
    )
    

# massing 

    
@client.tree.command(name="acc", 
                     guild=guild_id)
@has_server_role("staff_role") # staff role
async def acc(interaction: discord.Interaction, 
              masser: discord.Member,
              name: str):
    if not await require_ticket_channel(interaction):
        return
    await interaction.response.defer(ephemeral=True)
    role = interaction.guild.get_role(server_resource(interaction, "massing_role"))
    if role is None:
        await interaction.edit_original_response(
            content=output(interaction, "roles_missing_notice")
        )
        return
    try:
        await masser.add_roles(role)
    except discord.Forbidden:
        await interaction.edit_original_response(
            content=output(interaction, "manage_roles_error")
        )
        return
    await interaction.channel.send(
        output(interaction, "mass_instructions", masser=masser.mention)
    )
    await interaction.channel.edit(
        name='┈ㆍmassㆍ' + name,
        topic=f"masser: {masser.id}",
    )
    await interaction.edit_original_response(content=output(interaction, "done"))


@client.tree.command(name="done",
                     description="congrats! you're done :)",
                     guild=guild_id)
@app_commands.choices(
    sep=[
        discord.app_commands.Choice(name="3hr", value="3hr"),
        discord.app_commands.Choice(name="4hr", value="4hr"),
        discord.app_commands.Choice(name="5hr", value="5hr"),
        discord.app_commands.Choice(name="8hr", value="8hr"),
        discord.app_commands.Choice(name="12hr", value="12hr"),
        discord.app_commands.Choice(name="24hr", value="24hr"),
    ],
    urg=[
        discord.app_commands.Choice(name="n-urg", value="n-urg"),
        discord.app_commands.Choice(name="semi-urg", value="semi-urg"),
        discord.app_commands.Choice(name="very urg", value="very urg"),
        discord.app_commands.Choice(name="ovd", value="ovd")
    ]
)

@app_commands.describe(
    sep="8h + sep is for v-urg & bypass only. . .",
)
async def done(interaction: discord.Interaction, 
               sep: str,
               urg: str):
    if not await require_ticket_channel(interaction):
        return
    if not await require_assigned_masser(interaction):
        return
    guild = interaction.guild
    channel = guild.get_channel(server_resource(interaction, "done_output_channel"))
    user = interaction.user
    old = guild.get_role(server_resource(interaction, "massing_role"))
    new = guild.get_role(server_resource(interaction, "posted_role"))
    if old is None or new is None:
        return await interaction.response.send_message(
            output(interaction, "roles_missing_notice"),
            ephemeral=True,
        )

    try:
        await user.add_roles(new)
        await user.remove_roles(old)
    except discord.Forbidden:
        return await interaction.response.send_message(
            output(interaction, "manage_roles_error"), ephemeral=True
        )
    except discord.HTTPException:
        return await interaction.response.send_message(
            output(interaction, "role_update_error"),
            ephemeral=True,
        )
    
    await interaction.response.send_message(output(interaction, "wait_for_post"))
    await channel.send(
        output(
            interaction,
            "done_output",
            staff_role=f"<@&{server_resource(interaction, 'staff_role')}>",
            masser=user.mention,
            sep=sep,
            urg=urg,
            channel=interaction.channel.mention,
        )
    )
    await interaction.channel.edit(name=f'{sep}ㆍ{urg}')


@client.tree.command(name="posted",
                    guild=guild_id)
@has_server_role("staff_role") # staff role
@app_commands.choices(
    sep=[
        discord.app_commands.Choice(name="1h", value="1h"),
        discord.app_commands.Choice(name="3h", value="3h"),
        discord.app_commands.Choice(name="4h", value="4h"),
        discord.app_commands.Choice(name="5h", value="5h"),
        discord.app_commands.Choice(name="8h", value="8h"),
        discord.app_commands.Choice(name="12h", value="12h"),
        discord.app_commands.Choice(name="24h", value="24h"),
]
)
async def posted(
    interaction: discord.Interaction,
    masser: discord.Member,
    sep: str, 
    link: str):
    if not await require_ticket_channel(interaction):
        return
    if not await require_assigned_masser(interaction):
        return
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    channel = interaction.channel
    output_channel = guild.get_channel(
        server_resource(interaction, "posted_output_channel")
    )
    await channel.edit(name="┈ㆍw4s")
    await channel.send(
        output(interaction, "posted_ticket", masser=masser.mention, link=link)
    )

    await output_channel.send(
        output(
            interaction,
            "posted_output",
            masser=masser.mention,
            sep=sep,
            link=link,
        )
    )
    await interaction.delete_original_response()


@client.tree.command(name="over",
                    guild=guild_id)
@has_server_role("staff_role") # staff role
async def over(
    interaction: discord.Interaction,
    masser: discord.Member,
    sep: str, 
    link: str):
    if not await require_ticket_channel(interaction):
        return
    if not await require_assigned_masser(interaction):
        return
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    channel = interaction.channel
    await interaction.channel.edit(name="┈ㆍdone")
    await channel.send(
        output(interaction, "over_ticket", masser=masser.mention, sep=sep, link=link)
    )
    await interaction.delete_original_response()


@client.tree.command(
    name="close",
    description="close a ticket and notify its masser",
    guild=guild_id,
)
@has_server_role("staff_role")
@app_commands.choices(
    reason=[
        app_commands.Choice(name="much", value="much"),
        app_commands.Choice(name="over", value="over"),
        app_commands.Choice(name="oops", value="oops"),
    ]
)
@app_commands.describe(
    reason="Why this ticket is being closed",
    masser="Choose a masser only when the ticket has none assigned",
)
async def close_ticket(
    interaction: discord.Interaction,
    reason: str,
    masser: discord.Member | None = None,
) -> None:
    await interaction.response.defer(ephemeral=True)

    guild = interaction.guild
    channel = interaction.channel
    if guild is None or not isinstance(channel, discord.TextChannel):
        await interaction.edit_original_response(
            content="This command must be used in a ticket channel."
        )
        return
    if channel.category_id != server_resource(interaction, "ticket_category"):
        await interaction.edit_original_response(
            content="This command must be used in a ticket channel."
        )
        return

    assigned_masser_id = ticket_masser_id(channel)
    if assigned_masser_id is not None:
        masser = guild.get_member(assigned_masser_id)
        if masser is None:
            try:
                masser = await guild.fetch_member(assigned_masser_id)
            except discord.NotFound:
                await interaction.edit_original_response(
                    content="The assigned masser is no longer in this server."
                )
                return
            except discord.HTTPException as error:
                print(
                    f"Could not resolve assigned masser {assigned_masser_id}: {error}"
                )
                await interaction.edit_original_response(
                    content="Could not look up the assigned masser. The ticket was not deleted."
                )
                return
    elif masser is None:
        await interaction.edit_original_response(
            content="No masser is assigned. Choose a masser in the `/close` command."
        )
        return

    try:
        await channel.delete(
            reason=f"Ticket manually closed ({reason}) by {interaction.user}."
        )
    except discord.Forbidden:
        await interaction.edit_original_response(
            content="I do not have permission to delete this ticket channel."
        )
        return
    except discord.HTTPException as error:
        print(f"Could not delete ticket channel {channel.id}: {error}")
        await interaction.edit_original_response(
            content="Discord could not delete this ticket channel. Please try again."
        )
        return

    try:
        await masser.send(output(interaction, f"close_{reason}"))
    except discord.Forbidden:
        await interaction.edit_original_response(
            content=f"Ticket deleted, but I could not DM {masser.mention}. Their DMs may be closed."
        )
        return
    except discord.HTTPException as error:
        print(f"Could not DM masser {masser.id} about ticket {channel.id}: {error}")
        await interaction.edit_original_response(
            content=f"Ticket deleted, but Discord could not deliver the DM to {masser.mention}."
        )
        return

    await interaction.edit_original_response(
        content=f"Ticket deleted and closure notice sent to {masser.mention}."
    )


@client.tree.command(name="invs", 
                     description="꒰ ✿❀ ꒱． ． how many invites?", 
                     guild=guild_id)
@has_server_role("posted_role")
async def invs(interaction: discord.Interaction, 
               invs: int, 
               portals: int, 
               sep: int,
              desc: str):
    if not await require_ticket_channel(interaction):
        return
    if not await require_assigned_masser(interaction):
        return
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    channel = guild.get_channel(
        server_resource(interaction, "invs_output_channel")
    )
    user = interaction.user
    await channel.send(
        output(
            interaction,
            "invs_output",
            masser=user.mention,
            invs=invs,
            sep=sep,
            portals=portals,
            desc=desc,
        )
    )
    await interaction.edit_original_response(content=output(interaction, "invs_complete"))
    await asyncio.sleep(5)
    try:
        await interaction.channel.delete()
    except Exception as e:
        print(f'Failed to delete invs channel: {e}')


@client.tree.command(name="her",
                    description="꒰ 𐙚 ୭． ．checkpoint.",
                    guild=guild_id)
async def her(interaction: discord.Interaction, 
              confess: str):
    channel = interaction.guild.get_channel(
        server_resource(interaction, "her_output_channel")
    )
    user = interaction.user.mention
    await channel.send(
        output(interaction, "checkpoint_output", member=user, confession=confess)
    )
    await interaction.response.send_message(
        output(interaction, "checkpoint_reply"),
        ephemeral=True,
    )


# paids, proofs, waitlists

@client.tree.command(name="proof", 
                     description="┈┈⠀finished!", 
                     guild=guild_id)
async def proof(interaction: discord.Interaction):
    await interaction.response.send_message(
        output(interaction, "menu_prompt"),
        view=proof_menu(),
        ephemeral=True,
    )


@client.tree.command(
    name="runs",
    description="໒꒱．post a currently ongoing run",
    guild=guild_id,
)
@has_server_role("staff_role")
async def runs(interaction: discord.Interaction) -> None:
    await interaction.response.send_message(
        output(interaction, "menu_prompt"),
        view=runs_menu(),
        ephemeral=True,
    )


@client.tree.command(name="counts",
                     description="໒♡꒱．countss w2p or n2p tickets!",
                     guild=guild_id)
@has_server_role("staff_role")
async def counts(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    guild = interaction.guild
    if guild is None:
        await send_missing_item_notice(interaction, "server")
        return

    category = guild.get_channel(server_resource(interaction, "ticket_category"))
    status_channel = guild.get_channel(server_resource(interaction, "status_channel"))
    mass_channel = guild.get_channel(
        server_resource(interaction, "mass_status_channel")
    )

    if not isinstance(category, discord.CategoryChannel):
        await send_missing_item_notice(interaction, "category")
        return

    if not isinstance(status_channel, discord.VoiceChannel):
        await send_missing_item_notice(interaction, "status channel")
        return

    if not isinstance(mass_channel, discord.VoiceChannel):
        await send_missing_item_notice(interaction, "mass status channel")
        return

    text_channels = [
        channel
        for channel in category.channels
        if isinstance(channel, discord.TextChannel)
    ]
    w2p_count = sum("w2p" in channel.name.lower() for channel in text_channels)
    n2p_count = count_n2p_channels(category)

    new_name = f"🦷꒱，{w2p_count}w : {n2p_count}n 𓂃"
    mass_name = f"mass: {get_mass_status(n2p_count, guild.id)}。。。꒰ঌ"

    try:
        await status_channel.edit(name=new_name)
        await mass_channel.edit(name=mass_name)
    except discord.Forbidden:
        await interaction.edit_original_response(
            content=output(interaction, "counts_permission_error")
        )
        return
    except discord.HTTPException as error:
        print(f"Discord could not update the counts status channels: {error}")
        await interaction.edit_original_response(
            content=output(interaction, "counts_update_error")
        )
        return

    try:
        reminders_sent, history_errors, send_errors = await send_w2p_reminders(
            guild,
            text_channels,
        )
    except discord.Forbidden:
        await interaction.edit_original_response(
            content=output(interaction, "counts_audit_error")
        )
        return
    except discord.HTTPException as error:
        print(f"Discord could not provide the channel audit log: {error}")
        await interaction.edit_original_response(
            content=output(interaction, "counts_audit_error")
        )
        return

    result = output(
        interaction,
        "counts_success",
        amount=reminders_sent,
        mass_link=f"https://discord.com/channels/{guild.id}/{mass_channel.id}",
        status_link=f"https://discord.com/channels/{guild.id}/{status_channel.id}",
    )
    if history_errors or send_errors:
        result += "\n" + output(
            interaction,
            "counts_partial_warning",
            history_errors=history_errors,
            send_errors=send_errors,
        )
    await interaction.edit_original_response(content=result)


@client.tree.command(name="waits", 
                     description="໒꒰୨୧꒱ა，new for the waitlist!", 
                     guild=guild_id)
@has_server_role("staff_role")
async def waits(interaction: discord.Interaction, 
               line: int, 
               name: str, 
               link: str, 
               hirer: discord.Member):
    channel = interaction.channel
    await channel.send(
        output(
            interaction,
            "waitlist_output",
            line=line,
            name=name,
            link=link,
            hirer=hirer.mention,
        )
    )
    await channel.send(output(interaction, "spacer"))
    await channel.send(output(interaction, "waitlist_separator"))
    await channel.send(output(interaction, "spacer"))
    await interaction.response.send_message(output(interaction, "message_sent"), ephemeral=True)


@client.tree.command(
    name="setup",
    description="Customize the bot's output messages for this server.",
    guild=guild_id,
)
async def setup(interaction: discord.Interaction):
    if interaction.guild_id is None:
        await interaction.response.send_message(
            get_message(None, "setup_guild_only"),
            ephemeral=True,
        )
        return
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            get_message(interaction.guild_id, "setup_admin_only"),
            ephemeral=True,
        )
        return
    await interaction.response.send_message(
        get_message(
            interaction.guild_id,
            "setup_start",
            user=interaction.user.mention,
        ),
        view=message_setup_view(interaction.user.id, interaction.guild_id),
        ephemeral=True,
    )

client.run(bot_token)