# Canvas de referências

Abra **Refs**, ao lado de Canvas e Animatic. Cada projeto tem seu próprio painel
de imagens livres. As imagens, nomes, posições e tamanhos pertencem aos elementos
em `Storyboard.references`; não há armazenamento paralelo por identificador.
Referências não participam do storyboard narrativo, da montagem ou do MP4.
As teclas 1, 2 e 3 da fileira superior abrem Canvas, Animatic e Refs. Esses
atalhos podem ser alterados em Preferências > Atalhos; não são disparados
durante a edição de campos. O teclado numérico não faz parte desses padrões.

## Uso

- Importe pelo botão de imagem ou Ctrl+I; também é possível soltar imagens do
  Explorador ou colar uma imagem com Ctrl+V.
- Clique para selecionar; Shift + clique altera a seleção. Arrastar uma área
  vazia cria uma caixa de seleção. Clique no vazio para desmarcar.
- Arraste uma imagem para mover a seleção. A alça no canto inferior direito
  escala toda a seleção, preservando as proporções e as distâncias relativas.
  O botão Escala destaca a alça da seleção. Esc cancela o gesto.
- A barra oferece Grade, Ajustar à grade e Alinhamento inteligente como opções
  independentes. O alinhamento aproxima bordas e centros dos outros objetos e
  mostra guias temporárias; a distância é medida em pixels da tela, em qualquer zoom.
- Ctrl+D duplica; Delete exclui; Ctrl+A seleciona todas.
- G move a seleção e S escala proporcionalmente com o movimento do mouse.
  Enter ou clique esquerdo confirma; Esc ou clique direito cancela a prévia.
  Cada confirmação registra uma única alteração no histórico.
- A roda aplica zoom no cursor. H ativa pan; V retorna à seleção. Espaço ativa
  pan temporariamente. Arrastar com o botão direito também move a vista,
  usando o mesmo controle nativo do Canvas. F enquadra a seleção, ou todas as
  imagens sem seleção.
- Alt+Shift+arrastar com o botão esquerdo faz zoom suave em Canvas e Refs,
  ancorado no clique inicial. A combinação pode ser remapeada em Atalhos.
- Ctrl+Z e Ctrl+Shift+Z usam o mesmo histórico do restante do projeto.

Os controles usam o padrão compacto do editor. **Preferências > Referências**
reúne fundo, largura inicial, deslocamento ao duplicar e limites/sensibilidade
de zoom. A qualidade das prévias segue Salvamento e desempenho. Alterar esses
padrões não modifica imagens, posições ou tamanhos já confirmados.
Na primeira abertura de Refs de cada projeto, o padrão é enquadrar todas as
imagens após medir a área disponível. Nas entradas seguintes, a área retoma
o último zoom e posição da câmera. A preferência **Primeira abertura** controla
somente o enquadramento inicial; F continua disponível a qualquer momento.
Grade inicial, espaçamento, ajuste à grade, alinhamento e sua distância também
ficam nessa seção. Os botões alteram o estado temporário da área de trabalho.

## Integração e limites

`reference_models` valida cada elemento e limita o painel a 500 referências.
`reference_actions` importa fora do fluxo de eventos do mouse e confirma cada
lote ou gesto uma única vez. `reference_canvas` mantém somente seleção, câmera,
gesto temporário e controles de apresentação. Durante movimentos, publica
apenas os controles afetados, retendo os corpos das imagens.
`reference_transform` concentra escala e alinhamento: os candidatos são indexados
no início do gesto e consultados por busca binária. `reference_overlays` desenha
a grade apenas na região visível, com quantidade limitada de linhas; guias e
moldura de seleção são controles locais. Essas opções não exigem mudança no `.koma`.
Arrastes usam coordenadas locais do gesto, já convertidas pela câmera nativa,
preservando o ponto do clique inicial sem compensar o zoom novamente. Cada
movimento publica imagens afetadas, moldura e guias no mesmo lote.
A área lógica cobre os limites do modelo com origem fixa. Mover ou escalar,
inclusive para coordenadas negativas, não expande a área nem compensa a câmera
ao confirmar. A grade continua limitada à região visível, sem desenhar toda
a área lógica reservada.
O cliente com `spatial_camera_v1` aplica a câmera por estado declarativo: zoom e
translação chegam juntos, inclusive na primeira composição. O enquadramento não
depende de uma sequência de reset, zoom e pan. A câmera nativa informa sua pose
real para grade e guias; snapshots antigos são descartados pela revisão.

As imagens são copiadas para o armazenamento do projeto pelo importador existente,
com seus limites de arquivo e resolução. Duplicações compartilham o arquivo de
imagem imutável e possuem seus próprios dados de posição e tamanho. Salvar, abrir,
backups e recuperação percorrem os mesmos assets utilizados pelo modelo.

O manifesto `.koma` passa à **versão 8**, adicionando `references`. Documentos
das versões 1 a 7 continuam aceitos, com uma lista vazia de referências. A
migração de sequências permanece restrita às versões anteriores à 7; a versão
7 conserva sua Entrada e Saída. O salvamento mantém o processo atômico e backup
existentes. Versões antigas do aplicativo recusam o formato 8 explicitamente.

Grupos, anotações e comandos de ordenação de sobreposição ficam para uma etapa
posterior. A lista persistida define a ordem visual atual.
