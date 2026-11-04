# Transformação e keyframes

No Animatic, o controle junto à borda direita do preview abre o painel lateral de transformação,
recolhível e redimensionável. Clique no valor para digitar ou arraste para ajustar;
soltar confirma e Esc cancela a prévia do arraste. G, S e R escolhem mover,
escalonar e girar imediatamente, seguindo o mouse sem manter um botão pressionado.
Clique esquerdo ou Enter confirma; botão direito ou Esc cancela. Os botões das
ferramentas iniciam o mesmo gesto. Também é possível clicar e arrastar no preview;
soltar confirma uma operação no histórico. Esc novamente sai da edição da mídia.
O movimento continua quando o cursor sai do preview, dentro da janela do app.
Os campos X/Y e escala usam porcentagens; giro usa graus. Aceitam expressões
aritméticas e Enter confirma. Desenhos continuam em sua camada independente.
Durante G, X restringe à horizontal e Y à vertical, com uma guia do eixo ativo.
Pressionar o mesmo eixo novamente libera o movimento.

I ou o diamante grava a pose da prévia na agulha, adicionando ou sobrescrevendo
o keyframe existente. Não apaga uma chave ao pressionar novamente. A barra compacta
junto à reprodução reúne Auto Key, Gravar/Atualizar, Excluir e interpolação.
Botões próprios avançam/recuam entre keyframes; os de quadro/marcador permanecem
separados. Repetir e Legendas ficam à direita da reprodução. O painel lateral
mantém somente as ferramentas e valores da transformação.
Delete e Alt+I removem somente a chave. A navegação e seleção das chaves ficam na timeline.
Uma trilha fina **Keyframes**, abaixo dos quadros, mostra as chaves da mídia
atual. Clique para selecionar, arraste para reposicionar em frames inteiros e
use Delete para excluir. Esc cancela o arraste; sobrepor uma chave existente
é recusado preservando os dados. A agulha não precisa acompanhar o arraste.
Excluir chaves nunca altera a transformação base. A pose visível permanece como
prévia temporária, inclusive após desfazer/refazer a exclusão. Play volta aos
dados salvos; I grava a prévia explicitamente. Os campos exibem um único valor:
o modo de leitura arrastável e o campo de digitação são mutuamente exclusivos.
Com Auto Key desligado, transformar não altera dados nem histórico: a pose é
temporária, mesmo quando já existem keyframes. Play descarta essa prévia e usa
a animação salva. I grava explicitamente a pose temporária. Com Auto Key ligado,
confirmar uma transformação grava a chave no tempo atual. Ao iniciar uma animação
fora do começo do quadro, a pose inicial é registrada no tempo zero.
Alt+G zera X/Y, Alt+R zera o giro e Alt+S restaura a escala. Esses resets seguem
a mesma regra de Auto Key; desligado, permanecem temporários até gravar com I.
Interpolação Linear ou Constante vale da chave atual até a próxima.

Cada mídia possui sua própria pose e tupla de keyframes dentro do node.
Trocar mídia não mistura animações nem altera a duração. Posições são frações
da tela, escala é proporcional e giro tem sentido horário. O tempo é local
ao quadro, em segundos, com criação das chaves alinhada aos frames do projeto.
Alterar a duração não destrói chaves posteriores; as que ficam fora do quadro
são preservadas e não participam da reprodução até estender sua duração.

Canvas, miniaturas e PDF mostram a pose no início do quadro. O Animatic e o
MP4 avaliam a animação no tempo local, inclusive ao exportar intervalos.
Filtros atuam somente na mídia; legendas, desenhos e guias não são transformados.

O formato de documento 11 adiciona pose e keyframes ao `MediaTransform`.
Documentos anteriores recebem a transformação neutra, sem animação. Salvar,
reabrir, copiar nodes e desfazer/refazer preservam esses dados. Limites de
tempo, escala, deslocamento e número de chaves ficam em `media_animation.py`.
Keyframe automático e interpolação iniciais ficam em Preferências > Animatic.

Os movimentos do mouse são resolvidos no cliente nativo, sem tráfego de prévias
para o Python nem gravações por movimento. Somente a confirmação atualiza o
documento; o MP4 usa composição por quadro em fluxo, sem armazenar o filme.
A reprodução das transformações usa o relógio de quadros do cliente, sem
depender da frequência das atualizações Python ou arredondar o tempo entre
keyframes. A edição continua alinhada a frames inteiros.
