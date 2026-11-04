# Tempo do projeto e áudio

A montagem e as cenas isoladas usam o mesmo eixo absoluto. O início de uma
cena é a soma da duração dos quadros das cenas anteriores; isolar uma cena
não desloca quadros, waveform ou marcadores para zero. A reprodução isolada
fica limitada ao intervalo da cena, mantendo sua posição na timeline.
Trocar cena/montagem preserva o zoom e a rolagem.

`project_time.project_layout` percorre uma única hierarquia e fornece os
intervalos das cenas para player, migração e exportação. Nodes desconectados
de cenas não entram na montagem. A duração do áudio não aumenta a duração
dos quadros. Áudio além do intervalo visual permanece no projeto, mas não
prolonga automaticamente o último quadro nem desloca as cenas seguintes.

## Trilhas

O seletor de áudio usa **Projeto** por padrão; **Cena** adiciona ou substitui
uma trilha opcional da cena aberta. Na montagem, a trilha editável é a do
projeto. `Storyboard.audio_tracks` continua sendo a fonte dos dados:
`scene_id` vazio indica áudio do projeto; uma cena indica áudio local opcional.
A posição de uma trilha de cena é armazenada localmente e projetada uma única
vez no eixo absoluto. Áudio de cena é limitado ao intervalo daquela cena.

Waveform e reprodução usam as mesmas posições. O transporte mistura as trilhas
audíveis em blocos, fora da interface, sem carregar o áudio inteiro. MP4 usa os
mesmos intervalos; exportar uma cena ou um recorte conserva o deslocamento
correto na música. Janelas contínuas da mesma fonte são reunidas para evitar
abrir o mesmo arquivo uma vez por cena.

O formato 12 promove a primeira trilha de cena existente a trilha do projeto,
mantendo identificador, arquivo, volume, mute e posição absoluta. As demais
continuam como trilhas opcionais de cena. Se já houver áudio do projeto,
a migração preserva a organização existente. Nodes e suas durações não mudam.
Arquivos salvos no formato 12 precisam desta versão do aplicativo ou posterior.

## Edição

Arrastar a borda ajusta a duração entre dois quadros também na montagem;
Shift + arrastar empurra os seguintes. A prévia usa os mesmos nodes, sem
validar desenhos ou reconstruir o grafo a cada movimento. Soltar confirma
uma alteração no histórico; cancelar descarta a prévia.

Novos marcadores usam o tempo do projeto. Marcadores antigos ligados a cenas
mantêm seus dados locais, com conversão explícita na visualização e edição.
Delete atua somente na seleção explícita: marcador, keyframe ou desenho.
Selecionar um desses elementos limpa as seleções dos demais. Alt+I mantém a
ação explícita de remover o keyframe no tempo atual. O menu do marcador oferece
Renomear e Remover, reutilizando os mesmos comandos e histórico.

## Snap e início do áudio

O ímã e o atalho S controlam o mesmo snap para agulha, cortes, keyframes,
marcadores e áudio. Os alvos incluem limites de shots e cenas, marcadores,
keys da mídia ativa de cada quadro e extremos de áudio. O índice é preparado
fora dos movimentos do mouse; o gesto conserva sua escala e seus alvos,
ignorando o próprio elemento em movimento. A tolerância é medida em pixels,
mantendo o comportamento ao trocar de zoom. Desligar o ímã mantém apenas o
alinhamento a frames inteiros.

Início aceita expressões negativas. Por exemplo, -48 f em 24 FPS avança dois
segundos no arquivo de áudio. O modelo guarda esse início assinado; a projeção
de reprodução/exportação calcula o recorte da fonte sem alterar o arquivo.
Waveform, áudio do projeto, áudio opcional da cena e MP4 usam esse mesmo recorte.
O formato 13 explicita o suporte a início negativo; documentos até a versão 12
mantêm seus valores existentes, sem nova reorganização de trilhas.

O seletor de áudio lembra a última pasta escolhida entre sessões e projetos,
separadamente das imagens. Esse estado pertence ao aplicativo, em
dialog-directories.json; cancelar a seleção não altera a pasta lembrada.

Os dados de referência usam rótulos compactos por padrão (Proj., Seq., Dur.,
Quadro). Nomes e valores completos quebram de linha na prévia; a exportação
também preserva os nomes inteiros, sem reticências. Contadores continuam com
largura numérica estável e respeitam as Preferências.
