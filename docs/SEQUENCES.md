# Node de Sequência

Selecione quadros do mesmo nível e use **Inserir → Sequência**,
**Fluxo → Criar sequência** ou `Ctrl+Shift+G`. O atalho usa o catálogo compartilhado
e pode ser remapeado. Sem quadros selecionados, o comando cria uma sequência vazia.
O botão **+** do bloco adiciona um quadro ao seu conteúdo e o conecta ao final.

O bloco mostra a quantidade de quadros e a duração total em frames e segundos.
A duração é calculada a partir dos quadros ativos; não há uma segunda duração
editável ou um valor total salvo para sincronizar.

- **Duplo clique** no bloco ou **Abrir** entra no conteúdo. O canvas exibe somente
  os membros diretos desse nível; sequências internas continuam como blocos.
- O caminho **Canvas → Cena → Sequência** permite retornar aos níveis anteriores.
  **Esc** volta um nível quando não há gesto ou outra ação a cancelar.
- Navegar não altera o documento nem cria passos no histórico. Câmera e seleção
  de cada nível são estado temporário da interface. Os mesmos cards são reutilizados.
- Arrastar o cabeçalho ou usar **G** move apenas o bloco, sem deslocar seus membros.
  As posições originais dos quadros continuam no próprio node. Cancelar descarta a prévia.
- Fora da sequência, as conexões pertencem ao próprio bloco. Dentro dela existem
  conectores **Entrada** e **Saída**, além dos quadros. Arraste Entrada até um quadro
  e a saída do último quadro até Saída. As ligações podem ser cortadas e refeitas
  normalmente, inclusive as ligações dos conectores.
- Somente um caminho completo de Entrada até Saída participa do animatic, da
  duração total e das exportações PDF/MP4. Quadros desconectados permanecem no grupo,
  com suas mídias, desenhos e posições. Um ícone discreto no bloco informa quando
  não há caminho completo; passar o mouse explica o motivo. Uma sequência aninhada
  incompleta também invalida o caminho do grupo que a atravessa.
- Criar, importar, duplicar e colar no conteúdo adiciona os novos nodes à sequência
  e continua o fluxo antes de sua saída externa. Organizar atua somente no nível
  aberto. Copiar um bloco preserva a organização interna de seus membros.
- **⋯ → Dissolver sequência** remove apenas o organizador e preserva os quadros e
  as ligações. **Excluir** o node remove também seu conteúdo; desfazer restaura tudo.
- Excluir um membro reconecta os quadros restantes quando possível e ajusta os
  conectores. Desconectar temporariamente é permitido e aceita desfazer/refazer.

Inícios de cena permanecem fora das sequências. Sequências completas podem ser
agrupadas novamente, permitindo níveis de organização. Cada membro pertence a
um único organizador direto; composições circulares e conexões entre níveis são
rejeitadas. Use os conectores do bloco para o fluxo externo. Molduras continuam
sendo um recurso independente.

O animatic, a timeline, o PDF e o MP4 continuam consumindo os quadros originais na
ordem do fluxo. Recolher o canvas não elimina conteúdo da reprodução ou da
exportação. Mutar a sequência usa o comando de lote sobre seus quadros; as opções
individuais de cada membro continuam pertencendo a ele.

Na timeline, uma faixa compacta acima dos quadros identifica a sequência imediata.
Cada trecho cobre exatamente o intervalo dos seus quadros ativos; a geometria
acompanha zoom e prévias de duração. Em grupos aninhados, passar o mouse mostra o
caminho completo. A faixa só ocupa espaço quando há quadros de sequências na cena.
O painel de propriedades mostra `Cena > Sequência > Quadro`, com o caminho completo
no tooltip quando o texto não cabe. Ambos usam a mesma hierarquia dos nodes, sem
novos dados persistidos. Os trechos são reutilizados durante reprodução e gestos;
o histórico continua registrando somente as alterações dos nodes.

## Estrutura e compatibilidade

`SequenceState` pertence ao próprio `StoryFrame` do tipo composto. Guarda os membros,
a Entrada (`entry`), a Saída (`exit`) e o estado legado recolhido. São relações entre
nodes, como as conexões do fluxo guardam
relações entre nodes. Cada quadro continua existindo uma única vez no documento,
com sua imagem, desenho, roteiro, duração e demais propriedades na própria
estrutura. Nenhum dado de quadro é transferido para um cadastro paralelo.

`SequenceIndex` deriva hierarquia, duração e extremidades do documento atual.
`SequenceScope` deriva a visibilidade e as conexões do nível aberto, guardando
apenas navegação, câmera e seleção temporárias. `SequenceActions` usa os comandos compartilhados de histórico e persistência;
`SequenceBody` somente apresenta os valores e chama essas ações. Duplicação e
clipboard incluem o conteúdo e remapeiam os identificadores e as mídias.

Sequências foram introduzidas no formato **5**. O salvamento atual usa o formato
**7**, com interfaces próprias de grupo. A migração dos formatos **1 a 6** converte
as antigas ligações externas dos quadros para o bloco e define Entrada/Saída,
processando grupos aninhados de dentro para fora. Preserva posições, mídias,
desenhos e a ordem de reprodução; o arquivo original não é reescrito ao abrir.
Mantenha uma cópia
anterior se precisar continuar usando uma versão antiga do app.

As verificações automatizadas cobrem composição, aninhamento, movimento e
cancelamento, duração derivada, exportação, `.koma`, compatibilidade com o formato
anterior, cópia entre projetos, duplicação, exclusão, dissolução e histórico.
Não foram feitos testes manuais.

O campo legado `collapsed` continua sendo lido e preservado nos arquivos existentes,
mas não controla a navegação interna. Não são criadas cópias dos quadros durante
a migração ou a navegação. Os conectores na interface representam os valores
`entry`/`exit` do próprio node; suas posições são derivadas do conteúdo do grupo.
