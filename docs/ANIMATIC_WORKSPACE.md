# Modo Animatic

Use **Canvas** e **Animatic** na barra superior para alternar as áreas de trabalho
do mesmo projeto. O animatic ocupa a área principal, com prévia ao centro,
timeline em toda a largura abaixo e o inspetor compartilhado à direita da prévia.
O inspetor não reduz a largura das trilhas.

- Arraste o divisor horizontal para distribuir espaço entre prévia e timeline.
- Arraste a borda do inspetor para ajustar sua largura. A seta recolhe o painel;
  a aba lateral o reabre. `N` também alterna sua visibilidade nos dois modos.
- Clique em um bloco para selecionar seu node e visualizar suas propriedades.
- A agulha e a reprodução alteram a prévia, preservando a seleção do inspetor.
- O seletor de cena no cabeçalho muda o contexto de quadros, áudio e marcadores.
- A timeline tem faixas identificadas para marcas, quadros e áudio. Cada bloco
  mostra a imagem do node e sua duração. O zoom aceita roda do mouse, slider,
  botões e `F` para enquadrar.
- O rodapé reúne importar, silenciar, volume, início em frames e remover áudio.
  O nome aparece na waveform. O volume confirma uma operação ao soltar;
  `Esc` descarta o ajuste em andamento.
- As ferramentas de desenho continuam atuando sobre o quadro exibido na prévia.
  O campo de frames junto ao transporte também se refere à prévia; o inspetor
  apresenta os valores do node selecionado.
- `Esc` cancela a edição em andamento ou limpa a seleção do desenho antes de
  retornar ao canvas. O botão Canvas também permite retornar.

O tamanho dos painéis, a câmera e a seleção do canvas permanecem ao alternar os
modos. Na mesma cena, a posição, o zoom e a seleção do animatic são preservados.
Trocar de aba suspende a reprodução e retoma o modo daquela aba ao voltar, sem
reproduzir automaticamente. Esses valores são estado de interface da sessão;
não alteram o documento nem criam entradas no histórico.

## Dados e componentes

`WorkModes` coordena duas superfícies estáveis e um único `FrameProperties`.
O Canvas permanece montado para preservar a câmera e os gestos nativos. A
superfície do Animatic só fica montada enquanto esse modo está aberto, sem
transições; os controles e o estado de edição Python permanecem disponíveis.
Eventos atrasados de tamanho/rolagem do Animatic são descartados quando a
apresentação não está ativa, inclusive após mudar de aba.
`AnimaticWorkspace` define o layout redimensionável, reaproveitando o `Splitter`
compartilhado. Os componentes de desenho, reprodução, áudio, marcadores,
miniaturas e edição temporal continuam sendo os mesmos.
As medidas comuns ficam em `WorkspaceStyle`, as cores no tema e a geometria
dos cards/conectores em `NodeLayout`. As referências aprovadas estão em
[Design da interface](design/README.md).

Cada seleção guarda somente IDs como estado temporário de interface. Os valores
apresentados e editados são lidos de `StoryboardView.board`; mídias, desenhos,
textos e durações permanecem nos próprios nodes. Os dois modos usam o mesmo
histórico e a mesma persistência. A seleção do canvas é mantida enquanto o
animatic tem sua própria seleção, independente da agulha.

Alterações nas propriedades atualizam o node e a timeline. `Timeline.with_board`
reaproveita a ordem da cena nas alterações de valores; mudanças de composição,
fluxo ou mute recalculam a sequência. Desfazer/refazer e remoção de nodes
reconciliam a seleção e o inspetor com o documento atual.

O inspetor é atualizado quando muda a seleção, o node selecionado ou a
disponibilidade da edição. A reprodução não reconstrói seus campos. Campos
focados preservam suas expressões e o tratamento de teclas de texto. Pedidos de
foco atrasados são descartados quando a área ou o projeto já não estão ativos.
As ferramentas específicas do canvas permanecem nesse modo; exportação e
histórico estão disponíveis no animatic. Exportar abre suas opções sem sair da
área de trabalho.

Não há mudança no formato `.koma` nem dependência nova. O cliente Flet existente
apresenta os mesmos controles; esta alteração não exige recompilar o Flutter.

## Verificações

Os testes automatizados de modos cobrem seleção independente, propriedades,
expressões, histórico, reconciliação, painéis, troca de cena, suspensão por aba,
exportação e serialização da árvore de controles. As verificações existentes de
desenho, timeline, marcadores, mídias e abas protegem as integrações reutilizadas.
Não foram executados testes manuais nem gerada uma nova release.

A regressão nativa em `tests/flutter/animatic_layout_test.dart` usa a árvore
serializada dos componentes Python para conferir a timeline em duas dimensões
de janela e a coincidência dos conectores dos cards com as âncoras das linhas.
Gere a entrada com `python -m tests.flutter.export_animatic_layout`, usando o
ambiente virtual do projeto, antes de executar o teste Flutter.
