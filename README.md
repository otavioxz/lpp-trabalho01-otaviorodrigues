# Vila em Tempo Real — Pomar e geleias

Trabalho 01 de Linguagem de Programação e Paradigmas (Programação Orientada a Eventos, 2026/2).
Vila sorteada: **13 — Pomar e geleias**. O pomar colhe 🍎 frutas, os Jogadores constroem 🍯 tachos
que transformam frutas em 🫙 potes de geleia, e de tempos em tempos amadurece um lote de frutas
que precisa ser colhido antes de estragar.

As regras, a tabela de eventos e os cenários de teste estão em [`docs/especificacao.md`](docs/especificacao.md).

## Integrantes
- Otavio Rodrigues — @otavioxz

## Tecnologias
- **Servidor:** Python 3 (testado no 3.13), `python-socketio` e `uvicorn`.
- **Tela:** Vue 3, Socket.IO (cliente) e Phaser 3, carregados por CDN (nada para instalar).

## Como instalar e executar
1. Instale o [Python 3](https://www.python.org/downloads/) e clone o repositório:
   ```
   git clone https://github.com/otavioxz/lpp-trabalho01-otaviorodrigues.git
   cd lpp-trabalho01-otaviorodrigues
   ```
2. Crie e ative um ambiente virtual e instale as dependências:
   ```
   python -m venv .venv
   .venv\Scripts\activate          # Windows
   source .venv/bin/activate       # Linux ou macOS
   pip install -r requirements.txt
   ```
3. Suba o servidor:
   ```
   uvicorn server:app --reload
   ```
4. Abra **http://localhost:8000** no navegador (não abra o arquivo direto com `file://`).

> O estado do pomar fica na memória do servidor. Quando o `--reload` reinicia o servidor,
> o pomar volta ao começo: recarregue as abas e entre de novo.

## Como testar com duas abas
1. Abra duas abas lado a lado em `http://localhost:8000`.
2. **Aba 1:** digite um nome e clique em **Entrar como Mestre**. **Aba 2:** digite outro nome e
   clique em **Entrar como Jogador**. As duas mostram 120 frutas, 0 potes, colhedores 0/3,
   temporada *aguardando*, e o Painel de eventos mostra `⬇ on estado.sincronizado`.
3. **Recusa:** no Jogador, clique em **Construir tacho** antes de abrir. Só a aba do Jogador
   mostra o aviso vermelho "A temporada não está aberta" e a vila treme.
4. **Abertura:** no Mestre, clique em **Abrir temporada**. As duas abas passam a *aberta*, sem
   recarregar. A cada 5 s as frutas sobem sozinhas (`recurso.produzido`, causa: temporizador).
5. **Construção:** no Jogador, clique em **Construir tacho**. As duas abas mostram −40 frutas,
   colhedores 1/3 e o canteiro na vila. Depois de 8 s o canteiro vira um tacho
   (`construcao.concluida`), a colheita sobe 5 frutas e, a cada colheita, o tacho faz 1 pote de geleia.
6. **Fruta madura:** a cada 20 s aparece um lote de 30 frutas com uma barra de prazo de 10 s e o
   botão **Colher lote maduro**. Se o Jogador colher, todos veem +30 frutas; se ninguém colher,
   todos veem "O lote maduro estragou".
7. **Disputa (use uma terceira aba como Jogador B):** com 2 de 3 colhedores ocupados, clique em
   **Construir tacho** nos dois Jogadores quase ao mesmo tempo. Só um consegue; o outro vê
   "Sem colhedor livre". O mesmo vale para o lote maduro: só um colhe, o outro vê
   "Não há fruta madura para colher".
8. **Encerramento:** no Mestre, clique em **Encerrar temporada**. Todas as abas escurecem, as frutas
   param de subir, as obras não terminam mais e todo novo pedido é recusado.

## Perguntas

### 1. Quais eventos o seu sistema emite e escuta?

| Evento | Quem emite | Quem escuta |
|---|---|---|
| `vila.abertura_solicitada` | Mestre (cliente) | Servidor |
| `construcao.solicitada` | Jogador (cliente) | Servidor |
| `colheita.solicitada` | Jogador (cliente) | Servidor |
| `vila.encerramento_solicitado` | Mestre (cliente) | Servidor |
| `estado.sincronizado` | Servidor | Só o cliente que acabou de entrar |
| `vila.iniciada` | Servidor | Todos os clientes |
| `construcao.iniciada` | Servidor | Todos os clientes |
| `operacao.recusada` | Servidor | Só o cliente que fez o pedido |
| `recurso.produzido` | Servidor (temporizador) | Todos os clientes |
| `construcao.concluida` | Servidor (temporizador) | Todos os clientes |
| `fruta.amadureceu` | Servidor (temporizador) | Todos os clientes |
| `colheita.realizada` | Servidor | Todos os clientes |
| `fruta.estragou` | Servidor (temporizador) | Todos os clientes |
| `vila.encerrada` | Servidor | Todos os clientes |

Os eventos `*_solicitado(a)` são **pedidos** do cliente; os demais são **fatos** que o servidor
confirma. A recusa também é um evento (`operacao.recusada`).

### 2. Como o sistema sabe quando deve atualizar os outros jogadores?

O cliente nunca altera o estado sozinho: ele só pede. O servidor guarda o estado, valida o pedido e,
quando algo muda, **emite um fato para todos** (`sio.emit(evento, dados)` sem destinatário). Cada
cliente tem um handler (`ouvir(...)`) para esse fato e se atualiza ao recebê-lo. Quando nada muda
para os outros, o servidor responde só a quem interessa (`to=sid`): a recusa vai só para quem pediu
e o `estado.sincronizado` só para quem acabou de entrar. Os temporizadores do servidor
(colheita, obra, amadurecimento e prazo do lote) também são fontes de eventos: eles alteram o
estado e emitem o fato, sem nenhum clique e sem o cliente precisar perguntar.

### 3. Que parte do código mostra claramente o uso do paradigma orientado a eventos?

- **`server.py`, handlers `@sio.on(...)`**: `construir` e `colher` escutam um pedido, validam tudo
  sem `await` no meio (por isso dois pedidos simultâneos são decididos um de cada vez) e emitem
  `construcao.iniciada`/`colheita.realizada` para todos ou `operacao.recusada` só para quem pediu.
- **`server.py`, temporizadores `producao`, `obra`, `amadurecimento` e `prazo_do_lote`**: rodam em
  segundo plano com `sio.sleep` e emitem fatos com a causa "temporizador".
- **`server.py`, função `fato(causa, ...)`**: todo fato leva o estado e a sua causa, o que deixa o
  encadeamento visível (ex.: `construcao.concluida` ← `construcao.iniciada (temporizador)`).
- **`client/index.html`, região ESCUTAS dentro de `entrar()`**: cada `ouvir("evento", "reação", ...)`
  liga um fato do servidor a uma reação na tela e na vila desenhada. Na região PEDIDOS, cada botão
  só faz `pedir("..._solicitada")`.
- **Painel de eventos** na tela: mostra cada `⬆ emit` e `⬇ on`, com horário, dados, causa e reação.

## Uso de IA
Usei o **Claude Code** (Anthropic) como assistente durante o desenvolvimento:
- para revisar a especificação e apontar lacunas (recusas do Mestre e botão de colher), que depois
  acrescentei à especificação antes do código;
- para implementar as etapas seguindo o Guia de Implementação, uma por vez, testando cada uma antes
  do commit;
- para criar a arte nova (o tacho de geleia e a árvore com maçãs) a partir da arte do kit e para
  adaptar o mapa no formato do Tiled;

## Extras
- **Contadores por evento:** no alto do Painel de eventos,
  uma etiqueta por evento mostra quantas vezes este cliente já o emitiu ou escutou
  (ex.: `construcao.iniciada ×2`).
- **Arte própria do pomar:** o tacho de geleia (quadro 2 de `sprites-vila.png`) e a árvore com maçãs
  (peça 48 de `tileset-vila.png`) foram desenhados para este trabalho a partir da arte original do kit
  (uso livre na disciplina). Nenhuma arte de terceiros foi usada.
- **Mapa personalizado** (`client/assets/vila.json`): pomar cercado, árvores frutíferas e um ponto
  `fruta_madura` onde o lote maduro aparece, com uma barra que mostra o prazo escorrendo.
- **Painel de eventos:** os pedidos `construcao.solicitada` e `colheita.solicitada` passaram a
  aparecer como pedido (azul), e não como fato.
