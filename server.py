import socketio

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
app = socketio.ASGIApp(sio, static_files={
    "/": "client/index.html",
    "/assets": "client/assets",      # mapa, tileset e sprites da vila
})

# A partir da Etapa 1, adicione o seu código ABAIXO desta linha.

# ---------------------------------------------------------------------
#  Regras do pomar (docs/especificacao.md, seção 1)
# ---------------------------------------------------------------------
CUSTO = 40            # frutas por tacho de geleia
TEMPO_OBRA = 8        # segundos até o tacho ficar pronto
INTERVALO = 5         # segundos entre as colheitas automáticas

# Estado do pomar: só o servidor altera. Os clientes recebem cópias pelos eventos.
estado = {
    "fase": "aguardando",      # aguardando -> aberta -> encerrada
    "frutas": 120,             # recurso primário
    "potes": 0,                # recurso refinado (potes de geleia)
    "colhedores": 0,           # colhedores ocupados em obras agora
    "limite": 3,               # total de colhedores do pomar
    "producao": 10,            # frutas colhidas a cada INTERVALO
    "intervalo": INTERVALO,
    "tempo_obra": TEMPO_OBRA,
    "custo": CUSTO,
    "concluidas": 0,           # tachos prontos
    "em_obra": 0,              # tachos em obra
}

jogadores = {}  # sid -> {"nome": ..., "papel": ...}


def fato(causa, **extras):
    """Monta o payload de um FATO: o estado atual, a CAUSA (o pedido ou o
    temporizador que gerou o fato) e dados extras."""
    return {"estado": dict(estado), "causa": causa, **extras}


# ESCUTA o evento de conexão: um novo cliente entrou no pomar.
@sio.event
async def connect(sid, environ, auth):
    auth = auth or {}
    jogadores[sid] = {
        "nome": auth.get("nome", "Anônimo"),
        "papel": auth.get("papel", "jogador"),
    }
    # EMITE estado.sincronizado só para quem entrou (to=sid): os demais já
    # têm o estado, só o recém-chegado precisa recebê-lo.
    await sio.emit("estado.sincronizado", fato("conexao"), to=sid)


# ESCUTA a desconexão: o cliente saiu e deixa de ser contado.
@sio.event
async def disconnect(sid):
    jogadores.pop(sid, None)


async def recusar(sid, motivo, causa):
    """EMITE operacao.recusada só para quem pediu (to=sid): a recusa não muda
    o estado, então os outros jogadores não precisam saber dela."""
    await sio.emit("operacao.recusada", {"motivo": motivo, "causa": causa}, to=sid)


# ESCUTA o pedido do Mestre para abrir a temporada. O servidor decide se aceita.
@sio.on("vila.abertura_solicitada")
async def abrir_vila(sid, dados=None):
    pedido = "vila.abertura_solicitada"
    if jogadores[sid]["papel"] != "mestre":
        await recusar(sid, "Só o Mestre pode abrir a temporada", pedido)
        return
    if estado["fase"] != "aguardando":
        await recusar(sid, "A temporada já foi aberta", pedido)
        return
    estado["fase"] = "aberta"
    # EMITE vila.iniciada para todos: a fase mudou e todas as telas precisam mostrar isso.
    await sio.emit("vila.iniciada", fato(pedido))
