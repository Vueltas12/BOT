import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Select
import sqlite3
from datetime import datetime

# Configuración
TOKEN = "MTM3NzA2MDY0NTkxMjA1NTgwOA.GudCQQ.PmgpLKGCtHehfbx2wOE3b-GwB0q1r2u-cmmJaU"
ID_CANAL_ADVERTENCIAS = 1335972377179455659
ID_CANAL_LOGS = 1377100130204913664

# Base de datos
conn = sqlite3.connect("advertencias.db")
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS advertencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER,
    razon TEXT,
    cantidad INTEGER,
    fecha TEXT,
    mensaje_id TEXT
)
""")
conn.commit()

# Intents y bot
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await bot.wait_until_ready()
    try:
        synced = await bot.tree.sync(guild=discord.Object(id=1197745443963146312))
        print(f"Slash commands sincronizados en servidor: {len(synced)}")
    except Exception as e:
        print(f"Error al sincronizar comandos: {e}")
    print(f"Bot conectado como {bot.user}")

@bot.tree.command(name="advertencia", description="Enviar una advertencia a un usuario", guild=discord.Object(id=1197745443963146312))
@app_commands.describe(usuario="Usuario a advertir", razon="Motivo de la advertencia", cantidad="Cantidad de advertencias (1-3)", pagable="¿Es pagable? (Sí o No)")
async def advertencia(interaction: discord.Interaction, usuario: discord.Member, razon: str, cantidad: app_commands.Range[int, 1, 3], pagable: str):
    fecha_actual = datetime.now().strftime("%d/%m/%y")
    pagable_texto = "Sí" if pagable.lower() in ["sí", "si"] else "No"

    canal = interaction.guild.get_channel(1335972377179455659)
    if not canal or not canal.permissions_for(interaction.guild.me).send_messages:
        await interaction.response.send_message("❌ No tengo permisos para enviar mensajes en el canal de advertencias.", ephemeral=True)
        return

    embed = discord.Embed(
        title="⚠️ Nueva Advertencia Emitida",
        color=discord.Color.orange(),
        description=f"**Sistema de advertencias activado por {interaction.user.mention}**"
    )
    embed.add_field(name="👤 Usuario", value=usuario.mention, inline=True)
    embed.add_field(name="📄 Razón", value=razon, inline=False)
    embed.add_field(name="🔢 Advertencias", value=f"{cantidad}/3", inline=True)
    embed.add_field(name="💸 Pagable", value=pagable_texto, inline=True)
    embed.add_field(name="📅 Fecha", value=fecha_actual, inline=True)
    embed.set_footer(text="Registro automático del bot de disciplina", icon_url=interaction.user.display_avatar.url)

    mensaje = await canal.send(embed=embed, content="||@everyone||")

    # Guardar en base de datos
    c.execute("INSERT INTO advertencias (usuario_id, razon, cantidad, fecha, mensaje_id) VALUES (?, ?, ?, ?, ?)",
              (usuario.id, razon, cantidad, fecha_actual, str(mensaje.id)))
    conn.commit()

    confirm = discord.Embed(
        title="✅ Advertencia registrada",
        description=f"Se registró una advertencia para {usuario.mention} en {canal.mention}.",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=confirm, ephemeral=True)

@bot.tree.command(name="ver_advertencias", description="Ver historial de advertencias de un usuario", guild=discord.Object(id=1197745443963146312))
@app_commands.describe(usuario="Usuario a consultar")
async def ver_advertencias(interaction: discord.Interaction, usuario: discord.Member):
    c.execute("SELECT razon, cantidad, fecha FROM advertencias WHERE usuario_id = ?", (usuario.id,))
    resultados = c.fetchall()

    if not resultados:
        await interaction.response.send_message(f"ℹ️ {usuario.mention} no tiene advertencias registradas.", ephemeral=True)
        return

    embed = discord.Embed(title=f"📋 Historial de Advertencias de {usuario.display_name}", color=discord.Color.red())
    for i, (razon, cantidad, fecha) in enumerate(resultados, 1):
        embed.add_field(name=f"Advertencia {i}", value=f"📝 **Razón:** {razon}\n🔢 **Cantidad:** {cantidad}/3\n📅 **Fecha:** {fecha}", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="retirar_advertencia", description="Retirar una advertencia de un usuario", guild=discord.Object(id=1197745443963146312))
@app_commands.describe(usuario="Usuario a retirar advertencia")
async def retirar_advertencia(interaction: discord.Interaction, usuario: discord.Member):
    c.execute("SELECT id, razon, fecha FROM advertencias WHERE usuario_id = ?", (usuario.id,))
    resultados = c.fetchall()

    if not resultados:
        await interaction.response.send_message(f"ℹ️ {usuario.mention} no tiene advertencias para retirar.", ephemeral=True)
        return

    opciones = [
        discord.SelectOption(
            label=f"Advertencia {i+1}",
            description=f"{razon[:90]} - {fecha}",
            value=str(id_)
        ) for i, (id_, razon, fecha) in enumerate(resultados)
    ]

    class RetiroView(View):
        @discord.ui.select(placeholder="Selecciona la advertencia a retirar", options=opciones)
        async def select_callback(self, interaction2: discord.Interaction, select: discord.ui.Select):
            advertencia_id = int(select.values[0])
            c.execute("SELECT mensaje_id FROM advertencias WHERE id = ?", (advertencia_id,))
            resultado = c.fetchone()
            if resultado and resultado[0]:
                try:
                    canal_adv = interaction.guild.get_channel(1335972377179455659)
                    mensaje = await canal_adv.fetch_message(int(resultado[0]))
                    await mensaje.delete()
                except:
                    pass

            c.execute("DELETE FROM advertencias WHERE id = ?", (advertencia_id,))
            conn.commit()

            await interaction2.response.edit_message(content=f"✅ Se retiró la advertencia de {usuario.mention}.", embed=None, view=None)

            try:
                canal_logs = interaction.guild.get_channel(1377100130204913664)
                log_embed = discord.Embed(
                    title="🔍 Advertencia retirada",
                    description=f"👤 Usuario: {usuario.mention}\n🛠️ Moderador: {interaction.user.mention}\n📅 Fecha: {datetime.now().strftime('%d/%m/%y %H:%M')}",
                    color=discord.Color.blue()
                )
                await canal_logs.send(embed=log_embed)
            except:
                pass

    embed = discord.Embed(
        title=f"❌ Retirar Advertencia",
        description=f"Selecciona cuál advertencia deseas eliminar para {usuario.mention}:",
        color=discord.Color.red()
    )
    await interaction.response.send_message(embed=embed, view=RetiroView(), ephemeral=True)

@bot.tree.command(name="resumen_advertencias", description="Ver resumen general de advertencias", guild=discord.Object(id=1197745443963146312))
async def resumen_advertencias(interaction: discord.Interaction):
    c.execute("SELECT usuario_id, COUNT(*) FROM advertencias GROUP BY usuario_id")
    resultados = c.fetchall()

    if not resultados:
        await interaction.response.send_message("📭 No hay advertencias registradas actualmente.", ephemeral=True)
        return

    embed = discord.Embed(title="📊 Resumen de Advertencias Activas", color=discord.Color.gold())
    for usuario_id, cantidad in resultados:
        miembro = interaction.guild.get_member(usuario_id)
        nombre = miembro.mention if miembro else f"ID: {usuario_id}"
        embed.add_field(name=nombre, value=f"{cantidad} advertencia(s)", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)

bot.run(TOKEN)
