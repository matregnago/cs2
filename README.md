# Servidor CS2 com atualização automática de mods

Imagem Linux amd64 derivada de `joedwards32/cs2:latest`, para partidas com
MatchZy e skins pelo [Inventory Simulator](https://inventory.cstrike.app/).

## Iniciar

Ajuste as opções do `docker-compose.yml`, incluindo senhas e o `AUTHKEY` caso
utilize autenticação. O servidor está configurado para LAN. Reserve pelo menos
60 GB para os arquivos do jogo, além de espaço para mods, backups temporários e demos.

```sh
docker compose up -d --build
docker compose logs -f cs2-server
```

O Compose constrói a imagem `cs2-server-modded:local`. Os arquivos do jogo,
mods, configurações e versões instaladas persistem em `./cs2-data`.
Na inicialização, o wrapper ajusta o proprietário dos arquivos do volume para
UID/GID `1000:1000` e então executa o servidor como `steam`. Isso permite usar
diretórios ou arquivos criados anteriormente por root. O servidor não roda como
root. Não defina `user:` no Compose se quiser usar essa correção automática;
volumes montados como somente leitura ou que bloqueiem `chown` precisam ser
ajustados no host.

Para consultar novas versões dos mods e do jogo:

```sh
docker compose restart cs2-server
```

Para reconstruir também com a versão atual da imagem base:

```sh
docker compose build --pull
docker compose up -d
```

## Atualizações na inicialização

Depois de o SteamCMD atualizar o jogo, o hook consulta as releases publicadas
dos seguintes repositórios, incluindo **pré-releases** e excluindo drafts:

| Mod | Repositório | Pacote |
| --- | --- | --- |
| Metamod | [alliedmodders/metamod-source](https://github.com/alliedmodders/metamod-source) | Linux da linha **2.x**, compatível com CS2 |
| CounterStrikeSharp | [roflmuffin/CounterStrikeSharp](https://github.com/roflmuffin/CounterStrikeSharp) | Linux com runtime .NET |
| MatchZy | [shobhit-pathak/MatchZy](https://github.com/shobhit-pathak/MatchZy) | Sem CounterStrikeSharp embutido |
| Inventory Simulator | [ianlucas/cs2-css-inventory-simulator](https://github.com/ianlucas/cs2-css-inventory-simulator) | InventorySimulator ZIP |

"Mais recente" corresponde à maior data `published_at`, sem comparação numérica
das tags. Para Metamod, releases 1.x são ignoradas porque atendem a jogos Source 1.

Os manifestos ficam em `cs2-data/.mod-updater/<mod>.json`. Se repositório, tag,
release ID e asset ID coincidirem e os arquivos essenciais existirem, o pacote
não será baixado nem reinstalado. Na primeira execução, instalações existentes
sem manifesto recebem uma instalação gerenciada. Não há atualização em segundo
plano nem atualização durante partidas.

Todos os pacotes alterados são baixados, extraídos e validados antes da aplicação.
O tamanho e o SHA-256 publicado pelo GitHub, quando disponível, são conferidos.
Uma transação faz backup dos arquivos afetados e inclui os manifestos; falhas
durante a aplicação restauram os arquivos anteriores. Transações interrompidas
são restauradas no próximo início. Os logs usam o prefixo `[mod-updater]`.

Se o GitHub estiver indisponível, houver limite de requisições ou uma atualização
falhar, o servidor usa a instalação anterior se os quatro mods estiverem completos.
Sem instalação completa, com falha de restauração ou sem conseguir preparar as
configurações obrigatórias, a inicialização é encerrada. Isso verifica a presença
dos arquivos essenciais; compatibilidade funcional com uma nova versão do CS2
depende dos projetos upstream.

As requisições têm timeout de 30 segundos por operação de rede e até três tentativas.
Para aumentar o limite da API, defina opcionalmente `GITHUB_TOKEN` no ambiente do
Compose ou em um arquivo `.env` local, ignorado pelo Git:

```dotenv
GITHUB_TOKEN=seu_token
```

O token é passado apenas em requisições à API, não faz parte do build e não é
registrado nos logs.

## Configurações persistentes

### IDs de administradores

Copie `.env.example` para `.env` e configure os SteamID64 (17 dígitos) dos admins:

```dotenv
CS2_ADMIN_STEAMIDS=76561198330843136,76561198000000000
```

Também é possível definir `CS2_ADMIN_STEAMIDS` no ambiente do Compose. Espaços
podem separar os IDs; duplicatas são ignoradas. Após alterar a lista, recrie o
container para carregar o novo ambiente:

```sh
docker compose up -d --build --force-recreate
```

A lista substitui os admins de `cfg/MatchZy/admins.json` a cada início e cria
entradas com permissão total `@css/root` no arquivo de admins do CounterStrikeSharp.
Entradas desse último arquivo com prefixo `cs2-docker-` são gerenciadas pela variável;
as demais entradas manuais são preservadas. IDs removidos da variável deixam de
constar nas entradas gerenciadas; contas adicionadas manualmente no CounterStrikeSharp
continuam com suas permissões próprias.

Variável ausente ou vazia preserva os arquivos atuais. Para esvaziar a lista do
MatchZy e remover as entradas gerenciadas do CounterStrikeSharp, use
`CS2_ADMIN_STEAMIDS=[]`. IDs inválidos interrompem a inicialização sem alterar os
arquivos. Os formatos seguem as documentações do
[MatchZy](https://shobhit-pathak.github.io/MatchZy/configuration/#creating-admins) e do
[CounterStrikeSharp](https://docs.cssharp.dev/docs/admin-framework/defining-admins.html).

### Arquivos e correções automáticas

As configurações em `cfg/` são instaladas apenas quando ainda não existem no volume.
Para alterar um servidor já inicializado, edite os arquivos em
`cs2-data/game/csgo/cfg/`. As configurações do repositório têm prioridade sobre os
padrões dos pacotes somente na primeira instalação.

Exceto pelos admins gerenciados explicitamente pela variável acima, o atualizador
preserva arquivos existentes em `cfg/`, nas configurações do
CounterStrikeSharp, os arquivos `admins.json`, `.cfg`, `.ini`, bancos `.db`,
`.sqlite`, `.sqlite3` e arquivos de spawns. Não limpa diretórios de plugins nem
remove arquivos antigos, preservando dados gerados pelo servidor.
No `core.json`, somente `FollowCS2ServerGuidelines` é definido como `false`;
os demais valores são mantidos. O Compose executa `inventory_simulator.cfg`.

A entrada de busca do Metamod em `gameinfo.gi` é verificada a cada início,
inclusive após atualização do jogo, sem duplicação.
O patch insere `Game csgo/addons/metamod` após `Game_LowViolence csgo_lv`, como
no script original; se essa entrada não existir, insere antes de `Game csgo`.
Se não houver nenhum desses pontos, falha sem modificar o arquivo.

**O arquivo `cs2-data/pre.sh` passa a ser gerenciado pela imagem e é substituído
a cada início.** Os scripts e configurações padrão ficam em `/opt/cs2-mods`, fora
do volume. Para personalizar o hook, altere o `pre.sh` deste repositório e reconstrua
a imagem. Um volume só pode ser usado por um servidor por vez.

## Validação

Testes locais com pacotes e respostas simulados, sem baixar o jogo:

```sh
python -m unittest discover -s tests -v
docker compose config --quiet
docker compose build
```

Teste opcional com os pacotes reais do GitHub, em diretório temporário dentro do
container, sem alterar `cs2-data` nem baixar/iniciar o CS2:

```sh
docker run --rm --mount "type=bind,source=CAMINHO_ABSOLUTO_DO_REPO/tests,target=/tests,readonly" cs2-server-modded:local python3 /tests/smoke_upstream.py
```

Esse teste executa o wrapper e o hook duas vezes: instala os quatro mods e
confirma que a segunda execução não baixa pacotes nem altera os arquivos.
Para diagnosticar incompatibilidades com atualizações do jogo, consulte também
[cs2-signatures](https://github.com/ianlucas/cs2-signatures).

## Créditos

- [kus/cs2-modded-server](https://github.com/kus/cs2-modded-server)
- [joedwards32/CS2](https://github.com/joedwards32/CS2)
- [ianlucas](https://github.com/ianlucas)
