# Exportação MP4 interna

O Koma gera MP4 com **H.264 e áudio AAC**, usando o PyAV incluído no aplicativo.
Não requer Blender, FFmpeg instalado separadamente ou outro programa externo.
O comando continua em **Arquivo → Exportar → MP4** e no animatic.

O exportador respeita o formato e o FPS do projeto, cenas, intervalos, quadros
mutados, duração e enquadramento de cada mídia. Desenhos visíveis e legendas
habilitadas compõem os frames. Vídeos são cortados pela duração do node ou mantêm
o último frame quando terminam antes. Um intervalo que começa dentro de um vídeo
parte do instante correspondente, sem alterar o node.

## Dados de referência

Em **Dados de referência**, habilite cada campo que deseja gravar na imagem:
projeto, cena, sequência, quadro, duração em frames, duração em segundos, frame do
quadro, frame atual do vídeo, total de frames, tempo do vídeo, FPS e resolução.
As escolhas ficam nas preferências de exportação; o projeto e os nodes não são
alterados. Por padrão nenhum campo está ligado.

O botão **Dados de referência** (ícone de informação) no Animatic oferece as mesmas
escolhas. Os dados aparecem sobre a prévia e acompanham a agulha, sem ocupar
os blocos da timeline.

Por padrão, os contadores reservam quatro dígitos (`0009`, `0010`); o mínimo e
as casas decimais são configuráveis em Preferências > Timeline. Vídeos maiores
reservam mais dígitos desde o início. A renderização do MP4 usa células numéricas
de largura fixa, e os campos ao vivo também têm larguras estáveis, sem depender
da largura variável dos algarismos da fonte.

A faixa aparece por padrão no topo, com fundo translúcido e texto ajustado ao formato.
Estilo e posição podem ser alterados em Preferências > Dados de referência. Os
contadores começam em 1 e o tempo começa em 0 s. Frame atual e total correspondem
ao MP4 gerado, inclusive quando se exporta um intervalo. A duração em frames e
segundos corresponde ao trecho exportado de cada quadro, incluindo recorte e
eventual extensão pelo áudio. O nome e o número do quadro mantêm a identificação
de sua cena de origem. Legendas e desenhos continuam sendo compostos normalmente.

Os dados são derivados de um snapshot imutável dos mesmos nodes usados na
exportação. `reference_overlay` centraliza o catálogo dos campos e a renderização;
`StoryboardFrames` atualiza os contadores durante a codificação em segundo plano.
Os padrões estão em `assets/storyboard-reference.json`, sobrepostos pelas
preferências globais capturadas no início da exportação. Nenhuma renderização dessa
faixa ocorre durante os gestos do canvas ou da timeline.

O áudio das cenas é misturado em blocos de 1.024 amostras, a 48 kHz estéreo.
Entrada, volume, mute, recortes e sobreposições são preservados. Os espaços sem
áudio permanecem em silêncio, e a saída é limitada à duração da sequência.
O áudio embutido nas mídias de vídeo continua fora da trilha sonora do projeto.

## Responsabilidades

- `video_frames`: contrato de fontes de frames; lê o modelo ou arquivos preparados.
- `video_export`: contagem de frames e composição compartilhada de imagem,
  enquadramento, desenho e legenda. As sobreposições são preparadas uma vez por node.
- `video_audio`: validação das trilhas e mistura incremental de PCM.
- `video_encoder`: codificação H.264/AAC e verificação dos streams produzidos.
- `video_runner`: execução fora da interface, progresso, cancelamento, proteção
  das origens e publicação atômica.
- `file_actions`: coleta a seleção de exportação e apresenta o resultado.

O caminho principal lê os nodes diretamente: não cria vídeos intermediários nem
carrega a timeline inteira em memória. A interface recebe progresso com frequência
limitada. A saída só substitui o destino após conclusão e verificação; cancelamento,
falhas ou alterações externas preservam o arquivo existente. Fechar o aplicativo
aguarda a liberação dos arquivos antes de encerrar a sessão. Os logs de falha
registram a categoria do erro, sem imagens, áudio, legendas ou caminhos das mídias.

O `.koma` permanece no formato 6. A configuração antiga do Blender deixa de ser
usada; documentos, dados dos nodes e histórico não precisam de migração.

## Distribuição e verificações

O hook do PyInstaller coleta o PyAV e suas bibliotecas de codecs em `av.libs`.
O processo de build existente passa a verificar também um MP4 pelo executável
empacotado, sem recompilar o cliente Flutter por esta alteração em Python.

`tests/test_video_runner.py` verifica arquivos reais pequenos, áudio, desenhos,
legendas, intervalos, cancelamento, trabalho em segundo plano e publicação segura.
O diagnóstico opcional `--diagnostics RELATORIO.json --video` usa o mesmo exportador.
Não foram executados testes manuais nem gerada uma nova release nesta alteração.
