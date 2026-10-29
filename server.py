import socketio

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
app = socketio.ASGIApp(sio, static_files={
    "/": "client/index.html",
    "/assets": "client/assets",      # mapa, tileset e sprites da vila
})

# ---------------------------------------------------------------------
#  Regras do pomar (docs/especificacao.md, seção 1)
# ---------------------------------------------------------------------
CUSTO = 40            # frutas por tacho de geleia
TEMPO_OBRA = 8        # segundos até o tacho ficar pronto
INTERVALO = 5         # segundos entre as colheitas automáticas
GANHO_POR_TACHO = 5   # frutas a mais por colheita para cada tacho pronto
FRUTAS_POR_POTE = 5   # frutas que cada tacho pronto transforma em 1 pote por colheita
AMADURECER = 20       # segundos entre um lote maduro e o próximo
LOTE = 30             # frutas de um lote maduro
PRAZO = 10            # segundos para colher o lote antes que ele estrague

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
    "lote_maduro": 0,          # frutas do lote maduro à espera de colheita (0 = nenhum)
    "prazo": PRAZO,
}

jogadores = {}  # sid -> {"nome": ..., "papel": ...}
numero_lote = 0  # identifica cada lote, para o prazo de um lote antigo não estragar um novo


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
    sio.start_background_task(amadurecimento)  # e também a amadurecer lotes de frutas
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


# ESCUTA o pedido do Mestre para encerrar a temporada.
@sio.on("vila.encerramento_solicitado")
async def encerrar_vila(sid, dados=None):
    pedido = "vila.encerramento_solicitado"
    if jogadores[sid]["papel"] != "mestre":
        await recusar(sid, "Só o Mestre pode encerrar a temporada", pedido)
        return
    if estado["fase"] != "aberta":
        await recusar(sid, "A temporada não está aberta", pedido)
        return
    # Com a fase "encerrada", os temporizadores de colheita, obra e amadurecimento param
    # sozinhos e todo novo pedido de construção passa a ser recusado.
    estado["fase"] = "encerrada"
    estado["lote_maduro"] = 0              # o lote pendente é descartado
    # EMITE vila.encerrada para todos: a temporada acabou para todas as telas.
    await sio.emit("vila.encerrada", fato(pedido))


# TEMPORIZADOR do amadurecimento (evento próprio do pomar): a cada AMADURECER
# segundos surge um lote maduro, que os Jogadores disputam antes que estrague.
async def amadurecimento():
    global numero_lote
    while estado["fase"] == "aberta":
        await sio.sleep(AMADURECER)
        if estado["fase"] != "aberta":
            break
        if estado["lote_maduro"]:          # só existe um lote maduro por vez
            continue
        estado["lote_maduro"] = LOTE
        numero_lote += 1
        # EMITE fruta.amadureceu para todos: todos podem disputar o lote.
        await sio.emit("fruta.amadureceu", fato("temporizador", lote=LOTE, prazo=PRAZO))
        sio.start_background_task(prazo_do_lote, numero_lote)


# TEMPORIZADOR do prazo: se ninguém colher o lote a tempo, ele estraga.
async def prazo_do_lote(numero):
    await sio.sleep(PRAZO)
    # o lote já foi colhido, descartado no encerramento ou trocado por outro
    if estado["fase"] != "aberta" or not estado["lote_maduro"] or numero != numero_lote:
        return
    perdidas = estado["lote_maduro"]
    estado["lote_maduro"] = 0
    # EMITE fruta.estragou para todos: o lote sumiu sem somar frutas.
    await sio.emit("fruta.estragou", fato("fruta.amadureceu (temporizador)", perdidas=perdidas))


# ESCUTA o pedido de um Jogador para colher o lote maduro.
@sio.on("colheita.solicitada")
async def colher(sid, dados=None):
    pedido = "colheita.solicitada"
    # Valide e altere sem await no meio: se dois jogadores pedirem ao mesmo
    # tempo, o primeiro leva o lote e o segundo já encontra o lote vazio.
    if estado["fase"] != "aberta":
        motivo = "A temporada não está aberta"
    elif jogadores[sid]["papel"] != "jogador":
        motivo = "Só os Jogadores podem colher"
    elif not estado["lote_maduro"]:
        motivo = "Não há fruta madura para colher"
    else:
        motivo = None
    if motivo:
        await recusar(sid, motivo, pedido)
        return
    colhidas = estado["lote_maduro"]
    estado["frutas"] += colhidas
    estado["lote_maduro"] = 0
    # EMITE colheita.realizada para todos: as frutas subiram e o lote acabou.
    await sio.emit("colheita.realizada", fato(pedido, por=jogadores[sid]["nome"], colhidas=colhidas))
