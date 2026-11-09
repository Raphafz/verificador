## PARTE 6 — EVENTOS

O Baileys utiliza um sistema de eventos baseado no padrão `EventEmitter` do Node.js para notificar a aplicação sobre mudanças de estado, novas mensagens e outras atividades. Todos os eventos são fortemente tipados na interface `BaileysEventMap` (em `src/Types/Events.ts`) [1].

### TODOS os eventos disponíveis

Abaixo, detalhamos os principais eventos, seus payloads e casos de uso:

| Evento | Quando dispara | Payload | Como utilizar / Casos de uso |
| :--- | :--- | :--- | :--- |
| `connection.update` | Mudanças no estado da conexão WebSocket (conectando, aberto, fechado, QR code gerado). | `Partial<ConnectionState>` (inclui `connection`, `lastDisconnect`, `qr`, `isNewLogin`, etc.) | **Uso:** Monitorar a saúde da conexão, exibir QR code no terminal/UI, implementar lógica de reconexão automática. **Erro comum:** Não tratar `DisconnectReason.loggedOut`, que exige apagar a sessão e gerar novo QR. |
| `creds.update` | Quando as credenciais de autenticação ou chaves criptográficas são atualizadas (e.g., após enviar/receber mensagens). | `Partial<AuthenticationCreds>` | **Uso:** Chamar a função `saveCreds` (do `useMultiFileAuthState`) para persistir as chaves no disco. **Erro comum:** Esquecer de ouvir este evento, resultando em perda de chaves e falha na descriptografia futura. |
| `messaging-history.set` | Durante o login inicial (ou pareamento de novo dispositivo), quando o WhatsApp envia o histórico de conversas e mensagens. | Objeto com arrays de `chats`, `contacts`, `messages`, `isLatest`, etc. | **Uso:** Popular o banco de dados local com o histórico do usuário. **Boa prática:** O payload pode ser enorme; processe em lotes ou insira no banco de forma assíncrona para não bloquear o event loop. |
| `chats.upsert` / `chats.update` / `chats.delete` | Quando um chat é criado, atualizado (e.g., nova mensagem, lido/não lido) ou deletado. | Arrays de `Chat` ou `ChatUpdate` ou IDs de chats. | **Uso:** Manter a lista de conversas da UI atualizada. |
| `presence.update` | Quando o status de presença de um contato muda (online, offline, digitando, gravando áudio). | `{ id: string; presences: { [participant: string]: PresenceData } }` | **Uso:** Mostrar indicadores de "digitando..." na interface do usuário. |
| `contacts.upsert` / `contacts.update` | Quando a lista de contatos é sincronizada ou um contato é atualizado (nome, foto). | Arrays de `Contact` ou `Partial<Contact>` | **Uso:** Atualizar a agenda de contatos local. |
| `messages.upsert` | **O evento mais importante.** Dispara quando uma nova mensagem é recebida ou enviada (por você em outro dispositivo). | `{ messages: WAMessage[]; type: MessageUpsertType; requestId?: string }` | **Uso:** Processar comandos de bot, exibir novas mensagens na UI, salvar no banco de dados. **Boa prática:** Verifique `type === 'notify'` para mensagens novas em tempo real (ignore 'append' se não quiser processar histórico). |
| `messages.update` | Quando o status de uma mensagem muda (e.g., entregue, lida, erro de descriptografia). | `WAMessageUpdate[]` | **Uso:** Atualizar os "ticks" (vistos) das mensagens enviadas na UI. |
| `messages.delete` | Quando uma mensagem é apagada (para todos ou apenas para mim). | `{ keys: WAMessageKey[] }` ou `{ jid: string; all: true }` | **Uso:** Remover a mensagem da UI ou marcá-la como "apagada". |
| `messages.reaction` | Quando alguém reage a uma mensagem. | `{ key: WAMessageKey; reaction: proto.IReaction }[]` | **Uso:** Atualizar a contagem de reações em uma mensagem específica. |
| `message-receipt.update` | Quando recibos de leitura/entrega são recebidos em lote. | `MessageUserReceiptUpdate[]` | **Uso:** Atualizar o status de leitura de mensagens em grupos. |
| `groups.upsert` / `groups.update` | Quando um grupo é criado ou seus metadados (nome, descrição, configurações) mudam. | Arrays de `GroupMetadata` ou `Partial<GroupMetadata>` | **Uso:** Manter as informações do grupo atualizadas no cache local. |
| `group-participants.update` | Quando participantes entram, saem, são promovidos ou rebaixados em um grupo. | `{ id, author, participants, action: 'add' \| 'remove' \| 'promote' \| 'demote' }` | **Uso:** Enviar mensagens de boas-vindas, atualizar a lista de membros na UI. |
| `call` | Quando uma chamada de voz/vídeo é recebida, aceita ou rejeitada. | `WACallEvent[]` | **Uso:** O Baileys não suporta chamadas de áudio/vídeo, mas você pode usar este evento para enviar uma mensagem automática dizendo "Não aceito chamadas por aqui". |

## PARTE 7 — AUTENTICAÇÃO

A autenticação no Baileys é um processo complexo que envolve o gerenciamento de estado criptográfico persistente para emular um dispositivo pareado.

### `useMultiFileAuthState`

Esta é a função utilitária recomendada (em `src/Utils/use-multi-file-auth-state.ts`) para gerenciar o estado de autenticação em um ambiente Node.js [2]. Em vez de salvar tudo em um único arquivo JSON gigante (o que causaria problemas de concorrência e uso excessivo de memória), ela salva as credenciais em múltiplos arquivos dentro de um diretório.

*   **Como funciona:** Ela cria um diretório (e.g., `auth_info_baileys`). O arquivo `creds.json` armazena as credenciais principais (chaves de identidade, token de roteamento). A pasta armazena arquivos individuais para cada chave do Signal Protocol (e.g., `app-state-sync-key-X.json`, `session-Y.json`, `sender-key-Z.json`).
*   **Vantagem:** Permite leituras e escritas atômicas e rápidas de chaves específicas, essencial para a performance e estabilidade do Signal Protocol.

### `AuthenticationState`

É a interface principal que encapsula todo o estado necessário para a conexão. Ela contém duas propriedades principais:

1.  **`creds` (`AuthenticationCreds`)**: As credenciais estáticas ou de rotação lenta.
2.  **`keys` (`SignalKeyStore`)**: Uma interface para acessar e modificar as chaves criptográficas dinâmicas (sessões, pre-keys).

### Signal Keys e `Keys` (`SignalKeyStore`)

O `SignalKeyStore` é uma abstração para o banco de dados de chaves do Signal Protocol. Ele define métodos `get` e `set` para acessar diferentes tipos de dados:

*   `pre-key`: Chaves de uso único.
*   `session`: O estado da sessão do Double Ratchet com um contato específico.
*   `sender-key` / `sender-key-memory`: Chaves usadas para criptografia de mensagens em grupos.
*   `app-state-sync-key` / `app-state-sync-version`: Chaves para sincronizar configurações do aplicativo (histórico, mutar chats, etc.).

### `Creds` (`AuthenticationCreds`)

O objeto `creds` (salvo em `creds.json`) contém a identidade fundamental do cliente:

*   **`noiseKey`**: Par de chaves Curve25519 usado para o handshake inicial do Noise Protocol.
*   **`signedIdentityKey`**: O par de chaves de identidade de longo prazo do Signal Protocol. Autentica o dispositivo para outros usuários.
*   **`signedPreKey`**: Uma chave de médio prazo, assinada pela `signedIdentityKey`, rotacionada periodicamente.
*   **`me`**: Informações sobre o próprio usuário (ID, nome).
*   **`account`**: Informações da conta, incluindo a assinatura do dispositivo (`device-identity`).

### Sessions

Uma **Sessão** (Session) no contexto do Signal Protocol representa o estado criptográfico compartilhado entre dois dispositivos (o seu e o do seu contato). Ela contém as chaves de cadeia (chain keys) e chaves de mensagem (message keys) do Double Ratchet Algorithm. Quando você envia ou recebe uma mensagem, o estado da sessão é atualizado (as catracas giram). Se a sessão for perdida ou corrompida, as mensagens não poderão ser descriptografadas.

### Device Identity

O `device-identity` é uma estrutura criptográfica que prova que o seu dispositivo (a instância do Baileys) foi legitimamente autorizado pelo telefone principal. Ele é gerado durante o pareamento (QR code) e é anexado a certas mensagens para provar a autenticidade do remetente [3].

### Signed Pre Key, Noise Key, Identity Key

*   **Noise Key**: Usada *apenas* para estabelecer a conexão segura com o servidor do WhatsApp (camada de transporte).
*   **Identity Key**: A raiz da sua identidade no Signal Protocol. Se vazar, alguém pode se passar por você.
*   **Signed Pre Key**: Usada por outros usuários para iniciar uma nova sessão E2EE com você quando você está offline. Ela é assinada pela sua Identity Key para provar que pertence a você.

### App State

O `App State` refere-se à sincronização de dados não-mensagem entre seus dispositivos (e.g., quais chats estão arquivados, quais contatos estão silenciados, histórico de mensagens). O WhatsApp usa chaves específicas (`app-state-sync-key`) para criptografar essas informações de estado, que são sincronizadas através de "mutações" (mutations) enviadas pelo servidor.

## PARTE 8 — ENVIO DE MENSAGENS

O envio de mensagens é orquestrado por um pipeline complexo que garante a formatação correta, criptografia e entrega.

### `sendMessage()`

Esta é a função de alto nível exposta pela API do Baileys (em `src/Socket/messages-send.ts`). Ela é o ponto de entrada para o desenvolvedor.

```typescript
// Exemplo de uso
await sock.sendMessage(jid, { text: 'Olá!' })
```

**O que ela faz:**
1.  Aceita o JID de destino e o conteúdo da mensagem (`AnyMessageContent`).
2.  Chama `generateWAMessage` para converter o conteúdo amigável em um objeto `proto.IMessage` estrito.
3.  Lida com opções adicionais (como responder a uma mensagem específica, menções).
4.  Delega o trabalho pesado para `relayMessage`.

### `generateWAMessage()`

Localizada em `src/Utils/generics.ts`, esta função atua como um tradutor. Ela pega o objeto de conveniência passado pelo usuário (e.g., `{ image: buffer, caption: 'Foto' }`) e constrói a estrutura exata exigida pelo Protocol Buffers do WhatsApp (`proto.IMessage`).

*   Para mídia, ela invoca as funções de upload e criptografia de mídia antes de construir o `proto.IMessage`.
*   Para mensagens de texto, ela simplesmente preenche o campo `conversation` ou `extendedTextMessage`.

### `relayMessage()`

Esta é a função central (em `src/Socket/messages-send.ts`) que executa a criptografia e o envio real [3].

**Fluxo profundo:**
1.  **Resolução de Dispositivos (`getUSyncDevices`)**: O WhatsApp é multi-dispositivo. Para enviar uma mensagem 1:1, o Baileys precisa saber quais são os dispositivos ativos do destinatário *e* os seus próprios outros dispositivos (para que a mensagem apareça no seu telefone também).
2.  **Criptografia (Signal Protocol)**:
    *   **1:1**: Itera sobre cada dispositivo descoberto. Garante que existe uma sessão Signal ativa (`assertSessions`). Criptografa o `proto.IMessage` individualmente para cada dispositivo usando `signalRepository.encryptMessage`.
    *   **Grupos**: Usa o Sender Key Protocol. Criptografa a mensagem uma única vez com a Sender Key do grupo (`signalRepository.encryptGroupMessage`). Se houver novos membros, gera e anexa uma `SenderKeyDistributionMessage` criptografada individualmente para eles.
3.  **Montagem do Stanza (`BinaryNode`)**: Empacota o conteúdo criptografado (o nó `<enc>`), a lista de participantes (nós `<to>`), a identidade do dispositivo (`<device-identity>`) e outros metadados em um nó XML binário `<message>`.
4.  **Envio**: Envia o nó binário através do WebSocket (`sendNode`).

### Upload de mídia, Criptografia, Thumbnail, Stream, Compressão

O envio de mídia (imagens, vídeos, documentos) segue um fluxo especial gerenciado por `src/Utils/messages-media.ts` [4]:

1.  **Stream**: A mídia é lida como um stream (de um arquivo local, URL ou buffer) para evitar carregar arquivos grandes inteiros na memória RAM.
2.  **Criptografia (`encryptedStream`)**:
    *   Uma `mediaKey` aleatória de 32 bytes é gerada.
    *   Chaves AES e HMAC são derivadas da `mediaKey` usando HKDF.
    *   O stream de mídia é lido em chunks, criptografado com AES-256-CBC, e um hash SHA256 é calculado em tempo real.
    *   O resultado criptografado é salvo em um arquivo temporário.
3.  **Upload**: O arquivo temporário criptografado é enviado para os servidores de mídia do WhatsApp via requisição HTTP POST. O servidor retorna uma URL de download.
4.  **Thumbnail (`generateThumbnail`)**: Para imagens e vídeos, o Baileys usa bibliotecas como `sharp`, `jimp` ou `ffmpeg` para gerar uma miniatura em base64.
5.  **Montagem**: O `proto.IMessage` é construído contendo a URL de download, a `mediaKey`, os hashes SHA256, o tamanho do arquivo e a thumbnail.
6.  **Envio**: Este `proto.IMessage` é então passado para `relayMessage` para ser criptografado com o Signal Protocol e enviado.

## PARTE 9 — RECEBIMENTO

O pipeline de recebimento é o inverso do envio, focado em decodificar, descriptografar e emitir eventos.

### O Pipeline Inteiro

1.  **Mensagem chega (WebSocket)**: O servidor do WhatsApp envia um frame binário através da conexão WebSocket.
2.  **`decodeBinaryNode` (WABinary)**: O frame bruto é passado para `src/WABinary/decode.ts`. Se estiver comprimido (zlib), é descomprimido. Em seguida, o parser lê as tags e tokens para reconstruir a estrutura de árvore XML (`BinaryNode`) [5].
3.  **`processNode` / `offlineNodeProcessor`**: O nó decodificado entra em uma fila de processamento. Isso garante que as mensagens sejam processadas em ordem, mesmo se chegarem em rajadas (especialmente durante a sincronização offline) [6].
4.  **`handleMessage` (Socket)**: O nó do tipo `<message>` é roteado para a função `handleMessage` em `src/Socket/messages-recv.ts` [6].
5.  **`decryptMessageNode` (Signal)**:
    *   Extrai o nó `<enc>` (que contém o payload criptografado).
    *   Identifica o tipo de criptografia (`pkmsg` para pre-key, `msg` para mensagem normal 1:1, `skmsg` para grupo).
    *   Usa o `signalRepository` para acessar a sessão correspondente e descriptografar o payload usando o Signal Protocol ou Sender Key.
    *   O resultado é um buffer que contém o `proto.IMessage` serializado.
6.  **`decode` (Protobuf)**: O buffer descriptografado é decodificado usando as definições do Protocol Buffers (`proto.Message.decode`), resultando em um objeto JavaScript/TypeScript utilizável (`WAMessage`).
7.  **Tratamento de Erros / Retries**: Se a descriptografia falhar (e.g., chaves ausentes), o Baileys envia um NACK ou um pedido de retry (`sendRetryRequest`) ao remetente.
8.  **Envio de Receipt**: Se a mensagem for processada com sucesso, o Baileys envia um recibo de entrega (`receipt`) de volta ao servidor.
9.  **`upsertMessage`**: A mensagem é formatada, limpa e salva no cache/store local.
10. **Event Emitter**: Finalmente, o evento `messages.upsert` é emitido com a mensagem pronta, notificando a aplicação do usuário.

## PARTE 10 — MÍDIA

O tratamento de mídia no Baileys é robusto e lida com a criptografia ponta a ponta exigida pelo WhatsApp.

### Imagem, Vídeo, Áudio, Documento, Sticker, PTT, GIF

Todos esses tipos de mídia compartilham o mesmo mecanismo subjacente de criptografia e upload/download, mas diferem na estrutura do `proto.IMessage` e nos metadados associados:

*   **Imagem (`imageMessage`)**: Requer thumbnail, dimensões (largura/altura) e mimetype (e.g., `image/jpeg`).
*   **Vídeo (`videoMessage`)**: Requer thumbnail, duração em segundos, mimetype (e.g., `video/mp4`) e pode ter a flag `gifPlayback` para se comportar como um GIF.
*   **Áudio (`audioMessage`)**: Requer duração. A flag `ptt` (Push-To-Talk) define se é uma mensagem de voz gravada na hora (aparece com o ícone de microfone) ou um arquivo de áudio normal.
*   **Documento (`documentMessage`)**: Requer mimetype, nome do arquivo (`fileName`) e tamanho.
*   **Sticker (`stickerMessage`)**: É essencialmente uma imagem WebP com metadados específicos. O Baileys não converte imagens para WebP automaticamente; você deve fornecer o buffer WebP correto.

### Upload e Criptografia

Como detalhado na Parte 8, o upload envolve gerar uma `mediaKey`, criptografar o arquivo localmente com AES-256-CBC, calcular hashes SHA256 e enviar o binário criptografado para os servidores do WhatsApp [4]. O servidor não tem acesso ao conteúdo real da mídia.

### Download e Descriptografia
O down
(Content truncated due to size limit. Use line ranges to read remaining content)