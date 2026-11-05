# Koma

O Koma é um aplicativo para criar storyboards e animatics no Windows. Organize cenas e planos, teste o ritmo com áudio na timeline e compartilhe o resultado em PDF ou MP4.

## Baixar e abrir

Na página de [versões para Windows](https://github.com/kurtcobainbrs/Koma/releases), abra a versão desejada e escolha um dos arquivos em **Assets**.

- **Instalador (`setup.exe`)** — execute o arquivo e siga as instruções.
- **Portátil (`portable.zip`)** — extraia o ZIP inteiro e abra `Koma.exe` na pasta extraída.

Os dois pacotes são para Windows x64 e já incluem o necessário para rodar o Koma. As notas de cada versão indicam os recursos disponíveis naquele pacote.

## Do storyboard ao animatic

1. **Canvas** — arraste uma imagem do Explorador para um espaço vazio para criar um quadro. Conecte os quadros na ordem desejada a partir de um início de cena. Selecione um quadro para ajustar a duração, o enquadramento e o roteiro no painel de propriedades.
2. **Animatic** — abra o modo para ver a **Montagem** do projeto ou escolha uma cena na lista lateral. Pressione **Espaço** para reproduzir ou pausar. Arraste a borda de um quadro na timeline para ajustar sua duração. Use a roda do mouse ou o slider para mudar o zoom. Você pode adicionar áudio, marcadores, desenhos e keyframes.
3. **Refs** — reúna imagens de inspiração numa área separada do storyboard. Selecione e envie as imagens que quiser usar para criar quadros no Canvas.

Canvas e Animatic mostram os mesmos quadros. Alterações feitas em um modo aparecem no outro.

## Salvar e compartilhar

- **Projeto `.koma`** — use **Arquivo → Salvar** ou **Ctrl+S** para guardar um projeto editável com suas mídias. Para abrir um existente, use **Arquivo → Abrir** ou arraste o `.koma` para a janela. Você pode trabalhar com vários projetos em abas.
- **Storyboard em PDF** — em **Arquivo → Exportar → PDF**, ajuste a folha e os campos incluídos. Use a prévia para conferir a distribuição dos quadros antes de exportar.
- **Animatic em MP4** — use **Exportar MP4** no Animatic. Escolha a cena, o conjunto de cenas ou o projeto completo e ajuste o intervalo e as opções de exportação.

Use **Arquivo → Projeto** para ajustar a proporção da imagem e o FPS. Os atalhos e a aparência ficam em **Editar → Preferências**. Se o aplicativo fechar inesperadamente, procure sua sessão em **Arquivo → Recuperar sessão**.

Para instruções de desenvolvimento, testes e publicação, consulte o [AGENTS.md](AGENTS.md).
