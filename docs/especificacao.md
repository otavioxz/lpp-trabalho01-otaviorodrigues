# Especificação — Vila em Tempo Real

**Integrante(s):** Otavio Rodrigues — @otavioxz
**Tipo de vila (sorteio):** 13 — Pomar e geleias

> Escreva este documento ANTES do código e faça o commit antes da Etapa 0.
> Descreva o comportamento na linguagem da vila. Não cite tecnologia.

## 1. Regras da vila

O pomar é cooperativo. O **Mestre** abre e encerra a temporada de colheita. Os **Jogadores** constroem tachos de geleia e disputam os lotes de frutas maduras. Toda decisão é do pomar (o servidor). Os jogadores só pedem e acompanham.

- **Recurso primário e recurso refinado:** 🍎 **frutas** (primário) e 🫙 **potes de geleia** (refinado). O pomar começa a temporada com **120 frutas** e **0 potes**.
- **Custo de uma construção:** cada **tacho de geleia** custa **40 frutas**.
- **Tempo da obra:** um tacho fica pronto **8 segundos** depois de iniciado.
- **Limite de trabalhadores:** o pomar tem **3 colhedores**. Cada obra em andamento ocupa 1 colhedor, que fica livre quando a obra termina. Não pode haver mais de 3 obras ao mesmo tempo.
- **Intervalo e quantidade da produção automática:** a cada **5 segundos** o pomar colhe **10 frutas**, mais **5 frutas por tacho pronto**.
- **O que muda quando uma obra termina:**
  - o colhedor volta a ficar livre;
  - o número de tachos prontos sobe 1;
  - a colheita automática aumenta em 5 frutas por ciclo;
  - **o tacho passa a fazer geleia:** a cada ciclo de colheita, cada tacho pronto transforma **5 frutas em 1 pote de geleia**, se houver frutas suficientes.
- **Fruta madura estraga (evento próprio):**
  - a cada **20 segundos** de temporada aberta, amadurece um **lote de 30 frutas** com prazo de **10 segundos** para ser colhido;
  - só existe um lote maduro por vez;
  - enquanto há um lote maduro, os Jogadores veem a opção de colher; quando o lote é colhido ou estraga, a opção some;
  - o primeiro jogador que pedir a colheita leva o lote, que soma 30 ao estoque, e os outros recebem recusa;
  - se ninguém colher dentro do prazo, o lote **estraga** e se perde.
- **Recusas:** um pedido é recusado, e **só quem pediu** é avisado, quando:
  - a temporada não está aberta;
  - faltam frutas para o tacho;
  - não há colhedor livre;
  - não há lote maduro para colher;
  - um Jogador tenta abrir ou encerrar a temporada (só o Mestre pode);
  - o Mestre tenta construir um tacho ou colher um lote (só os Jogadores podem);
  - o Mestre tenta abrir uma temporada que já foi aberta;
  - o Mestre tenta encerrar uma temporada que não está aberta.
- **Encerramento:**
  - a colheita automática e o amadurecimento param;
  - obras em andamento não terminam mais;
  - um lote maduro pendente é descartado;
  - todo novo pedido é recusado.

## 2. Eventos

| Evento | Emite | Recebe | O que muda no estado |
|---|---|---|---|
| `estado.sincronizado` | Servidor | Só quem entrou | Nada muda. O recém-chegado recebe o estado atual do pomar. |
| `vila.abertura_solicitada` | Mestre | Servidor | (é um pedido; nada muda) |
| `vila.iniciada` | Servidor | Todos | A fase passa de "aguardando" para "aberta". A colheita automática e o amadurecimento começam. |
| `construcao.solicitada` | Jogador | Servidor | (é um pedido; nada muda) |
| `construcao.iniciada` | Servidor | Todos | Frutas −40, colhedores ocupados +1, tachos em obra +1. |
| `operacao.recusada` | Servidor | Só quem pediu | Nada muda. Informa o motivo da recusa e qual pedido foi recusado. |
| `recurso.produzido` | Servidor | Todos | Frutas + (10 + 5 × tachos prontos). Depois, cada tacho pronto transforma 5 frutas em 1 pote de geleia. |
| `construcao.concluida` | Servidor | Todos | Colhedores ocupados −1, tachos em obra −1, tachos prontos +1. A colheita sobe 5 frutas por ciclo. |
| `fruta.amadureceu` | Servidor | Todos | Surge um lote maduro de 30 frutas com prazo de 10 s. |
| `colheita.solicitada` | Jogador | Servidor | (é um pedido; nada muda) |
| `colheita.realizada` | Servidor | Todos | Frutas +30. O lote maduro deixa de existir. |
| `fruta.estragou` | Servidor | Todos | O lote maduro deixa de existir sem somar frutas. |
| `vila.encerramento_solicitado` | Mestre | Servidor | (é um pedido; nada muda) |
| `vila.encerrada` | Servidor | Todos | A fase passa a "encerrada". Colheita, amadurecimento e obras param, e o lote pendente é descartado. |

**Causa de cada fato:**
- os fatos gerados por pedido levam como causa o nome do pedido (ex.: `construcao.iniciada` ← `construcao.solicitada`);
- os gerados pelo relógio do pomar levam como causa o temporizador:
  - `recurso.produzido` e `fruta.amadureceu` ← temporizador;
  - `construcao.concluida` ← `construcao.iniciada` (temporizador);
  - `fruta.estragou` ← `fruta.amadureceu` (temporizador).

## 3. Cenários de teste (Dado / Quando / Então, escritos com eventos)

### Recusa
**Dado** que a temporada está aberta, há 30 frutas e 1 de 3 colhedores ocupados,
**quando** o Jogador A emite `construcao.solicitada`,
**então** o servidor emite `operacao.recusada` com o motivo "Frutas insuficientes" apenas para o Jogador A. As frutas continuam 30, os colhedores continuam 1/3 e os demais jogadores não recebem nada.

**Dado** que a temporada ainda está aguardando,
**quando** o Jogador A emite `construcao.solicitada`,
**então** o servidor emite `operacao.recusada` com o motivo "A temporada não está aberta" apenas para o Jogador A.

### Passagem do tempo
**Dado** que o Mestre emitiu `vila.abertura_solicitada`, o servidor emitiu `vila.iniciada` e há 120 frutas, 0 potes e nenhum tacho pronto,
**quando** passam 5 segundos sem nenhum clique,
**então** o servidor emite `recurso.produzido` para todos com causa "temporizador" e as frutas vão a 130.

**Dado** que o Jogador A teve a obra aceita (`construcao.iniciada`), deixando 80 frutas e 1/3 colhedores,
**quando** passam 8 segundos,
**então** o servidor emite `construcao.concluida` para todos:
- os colhedores voltam a 0/3 e os tachos prontos vão a 1;
- no próximo `recurso.produzido` entram 15 frutas e 5 delas viram 1 pote de geleia.

**Dado** que o servidor emitiu `fruta.amadureceu` (lote de 30 frutas, prazo de 10 s),
**quando** passam 10 segundos sem nenhum `colheita.solicitada`,
**então** o servidor emite `fruta.estragou` para todos e o estoque de frutas não muda.

### Disputa entre dois jogadores
**Dado** que a temporada está aberta, há 200 frutas e 2 de 3 colhedores ocupados,
**quando** os jogadores A e B emitem `construcao.solicitada` ao mesmo tempo,
**então** o servidor atende os pedidos um de cada vez:
- emite `construcao.iniciada` para todos por causa do primeiro pedido (colhedores 3/3, frutas 160);
- emite `operacao.recusada` com o motivo "Sem colhedor livre" apenas para o outro jogador;
- os colhedores nunca passam de 3/3.

**Dado** que o servidor emitiu `fruta.amadureceu` e o lote ainda está no prazo,
**quando** os jogadores A e B emitem `colheita.solicitada` ao mesmo tempo,
**então** o servidor emite `colheita.realizada` para todos (frutas +30) por causa do primeiro pedido. Emite também `operacao.recusada` com o motivo "Não há fruta madura para colher" apenas para o outro jogador. O lote não estraga depois, porque já foi colhido.
