# Guia Técnico Completo da Biblioteca @whiskeysockets/baileys

## PARTE 1 — VISÃO GERAL

### O que é o Baileys

O Baileys é uma biblioteca TypeScript de código aberto, baseada em WebSockets, projetada para interagir com a API do WhatsApp Web. Ele permite que desenvolvedores criem aplicações que automatizam tarefas no WhatsApp, como enviar e receber mensagens, gerenciar grupos, e lidar com mídias, sem a necessidade de um navegador web (como Selenium ou Chromium) para manter a sessão ativa [1].

### Qual problema ele resolve

O WhatsApp não oferece uma API pública e oficial para automação em larga escala, especialmente para contas de usuário comuns (não Business API). O Baileys preenche essa lacuna, permitindo que desenvolvedores construam bots, sistemas de atendimento, e outras ferramentas que interagem com o WhatsApp de forma programática. Ele resolve o problema de **automação e integração** com o WhatsApp, oferecendo uma alternativa eficiente e de baixo consumo de recursos em comparação com soluções baseadas em navegadores [1].

### Como surgiu

O Baileys foi originalmente desenvolvido por Adiwajshing e surgiu como um projeto acadêmico na Ashoka University. Com o tempo, evoluiu para uma das bibliotecas mais populares para interação com o WhatsApp Web. Após a remoção do repositório original pelo autor, a comunidade assumiu a manutenção sob a organização WhiskeySockets, continuando o desenvolvimento e aprimoramento da biblioteca [1].

### Como funciona em alto nível

Em alto nível, o Baileys emula o comportamento de um cliente WhatsApp Web. Ele estabelece uma conexão WebSocket persistente com os servidores do WhatsApp. Através dessa conexão, ele envia e recebe mensagens binárias que são codificadas e decodificadas usando o Protocol Buffers (Protobuf) do WhatsApp. A biblioteca gerencia o ciclo de vida da conexão, autenticação (incluindo QR code e pairing code), criptografia de ponta a ponta (usando o Signal Protocol e Noise Protocol), e a persistência de sessão, permitindo que a aplicação se reconecte sem a necessidade de reautenticação constante [1].

### Quais tecnologias utiliza

O Baileys é construído principalmente com **TypeScript** e **Node.js**, aproveitando o ecossistema JavaScript moderno. As principais tecnologias e protocolos utilizados incluem:

*   **WebSockets**: Para manter uma conexão persistente e em tempo real com os servidores do WhatsApp.
*   **Protocol Buffers (Protobuf)**: Para serialização e desserialização eficiente das mensagens binárias trocadas com o WhatsApp.
*   **Noise Protocol Framework**: Utilizado para o handshake inicial e estabelecimento de uma sessão criptografada de transporte entre o cliente Baileys e o servidor do WhatsApp [2] [3].
*   **Signal Protocol**: Implementa a criptografia de ponta a ponta para as mensagens, garantindo a segurança e privacidade das comunicações [4] [5].
*   **Curve25519, AES-GCM, SHA256**: Algoritmos criptográficos fundamentais utilizados pelo Noise e Signal Protocols [3].
*   **NodeCache**: Para cache de dados, como metadados de grupo e informações de dispositivos [1].

### Como se comunica com o WhatsApp

A comunicação do Baileys com o WhatsApp ocorre diretamente via um **WebSocket** seguro. Diferente de outras bibliotecas que podem depender de um navegador (como `whatsapp-web.js` que usa Puppeteer/Selenium), o Baileys implementa o protocolo de comunicação do WhatsApp Web nativamente. Isso significa que ele constrói e interpreta os "stanzas" (nós XML binários) que o WhatsApp usa para trocar informações, autenticar, enviar e receber mensagens. O processo envolve um handshake inicial com o Noise Protocol para estabelecer uma camada de transporte segura, seguido pela troca de mensagens criptografadas pelo Signal Protocol [1] [2] [3] [4].

### Qual a diferença entre ele e a API oficial do WhatsApp

Existem diferenças cruciais entre o Baileys e a API oficial do WhatsApp (WhatsApp Business API):

| Característica        | Baileys                                       | WhatsApp Business API                               |
| :-------------------- | :-------------------------------------------- | :-------------------------------------------------- |
| **Tipo de Conta**     | Emula um cliente WhatsApp Web (conta pessoal) | Requer uma conta WhatsApp Business oficial          |
| **Aprovação**         | Não requer aprovação do WhatsApp             | Requer aprovação do WhatsApp para uso              |
| **Funcionalidades**   | Acesso a quase todas as funcionalidades do app | Funcionalidades específicas para negócios (templates, etc.) |
| **Custo**             | Gratuito (código aberto)                      | Baseado em volume de mensagens (pago)               |
| **Estabilidade**      | Sujeito a quebras com atualizações do WhatsApp | Mais estável, garantido pelo WhatsApp               |
| **Risco de Banimento**| Maior, se usado de forma abusiva/não oficial | Menor, uso oficial e permitido                      |
| **Escalabilidade**    | Limitada pela infraestrutura do desenvolvedor | Alta, gerenciada pelo WhatsApp                      |
| **Uso**               | Automação pessoal, bots, integrações customizadas | Atendimento ao cliente, marketing, notificações transacionais |

### Quando utilizar

O Baileys é ideal para cenários onde você precisa de **flexibilidade máxima** e controle sobre a interação com o WhatsApp, e quando a WhatsApp Business API não é viável ou necessária. Isso inclui:

*   **Bots e assistentes pessoais**: Para automatizar respostas, enviar lembretes, etc.
*   **Integrações customizadas**: Conectar o WhatsApp a sistemas internos, CRMs, etc., sem os custos ou restrições da API oficial.
*   **Projetos de pesquisa e desenvolvimento**: Para entender o funcionamento interno do WhatsApp ou experimentar novas funcionalidades.
*   **Baixo volume de mensagens**: Para uso pessoal ou pequenas operações onde o risco de banimento é gerenciável.

### Quando NÃO utilizar

Evite o Baileys em situações que exigem **alta estabilidade, garantia de entrega, conformidade legal** ou **uso em larga escala**:

*   **Aplicações críticas de negócios**: Onde a interrupção do serviço ou o banimento da conta seria catastrófico.
*   **Comunicação em massa (spam)**: O uso indevido pode levar ao banimento permanente da conta.
*   **Serviços que exigem conformidade com os Termos de Serviço do WhatsApp**: O Baileys não é uma ferramenta oficial e seu uso pode violar os termos.
*   **Projetos que exigem suporte oficial e SLAs**: A comunidade oferece suporte, mas não há garantias formais.

## PARTE 2 — COMO O WHATSAPP FUNCIONA

O WhatsApp Web, e por extensão o Baileys, opera sobre uma arquitetura cliente-servidor que utiliza uma combinação de tecnologias para garantir comunicação em tempo real, segurança e sincronização entre múltiplos dispositivos. Vamos detalhar os componentes chave:

### WebSocket

O **WebSocket** é um protocolo de comunicação que permite uma conexão full-duplex persistente entre um cliente (navegador web, Baileys) e um servidor através de uma única conexão TCP. Diferente do HTTP, que é stateless e baseado em requisição/resposta, o WebSocket mantém a conexão aberta, permitindo que o servidor envie dados para o cliente a qualquer momento, e vice-versa. Isso é fundamental para a natureza em tempo real do WhatsApp, onde mensagens e eventos precisam ser entregues instantaneamente [1].

### Handshake

O processo de **handshake** é a fase inicial de estabelecimento de uma conexão segura. No contexto do WhatsApp Web e Baileys, isso envolve o **Noise Protocol Framework** [2] [3]. Durante o handshake, o cliente e o servidor trocam chaves públicas Diffie-Hellman (DH) e realizam uma série de etapas criptográficas para derivar chaves de sessão compartilhadas. O objetivo é autenticar as partes e estabelecer um canal de comunicação criptografado e autenticado antes que qualquer dado sensível seja transmitido. O WhatsApp utiliza um padrão específico do Noise Protocol, frequentemente com Curve25519, AES-GCM e SHA256 [3].

### Criptografia

A criptografia no WhatsApp é de ponta a ponta (End-to-End Encryption - E2EE), implementada principalmente pelo **Signal Protocol** [4] [5]. Isso significa que apenas o remetente e o destinatário podem ler as mensagens, e nem mesmo o WhatsApp tem acesso ao conteúdo. A criptografia é aplicada tanto à camada de transporte (via Noise Protocol) quanto ao conteúdo das mensagens (via Signal Protocol).

### Noise Protocol

O **Noise Protocol Framework** é uma estrutura criptográfica para construir protocolos de canal seguro. Ele define uma série de padrões de handshake que especificam a ordem das mensagens e as operações criptográficas (troca de chaves DH, hashing, cifragem) que ocorrem durante o estabelecimento da conexão. O WhatsApp utiliza o Noise Protocol para proteger a comunicação entre o cliente e o servidor, garantindo que a sessão seja segura e autenticada desde o início [2] [3].

### Signal Protocol

O **Signal Protocol** é a base da criptografia de ponta a ponta do WhatsApp. Ele é um protocolo criptográfico que fornece confidencialidade, integridade, autenticidade, proteção de encaminhamento (forward secrecy) e proteção de retrocesso (future secrecy) para conversas assíncronas. Seus componentes chave incluem:

*   **Double Ratchet Algorithm**: Gera novas chaves de sessão para cada mensagem, garantindo forward e future secrecy.
*   **Pre-Keys**: Chaves pré-geradas e publicadas no servidor, permitindo que um remetente inicie uma conversa criptografada com um destinatário offline [4] [5].
*   **Signed Pre-Keys**: Chaves de médio prazo, assinadas pela chave de identidade, que são rotacionadas periodicamente [4] [5].
*   **Identity Keys**: Pares de chaves de longo prazo que autenticam a identidade de um usuário [4] [5].
*   **Ephemeral Keys**: Chaves de uso único geradas para cada sessão de handshake.

### Sessão

Uma **sessão** no WhatsApp representa o estado criptográfico e de autenticação entre um cliente e o servidor, ou entre dois clientes para comunicação E2EE. Para o WhatsApp Web/Baileys, a sessão é o conjunto de credenciais e chaves que permitem que o cliente se conecte e opere sem a necessidade de escanear o QR code repetidamente. Essas informações de sessão precisam ser persistidas localmente para permitir reconexões [1].

### Device Pairing

O **Device Pairing** é o processo de vincular um novo dispositivo (como o WhatsApp Web ou uma instância do Baileys) à sua conta principal do WhatsApp no seu telefone. Isso é feito escaneando um QR Code ou inserindo um código de pareamento. Durante este processo, o novo dispositivo troca chaves com o telefone principal e com o servidor do WhatsApp para estabelecer sua identidade e sincronizar o estado da conta [1].

### Multi Device

A funcionalidade **Multi Device** (ou Multi-Aparelhos) do WhatsApp permite que os usuários utilizem o WhatsApp em até quatro dispositivos não-telefone simultaneamente, mesmo que o telefone principal esteja offline. Isso é um avanço significativo, pois as versões anteriores do WhatsApp Web exigiam que o telefone estivesse conectado à internet. A arquitetura multi-dispositivo utiliza o Signal Protocol para garantir que as mensagens sejam criptografadas de ponta a ponta para todos os dispositivos de um usuário [6] [7].

### QR Code

O **QR Code** é o método principal para o Device Pairing. O cliente WhatsApp Web (ou Baileys) gera um QR code que contém informações criptográficas efêmeras. O usuário escaneia este QR code com o aplicativo WhatsApp no telefone principal, que então autoriza o novo dispositivo a se conectar e sincronizar a sessão [1].

### Login

O processo de **login** no WhatsApp Web/Baileys, após o pareamento inicial, envolve o uso das credenciais de sessão persistidas. O cliente envia essas credenciais ao servidor do WhatsApp para reestabelecer a conexão. Se as credenciais forem válidas, o servidor autentica o cliente e permite a sincronização de dados e a troca de mensagens [1].

### Tokens

No contexto do WhatsApp, **tokens** referem-se a vários identificadores e chaves criptográficas. Isso inclui tokens de sessão, tokens de autenticação e chaves derivadas dos protocolos Noise e Signal. Por exemplo, o `tctoken` (Transaction Control Token) é usado para controlar o envio de mensagens em conversas 1:1, especialmente em cenários de restrição de conta [8].

### Chaves públicas

As **chaves públicas** são componentes essenciais da criptografia de chave pública. No Signal Protocol, cada usuário possui um par de chaves de identidade (pública e privada) e publica chaves pré-assinadas (Signed Pre-Keys) e chaves de uso único (One-Time Pre-Keys) no servidor. Essas chaves públicas são usadas por outros usuários para iniciar sessões criptografadas [4] [5].

### Chaves privadas

As **chaves privadas** são mantidas em segredo pelo usuário e são usadas para descriptografar mensagens e assinar chaves públicas. A segurança do Signal Protocol depende da confidencialidade dessas chaves privadas [4] [5].

### Sincronização

A **sincronização** no WhatsApp garante que o estado da conversa (mensagens, contatos, grupos) seja consistente em todos os dispositivos do usuário. Com a arquitetura multi-dispositivo, a sincronização de histórico (`History Sync`) é um processo contínuo que permite que novos dispositivos recebam mensagens antigas e que o estado seja atualizado em tempo real [6] [7].

### Histórico

O **histórico** de mensagens é sincronizado entre os dispositivos. Quando um novo dispositivo é pareado, ele pode solicitar o histórico completo de mensagens do servidor do WhatsApp. O Baileys implementa mecanismos para lidar com essa sincronização de histórico, permitindo que a aplicação tenha acesso às conversas passadas [1].

### Eventos

O WhatsApp, e consequentemente o Baileys, opera com base em **eventos**. Quando algo acontece (uma nova mensagem chega, um status de entrega muda, um usuário fica online/offline), o servidor envia um evento para o cliente. O Baileys expõe esses eventos através de um `EventEmitter`, permitindo que a aplicação reaja a eles de forma assíncrona [1].

## PARTE 3 — COMO O BAILEYS IMPLEMENTA ISSO

O Baileys implementa os mecanismos do WhatsApp Web de forma programática, abstraindo a complexidade dos protocolos subjacentes. Vamos explorar como ele lida com as principais funcionalidades:

### Como cria conexão

A conexão é iniciada pela função `makeWASocket` [1]. Internamente, ela cria uma instância de `WebSocketClient` que tenta se conectar ao `waWebSocketUrl` (geralmente `wss://web.whatsapp.com/ws/chat`). O Baileys então inicia o processo de handshake do Noise Protocol para estabelecer um canal de comunicação seguro. O arquivo `src/Socket/socket.ts` é o coração desse processo, onde a função `makeSocket` gerencia a criação do WebSocket, o `noise` handler e o `validateConnection` para o handshake inicial [9].

### Como autentica

A autenticação no Baileys pode ocorrer de duas formas principais: **QR Code** ou **Pairing Code** [1].

1.  **QR Code**: O Baileys gera um QR code (ou dados para renderizá-lo) que o usuário escaneia com o aplicativo WhatsApp no telefone. Isso inicia o processo de pareamento, onde o telefone autoriza o Baileys como um novo dispositivo.
2.  **Pairing Code**: Uma alternativa ao QR code, onde um código numérico é exibido no terminal do Baileys e o usuário o insere no aplicativo WhatsApp no telefone.

Após o pareamento inicial, o Baileys armazena as credenciais de autenticação (`authState.creds`) e as chaves criptográficas (`authState.keys`). Em reconexões futuras, ele usa essas credenciais para autenticar automaticamente, sem a necessidade de um novo QR code [1]. O `validateConnection` em `src/Socket/socket.ts` lida com a lógica de login/registro [9].

### Como salva sessão

O Baileys utiliza um mecanismo de persistência para salvar o estado da sessão. A função `useMultiFileAuthState` (em `src/Utils/use-multi-file-auth-state.ts`) é uma utilidade que salva as credenciais e chaves em arquivos JSON separados dentro de uma pasta especificada. Isso inclui a `noiseKey`, `pairingEphemeralKeyPair`, `signedIdentityKey`, `signedPreKey`, `registrationId`, `advSecretKey`, e outras informações de estado. Sempre que as credenciais são atualizadas (por exemplo, após o envio/recebimento de mensagens que exigem a rotação de chaves Signal), o evento `creds.update` é disparado, e a função `saveCreds` é chamada para persistir as alterações [1] [10].

### Como restaura sessão

Para restaurar uma sessão, o Baileys carrega as credenciais e chaves salvas do armazenamento persistente (geralmente arquivos JSON). Ao inicializar `makeWASocket`, o `authState` é passado, e a biblioteca tenta usar essas informações para se conectar. Se as credenciais forem válidas, a conexão é estabelecida sem a necessidade de um novo pareamento [1].

### Como renova chaves

O Signal Protocol, usado pelo WhatsApp, envolve a rotação de chaves para garantir a segurança. O Baileys gerencia a renovação de chaves automaticamente. Por exemplo, ele monitora o número de Pre-Keys disponíveis no servidor do WhatsApp e, se o número cair abaixo de um limite (`MIN_PREKEY_COUNT`), ele gera e faz upload de novas Pre-Keys. A função `uploadPreKeys` em `src/Socket/socket.ts` é responsável por essa lógica [9]. Além disso, as chaves de sessão do Double Ratchet Algorithm são rotacionadas a cada mensagem enviada/recebida.

### Como recebe eventos

O Baileys utiliza um `EventEmitter` para notificar a aplicação sobre diversos eventos que ocorrem na conexão ou com as mensagens. O `makeEventBuffer` em `src/Socket/socket.ts` cria um buffer de eventos para otimizar o processamento. Os eventos são tipados (definidos em `src/Types/Events.ts`) e incluem `connection.update`, `creds.update`, `messages.upsert`, `message-receipt.update`, `groups.update`, entre outros [1] [11]. O `processNode` e `handleMessage` em `src/Socket/messages-recv.ts` são responsáveis por decodificar os nós binários recebidos do WebSocket e emitir os eventos correspondentes [12].

### Como envia mensagens

O envio de mensagens é um processo complexo que envolve a preparação da mensagem, criptografia e o envio através do WebSocket. A função `sendMessage` em `src/Socket/messages-send.ts` é o ponto de entrada principal. Ela chama `generateWAMessage` para construir o objeto `WAMessage` e, em seguida, delega para `relayMessage` [13].

O `relayMessage` (em `src/Socket/messages-send.ts`) é o coração do envio. Ele:

1.  **Resolve Destinatários**: Identifica todos os dispositivos dos destinatários (incluindo dispositivos múltiplos para o mesmo usuário) usando `getUSyncDevices`.
2.  **Criptografia**: Para mensagens 1:1, usa o Signal Protocol (`signalRepository.encryptMessage`). Para grupos, usa o Sender Key Distribution Message (`signalRepository.encryptGroupMessage`).
3.  **Monta Stanza XMPP**: Constrói o nó binário (`BinaryNode`) que representa a mensagem, incluindo o conteúdo criptografado, `device-identity`, `tctoken` (se aplicável) e outros atributos.
4.  **Envia via WebSocket**: Utiliza `sendNode` para enviar o nó binário através da conexão WebSocket [13].

### Como envia mídia

O envio de mídia (imagens, vídeos, áudios, documentos) envolve etapas adicionais de upload e criptografia. As funções em `src/Utils/messages-media.ts` são responsáveis por isso [14].

1.  **Upload**: A mídia é primeiro carregada para os servidores de mídia do WhatsApp. O Baileys gera uma chave de mídia (`mediaKey`), criptografa o arquivo localmente (`encryptedStream`), calcula hashes (SHA256 do arquivo original e criptografado) e, em seguida, faz o upload do conteúdo criptografado. O `getWAUploadToServer` é usado para obter a URL de upload [14].
2.  **Geração de Thumbnail**: Para imagens e vídeos, uma thumbnail é gerada (`generateThumbnail`, `extractImageThumb`, `extractVideoThumb`) e incluída na mensagem para visualização prévia [14].
3.  **Construção da Mensagem**: A mensagem de mídia inclui a URL do arquivo carregado, hashes, tamanho do arquivo, chave de mídia e a thumbnail. Essa estrutura é então criptografada e enviada como uma mensagem normal via `relayMessage` [13].

### Como envia documentos, áudio, vídeo, sticker, localização, contato, botões, listas, reactions, mensagens temporárias, grupos e broadcast

Todas essas funcionalidades seguem o mesmo pipeline geral de envio de mensagens, mas com diferentes estruturas de `proto.IMessage` e `WAMessageContent`. O Baileys encapsula a complexidade de construir esses objetos `proto` para cada tipo de mensagem. Por exemplo:

*   **Documentos, Áudio, Vídeo, Sticker**: São tratados como mídia, passando pelo processo de upload e criptografia descrito acima, mas com tipos de mídia (`MediaType`) específicos.
*   **Localização, Contato**: São mensagens estruturadas com dados específicos para cada tipo.
*   **Botões, Listas**: Utilizam estruturas de mensagens interativas definidas pelo WhatsApp.
*   **Reactions**: São mensagens de protocolo que atualizam o estado de uma mensagem existente.
*   **Mensagens Temporárias**: O Baileys permite definir a duração efêmera para chats ou mensagens específicas.
*   **Mensagem para Grupos**: Usa o `relayMessage` com a lógica de criptografia de grupo (Sender Key).
*   **Broadcast**: Similar ao envio para grupos, mas para listas de transmissão.

O `generateWAMessage` em `src/Utils/generics.ts` é a função que orquestra a criação dessas diferentes estruturas de mensagem antes de serem passadas para `relayMessage` [13].

### Como faz download de mídia

O download de mídia é o processo inverso do upload. Quando uma mensagem de mídia é recebida, ela contém a URL do arquivo criptografado nos servidores do WhatsApp, a chave de mídia e os hashes. O Baileys usa as funções em `src/Utils/messages-media.ts` para:

1.  **Baixar o arquivo**: Faz uma requisição HTTP para a URL do arquivo criptografado.
2.  **Descriptografar**: Utiliza a `mediaKey` e os algoritmos (AES-GCM) para descriptografar o conteúdo baixado (`aesDecryptGCM`).
3.  **Verificar Integridade**: Compara os hashes do arquivo descriptografado com os hashes fornecidos na mensagem para garantir que o arquivo não foi adulterado [14].

### Como descriptografa mídia

A descriptografia de mídia é realizada usando a `mediaKey` fornecida na mensagem de mídia. A função `getMediaKeys` em `src/Utils/messages-media.ts` deriva as chaves `cipherKey`, `iv` e `macKey` a partir da `mediaKey` usando HKDF. Em seguida, `aesDecryptGCM` é usada para descriptografar o conteúdo do arquivo [14].

### Como descriptografa mensagens

A descriptografia de mensagens é uma parte crítica do `handleMessage` em `src/Socket/messages-recv.ts`. Para mensagens 1:1, o Signal Protocol é usado para descriptografar o conteúdo. Para mensagens de grupo, o Sender Key é utilizado. O `decryptMessageNode` é a função central que lida com essa lógica, utilizando o `signalRepository` para acessar as chaves de sessão corretas e realizar a descriptografia [12].

### Como processa mensagens recebidas

O processamento de mensagens recebidas é orquestrado pela função `handleMessage` em `src/Socket/messages-recv.ts`. O fluxo geral é:

1.  **Decodificação**: O nó binário recebido do WebSocket é decodificado.
2.  **Descriptografia**: `decryptMessageNode` tenta descriptografar a mensagem. Se a descriptografia falhar (por exemplo, chaves ausentes), o Baileys pode solicitar um reenvio ou enviar um NACK (Negative Acknowledgement) [12].
3.  **LID Mapping**: Se a mensagem contiver informações de mapeamento LID (Linked Identity), o Baileys as armazena.
4.  **Gerenciamento de Retentativas**: Se a mensagem for uma retentativa, o `messageRetryManager` é atualizado.
5.  **Reenvio de Placeholder**: Para mensagens indisponíveis (placeholders), o Baileys pode solicitar o reenvio do conteúdo completo do telefone.
6.  **Envio de Receipts**: Após o processamento bem-sucedido, um receipt (entrega, leitura) é enviado de volta ao remetente.
7.  **Upsert**: A mensagem processada é então "upserted" (inserida ou atualizada) no armazenamento local da aplicação, e o evento `messages.upsert` é emitido [12].

### Como trata eventos

Os eventos são tratados pelo `BaileysEventEmitter` [11]. A aplicação se "escuta" a eventos específicos (e.g., `sock.ev.on('messages.upsert', handler)`). Quando um evento é emitido internamente pelo Baileys (após o processamento de um nó recebido ou uma mudança de estado), o handler registrado é invocado. O `processNodeWithBuffer` em `src/Socket/messages-recv.ts` garante que os eventos sejam processados de forma eficiente, potencialmente em buffer [12].

### Como trata desconexões

Desconexões são tratadas pelo `WebSocketClient` e pelo `makeSocket` em `src/Socket/socket.ts`. O Baileys monitora o estado da conexão WebSocket. Em caso de desconexão, ele tenta reconectar automaticamente. O evento `connection.update` é emitido com o `DisconnectReason` apropriado, informando a aplicação sobre o motivo da desconexão (e.g., `loggedOut`, `timedOut`, `connectionClosed`) [1] [9].

### Como faz reconnect

O Baileys possui uma lógica de reconexão embutida. Após uma desconexão, ele tenta restabelecer a conexão WebSocket e reautenticar usando as credenciais de sessão salvas. O `startKeepAliveRequest` em `src/Socket/socket.ts` também garante que a conexão seja mantida ativa enviando pings periódicos [9].

## PARTE 4 — ARQUITETURA

A arquitetura do Baileys é modular e em camadas, projetada para emular o cliente WhatsApp Web de forma eficiente e robusta. Ela é construída em torno de um núcleo de comunicação WebSocket e um sistema de gerenciamento de estado criptográfico.

### Estrutura de pastas

A estrutura de pastas do repositório Baileys reflete sua modularidade:

*   `src/`: Contém o código-fonte principal da biblioteca.
    *   `Defaults/`: Constantes e configurações padrão.
    *   `Signal/`: Implementação do Signal Protocol e gerenciamento de chaves.
    *   `Socket/`: Onde reside a lógica central de conexão, envio e recebimento de mensagens, dividida em módulos como `socket.ts`, `messages-send.ts`, `messages-recv.ts`, `groups.ts`, etc.
    *   `Types/`: Definições de tipos TypeScript para todas as estruturas de dados e eventos.
    *   `Utils/`: Funções utilitárias para criptografia, manipulação de mídia, autenticação, etc.
    *   `WABinary/`: Lógica para codificação e decodificação do protocolo binário do WhatsApp.
    *   `WAM/`: Modelos de dados para telemetria do WhatsApp.
    *   `WAUSync/`: Implementação do protocolo USync para sincronização de usuários e dispositivos.
*   `WAProto/`: Definições de Protocol Buffers (`.proto`) do WhatsApp, compiladas para TypeScript.
*   `Example/`: Exemplos de uso da biblioteca.

### Responsabilidades

Cada módulo e camada tem responsabilidades bem definidas:

*   **`Socket`**: Gerencia a conexão WebSocket, o handshake, a autenticação, o envio e recebimento de nós binários (stanzas) e a emissão de eventos de alto nível.
*   **`Signal`**: Lida com toda a complexidade do Signal Protocol, incluindo gerenciamento de chaves (Identity, Signed Pre, One-Time Pre, Sender Keys), criptografia e descriptografia de mensagens de ponta a ponta.
*   **`WABinary`**: Responsável pela serialização e desserialização dos dados no formato binário do WhatsApp (Protocol Buffers).
*   **`Utils`**: Contém funções auxiliares para tarefas como manipulação de mídia, gerenciamento de estado de autenticação, criptografia de baixo nível e processamento de dados.
*   **`Types`**: Garante a segurança de tipo e a clareza da API, definindo interfaces para todos os objetos e eventos.

### Camadas

A arquitetura pode ser vista em camadas, do mais baixo nível de comunicação ao mais alto nível de abstração:

1.  **Camada de Transporte (WebSocket + Noise Protocol)**: Gerencia a conexão física e o canal de comunicação seguro.
2.  **Camada de Protocolo Binário (WABinary)**: Codifica e decodifica os dados brutos trocados com o servidor.
3.  **Camada Criptográfica (Signal Protocol)**: Lida com a criptografia de ponta a ponta das mensagens.
4.  **Camada de Lógica de Negócios (Socket)**: Orquestra o fluxo de mensagens, autenticação, gerenciamento de sessão e eventos.
5.  **Camada de Utilidades (Utils)**: Fornece ferramentas para tarefas específicas como mídia, autenticação, etc.
6.  **Camada de Aplicação (Seu Código)**: Interage com a API de alto nível do Baileys para construir a funcionalidade desejada.

### Fluxo interno

O fluxo interno de uma mensagem, por exemplo, segue um pipeline:

*   **Envio**: `Sua Aplicação` -> `sendMessage` -> `relayMessage` -> `Signal` (criptografia) -> `WABinary` (codificação) -> `Socket` (envio via WebSocket).
*   **Recebimento**: `Socket` (recebe via WebSocket) -> `WABinary` (decodificação) -> `Signal` (descriptografia) -> `handleMessage` -> `Sua Aplicação` (via eventos).

### Módulos

Os módulos são as unidades lógicas de código, como `Socket`, `Signal`, `WABinary`, `Utils`, cada um com um conjunto coeso de funcionalidades.

### Dependências

O Baileys gerencia suas dependências internas (como `@hapi/boom` para erros, `NodeCache` para cache) e externas (como `music-metadata` para áudio, `sharp`/`jimp` para processamento de imagem) de forma modular. As dependências são declaradas no `package.json` e gerenciadas pelo `yarn`.

### Injeção de dependência

Embora não utilize um framework de injeção de dependência formal, o Baileys emprega um padrão de injeção de dependência manual. A função `makeSocket` (e suas camadas subsequentes como `makeMessagesSocket`, `makeNewsletterSocket`) recebe um objeto `config` que contém dependências como `logger`, `authState`, `signalRepository`, etc. Isso permite que a biblioteca seja flexível e testável, pois as dependências podem ser facilmente substituídas ou mockadas.

### Tipagem

Sendo uma biblioteca TypeScript, o Baileys é fortemente tipado. As definições de tipo em `src/Types/` são extensas e cobrem todas as estruturas de dados, parâmetros de funções e eventos. Isso proporciona autocompletar, validação em tempo de compilação e melhora a manutenibilidade do código.

### Interfaces

As interfaces são amplamente utilizadas para definir contratos de dados e comportamentos, como `AuthenticationCreds`, `WAMessage`, `BaileysEventMap`. Isso promove a consistência e facilita a integração com outras partes do sistema.

### Classes

O Baileys utiliza classes para encapsular lógica e estado, como `WebSocketClient`, `USyncQuery`, `MessageRetryManager`. No entanto, muitas funcionalidades são implementadas como funções puras ou factories (`makeSocket`, `makeNoiseHandler`) que retornam objetos com métodos, seguindo um estilo mais funcional.

### Funções

Funções são a espinha dorsal do Baileys, com muitas utilidades e lógicas centrais implementadas como funções puras ou com efeitos colaterais controlados. Exemplos incluem `generateMessageIDV2`, `encodeWAMessage`, `decryptMessageNode`.

### Helpers e Utils

Os diretórios `src/Utils/` contêm uma vasta coleção de funções auxiliares (`helpers`) e utilitários (`utils`) que realizam tarefas específicas, como criptografia (`crypto.ts`), manipulação de JIDs (`jid-utils.ts`), gerenciamento de mídia (`messages-media.ts`), e lógica de autenticação (`auth-utils.ts`).

### Middlewares internos

Embora não explicitamente chamados de "middlewares", o Baileys utiliza padrões semelhantes a pipelines para processar dados. Por exemplo, o `makeEventBuffer` atua como um middleware para eventos, e as funções de processamento de nós (`processNode`) em `messages-recv.ts` podem ser vistas como etapas em um pipeline de processamento de mensagens.

### Eventos

O sistema de eventos (`BaileysEventEmitter`) é um componente arquitetural chave, permitindo que diferentes partes da biblioteca e a aplicação do usuário se comuniquem de forma desacoplada. Ele segue o padrão Observer, onde os listeners reagem a mudanças de estado ou ocorrências importantes [11].

### Pipeline

O Baileys organiza o fluxo de dados em pipelines lógicos. Por exemplo, o pipeline de envio de mensagens envolve a geração, criptografia, empacotamento binário e envio. O pipeline de recebimento envolve a recepção, decodificação binária, descriptografia, processamento e emissão de eventos. Esses pipelines garantem um fluxo de trabalho estruturado e previsível.

## PARTE 5 — ESTUDO DE CÓDIGO

Para entender o Baileys em profundidade, vamos analisar alguns dos principais arquivos e fluxos de código, focando em como as partes teóricas são implementadas na prática.

### `src/Socket/socket.ts` - O Coração da Conexão

Este arquivo é o ponto de entrada para a criação de uma instância de socket do Baileys e gerencia o ciclo de vida da conexão WebSocket. A função `makeSocket` é a factory principal.

```typescript
// src/Socket/socket.ts

import { Boom } from '@hapi/boom'
import { randomBytes } from 'crypto'
import { URL } from 'url'
import { promisify } from 'util'
import { proto } from '../../WAProto/index.js'
import {
	DEF_CALLBACK_PREFIX,
	DEF_TAG_PREFIX,
	INITIAL_PREKEY_COUNT,
	MIN_PREKEY_COUNT,
	NOISE_WA_HEADER,
	PROCESSABLE_HISTORY_TYPES,
	TimeMs,
	UPLOAD_TIMEOUT
} from '../Defaults'
import {
	type LIDMapping,
	type NewChatMessageCapInfo,
	QueryIds,
	ReachoutTimelockEnforcementType,
	type ReachoutTimelockState,
	type SocketConfig
} from '../Types'
import { DisconnectReason, XWAPaths } from '../Types'
import {
	addTransactionCapability,
	aesEncryptCTR,
	bindWaitForConnectionUpdate,
	buildPairingQRData,
	bytesToCrockford,
	configureSuccessfulPairing,
	Curve,
	derivePairingCodeKey,
	generateLoginNode,
	generateMdTagPrefix,
	generateRegistrationNode,
	getCodeFromWSError,
	getCompanionPlatformId,
	getErrorCodeFromStreamError,
	getNextPreKeysNode,
	makeEventBuffer,
	makeNoiseHandler,
	promiseTimeout,
	signedKeyPair,
	xmppSignedPreKey
} from '../Utils'
import {
	assertNodeErrorFree,
	type BinaryNode,
	binaryNodeToString,
	encodeBinaryNode,
	getAllBinaryNodeChildren,
	getBinaryNodeChild,
	getBinaryNodeChildren,
	isLidUser,
	jidDecode,
	jidEncode,
	S_WHATSAPP_NET
} from '../WABinary'
import { BinaryInfo } from '../WAM/BinaryInfo.js'
import { USyncQuery, USyncUser } from '../WAUSync/'
import { WebSocketClient } from './Client'
import { executeWMexQuery } from './mex.js'

/**
 * Connects to WA servers and performs:
 * - simple queries (no retry mechanism, wait for connection establishment)
 * - listen to messages and emit events
 * - query phone connection
 */

export const makeSocket = (config: SocketConfig) => {
		const {
			waWebSocketUrl,
			connectTimeoutMs,
			logger,
			keepAliveIntervalMs,
			browser,
			auth: authState,
			printQRInTerminal,
			defaultQueryTimeoutMs,
			transactionOpts,
			qrTimeout,
			makeSignalRepository
		} = config

		// ... (outras inicializações)

		/** ephemeral key pair used to encrypt/decrypt communication. Unique for each connection */
		const ephemeralKeyPair = Curve.generateKeyPair()
		/** WA noise protocol wrapper */
		const noise = makeNoiseHandler({
			keyPair: ephemeralKeyPair,
			NOISE_HEADER: NOISE_WA_HEADER,
			logger,
			routingInfo: authState?.creds?.routingInfo
		})

		const ws = new WebSocketClient(url, config)

		ws.connect()

		// ... (funções sendRawMessage, sendNode, waitForMessage, query)

		/** connection handshake */
		const validateConnection = async () => {
			let helloMsg: proto.IHandshakeMessage = {
				clientHello: { ephemeral: ephemeralKeyPair.public }
			}
			helloMsg = proto.HandshakeMessage.fromObject(helloMsg)

			logger.info({ browser, helloMsg }, 'connected to WA')

			const init = proto.HandshakeMessage.encode(helloMsg).finish()

			const result = await awaitNextMessage<Uint8Array>(init)
			const handshake = proto.HandshakeMessage.decode(result)

			logger.trace({ handshake }, 'handshake recv from WA')

			const keyEnc = noise.processHandshake(handshake, creds.noiseKey)

			let node: proto.IClientPayload
			if (!creds.me) {
				node = generateRegistrationNode(creds, config)
				logger.info({ node }, 'not logged in, attempting registration...')
			} else {
				node = generateLoginNode(creds.me.id, config)
				logger.info({ node }, 'logging in...')
			}

			const payloadEnc = noise.encrypt(proto.ClientPayload.encode(node).finish())
			await sendRawMessage(
				proto.HandshakeMessage.encode({
					clientFinish: {
						static: keyEnc,
						payload: payloadEnc
					}
				}).finish()
			)
			await noise.finishInit()
			startKeepAliveRequest()
		}

		// ... (outras funções e retorno da API do socket)
}
```

**Explicação:**

*   **`makeSocket`**: Esta função é o construtor principal que recebe um objeto `SocketConfig` com todas as configurações necessárias (URL do WebSocket, logger, estado de autenticação, etc.).
*   **`ephemeralKeyPair`**: Um par de chaves efêmeras é gerado para cada conexão. Essas chaves são de curto prazo e usadas apenas para o handshake do Noise Protocol.
*   **`noise = makeNoiseHandler(...)`**: Cria uma instância do handler do Noise Protocol, que é responsável por gerenciar o estado criptográfico do handshake e da comunicação de transporte. Ele usa o `ephemeralKeyPair` e a `noiseKey` persistida do `authState`.
*   **`ws = new WebSocketClient(url, config)`**: Instancia o cliente WebSocket que gerencia a conexão de rede real.
*   **`ws.connect()`**: Inicia a conexão WebSocket.
*   **`validateConnection`**: Esta função assíncrona executa o handshake do Noise Protocol:
    *   Envia um `ClientHello` com a chave pública efêmera do cliente.
    *   Recebe um `HandshakeMessage` do servidor.
    *   `noise.processHandshake` processa a mensagem do servidor, derivando as chaves de sessão de transporte.
    *   Constrói um `ClientPayload` (`generateRegistrationNode` para primeiro login ou `generateLoginNode` para reconexões) que contém informações de autenticação.
    *   Criptografa o `ClientPayload` usando `noise.encrypt` e o envia em um `ClientFinish`.
    *   `noise.finishInit()` finaliza o handshake, e `startKeepAliveRequest()` inicia o mecanismo de keep-alive para manter a conexão viva.

**Fluxo:**

1.  A aplicação chama `makeWASocket`.
2.  Um `WebSocketClient` é criado e tenta conectar.
3.  `validateConnection` é chamado para iniciar o handshake criptográfico.
4.  Chaves efêmeras são trocadas, e o `Noise Protocol` estabelece um canal seguro.
5.  O cliente envia seu payload de login/registro, criptografado com as chaves do Noise.
6.  A conexão é estabelecida, e o `startKeepAliveRequest` é iniciado.

**Dependências:**

*   `WebSocketClient`: Gerencia a conexão de rede.
*   `makeNoiseHandler`: Lida com o Noise Protocol.
*   `authState`: Contém as credenciais e chaves de autenticação persistidas.
*   `proto`: Definições de Protocol Buffers para as mensagens do handshake.

### `src/WABinary/decode.ts` - Decodificação do Protocolo Binário

Este arquivo é crucial para entender como o Baileys interpreta os dados brutos recebidos do WebSocket. O WhatsApp usa um formato binário compacto para suas mensagens, e este módulo é responsável por convertê-lo em uma estrutura de `BinaryNode` mais legível.

```typescript
// src/WABinary/decode.ts

import { promisify } from 'util'
import { inflate } from 'zlib'
import * as constants from './constants'
import { jidEncode, type JidServer, WAJIDDomains } from './jid-utils'
import type { BinaryNode, BinaryNodeCodingOptions } from './types'

const inflatePromise = promisify(inflate)

export const decompressingIfRequired = async (buffer: Buffer) => {
	if (2 & buffer.readUInt8()) {
		buffer = await inflatePromise(buffer.slice(1))
	} else {
		// nodes with no compression have a 0x00 prefix, we remove that
		buffer = buffer.slice(1)
	}

	return buffer
}

export const decodeDecompressedBinaryNode = (
		buffer: Buffer,
		opts: Pick<BinaryNodeCodingOptions, 'DOUBLE_BYTE_TOKENS' | 'SINGLE_BYTE_TOKENS' | 'TAGS'>,
		indexRef: { index: number } = { index: 0 }
	): BinaryNode => {
		const { DOUBLE_BYTE_TOKENS, SINGLE_BYTE_TOKENS, TAGS } = opts

		// ... (funções auxiliares para ler bytes, ints, strings, etc.)

		const readString = (tag: number): string => {
			if (tag >= 1 && tag < SINGLE_BYTE_TOKENS.length) {
				return SINGLE_BYTE_TOKENS[tag] || ''
			}

			switch (tag) {
				// ... (casos para diferentes tipos de tags, incluindo dicionários, binários, JIDs)
				case TAGS.JID_PAIR:
					return readJidPair()
				// ...
				default:
					throw new Error('invalid string with tag: ' + tag)
			}
		}

		const listSize = readListSize(readByte()!)
		const header = readString(readByte()!)
		if (!listSize || !header.length) {
			throw new Error('invalid node')
		}

		const attrs: BinaryNode['attrs'] = {}
		let data: BinaryNode['content']

		// ... (leitura de atributos)

		// ... (leitura de conteúdo)

		return {
			tag: header,
			attrs,
			content: data
		}
	}

export const decodeBinaryNode = async (buff: Buffer): Promise<BinaryNode> => {
		const decompBuff = await decompressingIfRequired(buff)
		return decodeDecompressedBinaryNode(decompBuff, constants)
	}
```

**Explicação:**

*   **`decodeBinaryNode`**: Esta é a função principal para decodificar um buffer binário completo. Ela primeiro verifica se o buffer está comprimido (`decompressingIfRequired`) e, em seguida, passa o buffer descomprimido para `decodeDecompressedBinaryNode`.
*   **`decompressingIfRequired`**: Verifica o primeiro byte do buffer para determinar se ele está comprimido (usando `zlib.inflate`). Se estiver, ele descomprime o restante do buffer. Caso contrário, remove o byte de prefixo.
*   **`decodeDecompressedBinaryNode`**: Esta função recursiva lê o buffer byte a byte para construir o `BinaryNode`:
    *   **`readListSize`**: Lê o tamanho da lista (número de elementos) do nó.
    *   **`readString`**: Lê strings, que podem ser codificadas de várias maneiras (tokens de byte único, tokens de byte duplo, binário, JIDs).
    *   **Atributos**: Itera para ler os pares chave-valor dos atributos do nó.
    *   **Conteúdo**: Lê o conteúdo do nó, que pode ser uma lista de outros `BinaryNode`s, um buffer binário ou uma string.

**Fluxo:**

1.  Um buffer binário é recebido do WebSocket.
2.  `decodeBinaryNode` é chamado.
3.  O buffer é descomprimido, se necessário.
4.  `decodeDecompressedBinaryNode` parseia o buffer, identificando tags, atributos e conteúdo recursivamente.
5.  Um objeto `BinaryNode` é retornado, representando a estrutura da mensagem do WhatsApp.

**Dependências:**

*   `zlib`: Para descompressão.
*   `constants`: Contém os mapeamentos de tokens e tags usados na codificação binária.
*   `jid-utils`: Para codificação/decodificação de JIDs (WhatsApp IDs).

### `src/Socket/messages-send.ts` - O Pipeline de Envio de Mensagens

Este arquivo contém a lógica para construir, criptografar e enviar mensagens de todos os tipos. A função `relayMessage` é central para este processo.

```typescript
// src/Socket/messages-send.ts

import NodeCache from '@cacheable/node-cache'
import { Boom } from '@hapi/boom'
import { proto } from '../../WAProto/index.js'
import { DEFAULT_CACHE_TTLS, WA_DEFAULT_EPHEMERAL } from '../Defaults'
import type {
	AnyMessageContent,
	MediaConnInfo,
	MessageReceiptType,
	MessageRelayOptions,
	MiscMessageGenerationOptions,
	SocketConfig,
	WAMessage,
	WAMessageKey
} from '../Types'
import {
	aggregateMessageKeysNotFromMe,
	assertMediaContent,
	assertMeId,
	bindWaitForEvent,
	decryptMediaRetryData,
	DEF_MEDIA_HOST,
	encodeNewsletterMessage,
	encodeSignedDeviceIdentity,
	encodeWAMessage,
	encryptMediaRetryRequest,
	extractDeviceJids,
	generateMessageIDV2,
	generateParticipantHashV2,
	generateWAMessage,
	getStatusCodeForMediaRetry,
	getUrlFromDirectPath,
	getWAUploadToServer,
	MessageRetryManager,
	normalizeMessageContent,
	parseAndInjectE2ESessions,
	unixTimestampSeconds
} from '../Utils'
import { getUrlInfo } from '../Utils/link-preview'
import { makeKeyedMutex, makeMutex } from '../Utils/make-mutex'
import { getMessageReportingToken, shouldIncludeReportingToken } from '../Utils/reporting-utils'
import {
	buildMergedTcTokenIndexWrite,
	isTcTokenExpired,
	resolveIssuanceJid,
	resolveTcTokenJid,
	shouldSendNewTcToken,
	storeTcTokensFromIqResult
} from '../Utils/tc-token-utils'
import {
	areJidsSameUser,
	type BinaryNode,
	type BinaryNodeAttributes,
	type FullJid,
	getBinaryNodeChild,
	getBinaryNodeChildren,
	isHostedLidUser,
	isHostedPnUser,
	isJidBot,
	isJidGroup,
	isJidMetaAI,
	isLidUser,
	isPnUser,
	jidDecode,
	jidEncode,
	jidNormalizedUser,
	type JidWithDevice,
	PSA_WID,
	S_WHATSAPP_NET
} from '../WABinary'
import { USyncQuery, USyncUser } from '../WAUSync'
import { makeNewsletterSocket } from './newsletter'

// ... (outras inicializações e funções auxiliares)

export const makeMessagesSocket = (config: SocketConfig) => {
		// ... (inicialização do socket base e outras variáveis)

		const relayMessage = async (
			jid: string,
			message: proto.IMessage,
			{
				messageId: msgId,
				participant,
				additionalAttributes,
				additionalNodes,
				useUserDevicesCache,
				useCachedGroupMetadata,
				statusJidList
			}: MessageRelayOptions
		) => {
			const meId = assertMeId(authState.creds)
			const meLid = authState.creds.me?.lid
			// ... (determinação de tipos de JID, inicialização de arrays)

			await authState.keys.transaction(async () => {
				// ... (lógica para newsletters, mensagens de pin/reaction)

				if (isGroupOrStatus && !isRetryResend) {
					// ... (lógica para grupos e status: obter metadados, participantes, criptografia Sender Key)
					const { ciphertext, senderKeyDistributionMessage } = await signalRepository.encryptGroupMessage({
						group: destinationJid,
						data: bytes,
						meId: groupSenderIdentity
					})
					// ... (adicionar Sender Key Distribution Message se necessário)
					binaryNodeContent.push({
						tag: 'enc',
						attrs: { v: '2', type: 'skmsg', ...extraAttrs },
						content: ciphertext
					})
					// ... (salvar sender-key-memory)
				} else {
					// ... (lógica para 1:1: enumerar dispositivos, assertar sessões, criptografia Signal Protocol)
					const allRecipients: string[] = []
					// ... (popular allRecipients com dispositivos do remetente e destinatário)
					await assertSessions(allRecipients)

					const [
						{ nodes: meNodes, shouldIncludeDeviceIdentity: s1 },
						{ nodes: otherNodes, shouldIncludeDeviceIdentity: s2 }
					] = await Promise.all([
						createParticipantNodes(meRecipients, meMsg || message, extraAttrs),
						createParticipantNodes(otherRecipients, message, extraAttrs, meMsg)
					])
					participants.push(...meNodes)
					participants.push(...otherNodes)
					// ... (adicionar hash de participantes)
				}

				// ... (lógica para retentativas de reenvio)

				if (participants.length) {
					// ... (adicionar nós de participantes ao conteúdo binário)
				}

				const stanza: BinaryNode = {
					tag: 'message',
					attrs: {
						id: msgId,
						to: destinationJid,
						type: getMessageType(message),
						...(additionalAttributes || {})
					},
					content: binaryNodeContent
				}

				// ... (ajustes de 'to' e 'recipient' para retentativas)

				if (shouldIncludeDeviceIdentity) {
					;(stanza.content as BinaryNode[]).push({
						tag: 'device-identity',
						attrs: {},
						content: encodeSignedDeviceIdentity(authState.creds.account!, true)
					})
				}
				// ... (lógica para reporting token e tctoken)

				await sendNode(stanza)
			})
		}

		// ... (outras funções e retorno da API de mensagens)
}
```

**Explicação:**

*   **`makeMessagesSocket`**: Esta factory estende o socket base com funcionalidades de envio de mensagens.
*   **`relayMessage`**: Esta é a função central para o envio de mensagens. Ela recebe o JID do destinatário, o objeto `proto.IMessage` (que já contém o conteúdo da mensagem) e opções adicionais.
    *   **Determinação do Tipo de Chat**: Verifica se é um grupo (`isGroup`), status (`isStatus`), newsletter (`isNewsletter`) ou chat 1:1.
    *   **Criptografia**: Esta é a parte mais complexa. Dependendo se é um grupo ou um chat 1:1, ele usa diferentes mecanismos de criptografia:
        *   **Grupos**: Utiliza `signalRepository.encryptGroupMessage` para criptografar a mensagem com uma Sender Key. Se necessário, ele também envia um `SenderKeyDistributionMessage` para os participantes que ainda não possuem a chave.
        *   **1:1**: Primeiro, ele enumera todos os dispositivos do remetente e do destinatário (`getUSyncDevices`) e garante que as sessões Signal para esses dispositivos estejam estabelecidas (`assertSessions`). Em seguida, ele usa `signalRepository.encryptMessage` para criptografar a mensagem para cada dispositivo individualmente.
    *   **Construção do `BinaryNode`**: A mensagem criptografada é empacotada em um nó binário (`<enc>`) com atributos como `v` (versão) e `type` (e.g., `pkmsg` para 1:1, `skmsg` para grupo). Outros nós, como `device-identity` e `reporting` token, podem ser adicionados.
    *   **Envio**: O nó binário final é enviado através do WebSocket usando `sendNode` (que, por sua vez, usa `sendRawMessage` do `socket.ts`).

**Fluxo:**

1.  A aplicação chama uma função de envio (e.g., `sock.sendMessage`).
2.  `sendMessage` prepara o `proto.IMessage` e chama `relayMessage`.
3.  `relayMessage` determina o tipo de chat e os destinatários.
4.  A mensagem é criptografada usando o Signal Protocol (1:1) ou Sender Key (grupo).
5.  Um nó binário é construído com o conteúdo criptografado e metadados.
6.  O nó binário é enviado via WebSocket.

**Dependências:**

*   `authState.keys.transaction`: Garante a atomicidade das operações de chave.
*   `signalRepository`: Gerencia as operações do Signal Protocol (criptografia, gerenciamento de chaves).
*   `getUSyncDevices`: Obtém a lista de dispositivos para um JID.
*   `assertSessions`: Garante que as sessões Signal estejam estabelecidas.
*   `encodeWAMessage`: Codifica o `WAMessage` em um buffer.
*   `sendNode`: Envia o nó binário através do WebSocket.

### `src/Socket/messages-recv.ts` - O Pipeline de Recebimento de Mensagens

Este arquivo lida com o processamento de mensagens e outros nós recebidos do servidor do WhatsApp. A função `handleMessage` é a responsável por decifrar e processar as mensagens.

```typescript
// src/Socket/messages-recv.ts

import NodeCache from '@cacheable/node-cache'
import { Boom } from '@hapi/boom'
import { randomBytes } from 'crypto'
import Long from 'long'
import { proto } from '../../WAProto/index.js'
import {
	DEFAULT_CACHE_TTLS,
	KEY_BUNDLE_TYPE,
	MIN_PREKEY_COUNT,
	PLACEHOLDER_MAX_AGE_SECONDS,
	STATUS_EXPIRY_SECONDS
} from '../Defaults'
import type {
	GroupParticipant,
	MessageReceiptType,
	MessageRelayOptions,
	MessageUserReceipt,
	NewChatMessageCapInfo,
	SocketConfig,
	WACallEvent,
	WAMessage,
	WAMessageKey
} from '../Types'
import { ReachoutTimelockEnforcementType, WAMessageStatus, WAMessageStubType } from '../Types'
import {
	ACCOUNT_RESTRICTED_TEXT,
	aesDecryptCTR,
	aesEncryptGCM,
	cleanMessage,
	Curve,
	decodeMediaRetryNode,
	decodeMessageNode,
	decryptMessageNode,
	delay,
	derivePairingCodeKey,
	encodeBigEndian,
	encodeSignedDeviceIdentity,
	extractAddressingContext,
	extractE2ESessionFromRetryReceipt,
	getCallStatusFromNode,
	getHistoryMsg,
	getNextPreKeys,
	getStatusFromReceiptType,
	handleIdentityChange,
	hkdf,
	MISSING_KEYS_ERROR_TEXT,
	NACK_REASONS,
	NO_MESSAGE_FOUND_ERROR_TEXT,
	SERVER_ERROR_CODES,
	toNumber,
	unixTimestampSeconds,
	xmppPreKey,
	xmppSignedPreKey
} from '../Utils'
import { makeMutex } from '../Utils/make-mutex'
import { makeOfflineNodeProcessor, type MessageType } from '../Utils/offline-node-processor'
import { buildAckStanza } from '../Utils/stanza-ack'
import {
	buildMergedTcTokenIndexWrite,
	isTcTokenExpired,
	readTcTokenIndex,
	resolveIssuanceJid,
	resolveTcTokenJid,
	storeTcTokensFromIqResult,
	TC_TOKEN_INDEX_KEY
} from '../Utils/tc-token-utils'
import {
	areJidsSameUser,
	type BinaryNode,
	binaryNodeToString,
	getAllBinaryNodeChildren,
	getBinaryNodeChild,
	getBinaryNodeChildBuffer,
	getBinaryNodeChildren,
	getBinaryNodeChildString,
	getBinaryNodeChildUInt,
	isJidGroup,
	isJidNewsletter,
	isJidStatusBroadcast,
	isLidUser,
	isPnUser,
	jidDecode,
	jidNormalizedUser,
	type JidWithDevice,
	S_WHATSAPP_NET
} from '../WABinary'
import { extractGroupMetadata } from './groups'
import { makeMessagesSocket } from './messages-send'

// ... (outras inicializações e funções auxiliares)

export const makeMessagesRecvSocket = (config: SocketConfig) => {
		// ... (inicialização do socket base e outras variáveis)

		const handleMessage = async (node: BinaryNode) => {
			const encNode = getBinaryNodeChild(node, 'enc')
			// ... (tratamento de msmsg, que é ignorado)

			let acked = false

			try {
				const {
					fullMessage: msg,
					category,
					author,
					decrypt
				} = decryptMessageNode(node, authState.creds.me!.id, authState.creds.me!.lid || '', signalRepository, logger)

				// ... (lógica para armazenar novos mapeamentos LID/PN)

				await messageMutex.mutex(async () => {
					await decrypt()

					// ... (adicionar mensagem ao messageRetryManager)

					if (msg.messageStubType === proto.WebMessageInfo.StubType.CIPHERTEXT && msg.category !== 'peer') {
						// ... (lógica para mensagens que falharam na descriptografia: MISSING_KEYS_ERROR_TEXT, NO_MESSAGE_FOUND_ERROR_TEXT)
						// Solicitar reenvio de placeholder ou enviar retry request
						await retryMutex.mutex(async () => {
							// ... (enviar sendRetryRequest ou sendMessageAck)
						})
					} else {
						// Mensagem descriptografada com sucesso
						// ... (cancelar pending phone request no messageRetryManager)

						if (!isNewsletter) {
							// ... (determinar tipo de receipt e enviar sendReceipt)
							// ... (enviar ack para history message)
						} else {
							// ... (processar mensagem de newsletter sem receipts)
						}

						cleanMessage(msg, authState.creds.me!.id, authState.creds.me!.lid!)

						await upsertMessage(msg, node.attrs.offline ? 'append' : 'notify')
					}
				})
			} catch (error) {
				// ... (tratamento de erros e envio de NACK)
			}
		}

		// ... (outras funções como handleCall, handleBadAck, processNodeWithBuffer, offlineNodeProcessor)
}
```

**Explicação:**

*   **`makeMessagesRecvSocket`**: Esta factory estende o socket de envio com funcionalidades de recebimento e processamento de mensagens.
*   **`handleMessage`**: Esta função é invocada quando um nó binário do tipo `message` é recebido. Ela orquestra o processo de tratamento da mensagem:
    *   **`decryptMessageNode`**: Esta é a função mais crítica. Ela tenta descriptografar o conteúdo da mensagem usando o `signalRepository`. Ela lida com a complexidade do Signal Protocol para mensagens 1:1 e Sender Key para grupos. Retorna o `fullMessage` (o objeto `WAMessage` descriptografado) e uma função `decrypt` que, quando chamada, realiza a descriptografia real.
    *   **LID Mapping**: Se a mensagem contiver informações de mapeamento de Identidade Vinculada (LID), elas são armazenadas para futuras referências.
    *   **`messageMutex.mutex`**: Garante que o processamento de mensagens seja serializado para evitar condições de corrida, especialmente durante a descriptografia e atualização do estado.
    *   **Tratamento de Falhas de Descriptografia**: Se a mensagem não puder ser descriptografada (e.g., `MISSING_KEYS_ERROR_TEXT`, `NO_MESSAGE_FOUND_ERROR_TEXT`), o Baileys pode:
        *   Enviar um `NACK` (Negative Acknowledgement) ao remetente.
        *   Solicitar um reenvio de placeholder (`requestPlaceholderResend`) para obter o conteúdo completo do telefone.
        *   Enviar um `retry request` para o remetente, indicando que a mensagem precisa ser reenviada.
    *   **Envio de Receipts**: Após a descriptografia bem-sucedida, o Baileys envia um `receipt` (recibo de entrega ou leitura) de volta ao remetente usando `sendReceipt`.
    *   **`cleanMessage`**: Realiza a limpeza e normalização do objeto `WAMessage`.
    *   **`upsertMessage`**: A mensagem processada é então adicionada ou atualizada no armazenamento local da aplicação, e o evento `messages.upsert` é emitido para a aplicação do usuário.

**Fluxo:**

1.  Um nó binário é recebido do WebSocket.
2.  O `offlineNodeProcessor` (ou `processNode`) encaminha o nó para `handleMessage`.
3.  `handleMessage` tenta descriptografar o nó usando `decryptMessageNode`.
4.  Se a descriptografia for bem-sucedida, a mensagem é limpa, um recibo é enviado e o evento `messages.upsert` é emitido.
5.  Se a descriptografia falhar, um NACK é enviado ou um reenvio é solicitado.

**Dependências:**

*   `decryptMessageNode`: Descriptografa o conteúdo da mensagem.
*   `signalRepository`: Acessa as chaves Signal para descriptografia.
*   `messageMutex`: Garante o processamento serializado de mensagens.
*   `messageRetryManager`: Gerencia retentativas de mensagens.
*   `sendReceipt`: Envia recibos de entrega/leitura.
*   `upsertMessage`: Atualiza o estado da mensagem na aplicação.
*   `BaileysEventEmitter`: Emite eventos para a aplicação.

### `src/Utils/messages-media.ts` - Manipulação de Mídia

Este arquivo contém as funções utilitárias para lidar com o upload, download, criptografia e descriptografia de arquivos de mídia.

```typescript
// src/Utils/messages-media.ts

import { Boom } from '@hapi/boom'
import { exec } from 'child_process'
import * as Crypto from 'crypto'
import { once } from 'events'
import { createReadStream, createWriteStream, promises as fs, WriteStream } from 'fs'
import type { Agent } from 'https'
import type { IAudioMetadata } from 'music-metadata'
import { tmpdir } from 'os'
import { join } from 'path'
import { Readable, Transform } from 'stream'
import { URL } from 'url'
import { proto } from '../../WAProto/index.js'
import { DEFAULT_ORIGIN, MEDIA_HKDF_KEY_MAPPING, MEDIA_PATH_MAP, type MediaType } from '../Defaults'
import type {
	BaileysEventMap,
	DownloadableMessage,
	MediaConnInfo,
	MediaDecryptionKeyInfo,
	MessageType,
	SocketConfig,
	WAGenericMediaMessage,
	WAMediaUpload,
	WAMediaUploadFunction,
	WAMessageContent,
	WAMessageKey
} from '../Types'
import { type BinaryNode, getBinaryNodeChild, getBinaryNodeChildBuffer, jidNormalizedUser } from '../WABinary'
import { aesDecryptGCM, aesEncryptGCM, hkdf } from './crypto'
import { generateMessageIDV2 } from './generics'
import type { ILogger } from './logger'

// ... (funções auxiliares como getTmpFilesDirectory, getImageProcessingLibrary)

export const hkdfInfoKey = (type: MediaType) => {
		const hkdfInfo = MEDIA_HKDF_KEY_MAPPING[type]
		return `WhatsApp ${hkdfInfo} Keys`
	}

export async function getMediaKeys(
		buffer: Uint8Array | string | null | undefined,
		mediaType: MediaType
	): Promise<MediaDecryptionKeyInfo> {
		// ... (derivação de iv, cipherKey, macKey usando HKDF)
	}

export const encryptedStream = async (
		media: WAMediaUpload,
		mediaType: MediaType,
		{ logger, saveOriginalFileIfRequired, opts }: EncryptedStreamOptions = {}
	) => {
		const { stream, type } = await getStream(media, opts)

		const mediaKey = Crypto.randomBytes(32)
		const { cipherKey, iv, macKey } = await getMediaKeys(mediaKey, mediaType)

		// ... (criação de streams de escrita, inicialização de AES, HMAC, SHA256)

		// ... (loop para ler chunks do stream, criptografar, calcular hashes e escrever para arquivos temporários)

		return {
			mediaKey,
			originalFilePath,
			encFilePath,
			mac,
			fileEncSha256,
			fileSha256,
			fileLength
		}
	}

export async function generateThumbnail(
		file: string,
		mediaType: 'video' | 'image',
		options: {
			logger?: ILogger
		}
	) {
		// ... (lógica para extrair thumbnail de imagem ou vídeo usando sharp/jimp ou ffmpeg)
	}

// ... (outras funções como getHttpStream, toBuffer, getStream, extractImageThumb, extractVideoThumb)
```

**Explicação:**

*   **`getMediaKeys`**: Esta função é fundamental para a criptografia/descriptografia de mídia. Ela recebe a `mediaKey` (uma chave de 32 bytes) e o `mediaType` e, usando HKDF (HMAC-based Key Derivation Function) com um `hkdfInfoKey` específico para o tipo de mídia, deriva as chaves `iv` (Initialization Vector), `cipherKey` (chave de criptografia AES) e `macKey` (chave para HMAC) [14].
*   **`encryptedStream`**: Esta função lida com o processo de criptografia de um stream de mídia antes do upload:
    *   Obtém o stream de entrada da mídia (`getStream`).
    *   Gera uma `mediaKey` aleatória.
    *   Deriva `cipherKey`, `iv` e `macKey` usando `getMediaKeys`.
    *   Cria um `AES-256-CBC` cipher e um `HMAC-SHA256`.
    *   Lê o stream de mídia em chunks, criptografa cada chunk com AES, calcula o HMAC e os hashes SHA256 (do arquivo original e criptografado), e escreve o conteúdo criptografado em um arquivo temporário.
    *   Retorna a `mediaKey`, os caminhos dos arquivos temporários e os hashes calculados.
*   **`generateThumbnail`**: Esta função cria thumbnails para imagens e vídeos. Para imagens, ela usa bibliotecas como `sharp` ou `jimp` para redimensionar e converter a imagem. Para vídeos, ela pode usar `ffmpeg` para extrair um frame específico [14].

**Fluxo de Upload de Mídia:**

1.  A aplicação fornece um arquivo de mídia.
2.  `encryptedStream` é chamado para criptografar a mídia.
3.  Uma `mediaKey` é gerada, e as chaves de criptografia são derivadas.
4.  A mídia é lida em stream, criptografada e os hashes são calculados.
5.  O conteúdo criptografado é salvo em um arquivo temporário.
6.  Uma thumbnail é gerada, se aplicável.
7.  Os dados resultantes (incluindo `mediaKey`, hashes, tamanho) são usados para construir o `proto.IMessage` de mídia, que é então enviado via `relayMessage`.

**Fluxo de Download de Mídia:**

1.  Uma mensagem de mídia é recebida, contendo a URL do arquivo criptografado, `mediaKey`, hashes, etc.
2.  O Baileys baixa o arquivo criptografado da URL.
3.  `getMediaKeys` é usado para derivar as chaves de descriptografia a partir da `mediaKey`.
4.  `aesDecryptGCM` é usado para descriptografar o conteúdo baixado.
5.  Os hashes são verificados para garantir a integridade.

**Dependências:**

*   `crypto`: Para geração de chaves aleatórias, AES, HMAC, SHA256.
*   `hkdf`: Função de derivação de chave.
*   `fs`, `stream`: Para manipulação de arquivos e streams.
*   `sharp`, `jimp`, `ffmpeg`: Para processamento de imagem/vídeo (se instalados).
*   `proto`: Definições de Protocol Buffers para mensagens de mídia.

### Diagrama de Fluxo de Mensagens (Texto)

```mermaid
graph TD
    A[Sua Aplicação] --> B{makeWASocket(config)}
    B --> C[WebSocketClient.connect()]
    C --> D{validateConnection()}
    D --> E[Noise Protocol Handshake]
    E --> F[Login/Registration Payload]
    F --> G[WebSocket Conectado & Autenticado]

    G --> H{Envio de Mensagem}
    H --> I[sendMessage(jid, content)]
    I --> J[generateWAMessage()]
    J --> K[relayMessage(jid, WAMessage)]
    K --> L{Determinar Destinatários & Tipo de Chat}
    L -- Grupo/Status --> M[Criptografia Sender Key (encryptGroupMessage)]
    L -- 1:1 --> N[Enumerar Dispositivos (getUSyncDevices)]
    N --> O[Assertar Sessões Signal (assertSessions)]
    O --> P[Criptografia Signal Protocol (encryptMessage)]
    M & P --> Q[Construir BinaryNode (<message>)]
    Q --> R[sendNode(BinaryNode)]
    R --> S[WebSocket.send(BinaryData)]
    S --> T[Servidor WhatsApp]

    T --> U{Recebimento de Mensagem}
    U --> V[WebSocket.on('frame', ...)]
    V --> W[decodeBinaryNode(BinaryData)]
    W --> X[decryptMessageNode(BinaryNode)]
    X --> Y{Descriptografia Signal/Sender Key}
    Y -- Sucesso --> Z[cleanMessage()]
    Z --> AA[sendReceipt()]
    AA --> AB[upsertMessage()]
    AB --> AC[BaileysEventEmitter.emit('messages.upsert')]
    AC --> A
    Y -- Falha --> AD[sendNACK() ou requestPlaceholderResend()]
    AD --> A

    subgraph Mídia
        K -- Mídia --> K1[encryptedStream(media)]
        K1 --> K2[Upload para Servidor de Mídia]
        K2 --> K3[generateThumbnail()]
        K3 --> K
        X -- Mídia --> X1[Download de Mídia]
        X1 --> X2[Descriptografia de Mídia (aesDecryptGCM)]
        X2 --> X
    end
```

## Referências

[1] WhiskeySockets/Baileys. (n.d.). *WhiskeySockets/Baileys: Socket-based TS/JavaScript API for WhatsApp Web*. GitHub. Retrieved from [https://github.com/WhiskeySockets/Baileys](https://github.com/WhiskeySockets/Baileys)
[2] The Noise Protocol Framework. (2018, July 11). Retrieved from [https://noiseprotocol.org/noise.html](https://noiseprotocol.org/noise.html)
[3] tgalal/consonance. (n.d.). *tgalal/consonance: WhatsApp's handshake implementation using Noise Protocol*. GitHub. Retrieved from [https://github.com/tgalal/consonance](https://github.com/tgalal/consonance)
[4] Signal Protocol: How WhatsApp Achieves E2EE at Scale. (2025, July 14). *Patsnap*. Retrieved from [https://eureka.patsnap.com/article/signal-protocol-how-whatsapp-achieves-e2ee-at-scale](https://eureka.patsnap.com/article/signal-protocol-how-whatsapp-achieves-e2ee-at-scale)
[5] How does the Signal Protocol, used by WhatsApp, work? (2016, April 23). *Security Stack Exchange*. Retrieved from [https://security.stackexchange.com/questions/121304/how-does-the-signal-protocol-used-by-whatsapp-work](https://security.stackexchange.com/questions/121304/how-does-the-signal-protocol-used-by-whatsapp-work)
[6] How WhatsApp enables multi-device capability. (2021, July 14). *Engineering at Meta*. Retrieved from [https://engineering.fb.com/2021/07/14/security/whatsapp-multi-device/](https://engineering.fb.com/2021/07/14/security/whatsapp-multi-device/)
[7] WhatsApp tests multi-device support that works without phone. (2021, July 14). *TechCrunch*. Retrieved from [https://techcrunch.com/2021/07/14/whatsapp-is-testing-multi-device-support-that-works-without-the-phone/](https://techcrunch.com/2021/07/14/whatsapp-is-testing-multi-device-support-that-works-without-the-phone/)
[8] `src/Socket/messages-recv.ts` (Linhas 1871-1909). Baileys GitHub Repository.
[9] `src/Socket/socket.ts`. Baileys GitHub Repository.
[10] `src/Utils/use-multi-file-auth-state.ts`. Baileys GitHub Repository.
[11] `src/Types/Events.ts`. Baileys GitHub Repository.
[12] `src/Socket/messages-recv.ts`. Baileys GitHub Repository.
[13] `src/Socket/messages-send.ts`. Baileys GitHub Repository.
[14] `src/Utils/messages-media.ts`. Baileys GitHub Repository.
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

O download é o processo inverso. A função `downloadMediaMessage` (geralmente exposta via utilitários ou implementada pelo usuário) faz o seguinte:

1.  Extrai a URL, `mediaKey` e hashes da mensagem recebida.
2.  Baixa o arquivo criptografado da URL.
3.  Deriva as chaves AES e HMAC da `mediaKey` usando HKDF.
4.  Descriptografa o arquivo baixado.
5.  Verifica o hash SHA256 para garantir a integridade.
6.  Retorna o buffer da mídia descriptografada.

### Thumbnail e Stream

*   **Thumbnail**: Miniaturas são essenciais para a experiência do usuário. O Baileys tenta gerá-las automaticamente durante o envio usando bibliotecas de processamento de imagem/vídeo, mas é altamente recomendável que o desenvolvedor forneça suas próprias thumbnails pré-geradas para melhor performance e controle.
*   **Stream**: O uso de streams (`Readable` e `WriteStream` do Node.js) é crucial ao lidar com mídia, especialmente vídeos ou documentos grandes. O Baileys suporta passar streams diretamente para a função de envio, evitando o esgotamento da memória RAM.

## Referências

[1] `src/Types/Events.ts`. Baileys GitHub Repository.
[2] `src/Utils/use-multi-file-auth-state.ts`. Baileys GitHub Repository.
[3] `src/Socket/messages-send.ts`. Baileys GitHub Repository.
[4] `src/Utils/messages-media.ts`. Baileys GitHub Repository.
[5] `src/WABinary/decode.ts`. Baileys GitHub Repository.
[6] `src/Socket/messages-recv.ts`. Baileys GitHub Repository.
## PARTE 11 — GRUPOS

O Baileys oferece funcionalidades abrangentes para interagir com grupos do WhatsApp, desde a criação até o gerenciamento de participantes e configurações. A lógica principal para essas operações está encapsulada em `src/Socket/groups.ts` [1].

### Como funciona:

As operações de grupo são realizadas através do envio de "stanzas" (nós binários) XMPP para o servidor do WhatsApp, que então processa a requisição e envia notificações de volta. O Baileys abstrai essa complexidade, fornecendo funções de alto nível.

#### Criar Grupo

A criação de um grupo é feita através de uma função como `groupCreate`. Ela requer um nome para o grupo e uma lista de participantes iniciais. O Baileys envia uma requisição `iq` (Info/Query) para o servidor do WhatsApp, que retorna os metadados do novo grupo, incluindo seu JID (ID do grupo).

```typescript
// Exemplo de uso (simplificado)
const groupName = 'Meu Novo Grupo'
const participants = ['5511999999999@s.whatsapp.net', '5521888888888@s.whatsapp.net']

const newGroup = await sock.groupCreate(groupName, participants)
console.log('Grupo criado:', newGroup)
```

#### Editar Grupo (Assunto, Descrição, Foto, Configurações)

*   **Assunto (Nome)**: A função `groupUpdateSubject` permite alterar o nome do grupo. Isso envia uma stanza com o novo assunto.
*   **Descrição**: `groupUpdateDescription` permite definir ou alterar a descrição do grupo. O Baileys envia uma stanza com o novo texto.
*   **Foto**: `groupUpdateProfilePicture` permite definir ou alterar a foto do perfil do grupo. Isso envolve o upload da imagem para os servidores de mídia do WhatsApp e o envio de uma stanza com a referência à nova imagem.
*   **Configurações**: Funções como `groupToggleEphemeral` (para mensagens temporárias), `groupSettingUpdate` (para controlar quem pode enviar mensagens, editar informações do grupo, etc.) permitem modificar as configurações do grupo.

#### Promover/Rebaixar Administradores

As funções `groupParticipantsUpdate` são usadas para gerenciar os papéis dos participantes. Para promover um membro a administrador, o Baileys envia uma requisição para o servidor indicando a ação `promote` e o JID do participante. O mesmo se aplica para rebaixar (`demote`).

```typescript
// Exemplo de promoção de participante
await sock.groupParticipantsUpdate(groupId, [participantJid], 'promote')
```

#### Expulsar Participantes

Similar à promoção/rebaixamento, `groupParticipantsUpdate` é usada com a ação `remove` para expulsar um participante do grupo.

```typescript
// Exemplo de expulsão de participante
await sock.groupParticipantsUpdate(groupId, [participantJid], 'remove')
```

#### Convite e Link de Convite

*   **Link de Convite**: A função `groupInviteCode` recupera o código de convite do grupo, que pode ser compartilhado para permitir que outros usuários entrem. `groupRevokeInvite` pode ser usado para invalidar o link atual e gerar um novo.
*   **Entrar via Convite**: `groupAcceptInvite` ou `groupJoin` permitem que o cliente Baileys entre em um grupo usando um código de convite.

#### Admins

O Baileys pode consultar os metadados de um grupo (`groupMetadata`) para obter a lista de administradores e suas permissões. Eventos como `group-participants.update` notificam a aplicação sobre mudanças nos papéis dos participantes.

## PARTE 12 — LIMITAÇÕES

Embora o Baileys seja uma ferramenta poderosa, é crucial entender suas limitações, especialmente por ser uma biblioteca não oficial que interage com um protocolo proprietário.

### O que não funciona / O que quebra

*   **Chamadas de Voz/Vídeo**: O Baileys não suporta chamadas de voz ou vídeo. Embora possa receber eventos relacionados a chamadas (`call` event), ele não pode iniciá-las ou participar delas [2].
*   **Status (Stories)**: A interação completa com os Status (visualizar, postar) pode ser limitada ou instável, pois o protocolo subjacente é complexo e muda frequentemente.
*   **Funcionalidades Novas/Experimentais**: O WhatsApp frequentemente lança novas funcionalidades em beta. O Baileys pode demorar a implementá-las ou pode não ter suporte total.
*   **Mensagens Interativas Complexas**: Embora suporte botões e listas básicas, funcionalidades mais avançadas de UI interativa do WhatsApp podem não ser totalmente replicadas ou podem ser mais difíceis de implementar.

### O que muda frequentemente

*   **Protocolo do WhatsApp Web**: O WhatsApp atualiza constantemente seu protocolo. Isso pode levar a quebras no Baileys, exigindo atualizações da biblioteca. A equipe de manutenção do Baileys trabalha para acompanhar essas mudanças, mas pode haver atrasos.
*   **Estruturas de Mensagens (Protobuf)**: As definições de Protocol Buffers (`WAProto`) podem mudar, o que exige a atualização dos arquivos `.proto` e a recompilação para que o Baileys possa codificar/decodificar mensagens corretamente.
*   **Mecanismos de Autenticação**: Embora o QR code e o pairing code sejam relativamente estáveis, o WhatsApp pode introduzir novos mecanismos ou alterar os existentes, exigindo adaptações no Baileys.

### O que depende do WhatsApp

*   **Disponibilidade do Serviço**: O Baileys depende da disponibilidade dos servidores do WhatsApp. Se o WhatsApp estiver fora do ar, o Baileys também estará.
*   **Termos de Serviço**: O uso do Baileys está sujeito aos Termos de Serviço do WhatsApp. O WhatsApp pode, a qualquer momento, alterar seus termos ou implementar medidas para bloquear o uso de clientes não oficiais.
*   **Recursos de Segurança**: A segurança do Baileys está intrinsecamente ligada à segurança do Signal Protocol e do Noise Protocol, que são mantidos por terceiros (Open Whisper Systems e a comunidade Noise Protocol, respectivamente).

### Riscos de Banimento

Este é um dos maiores riscos ao usar o Baileys ou qualquer API não oficial:

*   **Uso Abusivo**: Envio de spam, mensagens em massa não solicitadas, criação de muitos grupos rapidamente, ou qualquer comportamento que o WhatsApp considere abusivo pode levar ao banimento da conta associada.
*   **Detecção de Cliente Não Oficial**: O WhatsApp pode implementar mecanismos para detectar clientes que não são o aplicativo oficial. Se detectado, sua conta pode ser banida.
*   **Frequência de Mensagens**: Enviar um volume muito alto de mensagens em um curto período pode ser interpretado como comportamento de bot e levar ao banimento.

É fundamental usar o Baileys de forma responsável e ética, e estar ciente de que o risco de banimento existe e não pode ser totalmente mitigado, pois o controle final está nas mãos do WhatsApp.

### Limitações Técnicas

*   **Consumo de Recursos**: Embora mais leve que soluções baseadas em navegador, o Baileys ainda consome recursos (CPU, memória, rede), especialmente em cenários de alta carga.
*   **Complexidade de Manutenção**: Manter uma aplicação baseada em Baileys exige conhecimento técnico para lidar com as atualizações do WhatsApp e as eventuais quebras.
*   **Ausência de Suporte Oficial**: Não há suporte oficial do WhatsApp para problemas com o Baileys.

### Limitações Legais

*   **Termos de Serviço**: O uso de APIs não oficiais pode violar os Termos de Serviço do WhatsApp, o que pode ter implicações legais dependendo da jurisdição e do tipo de uso.
*   **Privacidade de Dados**: Ao usar o Baileys, o desenvolvedor é responsável por garantir a conformidade com as leis de privacidade de dados (LGPD, GDPR, etc.) ao lidar com informações de usuários do WhatsApp.

### Limitações de Performance e Escalabilidade

*   **Single-Threaded (Node.js)**: Embora o Node.js seja assíncrono, a execução de JavaScript é single-threaded. Operações intensivas de CPU (como criptografia/descriptografia pesada ou processamento de mídia) podem bloquear o event loop e impactar a performance.
*   **Gerenciamento de Sessões**: Escalar para centenas ou milhares de sessões simultâneas requer um gerenciamento cuidadoso de recursos, persistência de estado e balanceamento de carga.

### Problemas Conhecidos

*   **Desconexões Inesperadas**: O WhatsApp pode encerrar conexões por vários motivos (inatividade, atualizações de protocolo, detecção de cliente não oficial), exigindo lógica robusta de reconexão.
*   **Atrasos na Entrega de Mensagens**: Em alguns casos, pode haver atrasos na entrega ou recebimento de mensagens devido a problemas de rede, sobrecarga do servidor do WhatsApp ou detecção de comportamento incomum.
*   **Sincronização de Histórico Incompleta**: Em raras ocasiões, a sincronização inicial do histórico pode não ser completa, exigindo intervenção manual ou lógica de recuperação.

## PARTE 13 — SEGURANÇA

A segurança é um aspecto crítico ao trabalhar com o WhatsApp e, consequentemente, com o Baileys. A biblioteca se apoia nos protocolos de segurança do WhatsApp, mas a implementação e as boas práticas do desenvolvedor são fundamentais.

### Criptografia

*   **Criptografia de Ponta a Ponta (E2EE)**: O Baileys herda a E2EE do WhatsApp, implementada pelo Signal Protocol. Isso significa que as mensagens são criptografadas no dispositivo do remetente e só podem ser descriptografadas no dispositivo do destinatário. O Baileys atua como um desses "dispositivos" [3] [4].
*   **Criptografia de Transporte**: A comunicação entre o Baileys e os servidores do WhatsApp é protegida pelo Noise Protocol, garantindo que os dados em trânsito não possam ser interceptados ou adulterados [5] [6].
*   **Criptografia de Mídia**: Arquivos de mídia são criptografados antes de serem enviados para os servidores do WhatsApp e descriptografados após o download, garantindo que o WhatsApp não tenha acesso ao conteúdo da mídia [7].

### Armazenamento

O armazenamento seguro das credenciais e chaves é vital. O Baileys, através de `useMultiFileAuthState`, armazena esses dados em arquivos locais [8].

*   **Boas Práticas**: Em ambientes de produção, esses arquivos **NÃO** devem ser armazenados diretamente no sistema de arquivos sem criptografia adicional. Recomenda-se o uso de bancos de dados seguros (SQL, NoSQL) com criptografia em repouso, ou gerenciadores de segredos (e.g., HashiCorp Vault, AWS Secrets Manager) para as chaves mais sensíveis.
*   **Isolamento**: As credenciais de cada sessão (usuário) devem ser isoladas e não compartilhadas entre diferentes instâncias ou usuários.

### Credenciais

As credenciais (`AuthenticationCreds`) incluem chaves criptográficas sensíveis como `noiseKey`, `signedIdentityKey` e `advSecretKey`. O acesso não autorizado a essas credenciais comprometeria a segurança da sessão do WhatsApp.

*   **Proteção**: As credenciais devem ser tratadas como segredos de alta sensibilidade. Evite hardcoding, logs desnecessários e exposição em variáveis de ambiente não seguras.

### Boas Práticas

*   **Atualização Constante**: Mantenha o Baileys sempre atualizado para se beneficiar das últimas correções de segurança e adaptações ao protocolo do WhatsApp.
*   **Validação de Entrada**: Sempre valide e sanitize as entradas do usuário para prevenir ataques de injeção ou outros vetores de ataque.
*   **Princípio do Menor Privilégio**: Conceda à sua aplicação apenas as permissões necessárias para funcionar.
*   **Monitoramento**: Monitore o comportamento da sua aplicação para detectar atividades incomuns que possam indicar um comprometimento de segurança ou uso indevido.
*   **Auditoria de Código**: Realize auditorias de segurança no código da sua aplicação para identificar vulnerabilidades.

### Tokens

Além das chaves criptográficas, o WhatsApp utiliza tokens (como o `tctoken` para controle de transações) que são sensíveis e devem ser protegidos. O Baileys gerencia esses tokens internamente, mas é importante estar ciente de sua existência e propósito.

### Backup

Faça backup regular das credenciais de sessão. Em caso de perda de dados ou corrupção, um backup pode permitir a restauração da sessão sem a necessidade de reautenticação via QR code. No entanto, o backup deve ser armazenado de forma segura e criptografada.

### Vazamento de Sessão

Um vazamento de sessão ocorre quando as credenciais de autenticação são comprometidas. Isso pode permitir que um atacante se passe pelo usuário do WhatsApp.

*   **Prevenção**: Implemente medidas de segurança robustas para proteger os arquivos ou banco de dados de credenciais. Use autenticação multifator para acesso aos sistemas que hospedam o Baileys.
*   **Detecção e Resposta**: Monitore logs para atividades suspeitas. Em caso de vazamento, o usuário deve ser instruído a desconectar todos os dispositivos do WhatsApp no aplicativo oficial.

### Proteção

A proteção geral da sua aplicação Baileys envolve uma combinação de segurança da infraestrutura, segurança do código e boas práticas operacionais. Considere o ambiente onde o Baileys está sendo executado (servidor, contêiner) e aplique as melhores práticas de segurança para esse ambiente.

## PARTE 14 — PERFORMANCE

A performance de uma aplicação baseada em Baileys é influenciada por diversos fatores, desde o consumo de recursos até a eficiência da comunicação com o WhatsApp.

### Consumo de Memória

*   **Node.js e JavaScript**: Aplicações Node.js podem ter um consumo de memória considerável, especialmente se não forem otimizadas. O Baileys, por si só, tenta ser eficiente, mas o gerenciamento de grandes volumes de mensagens, mídias e estados de sessão pode aumentar o uso de RAM.
*   **Cache**: O uso de caches (e.g., `NodeCache` para metadados de grupo, `messageRetryManager`) ajuda a reduzir requisições repetidas, mas consome memória. É importante configurar TTLs (Time To Live) apropriados para evitar que o cache cresça indefinidamente [9].
*   **Streams**: O uso extensivo de streams para manipulação de mídia (`src/Utils/messages-media.ts`) ajuda a manter o consumo de memória baixo, evitando carregar arquivos grandes inteiros na RAM [7].

### CPU

*   **Criptografia/Descriptografia**: As operações de criptografia e descriptografia (Signal Protocol, Noise Protocol) são intensivas em CPU. Em cenários de alto volume de mensagens, isso pode se tornar um gargalo, especialmente em ambientes single-threaded como o Node.js.
*   **Processamento de Mídia**: Geração de thumbnails, redimensionamento de imagens e transcodificação de vídeo (se implementado) são tarefas que consomem muita CPU.
*   **Parsing de Protocol Buffers**: A serialização e desserialização de mensagens Protobuf também adiciona uma carga à CPU.

### WebSocket

*   **Conexão Persistente**: Manter uma conexão WebSocket persistente consome recursos de rede e memória. O Baileys implementa um mecanismo de `keepAlive` para garantir que a conexão não seja encerrada por inatividade [10].
*   **Latência**: A performance do WebSocket é sensível à latência da rede. Uma conexão instável ou com alta latência impactará diretamente a velocidade de envio e recebimento de mensagens.

### Eventos

*   **Event Loop**: O Node.js opera em um event loop. Operações síncronas e demoradas nos handlers de eventos podem bloquear o event loop, causando lentidão e atrasos no processamento de outras tarefas.
*   **Buffer de Eventos**: O `makeEventBuffer` ajuda a agrupar eventos e processá-los de forma mais eficiente, evitando que o event loop seja sobrecarregado por muitos eventos pequenos e rápidos [10].

### Cache

O Baileys utiliza caches para otimizar o acesso a dados frequentemente usados, como metadados de grupo e informações de dispositivos. Uma estratégia de cache bem configurada pode reduzir significativamente a carga no servidor do WhatsApp e melhorar a responsividade da aplicação.

### Upload/Download

*   **Velocidade da Rede**: A velocidade de upload e download de mídia é diretamente limitada pela largura de banda da rede onde a aplicação está sendo executada.
*   **Servidores de Mídia do WhatsApp**: O WhatsApp possui seus próprios servidores de mídia. A performance de upload/download também depende da capacidade e da localização desses servidores em relação à sua aplicação.

### Banco de Dados

Se você estiver usando um banco de dados para persistir o estado de autenticação, mensagens ou outros dados, a performance do banco de dados será um fator crítico. Consultas lentas ou um banco de dados sobrecarregado podem impactar a responsividade geral da aplicação.

### Escalabilidade

Discutida em detalhes na próxima seção, mas a performance é um pré-requisito para a escalabilidade. Uma aplicação performática é mais fácil de escalar.

## PARTE 15 — ESCALABILIDADE

Escalar uma aplicação Baileys para lidar com um grande número de usuários ou mensagens é um desafio que exige considerações arquiteturais cuidadosas. A natureza não oficial da API do WhatsApp adiciona complexidade.

### Como criar um sistema para X usuários

#### 100 Usuários

*   **Arquitetura**: Uma única instância do Node.js rodando o Baileys pode ser suficiente. Use `useMultiFileAuthState` para persistir sessões em disco. Um banco de dados simples (e.g., SQLite, PostgreSQL local) pode ser usado para armazenar mensagens e metadados.
*   **Gargalos**: O principal gargalo será o consumo de CPU e memória da instância única. Operações de criptografia/descriptografia podem começar a impactar a latência.

#### 1.000 Usuários

*   **Arquitetura**: Comece a considerar múltiplas instâncias do Baileys. Cada instância pode gerenciar um subconjunto de sessões. Um balanceador de carga (e.g., Nginx, HAProxy) distribuiria as requisições para as instâncias. Um banco de dados centralizado (e.g., PostgreSQL, MySQL) se torna essencial para o estado persistente. Use um sistema de mensagens (e.g., Redis Pub/Sub, RabbitMQ) para comunicação entre as instâncias e para enfileirar tarefas.
*   **Gargalos**: Gerenciamento de estado de sessão distribuído, concorrência no banco de dados, e a latência da rede entre as instâncias e o WhatsApp.

#### 10.000 Usuários

*   **Arquitetura**: Migração para uma arquitetura de microserviços. Separe a lógica de conexão/autenticação das lógicas de negócio (bots, CRM). Use um cluster de instâncias do Baileys, possivelmente em contêineres (Docker) orquestrados por Kubernetes. Um sistema de fila robusto (e.g., RabbitMQ, Kafka) é indispensável para processamento assíncrono de mensagens e eventos. Cache distribuído (e.g., Redis) para metadados e sessões.
*   **Gargalos**: Sincronização de estado entre microserviços, gerenciamento de chaves criptográficas em um ambiente distribuído, e a capacidade do WhatsApp de lidar com o volume de conexões/mensagens de uma única origem (seu IP).

#### 100.000+ Usuários

*   **Arquitetura**: Uma arquitetura altamente distribuída e resiliente. Múltiplos clusters de Kubernetes em diferentes regiões geográficas. Uso intensivo de filas de mensagens, processamento assíncrono, e estratégias de retry robustas. Sharding de sessões de WhatsApp entre múltiplos IPs de saída para evitar detecção e banimento. Monitoramento avançado e observabilidade.
*   **Gargalos**: **Riscos de Banimento** (o maior gargalo), latência do WhatsApp, gerenciamento de milhões de chaves criptográficas, e a complexidade operacional de uma arquitetura tão grande.

### Gargalos Existentes

*   **WhatsApp Rate Limits**: O WhatsApp impõe limites na frequência de mensagens e ações. Exceder esses limites pode levar a bloqueios temporários ou banimento.
*   **Detecção de Automação**: O WhatsApp pode detectar padrões de comportamento que indicam automação, resultando em banimento.
*   **Gerenciamento de Sessões**: Manter um grande número de sessões ativas e sincronizadas é complexo e consome muitos recursos.
*   **Criptografia**: A sobrecarga computacional da criptografia E2EE pode ser um gargalo significativo em alta escala.
*   **Mudanças de Protocolo**: A necessidade de adaptar a aplicação a mudanças frequentes no protocolo do WhatsApp pode ser um desafio de manutenção e estabilidade em larga escala.
*   **Recursos de Rede**: A largura de banda e a estabilidade da conexão de rede são cruciais para um grande volume de mensagens e mídias.

## PARTE 16 — CASOS REAIS

O Baileys pode ser a base para diversas arquiteturas de sistemas, dependendo do caso de uso e da escala. Aqui estão algumas arquiteturas comuns e tecnologias associadas:

### SaaS (Software as a Service)

*   **Arquitetura**: Multi-tenant, onde cada cliente tem suas próprias sessões isoladas do Baileys. Pode usar um gateway de API para rotear requisições para instâncias do Baileys. Filas de mensagens (RabbitMQ, Kafka) para processamento assíncrono de eventos e mensagens. Banco de dados escalável (PostgreSQL, MongoDB) para persistência de dados. Autenticação de usuários via OAuth/JWT.
*   **Tecnologias**: Node.js (com Baileys), Express.js/Fastify, PostgreSQL/MongoDB, Redis, RabbitMQ/Kafka, Docker, Kubernetes.

### CRM (Customer Relationship Management)

*   **Arquitetura**: Integração do Baileys com um CRM existente. Mensagens do WhatsApp são recebidas pelo Baileys, processadas e enviadas para o CRM via webhooks ou API. Respostas do CRM são enviadas de volta ao WhatsApp via Baileys. Pode usar um sistema de workers para processar mensagens em segundo plano e evitar sobrecarga do CRM principal.
*   **Tecnologias**: Node.js (com Baileys), API Gateway, Webhooks, CRM (e.g., Salesforce, HubSpot), Workers (e.g., BullMQ, Agenda.js), Redis.

### Chatbot

*   **Arquitetura**: O Baileys atua como a camada de comunicação com o WhatsApp. As mensagens recebidas são encaminhadas para um motor de processamento de linguagem natural (NLP) ou um sistema de regras. As respostas geradas são enviadas de volta via Baileys. Pode usar um sistema de fila para gerenciar o fluxo de mensagens e respostas.
*   **Tecnologias**: Node.js (com Baileys), NLP (e.g., Dialogflow, Rasa), Servidor de regras, Redis/RabbitMQ.

### Atendimento

*   **Arquitetura**: Similar ao CRM, mas focado em atendimento humano. O Baileys recebe mensagens e as encaminha para uma plataforma de atendimento (e.g., Zendesk, Freshdesk) ou um painel de controle customizado. Agentes humanos respondem através da plataforma, e as respostas são enviadas de volta via Baileys. Filas para garantir que nenhuma mensagem seja perdida.
*   **Tecnologias**: Node.js (com Baileys), Plataforma de Atendimento, Webhooks, Redis/RabbitMQ.

### Disparo (Mensagens em Massa)

*   **Arquitetura**: **CUIDADO: Alto risco de banimento.** Se for implementado, deve ser com extrema cautela. Envolve um sistema de fila para gerenciar o envio de mensagens em lotes, com atrasos e limites para evitar detecção. Pode usar múltiplos números de WhatsApp (e, portanto, múltiplas sessões Baileys) para distribuir o volume. Monitoramento rigoroso é essencial.
*   **Tecnologias**: Node.js (com Baileys), RabbitMQ/Kafka, Redis, Docker, Kubernetes, Proxy Rotativo (para IPs de saída).

### Multiempresa / Multi Sessão

*   **Arquitetura**: Cada empresa ou sessão de WhatsApp é isolada. Um serviço central gerencia a criação e o ciclo de vida das sessões. Cada sessão pode ser executada em um processo ou contêiner separado. O estado de autenticação é persistido em um banco de dados centralizado.
*   **Tecnologias**: Node.js (com Baileys), Docker, Kubernetes, PostgreSQL/MySQL, Redis.

### Fila / Workers

*   **Arquitetura**: Para processar tarefas demoradas ou de alto volume (e.g., envio de mídia, processamento de histórico), utilize um sistema de fila (e.g., Redis com BullMQ, RabbitMQ, Kafka) e workers dedicados. O Baileys envia tarefas para a fila, e os workers as processam em segundo plano, liberando o processo principal para lidar com novas mensagens.
*   **Tecnologias**: Node.js (com Baileys), Redis (BullMQ), RabbitMQ, Kafka, Workers (processos Node.js separados).

### Redis, RabbitMQ, Kafka

Essas tecnologias são fundamentais para a escalabilidade e resiliência:

*   **Redis**: Usado para cache distribuído, armazenamento de sessões de curta duração, Pub/Sub para comunicação entre serviços, e como backend para filas de tarefas (e.g., BullMQ).
*   **RabbitMQ**: Um message broker robusto, ideal para filas de tarefas, comunicação entre microserviços e garantia de entrega de mensagens.
*   **Kafka**: Um sistema de streaming de eventos distribuído, excelente para lidar com grandes volumes de dados em tempo real, como logs de mensagens, eventos de usuário e sincronização de estado em larga escala.

### Docker / Kubernetes

*   **Docker**: Permite empacotar a aplicação Baileys e suas dependências em contêineres isolados, facilitando a implantação e garantindo a consistência do ambiente.
*   **Kubernetes**: Um orquestrador de contêineres que automatiza a implantação, escalabilidade e gerenciamento de aplicações conteinerizadas. Essencial para escalar o Baileys para múltiplos processos e garantir alta disponibilidade.

## PARTE 17 — CÓDIGO

Esta seção é uma instrução geral para integrar exemplos de código e explicações detalhadas ao longo do guia. Já incorporei exemplos de código e explicações linha a linha nas seções anteriores (Partes 5, 8, 9, 11) para ilustrar os conceitos. Continuarei a fazer isso conforme necessário nas próximas seções, especialmente na comparação de APIs, para destacar diferenças de implementação.

## PARTE 18 — COMPARAÇÃO

Comparar o Baileys com outras bibliotecas e APIs para WhatsApp é crucial para entender suas vantagens e desvantagens e tomar a decisão certa para cada projeto.

### `whatsapp-web.js`

*   **Descrição**: Uma biblioteca Node.js que utiliza Puppeteer para controlar uma instância do WhatsApp Web em um navegador Chromium headless. Emula um cliente WhatsApp Web real.
*   **Vantagens**: Fácil de usar, abstrai grande parte da complexidade do protocolo, compatibilidade com a maioria das funcionalidades do WhatsApp Web, menos propenso a quebras por mudanças de protocolo (já que usa o cliente oficial).
*   **Desvantagens**: **Alto consumo de recursos** (CPU e RAM) devido ao uso do navegador Chromium, mais lento para iniciar, pode ser mais difícil de escalar para muitas sessões, dependência de uma versão específica do Chromium.

### `WPPConnect`

*   **Descrição**: Um fork e aprimoramento do `whatsapp-web.js`, focado em oferecer mais funcionalidades, estabilidade e uma comunidade ativa. Também baseado em Puppeteer.
*   **Vantagens**: Herda as vantagens do `whatsapp-web.js` (facilidade de uso, compatibilidade), adiciona funcionalidades extras, melhor gerenciamento de sessão e reconexão, comunidade e suporte ativos.
*   **Desvantagens**: Ainda sofre do **alto consumo de recursos** do Puppeteer, embora possa ter algumas otimizações. Os mesmos desafios de escalabilidade do `whatsapp-web.js`.

### `Evolution API`

*   **Descrição**: Uma API comercial (geralmente paga) que oferece uma interface RESTful para interagir com o WhatsApp. Pode ser construída sobre Baileys, `whatsapp-web.js` ou outras soluções internas.
*   **Vantagens**: Fácil integração (API REST), não exige que o desenvolvedor lide com a complexidade do protocolo do WhatsApp, geralmente oferece suporte e SLAs, pode ser mais escalável (se a infraestrutura por trás for bem projetada).
*   **Desvantagens**: **Custo** (geralmente pago por mensagem ou por sessão), menor flexibilidade e controle sobre o protocolo, dependência de um provedor externo, pode ter limitações nas funcionalidades disponíveis.

### `Meta Cloud API` (WhatsApp Business Platform Cloud API)

*   **Descrição**: A API oficial do WhatsApp para empresas, hospedada pela Meta. Oferece uma interface RESTful para enviar e receber mensagens de negócios.
*   **Vantagens**: **Oficial e suportada pela Meta**, alta estabilidade e escalabilidade, menor risco de banimento (se usada de acordo com as políticas), acesso a funcionalidades específicas de negócios (templates, mensagens interativas avançadas), conformidade legal.
*   **Desvantagens**: **Custo** (pago por conversa), requer aprovação da Meta, funcionalidades limitadas a casos de uso de negócios (não para automação de contas pessoais), menor flexibilidade para customizações fora do escopo de negócios.

### `OpenWA`

*   **Descrição**: Uma biblioteca Node.js mais antiga e menos mantida, que também tentava interagir com o WhatsApp Web. Atualmente, é amplamente considerada obsoleta e não recomendada.
*   **Vantagens**: (Históricas) Foi uma das primeiras a tentar a engenharia reversa do WhatsApp Web.
*   **Desvantagens**: **Não mantida**, alta probabilidade de quebrar com as atualizações do WhatsApp, falta de suporte para novas funcionalidades, riscos de segurança.

### Tabela Comparativa

| Característica        | Baileys                                      | `whatsapp-web.js` / `WPPConnect`                     | `Evolution API`                                  | `Meta Cloud API`                                  | `OpenWA`                                     |
| :-------------------- | :------------------------------------------- | :--------------------------------------------------- | :----------------------------------------------- | :------------------------------------------------ | :------------------------------------------- |
| **Tipo**              | Biblioteca (Node.js, TypeScript)             | Biblioteca (Node.js, Puppeteer)                      | Serviço (API REST)                               | Serviço (API REST, Oficial)                       | Biblioteca (Node.js, Obsoleta)               |
| **Oficial**           | Não                                          | Não                                                  | Não (geralmente)                                 | Sim                                               | Não                                          |
| **Consumo Recursos**  | Baixo/Médio (sem navegador)                  | Alto (com navegador Chromium)                        | Variável (depende do provedor)                   | Baixo (gerenciado pela Meta)                      | Alto (obsoleto)                              |
| **Risco Banimento**   | Médio/Alto                                   | Médio/Alto                                           | Médio (depende do provedor)                      | Baixo (se seguir políticas)                       | Alto                                         |
| **Flexibilidade**     | Alta (controle total do protocolo)           | Média (limitado pelo WhatsApp Web)                   | Baixa (limitado pela API)                        | Baixa (limitado a casos de uso de negócios)       | Baixa (obsoleta)                             |
| **Custo**             | Gratuito                                     | Gratuito                                             | Pago                                             | Pago                                              | Gratuito (mas não funcional)                 |
| **Manutenção**        | Ativa (comunidade WhiskeySockets)            | Ativa (comunidade)                                   | Pelo provedor                                    | Pela Meta                                         | Nenhuma                                      |
| **Escalabilidade**    | Desafiadora (requer arquitetura complexa)   | Muito desafiadora (recursos do navegador)            | Potencialmente alta (pelo provedor)              | Alta (gerenciada pela Meta)                       | Nenhuma                                      |
| **Uso Ideal**         | Automação customizada, bots eficientes       | Bots e automação simples, prototipagem               | Integração rápida, sem gerenciar infraestrutura  | Comunicação oficial de negócios, notificações     | Nenhum (obsoleta)                            |

## Referências

[1] `src/Socket/groups.ts`. Baileys GitHub Repository.
[2] `src/Types/Events.ts`. Baileys GitHub Repository.
[3] Signal Protocol: How WhatsApp Achieves E2EE at Scale. (2025, July 14). *Patsnap*. Retrieved from [https://eureka.patsnap.com/article/signal-protocol-how-whatsapp-achieves-e2ee-at-scale](https://eureka.patsnap.com/article/signal-protocol-how-whatsapp-achieves-e2ee-at-scale)
[4] How does the Signal Protocol, used by WhatsApp, work? (2016, April 23). *Security Stack Exchange*. Retrieved from [https://security.stackexchange.com/questions/121304/how-does-the-signal-protocol-used-by-whatsapp-work](https://security.stackexchange.com/questions/121304/how-does-the-signal-protocol-used-by-whatsapp-work)
[5] The Noise Protocol Framework. (2018, July 11). Retrieved from [https://noiseprotocol.org/noise.html](https://noiseprotocol.org/noise.html)
[6] tgalal/consonance. (n.d.). *tgalal/consonance: WhatsApp's handshake implementation using Noise Protocol*. GitHub. Retrieved from [https://github.com/tgalal/consonance](https://github.com/tgalal/consonance)
[7] `src/Utils/messages-media.ts`. Baileys GitHub Repository.
[8] `src/Utils/use-multi-file-auth-state.ts`. Baileys GitHub Repository.
[9] `src/Socket/messages-recv.ts`. Baileys GitHub Repository.
[10] `src/Socket/socket.ts`. Baileys GitHub Repository.
