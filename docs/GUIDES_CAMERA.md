# Guias e indicações de câmera

No Animatic, o botão de grade abre **Preferências > Guias e câmera**.
São padrões do programa; confirmar não altera os projetos abertos.

Guias disponíveis: terços, centro, grade com linhas/colunas ajustáveis, áreas
seguras de ação e títulos com margens próprias e guias horizontais/verticais
personalizadas. Informe percentuais separados por ponto e vírgula, por exemplo
`25; 50; 75`; vírgula decimal é aceita. O limite é de 16 guias personalizadas
por direção. Cor, espessura e opacidade também são globais.

**Mostrar na prévia** e **Incluir no MP4** são opções independentes, tanto para
guias quanto para indicações de câmera. Inicialmente, guias ficam desligadas e
indicações de câmera aparecem somente na prévia. Nada é incluído no MP4 sem
habilitar a opção correspondente.

Em **Propriedades > Câmera**, escolha o movimento, escreva uma nota opcional e
defina sua visibilidade. Pan, tilt, zoom, dolly, deslocamentos e órbita têm
indicações gráficas e nomes distintos. São orientações de produção: não movem
a mídia e não criam keyframes. O nome e a nota podem ser ocultados globalmente.
Aplicar ou Enter confirma uma transação; Cancelar ou Esc descarta a edição.
A edição também funciona para vários quadros selecionados, com um único desfazer.

## Dados e composição

`StoryFrame.camera` contém `CameraMotion(preset, note, visible)`. A estrutura é
imutável e pertence ao node; canvas, Animatic, propriedades, cópia entre projetos
e exportação consomem o mesmo modelo. A indicação continua pertencendo ao quadro
ao alternar sua mídia ativa.

O manifesto `.koma` passa à versão **9**. Versões 1–8 continuam abrindo, recebendo
uma indicação vazia; os demais dados são preservados. O salvamento atômico e os
backups existentes continuam em uso. Aplicativos anteriores recusam a versão 9.

`guide_geometry` produz geometria normalizada; `exports.guides` é o único
renderizador da prévia e do MP4. Prévia usa renderização em segundo plano com
uma tarefa ativa e somente o último pedido pendente, reaproveitando o orçamento
de cache já existente. Gestos e atualizações da agulha não renderizam guias.
Na exportação, a camada estática é preparada uma vez por quadro, inclusive para
mídias de vídeo. A composição preserva desenhos, mantém as legendas por cima e
não altera a mixagem de áudio. Guias não são adicionadas ao PDF.
