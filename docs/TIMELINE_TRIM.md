# Ajuste de duração por arraste

Arrastar a borda direita de um quadro ajusta o corte: aumenta sua duração e reduz
a do próximo quadro visível na mesma timeline, ou faz o inverso. O tempo total,
os cortes posteriores, a trilha de áudio e os marcadores permanecem no lugar.
Os dois quadros mantêm pelo menos um frame, respeitando também o limite máximo
do modelo. Ao alcançar um limite, o movimento para; não passa a empurrar sozinho.

Segure **Shift ao iniciar o arraste** para alterar somente a duração daquele
quadro e empurrar os seguintes. O modo fica fixo até soltar, evitando mudanças
acidentais no meio do gesto. O modificador é configurável nos atalhos, em
**Empurrar quadros ao ajustar duração**. No último quadro, o arraste altera o
tempo total, pois não há um próximo quadro para compensar.

O campo numérico de duração mantém sua edição direta do quadro. Durante um
arraste, `Esc` descarta a prévia. Soltar confirma uma única operação de histórico
e salvamento, abrangendo os dois nodes quando necessário. Desfazer/refazer,
canvas, timeline e exportação usam as durações confirmadas no próprio modelo.
Não há alteração no formato dos documentos.

## Responsabilidades e fluidez

`duration_trim.DurationTrim` calcula limites e durações sem interface. A timeline
gera um snapshot temporário com `with_durations`; `TimelineEditor` controla o
gesto. A interface fornece o modificador pelo catálogo de atalhos e pelo estado
atual das teclas, sem identificar comandos por seus textos.

O início do gesto usa um bloqueio lógico, sem atualizar o canvas inteiro. Durante
o arraste, somente as durações e a apresentação temporal mudam; desenhos e mídias
imutáveis não são revalidados nem recriados. Quando o quadro da prévia já está
ativo, sua imagem e sua camada de desenho são preservadas. Ao confirmar,
`set_frames_properties` modifica os nodes em uma única transação compartilhada.

As verificações automatizadas cobrem ambos os modos, remapeamento do modificador,
limites, durações fracionárias anteriores, último quadro, preservação dos cortes
posteriores, cancelamento, salvamento e histórico. Também protegem o início e os
movimentos contra atualizações do canvas inteiro e validação pesada no gesto.
Não foram executados testes manuais.
