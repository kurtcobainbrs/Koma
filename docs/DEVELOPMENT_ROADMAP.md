# Evolução do fluxo de produção

Ordem aprovada: concluir cada etapa como um fluxo funcional, preservando os
dados dos nodes, histórico, compatibilidade e fluidez. Preferências globais
entram no catálogo e no painel existente; não ficam espalhadas nas telas.

1. **Colar imagens — implementado:** sem quadro ativo cria um quadro; com
   quadro ativo adiciona uma mídia, preservando duração e mídias anteriores.
   Posição e destino são capturados antes da importação. Cancelamento de
   contextos antigos não confirma dados; criação participa do histórico e da
   recuperação. Colagem de nodes e imagens compartilha a conversão de posição.
2. **Cenas e montagem — implementado:** lista lateral recolhível e redimensionável com código,
   nome, miniatura e duração; montagem do projeto inteiro, ordem das cenas,
   reprodução e acesso à edição interna. Consumir os mesmos nodes.
3. **Navegação — implementado:** zoom e pan independentes do preview e da
   timeline, ancoragem no cursor e enquadramento com F na área em uso.
   Padrões em Preferências. Gestos locais e pedidos de zoom agrupados evitam
   acumular eventos; as câmeras não alteram nodes, histórico ou exportação.
4. **Transformação e keyframes — implementado:** mover, escalar e girar a mídia
   ativa com gesto local, confirmação única e Esc. Poses e keyframes pertencem
   à mídia no node; interpolação linear ou constante no tempo local do quadro,
   com a mesma avaliação na prévia e no MP4. Consulte `MEDIA_ANIMATION.md`.
5. **Guias e câmera — implementado:** terços, centro, grade, áreas seguras e
   guias personalizadas; exibição e exportação independentes. Indicações de
   pan, tilt, zoom, dolly, deslocamento e órbita pertencem ao node; preferências
   de exibição são globais. Consulte `GUIDES_CAMERA.md`.
6. **Filtros — preto e branco implementado:** propriedade não destrutiva do projeto,
   com seletor único para Canvas, Animatic, PDF e MP4; Refs preserva as cores.
   A exportação segue o filtro ativo, preservando transparência e anotações.
   Saturação, brilho e contraste permanecem para uma etapa posterior.
7. **Referências — primeira versão implementada:** modo Refs com importação,
   soltura, colagem, seleção por caixa, movimento, escala proporcional,
   duplicação, exclusão, zoom e pan. Dados no projeto e histórico compartilhado;
   padrões nas Preferências. Grupos, anotações e comandos de sobreposição
   permanecem para uma etapa posterior. Consulte `REFERENCE_CANVAS.md`.

Mudanças de formato exigem migração explícita e proteção dos arquivos antigos.
Verificações automatizadas devem focar salvar/abrir, copiar, desfazer/refazer e
exportar. Não executar testes manuais sem solicitação.

## Revisão — precisão da timeline (registrada em 04/11/2026)

Revisar antes de ampliar a edição da montagem. A waveform é uma referência
crucial para sincronizar os cortes com música e áudio.

1. **Editar durações na montagem:** atualmente, arrastar a borda final dos
   blocos não permite ajustar os tempos nesse modo. Habilitar esse fluxo
   usando os mesmos nodes e histórico, preservando o ajuste entre quadros
   e Shift + arraste para empurrar os seguintes.
2. **Sincronização exata entre cena e montagem:** ao alternar os modos,
   a waveform aparenta mudar de alinhamento e a timeline é reenquadrada.
   Investigar a origem; zoom e enquadramento não podem alterar a relação
   temporal entre áudio, marcadores e quadros. Usar uma referência temporal
   comum e conversões explícitas entre o tempo local e o tempo da montagem,
   sem deslocamentos ou diferenças de duração. Preservar o zoom e a posição
   da vista ao alternar, sem reenquadramento automático inesperado.
3. **Cena isolada na posição da montagem:** ao isolar uma cena posterior,
   mostrar seu início após o fim da anterior, na posição temporal que ocupa
   no projeto, em vez de deslocá-la para zero. Manter a referência da música
   e da waveform para ajustar as trocas de cena com precisão.
4. **Áudio principal do projeto:** a trilha principal deve pertencer ao projeto,
   mantendo a continuidade entre cenas e montagem. Áudio próprio de uma cena
   pode existir como trilha opcional. Ao implementar, preservar e migrar
   explicitamente os áudios existentes, sem perda ou duplicação involuntária.
5. **Transferir imagens de Refs:** oferecer ações distintas para copiar a
   imagem ao clipboard e enviar as referências selecionadas ao Canvas.
   Enviar deve sempre criar nodes novos, mesmo quando já houver um node
   selecionado; nunca substituir suas mídias. Reaproveitar os fluxos de
   importação, propriedade dos dados e histórico.
6. **Preservar a câmera do Refs — problema ainda relatado:** após dar zoom e
   mover a vista, alternar para outro ambiente e voltar ainda desorganiza o
   enquadramento e tira de vista o conteúdo em uso. A correção incluída na
   v0.6.0 não resolveu integralmente o caso relatado. Investigar o ciclo
   completo de saída e retorno, preservando zoom e posição por projeto;
   enquadrar automaticamente apenas na primeira entrada, conforme o padrão
   configurado. Não reenquadrar nem reaplicar uma câmera antiga ao voltar.
7. **Remover marcador:** disponibilizar no menu do marcador e por Delete,
   com desfazer/refazer. Delete deve remover somente o elemento explicitamente
   selecionado; selecionar marcador e keyframe deve ser mutuamente exclusivo.
8. **Inverter mídia:** opções horizontal e vertical da mídia ativa, sem alterar
   o original, com persistência, histórico e resultado consistente na exportação.
9. **Keyframes fora do intervalo:** manter visíveis e editáveis os keys do
   quadro selecionado, inclusive quando a agulha estiver em outro quadro ou
   os keys estiverem além da duração atual. Não aumentar a duração do quadro
   por causa dessa visualização.

Reprodução relatada: abrir uma cena com áudio e marcadores, alternar para
Montagem, tentar ajustar a borda de um quadro e depois isolar a cena seguinte.
Conferir a mesma correspondência entre cortes, marcadores e waveform nos dois
contextos.

Os nove itens foram implementados no código em 04/11/2026, com verificações
automatizadas direcionadas; a confirmação de usabilidade fica com o usuário,
sem testes manuais do agente. O item 6 recebeu uma segunda correção: retenção
da matriz no cliente nativo durante a desmontagem/remontagem da interface.
Consulte `PROJECT_TIMING.md` para o contrato temporal e a migração do áudio.
