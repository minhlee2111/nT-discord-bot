import discord
from discord.ext import commands
import yt_dlp
import asyncio
import lyricsgenius
import os

# --------------------------------------
# CONFIG
# --------------------------------------
PREFIXES = ["-", "!"]
TOKEN =   # sửa token
WELCOME_CHANNEL_ID =     # sửa ID channel
LEAVE_CHANNEL_ID =  # sửa ID channel
GENIUS_API = "YOUR_GENIUS_API_KEY"

genius = lyricsgenius.Genius(GENIUS_API)

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIXES, intents=intents)

ytdl_opts = {
    "format": "bestaudio/best",
    "quiet": True,
    "extract_flat": False
}
ytdl = yt_dlp.YoutubeDL(ytdl_opts)

ffmpeg_opts = {
    "options": "-vn"
}

queues = {}       # queue theo server
volumes = {}      # volume theo server


# --------------------------------------
# HELP COMMAND
# --------------------------------------
@bot.command()
async def help(ctx):
    embed = discord.Embed(
        title="📘 Lara Bot Commands",
        description="Danh sách lệnh đầy đủ",
        color=discord.Color.blue()
    )

    embed.add_field(name="🔧 Utility", value="""
`-ping` / `!ping` → xem độ trễ  
`-support` → server hỗ trợ  
`-help` / `!help` → xem lệnh
    """, inline=False)

    embed.add_field(name="🎵 Music", value="""
`-play <song>` | `-p <song>`  
`-stop`  
`-skip`  
`-queue`  
`-playlist <url>`  
`-lyrics <song>`  
`-volume <0-100>` | `-v <num>`  
`-join`
    """, inline=False)

    embed.add_field(name="🛡 Moderation", value="""
`-kick @user`  
`-ban @user`  
`-mute @user`  
`-unmute @user`  
`-warn @user <reason>`  
`-slowmode <sec>`  
`-lock`  
`-unlock`  
`-clear <num>`
    """, inline=False)

    await ctx.send(embed=embed)


# --------------------------------------
# UTILITY COMMANDS
# --------------------------------------
@bot.command()
async def ping(ctx):
    await ctx.send(f"Pong! `{round(bot.latency * 1000)}ms`")


@bot.command()
async def support(ctx):
    await ctx.send(f"🔗 Support server: {SUPPORT_SERVER}")


# --------------------------------------
# MUSIC FUNCTIONS
# --------------------------------------
async def play_next(ctx):
    guild = ctx.guild.id
    if queues[guild]:
        url = queues[guild].pop(0)
        await play_song(ctx, url)


async def play_song(ctx, url):
    guild = ctx.guild.id

    if guild not in volumes:
        volumes[guild] = 1.0

    vc = ctx.voice_client
    if not vc:
        vc = await ctx.author.voice.channel.connect()

    data = ytdl.extract_info(url, download=False)
    audio_url = data["url"]
    title = data["title"]

    source = discord.FFmpegPCMAudio(audio_url, **ffmpeg_opts)
    source = discord.PCMVolumeTransformer(source, volume=volumes[guild])

    vc.play(
        source,
        after=lambda _: asyncio.run_coroutine_threadsafe(
            play_next(ctx), bot.loop)
    )

    await ctx.send(f"🎶 Đang phát: **{title}**")


# --------------------------------------
# MUSIC COMMANDS
# --------------------------------------
@bot.command(aliases=["p"])
async def play(ctx, *, search):
    guild = ctx.guild.id

    if guild not in queues:
        queues[guild] = []

    vc = ctx.voice_client

    if not vc:
        await ctx.invoke(join)

    # Nếu bot đang phát nhạc → add queue
    if vc and vc.is_playing():
        queues[guild].append(search)
        return await ctx.send("📥 Đã thêm vào hàng đợi!")

    await play_song(ctx, search)


@bot.command()
async def join(ctx):
    if ctx.author.voice:
        await ctx.author.voice.channel.connect()
        await ctx.send("🟢 Đã vào voice!")
    else:
        await ctx.send("Bạn phải vào voice trước!")


@bot.command()
async def stop(ctx):
    guild = ctx.guild.id
    queues[guild] = []
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("⛔ Đã dừng và xóa queue!")


@bot.command()
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("⏭ Đã skip!")
    else:
        await ctx.send("Không có bài nào đang phát.")


@bot.command()
async def queue(ctx):
    guild = ctx.guild.id

    if guild not in queues or len(queues[guild]) == 0:
        return await ctx.send("Queue trống!")

    text = "\n".join(
        [f"{i+1}. {song}" for i, song in enumerate(queues[guild])])
    await ctx.send(f"📜 **Queue:**\n{text}")


@bot.command()
async def playlist(ctx, *, url):
    data = ytdl.extract_info(url, download=False)
    guild = ctx.guild.id

    for song in data["entries"]:
        queues[guild].append(f"https://youtube.com/watch?v={song['id']}")

    await ctx.send(f"📚 Đã thêm **{len(data['entries'])} bài** vào queue!")

    if not ctx.voice_client.is_playing():
        await play_song(ctx, queues[guild].pop(0))


@bot.command()
async def lyrics(ctx, *, song_name):
    song = genius.search_song(song_name)
    if song:
        await ctx.send(f"🎤 **Lyrics:**\n{song.lyrics[:1800]}")
    else:
        await ctx.send("Không tìm thấy lyrics!")


@bot.command(aliases=["v"])
async def volume(ctx, amount: int):
    guild = ctx.guild.id

    if amount < 0 or amount > 100:
        return await ctx.send("Nhập số từ **0–100**")

    volumes[guild] = amount / 100

    if ctx.voice_client and ctx.voice_client.source:
        ctx.voice_client.source.volume = volumes[guild]

    await ctx.send(f"🔊 Volume đặt thành **{amount}%**")


# --------------------------------------
# WELCOME & LEAVE
# --------------------------------------
@bot.event
async def on_member_join(member):
    channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if channel:
        await channel.send(f"🎉 Chào mừng {member.mention} đến với server!")


@bot.event
async def on_member_remove(member):
    channel = bot.get_channel(LEAVE_CHANNEL_ID)
    if channel:
        await channel.send(f"👋 {member.name} đã rời server.")


# --------------------------------------
# MODERATION
# --------------------------------------
warnings = {}


@bot.command()
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason="Không có lý do"):
    warnings[member.id] = warnings.get(member.id, 0) + 1
    await ctx.send(f"⚠ {member.mention} bị warn! Tổng: **{warnings[member.id]}**")


@bot.command()
async def mute(ctx, member: discord.Member):
    role = discord.utils.get(ctx.guild.roles, name="Muted")
    if not role:
        role = await ctx.guild.create_role(name="Muted")
        for ch in ctx.guild.channels:
            await ch.set_permissions(role, send_messages=False, speak=False)

    await member.add_roles(role)
    await ctx.send(f"🔇 {member.mention} đã bị mute!")


@bot.command()
async def unmute(ctx, member: discord.Member):
    role = discord.utils.get(ctx.guild.roles, name="Muted")
    await member.remove_roles(role)
    await ctx.send(f"🔊 {member.mention} đã được unmute!")


@bot.command()
async def lock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send("🔒 Kênh đã khóa!")


@bot.command()
async def unlock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send("🔓 Kênh đã mở khóa!")


@bot.command()
async def clear(ctx, amount: int):
    await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"🧹 Đã xóa {amount} tin!", delete_after=3)


# --------------------------------------
# START BOT
# --------------------------------------
bot.run(TOKEN)

