# Preferências globais

Abra **Editar > Preferências…**. A janela reúne 13 categorias em uma navegação
lateral, com campos compactos, prévia de identificação e estilos e restauração
por seção. Os atalhos editam o mapa compartilhado, com validação de conflitos.

Cenas e Shots têm blocos e exemplos separados. Cores usam amostras clicáveis
com o seletor já existente e código hexadecimal secundário. Números têm ajuste
por botões; tamanho, margem, opacidade e volume também oferecem sliders.
Timeline reúne unidade de tempo, casas decimais, contadores, snap e volume.
`ui.form_layout` centraliza a densidade dos formulários: controles de 28 px,
rótulo, slider e valor na mesma linha, opções booleanas em duas colunas e prévia
compacta dentro da área rolável, sem reservar um painel fixo separado.
A versão 2 do rascunho migra os campos da antiga categoria Números para Timeline.
A versão 3 reúne Salvamento e recuperação e Mídia e desempenho na categoria
Salvamento e desempenho, em seções internas, preservando os rascunhos anteriores.

**Aplicar** valida e salva `preferences.json` (versão 1), separado dos documentos
`.koma`. **Cancelar**, Esc e clicar fora descartam a edição da janela. Enter
confirma; valores inválidos impedem a gravação. Na primeira abertura, um rascunho
anterior de `preferences-preview.json` pode preencher os campos, sem ativação até
Aplicar. Atalhos e opções antigas de referência são lidos para compatibilidade.
Os atalhos continuam no armazenamento compartilhado existente (`settings.json`),
sem uma segunda cópia autoritativa no arquivo de preferências visuais.

## Comportamentos conectados

- **Identificação:** prefixos, sufixos e dígitos na apresentação do canvas,
  timeline, propriedades e MP4. Códigos continuam derivados do fluxo; UUIDs,
  títulos e posições não mudam.
- **Legendas e dados de referência:** fonte, tamanho proporcional, cor,
  alinhamento, posição, margem, fundo e opacidade. As legendas usam o mesmo
  renderizador na prévia e no MP4. Os campos de referência usam a mesma
  configuração e formatação; não ocupam os blocos da timeline.
- **Aparência e canvas:** fundo, cores de seleção, marcadores e grade,
  espaçamento, zoom e enquadramento inicial. O fundo da imagem também compõe
  o MP4; o espaçamento da grade também orienta o snap ao confirmar movimentos.
- **Timeline:** frames ou segundos, decimais e contadores, snap inicial dos
  marcadores e volume de monitoração. Esse volume não modifica os áudios do
  documento nem a mixagem exportada.
- **Animatic:** visibilidade e largura iniciais da lista de cenas e abertura
  sem seleção na última visualização, montagem completa ou primeira cena.
  Limites de zoom, sensibilidade da roda e velocidade de pan independentes
  para prévia e timeline; espaço adicional ao fim da timeline configurável.
- **Desenho:** cor e espessura iniciais, borracha independente e lembrança da
  ferramenta. Traços existentes permanecem intactos. O estado da ferramenta
  é salvo separadamente em `tool-state.json`, com uma escrita em andamento.
- **Atalhos:** edição, validação de conflitos e restauração. Separe combinações
  alternativas com ponto e vírgula.
- **Salvamento e desempenho:** backups completos `.koma` durante edições,
  intervalo mínimo e rotação por documento, restauração de abas salvas,
  qualidade das imagens e vídeos na prévia e orçamento de cache dividido entre
  legendas geradas e waveforms. O limite não é o da memória total do aplicativo;
  vídeos mantêm seu leitor ativo e imagens usam o cache nativo do cliente.
  Limpar prévias não exclui mídias. **Abrir backups** mostra as cópias, que podem
  ser abertas pelo comando Abrir normal.
- **Arquivos e exportação:** pastas, limite de recentes, qualidade do MP4 e
  nomes com `{project}`, `{scene}` e `{shot}`.
- **Confirmações:** exclusão e fechamento. Desativar o aviso ao fechar preserva
  as alterações não salvas na recuperação local.
- **Novos projetos:** FPS e resolução, dentro dos limites reais do modelo.
  Projetos abertos, importados e recuperados não recebem esses valores.

A recuperação local continua sendo atualizada após alterações confirmadas.
O intervalo controla apenas as cópias completas adicionais em
`backups/<document_id>/`. A última sessão restaura arquivos salvos; documentos
sem caminho continuam disponíveis no fluxo de recuperação.

`preference_catalog` define categorias, campos, tipos, limites e validação.
`global_preferences` valida contratos cruzados e publica snapshots imutáveis.
`preference_draft` permanece apenas para compatibilidade com o protótipo.
`ui.preferences_panel` gera os controles e exemplos a partir do catálogo.
Leitura e escrita ocorrem fora do fluxo da interface. Nenhum node ou histórico
é modificado ao aplicar preferências. Escritas globais são serializadas.

`editor.preference_bindings` atualiza os consumidores ao confirmar, com
invalidação por categoria. Alterações só em dados de referência atualizam seu
controle local; pastas e padrões de novos projetos não reconstroem o canvas.
Abas inativas atualizam a apresentação ao serem ativadas. Gestos não consultam
arquivos nem revalidam a configuração completa.

Cada exportação captura sua configuração: alterações posteriores não mudam um
MP4 já em andamento. A cache de legendas considera a revisão das preferências.
O formato dos documentos `.koma` permanece inalterado.

## Navegação do Animatic

A roda aproxima ou afasta mantendo o ponto sob o cursor. Arrastar com o botão
do meio move a visualização. Na timeline, Shift + roda também desloca a trilha.
F enquadra a área sob o mouse; a prévia também oferece um botão de enquadrar
junto ao indicador de zoom. O zoom da prévia é relativo à imagem enquadrada.

As duas câmeras são estados temporários independentes: navegar não move mídias,
não cria histórico e não muda o MP4. O botão direito continua sendo borracha.
No cliente atualizado, o pan ocorre localmente e a timeline mantém apenas um
pedido de zoom em andamento, agrupando os movimentos seguintes. Clientes
anteriores usam a navegação compatível disponível; reabra o aplicativo para
carregar o cliente compilado com a nova navegação.
