import random
import discord
from discord.ext import commands, tasks
import yt_dlp as youtube_dl
import os
import asyncio
from datetime import time, timezone, timedelta
import datetime
from dotenv import load_dotenv

from collections import deque

fuso_brasilia = timezone(timedelta(hours=-3))  # Fuso horário de Brasília (UTC-3)
horario_exec = time(hour=0, minute=0, second=0, tzinfo=fuso_brasilia)  # Horário de execução (00:00)

# Caminho relativo para o ffmpeg dentro do projeto
FFMPEG_PATH = os.path.join(os.getcwd(), "ffmpeg", "bin", "ffmpeg.exe")

# Verifica se o FFMPEG realmente existe no local esperado
if not os.path.exists(FFMPEG_PATH):
    raise FileNotFoundError(f"FFmpeg não encontrado em: {FFMPEG_PATH}")
else:
    print('FFmpeg encontrado!')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # ADICIONE ESTA LINHA

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

# Inicia a tarefa assim que o bot estiver pronto
@bot.event
async def on_ready():
    print(f'Bot {bot.user} está online!')
    if not rotate_joker_task.is_running():
        rotate_joker_task.start()
        print("Task do Joker iniciada!")


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
        print(music_queue)

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

@bot.command(name='down', help='Diminui o volume')
async def down(ctx):
    if ctx.voice_client and ctx.voice_client.source:
        ctx.voice_client.source.volume = 0.2  # Diminui o volume
        await ctx.send("❌ Volume baixo!")
    else:
        await ctx.send("❌ O bot não está tocando nada no momento.")

@bot.command(name='midV', help='Volume normal')
async def midV(ctx):
    if ctx.voice_client and ctx.voice_client.source:
        ctx.voice_client.source.volume = 0.5 
        await ctx.send("🔊 Volume normal!")
    else:
        await ctx.send("❌ O bot não está tocando nada no momento.")

@bot.command(name='addcargo', help='Adiciona um cargo a um usuário. Uso: !addcargo @usuario NomeDoCargo')
@commands.has_permissions(manage_roles=True) # Apenas usuários com permissão podem usar
async def add_role(ctx, member: discord.Member, *, role_name: str):
    # Procura o cargo no servidor pelo nome
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    
    if role is None:
        await ctx.send(f"❌ O cargo '{role_name}' não foi encontrado.")
        return

    try:
        # Adiciona o cargo ao membro mencionado
        await member.add_roles(role)
        await ctx.send(f"✅ O cargo **{role.name}** foi adicionado com sucesso a {member.mention}!")
    except discord.Forbidden:
        await ctx.send("❌ Eu não tenho permissão para adicionar esse cargo (verifique a hierarquia).")
    except Exception as e:
        await ctx.send(f"❌ Ocorreu um erro: {e}")

# Tratamento de erro caso o usuário não tenha permissão para usar o comando
@add_role.error
async def add_role_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Você não tem permissão para gerenciar cargos.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Uso correto: `!addcargo @usuario NomeDoCargo`")


# Nome do cargo que será alternado
JOKER_ROLE_NAME = "joker"

async def run_rotation(guild):
    """Função auxiliar para rodar a lógica em um servidor específico"""
    role = discord.utils.get(guild.roles, name=JOKER_ROLE_NAME)
    
    if role is None:
        print(f"⚠️ Cargo '{JOKER_ROLE_NAME}' não encontrado no servidor {guild.name}.")
        return

    # 1. Remover o cargo de quem já tem
    for member in role.members:
        try:
            await member.remove_roles(role)
            print(f"✅ Cargo removido de {member.name}")
        except discord.Forbidden:
            print(f"❌ Erro de Hierarquia: O cargo '{JOKER_ROLE_NAME}' está acima do meu cargo em {guild.name}!")
        except Exception as e:
            print(f"❌ Erro ao remover cargo em {guild.name}: {e}")

    # 2. Escolher um novo usuário aleatório (que não seja bot)
    human_members = [m for m in guild.members if not m.bot]
    
    if human_members:
        new_dictator = random.choice(human_members)
        try:
            await new_dictator.add_roles(role)
            
            # 3. Anúncio no canal
            channel = guild.system_channel or next((x for x in guild.text_channels if x.permissions_for(guild.me).send_messages), None)
            if channel:
                embed = discord.Embed(
                    title="🤡 NOVA DITADURA ESTABELECIDA!",
                    description=f"Curvem-se! {new_dictator.mention} é o novo **Joker**!",
                    color=0xFF0000
                )
                embed.set_thumbnail(url=new_dictator.display_avatar.url)
                await channel.send(content="@everyone", embed=embed)
            print(f"✅ {new_dictator.name} promovido a Joker em {guild.name}")
        except discord.Forbidden:
            print(f"❌ Sem permissão para adicionar o cargo em {guild.name}. Verifique a hierarquia!")
        except Exception as e:
            print(f"❌ Erro ao adicionar cargo: {e}")

# Task automática
@tasks.loop(time=horario_exec)
async def rotate_joker_task():
    if not bot.is_ready():
        return
    for guild in bot.guilds:
        await run_rotation(guild)

#################################### INCIO METODOS AUXILIARES ####################################

# Comando de Teste (Agora foca APENAS no servidor onde foi enviado)

# @bot.command(name='rodar_joker')
# @commands.has_permissions(administrator=True)
# async def force_rotate(ctx):
#     await ctx.send(f"🔄 Iniciando rotação forçada no servidor: **{ctx.guild.name}**...")
#     await run_rotation(ctx.guild)
#     await ctx.send("✅ Processo concluído. Verifique o console para detalhes.")

# @bot.command(name='listarcargos')
# @commands.has_permissions(manage_roles=True)
# async def list_roles(ctx):
#     # Lista todos os nomes de cargos, ignorando o @everyone
#     roles = [role.name for role in ctx.guild.roles if role.name != "@everyone"]
    
#     if roles:
#         lista = "\n".join(roles)
#         await ctx.send(f"**Cargos disponíveis neste servidor:**\n```\n{lista}\n```")
#     else:
#         await ctx.send("Não encontrei cargos neste servidor.")

#################################### FIM METODOS AUXILIARES ####################################
load_dotenv()
bot.run(os.getenv('KeyBot')) ## TOKEN DO BOT
