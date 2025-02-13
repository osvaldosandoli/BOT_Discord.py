import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import os
import asyncio

from collections import deque

# Caminho relativo para o ffmpeg dentro do projeto
FFMPEG_PATH = os.path.join(os.getcwd(), "ffmpeg", "bin", "ffmpeg.exe")

# Verifica se o FFMPEG realmente existe no local esperado
if not os.path.exists(FFMPEG_PATH):
    raise FileNotFoundError(f"FFmpeg não encontrado em: {FFMPEG_PATH}")
else:
    print('FFmpeg encontrado!')

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Configurações do youtube_dl
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'  # IPv4
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

# Fila de músicas
music_queue = deque()

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, executable=FFMPEG_PATH, **ffmpeg_options), data=data)

@bot.event
async def on_ready():
    print(f'Bot {bot.user} está online!')

@bot.command(name='join', help='Faz o bot entrar no canal de voz')
async def join(ctx):
    if not ctx.message.author.voice:
        await ctx.send(f'{ctx.message.author.name} não está em um canal de voz!')
        return

    channel = ctx.message.author.voice.channel
    await channel.connect()

@bot.command(name='leave', help='Faz o bot sair do canal de voz')
async def leave(ctx):
    if ctx.voice_client:
        await ctx.guild.voice_client.disconnect()
        await ctx.send('Desconectado do canal de voz.')

@bot.command(name='play', help='Toca uma música do YouTube')
async def play(ctx, url):
    # Verifica se o usuário está em um canal de voz
    if not ctx.author.voice:
        await ctx.send('Você precisa estar em um canal de voz para tocar música!')
        return

    # Verifica se o bot já está conectado, se não estiver, ele entra
    if not ctx.voice_client:
        try:
            await ctx.author.voice.channel.connect()
        except discord.errors.ClientException as e:
            await ctx.send(f'Erro ao conectar ao canal de voz: {e}')
            return

    async with ctx.typing():
        player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
        
        # Adiciona a música na fila
        music_queue.append(player)

        if not ctx.voice_client.is_playing():
            await play_next(ctx)

    await ctx.send(f'Agora tocando: {player.title}')

# Função para tocar a próxima música da fila
@bot.command(name='play_next', help='Next')
# Função para tocar a próxima música da fila
async def play_next(ctx):
    if len(music_queue) > 0:
        player = music_queue.popleft()

        # Verifique se o bot está tocando algo antes de tentar tocar a próxima música
        if not ctx.voice_client.is_playing():
            ctx.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop) if e is None else None)
            await ctx.send(f'Agora tocando: {player.title}')
        else:
            # Caso esteja tocando, apenas adicione o player de volta à fila
            music_queue.appendleft(player)
            await ctx.send("O bot já está tocando. A música será retomada assim que a atual terminar.")
    else:
        await ctx.send("Não há mais músicas na fila.")


@bot.command(name='pause', help='Pausa a música atual')
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send('Música pausada.')

@bot.command(name='resume', help='Continua a música pausada')
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send('Música continuada.')

@bot.command(name='stop', help='Para a música atual')
async def stop(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send('Música parada.')

@bot.command(name='up', help='Aumenta o volume para o máximo')
async def up(ctx):
    if ctx.voice_client and ctx.voice_client.source:
        ctx.voice_client.source.volume = 1.0  # Define o volume para o máximo
        await ctx.send("🔊 Volume no máximo!")
    else:
        await ctx.send("❌ O bot não está tocando nada no momento.")

@bot.command(name='down', help='Aumenta o volume para o máximo')
async def down(ctx):
    if ctx.voice_client and ctx.voice_client.source:
        ctx.voice_client.source.volume = 0  # Zera o volume
        await ctx.send("❌ Bot mutado!")
    else:
        await ctx.send("❌ O bot não está tocando nada no momento.")

@bot.command(name='midV', help='Aumenta o volume para o máximo')
async def midV(ctx):
    if ctx.voice_client and ctx.voice_client.source:
        ctx.voice_client.source.volume = 0.5 
        await ctx.send("🔊 Volume normal!")
    else:
        await ctx.send("❌ O bot não está tocando nada no momento.")

bot.run('MTMzODM1MjEwNzA2OTI0NzU3MQ.Gt07f2.vLc9JWf4BE2tOidVfOrPtMxgKaArqPs7h9d7og')
