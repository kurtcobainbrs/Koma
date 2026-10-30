# Desempenho do canvas

- O cliente desktop usa o caminho local das miniaturas preparadas pelo documento.
  Duplicações reutilizam o mesmo arquivo imutável e o cache de imagens do Flutter,
  sem reenviar seus bytes em cada card. O caminho fica somente na apresentação;
  os nodes continuam guardando o nome do asset, e o formato dos projetos não muda.
  A apresentação por bytes continua disponível fora do cliente nativo.
- Cards preservam os controles existentes e só sincronizam seu conteúdo quando
  mudam seus dados, mídia, formato, FPS ou estado visual de seleção. Os atalhos
  continuam sendo atualizados pelo mecanismo próprio do catálogo.
- O início do movimento com G evita repetir a troca de ferramenta e a elevação
  do mesmo node. Eventos com a mesma posição não redesenham conexões. Apenas
  molduras que contêm nodes movidos têm seus limites recalculados.
- Durante o gesto, containers retidos usam a API `is_isolated` do Flet para
  impedir que atualizações dos pais percorram novamente o conteúdo dos cards.
  Atualizações explícitas continuam disponíveis, e mudanças pendentes são
  enviadas quando o gesto termina. O isolamento não congela os dados do modelo.
- Uma seleção com vários nodes que inclui toda a cena usa uma única translação
  temporária de sua camada de apresentação, incluindo conexões e molduras. A
  camada permanece na mesma árvore; não há recriação ou troca de pais dos cards
  ao ativar G. Confirmar aplica o deslocamento às posições dos nodes em uma
  operação; cancelar remove a translação. Seleções parciais mantêm o arraste
  individual e o conteúdo retido dos cards.
- A camada de translação usa apenas stacks de layout. Containers decorados de
  tela inteira interceptam cliques mesmo sem cor de fundo; por isso ficam fora
  desse caminho. O espaço vazio continua alcançando o gesto de fundo para limpar
  a seleção e iniciar a caixa, enquanto os nodes mantêm seus próprios eventos.
- O destaque de caminhos visita cada ligação uma vez por direção, mesmo quando
  vários nodes da mesma sequência estão selecionados. A geometria das portas
  é reaproveitada durante cada atualização. A prévia de desconexão com Alt é
  recalculada quando mudam seu documento ou sua seleção, e descartada ao sair.
- A leitura de miniaturas elimina arquivos repetidos e usa quatro leitores.
  A recuperação de miniaturas ausentes é serializada para limitar a memória da
  decodificação. O carregamento prepara cards em lotes com devolução de controle
  entre eles. Notificações de altura são agrupadas em uma atualização por ciclo,
  com cancelamento ao desmontar e recuperação das medidas ao reabrir a aba.

Os caches e os pedidos pendentes são estado temporário da interface, sem substituir
os dados dos nodes. Movimentos só alteram o documento ao confirmar; cancelamento,
desfazer/refazer, assets compartilhados e salvamento mantêm seus contratos.

Em medições automatizadas isoladas de 28/10/2026, o destaque de uma cadeia de
512 nodes com todos selecionados foi aproximadamente 113 vezes mais rápido.
No envio inicial de 20 miniaturas iguais, o pacote de controles caiu de 4.232.318
para 1.858 bytes ao usar um arquivo local. Esses valores medem operações específicas,
não a velocidade total do aplicativo. Não foram realizados testes manuais.

Na revisão do início de G, um caso automatizado com 256 nodes selecionados,
incluindo a serialização real de atualizações do Flet, mediu aproximadamente
144 ms para ativar e 195 ms para preparar o primeiro movimento antes do isolamento.
Com conteúdo retido e translação conjunta, os mesmos passos mediram cerca de
8 ms e 0,75 ms. Essa medição não inclui a renderização da janela nativa.

O ajuste de duração na timeline também usa bloqueio lógico durante o gesto,
sem reenviar o canvas na ativação. Os snapshots validam somente os números de
tempo alterados, preservando imagens e desenhos imutáveis. Veja
[Ajuste de duração](TIMELINE_TRIM.md). A fluidez desde o primeiro movimento é
uma diretriz permanente em `AGENTS.md`.

## Atualizações após a reorganização visual

Selecionar nodes agrupa bordas, propriedades e barras em uma atualização. As
partes estáveis dos cards são retidas durante esse patch; elevar um card altera
a ordem da camada sem percorrer suas imagens. Mudar a cor/espessura do destaque
de uma conexão reaproveita sua curva e seus pontos de amostragem.

O Canvas permanece montado, preservando sua câmera e seus reconhecedores de
gestos. O Animatic ocupa a outra superfície somente enquanto aberto; ao sair,
sua parte visual é desmontada. Mantê-lo montado atrás do Canvas deixava
observadores e controles nativos ativos desnecessariamente. Eventos atrasados
de tamanho e rolagem são descartados antes de recalcular prévias, desenhos ou
trilhas quando o Animatic ou a aba estão inativos. A transição
cancela o estado temporário do mouse e reaplica a configuração da navegação
depois de liberar teclas temporárias. A timeline é reutilizada se documento e
cena não mudaram; alterações do modelo invalidam esse reaproveitamento.

Durante o ajuste da duração, geometria e valores temporais continuam sendo
enviados, mas o patch não percorre imagens, desenhos e waveform estáveis.
`retain_children` limita esse isolamento a uma atualização síncrona e restaura
o comportamento normal ao sair, inclusive quando ocorre uma exceção.

`test_interaction_workload` executa o diff real do Flet e impede a travessia
dessas partes pesadas durante as interações. A regressão Flutter verifica ciclos
entre modos, identidade da câmera e destino dos cliques; a integração Python
verifica desmarcar e selecionar por caixa após esses ciclos. Essas verificações
não medem a fluidez visual completa na máquina do usuário.
O teste nativo também monta os controles reais no perfil Windows, com
acessibilidade ativa, e confirma que a câmera sobrevive aos ciclos e que não há
novos quadros agendados depois de remover a superfície do Animatic. Eventos
atrasados de layout/rolagem são injetados separadamente na integração Python;
eles não podem produzir patches nem reconstruir a timeline quando inativos.

## Foco e encerramento da conexão

Canvas e Animatic compartilham `FocusRequests`. Há uma chamada nativa de foco
por editor e, durante essa chamada, somente o destino mais recente é guardado.
Pedidos repetidos para o mesmo destino não criam tarefas adicionais. Trocar de
modo/aba invalida pedidos antigos; fechar ou desconectar impede novos pedidos.
A reconexão direciona o foco somente à área ativa.

`FocusListener` limita a chamada nativa a cinco segundos usando o prazo do
próprio transporte do Flet. A chamada já enviada termina nesse prazo, permitindo
que o transporte libere seu callback. `Session closed` é tratado como término
da conexão; outros erros inesperados de foco continuam visíveis. Esse erro,
isoladamente, não identifica o motivo original de uma desconexão do cliente.

## Eventos sem alterações visuais

O início dos gestos de desenho e as trocas de ferramenta também publicam apenas
os controles locais e a camada de desenho. Não atualizam a imagem de prévia, a
timeline, a waveform ou o canvas. O orçamento de pontos é calculado no início do
traço e posições repetidas não provocam redesenho. Confirmação mantém um registro
no histórico; cancelar restaura a camada confirmada usando o mesmo caminho local.

O Flet 1.0.5 executa `Session.after_event` depois do callback. Quando não há
um update explícito, ele procura um ancestral isolado e pode calcular o diff
da página inteira. Isso ocorria mesmo em hover sem conexão, teclas liberadas,
medidas repetidas e eventos descartados. Testar somente os métodos do editor
ou interceptar suas chamadas a `page.update` não cobria esse custo implícito.

`ui.event_updates.explicit_updates` define o contrato dos eventos de interação:
o callback publica as mudanças locais necessárias; retornar sem mudança não
provoca um diff de ancestral. A política é restrita ao contexto do evento,
preserva funções assíncronas e não altera os widgets nem a configuração global
do Flet. Canvas, teclado, conexões, gestos de timeline, desenho e divisores usam
esse contrato. As demais telas mantêm o comportamento padrão do framework.

`tests/test_event_updates.py` usa `Session.dispatch_event` real, reproduz o update
implícito com o callback anterior e verifica sua ausência no caminho corrigido,
incluindo uma sequência de eventos. Verifica também que updates explícitos ainda
funcionam e que a política não afeta outro evento comum. A seleção finaliza com
um patch local, e medidas idênticas da superfície de desenho não a redesenham.
Essas verificações não equivalem a medir toda a fluidez ou diagnosticar qualquer
possível encerramento nativo. Não foram realizados testes manuais.
