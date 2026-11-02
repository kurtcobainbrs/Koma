# Cenas e montagem do projeto

O Animatic tem uma lista lateral de cenas com código, nome, miniatura e duração.
Ela pode ser redimensionada ou recolhida; o botão Cenas permanece disponível
para reabri-la. Os padrões ficam em **Editar > Preferências > Animatic**.

**Montagem** reproduz o projeto inteiro usando a mesma seleção da exportação:
cenas na ordem do documento, quadros dos caminhos válidos e quadros livres
incluídos pelo contrato existente. Cenas mutadas e grupos sem caminho completo
seguem as mesmas regras da exportação. Áudio que ultrapassa os quadros mantém a
última imagem da cena até terminar; a próxima cena começa depois dessa extensão.

Clique numa cena da lista para localizá-la na montagem. Dê duplo clique para
entrar na edição da cena. A faixa acima dos quadros identifica cada cena e também
aceita duplo clique. Na edição individual, um clique na lista troca de cena.
As propriedades e desenhos continuam editando os mesmos nodes.

Arraste uma cena na lista para alterar sua ordem. A operação muda somente a
ordem no documento; ligações, posições no canvas, mídias e propriedades dos nodes
permanecem intactas. A numeração de produção é recalculada pela ordem vigente.
Desfazer/refazer usa o histórico compartilhado. Eventos de uma aba ou de um
documento antigo não podem confirmar uma reordenação.

Cortes, reordenação de quadros, áudio e marcadores são editados dentro da cena,
onde seus tempos locais têm um único significado. Na montagem, seus controles
locais ficam desabilitados, mas reprodução, navegação, propriedades e desenhos
permanecem disponíveis. A exportação aberta pela montagem inicia em Projeto
completo, preservando o diálogo de intervalos e opções existente.

`ProjectTimeline` é uma projeção derivada de `ExportSequence`, sem novos nodes ou
mapas paralelos de propriedades. Mantém referências aos quadros confirmados,
offsets temporais de cenas, áudio e marcadores. A navegação entre visualizações
não altera o documento nem entra no histórico. O formato `.koma` não mudou.

A lista é reconstruída somente quando mudam o documento ou a identificação;
durante reprodução, o destaque atualiza apenas as cenas anterior e atual.
Waveforms são carregadas em segundo plano com concorrência limitada, retenção
limitada pelo número de trilhas do modelo e resolução ajustada ao orçamento de
cache. O arraste de cena apenas captura a proposta e confirma ao soltar.
