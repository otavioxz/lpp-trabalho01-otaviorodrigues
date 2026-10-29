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
GANHO_POR_TACHO = 5   # frutas a mais por colheita para cada tacho pronto
FRUTAS_POR_POTE = 5   # frutas que cada tacho pronto transforma em 1 pote por colheita

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
    sio.start_background_task(producao)    # o relógio do pomar começa a emitir colheitas
    # EMITE vila.iniciada para todos: a fase mudou e todas as telas precisam mostrar isso.
    await sio.emit("vila.iniciada", fato(pedido))


# ESCUTA o pedido de um Jogador para construir um tacho de geleia.
@sio.on("construcao.solicitada")
async def construir(sid, dados=None):
    pedido = "construcao.solicitada"
    # Valide TUDO antes de alterar o estado e sem await no meio: o servidor
    # trata um evento por vez, então dois pedidos simultâneos são decididos
    # em sequência e só um fica com o último colhedor.
    if estado["fase"] != "aberta":
        motivo = "A temporada não está aberta"
    elif jogadores[sid]["papel"] != "jogador":
        motivo = "Só os Jogadores podem construir tachos"
    elif estado["frutas"] < CUSTO:
        motivo = "Frutas insuficientes"
    elif estado["colhedores"] >= estado["limite"]:
        motivo = "Sem colhedor livre"
    else:
        motivo = None
    if motivo:
        await recusar(sid, motivo, pedido)
        return
    estado["frutas"] -= CUSTO
    estado["colhedores"] += 1
    estado["em_obra"] += 1
    nome = jogadores[sid]["nome"]
    # EMITE construcao.iniciada para todos: as frutas e os colhedores mudaram
    # e todas as telas precisam mostrar o novo tacho em obra.
    await sio.emit("construcao.iniciada", fato(pedido, por=nome))
    sio.start_background_task(obra, nome)  # o temporizador da obra emitirá construcao.concluida


# TEMPORIZADOR da colheita: roda em segundo plano enquanto a temporada está
# aberta. Ninguém clica: o próprio servidor gera o fato a cada INTERVALO.
async def producao():
    while estado["fase"] == "aberta":
        await sio.sleep(INTERVALO)        # sio.sleep não trava o servidor (time.sleep travaria)
        if estado["fase"] != "aberta":
            break
        estado["frutas"] += estado["producao"]
        # cada tacho pronto transforma FRUTAS_POR_POTE frutas em 1 pote, se houver frutas
        potes = min(estado["concluidas"], estado["frutas"] // FRUTAS_POR_POTE)
        estado["frutas"] -= potes * FRUTAS_POR_POTE
        estado["potes"] += potes
        # EMITE recurso.produzido para todos: o estoque mudou sem ninguém pedir.
        await sio.emit("recurso.produzido", fato("temporizador", colhidas=estado["producao"], potes_feitos=potes))


# TEMPORIZADOR da obra: começa quando a construção é aceita e termina sozinho.
async def obra(nome):
    await sio.sleep(TEMPO_OBRA)
    if estado["fase"] != "aberta":        # temporada encerrada: a obra não termina mais
        return
    estado["colhedores"] -= 1
    estado["em_obra"] -= 1
    estado["concluidas"] += 1
    estado["producao"] += GANHO_POR_TACHO
    # EMITE construcao.concluida para todos: o colhedor ficou livre e a colheita aumentou.
    await sio.emit("construcao.concluida", fato("construcao.iniciada (temporizador)", por=nome))
