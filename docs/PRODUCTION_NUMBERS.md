# Cenas e shots

Os nomes descritivos são independentes dos códigos de produção:

- `Scene_01 · Mineração`, `Scene_02 · Esteira`.
- `shot_0001`, `shot_0002`… seguem a ordem do fluxo, com contagem global contínua entre as cenas.

Reordenar as ligações altera o shot que cada quadro representa. Alterar o nome ou
mover o card no espaço, sem mudar as ligações, não muda seu código. Sequências
completas são percorridas na ordem de Entrada até Saída. Quadros desconectados
dentro de um grupo não recebem uma posição nesse fluxo. Quadros livres no nível
principal recebem números depois dos quadros das cenas. Mutar um quadro não apaga
sua posição de produção.

`ProductionNumbers` deriva os códigos dos mesmos nodes e conexões, com cache no
índice do documento. Canvas, lista de cenas, timeline, propriedades e dados de
referência usam esse mesmo cálculo. Não há campos paralelos de numeração para
sincronizar nem mudança no formato `.koma`. O identificador interno do node
continua o mesmo ao reordenar; código de produção representa seu papel no fluxo.
