# Desenho por quadro

No cabeçalho do animatic, a barra de desenho fica expandida e centralizada. Escolher o lápis, a borracha ou uma forma ativa o desenho sobre o quadro atual. O menu de formas contém apenas ícones, com nomes nas dicas: retângulo, círculo, linha e seta. Clique e arraste para definir a forma. O retângulo tem largura e altura livres; círculos mantêm suas proporções no formato atual do projeto.

A amostra de cor abre o seletor compartilhado. O campo **px** e o slider controlam a mesma espessura, de 1 a 64 pixels do projeto. A borracha usa um ícone vetorial de apagador e apaga os traços inteiros que tocar.

`Tab` abre uma lista vertical compacta junto ao cursor, apenas com ícones: seleção, lápis, borracha, retângulo, círculo, linha e seta. Os nomes aparecem apenas nas dicas ao passar o mouse. Escolher uma ferramenta, pressionar `Esc` ou clicar fora fecha o menu. A barra permanece no cabeçalho; as duas entradas chamam os mesmos comandos de desenho. O atalho é configurável e respeita campos em edição. O cliente acompanha o mouse localmente, sem enviar movimentos à aplicação Python, e mantém o menu dentro dos limites da janela.

O botão direito funciona como borracha temporária na prévia: clique para apagar um traço ou arraste para apagar os traços atravessados. A ferramenta ativa permanece selecionada. Soltar confirma uma única operação de histórico; `Esc` cancela o gesto. Os dois botões usam os mesmos comandos de desenho, com controle separado de seus gestos para evitar interferência.

O botão de camadas mostra ou oculta o desenho daquele quadro, sem excluir os traços. A ferramenta inicial é **Seleção**; escolha o lápis ou uma forma para desenhar e volte à Seleção para mover os elementos. Não há um botão separado para ligar o desenho. `Esc` cancela um traço ainda em andamento; `Ctrl+Z` e refazer usam o histórico do documento, com uma operação por traço ou gesto de borracha.

Use a ferramenta de **Seleção** para clicar e mover uma forma ou traço existente. Formas fechadas também podem ser selecionadas pelo interior; em sobreposições, é selecionado o elemento superior. O contorno de seleção é apenas uma indicação temporária da interface. Arrastar move o vetor inteiro dentro dos limites da tela, sem distorcer sua geometria. Soltar confirma uma operação no histórico; `Esc` cancela um movimento em andamento ou desfaz a seleção quando não há gesto ativo. Os pontos alterados permanecem na camada do próprio node.

`Delete` apaga a forma ou traço selecionado, com desfazer/refazer. Uma seleção de desenho tem prioridade sobre o marcador selecionado. Sem desenho selecionado, o mesmo comando mantém a exclusão de marcadores. Campos em edição preservam seu próprio tratamento da tecla, e o atalho continua configurável pelo catálogo de ações.

As formas são geradas por `drawing_geometry` como traços do formato vetorial existente. Seus pontos, cor e espessura ficam na camada do próprio node, compartilhando borracha, histórico, persistência e exportação com o lápis. Não há um cadastro externo de formas nem mudança adicional de versão do documento para esta função.

Os desenhos pertencem ao node e acompanham duplicação, copiar/colar e importação entre projetos. São mostrados no animatic, nos cards e nas miniaturas; quando visíveis, também compõem o PDF e o MP4, abaixo das legendas. A camada usa coordenadas proporcionais ao formato do projeto, independentes do tamanho da janela e do enquadramento da imagem. Alterar o enquadramento da imagem não move os desenhos.

Os dados ficam no manifesto como vetores validados, sem alterar o arquivo de imagem. Modelo e geometria ficam em `drawing_models`, os comandos em `drawing_editor`, a entrada e os controles em `drawing_surface`, a apresentação compartilhada em `drawing_overlay` e a composição das exportações em `exports/drawings`.

O salvamento passa a usar o formato de documento 4; documentos de versões 1, 2 e 3 continuam abrindo com uma camada vazia. Aplicativos anteriores não abrem o novo formato. Preserve uma cópia se precisar continuar usando a release v0.2.0.

Há limites por camada para conter o tamanho dos documentos: 2.048 traços, 8.192 pontos por traço e 65.536 pontos no total. Os traços concluídos são reaproveitados na apresentação; durante o movimento não há gravação em disco. Fechar o player, trocar de quadro, perder o foco da janela ou redimensionar a superfície cancela um gesto ainda em andamento.
