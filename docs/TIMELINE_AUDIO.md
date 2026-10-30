# Áudio, waveform e marcadores

Na prévia do animatic, o botão de arquivo de áudio importa ou substitui a trilha
da cena. São aceitos WAV, MP3, FLAC e OGG. O campo **Início (f)** define a entrada
em frames e aceita expressões; Enter confirma. Os botões de volume e lixeira
mutam ou removem a trilha. Essas operações participam do desfazer/refazer.

O botão de adicionar marcador abre nome e posição, inicialmente na agulha.
Clique na bandeira para navegar; duplo clique permite editar ou excluir.
As setas navegam pelos marcadores e o menu de bandeira lista todos os nomes.
Marcadores usam posições alinhadas ao FPS, sem alterar a duração dos quadros.

A waveform, a régua, os quadros e os marcadores compartilham a mesma escala e
rolagem. F enquadra a sequência inteira e a roda aproxima/afasta sob o cursor.
A reprodução mantém o último quadro até o fim da trilha, quando necessário.
O MP4 exportado pelo PyAV inclui o áudio ativo em AAC; áudio mutado é omitido.

## Organização

- `editor/media_models.py`: dados imutáveis e limites de trilhas e marcadores.
- `documents/audio.py`: decodificação por miniaudio, normalização PCM e cache de picos.
- `audio_transport.py`: saída nativa, comandos serializados e streaming fora da interface.
- `editor/timeline_media.py`: importação, comandos de edição, histórico e recuperação.
- `ui/timeline_audio.py`: waveform, controles e formulário de marcadores.
- `editor/timeline.py`: seleção da cena e duração comum da reprodução/exportação.
- `documents/bundle.py` e `documents/session.py`: mídia portátil e validação ao abrir/recuperar.
- `exports/video_audio.py`, `exports/video_encoder.py` e `exports/video_runner.py`: mistura de áudio, codificação e publicação segura.

A leitura e a normalização são incrementais, fora da interface, limitadas a uma
hora e 750 MB por áudio. O arquivo original permanece intacto. Cada cena tem uma
trilha substituível; documentos sem Node Principal usam a trilha do storyboard.
Os modelos guardam identidade, origem interna, duração, início, volume e mute.
Remover uma cena remove suas referências de áudio e marcadores no mesmo passo
do histórico. Arquivos internos continuam disponíveis durante a sessão para undo.

A waveform usa uma pirâmide de picos. Somente a região visível e a resolução
adequada ao zoom viram desenho; o cache de formas em memória tem limite e os
arquivos de picos podem ser regenerados. O cache não faz parte do `.koma`.
O áudio usa o relógio monotônico do player e streaming PCM com buffer de 50 ms;
pausa, busca, repetição e troca de documento interrompem/reposicionam a saída.
Essa latência de saída é própria da reprodução, não altera os tempos do arquivo.

## Compatibilidade e integridade

Ao arrastar um marcador, a agulha e a imagem de prévia permanecem paradas.
O gesto atualiza apenas a bandeira e sua linha vertical; não redesenha o player,
as miniaturas, a waveform ou o canvas. O início usa bloqueio lógico, sem atualizar
todo o editor. Soltar inclui a última posição do mouse e confirma uma única ação
no histórico; Esc descarta a prévia. Clicar no marcador continua buscando seu tempo.

O manifesto passou à versão 2. Projetos da versão 1 continuam abrindo com listas
vazias de áudio/marcadores. Ao salvar, a versão 2 impede que um cliente antigo
abra o projeto e descarte silenciosamente esses dados.
As cópias normalizadas ficam em `audio/<uuid>.wav` dentro do pacote, sem caminhos
externos no manifesto. Abertura, recuperação e salvamento verificam o conteúdo,
a duração e os limites; áudio truncado ou arquivos inesperados são rejeitados.
O limite total de 2 GB e a publicação atômica do pacote foram preservados.

`tests/test_timeline_audio.py` cobre importação, cache, cancelamento, PCM,
portabilidade, recuperação, dados inválidos, histórico e escopo por cena.
`scripts/validate_timeline_audio.py --video` gera um projeto independente e
valida o backend nativo sem saída sonora, a reabertura e um MP4 real com streams
de vídeo e áudio. O relatório fica no diretório de validação em `build/`.
A distribuição empacotada aprovada não foi substituída nesta implementação.
