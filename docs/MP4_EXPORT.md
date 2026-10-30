# Exportação MP4 interna

O Koma gera MP4 com **H.264 e áudio AAC**, usando o PyAV incluído no aplicativo.
Não requer Blender, FFmpeg instalado separadamente ou outro programa externo.
O comando continua em **Arquivo → Exportar → MP4** e no animatic.

O exportador respeita o formato e o FPS do projeto, cenas, intervalos, quadros
mutados, duração e enquadramento de cada mídia. Desenhos visíveis e legendas
habilitadas compõem os frames. Vídeos são cortados pela duração do node ou mantêm
o último frame quando terminam antes. Um intervalo que começa dentro de um vídeo
parte do instante correspondente, sem alterar o node.

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
