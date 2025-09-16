import os
import json
import asyncio
import datetime
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv  # 추가

# .env 로드 (프로젝트 루트의 .env 파일 자동 탐색)
load_dotenv()

DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")
DEFAULT_TZ = ZoneInfo("Asia/Seoul")
CHECK_TIME = datetime.time(hour=0, minute=5, tzinfo=DEFAULT_TZ)  # 매일 00:05(KST)
REMINDER_TIME_1H = datetime.time(hour=23, minute=5, tzinfo=DEFAULT_TZ)   # 매일 23:05(KST)
REMINDER_TIME_30M = datetime.time(hour=23, minute=35, tzinfo=DEFAULT_TZ) # 매일 23:35(KST)
REMINDER_TIME_10M = datetime.time(hour=23, minute=55, tzinfo=DEFAULT_TZ) # 매일 23:55(KST)

def today_str(tz: ZoneInfo = DEFAULT_TZ) -> str:
    return datetime.datetime.now(tz).date().isoformat()

def date_str_for(dt: datetime.datetime) -> str:
    return dt.date().isoformat()

def yesterday_str(tz: ZoneInfo = DEFAULT_TZ) -> str:
    return (datetime.datetime.now(tz).date() - datetime.timedelta(days=1)).isoformat()

def is_image_attachment(att: discord.Attachment) -> bool:
    if att.content_type and att.content_type.startswith("image/"):
        return True
    name = att.filename.lower()
    return name.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".heic", ".heif"))

class DataStore:
    def __init__(self, path: str):
        self.path = path
        self._lock = asyncio.Lock()
        self.data = {"guilds": {}}

    async def load(self):
        if not os.path.exists(self.path):
            await self.save()
            return
        async with self._lock:
            with open(self.path, "r", encoding="utf-8") as f:
                try:
                    self.data = json.load(f)
                except json.JSONDecodeError:
                    self.data = {"guilds": {}}

    async def save(self):
        async with self._lock:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)

    def _g(self, guild_id: int) -> dict:
        g = self.data["guilds"].setdefault(str(guild_id), {
            "channel_id": None,
            "participants": [],
            "debt": {},          # user_id(str) -> int(원)
            "submissions": {}    # date(YYYY-MM-DD) -> [user_id(str), ...]
        })
        return g

    async def set_channel(self, guild_id: int, channel_id: int):
        g = self._g(guild_id)
        g["channel_id"] = channel_id
        await self.save()

    def get_channel(self, guild_id: int) -> int | None:
        return self._g(guild_id).get("channel_id")

    async def join(self, guild_id: int, user_id: int):
        g = self._g(guild_id)
        uid = str(user_id)
        if uid not in g["participants"]:
            g["participants"].append(uid)
        g["debt"].setdefault(uid, 0)
        await self.save()

    async def leave(self, guild_id: int, user_id: int):
        g = self._g(guild_id)
        uid = str(user_id)
        if uid in g["participants"]:
            g["participants"].remove(uid)
        await self.save()

    def is_participant(self, guild_id: int, user_id: int) -> bool:
        return str(user_id) in self._g(guild_id)["participants"]

    async def mark_submission(self, guild_id: int, date: str, user_id: int):
        g = self._g(guild_id)
        day = g["submissions"].setdefault(date, [])
        uid = str(user_id)
        if uid not in day:
            day.append(uid)
            await self.save()

    def has_submitted(self, guild_id: int, date: str, user_id: int) -> bool:
        g = self._g(guild_id)
        return str(user_id) in g["submissions"].get(date, [])

    async def apply_penalties_for_date(self, guild_id: int, date: str) -> list[tuple[str, int]]:
        """전날(date)에 인증 안 한 참가자들에게 1000원씩 벌점 부과."""
        g = self._g(guild_id)
        participants = set(g["participants"])
        submitted = set(g["submissions"].get(date, []))
        missed = participants - submitted
        changed = []
        for uid in missed:
            g["debt"][uid] = g["debt"].get(uid, 0) + 1000
            changed.append((uid, g["debt"][uid]))
        await self.save()
        return changed

    def get_debt(self, guild_id: int, user_id: int) -> int:
        g = self._g(guild_id)
        return g["debt"].get(str(user_id), 0)

    def leaderboard(self, guild_id: int, limit: int = 10) -> list[tuple[str, int]]:
        g = self._g(guild_id)
        items = list(g["debt"].items())
        items.sort(key=lambda x: x[1], reverse=True)
        return items[:limit]

    def total_debt(self, guild_id: int) -> int:
        g = self._g(guild_id)
        return sum(g["debt"].values())

    def pending_for_date(self, guild_id: int, date: str) -> list[str]:
        """date(YYYY-MM-DD)에 아직 인증하지 않은 참가자 user_id(str) 목록"""
        g = self._g(guild_id)
        participants = set(g["participants"])
        submitted = set(g["submissions"].get(date, []))
        return sorted(participants - submitted)

store = DataStore(DATA_FILE)

intents = discord.Intents.default()
intents.message_content = True  # 인증 메시지/첨부 확인
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await store.load()
    if not daily_check.is_running():
        daily_check.start()
    # 리마인더 3종 시작
    if not reminder_check_1h.is_running():
        reminder_check_1h.start()
    if not reminder_check_30m.is_running():
        reminder_check_30m.start()
    if not reminder_check_10m.is_running():
        reminder_check_10m.start()
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

@tasks.loop(time=CHECK_TIME)
async def daily_check():
    # 전날 인증 누락자 벌점 처리
    for guild in bot.guilds:
        ymd = yesterday_str(DEFAULT_TZ)
        changed = await store.apply_penalties_for_date(guild.id, ymd)
        if not changed:
            continue
        channel_id = store.get_channel(guild.id)
        if channel_id:
            channel = guild.get_channel(channel_id) or await guild.fetch_channel(channel_id)
            try:
                lines = []
                for uid, debt in changed:
                    member = guild.get_member(int(uid)) or await guild.fetch_member(int(uid))
                    name = member.display_name if member else f"User {uid}"
                    lines.append(f"- {name}: 누락 1회 → 현재 벌점 {debt}원")
                msg = f"[{ymd}] 인증 누락 정산 결과\n" + "\n".join(lines)
                await channel.send(msg)
            except discord.HTTPException:
                pass

# 공통 리마인더 발송 함수
async def _send_pending_reminder(label: str):
    date = today_str(DEFAULT_TZ)
    for guild in bot.guilds:
        channel_id = store.get_channel(guild.id)
        if not channel_id:
            continue
        pending = store.pending_for_date(guild.id, date)
        if not pending:
            continue
        channel = guild.get_channel(channel_id) or await guild.fetch_channel(channel_id)
        mentions = " ".join(f"<@{uid}>" for uid in pending)
        msg = (
            f"⏰ 벌점 부과 {label} 알림 ({date})\n"
            f"{mentions}\n"
            "아직 인증하지 않았습니다. 자정까지 인증하지 않으면 00:05에 1000원 벌점이 부과됩니다."
        )
        try:
            await channel.send(msg)
        except discord.HTTPException:
            pass

# 1시간 전(23:05)
@tasks.loop(time=REMINDER_TIME_1H)
async def reminder_check_1h():
    await _send_pending_reminder("1시간 전")

# 30분 전(23:35)
@tasks.loop(time=REMINDER_TIME_30M)
async def reminder_check_30m():
    await _send_pending_reminder("30분 전")

# 10분 전(23:55)
@tasks.loop(time=REMINDER_TIME_10M)
async def reminder_check_10m():
    await _send_pending_reminder("10분 전")

@bot.event
async def on_message(message: discord.Message):
    # 봇 자신/DM/시스템 메시지 무시
    if message.author.bot or not message.guild:
        return

    # 명령어 처리 먼저
    await bot.process_commands(message)

    # 인증 채널에서 이미지 첨부 시 인증 처리
    channel_id = store.get_channel(message.guild.id)
    if not channel_id or message.channel.id != channel_id:
        return

    # 참가자만 인증 인정
    if not store.is_participant(message.guild.id, message.author.id):
        return

    has_image = any(is_image_attachment(att) for att in message.attachments)
    if not has_image:
        return

    date = today_str(DEFAULT_TZ)
    if store.has_submitted(message.guild.id, date, message.author.id):
        return

    await store.mark_submission(message.guild.id, date, message.author.id)
    try:
        await message.add_reaction("✅")
        await message.reply(f"{message.author.mention} 오늘 인증 완료! ({date})", mention_author=False)
    except discord.HTTPException:
        pass

@bot.command(name="study-channel")
@commands.has_permissions(manage_guild=True)
async def study_channel(ctx: commands.Context, channel: discord.TextChannel):
    await store.set_channel(ctx.guild.id, channel.id)
    await ctx.reply(f"인증 채널이 {channel.mention} 로 설정되었습니다.", mention_author=False)

@study_channel.error
async def study_channel_error(ctx: commands.Context, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.reply("이 명령은 서버 관리 권한이 필요합니다.", mention_author=False)
    else:
        await ctx.reply("사용법: !study-channel #인증채널", mention_author=False)

@bot.command(name="study-join")
async def study_join(ctx: commands.Context):
    await store.join(ctx.guild.id, ctx.author.id)
    await ctx.reply(f"{ctx.author.mention} 스터디에 참가되었습니다. 매일 인증 채널에 사진을 올리세요!", mention_author=False)

@bot.command(name="study-leave")
async def study_leave(ctx: commands.Context):
    await store.leave(ctx.guild.id, ctx.author.id)
    await ctx.reply(f"{ctx.author.mention} 스터디에서 제외되었습니다.", mention_author=False)

@bot.command(name="study-status")
async def study_status(ctx: commands.Context, member: discord.Member | None = None):
    member = member or ctx.author
    debt = store.get_debt(ctx.guild.id, member.id)
    await ctx.reply(f"{member.display_name} 현재 벌점: {debt}원", mention_author=False)

@bot.command(name="study-check")
async def study_check(ctx: commands.Context, member: discord.Member | None = None):
    """지정한 사용자(없으면 본인)의 오늘 인증 여부 확인"""
    member = member or ctx.author
    date = today_str(DEFAULT_TZ)
    done = store.has_submitted(ctx.guild.id, date, member.id)
    msg = (
        f"{member.display_name}은(는) 오늘({date}) 인증을 완료했습니다."
        if done
        else f"{member.display_name}은(는) 오늘({date}) 아직 인증하지 않았습니다."
    )
    await ctx.reply(msg, mention_author=False)

@bot.command(name="study-leaderboard")
async def study_leaderboard(ctx: commands.Context):
    top = store.leaderboard(ctx.guild.id, limit=10)
    if not top:
        await ctx.reply("아직 집계된 기록이 없습니다.", mention_author=False)
        return
    lines = []
    for i, (uid, debt) in enumerate(top, start=1):
        try:
            member = ctx.guild.get_member(int(uid)) or await ctx.guild.fetch_member(int(uid))
            name = member.display_name if member else f"User {uid}"
        except discord.HTTPException:
            name = f"User {uid}"
        lines.append(f"{i}. {name} — {debt}원")
    total = store.total_debt(ctx.guild.id)
    await ctx.reply("벌점 랭킹 Top 10\n" + "\n".join(lines) + f"\n총 벌점: {total}원", mention_author=False)

@bot.command(name="study-help")
async def study_help(ctx: commands.Context):
    msg = (
        "공부봇 사용법\n"
        "- !study-channel #채널: 인증 채널 설정(관리자)\n"
        "- !study-join: 스터디 참가\n"
        "- !study-leave: 스터디 탈퇴\n"
        "- !study-status [@유저]: 현재 벌점 확인\n"
        "- !study-check [@유저]: 오늘 인증 여부 확인\n"
        "- !study-leaderboard: 벌점 랭킹\n"
        "인증은 설정된 채널에 이미지(사진) 올리면 자동으로 처리됩니다.\n"
        "매일 00:05(KST)에 전날 미인증자에게 1000원 벌점이 부과됩니다."
    )
    await ctx.reply(msg, mention_author=False)

def main():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("환경변수 DISCORD_TOKEN 을 설정하세요.")
    bot.run(token)

if __name__ == "__main__":
    main()                # 변경


