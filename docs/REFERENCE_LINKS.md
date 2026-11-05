# Links em Refs

Cada `ReferenceImage` pode possuir uma URL opcional no campo `url`. O endereço
pertence ao objeto, junto da imagem, posição e tamanho; não há registro paralelo
de links por identificador. Editar a URL não altera o arquivo de imagem.

Selecione uma referência e use **Editar link** na barra de Refs. Salvar ou Enter
confirma; Cancelar ou Esc descarta. Remover limpa somente o link. Um globo
discreto no canto da imagem abre o endereço no navegador externo e aparece
somente quando a referência possui um link.

A validação compartilhada aceita endereços HTTP/HTTPS completos com até 4096
caracteres, preservando parâmetros e fragmentos, inclusive tempos do YouTube.
Nenhuma página ou miniatura é baixada automaticamente. A abertura do navegador
não modifica o documento nem cria uma entrada no histórico.

Editar/remover o link usa o mesmo histórico e a mesma persistência dos demais
dados da referência. Mover, escalar e duplicar preservam a URL. O pacote `.koma`
inclui esse dado, junto do arquivo de imagem já existente.

O formato de documento **14** acrescenta o campo. A migração de versões
anteriores inicializa a URL vazia sem modificar imagens, posições ou nodes.
